import sys
import math
from collections import deque

TARGET = None
SPLIT_ARMY_AT = 6  # od tohto počtu jednotiek polovica bráni, polovica útočí
houses = {}
adj = {}


def bfs(src):
    d = {src: 0}
    q = deque([src])
    while q:
        u = q.popleft()
        for v in adj.get(u, ()):
            if v not in d:
                d[v] = d[u] + 1
                q.append(v)
    return d


def reach_triangle(corners, unit_houses):
    total = 0
    for c in corners:
        total += min(bfs(u).get(c, 999) for u in unit_houses)
    return total


house_count = int(input())
for i in range(house_count):
    house_id, house_x, house_y = [int(j) for j in input().split()]
    houses[house_id] = (house_x, house_y)
    adj.setdefault(house_id, set())

while True:
    my_score, opponent_score = [int(i) for i in input().split()]
    my, opp = {}, {}
    for i in range(house_count):
        house_id, my_units, opponent_units = [int(j) for j in input().split()]
        my[house_id], opp[house_id] = my_units, opponent_units
    path_count = int(input())
    for i in range(path_count):
        house1, house2 = [int(j) for j in input().split()]
        adj.setdefault(house1, set()).add(house2)
        adj.setdefault(house2, set()).add(house1)
    triangle_count = int(input())
    tris = []
    for i in range(triangle_count):
        inputs = input().split()
        house1 = int(inputs[0])
        house2 = int(inputs[1])
        house3 = int(inputs[2])
        owner = int(inputs[3])
        me_can_capture = inputs[4] != "0"
        opponent_can_capture = inputs[5] != "0"
        tris.append((house1, house2, house3, owner, me_can_capture, opponent_can_capture))
    linkable_count = int(input())
    for i in range(linkable_count):
        house1, house2 = [int(j) for j in input().split()]

    # --- obrana získaných | útok na TARGET | spawn ---
    unit_h = [h for h in my if my[h] > 0]
    army = sum(my.values())
    owned_tris = [(t[0], t[1], t[2]) for t in tris if t[3] == 0]
    owned_corners = set()
    defend_weak = []
    for a, b, c in owned_tris:
        for corner in (a, b, c):
            owned_corners.add(corner)
            if my.get(corner, 0) <= opp.get(corner, 0):
                defend_weak.append(corner)
    defend_weak.sort(key=lambda c: (my.get(c, 0) - opp.get(c, 0), c))

    owned = None
    if TARGET:
        info = next((t for t in tris if frozenset(t[:3]) == frozenset(TARGET)), None)
        if info and info[3] == 0:
            owned = TARGET
        elif info and (info[3] != 0 or not info[4]):
            TARGET = None
    if TARGET is None and unit_h:
        cand = [t for t in tris if t[4] and t[3] != 0] or [t for t in tris if t[3] != 0] or tris
        t = min(
            cand,
            key=lambda x: (
                reach_triangle(x[:3], unit_h),
                -sum(1 for c in x[:3] if my.get(c, 0) > opp.get(c, 0)),
                -sum(my.get(c, 0) for c in x[:3]),
            ),
        )
        TARGET = (t[0], t[1], t[2])

    units = []
    for h in sorted(my):
        m, o = my[h], opp[h]
        if m > 0 and (o == 0 or m > o):
            units += [h] * (m - o if o else m)
    if army >= SPLIT_ARMY_AT and owned_tris:
        half = len(units) // 2
        def_units, atk_units = units[:half], units[half:]
    else:
        def_units, atk_units = [], units

    atk_corners = sorted(TARGET) if TARGET else []
    atk_set = set(atk_corners)
    atk_weak = [c for c in atk_corners if my.get(c, 0) <= opp.get(c, 0)] if TARGET else []
    target_held = owned and not atk_weak

    cmds, used = [], {}

    def lim_src(src):
        m, o = my[src], opp[src]
        return (m - o) if o else m

    def garrison(src, corner_set):
        return (
            src in corner_set
            and my[src] > opp[src]
            and my[src] <= opp[src] + 1
        )

    for i, src in enumerate(def_units):
        if used.get(src, 0) >= lim_src(src):
            continue
        if garrison(src, owned_corners):
            continue
        if not defend_weak:
            continue
        dst = defend_weak[i % len(defend_weak)]
        if src == dst:
            continue
        cmds.append(f"MOVE {src} {dst} 1")
        used[src] = used.get(src, 0) + 1

    atk_units.sort(key=lambda h: (1 if garrison(h, owned_corners) else 0, h))
    for i, src in enumerate(atk_units):
        if not TARGET:
            break
        if used.get(src, 0) >= lim_src(src):
            continue
        if garrison(src, owned_corners):
            continue
        if owned and src in atk_set and my[src] > opp[src]:
            continue
        if owned:
            if not atk_weak:
                continue
            dst = atk_weak[i % len(atk_weak)]
        else:
            dst = atk_corners[i % len(atk_corners)]
            if src == dst:
                continue
            if garrison(src, atk_set):
                continue
        if src != dst:
            cmds.append(f"MOVE {src} {dst} 1")
            used[src] = used.get(src, 0) + 1

    if target_held and TARGET:
        s = min(atk_corners, key=lambda h: my[h])
        r = [x for x in atk_corners if x != s]
        cmds.append(f"SPAWN {s} {r[0]} {r[1]}")
        TARGET = None
    elif owned_tris:
        for a, b, c in owned_tris:
            if frozenset((a, b, c)) == frozenset(TARGET or ()):
                continue
            corners = (a, b, c)
            if all(my.get(x, 0) > opp.get(x, 0) for x in corners):
                s = min(corners, key=lambda h: my[h])
                r = [x for x in corners if x != s]
                cmds.append(f"SPAWN {s} {r[0]} {r[1]}")
                break
    print(";".join(cmds) if cmds else ";", flush=True)
