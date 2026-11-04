import sys
from collections import deque

houses = {}
adj = {}

# Persistent state across turns (the bot process lives for the whole game)
MISSIONS = []  # list of (c1, c2, c3) corner tuples we are trying to capture
MISSION_AGE = {}


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

    # Hub connectivity per triangle
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

    # ------------------------------------------------------------------
    # 1. ATTACK: wipes ALL opponent units on an adjacent house. This is the
    # only counter to enemy stack snowball (Arnaud piles 5-10 units/house).
    # Attack replaces this triangle's spawn for the turn.
    # ------------------------------------------------------------------
    for t in sorted(
        usable,
        key=lambda tr: max((opp.get(n, 0) for c in tr[:3] for n in adj.get(c, ())), default=0),
        reverse=True,
    ):
        if t[:3] in used_tris:
            continue
        corners = t[:3]
        best_n = None
        best_kill = 0
        for c in corners:
            for n in adj.get(c, ()):
                k = opp.get(n, 0)
                if k > best_kill:
                    best_kill = k
                    best_n = n
        # Attack when profitable: >=3 units anytime, >=2 when we have army to spare.
        if (
            best_n is not None
            and opp.get(best_n, 0) > 0
            and (best_kill >= 3 or (best_kill >= 2 and army >= 12))
        ):
            cmds.append(f"ATTACK {corners[0]} {corners[1]} {corners[2]} {best_n}")
            used_tris.add(corners)
            opp[best_n] = 0
            for c in corners:
                my[c] = max(0, my[c] - 1)

    # ------------------------------------------------------------------
    # 2. MASS SPAWN (Arnaud style): spawn is FREE (+1 unit forever). The cost
    # is only that the triangle goes neutral for ~2 turns. Unit compounding
    # beats the temporary score dip — every owned triangle spawns every turn
    # it is staffed.
    # ------------------------------------------------------------------
    max_army = max(40, opp_army + 14)
    to_spawn = []
    n_owned = len(owned)
    for t in usable:
        corners = t[:3]
        if corners in used_tris:
            continue
        # Don't neutralize our LAST scoring triangle once the army is established:
        # keep it scoring while other triangles drive growth.
        if n_owned - len(to_spawn) <= 1 and army >= 14:
            continue
        if army >= max_army:
            break
        used_tris.add(corners)
        to_spawn.append(corners)

    # Spawn corner choice: prefer a corner that unlocks the most capturable
    # triangles (the spawned unit ends the turn there and counts toward them).
    avail = dict(my)
    locked_end = {h: 0 for h in houses}
    cands_all = [t for t in tris if t[3] != 0 and t[4]]

    def spawn_score(c):
        return (
            sum(1 for tr in cands_all if c in tr[:3] and opp.get(c, 0) == 0),
            corner_deg[c],
            -opp.get(c, 0),
        )

    spawn_houses = {h: 0 for h in houses}
    for corners in to_spawn:
        best_c = max(corners, key=spawn_score)
        others = [c for c in corners if c != best_c]
        cmds.append(f"SPAWN {best_c} {others[0]} {others[1]}")
        locked_end[best_c] += 1
        spawn_houses[best_c] += 1
        avail[best_c] = avail.get(best_c, 0) + 0  # spawned unit cannot move this turn

    # ------------------------------------------------------------------
    # 3. Units available for orders = current units minus the spawned ones
    # (spawned units appear AFTER moves and cannot act this turn).
    # ------------------------------------------------------------------
    # NOTE: `my` includes units present at start; the spawned units are added by
    # the referee after moves, so they are NOT in `avail` — correct.

    # Surround/expiry risk heuristic: dead-ends are traps, houses fully surrounded by
    # opponent units get swept (surround kill) or ATTACKed.
    def risky(n):
        neighs = list(adj.get(n, ()))
        if not neighs:
            return 3
        opp_nb = sum(1 for m in neighs if opp.get(m, 0) > 0)
        if opp_nb == len(neighs):
            return 3  # surrounded: unit dies
        if opp_nb >= len(neighs) - 1 and opp_nb > 0:
            return 2  # one step from being surrounded
        if opp_nb > 0:
            return 1
        return 0

    opp_tris = [t[:3] for t in tris if t[3] == 1 and all(opp.get(c, 0) > 0 for c in t[:3])]
    attack_danger = set()
    for ot in opp_tris:
        for c in ot:
            attack_danger.update(adj.get(c, ()))

    opp_reach1 = {
        h: opp.get(h, 0) + sum(opp.get(n, 0) for n in adj.get(h, ()) if opp.get(n, 0) > 0)
        for h in houses
    }

    # ------------------------------------------------------------------
    # 4. ENGINE REFILL first: owned triangles with an empty corner cannot
    # spawn — refill them before anything else so the spawn engine never dies.
    # ------------------------------------------------------------------
    engine_tris = [t[:3] for t in owned if t[:3] not in used_tris]
    engine_tris.sort(
        key=lambda cs: (
            sum(1 for c in cs if my.get(c, 0) == 0),
            -tri_hub[cs][0],
            -tri_hub[cs][1],
        )
    )
    for cs in engine_tris:
        for c in cs:
            while my.get(c, 0) == 0:
                srcs = [u for u in houses if avail.get(u, 0) > 0 and dist(u, c) <= 3 and u != c]
                if not srcs:
                    break
                srcs.sort(key=lambda u: (dist(u, c), risky(u), -avail[u]))
                u = srcs[0]
                avail[u] -= 1
                cmds.append(f"MOVE {u} {c} 1")
                if dist(u, c) <= 1:
                    # unit arrives this turn; count it so we don't double-book the corner
                    my[c] = my.get(c, 0) + 1
                break  # one unit per empty corner per turn

    # ------------------------------------------------------------------
    # 5. MISSIONS: persistent capture targets. Without sticky targets units
    # oscillate between triangles forever (each turn a different "best"
    # triangle) and never complete a capture. Missions persist until the
    # triangle is captured (owner==0) or hopeless for too many turns.
    # ------------------------------------------------------------------
    cands_all_map = {t[:3]: t for t in tris}
    me_cap_now = {t[:3]: t[4] for t in tris}
    owner_now = {t[:3]: t[3] for t in tris}

    # RESETTABLE triangles: neutral (or just spawned-on) with me_cap=False.
    # Our units standing on their corners BLOCK the me_cap reset, and no unit may
    # ENTER their corners this turn — first everyone must vacate, then next turn
    # me_cap flips True and the mission can complete.
    must_vacate = set()
    for t in tris:
        if t[3] != 0 and not t[4]:
            must_vacate.update(t[:3])
    for cs in to_spawn:
        must_vacate.update(cs)
    forbidden = set(must_vacate)

    # Drop finished / hopeless missions
    alive = []
    for cs in MISSIONS:
        if owner_now.get(cs, -1) == 0:
            continue  # captured — mission complete
        if me_cap_now.get(cs, False) is False and owner_now.get(cs, -1) != 0:
            # me_cap False: our units block the reset — still worth keeping if
            # we are vacating; keep the mission but it can only complete after vacate.
            pass
        age = MISSION_AGE.get(cs, 0) + 1
        if age > 12:
            continue  # hopeless — drop
        MISSION_AGE[cs] = age
        alive.append(cs)
    MISSIONS = alive

    # Add new missions for the best un-missioned capturable triangles.
    # Each mission needs ~3 units (1 per corner) — never more missions than the
    # army can staff, otherwise every mission starves and none completes.
    max_missions = max(1, min(8, army // 3))
    if len(MISSIONS) < max_missions:
        pool = [
            t[:3]
            for t in tris
            if t[3] != 0 and t[4] and t[:3] not in MISSIONS
        ]
        pool.sort(key=lambda cs: (min(dist(u, c) for u in houses for c in cs if True) if False else 0,))
        # rank by distance from our units, then hub
        unit_houses = [h for h, cnt in my.items() if cnt > 0]

        def mission_rank(cs):
            dmin = min((dist(u, c) for u in unit_houses for c in cs), default=99)
            return (dmin, -tri_hub[cs][0], -tri_hub[cs][1])

        pool.sort(key=mission_rank)
        for cs in pool:
            if len(MISSIONS) >= max_missions:
                break
            MISSIONS.append(cs)
            MISSION_AGE[cs] = 0

    # Assign units to mission corners (deficit = opponent + 1 - ours).
    # Lock only as many units per won corner as needed (opp+1) — excess units
    # on a crowded corner are FREE to move to the other corners of the mission.
    need = {}
    for cs in MISSIONS:
        for c in cs:
            if c in forbidden:
                continue  # resettable triangle: vacate first, capture next turn
            need[c] = max(need.get(c, 0), opp.get(c, 0) + 1)
    free = dict(avail)
    for c, nd in need.items():
        excess = my.get(c, 0) - nd
        if excess > 0:
            free[c] = free.get(c, 0) - excess
        else:
            # all units standing here are counted toward this corner
            free[c] = free.get(c, 0) - my.get(c, 0)
    free = {k: max(0, v) for k, v in free.items()}
    mission_moves = []
    for c in sorted(need, key=lambda x: (min((dist(u, x) for u in houses if free.get(u, 0) > 0), default=99), x)):
        deficit = need[c] - my.get(c, 0)
        while deficit > 0:
            srcs = [u for u in houses if free.get(u, 0) > 0 and u != c]
            if not srcs:
                break
            srcs.sort(key=lambda u: (dist(u, c), risky(u)))
            u = srcs[0]
            take = min(free[u], deficit)
            free[u] -= take
            deficit -= take
            if u != c:
                mission_moves.append((u, c, take))
            if dist(u, c) <= 1:
                my[c] = my.get(c, 0) + take
    for u, c, take in mission_moves:
        cmds.append(f"MOVE {u} {c} {take}")
    avail = {k: max(0, v) for k, v in free.items()}

    # ------------------------------------------------------------------
    # 6. VACATE: units still sitting on forbidden corners must step off.
    # ------------------------------------------------------------------
    moved_from = {u for u, c, _ in mission_moves}
    for src in sorted(avail):
        cnt = avail.get(src, 0)
        if cnt <= 0 or src not in must_vacate or src in moved_from:
            continue
        neighs = sorted(
            adj.get(src, ()),
            key=lambda n: (
                n in must_vacate,
                risky(n),
                opp.get(n, 0) > 0,
                -(sum(1 for cs in MISSIONS if n in cs and opp.get(n, 0) == 0)),
                corner_deg[n],
            ),
        )
        for i in range(cnt):
            dst = neighs[min(i, len(neighs) - 1)]
            cmds.append(f"MOVE {src} {dst} 1")
        avail[src] = 0

    # ------------------------------------------------------------------
    # 7. March: leftover units head to the nearest capturable corner.
    # Safety net against stalls: if nothing was ordered this turn, march all
    # free units toward the nearest triangle corner regardless of me_cap.
    # ------------------------------------------------------------------
    targets = sorted({c for t in tris if t[4] for c in t[:3]}) or sorted({c for t in tris for c in t[:3]})
    moved_from = moved_from if False else {u for u, c, _ in mission_moves}
    any_order = any(not c.startswith("MSG") for c in cmds)
    for src in sorted(avail):
        cnt = avail.get(src, 0)
        if cnt <= 0 or not targets:
            continue
        if any_order and src in must_vacate:
            continue
        dst = min(targets, key=lambda c: (dist(src, c), opp.get(c, 0), -corner_deg[c]))
        if src != dst and dist(src, dst) < 999:
            cmds.append(f"MOVE {src} {dst} {cnt}")
            avail[src] = 0

    ui = f"v={army} t={len(owned)}"
    print(("MSG " + ui + ";" + ";".join(cmds)) if cmds else ("MSG " + ui), flush=True)
