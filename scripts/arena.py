#!/usr/bin/env python3
"""Local bot-vs-bot arena on real maps (from seeds/<player>/<seed>.txt + results/runs.jsonl).

Usage: python3 scripts/arena.py botA.py botB.py [--maps N] [--jobs J] [--turns T] [--swap]
Each map is played with A as player 0 (and, with --swap, also as player 1).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from game_sim import Board, BotSession  # noqa: E402


def load_maps() -> list[str]:
    maps: dict[str, str] = {}
    for p in sorted(ROOT.glob("seeds/*/*.txt")):
        txt = p.read_text()
        seed = txt.splitlines()[0]
        maps[seed] = "\n".join(l for l in txt.splitlines() if "=" in l and not l.startswith("agents"))
    runs = ROOT / "results" / "runs.jsonl"
    if runs.exists():
        for line in runs.open():
            r = json.loads(line)
            go = r.get("game_options")
            if go:
                maps.setdefault(go.splitlines()[0], go)
    return list(maps.values())


def play(args) -> dict:
    opts, bot0, bot1, max_turns = args
    board = Board.from_game_options(opts)
    s0, s1 = BotSession(Path(bot0)), BotSession(Path(bot1))
    s0.start(board)
    s1.start(board)
    result = {"seed": opts.splitlines()[0], "end": "turns"}
    tmax = [0.0, 0.0]
    try:
        for turn in range(max_turns):
            dead = [False, False]
            total = len(board.triangles)
            for pid in (0, 1):
                units = board.total_units(pid)
                tri = board.owned_triangles(pid)
                if units == 0 and tri == 0:
                    dead[pid] = True
                elif units == 1 and tri == 0 and board.scores[pid] < board.scores[1 - pid]:
                    dead[pid] = True
                elif board.owned_triangles(1 - pid) >= total * 0.8:
                    dead[pid] = True
            if any(dead):
                result["end"] = f"T{turn}"
                for pid in (0, 1):
                    if dead[pid]:
                        board.scores[pid] = -1
                break
            t0 = time.perf_counter()
            c0 = s0.turn(board, 0)
            t1 = time.perf_counter()
            c1 = s1.turn(board, 1)
            t2 = time.perf_counter()
            tmax[0] = max(tmax[0], t1 - t0) if turn else 0
            tmax[1] = max(tmax[1], t2 - t1) if turn else 0
            board.play_turn(c0, c1)
    except Exception as e:  # noqa: BLE001
        result["error"] = str(e)[:300]
    finally:
        s0.close()
        s1.close()
    result["scores"] = list(board.scores)
    result["units"] = [board.total_units(0), board.total_units(1)]
    result["tmax"] = [round(tmax[0] * 1000), round(tmax[1] * 1000)]
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--maps", type=int, default=20)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--turns", type=int, default=200)
    ap.add_argument("--swap", action="store_true")
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args()
    maps = load_maps()[a.offset : a.offset + a.maps]
    jobs = [(m, a.a, a.b, a.turns) for m in maps]
    if a.swap:
        jobs += [(m, a.b, a.a, a.turns) for m in maps]
    wins = draws = losses = 0
    diff = 0
    tmax = 0
    with ProcessPoolExecutor(a.jobs) as ex:
        for i, r in enumerate(ex.map(play, jobs)):
            a_is0 = i < len(maps)
            sa, sb = (r["scores"][0], r["scores"][1]) if a_is0 else (r["scores"][1], r["scores"][0])
            ua, ub = (r["units"][0], r["units"][1]) if a_is0 else (r["units"][1], r["units"][0])
            ta = r["tmax"][0] if a_is0 else r["tmax"][1]
            tmax = max(tmax, ta)
            if sa > sb:
                wins += 1
            elif sa < sb:
                losses += 1
            else:
                draws += 1
            diff += sa - sb
            if a.v or "error" in r:
                print(f"{'A0' if a_is0 else 'A1'} {r['seed'][:26]:26s} {sa:5d}:{sb:<5d} units {ua}:{ub} {r['end']} tA={ta}ms {r.get('error','')}")
    n = wins + draws + losses
    print(f"A={a.a} vs B={a.b}: W{wins} D{draws} L{losses} / {n}  avg diff {diff / max(1, n):.1f}  max tA {tmax}ms")


if __name__ == "__main__":
    main()
