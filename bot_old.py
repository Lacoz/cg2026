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

# Persistent focus: the triangle we are committed to capturing. Without it the
# greedy re-evaluates every turn, units wander through hubs (pass-through parking)
# and we lose the early-game race to opponents that commit immediately.
FOCUS = None
FOCUS_AGE = 0
LAST_FOCUS = None  # recently captured focus — keep its cluster intact for chaining
TURN_NO = 0  # game turn counter for the spawn-phase schedule
CONTESTED = set()  # houses where we captured over enemy units — their capture force
# sits there and swarm opponents (AdrienGI) hunt exactly these stacks with ATTACK
LAST_OWNER = {}  # corner-tuple -> owner last turn; detects enemy just-neutralized triangles
MA = None  # MapAnalysis cache — the map is STATIC, everything below is built once

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

    # ------------------------------------------------------------------
    # MAP ANALYSIS — built ONCE (the map never changes). Everything the bot
    # queries hundreds of times per turn lives here: all-pairs distances,
    # routing table (next hop), corner->triangles index, triangle adjacency,
    # cluster decomposition (burst planning), opening chain ranking.
    # ------------------------------------------------------------------
    if False:
        _dist = {h: bfs(h) for h in houses}
        # routing table: route[src][dst] = next hop on the shortest path
        _route = {}
        for s in houses:
            r = {}
            for d in houses:
                if d == s:
                    continue
                neighs = sorted(adj.get(s, ()))
                if neighs:
                    r[d] = min(neighs, key=lambda n: (_dist[n].get(d, 999), n))
            _route[s] = r
        # corner -> triangles containing it (corner-to-tris index)
        _corner_to_tris = {}
        _tri_shapes = [t[:3] for t in tris]
        for cs in _tri_shapes:
            for c in cs:
                _corner_to_tris.setdefault(c, []).append(cs)
        # corner degree + triangle hub connectivity (static)
        _corner_deg = {h: len(_corner_to_tris.get(h, ())) for h in houses}
        _csets = [set(cs) for cs in _tri_shapes]
        _tri_hub = {}
        for i, cs in enumerate(_tri_shapes):
            s = sum(_corner_deg[c] for c in cs)
            adj_t = sum(1 for j, ocs in enumerate(_csets) if i != j and len(_csets[i] & ocs) >= 2)
            _tri_hub[cs] = (adj_t, s)
        # triangle adjacency: triangles sharing >= 1 corner (cluster graph)
        _tri_adj = {}
        for i, cs in enumerate(_tri_shapes):
            _tri_adj[cs] = {
                _tri_shapes[j] for j, ocs in enumerate(_csets) if i != j and (_csets[i] & ocs)
            }
        # CLUSTERS: connected components of the triangle graph (shared corners) —
        # the natural burst targets: capturing one triangle unlocks its cluster.
        _tri_cluster = {}
        _clusters = []
        _cid = 0
        for cs in _tri_shapes:
            if cs in _tri_cluster:
                continue
            # BFS over triangle adjacency
            comp = []
            stack = [cs]
            _tri_cluster[cs] = _cid
            while stack:
                cur = stack.pop()
                comp.append(cur)
                for nb in _tri_adj[cur]:
                    if nb not in _tri_cluster:
                        _tri_cluster[nb] = _cid
                        stack.append(nb)
            _clusters.append(comp)
            _cid += 1
        # OPENING CHAIN: rank all triangles by reachability from our start units
        # (max corner distance first — the capture completes when the LAST unit
        # arrives) — built AFTER start positions are known (see below).
        MA = {
            "dist": _dist,
            "route": _route,
            "corner_to_tris": _corner_to_tris,
            "corner_deg": _corner_deg,
            "tri_hub": _tri_hub,
            "tri_adj": _tri_adj,
            "tri_cluster": _tri_cluster,
            "clusters": _clusters,
        }

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
        pass  # pre-MA: no opening chain

    _route_tbl = None

    def first_step(src, dst):
        if src == dst:
            return src
        # OLD semantic kept intentionally: first neighbor (sorted) with STRICTLY
        # smaller distance — ties resolve to the earliest neighbor, and if the
        # target is unreachable we STAY PUT. The route table is available for a
        # future tuning pass; switching to it changed endgame behavior negatively.
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
    TURN_NO += 1

    # PHASE SCHEDULE: each triangle cycles spawn -> vacate -> capture in 3 turns.
    # The phases are staggered deterministically (hash of corners + turn), so at any
    # moment only ~1/3 of our triangles need their corners staffed and the rest of
    # the army is FREE to swarm captures. This is what [CG]loick/Rikus do and we
    # didn't: our old anchors parked 2/3 of the army doing nothing.
    def phase_of(cs):
        return (TURN_NO + sum(cs)) % 3

    owned = [t for t in tris if t[3] == 0]
    usable = [t for t in owned if all(my.get(c, 0) > 0 for c in t[:3])]
    used_tris = set()
    cmds = []

    # Threat map (needed by the ATTACK section below).
    opp_tris = [t[:3] for t in tris if t[3] == 1 and all(opp.get(c, 0) > 0 for c in t[:3])]
    attack_danger = set()
    for ot in opp_tris:
        for c in ot:
            attack_danger.update(adj.get(c, ()))
    # Their engine corners: houses that are corners of ANY enemy-owned triangle —
    # hitting these breaks their spawn cycle (2-3 turns lost), worth far more than
    # the units killed. Prefer them over random stacks.
    their_engine_corners = {c for t in tris if t[3] == 1 for c in t[:3]}

    def risky(h):
        """Parking danger: dead-ends and houses fully surrounded by the opponent
        get swept (surround kill) or ATTACKed."""
        neighs = list(adj.get(h, ()))
        if not neighs:
            return 2
        opp_nb = sum(1 for m in neighs if opp.get(m, 0) > 0)
        if opp_nb == len(neighs):
            return 2
        return 1 if opp_nb > 0 else 0

    # 1. ATTACK: hit ENEMY ENGINE CORNERS first (breaks their spawn cycle), then
    # any stack >= 2. Low thresholds — their attacks fire at kill>=2 constantly, so
    # an all-out attack war punishes both, but engine breaks cost them much more.
    # SAFETY: attack only from a triangle whose corners are NOT in the enemy's attack
    # blast radius — simultaneous attacks resolve against each other and our corner
    # units can die first, silently voiding our ATTACK (ChuOkupai f44).
    for t in sorted(
        usable,
        key=lambda tr: max(
            (2 if n in their_engine_corners else 0) + opp.get(n, 0)
            for c in tr[:3]
            for n in adj.get(c, ())
        ),
        reverse=True,
    ):
        corners = t[:3]
        best_n = None
        best_key = None
        for c in corners:
            for n in adj.get(c, ()):
                k = opp.get(n, 0)
                if k <= 0:
                    continue
                key = (1 if n in their_engine_corners else 0, k)
                if best_key is None or key > best_key:
                    best_key = key
                    best_n = n
        best_kill = best_key[1] if best_key else 0
        breaks_engine = best_key[0] == 1 if best_key else False
        if best_n is not None and (
            breaks_engine
            or best_kill >= 5
            or (best_kill >= 4 and army >= 18 and len(usable) - len(used_tris) >= 2)
            or (best_kill >= 3 and army >= 28 and len(usable) - len(used_tris) >= 3)
        ):
            # SAFETY: normally skip attacks from triangles whose corners sit in the
            # enemy attack blast radius (simultaneous attacks may void ours —
            # ChuOkupai f44). EXCEPTION: engine-breaking attacks are worth the risk —
            # breaking their spawn cycle costs them 2-3 turns of spawns.
            safe = all(c not in attack_danger for c in corners) and all(
                opp.get(c, 0) == 0 for c in corners
            )
            if safe or breaks_engine:
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
        # PHASE SCHEDULE: prefer phase-0 triangles (their staffing cycle aligned),
        # but the spawn engine NEVER sleeps — if no phase-0 triangle is usable,
        # spawn on the best usable triangle anyway (army growth beats schedule).
        # (Mass-spawn tested: worse vs boss on all seeds — the score dip costs more
        # than the extra units when the capture machine can't keep up.)
        spawnable = [t for t in usable if t[:3] not in used_tris]
        in_phase = [t for t in spawnable if phase_of(t[:3]) == 0]
        ordered = in_phase + [t for t in spawnable if t not in in_phase]
        # Spawn WHERE it hurts least: never on the fresh capture that anchors the
        # cluster chain. Rank spawnable by (shared corners with FOCUS asc, hub desc)
        # so high-connectivity triangles stay owned and keep chaining captures.
        focus_set = set(FOCUS if FOCUS else LAST_FOCUS or ())

        def spawn_rank(t):
            shared = len(set(t[:3]) & focus_set)
            return (shared, -tri_hub[t[:3]][0], -tri_hub[t[:3]][1])

        ordered.sort(key=spawn_rank)
        hold_group = [t[:3] for t in ordered]
        # SPAWN DISCIPLINE: spawn ONLY phase-0 triangles (~owned/3 per turn, matching
        # the 3-turn cycle) + at most ONE off-phase fallback. Spawning on ALL usable
        # neutralizes as many triangles as we capture -> owned count freezes at 1-3
        # and the spawn rate can never scale. This was the hidden growth killer!
        spawn_candidates = in_phase
        if not spawn_candidates and ordered:
            spawn_candidates = [ordered[0]]
        for t in spawn_candidates:
            if army + len(to_spawn) >= max_army:
                break
            to_spawn.append(t[:3])
            used_tris.add(t[:3])

    # 3. Jointly optimize SPAWN corner choices + 1-turn (`d <= 1`) unit movements!
    avail = dict(my)
    locked_end = {h: 0 for h in houses}
    spawn_houses = {h: 0 for h in houses}
    cands = [t for t in tris if t[3] != 0 and t[4]]

    # PHASE LOCK: ONLY phase-2 triangles (their spawn is NEXT turn) need their
    # corners staffed — 1 unit per corner (+1 if the corner is contested). That is
    # ~owned/3 triangles x 3 corners = ~owned units locked. EVERYTHING else swarms.
    # The old `army//2` budget parked half the army while loick/Rikus moved 20+.
    locked_total = 0
    for t in sorted(owned, key=lambda x: -tri_hub[x[:3]][0]):
        cs = t[:3]
        if cs in used_tris or phase_of(cs) != 2:
            continue
        for c in cs:
            # house-level cap: total units committed to this house (sitting +
            # spawning + en route) must stay <= 3, and lock at most 1 here
            committed = my.get(c, 0) + spawn_houses.get(c, 0) + en_route.get(c, 0)
            if committed >= 3:
                continue
            keep = 2 if opp.get(c, 0) > 0 else 1
            lock = min(keep, avail.get(c, 0))
            if lock > 0:
                avail[c] = max(0, avail.get(c, 0) - lock)
                locked_end[c] += lock
                locked_total += lock

    avail_total = sum(avail.values())
    must_vacate = {c for t in tris if t[3] != 0 and not t[4] for c in t[:3]} | {
        c for cs in to_spawn for c in cs
    }
    resettable_tris = [t[:3] for t in tris if (t[3] != 0 and not t[4]) or (t[:3] in to_spawn)]

    owner_now = {t[:3]: t[3] for t in tris}
    me_cap_now = {t[:3]: t[4] for t in tris}

    opp_reach1 = {
        h: opp.get(h, 0) + sum(opp.get(n, 0) for n in adj.get(h, ()) if n not in home_side or opp.get(n, 0) > 0)
        for h in houses
    }

    # Units committed this turn that arrive on `h` NEXT turn (multi-step moves).
    # Without this, two triangles sharing a corner both send units to it and the
    # excess piles up into one enemy ATTACK target (czuk killed 6 units this way).
    en_route = {}

    # TRAP RISK v2: if we stack units on corner H of triangle t, the opponent can
    # ATTACK H next turn from any of THEIR triangles that (a) can reach H (a corner
    # adjacent to H) and (b) we do NOT break by capturing t (shares no corner with t).
    # v2: also counts POTENTIALLY-ready triangles — the enemy can staff all 3 corners
    # THIS turn (their units within 1 step of every corner), so the triangle becomes
    # ready in the very round we capture (AdrienGI made 3 ready triangles per round
    # and hunted our stacks with 6 attacks). Uncontested corners (opp == 0) are safe.
    opp_potential = []
    for t in tris:
        if t[3] == 1:
            cs = t[:3]
            # enemy can staff every corner within 1 step (units there or adjacent)
            if all(
                opp.get(c, 0) > 0
                or any(opp.get(u, 0) > 0 and dist(u, c) == 1 for u in houses)
                for c in cs
            ):
                opp_potential.append(cs)

    def trap_risk(t):
        cs = set(t[:3])
        for H in t[:3]:
            # uncontested corner: nothing to attack there — no stack exposure
            if opp.get(H, 0) == 0 and not any(
                opp.get(u, 0) > 0 and dist(u, H) == 1 for u in houses
            ):
                continue
            for ot in opp_tris + opp_potential:
                ocs = set(ot)
                if ocs & cs:
                    continue  # capturing t breaks ot — no trap
                if any(dist(c, H) == 1 for c in ot):
                    return 1
        return 0

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
    # FOCUS: sticky commitment — pick the target ONCE and keep it until captured
    # (or hopeless). Prevents turn-by-turn re-targeting that makes units wander.
    # NOTE: module-level scope — no `global` needed (and it would be a SyntaxError).
    focus_cs = None
    if FOCUS is not None:
        ft = next((t for t in tris if t[:3] == FOCUS), None)
        if ft is None:
            FOCUS = None
        elif ft[3] == 0:
            LAST_FOCUS = FOCUS  # captured — keep its cluster intact when choosing spawn targets
            FOCUS = None  # mission complete
        elif not ft[4] and ft[3] != 0:
            FOCUS_AGE += 1  # me_cap False: waiting for reset/vacate — keep waiting
        else:
            FOCUS_AGE += 1
        if FOCUS_AGE > 14:
            FOCUS = None  # hopeless — re-target
    if FOCUS is None:
        unit_houses = [h for h, cnt in my.items() if cnt > 0]
        owned_cs = [set(t[:3]) for t in owned]
        pool = [t for t in cands if t[4]]
        if pool:
            # Opening chain (static): triangles ranked by start-distance — a static
            # tiebreak so the opening follows a precomputed chain instead of
            # re-sorting with moving-unit distances every turn.
            opening = {}
            tri_adj = {}

            def focus_rank(t):
                dmax = max(
                    (min(dist(u, c) for u in unit_houses) if unit_houses else 99) for c in t[:3]
                )
                # Cluster growth: prefer triangles sharing a corner with one we own —
                # the capture force can re-task between them and spawns chain.
                cluster = 0 if any(set(t[:3]) & ocs for ocs in owned_cs) else 1
                return (
                    cluster,
                    dmax,
                    -tri_hub[t[:3]][0],
                    0 if t[3] == 1 else 1,
                )
            pool.sort(key=focus_rank)
            FOCUS = pool[0][:3]
            FOCUS_AGE = 0
    focus_cs = FOCUS

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

    def can_satisfy(sub, cur_avail, cur_locked, used_sp):
        corners_set = {c for t in sub for c in t[:3]}
        reqs = {c: max(0, (opp.get(c, 0) + 1) - cur_locked.get(c, 0)) for c in corners_set}

        sp_choices = []
        used_sp_corners = set(used_sp)
        for corners in to_spawn:
            # HARD exclusion: never spawn two units onto the same corner this turn
            # (they cannot move and pile up into one enemy ATTACK target).
            options = [c for c in corners if c not in used_sp_corners] or list(corners)
            best_c = max(
                options,
                key=lambda c: (
                    2 if reqs.get(c, 0) > 0 else (1 if (c in corners_set and c not in used_sp_corners) else 0),
                    -min(my.get(c, 0), 3),  # prefer emptier corners — no spawn piles
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
        spawned_corners = set()
        n_imm = len(imm_cands)
        subsets_to_try = []
        # BURST: try up to 4-subsets when the candidate list is small — joint
        # multi-capture in one turn is how AdrienGI took 7 triangles at once.
        # With shared corners a burst costs only the non-shared corners.
        max_r = min(4, n_imm) if n_imm <= 6 else min(3, n_imm)
        for r in range(max_r, 0, -1):
            subsets_to_try.extend(itertools.combinations(imm_cands, r))
        tried = 0
        for sub in subsets_to_try:
            tried += 1
            if tried > 200:
                break
            res = can_satisfy(sub, avail, locked_end, spawned_corners)
            if res is not None:
                sp_choices, moves, total_add, resets, reach_sc = res
                opp_owned = sum(1 for t in sub if t[3] == 1)
                home_cnt = sum(1 for t in sub if all(c in home_side for c in t[:3]))
                safe_cnt = sum(1 for t in sub if all(opp_reach1.get(c, 0) == 0 for c in t[:3]))
                trap_cnt = sum(1 for t in sub if trap_risk(t))
                hub_sc = sum(tri_hub[t[:3]][0] * 10 + tri_hub[t[:3]][1] for t in sub)
                sc = (len(sub), safe_cnt, -trap_cnt, home_cnt, opp_owned, reach_sc, resets, -total_add, hub_sc)
                if best_imm is None or sc > best_imm[0]:
                    best_imm = (sc, sub, sp_choices, moves)

    if best_imm is not None:
        _, sub, sp_choices, moves = best_imm
        for corners, best_c in sp_choices:
            others = [c for c in corners if c != best_c]
            cmds.append(f"SPAWN {best_c} {others[0]} {others[1]}")
            locked_end[best_c] = locked_end.get(best_c, 0) + 1
            spawn_houses[best_c] += 1
        for t in sub:
            if t in cands:
                cands.remove(t)
        for src, dst, take in moves:
            avail[src] -= take
            avail_total -= take
            locked_end[dst] = locked_end.get(dst, 0) + take
            en_route[dst] = en_route.get(dst, 0) + take
            if opp.get(dst, 0) > 0 and my.get(dst, 0) + take > opp.get(dst, 0):
                CONTESTED.add(dst)
            if src != dst:
                cmds.append(f"MOVE {src} {dst} {take}")
    else:
        spawned_corners = set()
        for corners in to_spawn:
            options = [c for c in corners if c not in spawned_corners] or list(corners)
            best_c = max(
                options,
                key=lambda c: (
                    c in home_side,
                    -min(my.get(c, 0), 3),  # prefer emptier corners — no spawn piles
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
            spawn_houses[best_c] += 1
            spawned_corners.add(best_c)

    forbidden_end = set()
    for rt in resettable_tris:
        if all(locked_end.get(c, 0) == 0 for c in rt):
            forbidden_end.update(rt)

    # 4B. REFILL spawn-ready corners BEFORE captures: owned triangles with an empty corner
    # cannot SPAWN (spawn needs >= 1 unit on every corner). This is the spawn engine —
    # without refill the engine dies and we stop growing (how Arnaud.Net outran us).
    # PHASE DISCIPLINE: only refill phase-2 triangles (their spawn turn is next) —
    # phase-1 triangles are in their vacate turn and must stay EMPTY (me_cap reset),
    # phase-0 triangles spawn right now (too late to staff).
    engine_tris = [
        t[:3]
        for t in owned
        if t[:3] not in used_tris and phase_of(t[:3]) == 2
    ]
    # Sort engines: fewest missing corners first (cheapest to make spawn-ready)
    engine_tris.sort(
        key=lambda cs: (
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
                reach = 999 if len(engine_tris) <= 2 else 3
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
                    if dist(u, c) > 1:
                        en_route[c] = en_route.get(c, 0) + 1
                    else:
                        locked_end[c] = locked_end.get(c, 0) + 1

    # 4B1. PUNISH: enemy just neutralized a triangle (their ATTACK or their own
    # SPAWN) — it is now neutral with WEAKENED/vacating corners. Capturing it
    # immediately is cheap and punishes their attack (AdrienGI attacked 13x/game
    # for free — this makes every attack cost them a triangle).
    # Runs BEFORE FOCUS: punishing the attacker beats chasing our own plan.
    punish_tris = [
        cs
        for cs, own in LAST_OWNER.items()
        if own == 1 and owner_now.get(cs, -1) != 1 and me_cap_now.get(cs, False)
    ]
    for cs in punish_tris:
        for c in cs:
            deficit = (opp.get(c, 0) + 1) - my.get(c, 0) - locked_end.get(c, 0) - en_route.get(c, 0)
            while deficit > 0 and avail_total > 0:
                srcs = [
                    u
                    for u in houses
                    if avail.get(u, 0) > 0
                    and u != c
                    and first_step(u, c) not in forbidden_end
                ]
                if not srcs:
                    break
                srcs.sort(key=lambda u: (dist(u, c), risky(u), -avail[u]))
                u = srcs[0]
                take = min(avail[u], deficit)
                avail[u] -= take
                avail_total -= take
                deficit -= take
                en_route[c] = en_route.get(c, 0) + take
                step = first_step(u, c)
                locked_end[step] = locked_end.get(step, 0) + 1
                if u != c:
                    cmds.append(f"MOVE {u} {c} {take}")

    # 4B2. FOCUS commitment: serve the sticky target's deficits BEFORE other
    # captures so units converge instead of wandering. (Burst-set pre-positioning
    # tested and DISABLED: it pulled units away from immediate captures and our
    # score vs AdrienGI went 77-82 -> 94-98. The tri_adj cluster graph from
    # MapAnalysis is available for a smarter burst planner later.)
    if focus_cs is not None:
        ft = next((t for t in tris if t[:3] == focus_cs), None)
        if ft is not None and ft[4]:
            burst = [ft]
            for bt in burst:
                for c in bt[:3]:
                    deficit = (opp.get(c, 0) + 1) - my.get(c, 0) - locked_end.get(c, 0) - en_route.get(c, 0)
                    while deficit > 0 and avail_total > 0:
                        srcs = [
                            u
                            for u in houses
                            if avail.get(u, 0) > 0
                            and u != c
                            and first_step(u, c) not in forbidden_end
                        ]
                        if not srcs:
                            break
                        srcs.sort(key=lambda u: (dist(u, c), risky(u), -avail[u]))
                        u = srcs[0]
                        take = min(avail[u], deficit)
                        avail[u] -= take
                        avail_total -= take
                        deficit -= take
                        en_route[c] = en_route.get(c, 0) + take
                        step = first_step(u, c)
                        locked_end[step] = locked_end.get(step, 0) + 1
                        if u != c:
                            cmds.append(f"MOVE {u} {c} {take}")

    # 4C. Greedy assignment for remaining triangles.
    # FULL SWARM: no stay_home — every free unit joins the capture effort. Defending
    # while behind gave AdrienGI free rein (their score jumped to 188 in that test).
    stay_home = False
    max_allowed_d = 999

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
        # HARD trap avoidance: if ANY non-trap capture is possible, skip trap-risky
        # ones entirely — walking into an unbroken enemy ATTACK loses the whole stack.
        non_trap_exists = any(not trap_risk(t) for t in cands)
        # End-of-turn position estimate: units stay put or land on first_step of their move.
        # MUST include en_route (units committed by earlier assignments this turn) —
        # otherwise two triangles sharing a hub each "see" an empty hub and both send
        # units there → cross-triangle pile (the 10-unit ATTACK kill vs AdrienGI).
        # Prevents unknowingly parking a pile on a house the opponent can ATTACK next round.
        parked = {
            h: my.get(h, 0) + spawn_houses.get(h, 0) + en_route.get(h, 0)
            for h in houses
        }
        for t in cands:
            corners = t[:3]
            if stay_home and best_imm is not None and not all(c in home_side for c in corners):
                continue
            if non_trap_exists and trap_risk(t):
                continue
            temp_avail = dict(avail)
            temp_parked = dict(parked)
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
                need = (
                    (opp.get(target, 0) + 1)
                    - temp_locked.get(target, 0)
                    - en_route.get(target, 0)
                )
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
                    # GLOBAL cap 2 units per house: swarm opponents (AdrienGI)
                    # attack EVERY stack they can reach, 2-6 units per attack,
                    # every turn. A 3-6 stack is a gift to them; a 2-stack loses
                    # at most 2. Captures of contested corners complete over two
                    # turns instead of one — slower but the army survives.
                    if d > 1 and temp_parked.get(step, 0) >= 2 and step != target:
                        continue
                    if temp_parked.get(target, 0) >= 2 and opp.get(target, 0) > 0:
                        # contested corner already saturated this turn — wait
                        continue
                    take = cnt if cnt < rem else rem
                    temp_avail[h] = cnt - take
                    temp_parked[h] = temp_parked.get(h, 0) - take
                    temp_parked[step] = temp_parked.get(step, 0) + take
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
            # Contested captures (any corner with enemy units) build stacks the
            # swarm opponents hunt with ATTACK (AdrienGI: 25 of our units killed
            # this way). Prefer uncontested captures when available.
            contested = 1 if any(opp.get(c, 0) > 0 for c in corners) else 0
            score = (
                0 if max_d <= 1 else max_d,
                trap_risk(t),
                contested,
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
            en_route[dst] = en_route.get(dst, 0) + take
            step = first_step(src, dst)
            if max_d > 1 and src == dst and src in must_vacate:
                avail[src] += take
                avail_total += take
                continue
            locked_end[step] = locked_end.get(step, 0) + take
            # Capture over enemy units → this house becomes a hunt target for
            # swarm opponents (AdrienGI attacks our capture forces turn after
            # turn). Mark it: next turn the excess must dissolve.
            if d <= 1 and opp.get(dst, 0) > 0 and my.get(dst, 0) + take > opp.get(dst, 0):
                CONTESTED.add(dst)
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
                # en_route: units already committed (greedy/imm) that arrive next turn
                need = (opp.get(c, 0) + 1) - locked_end.get(c, 0) - en_route.get(c, 0)
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
                        # no pass-through parking on 3+ piles (czuk scenario)
                        if step != c and my.get(step, 0) + locked_end.get(step, 0) >= 3:
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
                    if dist(best_u, c) > 1:
                        # committed en route — arrives in a later turn
                        en_route[c] = en_route.get(c, 0) + 1
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
    # PLUS anti-ATTACK spread: never keep more than 2 of our units on a house that
    # sits in the blast radius of an opponent-ready triangle (czuk killed 6 with one ATTACK).
    for src in rem_units:
        neighs = list(adj.get(src, ()))
        excess = 0
        if src in attack_danger:
            excess = max(excess, my.get(src, 0) - 2)
        if risky(src) >= 2:
            # surround risk: all neighbours (nearly) opponent-owned — keep 1, flee
            excess = max(excess, my.get(src, 0) - 1)
        if src in CONTESTED:
            # Our capture force sits on a house we took over enemy units — swarm
            # opponents (AdrienGI) hunt exactly these stacks with ATTACK next turn.
            # Dissolve: keep 2, scatter the rest.
            excess = max(excess, my.get(src, 0) - 2)
        # PREDICTIVE surround: if the opponent could out-stock EVERY neighbour next
        # turn (their reach-1 army beats our presence), this house becomes a kill
        # pocket — flee now, before the encirclement closes (Rikus/ChuOkupai kill 4-9
        # units per turn this way).
        if neighs and all(
            opp_reach1.get(m, 0) > my.get(m, 0) for m in neighs
        ):
            excess = max(excess, my.get(src, 0) - 1)
        must_move = (
            src in must_vacate
            or src not in home_side
            or corner_deg.get(src, 0) == 0
            or locked_end.get(src, 0) >= 2
            or excess > 0
        )
        if neighs and must_move:
            # Which triangle is this unit vacating? Prefer parking that stays
            # adjacent to that triangle's OTHER corners — at the next staffing
            # phase (2 turns later) the unit steps right back in and the spawn
            # cycle continues without a dead turn.
            vacating_tris = [
                cs for cs in resettable_tris if src in cs
            ] + [cs for cs in to_spawn if src in cs]
            park_bonus = set()
            for cs in vacating_tris[:2]:
                for other in cs:
                    if other != src:
                        park_bonus |= adj.get(other, set())
            dst = min(
                neighs,
                key=lambda n: (
                    n in forbidden_end,
                    n not in home_side if stay_home else False,
                    corner_deg.get(n, 0) == 0,
                    n in must_vacate,
                    0 if n in park_bonus else 1,
                    1 if (n in attack_danger and locked_end.get(n, 0) >= 2) else 0,
                    opp.get(n, 0) > locked_end.get(n, 0) + 1,
                    -cand_home_deg[n],
                    -corner_deg.get(n, 0),
                    locked_end.get(n, 0),
                ),
            )
            locked_end[dst] = locked_end.get(dst, 0) + 1
            cmds.append(f"MOVE {src} {dst} 1")
            if excess > 0:
                my[src] = my.get(src, 0) - 1
                excess -= 1

    ui = f"v={army} t={len(owned)}"
    # Persist owner state for next turn's punish detection
    for t in tris:
        LAST_OWNER[t[:3]] = t[3]
    print(("MSG " + ui + ";" + ";".join(cmds)) if cmds else ("MSG " + ui), flush=True)
