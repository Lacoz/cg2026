import gc
import random
import sys
import time
from collections import deque

try:
    import numpy as np
    from scipy.optimize import linear_sum_assignment
except ImportError:
    linear_sum_assignment = None

# Tunable weights (unit value = WU).
P = {
    "WU": 10.0,  # value of one of our units
    "WK": 9.0,  # value of killing one enemy unit by surround
    "V_CAP": 14.0,  # capture a neutral triangle
    "V_STEAL": 24.0,  # capture an enemy triangle
    "V_LOSE": 20.0,  # enemy captures one of ours
    "V_OPPCAP": 7.0,  # enemy captures a neutral triangle
    "V_RESET": 6.0,  # all corners of a used triangle empty -> capturable again
    "V_RPART": 0.6,  # per empty corner of a used triangle
    "V_PART": 0.2,  # per owned corner of a capturable triangle
    "EXP": 0.0,  # per unit in a >=3 stack inside enemy ATTACK reach
    "EXP2": 0.0,  # per unit in a 2-stack inside enemy ATTACK reach
    "DANGER_CAP": 0.0,  # danger weight of triangles the enemy can capture this turn
    "SURR": 0.0,  # weight (in units) of the expected loss to being surrounded next turn
    "SPR": 0.4,  # per surplus unit on a house
    "FW": 1.0,  # pull per step toward the assigned corner
    "FW_IDLE": 0.3,  # pull per step for unassigned units
    "ATK_MIN": 4,  # min kills for an ATTACK
    "THREAT": 5.0,  # our triangle with all corners enemy-reachable and unguarded
    "MAXD": 9,  # max completion distance considered by the assignment
    "CONTEST_D": 0.0,  # assignment: extra turns charged per contested/exposed corner
    "P_CONT": 0.7,  # capture value factor per corner the enemy can still out-reinforce
    "OADJ_MAX": 1,  # cap on enemy units counted as able to reinforce a corner
    "RISK": 1.0,  # weight (in units) of the expected loss to a predicted enemy ATTACK
    "RISK_CAPW": 0.3,  # weight of triangles the enemy may capture this turn in the threat map
    "RISK_NET": 2.0,
    "RISK_CAPW_ATT": 1.0,  # RISK_CAPW once the enemy has made ATT_SEEN attacks
    "ATT_SEEN": 1,
    "ATK_S": 3.0,  # prior strength (pseudo-observations) of the attack-probability table
    "HOME_W": 0.6,  # extra weight of triangles closer to our start than to the enemy's
    "AWAY_W": 0.0,  # weight reduction of triangles closer to the enemy's start  # an ATTACK costs the enemy 3 units + the triangle: only losses above this count
    "SP_HOLD": 1,  # hold (do not spawn) triangles with enemy units on or next to a corner
    "SP_R": 1,  # 0: only enemy units on the corners count, 1: also on their neighbors
    "SP_HUBN": 3,  # ... only on corners shared by at least this many of our triangles
    "SP_ARMY": 1.0,  # ... only while our army is at least this fraction of the enemy's
    "SP_CASH": 1,  # still spawn a held triangle the enemy can take this turn anyway
    "FREE_SPAWN_TURNS": 40,
    "CAP_MIN": 20,
    "CAP_MUL": 1.25,
    "CAP_ADD": 8,
    "CAP_MAX": 80,
    "BUDGET": 0.030,
    "ILS": 1,  # spend leftover budget on random kicks + re-descent
    "KICK": 2,  # max tokens moved by one kick
}


def ints():
    return [int(x) for x in input().split()]


N = int(input())
for _ in range(N):
    input()

nb = None
dist = None
order_from = None
tri_c = None
tri_nb = None
turn = 0

# ---------------- opponent model (learned from state diffs, actions are not in the input) ----------------
# P(opponent ATTACKs | largest stack of ours in reach of his usable triangles), prior from ~80 logged games
ATK_PRIOR = [0.0, 0.01, 0.15, 0.32, 0.40, 0.56]
atk_n = [0] * 6
atk_a = [0] * 6
# P(opponent owns triangle at end of turn | corners he holds now, corners he can win now)
CAP_TAB = {(0, 2): 0.018, (0, 3): 0.07, (1, 2): 0.007, (1, 3): 0.14, (2, 2): 0.068, (2, 3): 0.33}
cap_pred = 0.0
cap_act = 0
own_n = 0
own_kept = 0
opp_attacks = []  # stack sizes the opponent killed
sur_lost = 0  # our units lost without an attack (surrounded)
# P(our units on a house get surrounded | enemy can reach every neighbour, enemy units still
# needed to flip them all), from ~80 logged games; scaled by sur_act / sur_pred per opponent
SUR_TAB = [0.5, 0.12, 0.05, 0.015, 0.005]
sur_pred = 0.0
sur_act = 0
prev = None  # (my, op, owner, opcap, our moves, our spawns, our attacks)


def cap_feat(i, mine, theirs):
    m = w = 0
    for c in tri_c[i]:
        if theirs[c] > mine[c]:
            m += 1
        if theirs[c] + sum(theirs[n] for n in nb[c]) > mine[c]:
            w += 1
    return CAP_TAB.get((m, w), 0.0)


def learn(my, op, owner):
    """Update the opponent model from what changed since our previous turn."""
    global cap_pred, cap_act, own_n, own_kept, sur_lost, sur_pred, sur_act
    pmy, pop, pown, popcap, pmoves, pspawns, patks = prev
    T_ = len(tri_c)
    exp = pmy[:]
    for a, b, c, tg in patks:
        for x in (a, b, c):
            exp[x] -= 1
    out = [0] * N
    for s, d, n in pmoves:
        exp[s] -= n
        exp[d] += n
        out[s] += n
    for s in pspawns:
        exp[s] += 1
    deficit = [exp[x] - my[x] for x in range(N)]
    usable = [i for i in range(T_) if pown[i] == 1 and all(pop[c] >= 1 for c in tri_c[i])]
    used = [i for i in usable if owner[i] == -1]
    reach = set()
    for i in usable:
        reach.update(tri_nb[i])
    kmax = max((pmy[h] for h in reach), default=0)
    hits = 0
    if used:
        tg_set = set()
        for i in used:
            tg_set.update(tri_nb[i])
        for h in sorted((h for h in tg_set if pmy[h] > 0), key=lambda h: -pmy[h]):
            if hits >= len(used):
                break
            pd = {h: pmy[h] - out[h]}
            for s, d, n in pmoves:
                if s == h:
                    pd[d] = pd.get(d, 0) + n
            if all(v <= deficit[x] for x, v in pd.items()):
                for x, v in pd.items():
                    deficit[x] -= v
                hits += 1
                opp_attacks.append(pmy[h])
    sur_lost += sum(d for d in deficit if d > 0)
    for h in range(N):
        if exp[h] <= 0:
            continue
        ns = nb[h]
        if not all(pop[n] + sum(pop[m] for m in nb[n]) > exp[n] for n in ns):
            continue
        need = sum(exp[n] - pop[n] + 1 for n in ns if pop[n] <= exp[n])
        sur_pred += SUR_TAB[need if need < 4 else 4]
        sur_act += deficit[h] > 0
    if kmax > 0:
        k = min(kmax, 5)
        atk_n[k] += 1
        atk_a[k] += 1 if hits else 0
    for i in range(T_):
        if pown[i] == 1:
            own_n += 1
            own_kept += owner[i] == 1
        elif popcap[i]:
            cap_pred += cap_feat(i, pmy, pop)
            cap_act += owner[i] == 1


def atk_prob():
    p = [0.0] * 6
    for k in range(1, 6):
        p[k] = max(p[k - 1], (atk_a[k] + ATK_PRIOR[k] * P["ATK_S"]) / (atk_n[k] + P["ATK_S"]))
    return p

# the turn loop creates no reference cycles; a collection would only cost time mid-turn
gc.disable()
while True:
    line = input()
    t_start = time.perf_counter()
    turn += 1
    my_score, op_score = [int(x) for x in line.split()]
    my = [0] * N
    op = [0] * N
    for _ in range(N):
        h, a, b = ints()
        my[h] = a
        op[h] = b
    edges = [ints() for _ in range(int(input()))]
    raw = [input().split() for _ in range(int(input()))]
    for _ in range(int(input())):
        input()

    if nb is None:
        nb = [[] for _ in range(N)]
        for a, b in edges:
            nb[a].append(b)
            nb[b].append(a)
        for l in nb:
            l.sort()
        dist = []
        for s in range(N):
            d = [99] * N
            d[s] = 0
            q = deque([s])
            while q:
                u = q.popleft()
                for v in nb[u]:
                    if d[v] == 99:
                        d[v] = d[u] + 1
                        q.append(v)
            dist.append(d)
        order_from = [sorted(range(N), key=lambda h, s=s: dist[s][h]) for s in range(N)]
        tri_c = [(int(r[0]), int(r[1]), int(r[2])) for r in raw]
        tris_of = [[] for _ in range(N)]
        for i, cs in enumerate(tri_c):
            for c in cs:
                tris_of[c].append(i)
        tri_nb = []
        for cs in tri_c:
            s = set(cs)
            for c in cs:
                s.update(nb[c])
            tri_nb.append(sorted(s))
        near2 = [[h for h in range(N) if dist[x][h] <= 2] for x in range(N)]
        # home side of each triangle: whose start is closer to all of its corners
        st_me = [h for h in range(N) if my[h] > 0]
        st_op = [h for h in range(N) if op[h] > 0]
        side = []
        for cs in tri_c:
            dm = max(min(dist[s][c] for s in st_me) for c in cs) if st_me else 99
            do = max(min(dist[s][c] for s in st_op) for c in cs) if st_op else 99
            side.append(1 if dm < do else -1 if do < dm else 0)
        tw = [1.0 + P["HOME_W"] if s == 1 else 1.0 - P["AWAY_W"] if s == -1 else 1.0 for s in side]

    T = len(tri_c)
    owner = [int(r[3]) for r in raw]
    mecap = [r[4] == "1" for r in raw]
    opcap = [r[5] == "1" for r in raw]
    army = sum(my)
    oarmy = sum(op)
    my0 = my[:]
    op0 = op[:]
    if prev is not None:
        learn(my, op, owner)
    pk = atk_prob()
    keep = (own_kept + 0.5 * 4) / (own_n + 4)
    act = min(3.0, max(0.3, (cap_act + 2.0) / (cap_pred + 2.0)))
    # threat[i]: P(opponent can ATTACK from triangle i next turn) = owns it after this turn with units on it
    risk = [0.0] * N
    # an enemy that already attacked tends to attack from fresh captures as well
    capw = P["RISK_CAPW_ATT"] if len(opp_attacks) >= P["ATT_SEEN"] else P["RISK_CAPW"]
    if P["RISK"] > 0:
        safe = [1.0] * N
        for i in range(T):
            cs = tri_c[i]
            if owner[i] == 1:
                th = keep * (0.9 if all(op[c] >= 1 for c in cs) else 0.3)
            elif opcap[i]:
                th = min(0.9, cap_feat(i, my, op) * act * capw)
            else:
                continue
            if th <= 0:
                continue
            for h in tri_nb[i]:
                safe[h] *= 1.0 - th
        risk = [1.0 - s for s in safe]
    cmds = []
    used = [False] * T

    # ---------------- ATTACK ----------------
    atk = []
    for i in range(T):
        if owner[i] != 0:
            continue
        a, b, c = tri_c[i]
        if my[a] < 1 or my[b] < 1 or my[c] < 1:
            continue
        for tg in tri_nb[i]:
            k = op[tg]
            if k >= 1:
                atk.append((k, i, tg))
    atk.sort(reverse=True)
    hit = set()
    for k, i, tg in atk:
        if used[i] or tg in hit:
            continue
        a, b, c = tri_c[i]
        if my[a] < 1 or my[b] < 1 or my[c] < 1:
            continue
        ok = k >= P["ATK_MIN"] + 1 or (k >= P["ATK_MIN"] and army >= oarmy)
        if not ok:
            continue
        used[i] = True
        hit.add(tg)
        op[tg] = 0
        my[a] -= 1
        my[b] -= 1
        my[c] -= 1
        cmds.append(f"ATTACK {a} {b} {c} {tg}")

    # ---------------- SPAWN ----------------
    spawn_tris = []
    if turn <= P["FREE_SPAWN_TURNS"]:
        cap = 10**6
    else:
        cap = max(P["CAP_MIN"], oarmy * P["CAP_MUL"] + P["CAP_ADD"])
    cap = min(cap, P["CAP_MAX"])
    # a spawned triangle stays closed to us until all its corners are empty, but stays open
    # to the enemy: next to enemy units we keep holding it, unless he can take it anyway
    near_op = [op[x] + (sum(op[n] for n in nb[x]) if P["SP_R"] >= 1 else 0) for x in range(N)]
    mine_at = [sum(1 for j in tris_of[x] if owner[j] == 0) for x in range(N)]
    for i in range(T):
        if owner[i] == 0 and not used[i] and army + len(spawn_tris) < cap:
            cs = tri_c[i]
            if (
                P["SP_HOLD"]
                and army >= oarmy * P["SP_ARMY"]
                and any(near_op[c] > 0 and mine_at[c] >= P["SP_HUBN"] for c in cs)
            ):
                lost = all(op[c] + sum(op[n] for n in nb[c]) > my[c] for c in cs)
                if not (P["SP_CASH"] and lost):
                    continue
            spawn_tris.append(i)
            used[i] = True

    # ---------------- threat maps ----------------
    # houses the enemy can ATTACK next turn: triangles it owns, or can capture this
    # turn (it attacks from fresh captures right away), with its units on the corners
    danger = [0.0] * N
    for i in range(T):
        cs = tri_c[i]
        if owner[i] == 1:
            if all(op[c] >= 1 for c in cs):
                w = 1.0
            elif all(op[c] >= 1 or any(op[n] >= 1 for n in nb[c]) for c in cs):
                w = 0.7
            else:
                continue
        elif (
            opcap[i]
            and (op[cs[0]] >= 1) + (op[cs[1]] >= 1) + (op[cs[2]] >= 1) >= 2
            and all(op[c] >= 1 or any(op[n] >= 1 for n in nb[c]) for c in cs)
        ):
            w = P["DANGER_CAP"]
        else:
            continue
        for h in tri_nb[i]:
            if danger[h] < w:
                danger[h] = w
    oreach = [op[h] + sum(op[n] for n in nb[h]) for h in range(N)]

    # ---------------- assignment: units -> corners of capturable triangles ----------------
    free = my[:]  # free units per house
    assigned_to = {}  # corner -> units assigned
    plan = []  # (src_house, corner, count, wait_adjacent)
    # capturable now, or waiting for its corners to empty (capturable in 2 turns)
    cand = [i for i in range(T) if owner[i] != 0 and not used[i]]
    MAXD = P["MAXD"]
    while cand and sum(free) > 0:
        best = None
        for i in cand:
            comp = 0 if mecap[i] else 2
            cost = 0
            ok = True
            for c in tri_c[i]:
                r = op[c] + 1 - assigned_to.get(c, 0)
                if r <= 0:
                    continue
                dc = 0
                for h in order_from[c]:
                    f = free[h]
                    if f <= 0:
                        continue
                    dh = dist[c][h]
                    take = f if f < r else r
                    r -= take
                    cost += dh * take
                    dc = dh
                    if r <= 0:
                        break
                if r > 0 or dc > MAXD:
                    ok = False
                    break
                if dc > comp:
                    comp = dc
            if not ok:
                continue
            contested = sum(1 for c in tri_c[i] if op[c] > 0 or danger[c] > 0)
            key = (comp + P["CONTEST_D"] * contested, 0 if owner[i] == 1 else 1, cost)
            if best is None or key < best[0]:
                best = (key, i)
        if best is None:
            break
        i = best[1]
        cand.remove(i)
        for c in tri_c[i]:
            r = op[c] + 1 - assigned_to.get(c, 0)
            if r <= 0:
                continue
            for h in order_from[c]:
                f = free[h]
                if f <= 0:
                    continue
                take = f if f < r else r
                free[h] -= take
                r -= take
                assigned_to[c] = assigned_to.get(c, 0) + take
                plan.append((h, c, take, not mecap[i]))
                if r <= 0:
                    break
    # keep the greedy choice of corners, but pick the units by min total distance
    if plan and linear_sum_assignment is not None:
        slots = []
        for h, c, n, w in plan:
            slots += [(c, w)] * n
        uh = [h for h in range(N) for _ in range(my[h])]
        ri, ci = linear_sum_assignment(np.array([[dist[h][c] for c, _ in slots] for h in uh]))
        free = my[:]
        agg = {}
        for r, k in zip(ri, ci):
            free[uh[r]] -= 1
            key = (uh[r],) + slots[k]
            agg[key] = agg.get(key, 0) + 1
        plan = [(h, c, n, w) for (h, c, w), n in agg.items()]

    # idle pull: nearest corner of any triangle we do not own
    tgt_idle = set()
    for i in range(T):
        if owner[i] != 0 and not used[i]:
            tgt_idle.update(tri_c[i])
    fd = [99] * N
    q = deque()
    for h in tgt_idle:
        fd[h] = 0
        q.append(h)
    while q:
        u = q.popleft()
        for v in nb[u]:
            if fd[v] == 99:
                fd[v] = fd[u] + 1
                q.append(v)

    WU, WK, EXP, SPR, EXP2 = P["WU"], P["WK"], P["EXP"], P["SPR"], P["EXP2"]
    V_CAP, V_STEAL, V_LOSE = P["V_CAP"], P["V_STEAL"], P["V_LOSE"]
    V_OPPCAP, V_RESET, V_RPART, V_PART = P["V_OPPCAP"], P["V_RESET"], P["V_RPART"], P["V_PART"]
    THREAT, FW, FWI, SURR = P["THREAT"], P["FW"], P["FW_IDLE"], P["SURR"]
    P_CONT = P["P_CONT"]
    RISK = P["RISK"] * WU
    RISK_NET = P["RISK_NET"]
    oadj = [min(sum(op[n] for n in nb[x]), P["OADJ_MAX"]) for x in range(N)]

    # ---------------- unit tokens ----------------
    cnt = [0] * N
    tok_origin = []
    tok_pos = []
    tok_opts = []
    tok_spawn = []
    tok_tgt = []
    tok_wait = []
    for h, c, n, w in plan:
        for _ in range(n):
            tok_origin.append(h)
            tok_pos.append(h)
            tok_opts.append([h] + nb[h])
            tok_spawn.append(-1)
            tok_tgt.append(c)
            tok_wait.append(w)
            cnt[h] += 1
    for h in range(N):
        for _ in range(free[h]):
            tok_origin.append(h)
            tok_pos.append(h)
            tok_opts.append([h] + nb[h])
            tok_spawn.append(-1)
            tok_tgt.append(-1)
            tok_wait.append(False)
            cnt[h] += 1
    for i in spawn_tris:
        cs = tri_c[i]
        best = min(cs, key=lambda c: (cnt[c], fd[c]))
        tok_origin.append(-1)
        tok_pos.append(best)
        tok_opts.append(list(cs))
        tok_spawn.append(i)
        tok_tgt.append(-2)
        tok_wait.append(False)
        cnt[best] += 1

    def tok_val(k, p):
        t = tok_tgt[k]
        if t >= 0:
            d = dist[p][t]
            if tok_wait[k]:
                d = d - 1 if d > 0 else 1
            return -FW * d
        if t == -1:
            d = fd[p]
            return -FWI * d if d < 99 else 0.0
        return 0.0

    use_dng = EXP != 0 or EXP2 != 0
    use_surr = SURR != 0
    SURR_W = SURR * WU * min(4.0, max(0.3, (sur_act + 1.0) / (sur_pred + 1.0)))

    # nmine[x] / nopp[x]: neighbours of x where we / the enemy have strictly more units
    deg = [len(nb[x]) for x in range(N)]
    nmine = [0] * N
    nopp = [0] * N
    for h in range(N):
        if cnt[h] != op[h]:
            arr = nmine if cnt[h] > op[h] else nopp
            for x in nb[h]:
                arr[x] += 1

    dirty = []  # houses whose nmine / nopp changed

    def bump(h, dv):
        d0 = cnt[h] - op[h]
        cnt[h] += dv
        d1 = d0 + dv
        if (d0 > 0) == (d1 > 0) and (d0 < 0) == (d1 < 0):
            return
        ns = nb[h]
        dirty.extend(ns)
        if d0 > 0:
            for x in ns:
                nmine[x] -= 1
        elif d0 < 0:
            for x in ns:
                nopp[x] -= 1
        if d1 > 0:
            for x in ns:
                nmine[x] += 1
        elif d1 < 0:
            for x in ns:
                nopp[x] += 1

    def house_eval(x):
        """(owner of house x, value of its units) for the current cnt."""
        c = cnt[x]
        o = op[x]
        allmine = nmine[x] == deg[x]
        allop = nopp[x] == deg[x]
        ow = 0 if allmine else 1 if allop else 0 if c > o else 1 if o > c else -1
        v = 0.0
        if c > 0:
            if allop:
                v -= WU * c
            else:
                if use_dng and c >= 2 and danger[x] > 0:
                    v -= danger[x] * (EXP * c if c >= 3 else EXP2 * c)
                if use_surr:
                    ns = nb[x]
                    if all(oreach[n] > cnt[n] for n in ns):
                        need = 0
                        for n in ns:
                            if op[n] <= cnt[n]:
                                need += cnt[n] - op[n] + 1
                        v -= SURR_W * c * SUR_TAB[need if need < 4 else 4]
                if c > RISK_NET and risk[x] > 0:
                    v -= RISK * (c - RISK_NET) * pk[c if c < 5 else 5] * risk[x]
                if c > o + 1:
                    s = c - o - 1
                    v -= SPR * s * s
        if o > 0 and allmine:
            v += WK * o
        return ow, v

    tri_st = []
    for i in range(T):
        so, sm = (-1, False) if used[i] else (owner[i], mecap[i])
        tri_st.append(tri_c[i] + (so, sm, used[i], so == -1 and opcap[i], tw[i]))

    def tri_term(i, own):
        a, b, c, so, sm, usd, oppc, w = tri_st[i]
        oa = own[a]
        ob = own[b]
        oc = own[c]
        if so == 0:
            if oa == 1 and ob == 1 and oc == 1:
                return -V_LOSE * w
            if oa != 0 and ob != 0 and oc != 0 and oreach[a] > cnt[a] and oreach[b] > cnt[b] and oreach[c] > cnt[c]:
                return -THREAT * w
            return 0.0 * w
        v = 0.0
        if sm:
            mine = (oa == 0) + (ob == 0) + (oc == 0)
            if mine == 3:
                v = V_STEAL if so == 1 else V_CAP
                for x in (a, b, c):
                    if oadj[x] > 0 and cnt[x] - op[x] <= oadj[x]:
                        v *= P_CONT
                return v * w
            v += V_PART * mine
        elif not usd:
            e = (cnt[a] == 0) + (cnt[b] == 0) + (cnt[c] == 0)
            v += V_RESET if e == 3 else V_RPART * e
        if oppc and oa == 1 and ob == 1 and oc == 1:
            v -= V_OPPCAP
        return v * w

    own = [0] * N
    hv = [0.0] * N
    for x in range(N):
        own[x], hv[x] = house_eval(x)
    tv = [tri_term(i, own) for i in range(T)]

    def eval_moves(mv):
        """mv: list of (token, new_pos). Returns (delta, state) without committing.
        Only houses whose own count or neighbour balance changed, and triangles with
        such a corner, are re-evaluated."""
        hs = []
        d = 0.0
        for k, qq in mv:
            p = tok_pos[k]
            hs.append(p)
            hs.append(qq)
            d += tok_val(k, qq) - tok_val(k, p)
        dirty.clear()
        for k, qq in mv:
            bump(tok_pos[k], -1)
            bump(qq, 1)
        H = set(hs)
        H.update(dirty)
        if use_surr:
            for x in hs:
                H.update(nb[x])
        no = []
        nh = []
        flip = []
        for x in H:
            o_, v = house_eval(x)
            no.append(o_)
            nh.append(v)
            d += v - hv[x]
            if o_ != own[x]:
                flip.append((x, own[x]))
                own[x] = o_
        TS = set()
        for x in hs:
            TS.update(tris_of[x])
        for x, _ in flip:
            TS.update(tris_of[x])
        nt = []
        for i in TS:
            v = tri_term(i, own)
            nt.append(v)
            d += v - tv[i]
        for x, o_ in flip:
            own[x] = o_
        for k, qq in mv:
            bump(tok_pos[k], 1)
            bump(qq, -1)
        return d, (H, TS, no, nh, nt)

    def commit(mv, state):
        H, TS, no, nh, nt = state
        for k, qq in mv:
            moved.append(tok_pos[k])
            moved.append(qq)
            bump(tok_pos[k], -1)
            bump(qq, 1)
            tok_pos[k] = qq
        for j, x in enumerate(H):
            own[x] = no[j]
            hv[x] = nh[j]
        for j, i in enumerate(TS):
            tv[i] = nt[j]

    budget = P["BUDGET"]
    ntok = len(tok_pos)
    moved = []  # houses touched by commits

    # initial greedy: every assigned unit takes its first step if it does not hurt
    for k in range(ntok):
        t = tok_tgt[k]
        if t < 0 or time.perf_counter() - t_start > budget:
            continue
        p = tok_pos[k]
        if p == t or (tok_wait[k] and dist[p][t] <= 1):
            continue
        step = min((n for n in nb[p]), key=lambda n: (dist[n][t], n))
        d, st = eval_moves([(k, step)])
        if d > -2.0:
            commit([(k, step)], st)

    def single_pass(toks=None):
        improved = False
        seen = set()
        for k in range(ntok) if toks is None else toks:
            if time.perf_counter() - t_start > budget:
                return improved
            p = tok_pos[k]
            key = (tok_origin[k], p, tok_spawn[k], tok_tgt[k])
            if key in seen:
                continue
            best_d = 1e-6
            best = None
            for qq in tok_opts[k]:
                if qq == p:
                    continue
                d, st = eval_moves([(k, qq)])
                if d > best_d:
                    best_d = d
                    best = ([(k, qq)], st)
            if best is not None:
                commit(*best)
                improved = True
                seen = set()
            else:
                seen.add(key)
        return improved

    def composite_pass(R=None):
        """R: only triangles / vacate sets touching these houses."""
        improved = False
        for i in range(T):
            if time.perf_counter() - t_start > budget:
                return improved
            if used[i] or owner[i] == 0 or not mecap[i]:
                continue
            cs = tri_c[i]
            if R is not None and cs[0] not in R and cs[1] not in R and cs[2] not in R:
                continue
            missing = [c for c in cs if own[c] != 0]
            if not missing:
                continue
            mv = []
            taken = set()
            ok = True
            for c in missing:
                r = op[c] + 1 - cnt[c]
                if r <= 0:
                    r = 1
                cands_k = [
                    k
                    for k in range(ntok)
                    if k not in taken and tok_pos[k] != c and tok_pos[k] not in cs and c in tok_opts[k]
                ]
                cands_k.sort(key=lambda k: (-(cnt[tok_pos[k]] - op[tok_pos[k]]), tok_tgt[k] >= 0))
                if len(cands_k) < r:
                    ok = False
                    break
                for k in cands_k[:r]:
                    taken.add(k)
                    mv.append((k, c))
            if not ok or not mv:
                continue
            d, st = eval_moves(mv)
            if d > 1e-6:
                commit(mv, st)
                improved = True
        # vacate: empty all corners of a waiting triangle (or a whole connected group
        # of waiting triangles sharing corners) at once so they become capturable
        for cs in vacate_sets:
            if time.perf_counter() - t_start > budget:
                return improved
            if R is not None and cs.isdisjoint(R):
                continue
            if sum(cnt[c] for c in cs) == 0:
                continue
            mv = []
            ok = True
            extra = {}
            for k in range(ntok):
                p = tok_pos[k]
                if p not in cs:
                    continue
                outs = [x for x in tok_opts[k] if x not in cs]
                if not outs:
                    ok = False
                    break
                dst = max(outs, key=lambda x: (-(cnt[x] + extra.get(x, 0) > op[x]), tok_val(k, x), -cnt[x] - extra.get(x, 0)))
                extra[dst] = extra.get(dst, 0) + 1
                mv.append((k, dst))
            if not ok or not mv or len(mv) > 12:
                continue
            d, st = eval_moves(mv)
            if d > 1e-6:
                commit(mv, st)
                improved = True
        return improved

    waiting = [i for i in range(T) if not used[i] and owner[i] != 0 and not mecap[i]]
    vacate_sets = [set(tri_c[i]) for i in waiting]
    # connected groups of waiting triangles (shared corners)
    seen_w = set()
    for i in waiting:
        if i in seen_w:
            continue
        comp = {i}
        stack = [i]
        seen_w.add(i)
        while stack:
            j = stack.pop()
            for c in tri_c[j]:
                for k2 in tris_of[c]:
                    if k2 not in seen_w and k2 in waiting:
                        seen_w.add(k2)
                        comp.add(k2)
                        stack.append(k2)
        if len(comp) > 1:
            g = set()
            for j in comp:
                g.update(tri_c[j])
            vacate_sets.append(g)
    vacate_sets.sort(key=len, reverse=True)

    passes = 0
    while passes < 8 and time.perf_counter() - t_start < budget:
        passes += 1
        a = single_pass()
        b = composite_pass()
        if not a and not b:
            break

    # rest of the budget: kick 1..KICK random tokens, descend again, keep only if the total improved
    kicks = kept = 0
    if P["ILS"] and ntok and passes < 8:
        rng = random.Random(turn)

        def total():
            return sum(hv) + sum(tv) + sum(tok_val(k, tok_pos[k]) for k in range(ntok))

        best_v = total()
        while time.perf_counter() - t_start < budget:
            kicks += 1
            snap = (tok_pos[:], cnt[:], own[:], hv[:], tv[:], nmine[:], nopp[:])
            moved.clear()
            for _ in range(rng.randint(1, P["KICK"])):
                k = rng.randrange(ntok)
                opts = [x for x in tok_opts[k] if x != tok_pos[k]]
                if opts:
                    mv = [(k, rng.choice(opts))]
                    commit(mv, eval_moves(mv)[1])
            # re-descend only around what moved
            R = set()
            for _ in range(8):
                for h in moved:
                    R.update(near2[h])
                moved.clear()
                a = single_pass([k for k in range(ntok) if tok_pos[k] in R])
                b = composite_pass(R)
                if not a and not b:
                    break
            v = total()
            if v > best_v + 1e-6:
                best_v = v
                kept += 1
            else:
                tok_pos[:], cnt[:], own[:], hv[:], tv[:], nmine[:], nopp[:] = snap

    # ---------------- output ----------------
    # two spawns on one house would both die to a single ATTACK
    spawn_at = set()
    for k in range(ntok):
        if tok_spawn[k] < 0:
            continue
        p = tok_pos[k]
        if p in spawn_at:
            alts = [x for x in tok_opts[k] if x not in spawn_at]
            if alts:
                p = min(alts, key=lambda x: (cnt[x], fd[x]))
                cnt[tok_pos[k]] -= 1
                cnt[p] += 1
                tok_pos[k] = p
        spawn_at.add(p)
    moves = {}
    for k in range(ntok):
        if tok_spawn[k] >= 0:
            i = tok_spawn[k]
            sp = tok_pos[k]
            others = [c for c in tri_c[i] if c != sp]
            cmds.append(f"SPAWN {sp} {others[0]} {others[1]}")
        elif tok_pos[k] != tok_origin[k]:
            key = (tok_origin[k], tok_pos[k])
            moves[key] = moves.get(key, 0) + 1
    for (a, b), n in sorted(moves.items()):
        cmds.append(f"MOVE {a} {b} {n}")
    our_atk = []
    our_sp = []
    for c in cmds:
        f = c.split()
        if f[0] == "ATTACK":
            our_atk.append(tuple(int(x) for x in f[1:5]))
        elif f[0] == "SPAWN":
            our_sp.append(int(f[1]))
    prev = (my0, op0, owner, opcap, [(a, b, n) for (a, b), n in moves.items()], our_sp, our_atk)
    ms = int((time.perf_counter() - t_start) * 1000)
    def f2(v):
        return f"{v:.2f}".rstrip("0").rstrip(".").lstrip("0") or "0"

    # the viewer shows only ~20 characters
    cmds.insert(0, f"MSG a{f2(pk[2])}/{f2(pk[3])}/{f2(pk[4])} k{f2(keep)} c{f2(act)} x{len(opp_attacks)} s{sur_lost} {ms}ms p{passes}")
    print(";".join(cmds), flush=True)
