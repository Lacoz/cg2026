import sys
import math
from collections import deque

TARGET = None
SPLIT_ARMY_AT = 8
GARRISON_AREA = 120_000.0  # väčší trojuholník → 2 jednotky na rohu
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


def tri_area(a, b, c):
    ax, ay = houses[a]
    bx, by = houses[b]
    cx, cy = houses[c]
    return abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) / 2.0


def reach_triangle(corners, unit_houses):
    total = 0
    for c in corners:
        total += min(bfs(u).get(c, 999) for u in unit_houses)
    return total


def move_energy(src, dst):
    steps = bfs(src).get(dst, 999)
    if steps >= 999:
        return 1e9
    sx, sy = houses[src]
    dx, dy = houses[dst]
    return steps * 80 + math.hypot(dx - sx, dy - sy) * 0.15


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

    unit_h = [h for h in my if my[h] > 0]
    army = sum(my.values())
    owned_tris = [(t[0], t[1], t[2]) for t in tris if t[3] == 0]
    owned_area = sum(tri_area(a, b, c) for a, b, c in owned_tris)
    corner_area = {}
    for a, b, c in owned_tris:
        ar = tri_area(a, b, c)
        for corner in (a, b, c):
            corner_area[corner] = max(corner_area.get(corner, 0.0), ar)

    owned_corners = set()
    defend_corners = []
    for a, b, c in owned_tris:
        ar = tri_area(a, b, c)
        for corner in (a, b, c):
            owned_corners.add(corner)
            margin = my.get(corner, 0) - opp.get(corner, 0)
            if margin <= 1:
                defend_corners.append((margin, -ar, corner))
    defend_corners.sort()
    defend_list = [c for _, _, c in defend_corners]
    secure_hold = not defend_list

    def corner_pressured(c):
        if opp.get(c, 0) > 0:
            return True
        return any(opp.get(n, 0) > 0 for n in adj.get(c, ()))

    def tri_spawn_ready(a, b, c):
        corners = (a, b, c)
        if any(my.get(x, 0) <= opp.get(x, 0) for x in corners):
            return False
        if any(corner_pressured(x) for x in corners):
            return all(my.get(x, 0) >= opp.get(x, 0) + 2 for x in corners)
        total = sum(my.get(x, 0) for x in corners)
        return total >= 4 and max(my.get(x, 0) for x in corners) >= 2

    owned = None
    if TARGET:
        info = next((t for t in tris if frozenset(t[:3]) == frozenset(TARGET)), None)
        if info and info[3] == 0:
            owned = TARGET
        elif info and (info[3] != 0 or not info[4]):
            TARGET = None

    if TARGET is None and unit_h:
        cand = [t for t in tris if t[4] and t[3] != 0] or [t for t in tris if t[3] != 0] or tris
        atk_energy = 1.0
        t = min(
            cand,
            key=lambda x: (
                reach_triangle(x[:3], unit_h),
                -sum(1 for c in x[:3] if my.get(c, 0) > opp.get(c, 0)),
                -sum(my.get(c, 0) for c in x[:3]),
            ),
        )
        atk_energy = reach_triangle(t[:3], unit_h) + 1
        TARGET = (t[0], t[1], t[2])

    units = []
    for h in sorted(my):
        m, o = my[h], opp[h]
        if m > 0 and (o == 0 or m > o):
            units += [h] * (m - o if o else m)

    if owned_tris and defend_list:
        if army >= SPLIT_ARMY_AT:
            hold_value = owned_area + len(defend_list) * 80_000
            atk_e = reach_triangle(TARGET, unit_h) + 1 if TARGET else 50
            def_frac = 0.72 + min(0.18, hold_value / (hold_value + atk_e * 35_000))
            def_frac = max(def_frac, 0.82)
            n_def = min(len(units) - 1, max(int(len(units) * def_frac), len(defend_list)))
        else:
            n_def = max(1, len(units) - 1)
        def_units, atk_units = units[:n_def], units[n_def:]
    elif owned_tris and secure_hold:
        def_units, atk_units = [], units
    else:
        def_units, atk_units = [], units

    atk_corners = sorted(TARGET) if TARGET else []
    atk_set = set(atk_corners)
    atk_weak = [c for c in atk_corners if my.get(c, 0) <= opp.get(c, 0)] if TARGET else []
    target_held = owned and not atk_weak

    cmds, used = [], {}

    def min_stay(h):
        m, o = my[h], opp[h]
        if h not in owned_corners or m <= o:
            return 0
        need = 2 if corner_area.get(h, 0) >= GARRISON_AREA else 1
        if o > 0:
            need = max(need, o + 1)
        return min(m, need)

    def primary_def():
        return defend_list[0] if defend_list else None

    def lim_src(src, dst=None):
        m, o = my[src], opp[src]
        if m <= 0 or (o > 0 and m <= o):
            return 0
        cap = m - o if o else m
        pri = primary_def()
        if pri and dst == pri and src in owned_corners and src != pri and m > o:
            return 1
        if src in owned_corners:
            cap = max(0, min(cap, m - min_stay(src)))
        return cap

    def can_leave_owned(src, dst=None):
        if src not in owned_corners:
            return True
        m, o = my[src], opp[src]
        if m <= o:
            return False
        pri = primary_def()
        if dst is not None and pri and dst == pri and src != pri:
            md = my.get(dst, 0) - opp.get(dst, 0)
            if md <= m - o:
                return True
        if dst is not None and dst in defend_list:
            if my.get(dst, 0) - opp.get(dst, 0) < m - o:
                return True
        return m > min_stay(src)

    for src in def_units:
        if not defend_list:
            continue
        dst = min(defend_list, key=lambda c: (my.get(c, 0) - opp.get(c, 0), move_energy(src, c)))
        if src == dst:
            continue
        if used.get(src, 0) >= lim_src(src, dst) or not can_leave_owned(src, dst):
            continue
        cmds.append(f"MOVE {src} {dst} 1")
        used[src] = used.get(src, 0) + 1

    atk_units.sort(key=lambda h: (1 if h in owned_corners else 0, h))
    for i, src in enumerate(atk_units):
        if not TARGET:
            break
        if owned:
            if not atk_weak:
                continue
            dst = min(atk_weak, key=lambda c: move_energy(src, c))
        else:
            dst = atk_corners[i % len(atk_corners)]
            if src == dst:
                continue
        if used.get(src, 0) >= lim_src(src, dst) or not can_leave_owned(src, dst):
            continue
        if owned and src in atk_set and my[src] > opp[src]:
            continue
        if src != dst:
            cmds.append(f"MOVE {src} {dst} 1")
            used[src] = used.get(src, 0) + 1

    spawn_ready = False
    if owned_tris:
        if target_held and TARGET and tri_spawn_ready(*TARGET):
            spawn_ready = True
            s = min(atk_corners, key=lambda h: my[h])
            r = [x for x in atk_corners if x != s]
            cmds.append(f"SPAWN {s} {r[0]} {r[1]}")
            TARGET = None
        else:
            ready = [t for t in owned_tris if tri_spawn_ready(*t)]
            if ready:
                spawn_ready = True
                a, b, c = max(ready, key=lambda t: tri_area(*t))
                s = min((a, b, c), key=lambda h: my[h])
                r = [x for x in (a, b, c) if x != s]
                cmds.append(f"SPAWN {s} {r[0]} {r[1]}")
    n_owned = len(owned_tris)
    n_frag = len(defend_list)
    mode = "HOLD" if owned_tris and not secure_hold else ("ATK" if TARGET else "IDLE")
    m = {"HOLD": "H", "ATK": "A", "IDLE": "I"}[mode]
    r = "R" if owned_tris and not secure_hold else "O"
    # UI message max ~20 znakov: v vojaci, t trojuholníky, f krehké rohy, r O/R, m H/A/I, c roh cieľa
    ui = f"v={army} t={n_owned} f={n_frag} r={r} m={m}"
    if spawn_ready and len(ui) <= 17:
        ui += " s=1"
    elif owned_tris and len(ui) <= 17:
        ui += " s=0"
    if TARGET and len(ui) <= 14:
        ui += f" c={min(atk_corners)}"
    if len(ui) > 20:
        ui = f"v={army} t={n_owned} r={r} m={m}"[:20]
    status = f"MSG {ui}"
    out = [status] + cmds
    print(";".join(out), flush=True)
