import sys
import math

TARGET = None

house_count = int(input())
for i in range(house_count):
    house_id, house_x, house_y = [int(j) for j in input().split()]

while True:
    my_score, opponent_score = [int(i) for i in input().split()]
    my, opp = {}, {}
    for i in range(house_count):
        house_id, my_units, opponent_units = [int(j) for j in input().split()]
        my[house_id], opp[house_id] = my_units, opponent_units
    path_count = int(input())
    for i in range(path_count):
        house1, house2 = [int(j) for j in input().split()]
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

    # --- obsad → drž → spawn (jeden trojuholník naraz) ---
    owned = None
    mine = [(t[0], t[1], t[2]) for t in tris if t[3] == 0]
    if mine:
        TARGET = mine[0] if TARGET is None or TARGET not in mine else TARGET
        owned = TARGET
    elif TARGET is None:
        cand = [t for t in tris if t[4] and t[3] != 0] or [t for t in tris if t[3] != 0] or tris
        t = min(cand, key=lambda x: sum(my.get(c, 0) for c in x[:3]))
        TARGET = (t[0], t[1], t[2])
    corners = sorted(TARGET)
    corner_set = set(corners)
    units = []
    for h in sorted(my):
        m, o = my[h], opp[h]
        if m > 0 and (o == 0 or m > o):
            units += [h] * (m - o if o else m)
    weak = [c for c in corners if my.get(c, 0) <= opp.get(c, 0)]
    held = owned and not weak
    plan = {c: my.get(c, 0) for c in corners}
    cmds, used = [], {}
    for i, src in enumerate(units):
        lim = (my[src] - opp[src]) if opp[src] else my[src]
        if used.get(src, 0) >= lim:
            continue
        if owned and src in corner_set and my[src] > opp[src]:
            continue
        if owned:
            if not weak:
                continue
            dst = weak[i % len(weak)]
        else:
            dst = min(corners, key=lambda c: (plan[c], c))
            plan[dst] += 1
            if src == dst:
                continue
        if src != dst:
            cmds.append(f"MOVE {src} {dst} 1")
            used[src] = used.get(src, 0) + 1
    if held:
        s = min(corners, key=lambda h: my[h])
        r = [x for x in corners if x != s]
        cmds.append(f"SPAWN {s} {r[0]} {r[1]}")
        TARGET = None
    print(";".join(cmds) if cmds else ";", flush=True)
