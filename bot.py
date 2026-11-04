import sys
from collections import deque
import itertools

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

start_my = None
start_opp = None
home_side = set()

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

    if start_my is None:
        start_my = [h for h, cnt in my.items() if cnt > 0]
        start_opp = [h for h, cnt in opp.items() if cnt > 0]
        for h in houses:
            dm = min((dist(h, s) for s in start_my), default=0)
            do = min((dist(h, s) for s in start_opp), default=99)
            if dm <= do:
                home_side.add(h)

    def first_step(src, dst):
        if src == dst:
            return src
        best_n = src
        best_d = 999
        for n in sorted(adj.get(src, ())):
            d = dist(n, dst)
            if d < best_d:
                best_d = d
                best_n = n
        return best_n

    corner_deg = {h: 0 for h in houses}
    for t in tris:
        for c in t[:3]:
            corner_deg[c] += 1

    tri_hub = {}
    for t in tris:
        cs = t[:3]
        s = sum(corner_deg[c] for c in cs)
        adj_t = sum(1 for t2 in tris if len(set(cs) & set(t2[:3])) >= 2)
        tri_hub[cs] = (adj_t, s)

    army = sum(my.values())
    opp_army = sum(opp.values())
    owned = [t for t in tris if t[3] == 0]
    usable = [t for t in owned if all(my.get(c, 0) > 0 for c in t[:3])]
    used_tris = set()
    cmds = []

    # 1. ATTACK only when it's strictly profitable (kills >= 4, or kills >= 3 when army >= 18)
    for t in sorted(
        usable,
        key=lambda tr: max((opp.get(n, 0) for c in tr[:3] for n in adj.get(c, ())), default=0),
        reverse=True,
    ):
        corners = t[:3]
        best_n = None
        best_kill = 0
        for c in corners:
            for n in adj.get(c, ()):
                k = opp.get(n, 0)
                if k > best_kill:
                    best_kill = k
                    best_n = n
        if best_n is not None and (
            best_kill >= 4
            or (best_kill >= 3 and army >= 18 and len(usable) - len(used_tris) >= 2)
            or (best_kill >= 2 and army >= 28 and len(usable) - len(used_tris) >= 3)
        ) and opp.get(best_n, 0) > 0:
            cmds.append(f"ATTACK {corners[0]} {corners[1]} {corners[2]} {best_n}")
            used_tris.add(corners)
            opp[best_n] = 0
            for c in corners:
                my[c] = max(0, my[c] - 1)

    # 2. Staggered engine cycles: split usable owned triangles into a SPAWN group and a HOLD group.
    # Spawning neutralizes a triangle (owner -> None), so spawning on ALL of them at once kills our
    # scoring base AND leaves nothing to spawn on next turn. Instead: high-hub triangles HOLD
    # (keep scoring + stay spawn-ready), low-hub triangles SPAWN this turn. Next turn the roles
    # swap as vacated units restaff the spawn group. This is how Arnaud.Net kept spawning 5-16
    # units/turn while always keeping a scoring base.
    max_army = max(36, opp_army + 12)
    to_spawn = []
    hold_group = []
    if army < max_army:
        spawnable = [t for t in usable if t[:3] not in used_tris]
        # High-hub triangles anchor the most adjacent triangles — keep those scoring.
        spawnable.sort(key=lambda t: (-tri_hub[t[:3]][0], -tri_hub[t[:3]][1]))
        if len(spawnable) >= 4:
            half = (len(spawnable) + 1) // 2
            hold_group = [t[:3] for t in spawnable[:half]]
            spawn_candidates = spawnable[half:]
        elif len(spawnable) >= 2:
            # Small base: still keep the best triangle scoring + spawn-ready, spawn on the rest
            hold_group = [spawnable[0][:3]]
            spawn_candidates = spawnable[1:]
        else:
            # Early game: grow as fast as possible
            spawn_candidates = spawnable
        for t in spawn_candidates:
            if army + len(to_spawn) >= max_army:
                break
            if army + len(to_spawn) < 26 or len(spawn_candidates) - len(to_spawn) > 0 or army <= opp_army + 6:
                to_spawn.append(t[:3])
                used_tris.add(t[:3])

    # 3. Jointly optimize SPAWN corner choices + 1-turn (`d <= 1`) unit movements!
    avail = dict(my)
    locked_end = {h: 0 for h in houses}
    cands = [t for t in tris if t[3] != 0 and t[4]]

    # Keep anchors on triangles that remain owned (not used for SPAWN/ATTACK)
    if army >= 12:
        for t in owned:
            if t[:3] in used_tris:
                continue
            if all(avail.get(c, 0) + locked_end.get(c, 0) > opp.get(c, 0) for c in t[:3]):
                for c in t[:3]:
                    need_hold = max(0, (opp.get(c, 0) + 1) - locked_end.get(c, 0))
                    take = min(avail.get(c, 0), need_hold)
                    avail[c] -= take
                    locked_end[c] += take

    avail_total = sum(avail.values())
    must_vacate = {c for t in tris if t[3] != 0 and not t[4] for c in t[:3]} | {
        c for cs in to_spawn for c in cs
    }
    resettable_tris = [t[:3] for t in tris if (t[3] != 0 and not t[4]) or (t[:3] in to_spawn)]

    opp_tris = [t[:3] for t in tris if t[3] == 1 and all(opp.get(c, 0) > 0 for c in t[:3])]
    attack_danger = set()
    for ot in opp_tris:
        for c in ot:
            attack_danger.update(adj.get(c, ()))

    opp_reach1 = {
        h: opp.get(h, 0) + sum(opp.get(n, 0) for n in adj.get(h, ()) if n not in home_side or opp.get(n, 0) > 0)
        for h in houses
    }

    cand_home_deg = {
        h: sum(1 for tr in cands if h in tr[:3] and tr[:3] not in used_tris and all(c in home_side for c in tr[:3]))
        for h in houses
    }
    cand_any_deg = {
        h: sum(1 for tr in cands if h in tr[:3] and tr[:3] not in used_tris and opp.get(h, 0) == 0)
        for h in houses
    }
    blocked_deg = {
        h: sum(1 for tr in tris if h in tr[:3] and (not tr[4] or tr[:3] in used_tris))
        for h in houses
    }

    # 4. Greedy assignment to capture triangles (me_cap=True, owner!=0) with available units (`avail`).
    # 4A. First find all triangles that can be captured THIS turn (`max_d <= 1`)!
    imm_cands = [
        t
        for t in cands
        if all(
            locked_end.get(c, 0)
            + sum(avail.get(u, 0) for u in houses if dist(u, c) <= 1)
            + sum(1 for sp in to_spawn if c in sp)
            > opp.get(c, 0)
            for c in t[:3]
        )
    ]
    if len(imm_cands) > 7:
        imm_cands.sort(
            key=lambda t: (
                0 if all(c in home_side for c in t[:3]) else 1,
                0 if t[3] == 1 else 1,
                -tri_hub[t[:3]][0],
                -tri_hub[t[:3]][1],
            )
        )
        imm_cands = imm_cands[:7]

    def can_satisfy(sub, cur_avail, cur_locked):
        corners_set = {c for t in sub for c in t[:3]}
        reqs = {c: max(0, (opp.get(c, 0) + 1) - cur_locked.get(c, 0)) for c in corners_set}

        sp_choices = []
        used_sp_corners = set()
        for corners in to_spawn:
            best_c = max(
                corners,
                key=lambda c: (
                    2 if reqs.get(c, 0) > 0 else (1 if (c in corners_set and c not in used_sp_corners) else 0),
                    -sum(cur_avail.get(u, 0) for u in houses if dist(u, c) <= 1) if reqs.get(c, 0) > 0 else -999,
                    0 if c not in used_sp_corners else -1,
                    cand_home_deg[c],
                    cand_any_deg[c],
                    -blocked_deg[c],
                    corner_deg[c],
                ),
            )
            sp_choices.append((corners, best_c))
            used_sp_corners.add(best_c)
            if reqs.get(best_c, 0) > 0:
                reqs[best_c] -= 1

        total_add = sum(reqs.values())
        if total_add > sum(cur_avail.values()):
            return None

        rem_avail = dict(cur_avail)
        moves = []
        order = sorted(
            [c for c, r in reqs.items() if r > 0],
            key=lambda c: sum(rem_avail.get(u, 0) for u in houses if dist(u, c) <= 1),
        )
        for c in order:
            need = reqs[c]
            srcs = [u for u in houses if rem_avail.get(u, 0) > 0 and dist(u, c) <= 1]
            srcs.sort(
                key=lambda u: (
                    0 if (u in must_vacate and u != c) else 1,
                    sum(1 for t_c in order if dist(u, t_c) <= 1),
                    dist(u, c),
                    -corner_deg.get(u, 0),
                )
            )
            for u in srcs:
                cnt = rem_avail[u]
                take = cnt if cnt < need else need
                if take > 0:
                    rem_avail[u] -= take
                    need -= take
                    moves.append((u, c, take))
                    if need == 0:
                        break
            if need > 0:
                return None
        end_sp = {c for _, c in sp_choices} | corners_set
        resets = sum(1 for rt in resettable_tris if not any(c in end_sp for c in rt))
        reach_sc = sum(cand_home_deg[c] * 3 + cand_any_deg[c] for _, c in sp_choices)
        return sp_choices, moves, total_add, resets, reach_sc

    best_imm = None
    if imm_cands:
        n_imm = len(imm_cands)
        subsets_to_try = []
        for r in range(min(3, n_imm), 0, -1):
            subsets_to_try.extend(itertools.combinations(imm_cands, r))
        for sub in subsets_to_try:
            res = can_satisfy(sub, avail, locked_end)
            if res is not None:
                sp_choices, moves, total_add, resets, reach_sc = res
                opp_owned = sum(1 for t in sub if t[3] == 1)
                home_cnt = sum(1 for t in sub if all(c in home_side for c in t[:3]))
                safe_cnt = sum(1 for t in sub if all(opp_reach1.get(c, 0) == 0 for c in t[:3]))
                hub_sc = sum(tri_hub[t[:3]][0] * 10 + tri_hub[t[:3]][1] for t in sub)
                sc = (len(sub), safe_cnt, home_cnt, opp_owned, reach_sc, resets, -total_add, hub_sc)
                if best_imm is None or sc > best_imm[0]:
                    best_imm = (sc, sub, sp_choices, moves)

    if best_imm is not None:
        _, sub, sp_choices, moves = best_imm
        for corners, best_c in sp_choices:
            others = [c for c in corners if c != best_c]
            cmds.append(f"SPAWN {best_c} {others[0]} {others[1]}")
            locked_end[best_c] = locked_end.get(best_c, 0) + 1
        for t in sub:
            if t in cands:
                cands.remove(t)
        for src, dst, take in moves:
            avail[src] -= take
            avail_total -= take
            locked_end[dst] = locked_end.get(dst, 0) + take
            if src != dst:
                cmds.append(f"MOVE {src} {dst} {take}")
    else:
        for corners in to_spawn:
            best_c = max(
                corners,
                key=lambda c: (
                    c in home_side,
                    cand_home_deg[c],
                    cand_any_deg[c],
                    -blocked_deg[c],
                    corner_deg[c],
                    -opp.get(c, 0),
                ),
            )
            others = [c for c in corners if c != best_c]
            cmds.append(f"SPAWN {best_c} {others[0]} {others[1]}")
            locked_end[best_c] = locked_end.get(best_c, 0) + 1

    forbidden_end = set()
    for rt in resettable_tris:
        if all(locked_end.get(c, 0) == 0 for c in rt):
            forbidden_end.update(rt)

    # 4B. REFILL spawn-ready corners BEFORE captures: owned triangles with an empty corner
    # cannot SPAWN (spawn needs >= 1 unit on every corner). This is the spawn engine —
    # without refill the engine dies and we stop growing (how Arnaud.Net outran us).
    # Runs before capture assignment so engines always get their units first.
    hold_corners = [c for cs in hold_group for c in cs]
    engine_tris = hold_group + [
        t[:3] for t in owned if t[:3] not in used_tris and t[:3] not in hold_group
    ]
    # Sort engines: hold_group first (spawn-ready next turn), then fewest missing corners
    engine_tris.sort(
        key=lambda cs: (
            0 if cs in hold_group else 1,
            sum(1 for c in cs if locked_end.get(c, 0) == 0),
            -tri_hub[cs][0],
            -tri_hub[cs][1],
        )
    )
    for cs in engine_tris:
        if avail_total <= 0:
            break
        for c in cs:
            if locked_end.get(c, 0) == 0 and avail_total > 0:
                # Few engines left -> unlimited reach, we MUST bring the engine back online
                reach = 999 if len(engine_tris) <= 2 else (3 if cs in hold_group else 2)
                srcs = [u for u in houses if avail.get(u, 0) > 0 and dist(u, c) <= reach and (u != c or u not in must_vacate)]
                if srcs:
                    srcs.sort(key=lambda u: (dist(u, c), -avail[u]))
                    u = srcs[0]
                    avail[u] -= 1
                    avail_total -= 1
                    step = first_step(u, c)
                    locked_end[step] = locked_end.get(step, 0) + 1
                    if u != c:
                        cmds.append(f"MOVE {u} {c} 1")

    # 4C. Greedy assignment for remaining triangles.
    stay_home = opp_army > 0 and army < opp_army + 10
    max_allowed_d = 2 if (stay_home and best_imm is not None) else 999

    # REBUILD MODE: when we own NO triangles (scoring base wiped by opponent ATTACK),
    # drop all territorial restrictions and throw everything at the single fastest capturable
    # triangle — restoring the spawn engine matters more than safety or position.
    # (Only after the game has progressed — at turn 1 nothing is owned by anyone yet.)
    rebuild = len(owned) == 0 and cands and (my_score > 0 or opp_score > 0) and army > 0
    if rebuild:
        stay_home = False
        max_allowed_d = 999
        src_houses = [u for u in houses if avail.get(u, 0) > 0]
        if src_houses:
            cands.sort(
                key=lambda t: (
                    max(min(dist(u, c) for u in src_houses) for c in t[:3]),
                    -tri_hub[t[:3]][0],
                )
            )
        cands = cands[:1]

    while avail_total > 0 and cands:
        best = None
        active_srcs = [h for h, cnt in avail.items() if cnt > 0]
        for t in cands:
            corners = t[:3]
            if stay_home and best_imm is not None and not all(c in home_side for c in corners):
                continue
            temp_avail = dict(avail)
            temp_locked = dict(locked_end)
            moves = []
            max_d = 0
            sum_d = 0
            total_req = 0
            ok = True
            ordered_corners = sorted(
                corners,
                key=lambda c: sum(temp_avail.get(u, 0) for u in active_srcs if dist(u, c) <= 2),
            )
            for target in ordered_corners:
                need = (opp.get(target, 0) + 1) - temp_locked.get(target, 0)
                if need <= 0:
                    continue
                rem = need
                by_d = sorted(
                    active_srcs,
                    key=lambda h: (
                        dist(h, target),
                        0 if (h in must_vacate and h != target) else 1,
                        -temp_avail.get(h, 0),
                    ),
                )
                for h in by_d:
                    cnt = temp_avail.get(h, 0)
                    if cnt <= 0:
                        continue
                    d = dist(h, target)
                    if d > max_allowed_d:
                        break
                    step = first_step(h, target)
                    if d > 1 and step in forbidden_end:
                        continue
                    take = cnt if cnt < rem else rem
                    temp_avail[h] = cnt - take
                    rem -= take
                    total_req += take
                    moves.append((h, target, take, d))
                    if d > max_d:
                        max_d = d
                    sum_d += d * take
                    if rem == 0:
                        break
                if rem > 0:
                    ok = False
                    break
                arrived = sum(tk for h, tg, tk, d in moves if tg == target and d <= 1)
                temp_locked[target] = temp_locked.get(target, 0) + arrived
            if not ok:
                continue
            adj_t, deg_sum = tri_hub[corners]
            shared_ready = sum(1 for c in corners if locked_end.get(c, 0) > opp.get(c, 0))
            is_home = 0 if all(c in home_side for c in corners) else 1
            score = (
                0 if max_d <= 1 else max_d,
                is_home,
                total_req if max_d <= 1 else 0,
                -shared_ready if max_d <= 1 else 0,
                total_req,
                0 if t[3] == 1 else 1,
                -adj_t,
                -deg_sum,
                sum_d,
            )
            if best is None or score < best[0]:
                best = (score, moves, t, total_req, max_d)
        if best is None:
            break
        _, moves, t, total_req, max_d = best
        cands.remove(t)
        avail_total -= total_req
        for src, dst, take, d in moves:
            avail[src] -= take
            step = first_step(src, dst)
            if max_d > 1 and src == dst and src in must_vacate:
                avail[src] += take
                avail_total += take
                continue
            locked_end[step] = locked_end.get(step, 0) + take
            if src != dst:
                cmds.append(f"MOVE {src} {dst} {take}")

    # 4D. Stage any remaining units (`avail`) toward the BEST local uncaptured triangle on `home_side`,
    # assigning 1 unit per needed corner of that triangle before moving on to the next triangle!
    rem_units = []
    for src in sorted(avail):
        rem_units.extend([src] * avail[src])

    if rebuild:
        local_cands = list(cands)
    else:
        home_cands = [t for t in cands if all(c in home_side for c in t[:3])]
        local_cands = home_cands if (stay_home and home_cands) else list(cands)

    if rem_units and local_cands:
        local_cands.sort(
            key=lambda t: (
                0 if all(c in home_side for c in t[:3]) else 1,
                max(min(dist(u, c) for u in rem_units) if locked_end.get(c, 0) <= opp.get(c, 0) else 0 for c in t[:3]),
                sum(min(dist(u, c) for u in rem_units) if locked_end.get(c, 0) <= opp.get(c, 0) else 0 for c in t[:3]),
                -tri_hub[t[:3]][0],
                -tri_hub[t[:3]][1],
            )
        )
        staged_targets = set()
        for t in local_cands:
            if not rem_units:
                break
            for c in t[:3]:
                if c in staged_targets:
                    continue
                need = (opp.get(c, 0) + 1) - locked_end.get(c, 0)
                while need > 0 and rem_units:
                    valid_u = []
                    for u in set(rem_units):
                        if u == c and u in must_vacate:
                            continue
                        step = first_step(u, c)
                        if step in forbidden_end:
                            continue
                        if stay_home and step not in home_side and u in home_side:
                            continue
                        if step in attack_danger and locked_end.get(step, 0) >= 2:
                            continue
                        valid_u.append(u)
                    if not valid_u:
                        break
                    best_u = min(
                        valid_u,
                        key=lambda u: (
                            dist(first_step(u, c), c),
                            locked_end.get(first_step(u, c), 0),
                            dist(u, c),
                            u not in must_vacate,
                        ),
                    )
                    rem_units.remove(best_u)
                    step = first_step(best_u, c)
                    locked_end[step] = locked_end.get(step, 0) + 1
                    need -= 1
                    if best_u != c:
                        cmds.append(f"MOVE {best_u} {c} 1")
                if need <= 0:
                    staged_targets.add(c)

    # 5B. Capture ALL currently-OWNED triangles (`owner == 0`) whose corners we can fully staff this turn
    # so they keep scoring! Their units stay on the corners (no `me_cap` reset needed since owner==0 already).
    scoring_hold = [t[:3] for t in owned if t[:3] not in used_tris]
    for cs in scoring_hold:
        for c in cs:
            if locked_end.get(c, 0) == 0 and rem_units:
                # Prefer a unit already adjacent (d<=1) so it stays on the corner this turn
                valid_u = [u for u in set(rem_units) if dist(u, c) <= 1 and (u != c or u not in must_vacate)]
                if valid_u:
                    best_u = min(valid_u, key=lambda u: (dist(u, c), u not in must_vacate))
                    rem_units.remove(best_u)
                    step = first_step(best_u, c)
                    locked_end[step] = locked_end.get(step, 0) + 1
                    if best_u != c:
                        cmds.append(f"MOVE {best_u} {c} 1")

    # 5C. Reinforce threatened border corners of captured triangles if spare units remain adjacent
    if best_imm is not None and rem_units:
        _, sub, _, _ = best_imm
        for t in sub:
            for c in t[:3]:
                if opp_reach1.get(c, 0) > opp.get(c, 0) and locked_end.get(c, 0) == opp.get(c, 0) + 1:
                    valid_u = [u for u in set(rem_units) if dist(u, c) <= 1 and (u != c or u not in must_vacate)]
                    if valid_u:
                        best_u = min(valid_u, key=lambda u: (u not in must_vacate, dist(u, c)))
                        rem_units.remove(best_u)
                        locked_end[c] = locked_end.get(c, 0) + 1
                        if best_u != c:
                            cmds.append(f"MOVE {best_u} {c} 1")

    # 6. Any units still on `must_vacate` (or still idle on `home_side`) step to a safe, non-forbidden `home_side` HUB corner!
    for src in rem_units:
        neighs = list(adj.get(src, ()))
        if neighs and (src in must_vacate or src not in home_side or corner_deg.get(src, 0) == 0 or locked_end.get(src, 0) >= 2):
            dst = min(
                neighs,
                key=lambda n: (
                    n in forbidden_end,
                    n not in home_side if stay_home else False,
                    corner_deg.get(n, 0) == 0,
                    n in must_vacate,
                    1 if (n in attack_danger and locked_end.get(n, 0) >= 2) else 0,
                    opp.get(n, 0) > locked_end.get(n, 0) + 1,
                    -cand_home_deg[n],
                    -corner_deg.get(n, 0),
                    locked_end.get(n, 0),
                ),
            )
            locked_end[dst] = locked_end.get(dst, 0) + 1
            cmds.append(f"MOVE {src} {dst} 1")

    ui = f"v={army} t={len(owned)}"
    print(("MSG " + ui + ";" + ";".join(cmds)) if cmds else ("MSG " + ui), flush=True)
