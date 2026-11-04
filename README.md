# Fall Challenge 2026 — TryAngle Catch bot (Wood 1)

Stav k **2026-11-04 09:47**. Cieľ tohto README: aby si vedel pokračovať bez
předlžovania kontextu — čo funguje, čo nie a prečo.

---

## Aktuálny stav v skratke

| Súbor | Čo je |
|---|---|
| `bot.py` | **Aktuálny bot = „staggered engines" verzia** (obnovená z transkriptu, validovaná). Toto submituj. |
| `bot_missions_backup.py` | Experiment „missions" (perzistentné ciele + mass-spawn). Lokálne OK, **online 0 % win rate** — príčina nezistená. NEsubmitovať. |
| `bot_recovered.py` | Medzistav recovery (pred replayom patchov), môžeš zmazať. |
| `statement.md` | Pravidlá Wood 1 (sedia s webom). |
| `BOT_SPEC.md` | Detailná špecifikácia + historické analýzy (čiastočne staré). |
| `scoring.yaml` | Opponent `default` ×5, brány: win_rate ≥ 0.2, median ≥ 3, crash ≤ 0.5. Boss sekcia zapoznámkovaná (NO_BOSS v Wood). |
| `tmp_seed_*.txt` | Full game_options seedov na lokálny replay (466 = Arnaud.Net, 328 = M_C, 436/−7474/−8423/194). |

**Posledná validácia `bot.py` (2026-11-04, po czuk opravách)**: unit testy 10 OK (2 skip = známy bug) ·
online `./cg test --games 2` → **2/2 WIN** (134:−1, **3459:11**), všetky brány prešli ·
opravy: spawn-corner uniqueness, `en_route` accounting, `trap_risk`, pass-through parking block.

---

## Ako funguje aktuálny `bot.py` (staggered engines)

Fázy v ťahu, v tomto poradí:

1. **ATTACK** — z own trojuholníka s jednotkami na všetkých rohoch zmaže ALL súperove jednotky
   na susednom dome. Podmienky: `kill ≥ 4`, alebo `kill ≥ 3 a army ≥ 18`, alebo `kill ≥ 2 a army ≥ 28`.
   Útok **zneutrálí** trojuholník (spotrebuje ho na tento ťah — `used_tris`).
2. **Výber spawn skupiny (stagger)**: usable own trojuholníky (1 jednotka na každom rohu) sa zoria
   podľa hub-konektivity. Ak ich je ≥ 4: horná polovica = **hold_group** (drží skóre, spawn-ready),
   dolná polovica = **spawnuje tento ťah**. Ak 2–3: 1 drží, zvyšok spawnuje. Army cap `max(36, opp+12)`.
3. **Engine refill** (pred priraďovaním!): vlastnený trojuholník s **prázdnym rohom nemôže spawnovať** —
   voľné jednotky sa pošlú doplniť rohy. Pri ≤ 2 engine unlimited dosah (999), inak 3 (hold) / 2.
4. **Capture assignment**: `imm_cands` (capture v 1 kroku, `max_d ≤ 1`) — najlepšia podmnožina ≤ 3
   trojuholníkov nájdená kombinatoricky (≤ 14 kandidátov, cap 7). Potom greedy multi-turn priradenie
   (`max_allowed_d = 2` počas `stay_home`), poradie rohov „najviac obmedzený najprv".
5. **Staging** — prebytočné jednotky na rohy najlepšieho lokálneho `cands` trojuholníka (1/roh).
6. **Vacate + forbidden_end**: rohy trojuholníkov s `me_cap=False` (a čerstvo spawnutých) musia byť
   **úplne prázdne**, aby sa `me_cap` next turn obnovil; iné jednotky na ne nesmú vstúpiť.
7. **Teritoriálna disciplína**: `home_side` (polovica mapy podľa štartu), `attack_danger`
   (dom susediaci s ready súperovým tri — nekopiť tam), `risky()` — slepé uličky a 1-krok-okolo-surround.

## Kľúčové mechaniky hry (naučené tvrdo)

- **Spawn cyklus = 3 ťahy na trojuholník**: own (owner=0) → `SPAWN` (owner→None, nova jednotka na rohu)
  → **všetky** jednotky musia z rohov odísť (aj spawnutá!) → `me_cap=True` (sticky pre neutral)
  → jednotky vstúpia na rohy → capture na konci ťahu → zasa own. **Preto stagger, nie mass-spawn na všetko.**
- **`me_cap` (meCanCapture)**: pre neutral tri = „všetky naše jednotky mimo rohov" (sticky `|=`).
  Spawn/ATTACK **nevyžaduje** `me_cap` — vyžaduje `owner==0` + jednotky na rohoch.
- **`MOVE src dst amount`** = 1 krok BFS smerom k `dst` (nie teleport). Viac `MOVE 1` z domu = OK.
- **ATTACK ničí neobmedzene** jednotky na cieli (aj stack 10) — jediná obrana proti snowball stackom.
- **Surround**: jednotka zomrie, ak VŠETKY susedia sú súperove — slepé uličky a hraničné domy sú pasce.
- **Referee zabije hráča**, ktorý nemôže skórovať (0 tri, alebo 1 jednotka + 0 tri) → preto `score −1` v prehrách.

## Čo sme zistili o súperoch

| Súper | Správanie | Ako proti nemu |
|---|---|---|
| `default` (Wood) | = level-2 boss: 3 jednotky na najbližší tri, 1 spawn/ťah, zvyšok random walk; ATTACK až pri > 10 jednotkách | Aktuálny bot ho bije 100 % (win rate, 10+ hier) |
| **czuk** (rank 53, `agent_id=6845057`) | Rovnaký snowball ako Arnaud: 2–8 spawnov/ťah, OUR pile-ups trestal ATTACKom (6 mŕtvych na f52) a surroundom. Po opravách (2026-11-04): ATTACK katastrofa zmizla, surround ≤ 4, ale spawn tempo 1/ťah vs ich 2–8/ťah rozhodne koncovku. LOSS −1:73 (game 916451418). | Rovnaké ako Arnaud: rýchlejší rast počtu tri |
| **Arnaud.Net** (rank 22, `agent_id=6844116`) | **Mass-spawn 5–16/ťah**, recapture cyklus, ATTACK na naše stacky. Do T20 má 2–3× našu armádu. | Ešte neporazený. Treba: rýchlejší rast počtu tri (viac engine) + rozptýlenie jednotiek (anti-ATTACK) + možno 1:1 kópia ich stratégie |
| **M_C** (rank ~50, `agent_id=6843883`) | Podobný snowball, menej presný | Remíza do stredu hry, prehráva koncovku |
| `ctuanle` (rank 483, `agent_id=6843670`) | Slabý — bieme ho (4806:26) | — |

Hrať proti konkrétnemu hráčovi: `./cg replay --seed <S> --opponent <agent_id> --ide`
(legy: `GET /challenges/fall-challenge-2026/opponents` — nick → `agent_id`).

## Otvorené problémy / next steps (prioritne)

1. **Spawn tempo vs silní súperi (czuk, Arnaud, M_C)** — oni 2–16 spawnov/ťah, my 1–3.
   Náš temp je limitovaný počtom vlastnených trojuholníkov × stagger (1 spawn / 3 ťahy / tri).
   Cesta hore: **rýchlejšia expanzia** (viac capture/ťah). Missions experiment mal správnu myšlienku,
   ale online zamrzal — pozri `bot_missions_backup.py`, bug nezistený (lokálny sim vyzeral zdravo!).
2. **ANTI-PILEUP (známy bug, 2 skipnuté testy v `tests/test_game_sim.py`)**: `SPAWN` landing +
   **pass-through parking** (jednotka poslaná na vzdialený cieľ sa 1. krokom zastaví na medzidome —
   ak je to roh tri v dosahu súperovho ATTACKu, nevedomo tam naskladnáme 4–9 jednotiek a jeden
   súperov ATTACK ich zmaže). Opravené čiastočne: spawn corner uniqueness (per ťah), `en_route`
   accounting, pass-through block (parked ≥ 3), `trap_risk` deprioritizácia, emptier-corner spawn
   preference. Stále nepostačuje — potrebné **path-aware end-position planning** (plánovať, kde
   jednotky really skončia: `first_step(src,dst)` pre každý move a počítať to do `parked`).
3. **Rebuild po t=0**: keď prídeme o všetky tri, spawn sa obnoví len cez rebuild mode —
   pomalé. Zvážiť prioritnú „regroup“ fázu.
4. **Lokálny sim vs realita**: sim má jednu vlnu ATTACK (realita = multi-frame), nepoužívaj ho ako
   jediný signál — pred submitom vždy 2–3 online hry vs `default`.
5. **BOT_SPEC.md** je čiastočne zastaraný (písal sa pre staršie verzie bota).

### Testy (2026-11-04)

`tests/test_game_sim.py` rozšírené o `czukRegressionTests` (10 testov, 2 skipnuté):
- `test_never_two_spawns_on_same_corner` — 30 ťahov solo: žiadne 2 SPAWN na ten istý roh (✅ prechádza)
- `test_no_overcommit_beyond_deficit` — ⏭️ skip: stack > opp+3 na dome ešte vzniká (boss port)
- `test_replay_czuk_turns_survive_attack` — ⏭️ skip: ≥ 5 jednotiek v dosahu súperovho ATTACKu (boss port)
- `boss_commands()` v testoch = port level-2 Boss.cs (rovnaký súper ako `default`) — použi ho
  pre vlastné scenáre: `b.play_turn(bot.turn(b), boss_commands(b, rng))`.
- Princíp: **regresné testy píš z reálnych online prehr** (game_id → log → čo nás zabilo → test).

## Workflow (overené)

```bash
./cg unittest                  # lokálne testy (rýchle, žiadne API)
./cg sim --builtin-seed403401 --turns 20        # solo rollout
python3 - <<'PY'               # vlastný sim vs local boss port (pozri chata históriu)
...Board + BotSession + boss()...
PY
./cg test --games 2            # online vs default (spomali! quota)
./cg replay --seed <S> --opponent <id|default> --ide   # 1 hra na konkrétnom seede
./cg limits                    # quota stav
```

- **Quota**: 10/1min, 20/5min, 30/15min, 80/1h, 600/24h test hier. Ne spamovať `./cg test`.
- **Debug online hry**: `results/runs.jsonl` (game_id, seed, tagy) → `./cg replay --game-id <ID> --ide`;
  log aj cez `cg_lib.fetch_game_log(game_id)`. Parsovanie frame-ov: `frame N agent X` + `stdout:`/
  `summary:` riadky; agent 0/1 stdout prichádzajú v pároch, summary ticks medzi ťahmi.
- **Recovery trick**: celý obsah `bot.py` je v transkripte (`agent-transcripts/<id>.jsonl`) —
  Write volania majú `input.content`; StrReplace patche replayuješ `old→new` v poradí. Zachránilo to nám
  verziu, keď experiment zlyhal.
- Commitovať len na požiadanie.

## Známe pasti (netreba znovu objavovať)

- `global X` vo `while True` na module level = SyntaxError (priradenie je už global).
- `bot_input` nezrkadlí súpera (pid 1) — druhý BotSession nie je korektný opponent.
- Seed 466: štart [17,34,41] vs [18,35,40]; najlepšie prvé tri = hub tri (16,22,38)/(15,23,39) typ,
  NIE bočné slepé (3,16,22) — max_d aj sum_d rozhodujú, nie ID.
- Seed 328: dom 36/20 má susedov iba rohy trojuholníka → vacate potrebuje 2 kroky cez sibling.
- 1v1 na rohu = remíza = `my > opp` zlyhá → posielať vždy `opp+1`.
- `SPAWN` prebieha PO `MOVE` → spawnutá jednotka sa v tom istom ťahu nehýbe a blokuje `me_cap` reset.
