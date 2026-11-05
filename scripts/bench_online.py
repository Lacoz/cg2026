#!/usr/bin/env python3
"""Online benchmark: play a bot on the maps of seeds/index.csv against the same opponents.

Usage: python3 scripts/bench_online.py BOT.py [BOT2.py ...] [--note-match TEXT] [--label PREFIX] [--limit N (default 3)]
Several bots alternate on every map (same opponent version, same moment), label = PREFIX + file stem.
Opponent agent ids are refreshed from /opponents by nick (they change with every submit).
Waits for the test-game rate limits; one result line per game, appended to results/bench.jsonl.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cg_lib import SEEDS_DIR, api, append_jsonl, run_test_game  # noqa: E402


def wait_for_quota(challenge: str) -> None:
    while True:
        lim = api("GET", f"/limits?challenge={challenge}")
        full = [w for w in lim.get("test_games", []) if w.get("remaining", 1) <= 0]
        if not full:
            return
        s = max(5, min(w.get("resets_in_seconds", 30) for w in full) + 2)
        print(f"  limit {full[0]['name']} vyčerpaný, čakám {s}s", flush=True)
        time.sleep(s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bots", type=Path, nargs="+", help="several bots alternate on every map")
    ap.add_argument("--note-match", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--limit", type=int, default=3, help="maps to play (0 = all)")
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "scoring.yaml").open(encoding="utf-8"))
    challenge, language = cfg["challenge"], cfg["language"]
    with (SEEDS_DIR / "index.csv").open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if a.note_match in r["note"] and r["file"]]
    if a.limit:
        # one map per opponent first, so a small sample is not a single player
        seen: set = set()
        first = [r for r in rows if not (r["nick"] in seen or seen.add(r["nick"]))]
        rows = (first + [r for r in rows if r not in first])[: a.limit]
    opps = api("GET", f"/challenges/{challenge}/opponents")["opponents"]
    ids = {o["nickname"]: o["agent_id"] for o in opps if o.get("nickname")}
    labels = [f"{a.label}{b.stem}" for b in a.bots]
    score = {lb: [0, 0] for lb in labels}
    for r in rows:
        nick = r["nick"]
        agent = ids.get(nick) or next((v for k, v in ids.items() if k.endswith(nick)), None)
        if agent is None:
            print(f"{nick}: nie je v /opponents, preskakujem")
            continue
        opts = (ROOT / r["file"]).read_text(encoding="utf-8").strip()
        for bot, label in zip(a.bots, labels):
            wait_for_quota(challenge)
            try:
                m = run_test_game(challenge, bot, language, str(agent), wait=30, game_options=opts, keep_seed=False)
            except SystemExit as e:
                print(f"{nick}: chyba {e}")
                continue
            score[label][0 if m.win else 1] += 1
            w, l = score[label]
            print(f"{label:12s} {nick[:14]:14s} {'W' if m.win else 'L'} {m.my_score}:{m.opp_score}  game {m.game_id}  ({w}:{l})", flush=True)
            append_jsonl(ROOT / "results" / "bench.jsonl", {
                "ts": datetime.now(timezone.utc).isoformat(), "label": label, "bot": str(bot),
                "nick": nick, "agent_id": agent, "seed": r["seed"], "src_game": r["game_id"],
                "game_id": m.game_id, "win": m.win, "my_score": m.my_score, "opp_score": m.opp_score,
            })
    for label, (w, l) in score.items():
        print(f"{label}: W{w} L{l}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
