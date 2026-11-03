#!/usr/bin/env python3
"""Run batch CodinGame test games and check scoring.yaml gates."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cg_lib import (  # noqa: E402
    GameMetrics,
    append_jsonl,
    git_short_hash,
    ide_url,
    limits,
    median,
    run_test_game,
)

DEFAULT_CONFIG = ROOT / "scoring.yaml"


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def summarize(games: list[GameMetrics]) -> dict:
    if not games:
        return {"games": 0}
    wins = sum(1 for g in games if g.win)
    crashes = sum(
        1 for g in games if g.timeout or g.my_score == -1 or g.eliminated
    )
    return {
        "games": len(games),
        "wins": wins,
        "win_rate": wins / len(games),
        "crash_rate": crashes / len(games),
        "median_my_score": median([float(g.my_score) for g in games if g.my_score >= 0]),
        "mean_spawns": statistics.mean(g.spawns for g in games),
        "mean_captures": statistics.mean(g.captures for g in games),
        "mean_move_errors": statistics.mean(g.move_errors for g in games),
    }


def check_gates(summary: dict, gates: dict) -> list[str]:
    failures: list[str] = []
    if "min_win_rate" in gates and summary["win_rate"] < gates["min_win_rate"]:
        failures.append(
            f"win_rate {summary['win_rate']:.2f} < {gates['min_win_rate']}"
        )
    if "min_median_score" in gates and summary["median_my_score"] < gates["min_median_score"]:
        failures.append(
            f"median_score {summary['median_my_score']:.1f} < {gates['min_median_score']}"
        )
    if "max_crash_rate" in gates and summary["crash_rate"] > gates["max_crash_rate"]:
        failures.append(
            f"crash_rate {summary['crash_rate']:.2f} > {gates['max_crash_rate']}"
        )
    return failures


def print_summary_table(by_opp: dict[str, dict]) -> None:
    print("\n=== Evaluation summary ===")
    for opp, summary in by_opp.items():
        print(
            f"  {opp:8}  games={summary['games']}  "
            f"win_rate={summary.get('win_rate', 0):.0%}  "
            f"median_score={summary.get('median_my_score', 0):.0f}  "
            f"crash_rate={summary.get('crash_rate', 0):.0%}  "
            f"avg_spawn={summary.get('mean_spawns', 0):.1f}  "
            f"avg_cap={summary.get('mean_captures', 0):.1f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate bot against scoring.yaml gates")
    parser.add_argument("-c", "--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--opponent", action="append", help="Override: only this opponent id")
    parser.add_argument("--games", type=int, help="Override games per opponent")
    parser.add_argument("--dry-run", action="store_true", help="Print plan only")
    args = parser.parse_args()

    cfg = load_config(args.config)
    challenge = cfg["challenge"]
    bot_path = ROOT / cfg["bot"]
    language = cfg["language"]
    results_dir = ROOT / cfg.get("results_dir", "results")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    jsonl_path = results_dir / "runs.jsonl"

    opponents_cfg = cfg.get("opponents", [])
    if args.opponent:
        opponents_cfg = [o for o in opponents_cfg if o["id"] in args.opponent]
        if not opponents_cfg:
            print("No matching opponents in config", file=sys.stderr)
            return 2

    plan = []
    for opp in opponents_cfg:
        n = args.games if args.games is not None else opp.get("games", 3)
        plan.append((opp["id"], n, opp.get("gates", {})))

    if args.dry_run:
        print("Would run:", plan)
        return 0

    lim = limits(challenge)
    print("Test-game limits:", lim.get("test_games", lim))

    all_failures: list[str] = []
    by_opp_summary: dict[str, dict] = {}

    for opp_id, n_games, gates in plan:
        print(f"\n--- {opp_id} x{n_games} ---")
        games: list[GameMetrics] = []
        for i in range(n_games):
            print(f"  game {i + 1}/{n_games}...", flush=True)
            try:
                m = run_test_game(challenge, bot_path, language, opp_id)
            except SystemExit as e:
                print(f"  ERROR: {e}", file=sys.stderr)
                all_failures.append(f"{opp_id} game {i + 1}: {e}")
                time.sleep(2)
                continue
            games.append(m)
            print(
                f"    {'WIN' if m.win else 'LOSS'}  score {m.my_score} vs {m.opp_score}  "
                f"spawn={m.spawns} cap={m.captures} err={m.move_errors}"
                + (f"  seed={m.seed}" if m.seed else "")
            )
            replay_cmd = (
                f"./cg replay --game-id {m.game_id} --ide"
                if m.game_id
                else (
                    f"./cg replay --seed {m.seed} --opponent {opp_id} --ide"
                    if m.seed is not None
                    else None
                )
            )
            append_jsonl(
                jsonl_path,
                {
                    "run_id": run_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "git": git_short_hash(ROOT),
                    "challenge": challenge,
                    "bot": str(bot_path.relative_to(ROOT)),
                    "weakness_score": m.weakness_score(),
                    "tags": m.weakness_tags(),
                    "ide_url": ide_url(challenge),
                    "replay_cmd": replay_cmd,
                    **asdict(m),
                },
            )
            time.sleep(1)

        summary = summarize(games)
        by_opp_summary[opp_id] = summary
        failures = check_gates(summary, gates)
        for f in failures:
            all_failures.append(f"{opp_id}: {f}")

    print_summary_table(by_opp_summary)

    summary_path = results_dir / f"summary-{run_id}.json"
    summary_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "git": git_short_hash(ROOT),
                "by_opponent": by_opp_summary,
                "failures": all_failures,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nLog: {jsonl_path}")
    print(f"Summary: {summary_path}")

    if all_failures:
        print("\nGATES FAILED:")
        for f in all_failures:
            print(f"  - {f}")
        return 1

    print("\nAll gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
