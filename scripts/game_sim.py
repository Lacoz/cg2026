"""
Minimal TryAngle Catch referee (Bronze: MOVE + SPAWN) for local bot tests.
Logic aligned with github.com/eulerscheZahl/TryAngle-Catch (Node, Triangle, Board).
"""
from __future__ import annotations

import subprocess
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

Coord = Tuple[int, int]


def ccw(a: Coord, b: Coord, c: Coord) -> bool:
    return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])


def point_in_triangle(p: Coord, a: Coord, b: Coord, c: Coord) -> bool:
    if p in (a, b, c):
        return False
    ccw1, ccw2, ccw3 = ccw(p, a, b), ccw(p, b, c), ccw(p, c, a)
    has_neg = not ccw1 or not ccw2 or not ccw3
    has_pos = ccw1 or ccw2 or ccw3
    return not (has_neg and has_pos)


@dataclass
class Triangle:
    a: int
    b: int
    c: int
    owner: Optional[int] = None  # None neutral, 0 me, 1 opp
    initial_owner: Optional[int] = None
    can_capture: List[bool] = field(default_factory=lambda: [True, True])

    def corners(self) -> Tuple[int, int, int]:
        return self.a, self.b, self.c

    def has_node(self, n: int) -> bool:
        return n in (self.a, self.b, self.c)

    def update_allowed_captures(self, units: Dict[int, List[int]]) -> None:
        for i in range(2):
            if self.owner is not None:
                self.can_capture[i] = self.owner != i
            else:
                u = units
                all_zero = all(u[n][i] == 0 for n in self.corners())
                self.can_capture[i] = self.can_capture[i] or all_zero

    def capture_if_possible(self, board: "Board") -> bool:
        old = self.owner
        for pid in (0, 1):
            if not self.can_capture[pid]:
                continue
            if all(board.node_owned(n, pid) for n in self.corners()):
                self.owner = pid
        return self.owner != old

    def can_use(self, pid: int, remaining: Dict[int, List[int]]) -> bool:
        if self.owner != pid or self.initial_owner != pid:
            return False
        return all(remaining[n][pid] >= 0 for n in self.corners())

    def use_spawn(self, pid: int, spawn_node: int, units: Dict[int, List[int]], remaining: Dict[int, List[int]]) -> None:
        for n in self.corners():
            take = min(0, units[n][pid])  # use(0) in referee
            units[n][pid] -= take
            remaining[n][pid] -= take
        self.can_capture[pid] = False
        self.owner = None
        units[spawn_node][pid] += 1


@dataclass
class Board:
    coords: Dict[int, Coord]
    adj: Dict[int, Set[int]]
    units: Dict[int, List[int]]  # [me, opp]
    remaining: Dict[int, List[int]]
    triangles: List[Triangle]
    scores: List[int] = field(default_factory=lambda: [0, 0])
    turn: int = 0

    @staticmethod
    def from_game_options(text: str) -> "Board":
        opts = {}
        for line in text.strip().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                opts[k.strip()] = v.strip()
        nodes = opts["nodes"].split("_")
        coords: Dict[int, Coord] = {}
        for i, part in enumerate(nodes):
            x, y = map(int, part.split(","))
            coords[i] = (x, y)
        adj: Dict[int, Set[int]] = {i: set() for i in coords}
        for part in opts["edges"].split("_"):
            a, b = map(int, part.split(","))
            adj[a].add(b)
            adj[b].add(a)
        units: Dict[int, List[int]] = {i: [0, 0] for i in coords}
        for i, part in enumerate(opts["units"].split("_")):
            u0, u1 = map(int, part.split(","))
            units[i] = [u0, u1]
        b = Board(coords, adj, units, {}, [])
        b.remaining = {n: u[:] for n, u in units.items()}
        b.triangles = discover_triangles(coords, adj)
        while b._finalize_subturn():
            pass
        return b

    def reset_remaining(self) -> None:
        self.remaining = {n: u[:] for n, u in self.units.items()}

    def bfs_dist(self, target: int) -> Dict[int, int]:
        dist = {target: 0}
        q = deque([target])
        while q:
            u = q.popleft()
            for v in self.adj.get(u, ()):
                if v not in dist:
                    dist[v] = dist[u] + 1
                    q.append(v)
        return dist

    def node_owner(self, n: int) -> Optional[int]:
        u = self.units[n]
        neigh = self.adj.get(n, set())
        if neigh:
            if all(self.units[v][0] > self.units[v][1] for v in neigh):
                return 0
            if all(self.units[v][1] > self.units[v][0] for v in neigh):
                return 1
        if u[0] > u[1]:
            return 0
        if u[1] > u[0]:
            return 1
        return None

    def node_owned(self, n: int, pid: int) -> bool:
        return self.node_owner(n) == pid

    def apply_move(self, pid: int, src: int, dst: int, amount: int) -> bool:
        if src == dst or amount <= 0:
            return False
        if self.remaining[src][pid] <= 0:
            return False
        dist = self.bfs_dist(dst)
        if src not in dist or dist[src] == 0:
            return False
        amount = min(amount, self.remaining[src][pid])
        # one step toward dst
        for nxt in self.adj.get(src, ()):
            if dist.get(nxt, 10**9) < dist[src]:
                self.units[src][pid] -= amount
                self.remaining[src][pid] -= amount
                self.units[nxt][pid] += amount
                return True
        return False

    def apply_spawn(self, pid: int, spawn: int, n2: int, n3: int) -> bool:
        tri = next(
            (t for t in self.triangles if t.has_node(spawn) and t.has_node(n2) and t.has_node(n3)),
            None,
        )
        if tri is None or not tri.can_use(pid, self.remaining):
            return False
        tri.use_spawn(pid, spawn, self.units, self.remaining)
        return True

    def parse_commands(self, pid: int, line: str) -> None:
        line = line.strip()
        if not line or line == ";":
            return
        moves, spawns = [], []
        for cmd in line.split(";"):
            cmd = cmd.strip()
            if not cmd:
                continue
            parts = cmd.split()
            if parts[0].upper() == "MOVE" and len(parts) == 4:
                moves.append((int(parts[1]), int(parts[2]), int(parts[3])))
            elif parts[0].upper() == "SPAWN" and len(parts) == 4:
                spawns.append((int(parts[1]), int(parts[2]), int(parts[3])))
        for src, dst, amt in moves:
            self.apply_move(pid, src, dst, amt)
        for sp in spawns:
            self.apply_spawn(pid, *sp)

    def surround(self) -> bool:
        changed = False
        advantage: List[Set[int]] = []
        for pid in (0, 1):
            adv = set()
            for n in self.coords:
                if self.units[n][pid] > self.units[n][1 - pid]:
                    adv.add(n)
            advantage.append(adv)
        for pid in (0, 1):
            opp = 1 - pid
            for n in self.coords:
                if self.units[n][pid] <= 0:
                    continue
                neigh = self.adj.get(n, set())
                if neigh and all(v in advantage[opp] for v in neigh):
                    self.units[n][pid] = 0
                    changed = True
        return changed

    def capture_triangles(self) -> bool:
        any_cap = False
        for t in self.triangles:
            any_cap |= t.capture_if_possible(self)
        return any_cap

    def _finalize_subturn(self) -> bool:
        for t in self.triangles:
            t.update_allowed_captures(self.units)
        if self.surround() or self.capture_triangles():
            return True
        for t in self.triangles:
            if t.owner is not None:
                self.scores[t.owner] += 1
            t.initial_owner = t.owner
        return False

    def end_turn(self) -> None:
        self.reset_remaining()
        while self._finalize_subturn():
            pass
        self.turn += 1

    def play_turn(self, cmd_p0: str, cmd_p1: str = "") -> None:
        self.reset_remaining()
        for t in self.triangles:
            t.initial_owner = t.owner
        self.parse_commands(0, cmd_p0)
        self.parse_commands(1, cmd_p1)
        self.end_turn()

    def bot_input(self, pid: int = 0) -> str:
        lines = [f"{self.scores[pid]} {self.scores[1-pid]}"]
        for n in sorted(self.coords):
            lines.append(f"{n} {self.units[n][0]} {self.units[n][1]}")
        edges = []
        seen = set()
        for a in sorted(self.adj):
            for b in sorted(self.adj[a]):
                if (a, b) not in seen and (b, a) not in seen:
                    seen.add((a, b))
                    edges.append(f"{a} {b}")
        lines.append(str(len(edges)))
        lines.extend(edges)
        lines.append(str(len(self.triangles)))
        for t in self.triangles:
            owner = -1 if t.owner is None else (0 if t.owner == 0 else 1)
            me = 1 if t.can_capture[0] else 0
            op = 1 if t.can_capture[1] else 0
            a, b, c = t.corners()
            lines.append(f"{a} {b} {c} {owner} {me} {op}")
        lines.append("0")
        return "\n".join(lines) + "\n"

    def total_units(self, pid: int = 0) -> int:
        return sum(self.units[n][pid] for n in self.coords)

    def owned_triangles(self, pid: int = 0) -> int:
        return sum(1 for t in self.triangles if t.owner == pid)


def discover_triangles(coords: Dict[int, Coord], adj: Dict[int, Set[int]]) -> List[Triangle]:
    tris: List[Triangle] = []
    nodes = sorted(coords)
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            if b not in adj[a]:
                continue
            for c in nodes:
                if c <= b or c not in adj[a] or c not in adj[b]:
                    continue
                if any(
                    point_in_triangle(coords[p], coords[a], coords[b], coords[c])
                    for p in coords
                ):
                    continue
                tris.append(Triangle(a, b, c))
    return tris


class BotSession:
    """One long-lived bot process (same as CodinGame — TARGET etc. persist)."""

    def __init__(self, bot_path: Path):
        self.proc = subprocess.Popen(
            [sys.executable, str(bot_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert self.proc.stdin and self.proc.stdout
        init = ""
        # caller must send house_count + houses first via start()

    def start(self, board: Board) -> None:
        init = f"{len(board.coords)}\n"
        for n in sorted(board.coords):
            x, y = board.coords[n]
            init += f"{n} {x} {y}\n"
        self.proc.stdin.write(init)
        self.proc.stdin.flush()

    def turn(self, board: Board, pid: int = 0) -> str:
        self.proc.stdin.write(board.bot_input(pid))
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"bot exited: {err}")
        return line.strip()

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
        if self.proc.stdin:
            self.proc.stdin.close()
        if self.proc.stdout:
            self.proc.stdout.close()


def run_bot_once(board: Board, bot_path: Path, pid: int = 0) -> str:
    """Single-turn helper (stateless — only for smoke tests)."""
    s = BotSession(bot_path)
    s.start(board)
    out = s.turn(board, pid)
    s.close()
    return out


def load_seed_options(seed: int) -> str:
    """Load game_options from results/runs.jsonl if present, else caller supplies."""
    raise NotImplementedError


SEED_4034019036303909000 = """seed=4034019036303909000
units=0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_1,0_0,1_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,1_1,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_0,0_1,0_0,1
edges=0,6_0,23_0,43_1,7_1,22_1,42_2,23_2,24_2,32_2,45_3,22_3,25_3,33_3,44_4,7_4,22_4,34_5,6_5,23_5,35_6,7_6,9_6,20_6,21_7,8_7,20_7,21_8,34_9,35_10,22_10,31_10,39_11,23_11,30_11,38_12,20_12,43_13,21_13,42_14,33_14,36_15,32_15,37_16,25_16,27_16,29_16,42_17,24_17,26_17,28_17,43_18,29_18,36_18,41_19,28_19,37_19,40_20,40_20,43_21,41_21,42_22,25_22,31_22,42_23,24_23,30_23,43_24,26_24,32_25,27_25,33_26,28_26,32_27,29_27,33_30,38_31,39_32,45_33,44_34,40_35,41_38,45_39,44
nodes=1269,601_650,358_1691,627_228,332_712,196_1207,763_1030,553_889,406_1097,189_822,770_497,94_1422,865_1174,478_745,481_89,644_1830,315_538,737_1381,222_473,861_1446,98_1210,324_709,635_489,287_1430,672_1576,470_343,489_1681,325_238,634_1639,152_280,807_1620,812_299,147_1805,532_114,427_933,150_986,809_127,844_1792,115_1780,857_139,102_1241,81_678,878_548,457_1371,502_86,239_1833,720"""
