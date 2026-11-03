import sys
from collections import deque
from typing import Dict, List, Optional, Tuple

houses: Dict[int, Tuple[int, int]] = {}
adj: Dict[int, set] = {}
paths: Dict[int, Dict[int, List[int]]] = {}

# Držíme jeden trojuholník, kým ho neobsadíme (owner == 0).
TARGET: Optional[Tuple[int, int, int]] = None


def add_edge(a: int, b: int) -> None:
    adj.setdefault(a, set()).add(b)
    adj.setdefault(b, set()).add(a)


def bfs_all_sources() -> None:
    global paths
    paths = {h: {} for h in houses}
    for src in houses:
        parent = {src: None}
        q = deque([src])
        while q:
            u = q.popleft()
            for v in adj.get(u, ()):
                if v not in parent:
                    parent[v] = u
                    q.append(v)
        for dst in parent:
            if dst == src:
                paths[src][dst] = [src]
                continue
            cur = dst
            rev: List[int] = []
            while cur is not None:
                rev.append(cur)
                cur = parent[cur]
            paths[src][dst] = list(reversed(rev))


def dist(a: int, b: int) -> int:
    p = paths.get(a, {}).get(b)
    return len(p) - 1 if p else 10**9


def next_step(src: int, dst: int) -> Optional[int]:
    if src == dst:
        return None
    p = paths.get(src, {}).get(dst)
    if not p or len(p) < 2:
        return None
    return p[1]


def movable(h: int, my_u: Dict[int, int], opp_u: Dict[int, int]) -> int:
    m, o = my_u.get(h, 0), opp_u.get(h, 0)
    if m <= 0:
        return 0
    if o > 0 and m <= o:
        return 0
    if o > 0:
        return m - o
    return m


def triangle_by_corners(
    triangles: List[Tuple[int, int, int, int, bool, bool]],
    corners: Tuple[int, int, int],
) -> Optional[Tuple[int, int, int, int, bool, bool]]:
    s = frozenset(corners)
    for t in triangles:
        if frozenset((t[0], t[1], t[2])) == s:
            return t
    return None


def pick_target(
    triangles: List[Tuple[int, int, int, int, bool, bool]],
    my_u: Dict[int, int],
) -> Tuple[int, int, int]:
    global TARGET
    unit_houses = [h for h in houses if my_u.get(h, 0) > 0]

    if TARGET is not None:
        info = triangle_by_corners(triangles, TARGET)
        if info is not None and info[3] == 0:
            TARGET = None
        elif info is not None and info[4]:
            return TARGET

    best_corners: Optional[Tuple[int, int, int]] = None
    best_cost = 10**18

    for a, b, c, owner, me_cap, _ in triangles:
        if not me_cap:
            continue
        corners = (a, b, c)
        cost = 0
        for corner in corners:
            cost += min(dist(u, corner) for u in unit_houses)
        if cost < best_cost:
            best_cost = cost
            best_corners = corners

    if best_corners is None:
        for a, b, c, owner, me_cap, _ in triangles:
            corners = (a, b, c)
            cost = sum(min(dist(u, x) for u in unit_houses) for x in corners)
            if cost < best_cost:
                best_cost = cost
                best_corners = corners

    if best_corners is None:
        best_corners = (triangles[0][0], triangles[0][1], triangles[0][2])

    TARGET = best_corners
    return TARGET


def build_moves(my_u: Dict[int, int], opp_u: Dict[int, int], target: Tuple[int, int, int]) -> List[str]:
    corners = sorted(target)
    units: List[int] = []
    for h in sorted(houses):
        units.extend([h] * movable(h, my_u, opp_u))

    cmds: List[str] = []
    used: Dict[int, int] = {}

    for i, src in enumerate(units):
        cap = movable(src, my_u, opp_u)
        if used.get(src, 0) >= cap:
            continue
        dst = corners[i % 3]
        if src == dst:
            dst = corners[(i + 1) % 3]
        if src == dst:
            continue
        if next_step(src, dst) is None:
            continue
        cmds.append(f"MOVE {src} {dst} 1")
        used[src] = used.get(src, 0) + 1

    return cmds


def build_spawns(triangles: List[Tuple[int, int, int, int, bool, bool]], my_u: Dict[int, int]) -> List[str]:
    cmds: List[str] = []
    for a, b, c, owner, _, _ in triangles:
        if owner != 0:
            continue
        spawn = min((a, b, c), key=lambda h: (my_u.get(h, 0), h))
        rest = [x for x in (a, b, c) if x != spawn]
        cmds.append(f"SPAWN {spawn} {rest[0]} {rest[1]}")
    return cmds


house_count = int(input())
for _ in range(house_count):
    house_id, house_x, house_y = map(int, input().split())
    houses[house_id] = (house_x, house_y)
    adj.setdefault(house_id, set())

while True:
    my_score, opponent_score = map(int, input().split())
    my_u: Dict[int, int] = {}
    opp_u: Dict[int, int] = {}
    for _ in range(house_count):
        house_id, my_units, opponent_units = map(int, input().split())
        my_u[house_id] = my_units
        opp_u[house_id] = opponent_units

    path_count = int(input())
    for _ in range(path_count):
        h1, h2 = map(int, input().split())
        add_edge(h1, h2)

    triangle_count = int(input())
    tris: List[Tuple[int, int, int, int, bool, bool]] = []
    for _ in range(triangle_count):
        parts = input().split()
        a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
        owner = int(parts[3])
        me_cap = parts[4] != "0"
        opp_cap = parts[5] != "0"
        tris.append((a, b, c, owner, me_cap, opp_cap))

    linkable_count = int(input())
    for _ in range(linkable_count):
        input()

    bfs_all_sources()
    target = pick_target(tris, my_u)
    moves = build_moves(my_u, opp_u, target)
    spawns = build_spawns(tris, my_u)
    out = moves + spawns
    print(";".join(out) if out else ";", flush=True)
