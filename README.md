# Fall Challenge 2026 — TryAngle Catch bot (Wood 1)

Stav k **2026-11-04 09:47**. Cieľ tohto README: aby si vedel pokračovať bez
předlžovania kontextu — čo funguje, čo nie a prečo.

---

## Aktuálny stav v skratke

| Súbor | Čo je |
|---|---|
| `bot.py` | **Aktuálny bot = kópia `bot2.py`** (token local search, viď sekciu nižšie). Toto submituj. |
| `bot2.py` | Vývojová verzia nového bota (rovnaký obsah ako `bot.py`). |
| `bot_old.py` | Starý „staggered engines" bot (rekonštrukcia: verzia z 12:22 s vypnutou MA cache). |
| `bot_submitted.py` | Kód posledného submitu na CG (2026-11-04 10:22 UTC). |
| `bot_missions_backup.py` | Experiment „missions" (perzistentné ciele + mass-spawn). Lokálne OK, **online 0 % win rate** — príčina nezistená. NEsubmitovať. |
| `bot_recovered.py` | Medzistav recovery (pred replayom patchov), môžeš zmazať. |
| `statement.md` | Pravidlá Wood 1 (sedia s webom). |
| `BOT_SPEC.md` | Detailná špecifikácia + historické analýzy (čiastočne staré). |
| `scoring.yaml` | Opponent `default` ×5, brány: win_rate ≥ 0.2, median ≥ 3, crash ≤ 0.5. Boss sekcia zapoznámkovaná (NO_BOSS v Wood). |
| `tmp_seed_*.txt` | Full game_options seedov na lokálny replay (466 = Arnaud.Net, 328 = M_C, 436/−7474/−8423/194). |

**Posledná validácia `bot.py` (2026-11-04, 11:30)**: unit testy 10 OK (2 skip = známy bug) ·
online `./cg test --games 2` → **2/2 WIN**, všetky brány prešli ·
opravy: spawn-corner uniqueness, `en_route` accounting, `trap_risk`, pass-through parking block,
FOCUS + LAST_FOCUS, fázový rozvrh, swarm doktrína, spawn tempo `owned//3`.

## Nový bot `bot2.py` (2026-11-04 popoludní) — porazil AdrienGI

Online vs AdrienGI (agent 6841548, seed 8557136380578188000): **3× WIN** 88:−1, 88:−1, 81:−1 (games
916529871, 916530660, 916531096 — posledná už so „žiadne 2 SPAWN na jeden dom“); predtým −1:79, −1:81, −1:92. `./cg test --games 3` vs default: 3/3 WIN, median 71.
Lokálne bije starý bot ~117/120.

Ako funguje (jeden ťah, ~10–30 ms):
1. **ATTACK** z vlastných trojuholníkov len na stack ≥ `ATK_MIN+1` (útok stojí 3 jednotky + trojuholník).
2. **SPAWN** na všetkých vlastných nepoužitých (od ťahu 40 cap podľa armády súpera).
3. **Assignment** — jednotky na rohy capturable / čakajúcich (spawn-reset) trojuholníkov, `op+1` na roh.
4. **Token local search** — každá jednotka je token, inkrementálne hodnotenie (house_term + tri_term),
   single moves, composite capture, composite vacate (aj celé skupiny čakajúcich trojuholníkov naraz).

Kľúčová zmena, ktorá rozhodla: **`P_CONT=0.7`, `OADJ_MAX=1`** — hodnota capture sa násobí 0.7 za každý
roh, kde má súper susednú jednotku a my nemáme náskok ≥ 2. Bot bez toho plánoval captures proti
statickému súperovi; AdrienGI ich od T19 blokoval všetky (5 plánovaných → 0), naše stacky na
spornom území zomierali. Lokálne 126/192 vs predchádzajúca verzia.

### Model súpera („opponent IQ guess“) + riziko útokov

Input neobsahuje akcie súpera, bot ich odvodzuje z rozdielu stavov medzi ťahmi (`learn()` v `bot2.py`):
- **Detekcia útoku**: súperov trojuholník (vlastnil ho, mal jednotky na rohoch) zneutrálnel a naše
  jednotky na susednom dome zmizli viac, než vysvetľujú naše vlastné príkazy → útok, veľkosť = stack.
  Overené lokálne: 17/17 útokov detegovaných presne.
- **P(útok | najväčší náš stack v dosahu k)**: Beta-posterior per k, prior z ~80 logovaných hier
  (k=2: 0.15, 3: 0.32, 4: 0.40, 5+: 0.56), monotónne. AdrienGI sa naučil na ~0.49 pre k≥3.
- **keep rate**: aký podiel vlastných trojuholníkov súper drží (nespawnuje). AdrienGI ~0.08, default/boss ~0.95.
- **capture aktivita**: skutočné / predikované captures súpera (tabuľka P(capture | rohy držané, rohy
  vyhrateľné) z logov). AdrienGI ~1.3–1.5×.
- **Mapa rizika**: P(dom je napadnuteľný budúci ťah) z trojuholníkov, ktoré súper bude vlastniť
  (držané × keep, dobyteľné × capture × `RISK_CAPW`). Penalta = `RISK`·WU·(c − `RISK_NET`)·P(útok|c)·riziko.
  `RISK_NET=3`: útok stojí súpera 3 jednotky + trojuholník, takže 2–3 stack obetovať je fér výmena —
  penalizujeme len čistú stratu (inak bot zamrzne, lokálne 16/198).
- MSG ukazuje profil: `a0.09/0.49/0.49` = P(útok) pre stack 2/3/4, `k` keep rate, `c` capture aktivita, `x` počet útokov.

Výsledok: nahradilo statickú `EXP` penaltu; lokálne 164/278 vs bez modelu, vs AdrienGI **WIN 95:−1**
(game 916536436), `./cg test --games 2` 2/2 WIN (79:−1, 63:−1).

Čo NEpomohlo (netreba skúšať znova): `DANGER_CAP>0`, `EXP2>0` (defenzíva = capture stall, lokálne 2/80),
`CONTEST_D`, ladenie `EXP/V_CAP/V_LOSE/THREAT/SPR/WU` (všetko šum).

Nástroje: `scripts/arena.py A.py B.py --maps N --swap` (lokálny turnaj), `scripts/variant.py out.py '{"K":v}'`
(variant parametrov), `scripts/replay_log.py <game_id> --losses --cmds` (resimulácia online logu +
straty ATK/SUR), `scripts/trace.py`, `scripts/losses.py`.

## Benchmark (2026-11-04, 11:30)

### Lokálne solo (50 ťahov; formát skóre/tri/jednotky)

| seed | T10 | T20 | T30 | T50 |
|---|---|---|---|---|
| 403 | 24/3/19 | 89/11/36 | 199/11/36 | 438/12/36 |
| 194 | 16/4/8 | 71/7/32 | 234/19/36 | 614/19/36 |
| 436 | 28/7/11 | 89/8/24 | 167/11/36 | 387/11/36 |
| loick | 10/0/11 | 41/4/25 | 142/14/36 | 422/14/36 |
| czuk | 19/2/16 | 67/8/36 | 203/14/36 | 483/14/36 |
| rikus | 43/7/15 | 133/16/36 | 339/21/36 | 759/21/36 |
| M_C | 16/1/18 | 97/12/36 | 217/12/36 | 457/12/36 |
| Arnaud | 20/2/21 | 176/20/36 | 385/21/36 | 805/21/36 |
| ctuanle | 11/2/12 | 200/39/36 | 590/39/36 | 1370/39/36 |

### Online rematče na rovnakých seedoch (aktuálny bot vs historické výsledky)

| Súper (rank) | Historicky | Teraz | Záver |
|---|---|---|---|
| `default` | 100 % win | **100 %** (2092:16, 350:−1) | dominancia |
| ctuanle (494) | WIN 4806:26 | **WIN 234:−1** | ✅ výhra |
| M_C (56) | LOSS −1:1522 → −1:47 | **LOSS −1:47** | gap sa zúžil, stále prehra |
| Arnaud.Net (32) | LOSS −1:71…123 | **LOSS −1:92** | prehra |
| czuk (nový submit, id 6845662) | LOSS −1:73 | **LOSS −1:118** | súper sa tiež zlepšil (nový bot!) |
| [CG]loick (38) | LOSS −1:46…67 | **LOSS −1:52** | prehra, ich skóre stabilné |
| Rikus (49) | LOSS −1:66…76 | **LOSS −1:74** | prehra |

Pozn.: agent_id súperov sa mení s každým ich submitom — pred rematčom vždy refresh
`GET /challenges/fall-challenge-2026/opponents` (inak 400 INVALID_OPPONENT).

### Lokálny boss-port benchmark (40 ťahov vs level-2 Boss port)

WIN na 8/9 seedov (Arnaud 500:5, rikus 384:27, 403 372:6…). **Výnimka: ctuanle seed — lokálne 0:2 LOSS,
ale ONLINE VÝHRA 234:−1** → sim má odchylku na tejto mape (skúmať: early stall v sim, geometria).

**Záver**: proti `default`-úrovni dominujeme všade. Gap je len proti Silver top-50 swarm botom
(capture tempo 4–7/ťah vs naše 1–2) — riešenie v §Otvorené problémy.

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
| `default` (Wood) | = level-2 boss: 3 jednotky na najbližší tri, 1 spawn/ťah, zvyšok random walk; ATTACK až pri > 10 jednotkách | Aktuálny bot ho bije 100 % (win rate, 15+ hier) |
| **czuk** (rank 53, `agent_id=6845057`) | Rovnaký snowball ako Arnaud: 2–8 spawnov/ťah, OUR pile-ups trestal ATTACKom (6 mŕtvych na f52) a surroundom. Po opravách (2026-11-04): ATTACK katastrofa zmizla, surround ≤ 4, ale spawn tempo 1/ťah vs ich 2–8/ťah rozhodne koncovku. LOSS −1:73 (game 916451418). | Rovnaké ako Arnaud: rýchlejší rast počtu tri |
| **AdrienGI** (rank 320, `agent_id=6841548`) | **Porazil nás napriek nižšiemu ranku!** Pattern: 7-capture burst (f33), potom **systematický lov našich stackov** — 6 ATTACKov (4+5+3+5+3+5 = 25 mŕtvych). My sme viedli (f32: t=3, v=16 vs ich t=1!) — ich burst + lov nás zlomil. LOSS −1:68 (games 916487228/916487642, seed 8557136380578188000). | Stackovanie capture sily na contested roh = inherentne zraniteľné — pozri ČASOVÁ OS nižšie |
| **ChuOkupai** (rank 18, `agent_id=6844913`) | **Najsilnejší testovaný súper**. Otvorenie: my sme boli V PREDOSTI (T3: 3 tri vs ich 2, T12: t=4 v=7, sp=3)! Zlom f45: oni spawnuli **8 jednotiek/ťah** (8+ usable tri) a prebrali vedenie. Naše slabiny: (a) ATTACK na f44 zlyhal ticho — simultánne útoky: ich útok môže zabiť naše rohové jednotky v rovnakej fáze, skôr než sa náš vykoná → ATTACK je teraz konzervatívny (kill ≥ 5 / bezpečné tri / rohy bez súperov); (b) pile-up: attacked 5 + surrounded 3+4 → v=15→5 → kolaps. LOSS −1:76 (game 916484382, seed −6881233887446812000). Straty na pile-upoch: 5+5+3+3+2 = 18 jednotiek. | Otvorenie je parity aj s rank 18! Zostáva: spawn tempo (oni 8/ťah) + anti-pileup |
| **Rikus** (rank 50, `agent_id=6843770`) | Rovnaká trieda ako loick: 3–8 spawnov/ťah, 15–38 MOVEov/ťah, surround-taktika (obkľúči naše pozície masou). Naše opening je parity (T1: 2 tri!), ale ich armáda rastie rýchlejšie → surround 3–4 jednotiek/ťah od T15. LOSS −1:70 (game 916480092, seed 8799062500137730000). | Rovnaký koreň: capture tempo → owned count → spawn tempo → armáda |
| **[CG]loick** (rank 30, `agent_id=6841719`) | Najrýchlejší známy swarm: **13–31 MOVEov/ťah** (hýbe VŠETKÝMI jednotkami), 4–7 capture/ťah v strede hry, 5–8 spawnov/ťah. Skoro žiadna garda — jednotky neustále captureujú. Naše porovnanie: mv 2–8, sp 1–2. LOSS −1:59 (game 916454805, seed 6661582836916759000). | Doktrína „swarm nad garrisson“ — naše jednotky musia neustále captureovať, nie sedieť na rohoch |
| **Arnaud.Net** (rank 22, `agent_id=6844116`) | **Mass-spawn 5–16/ťah**, recapture cyklus, ATTACK na naše stacky. Do T20 má 2–3× našu armádu. | Ešte neporazený. Treba: rýchlejší rast počtu tri (viac engine) + rozptýlenie jednotiek (anti-ATTACK) + možno 1:1 kópia ich stratégie |
| **M_C** (rank ~50, `agent_id=6843883`) | Podobný snowball, menej presný | Remíza do stredu hry, prehráva koncovku |
| `ctuanle` (rank 483, `agent_id=6843670`) | Slabý — bieme ho (4806:26) | — |

### Naučené zo súperov (2026-11-04, [CG]loick + Rikus analýza)

1. **Garrisson je drahý**: stará doktrína rezervovala `opp+1` jednotiek na KAŽDOM rohu KAŽDého
   own tri — pri 8 tri to parkovalo ~24 jednotiek, kým loick hýbal 20+. Oprava: **fázový rozvrh**
   (`phase_of(cs) = (TURN_NO + sum(cs)) % 3`) — spawn len na phase-0 tri, lock max 1/roh s budgetom
   `army//2`, ostatok armády swarmuje. Solo skóre @T29: rikus-seed 307 (t=20!), czuk 204, loick 128.
2. **Spawn tempo škálovať s owned countom**: `n_spawn = owned // 3` (3-ťahový cyklus spawn→vacate→
   recapture). Testované aj `//2` — na loick/czuk mapách HORŠIE (67→56, 78→71), lebo neutralizácia
   predbehne capture tempo. `//3` je sweet spot.
3. **FOCUS (sticky cieľ)**: greedy prehodnocuje cieľ každý ťah → jednotky wanderujú. FOCUS sa
   vyberie raz (cluster + najbližší), obsluhuje sa PRED ostatnými capturemi, drží sa kým ho
   nezískame (alebo 14 ťahov). `LAST_FOCUS` chráni cluster kotvu pred spawnom.
4. **Pass-through parking**: jednotka na vzdialený cieľ sa 1. krokom BFS zastaví na medzidome —
   ak je to roh v dosahu súperovho ATTACKu, nevedomo naskladnáme 4–9 jednotiek = jeden ATTACK
   ich zmaže (czuk f52: 6 mŕtvych). Blokované cez `parked` sledovanie.
5. **Spawn engine nikdy nespí**: ak žiaden phase-0 tri nie je usable, spawnuj najlepší usable
   aj mimo fázy — inak motor stojí 2 ťahy (Rikus f50–f62: sp=0 tri ťahy = smrť).
6. **Pre-positioning počas vacate**: jednotky opúšťajúce tri parkujú susedne k jeho ostatným
   rohom (`park_bonus`) — v staffing fáze sa vrátia 1 krokom a cyklus neprestáva.
7. **Hard trap avoidance**: ak existuje capture bez trap-rizika, trap-riskové sa preskočia
   úplne (nie len deprioritizácia) — stack v dosahu živého súperovho ATTACKu = strata stacku.

### Zvyšná gapa vs top Silver (Rikus/loick/Arnaud)

**Armádna gapa v strede hry** (oni 3× naša armáda → surround-taktika). Koreň: ich capture tempo
4–7/ťah vs naše 1–2. Riešenie vyžaduje **paralelné multi-capture plánovanie so zdieľanými rohmi**
(1. capture otvorí cluster, ďalšie stoja len 1–2 jednotky za ne-zdieľaný roh). Missions experiment
(`bot_missions_backup.py`) mal tú myšlienku, ale online zamrzal — bug nezistený.

### ČASOVÁ OS anti-pileup (AdrienGI analýza — prečo dissolve nestačí)

```
Round N:   naša capture sila (3-4 J) prichádza na contested roh → capture OK
           (v TOM ISTOM kole súperove MOVEy môžu urobiť iný tri ready)
Round N+1 fáza 0: súperov ATTACK zabije náš stack — SKÔR než sa náš "dissolve"
           pass (fáza MOVE round N+1) vykoná!
```

→ Dissolve po capture je **vždy neskoro**. Jediné ochrany:
1. **Minimalizovať stack už pri capture** — posielať presne `opp+1`, jednotky z rôznych
   smerov (via-count per medzidom), nie cez jeden hub.
2. **trap_risk musí predvídať NOVÉ ready tri** — súper môže urobiť tri ready TOMTO kole
   (their moves) vedľa nášho capture cieľa. Predikcia: tri, kde súper má jednotky pri
   všetkých 3 rohoch v dosahu 1 kroku = „ready next turn" → počítať do trap_risk.
3. **Vhodnejšie je capture NE-kontestovaného rohu** (opp=0) — žiadny stack pred súperom.

### AdrienGI lovný mechanizmus (2026-11-04, games 916487228–916492529)

AdrienGI zaútočil **13-krát za hru** (2–10 jednotiek na útok, ~39 strát) — každý náš stack
v dosahu ich tri dostal útok. Naše opravy znížili max zásah z 10 na 5, ale attrition war
sa prehráva: ich 39 kills vs našich ~15 spawnov.

**Punish mechanizmus (IMPLEMENTOVANÉ 2026-11-04)**: `LAST_OWNER` tracking + `punish_tris`
(4B1, priorita pred FOCUS) — capture tri, ktoré súper práve neutralizoval útokom/spawnom.
Výsledok vs AdrienGI: capture ich tri 1–3/ťah (funguje), ALE ich swarm rebuild je rýchlejší.

**FINÁLNA DIAGNÓZA prehier vs AdrienGI (8 hier, seed 8557136380578188000)**: hra sa rozhodne
do T20 — naša armáda je vyhladená (12→1 jednotka) ich útokmi na naše capture stacky; endgame
(t=0, 4 jednotky, 31 capturable tri) je už nezvratný — 80 ťahov bez jediného captureu. Koreň:
**tempo-flywheel** (ich capture 4–7/ťah → owned 10–20 → spawn 5–8/ťah → armáda 25+; náš:
1–3/1–5/1–2). Raid-the-rear rebuild testovaný a REVERTOVANÝ (default 100 %→50 %, vs AdrienGI
bez efektu). Engine-hunting ATTACK (náš najväčší zbrojný lever) fireuje len 1–2×/hra kvôli
simultánnemu útoku guardu — bez neho attrition favoiruje väčšiu armádu vždy.

Hrať proti konkrétnemu hráčovi: `./cg replay --seed <S> --opponent <agent_id> --ide`
(legy: `GET /challenges/fall-challenge-2026/opponents` — nick → `agent_id`).

## Otvorené problémy / next steps (prioritne)

1. **Spawn tempo vs silní súperi (czuk, Arnaud, M_C)** — oni 2–16 spawnov/ťah, my 1–3.
   Náš temp je limitovaný počtom vlastnených trojuholníkov × stagger (1 spawn / 3 ťahy / tri).
   Cesta hore: **rýchlejšia expanzia** (viac capture/ťah). Missions experiment mal správnu myšlienku,
   ale online zamrzal — pozri `bot_missions_backup.py`, bug nezistený (lokálny sim vyzeral zdravo!).
2. **ANTI-PILEUP (známy bug, 2 skipnuté testy v `tests/test_game_sim.py`)** — HLAVNÁ PRIČINA PREHIER
   s top Silver: `SPAWN` landing + **pass-through parking** + capture konvergencia vytvoria stack
   4–9 jednotiek na jednom dome → jeden súperov ATTACK/surround ich zmaže (ChuOkupai: 5+5+3+3+2 = 18
   straty na jednej hre!). Opravené čiastočne: spawn corner uniqueness, `en_route` accounting,
   pass-through block, `trap_risk`, predictive surround escape, kotvy max 1/roh.
   **Nutné riešenie**: end-position-aware planning — priraďovanie jednotiek musí plánovať KDE
   really skončia (`first_step(src,dst)` pre každý move) a cap-núť `parked[h] ≤ 2` priamo
   v priraďovacom algoritme (nie ako afterthought spread-pass, ktorý nemôže recall-núť
   už commitnuté jednotky).
3. **Capture tempo vs swarm súperov**: loick robí 4–7 capture/ťah v strede hry, my 1–2. Treba
   **paralelné multi-capture plánovanie** so zdieľanými rohmi (missions experiment mal správnu
   myšlienku, ale online zamrzal — bug nezistený, `bot_missions_backup.py`).
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
