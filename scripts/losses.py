#!/usr/bin/env python3
"""Per-turn unit-loss attribution for a local game.

python3 scripts/losses.py bot0.py bot1.py <seed-substring> [--turns N] [--show T1,T2]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from arena import load_maps  # noqa: E402
from game_sim import Board, BotSession  # noqa: E402

LOG: list = []
_orig_sur = Board.surround
_orig_atk = Board.apply_attack


def _sur(self):
    before = {n: u[:] for n, u in self.units.items()}
    r = _orig_sur(self)
    for n, u in self.units.items():
        for p in (0, 1):
            if u[p] < before[n][p]:
                LOG.append(("SUR", p, before[n][p] - u[p], n))
    return r


def _atk(self, pid, a, b, c, t, validated=False):
    k = self.units[t][1 - pid]
    r = _orig_atk(self, pid, a, b, c, t, validated)
    if r:
        LOG.append(("ATK", 1 - pid, k, t, (a, b, c)))
    return r


Board.surround = _sur
Board.apply_attack = _atk


def main() -> None:
    b0, b1, key = sys.argv[1:4]
    turns = int(sys.argv[sys.argv.index("--turns") + 1]) if "--turns" in sys.argv else 40
    show = set()
    if "--show" in sys.argv:
        show = {int(x) for x in sys.argv[sys.argv.index("--show") + 1].split(",")}
    opts = next(m for m in load_maps() if key in m.splitlines()[0])
    board = Board.from_game_options(opts)
    s0, s1 = BotSession(Path(b0)), BotSession(Path(b1))
    s0.start(board)
    s1.start(board)
    lost = [0, 0]
    for t in range(1, turns + 1):
        LOG.clear()
        pre = {n: u[:] for n, u in board.units.items()}
        c0 = s0.turn(board, 0)
        c1 = s1.turn(board, 1)
        board.play_turn(c0, c1)
        for e in LOG:
            lost[e[1]] += e[2]
        ev = " ".join(f"{e[0]}:p{e[1]}-{e[2]}@{e[3]}" for e in LOG if e[2])
        print(f"T{t:3d} units {board.total_units(0):2d}:{board.total_units(1):<2d} tris {board.owned_triangles(0):2d}:{board.owned_triangles(1):<2d} {ev}")
        if t in show:
            print("   pre  p0:", {n: u[0] for n, u in pre.items() if u[0]}, " p1:", {n: u[1] for n, u in pre.items() if u[1]})
            print("   0:", c0)
            print("   1:", c1)
    print("total lost", lost)
    s0.close()
    s1.close()


if __name__ == "__main__":
    main()
