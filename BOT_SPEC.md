# Fall Challenge 2026 — špecifikácia bota (TryAngle Catch)

## Cieľ hry

- **Body:** +1 za každý **tvoj** trojuholník na konci ťahu (maximálne držať obsadené).
- **Výhra:** viac bodov, alebo ≥80 % trojuholníkov, alebo súper bez jednotiek/trojuholníkov.
- **Bronze (aktuálne):** príkazy `MOVE`, `SPAWN` (cesty `ADD_PATH` / `ATTACK` až vyššie ligy).

## Prečo „stále len 3 vojaci“

| Fakt | Dôsledok |
|------|----------|
| Štart = **3 jednotky** | Bez ďalších akcií armáda nerastie. |
| Nová jednotka = **`SPAWN` na tvojom trojuholníku** | Musíš najprv **obsadiť** trojuholník (vlastniť **všetky 3 rohy**). |
| `SPAWN` trojuholník **zneutrálí** | 1 ťah príde o bod z neho, ale získaš jednotku na expanziu — boss to robí každý ťah. |
| Jeden `MOVE` = **1 krok** 1 jednotky z domu, kde **začala** ťah | Veľa príkazov v jednom výstupe = veľa jednotiek na mape (nie vizuálny bug). |

**Záver:** Bot musí bežať slučku **obsad → spawn → obsad ďalší** s koordináciou **3 rohov naraz**, nie len posúvať troch mužov na jeden dom.

## Fázy ťahu (referee)

1. Všetky **MOVE** (priorita 1, viacero snímok v rámci ťahu).
2. Všetky **SPAWN** (priorita 2).
3. Zabitie **obklčených** jednotiek.
4. **Obsadenie** trojuholníkov (vlastníctvo rohov).

Výstup: `MOVE …;MOVE …;SPAWN …` (poradie v reťazci nevadí, fázy sú pevné).

## Vlastníctvo domu (zjednodušene)

- Dom je **tvoj**, ak `myUnits > oppUnits`, alebo ak **všetci susedia** sú tvoji (pravidlo obklíčenia susedov).
- Obsadenie trojuholníka: **všetky 3 rohy** musia byť tvoje + `meCanCapture == 1`.

## Architektúra bota (ciele)

### 1. Makro: rast armády

```
CAPTURE(t₁) → [next turn] SPAWN(t₁) → +1 unit
             → CAPTURE(t₂) while reinforcing t₁ if needed
             → SPAWN all owned triangles each turn when possible
```

- **Každý ťah:** `SPAWN` na **každom** trojuholníku s `owner == 0` (my).
- Spawn umiestniť na roh, ktorý posúva **ďalšiu misiu** (najslabší / smer k ďalšiemu capture).

### 2. Meso: misia na trojuholník

Pre vybraný trojuholník `T`:

1. Rohy `need = { c ∈ T | c nie je náš }`.
2. **Round-robin:** min. **1 jednotka smerom ku každému** `c ∈ need` (nie všetci na jeden roh).
3. **Doplnenie:** zvyšok budgetu podľa `(my - opp)` na rohu (priorita prehraných rohov).
4. **Budget:** max `movable_units(h)` z každého domu (začiatok ťahu); nepresúvať z rohu, kde by sme **stratili** väčšinu (`my <= opp`).

### 3. Mikro: výber misií (viac frontov)

| Počet našich jednotiek | Počet paralelných misií |
|------------------------|-------------------------|
| ≤ 5 | 1 |
| 6–14 | 2 |
| ≥ 15 | 3 |

Priorita misie:

1. Trojuholník už **náš** (`owner == 0`) ale roh ohrozený — obrana bodov.
2. **2/3** rohov naše — dokončiť capture čo najskôr.
3. **1/3** — ak je blízko.
4. Nízka súčet vzdialeností (min. assignment jednotiek → rohy).

**Vyčerpať budget:** ak misia potrebuje len 1 roh, zvyšné jednotky nesmú stáť idle — každá `movable` jednotka dostane `MOVE` smerom k najbližšiemu potrebnému rohu (viac jednotiek na roh = boj o väčšinu).

### 4. Metriky úspechu (test / log)

- `myScore` rastie každých ~5 ťahov.
- Po ~turn 10: **> 3** jednotiek celkom (ak nie, spawn/capture zlyháva).
- Po ~turn 20: **≥ 1** owned triangle + pravidelné spawny v logu (`$0 spawned`).

## Vstup / výstup (implementácia)

- Súbor: `bot.py`, Python 3.
- Graf: `adj`, `paths` — BFS každý ťah (hrany sa môžu meniť až v Silver+).
- Stav: `my_u`, `opp_u`, zoznam `Triangle`.

## Known gaps (TODO vyššie ligy)

- `ATTACK` — zničiť jednotky na susednom dome cez trojuholník.
- `ADD_PATH` / `REMOVE_PATH` — skratky na mape.
- Simulácia 1 ťah dopredu pre `meCanCapture` po spawn.

## Feedback loop (test → gate → submit)

Lokálny workflow pred submisou na CodinGame:

```bash
pip install -r requirements.txt   # PyYAML
chmod +x cg

./cg test                         # batch test games + scoring.yaml gates
./cg test --opponent boss --games 10
./cg submit                       # submit len ak gates prejdú
./cg submit --force               # submit aj po fail (výnimočne)
./cg limits                       # zvyšok test-game kvót API
```

- **Konfigurácia prahov:** `scoring.yaml` (win rate, median score, crash rate per opponent).
- **História behov:** `results/runs.jsonl` (každá hra + metriky), `results/summary-<run>.json`.
- **Voliteľný referee:** `./cg local` — klon `TryAngle-Catch`, Maven build, viewer na `:8888` (Java + mvn).

Agent / CI: `./cg test` exit code **0** = gates OK, **1** = neodosielať.

### Online replay podľa seed (slabé miesta)

1. `./cg test` alebo `./cg weak --arena` — zoznam prehier + **seed** / **game_id**.
2. Otvor [IDE](https://www.codingame.com/ide/challenge/fall-challenge-2026) v prehliadači.
3. `./cg replay --seed <SEED> --opponent boss --ide` — rovnaká mapa, replay v IDE vieweri.
4. Presnejší replay: `./cg replay --game-id <ID> --ide` (arena aj test hry).

Export: `results/WEAK.md`, `results/weak_index.json` (príkazy `replay_cmd`).

## Referencie

- Pravidlá: `statement.md`
- Referee: [TryAngle-Catch](https://github.com/eulerscheZahl/TryAngle-Catch)
- Stub: `stub-generator.txt`
