#!/usr/bin/env python3
"""Replay a test game by seed or game_id and push it to the CodinGame IDE viewer."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cg_lib import (  # noqa: E402
    fetch_game_log,
    ide_url,
    load_runs_jsonl,
    log_rank,
    parse_game_options,
    parse_log,
    run_test_game,
)


def load_cfg(config: Path) -> dict:
    with config.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_from_runs(
    runs_path: Path, *, seed: int | None, game_id: int | None, index: int | None
) -> dict | None:
    rows = load_runs_jsonl(runs_path)
    if not rows:
        return None
    if index is not None:
        if index < 0 or index >= len(rows):
            raise SystemExit(f"Index {index} out of range (0..{len(rows) - 1})")
        return rows[index]
    if game_id is not None:
        for r in reversed(rows):
            if r.get("game_id") == game_id:
                return r
        return None
    if seed is not None:
        for r in reversed(rows):
            if r.get("seed") == seed:
                return r
        return None
    return None


def print_ide_instructions(challenge: str, show_in_ide: bool) -> None:
    url = ide_url(challenge)
    print("\n=== CodinGame IDE ===")
    print(url)
    if show_in_ide:
        print(
            "\nOtvor IDE v prehliadači TERAZ (musí byť otvorené pred koncom hry, "
            "inak sa replay nezobrazí)."
        )
        print("Po doběhnutí testu: viewer + konzola v IDE, Play = rovnaké parametre "
              "ak bolo overwrite_ide_game_parameters.")
    else:
        print("\nTip: pridaj --ide na zobrazenie replay v IDE.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay online test by seed or game id")
    parser.add_argument("-c", "--config", type=Path, default=ROOT / "scoring.yaml")
    parser.add_argument("--seed", type=int, help="Map seed from log options:")
    parser.add_argument("--game-id", type=int, help="CodinGame game id (uses replay_game_id)")
    parser.add_argument(
        "--from-run",
        type=int,
        metavar="N",
        help="Row index in results/runs.jsonl (0=oldest)",
    )
    parser.add_argument("--opponent", default="boss", help="If not using replay_game_id")
    parser.add_argument(
        "--ide",
        action="store_true",
        help="show_in_ide + overwrite_ide_game_parameters",
    )
    parser.add_argument(
        "--sync-code",
        action="store_true",
        help="overwrite_ide_code (prepíše kód v IDE)",
    )
    parser.add_argument(
        "--open-only",
        action="store_true",
        help="Only print IDE URL and replay command, do not call API",
    )
    parser.add_argument(
        "--game-options",
        type=str,
        help="Raw game_options string (overrides --seed)",
    )
    parser.add_argument("--bot", type=Path, help="Bot file (default: bot from scoring.yaml)")
    args = parser.parse_args()

    cfg = load_cfg(args.config)
    challenge = cfg["challenge"]
    bot_path = args.bot.resolve() if args.bot else ROOT / cfg["bot"]
    language = cfg["language"]
    runs_path = ROOT / cfg.get("results_dir", "results") / "runs.jsonl"

    game_options = args.game_options
    replay_game_id = args.game_id
    opponent = args.opponent

    row = resolve_from_runs(
        runs_path,
        seed=args.seed,
        game_id=args.game_id,
        index=args.from_run,
    )
    if row:
        if game_options is None:
            game_options = row.get("game_options")
        if replay_game_id is None and row.get("game_id"):
            replay_game_id = row["game_id"]
        opponent = row.get("opponent", opponent)
        if args.seed is None and row.get("seed") is not None:
            args.seed = row["seed"]

    if replay_game_id is None and game_options is None and args.seed is not None:
        game_options = f"seed={args.seed}"

    if replay_game_id is None and game_options is None:
        raise SystemExit(
            "Potrebujem --seed, --game-id, --from-run, alebo --game-options. "
            "Pozri ./cg weak pre zoznam."
        )

    print_ide_instructions(challenge, args.ide)

    if args.open_only:
        print("\nPlánovaný replay:")
        if replay_game_id:
            print(f"  replay_game_id={replay_game_id}")
        else:
            print(f"  opponent={opponent}")
            print(f"  game_options={game_options!r}")
        print(f"\n  ./cg replay --game-id {replay_game_id or 'SEED'} --ide")
        return 0

    print("\nSpúšťam online test game...")
    if replay_game_id:
        print(f"  replay_game_id={replay_game_id}")
    else:
        print(f"  opponent={opponent}")
        print(f"  game_options (first line): {(game_options or '').splitlines()[0]}")

    m = run_test_game(
        challenge,
        bot_path,
        language,
        opponent,
        wait=30,
        game_options=game_options if replay_game_id is None else None,
        replay_game_id=replay_game_id,
        show_in_ide=args.ide,
        overwrite_ide_game_parameters=args.ide,
        overwrite_ide_code=args.sync_code,
        keep_seed=True,
    )
    row = log_rank(challenge, "replay", min_gap_minutes=30)
    if row:
        print(f"Rank zapísaný do ranking.csv: {row['league']} {row['league_rank']}/{row['league_total']} score {row['score']}")

    print(
        f"\nVýsledok: {'WIN' if m.win else 'LOSS'}  "
        f"score {m.my_score} vs {m.opp_score}  "
        f"game_id={m.game_id}  seed={m.seed}"
    )
    print(f"Tagy: {', '.join(m.weakness_tags())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
