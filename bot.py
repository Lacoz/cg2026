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

    def held(cs):
        return all(my.get(c, 0) > opp.get(c, 0) for c in cs)

    army = sum(my.values())
    opp_army = sum(opp.values())
    owned = [t for t in tris if t[3] == 0]
    usable = [t for t in owned if all(my.get(c, 0) > 0 for c in t[:3])]
    used_tris = set()
    cmds = []

    # 1. SPAWN on usable triangles to snowball early and out-grow opponent,
    # capped at max(28, opp_army + 8) so we stay fast and keep triangles scoring late-game.
    max_army = max(28, opp_army + 8)
    if army < max_army:
        for t in usable:
            corners = t[:3]
            best_c = max(
                corners,
                key=lambda c: (
                    opp.get(c, 0) >= my.get(c, 0),
                    sum(1 for tr in tris if c in tr[:3] and tr[3] != 0 and tr[4]),
                    -my.get(c, 0),
                ),
            )
            others = [c for c in corners if c != best_c]
            if army + len(used_tris) < 18 or len(usable) - len(used_tris) > 2:
                cmds.append(f"SPAWN {best_c} {others[0]} {others[1]}")
                used_tris.add(corners)

    # 2. ATTACK only with a triangle not already used for SPAWN, and only when it kills >= 2 opp units
    # without sacrificing our last scoring triangle.
    rem_usable = [t for t in usable if t[:3] not in used_tris]
    if army > 10 and len(rem_usable) >= 2:
        best_atk = None
        for t in rem_usable:
            for c in t[:3]:
                for n in adj.get(c, ()):
                    if opp.get(n, 0) >= 2 and (best_atk is None or opp[n] > best_atk[0]):
                        best_atk = (opp[n], t, n)
        if best_atk:
            _, t, n = best_atk
            cmds.append(f"ATTACK {t[0]} {t[1]} {t[2]} {n}")
            used_tris.add(t[:3])

    # 3. Keep anchors on triangles that remain owned (not neutralized by SPAWN/ATTACK)
    # once we have enough army to hold and expand simultaneously.
    avail = dict(my)
    planned_in = {h: 0 for h in houses}
    if army >= 8:
        for t in owned:
            if t[:3] in used_tris or not held(t[:3]):
                continue
            for c in t[:3]:
                need_hold = opp.get(c, 0) + 1
                if avail.get(c, 0) >= need_hold and planned_in[c] < need_hold:
                    keep = need_hold - planned_in[c]
                    avail[c] -= keep
                    planned_in[c] += keep

    # 4. Assign units using house counts (O(houses * tris) instead of O(units * tris))
    avail_total = sum(avail.values())
    cands = [t for t in tris if t[3] != 0 and t[4]]
    while avail_total > 0 and cands:
        best = None
        active_srcs = [h for h, cnt in avail.items() if cnt > 0]
        for t in cands:
            corners = t[:3]
            needs = []
            for c in corners:
                req = (opp.get(c, 0) + 1) - planned_in[c]
                if req > 0:
                    needs.append((c, req))
            total_req = sum(r for _, r in needs)
            if total_req == 0 or total_req > avail_total:
                continue
            temp_avail = dict(avail)
            srcs = []
            max_d = 0
            sum_d = 0
            ok = True
            for target, req in needs:
                rem = req
                by_d = sorted(active_srcs, key=lambda h: dist(h, target))
                for h in by_d:
                    cnt = temp_avail.get(h, 0)
                    if cnt <= 0:
                        continue
                    d = dist(h, target)
                    if d >= 999:
                        break
                    take = cnt if cnt < rem else rem
                    temp_avail[h] = cnt - take
                    rem -= take
                    srcs.append((h, target, take))
                    if d > max_d:
                        max_d = d
                    sum_d += d * take
                    if rem == 0:
                        break
                if rem > 0:
                    ok = False
                    break
            if not ok:
                continue
            score = (max_d, total_req, 0 if t[3] == 1 else 1, sum_d)
            if best is None or score < best[0]:
                best = (score, srcs, t, total_req)
        if best is None:
            break
        _, srcs, t, total_req = best
        cands.remove(t)
        avail_total -= total_req
        for src, dst, take in srcs:
            avail[src] -= take
            planned_in[dst] += take
            if src != dst:
                cmds.append(f"MOVE {src} {dst} {take}")

    # 5. Vacate blocked triangles (owner != 0 and me_cap == False) with any remaining idle units
    blocked_corners = set()
    for t in tris:
        if t[3] != 0 and not t[4]:
            blocked_corners.update(t[:3])

    for src in sorted(avail):
        cnt = avail[src]
        if cnt > 0 and src in blocked_corners:
            neighs = list(adj.get(src, ()))
            if neighs:
                dst = min(
                    neighs,
                    key=lambda n: (n in blocked_corners, opp.get(n, 0), my.get(n, 0)),
                )
                avail[src] = 0
                avail_total -= cnt
                cmds.append(f"MOVE {src} {dst} {cnt}")

    # 6. Any leftover units march toward the nearest corner of a capturable triangle where we lack majority
    if avail_total > 0 and cands:
        targets = list({c for t in cands for c in t[:3] if planned_in[c] <= opp.get(c, 0)})
        if targets:
            for src in sorted(avail):
                cnt = avail[src]
                if cnt > 0:
                    dst = min(targets, key=lambda c: (dist(src, c), opp.get(c, 0)))
                    if src != dst and dist(src, dst) < 999:
                        cmds.append(f"MOVE {src} {dst} {cnt}")

    ui = f"v={army} t={len(owned)}"
    print(("MSG " + ui + ";" + ";".join(cmds)) if cmds else ("MSG " + ui), flush=True)
