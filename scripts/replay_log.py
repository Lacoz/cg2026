#!/usr/bin/env python3
"""Re-simulate an online game log locally and print per-turn stats for both players.

Usage: python3 scripts/replay_log.py <game_id|log_file> [--turns N] [--cmds]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_sim import Board  # noqa: E402


def load_log(arg: str) -> str:
    p = Path(arg)
    if p.exists():
        return p.read_text()
    from cg_lib import fetch_game_log

    return fetch_game_log(int(arg))


def parse(log: str):
    opts = re.search(r"options: (.*?)\nagents:", log, re.S).group(1)
    opts = "\n".join(l.strip() for l in opts.splitlines())
    names = re.findall(r"^\s+(\d) (\S+) \(", log, re.M)
    turns = []
    cur = {}
    for m in re.finditer(r"frame \d+ agent (\d)\n(?:  summary:.*\n(?:      .*\n)*)?  stdout: (.*)", log):
        a = int(m.group(1))
        if a in cur:
            turns.append(cur)
            cur = {}
        cur[a] = m.group(2)
        if len(cur) == 2:
            turns.append(cur)
            cur = {}
    if cur:
        turns.append(cur)
    return opts, dict((int(i), n) for i, n in names), turns


def main() -> None:
    log = load_log(sys.argv[1])
    show_cmds = "--cmds" in sys.argv
    limit = 999
    if "--turns" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--turns") + 1])
    LOG = None
    if "--losses" in sys.argv:
        from losses import LOG
    opts, names, turns = parse(log)
    b = Board.from_game_options(opts)
    print(f"0={names.get(0)} 1={names.get(1)} tris={len(b.triangles)} nodes={len(b.coords)}")
    for i, t in enumerate(turns[:limit]):
        c0, c1 = t.get(0, ""), t.get(1, "")
        b.play_turn(c0, c1)
        def cnt(cmds, k):
            return sum(1 for c in cmds.split(";") if c.strip().upper().startswith(k))
        occ = [sum(1 for n in b.coords if b.units[n][p] > 0) for p in (0, 1)]
        print(
            f"T{i+1:3d} score {b.scores[0]:5d}:{b.scores[1]:<5d} tris {b.owned_triangles(0):2d}:{b.owned_triangles(1):<2d} "
            f"units {b.total_units(0):2d}:{b.total_units(1):<2d} occ {occ[0]:2d}:{occ[1]:<2d} "
            f"S{cnt(c0,'SPAWN')}/{cnt(c1,'SPAWN')} A{cnt(c0,'ATTACK')}/{cnt(c1,'ATTACK')}"
        )
        if LOG is not None:
            for e in LOG:
                print("   ", e)
            LOG.clear()
        if show_cmds:
            print("   0:", c0[:300])
            print("   1:", c1[:300])


if __name__ == "__main__":
    main()
