#!/usr/bin/env python3
"""Trace one local game turn by turn: python3 scripts/trace.py bot0.py bot1.py <seed-substring> [--turns N] [--cmds]"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from arena import load_maps  # noqa: E402
from game_sim import Board, BotSession  # noqa: E402


def main() -> None:
    b0, b1, key = sys.argv[1:4]
    turns = int(sys.argv[sys.argv.index("--turns") + 1]) if "--turns" in sys.argv else 60
    show = "--cmds" in sys.argv
    opts = next(m for m in load_maps() if key in m.splitlines()[0])
    board = Board.from_game_options(opts)
    s0, s1 = BotSession(Path(b0)), BotSession(Path(b1))
    s0.start(board)
    s1.start(board)
    print(f"tris={len(board.triangles)} nodes={len(board.coords)}")
    for t in range(turns):
        c0 = s0.turn(board, 0)
        c1 = s1.turn(board, 1)
        board.play_turn(c0, c1)
        print(
            f"T{t+1:3d} score {board.scores[0]:5d}:{board.scores[1]:<5d} tris {board.owned_triangles(0):2d}:{board.owned_triangles(1):<2d} "
            f"units {board.total_units(0):2d}:{board.total_units(1):<2d}"
        )
        if show:
            print("   0:", c0[:400])
            print("   1:", c1[:400])
        if board.total_units(0) + board.owned_triangles(0) == 0 or board.total_units(1) + board.owned_triangles(1) == 0:
            break
    s0.close()
    s1.close()


if __name__ == "__main__":
    main()
