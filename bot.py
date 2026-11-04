import sys
from collections import deque

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


house_count = int(input())
for _ in range(house_count):
    hid, x, y = [int(j) for j in input().split()]
    houses[hid] = (x, y)
    adj.setdefault(hid, set())

while True:
    my_score, opp_score = [int(i) for i in input().split()]
    my, opp = {}, {}
    for _ in range(house_count):
        hid, mu, ou = [int(j) for j in input().split()]
        my[hid], opp[hid] = mu, ou
    for _ in range(int(input())):
        a, b = [int(j) for j in input().split()]
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    tris = []
    for _ in range(int(input())):
        h1, h2, h3, owner, me_cap, opp_cap = input().split()
        tris.append((int(h1), int(h2), int(h3), int(owner), me_cap != "0", opp_cap != "0"))
    for _ in range(int(input())):
        input()

    dist_from = {h: bfs(h) for h in houses}

    def dist(a, b):
        return dist_from[a].get(b, 999)

    cells = []
    for h in my:
        cells += [h] * my[h]
    army = len(cells)
    cmds = []

    # Same capture as the wood boss: 3 units onto the fastest triangle.
    # Extras do it again, instead of the boss's random walk.
    pool = cells[:]
    cands = [t for t in tris if t[3] != 0 and t[4]]
    while len(pool) >= 3 and cands:
        best = None
        for t in cands:
            corners = t[:3]
            free = pool[:]
            srcs = []
            cost = 0
            for target in corners:
                i = min(range(len(free)), key=lambda k: dist(free[k], target))
                srcs.append(free.pop(i))
                cost = max(cost, dist(srcs[-1], target))
            if best is None or cost < best[0]:
                best = (cost, srcs, t)
        if best is None:
            break
        _, srcs, t = best
        cands.remove(t)
        for src in srcs:
            pool.remove(src)
        for src, dst in zip(srcs, t[:3]):
            if src != dst and dist(src, dst) < 999:
                cmds.append(f"MOVE {src} {dst} 1")

    owned = [t for t in tris if t[3] == 0]
    if owned and army < house_count:
        a, b, c = owned[0][:3]
        cmds.append(f"SPAWN {a} {b} {c}")

    if army > 10 and owned:
        best = None
        for t in owned:
            if any(my.get(c, 0) <= 0 for c in t[:3]):
                continue
            for c in t[:3]:
                for n in adj.get(c, ()):
                    if opp.get(n, 0) > 1 and (best is None or opp[n] > best[0]):
                        best = (opp[n], t, n)
        if best:
            t, n = best[1], best[2]
            cmds.append(f"ATTACK {t[0]} {t[1]} {t[2]} {n}")

    ui = f"v={army} t={len(owned)}"
    print(("MSG " + ui + ";" + ";".join(cmds)) if cmds else ("MSG " + ui), flush=True)
