#!/usr/bin/env python3
"""Debug one bot turn or short rollout locally. Usage:
  python scripts/sim_turn.py --seed-file seeds/czuk/neg5800737516579411000.txt --turns 5
  python scripts/sim_turn.py --builtin-seed403401 --turns 10 --opp pass
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from game_sim import Board, BotSession, SEED_4034019036303909000


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seed-file", type=Path)
    p.add_argument("--builtin-seed403401", action="store_true")
    p.add_argument("--turns", type=int, default=5)
    p.add_argument("--bot", type=Path, default=ROOT / "bot.py")
    p.add_argument("--opp", choices=("pass",), default="pass")
    args = p.parse_args()

    if args.builtin_seed403401:
        opts = SEED_4034019036303909000
    elif args.seed_file:
        opts = args.seed_file.read_text()
    else:
        p.error("use --seed-file or --builtin-seed403401")

    b = Board.from_game_options(opts)
    bot = BotSession(args.bot)
    bot.start(b)
    print(f"houses={len(b.coords)} triangles={len(b.triangles)}")
    print(f"start units p0={b.total_units(0)} at", [n for n in sorted(b.coords) if b.units[n][0] > 0])

    try:
        for t in range(1, args.turns + 1):
            cmd = bot.turn(b)
            opp = "" if args.opp == "pass" else ""
            print(f"\n--- turn {t} bot: {cmd or ';'}")
            b.play_turn(cmd, opp)
    finally:
        bot.close()
        owned = [tr.corners() for tr in b.triangles if tr.owner == 0]
        print(f"score {b.scores[0]}-{b.scores[1]} units={b.total_units(0)} owned_tris={len(owned)}")


if __name__ == "__main__":
    main()
