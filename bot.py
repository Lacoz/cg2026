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

    # --- stratégia (≤30 riadkov) ---
    if TARGET and any(frozenset(t[:3]) == frozenset(TARGET) and t[3] == 0 for t in tris):
        TARGET = None
    if TARGET is None:
        cand = [t for t in tris if t[4]] or tris
        t = min(cand, key=lambda x: sum(my.get(c, 0) for c in x[:3]))
        TARGET = (t[0], t[1], t[2])
    corners = sorted(TARGET)
    units = []
    for h in sorted(my):
        m, o = my[h], opp[h]
        if m > 0 and (o == 0 or m > o):
            units += [h] * (m - o if o else m)
    cmds, used = [], {}
    for i, src in enumerate(units):
        lim = (my[src] - opp[src]) if opp[src] else my[src]
        if used.get(src, 0) >= lim:
            continue
        dst = corners[i % 3]
        if src == dst:
            dst = corners[(i + 1) % 3]
        if src != dst:
            cmds.append(f"MOVE {src} {dst} 1")
            used[src] = used.get(src, 0) + 1
    for a, b, c, owner, _, _ in tris:
        if owner == 0:
            s = min((a, b, c), key=lambda h: my[h])
            r = [x for x in (a, b, c) if x != s]
            cmds.append(f"SPAWN {s} {r[0]} {r[1]}")
    print(";".join(cmds) if cmds else ";", flush=True)
