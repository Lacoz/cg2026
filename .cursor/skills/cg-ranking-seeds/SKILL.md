---
name: cg-ranking-seeds
description: Keeps the TryAngle Catch ranking history in ranking.csv and the maps of played games in seeds/<player>/<seed>.txt. Use whenever submitting the bot, checking rank / leaderboard / progress, running ./cg replay or online test games against a named opponent, fetching battle logs, adding a player from a lost game, or when the user mentions rank, ranking, submit, replay, seed, loss or opponent (súper, hráč, prehra, pridaj hráča).
---

# Ranking history and seed library (cg2026)

Two pieces of state live in the repo and must stay current:

| File | Content | Written by |
|---|---|---|
| `ranking.csv` | one row per rank snapshot from `GET /challenges/fall-challenge-2026/progress` | `./cg rank [note]`, `./cg replay` (auto, at most every 30 min) |
| `seeds/<nick>/<seed>.txt` | full `game_options` of a map (seed, units, edges, nodes); negative seed → `neg` prefix | `./cg add`, `run_test_game` in `scripts/cg_lib.py` (auto), `save_seed(log)` |
| `seeds/index.csv` | which game each seed came from, opponent rank, result | `./cg add` |

Both are tracked in git; commit them together with the bot change they belong to (only when the user asks for a commit).

## Ranking

- **After a submit**: poll `/progress` until `percentage == 100`, then
  `./cg rank "submit <HH:MM> UTC: <what changed>"`. A row with `percentage < 100` is provisional; if you log one, say so in the note.
- **When the user asks about rank / leaderboard**: run `./cg rank "<short reason>"` instead of a bare API call, so every check leaves a row.
- `git_head` is the local HEAD at logging time, not necessarily the submitted code; put the submitted commit or file in the note when it differs.
- The API has no rank history for older submissions — never invent rows; approximate backfills must say where the number came from in the note.
- Compare a new submit against earlier rows in the same league (`league_rank / league_total`); `score` is the CG skill rating.

## Seeds

- **User found a loss / wants a player added** ("pridaj hráča", a replay link or game id):
  `./cg add <game_id|replay URL> [...] --note "<why>"`. It stores the map and appends a row to
  `seeds/index.csv` (game_id, seed, nick, agent_id, ranks, result, score, file, note).
- **Easy losses from the arena**: `./cg add --losses 30 --easy` adds every loss of the last 30
  ranking battles where the opponent was ranked below us (`--losses` alone: all losses). Report
  the list (nick, opponent rank vs ours, score) to the user.
- `./cg replay ...` always stores the map under the opponent's nick (taken from the log's `agents:` block; `[CG]` prefixes stripped, CG default bot → `default`).
- Other online test games store it only for named opponents (`opponent` is an agent id), not for `default`/`boss` batches from `./cg test`.
- For a battle log fetched by hand (`fetch_game_log(game_id)`), call `save_seed(log)` from `scripts/cg_lib.py` if the game is worth keeping (a loss, a new strong opponent).
- Existing files are never overwritten; the same map against another opponent gets its own file in that opponent's folder.
- Opponent unknown → `seeds/unknown/`. Moving a file between folders: `git mv`.
- Consumers: `scripts/arena.py` loads `seeds/*/*.txt` (+ `results/runs.jsonl`), `./cg sim --seed-file seeds/<nick>/<seed>.txt`, `./cg replay --game-options "$(cat seeds/<nick>/<seed>.txt)" --opponent <agent_id>`.
- Agent ids change with every submit of the opponent: refresh via `GET /challenges/fall-challenge-2026/opponents` (nick → `agent_id`) before replaying against a nick.

## Checklist after any online activity

```
- [ ] submit done → rank logged at percentage 100 with a note
- [ ] replay / named test game → "Seed uložený: seeds/..." printed (or file already existed)
- [ ] notable result (win/loss vs named opponent) → README section of that opponent updated
```
