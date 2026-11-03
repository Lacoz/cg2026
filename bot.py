import sys
from collections import Counter, deque
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


def node_owner(my_u: Dict[int, int], opp_u: Dict[int, int], h: int) -> int:
    nbs = adj.get(h, ())
    if nbs:
        if all(my_u.get(n, 0) > opp_u.get(n, 0) for n in nbs):
            return 0
        if all(opp_u.get(n, 0) > my_u.get(n, 0) for n in nbs):
            return 1
    m, o = my_u.get(h, 0), opp_u.get(h, 0)
    if m > o:
        return 0
    if o > m:
        return 1
    return -1


class Triangle:
    __slots__ = ("a", "b", "c", "owner", "me_cap", "opp_cap")

    def __init__(self, a, b, c, owner, me_cap, opp_cap):
        self.a, self.b, self.c = a, b, c
        self.owner = owner
        self.me_cap = me_cap
        self.opp_cap = opp_cap

    def corners(self) -> Tuple[int, int, int]:
        return self.a, self.b, self.c


def total_units(my_u: Dict[int, int]) -> int:
    return sum(my_u.values())


def would_surround(
    h: int, my_u: Dict[int, int], opp_u: Dict[int, int], leave: int
) -> bool:
    nbs = adj.get(h, ())
    if not nbs or my_u.get(h, 0) - leave <= 0:
        return False
    for n in nbs:
        if opp_u.get(n, 0) <= my_u.get(n, 0):
            return False
    return True


def movable_units(h: int, my_u: Dict[int, int], opp_u: Dict[int, int]) -> int:
    m, o = my_u.get(h, 0), opp_u.get(h, 0)
    if m <= 0:
        return 0
    if o > 0:
        return max(0, m - o - 1)
    if would_surround(h, my_u, opp_u, 1):
        return 0
    return m


def units_needed_on_corner(c: int, my_u: Dict[int, int], opp_u: Dict[int, int]) -> int:
    return max(0, opp_u.get(c, 0) - my_u.get(c, 0) + 1)


def mission_limit(my_u: Dict[int, int]) -> int:
    n = total_units(my_u)
    if n <= 5:
        return 1
    if n <= 14:
        return 2
    return 3


def mission_score(
    t: Triangle, my_u: Dict[int, int], opp_u: Dict[int, int]
) -> Tuple:
    if not t.me_cap:
        return (1, 0, 0, 0)
    owned_corners = sum(1 for c in t.corners() if node_owner(my_u, opp_u, c) == 0)
    need = [c for c in t.corners() if node_owner(my_u, opp_u, c) != 0]
    if not need and t.owner != 0:
        return (1, 0, 0, 0)

    pool: List[int] = []
    for h in houses:
        pool.extend([h] * movable_units(h, my_u, opp_u))
    reach = 0
    if need and pool:
        used = [False] * len(pool)
        for c in sorted(need, key=lambda x: my_u.get(x, 0) - opp_u.get(x, 0)):
            best_d, best_i = 10**9, -1
            for i, h in enumerate(pool):
                if used[i]:
                    continue
                d = dist(h, c)
                if d < best_d:
                    best_d, best_i = d, i
            if best_i >= 0:
                used[best_i] = True
                reach += best_d
            else:
                reach += 400
    elif need:
        reach = 999

    defend = 0 if t.owner == 0 and need else 1
    return (defend, -owned_corners, reach, sum(units_needed_on_corner(c, my_u, opp_u) for c in need))


def mission_triangles(
    my_u: Dict[int, int], opp_u: Dict[int, int], triangles: List[Triangle]
) -> List[Triangle]:
    scored: List[Tuple[Tuple, Triangle]] = []
    for t in triangles:
        if not t.me_cap:
            continue
        need = [c for c in t.corners() if node_owner(my_u, opp_u, c) != 0]
        if not need:
            continue
        scored.append((mission_score(t, my_u, opp_u), t))
    scored.sort(key=lambda x: x[0])
    limit = mission_limit(my_u)
    return [t for _, t in scored[:limit]]


def coordinate_triangle(
    t: Triangle,
    my_u: Dict[int, int],
    opp_u: Dict[int, int],
    budget: Counter,
) -> List[Tuple[int, int]]:
    need = [c for c in t.corners() if node_owner(my_u, opp_u, c) != 0]
    if not need:
        return []
    need_set = set(need)
    need.sort(
        key=lambda c: (
            my_u.get(c, 0) - opp_u.get(c, 0),
            units_needed_on_corner(c, my_u, opp_u),
            -opp_u.get(c, 0),
        )
    )
    demand = {c: max(1, units_needed_on_corner(c, my_u, opp_u)) for c in need}
    assignments: List[Tuple[int, int]] = []

    def pick_source(target: int) -> Optional[int]:
        best_h, best_d = None, 10**9
        for h in houses:
            if budget[h] <= 0:
                continue
            if h in need_set and my_u.get(h, 0) <= opp_u.get(h, 0):
                continue
            d = dist(h, target)
            if d >= 10**8:
                continue
            if d < best_d:
                best_d, best_h = d, h
        return best_h

    for c in need:
        src = pick_source(c)
        if src is None:
            continue
        assignments.append((src, c))
        demand[c] = max(0, demand[c] - 1)
        budget[src] -= 1

    while sum(budget.values()) > 0:
        progressed = False
        for c in need:
            if demand[c] <= 0:
                continue
            src = pick_source(c)
            if src is None:
                continue
            assignments.append((src, c))
            demand[c] -= 1
            budget[src] -= 1
            progressed = True
        if not progressed:
            break

    return assignments


def assign_moves(
    my_u: Dict[int, int], opp_u: Dict[int, int], triangles: List[Triangle]
) -> List[str]:
    budget: Counter = Counter()
    for h in houses:
        budget[h] = movable_units(h, my_u, opp_u)

    pairs: List[Tuple[int, int]] = []
    missions = mission_triangles(my_u, opp_u, triangles)
    for t in missions:
        if sum(budget.values()) <= 0:
            break
        pairs.extend(coordinate_triangle(t, my_u, opp_u, budget))

    # Use every remaining unit — army must grow, not sit at 3.
    needy: List[int] = []
    for t in missions:
        for c in t.corners():
            if node_owner(my_u, opp_u, c) != 0:
                needy.append(c)
    needy.sort(key=lambda c: (my_u.get(c, 0) - opp_u.get(c, 0), -opp_u.get(c, 0)))
    if not needy:
        for t in triangles:
            if not t.me_cap:
                continue
            for c in t.corners():
                if node_owner(my_u, opp_u, c) != 0:
                    needy.append(c)

    def pick_spare() -> Optional[Tuple[int, int]]:
        best: Optional[Tuple[int, int, int]] = None
        for h in houses:
            if budget[h] <= 0:
                continue
            for c in needy:
                d = dist(h, c)
                if d >= 10**8:
                    continue
                score = -d * 10 + opp_u.get(c, 0) * 5
                if best is None or score > best[0]:
                    best = (score, h, c)
        if best is None:
            return None
        return best[1], best[2]

    while sum(budget.values()) > 0:
        pair = pick_spare()
        if pair is None:
            break
        src, corner = pair
        pairs.append((src, corner))
        budget[src] -= 1

    max_per_house = {h: movable_units(h, my_u, opp_u) for h in houses}
    used: Counter = Counter()
    cmds: List[str] = []
    for src, corner in pairs:
        if used[src] >= max_per_house.get(src, 0):
            continue
        if would_surround(src, my_u, opp_u, used[src] + 1):
            continue
        if src == corner or dist(src, corner) >= 10**8:
            continue
        cmds.append(f"MOVE {src} {corner} 1")
        used[src] += 1
    return cmds


def spawn_for_triangle(
    t: Triangle,
    my_u: Dict[int, int],
    opp_u: Dict[int, int],
    next_corners: Set[int],
) -> Tuple[int, int, int]:
    corners = list(t.corners())
    if next_corners:
        pick = [c for c in corners if c in next_corners]
        if pick:
            first = min(pick, key=lambda c: (my_u.get(c, 0), -opp_u.get(c, 0), c))
            rest = [c for c in corners if c != first]
            return first, rest[0], rest[1]
    first = min(corners, key=lambda c: (my_u.get(c, 0), -opp_u.get(c, 0), c))
    rest = [c for c in corners if c != first]
    return first, rest[0], rest[1]


def generate_turn(
    my_u: Dict[int, int],
    opp_u: Dict[int, int],
    triangles: List[Triangle],
) -> str:
    missions = mission_triangles(my_u, opp_u, triangles)
    next_corners: Set[int] = set()
    for t in missions:
        for c in t.corners():
            if node_owner(my_u, opp_u, c) != 0:
                next_corners.add(c)

    move_cmds = assign_moves(my_u, opp_u, triangles)

    spawn_cmds: List[str] = []
    for t in triangles:
        if t.owner == 0:
            h1, h2, h3 = spawn_for_triangle(t, my_u, opp_u, next_corners)
            spawn_cmds.append(f"SPAWN {h1} {h2} {h3}")

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
