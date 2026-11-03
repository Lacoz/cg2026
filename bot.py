import sys
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

houses: Dict[int, Tuple[int, int]] = {}
adj: Dict[int, set] = {}
paths: Dict[int, Dict[int, List[int]]] = {}


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


class Triangle:
    __slots__ = ("a", "b", "c", "owner", "me_cap", "opp_cap")

    def __init__(self, a, b, c, owner, me_cap, opp_cap):
        self.a, self.b, self.c = a, b, c
        self.owner = owner
        self.me_cap = me_cap
        self.opp_cap = opp_cap

    def corners(self) -> Tuple[int, int, int]:
        return self.a, self.b, self.c


def we_control_corner(c: int, my_u: Dict[int, int], opp_u: Dict[int, int]) -> bool:
    return my_u.get(c, 0) > opp_u.get(c, 0)


def corner_deficit(c: int, my_u: Dict[int, int], opp_u: Dict[int, int]) -> int:
    """How many more units we want on c to secure strict majority."""
    m, o = my_u.get(c, 0), opp_u.get(c, 0)
    if m > o:
        return 0
    return o - m + 1


def movable_from(h: int, my_u: Dict[int, int], opp_u: Dict[int, int]) -> int:
    m, o = my_u.get(h, 0), opp_u.get(h, 0)
    if m <= 0:
        return 0
    if o > 0:
        if m <= o:
            return 0
        return m - o
    return m


def movable_from_garrison(
    h: int,
    garrison: Set[int],
    my_u: Dict[int, int],
    opp_u: Dict[int, int],
) -> int:
    """On a focus corner we control, never move away the last securing unit."""
    base = movable_from(h, my_u, opp_u)
    if h not in garrison or base <= 0:
        return base
    m, o = my_u.get(h, 0), opp_u.get(h, 0)
    if m <= o:
        return base
    # Keep at least one unit while we hold the corner (o==0 → leave m-1 max).
    keep = 1 if o == 0 else o + 1
    return max(0, min(base, m - keep))


def focus_triangle(
    triangles: List[Triangle], my_u: Dict[int, int], opp_u: Dict[int, int]
) -> Optional[Triangle]:
    unit_houses = [h for h in houses if my_u.get(h, 0) > 0]
    if not unit_houses:
        return None

    best: Optional[Triangle] = None
    best_key: Tuple = (10**9, 10**9, 10**9)

    for t in triangles:
        if not t.me_cap:
            continue
        corners = t.corners()
        owned = sum(1 for c in corners if we_control_corner(c, my_u, opp_u))
        need = [c for c in corners if corner_deficit(c, my_u, opp_u) > 0]
        if not need:
            continue

        reach = sum(min(dist(h, c) for h in unit_houses) for c in need)
        key = (-owned, reach, min(corners))
        if key < best_key:
            best_key = key
            best = t
    return best


def list_movable_units(
    garrison: Set[int], my_u: Dict[int, int], opp_u: Dict[int, int]
) -> List[int]:
    units: List[int] = []
    for h in sorted(houses):
        n = movable_from_garrison(h, garrison, my_u, opp_u)
        units.extend([h] * n)
    return units


def assign_units_to_corners(
    corners: Tuple[int, int, int],
    units: List[int],
    my_u: Dict[int, int],
    opp_u: Dict[int, int],
) -> List[Tuple[int, int]]:
    """One inbound unit per needy corner first; spread, never stack all on one roh."""
    corner_list = list(corners)
    needy = [c for c in corner_list if corner_deficit(c, my_u, opp_u) > 0]
    if not needy:
        needy = corner_list

    needy.sort(key=lambda c: (-corner_deficit(c, my_u, opp_u), -opp_u.get(c, 0), c))

    options: List[Tuple[int, int, int, int, int]] = []
    for ui, src in enumerate(units):
        for c in needy:
            d = dist(src, c)
            if d >= 10**8:
                continue
            options.append(
                (d, -corner_deficit(c, my_u, opp_u), ui, src, c)
            )
    options.sort()

    assigned_ui: Set[int] = set()
    assigned_dst: Set[int] = set()
    pairs: List[Tuple[int, int]] = []

    corner_set = set(corner_list)

    for d, deficit, ui, src, c in options:
        if ui in assigned_ui:
            continue
        if c in assigned_dst and deficit <= 1:
            continue
        if src == c:
            continue
        if we_control_corner(c, my_u, opp_u) and deficit == 0:
            continue
        if (
            src in corner_set
            and we_control_corner(src, my_u, opp_u)
            and corner_deficit(src, my_u, opp_u) == 0
            and deficit <= 1
        ):
            continue
        pairs.append((src, c))
        assigned_ui.add(ui)
        assigned_dst.add(c)

    for ui, src in enumerate(units):
        if ui in assigned_ui:
            continue
        best_c = min(
            needy,
            key=lambda c: (dist(src, c), -corner_deficit(c, my_u, opp_u), c),
        )
        if dist(src, best_c) >= 10**8 or src == best_c:
            continue
        if we_control_corner(best_c, my_u, opp_u) and corner_deficit(best_c, my_u, opp_u) == 0:
            continue
        if (
            src in corner_set
            and we_control_corner(src, my_u, opp_u)
            and corner_deficit(src, my_u, opp_u) == 0
            and corner_deficit(best_c, my_u, opp_u) <= 1
        ):
            continue
        pairs.append((src, best_c))
        assigned_ui.add(ui)

    return pairs


def build_moves(
    my_u: Dict[int, int], opp_u: Dict[int, int], triangles: List[Triangle]
) -> List[str]:
    focus = focus_triangle(triangles, my_u, opp_u)
    if focus is None:
        return []

    garrison = set(focus.corners())
    units = list_movable_units(garrison, my_u, opp_u)
    if not units:
        return []

    pairs = assign_units_to_corners(focus.corners(), units, my_u, opp_u)
    cmds: List[str] = []
    used: Dict[int, int] = {}

    for src, dst in pairs:
        cap = movable_from_garrison(src, garrison, my_u, opp_u)
        if used.get(src, 0) >= cap:
            continue
        nxt = next_step(src, dst)
        if nxt is None:
            continue
        cmds.append(f"MOVE {src} {dst} 1")
        used[src] = used.get(src, 0) + 1

    return cmds


def build_spawns(
    triangles: List[Triangle],
    my_u: Dict[int, int],
    opp_u: Dict[int, int],
    focus: Optional[Triangle],
) -> List[str]:
    cmds: List[str] = []
    expand_corners: List[int] = []
    if focus:
        expand_corners = [
            c for c in focus.corners() if corner_deficit(c, my_u, opp_u) > 0
        ]

    for t in triangles:
        if t.owner != 0:
            continue
        a, b, c = t.corners()
        spawn_on = a
        if expand_corners:
            candidates = [x for x in (a, b, c) if x in expand_corners]
            if candidates:
                spawn_on = min(
                    candidates, key=lambda h: (my_u.get(h, 0), -opp_u.get(h, 0), h)
                )
            else:
                spawn_on = min((a, b, c), key=lambda h: (my_u.get(h, 0), h))
        else:
            spawn_on = min((a, b, c), key=lambda h: (my_u.get(h, 0), h))
        rest = [x for x in (a, b, c) if x != spawn_on]
        cmds.append(f"SPAWN {spawn_on} {rest[0]} {rest[1]}")
    return cmds


def generate_turn(
    my_u: Dict[int, int],
    opp_u: Dict[int, int],
    triangles: List[Triangle],
) -> str:
    focus = focus_triangle(triangles, my_u, opp_u)
    move_cmds = build_moves(my_u, opp_u, triangles)
    spawn_cmds = build_spawns(triangles, my_u, opp_u, focus)
    parts = move_cmds + spawn_cmds
    return ";".join(parts) if parts else ";"


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
    triangles: List[Triangle] = []
    for _ in range(triangle_count):
        parts = input().split()
        h1, h2, h3 = int(parts[0]), int(parts[1]), int(parts[2])
        owner = int(parts[3])
        me_cap = parts[4] != "0"
        opp_cap = parts[5] != "0"
        triangles.append(Triangle(h1, h2, h3, owner, me_cap, opp_cap))

    linkable_count = int(input())
    for _ in range(linkable_count):
        input()

    bfs_all_sources()
    print(generate_turn(my_u, opp_u, triangles), flush=True)
