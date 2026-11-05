#!/usr/bin/env python3
"""Add the opponent of a game to the seed library: seeds/<nick>/<seed>.txt + a row in seeds/index.csv.

Usage:
  python3 scripts/add_player.py <game_id|replay URL> [...] [--note TEXT]
  python3 scripts/add_player.py --losses [N] [--easy] [--note TEXT]
    --losses N   scan our last N ranking battles (default 30) and add the lost ones
    --easy       ... only losses to opponents ranked below us
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cg_lib import SEEDS_DIR, api, fetch_game_log, game_summary, opponent_nick, save_seed  # noqa: E402

INDEX = SEEDS_DIR / "index.csv"
FIELDS = [
    "added_utc", "game_id", "seed", "nick", "opp_agent_id", "opp_rank", "my_rank",
    "result", "my_score", "opp_score", "file", "note",
]


def indexed_games() -> set[str]:
    if not INDEX.exists():
        return set()
    with INDEX.open(encoding="utf-8") as f:
        return {r["game_id"] for r in csv.DictReader(f)}


def add_game(gid: int, note: str, known: set[str]) -> dict | None:
    log = fetch_game_log(gid)
    if not log.startswith("game "):
        print(f"{gid}: log nedostupný ({log[:120]})")
        return None
    s = game_summary(log)
    nick = opponent_nick(log)
    path = save_seed(log)
    seed = s["seed"] or ""
    file = SEEDS_DIR / (nick or "unknown") / f"{'neg' + seed[1:] if seed.startswith('-') else seed}.txt"
    row = {
        "added_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M"),
        "game_id": gid, "seed": seed, "nick": nick,
        "opp_agent_id": s["opp_agent_id"], "opp_rank": s["opp_rank"], "my_rank": s["my_rank"],
        "result": s["result"], "my_score": s["my_score"], "opp_score": s["opp_score"],
        "file": file.relative_to(ROOT) if file.exists() else "", "note": note,
    }
    status = "nový seed" if path else "seed už bol"
    print(f"{gid}: {s['result']} {s['my_score']}:{s['opp_score']} vs {nick} "
          f"(rank {s['opp_rank']}, my {s['my_rank']}) -> {row['file']} [{status}]")
    if str(gid) in known:
        return None
    new = not INDEX.exists()
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    with INDEX.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
    known.add(str(gid))
    return row


def recent_losses(challenge: str, n: int, easy: bool) -> list[int]:
    battles = api("GET", f"/challenges/{challenge}/battles?limit={n}").get("battles", [])
    out = []
    for b in battles:
        if not b.get("done"):
            continue
        s = game_summary(fetch_game_log(b["game_id"]))
        if s["result"] != "L":
            continue
        if easy and not (s["opp_rank"] and s["my_rank"] and s["opp_rank"] > s["my_rank"]):
            continue
        out.append(b["game_id"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("games", nargs="*", help="game_id or replay URL")
    ap.add_argument("--losses", type=int, nargs="?", const=30, metavar="N")
    ap.add_argument("--easy", action="store_true")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    challenge = yaml.safe_load((ROOT / "scoring.yaml").open(encoding="utf-8"))["challenge"]
    gids = []
    for g in a.games:
        m = re.search(r"\d{6,}", g)
        if not m:
            ap.error(f"neviem nájsť game_id v {g!r}")
        gids.append(int(m.group(0)))
    if a.losses:
        found = recent_losses(challenge, a.losses, a.easy)
        print(f"Prehry v posledných {a.losses} ranking hrách{' (so slabšími)' if a.easy else ''}: {len(found)}")
        gids += found
    if not gids:
        ap.error("zadaj game_id / URL alebo --losses")
    known = indexed_games()
    for gid in gids:
        add_game(gid, a.note, known)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
