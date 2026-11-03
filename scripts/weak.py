#!/usr/bin/env python3
"""List weak games (by seed / game_id) for debugging — links to ./cg replay."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cg_lib import (  # noqa: E402
    GameMetrics,
    fetch_arena_losses,
    fetch_game_log,
    ide_url,
    load_runs_jsonl,
    parse_log,
)


def row_to_metrics(row: dict) -> GameMetrics:
    return GameMetrics(
        opponent=row.get("opponent", "?"),
        game_id=row.get("game_id"),
        seed=row.get("seed"),
        game_options=row.get("game_options"),
        win=row.get("win", False),
        my_score=row.get("my_score", -1),
        opp_score=row.get("opp_score", -1),
        ranking=row.get("ranking", []),
        spawns=row.get("spawns", 0),
        captures=row.get("captures", 0),
        move_errors=row.get("move_errors", 0),
        timeout=row.get("timeout", False),
        eliminated=row.get("eliminated", False),
        raw_scores=row.get("raw_scores", ""),
    )


def enrich_arena(challenge: str, arena_rows: list[dict], limit: int) -> list[dict]:
    out: list[dict] = []
    for b in arena_rows[:limit]:
        gid = b.get("game_id")
        if not gid:
            continue
        try:
            log = fetch_game_log(gid)
        except SystemExit:
            continue
        if not log:
            continue
        m = parse_log(log, opponent=str(b.get("opponent", "arena")), game_id=gid)
        rec = asdict(m)
        rec["source"] = "arena"
        rec["ended_at"] = b.get("ended_at")
        rec["weakness_score"] = m.weakness_score()
        rec["tags"] = m.weakness_tags()
        rec["ide_url"] = ide_url(challenge)
        rec["replay_cmd"] = f"./cg replay --game-id {gid} --ide"
        out.append(rec)
    return out


def build_index(rows: list[dict], challenge: str) -> list[dict]:
    indexed: list[dict] = []
    for i, row in enumerate(rows):
        m = row_to_metrics(row)
        rec = dict(row)
        rec["run_index"] = i
        rec["weakness_score"] = rec.get("weakness_score", m.weakness_score())
        rec["tags"] = rec.get("tags", m.weakness_tags())
        rec["ide_url"] = ide_url(challenge)
        if m.game_id:
            rec["replay_cmd"] = rec.get(
                "replay_cmd", f"./cg replay --game-id {m.game_id} --ide"
            )
        elif m.seed is not None:
            rec["replay_cmd"] = rec.get(
                "replay_cmd", f"./cg replay --seed {m.seed} --opponent {m.opponent} --ide"
            )
        else:
            rec["replay_cmd"] = "./cg replay --from-run N --ide"
        indexed.append(rec)
    indexed.sort(key=lambda r: -float(r.get("weakness_score", 0)))
    return indexed


def write_markdown(path: Path, items: list[dict], challenge: str) -> None:
    lines = [
        "# Slabé hry (seed / replay)",
        "",
        f"IDE: {ide_url(challenge)}",
        "",
        "| # | seed | game_id | opp | score | tags | replay |",
        "|---|------|---------|-----|-------|------|--------|",
    ]
    for i, r in enumerate(items[:50]):
        seed = r.get("seed", "")
        gid = r.get("game_id", "")
        opp = r.get("opponent", "")
        score = f"{r.get('my_score', '?')} vs {r.get('opp_score', '?')}"
        tags = ", ".join(r.get("tags", [])[:4])
        cmd = r.get("replay_cmd", "")
        lines.append(f"| {i} | {seed} | {gid} | {opp} | {score} | {tags} | `{cmd}` |")
    lines.append("")
    lines.append("Otvor IDE, potom spusti príkaz v stĺpci replay.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=Path, default=ROOT / "scoring.yaml")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--arena", action="store_true", help="Include recent arena losses")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include wins (default: only losses / weak games)",
    )
    parser.add_argument("--export", type=Path, help="Write weak_index.json")
    parser.add_argument("--md", type=Path, help="Write markdown table")
    args = parser.parse_args()

    with args.config.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    challenge = cfg["challenge"]
    runs_path = ROOT / cfg.get("results_dir", "results") / "runs.jsonl"

    rows = load_runs_jsonl(runs_path)
    if args.arena:
        arena = enrich_arena(challenge, fetch_arena_losses(challenge, limit=30), limit=15)
        rows = rows + arena

    if not args.all:
        rows = [r for r in rows if not r.get("win", False)]

    items = build_index(rows, challenge)[: args.top]

    if not items:
        print("Žiadne záznamy. Spusti najprv ./cg test", file=sys.stderr)
        return 1

    print(f"{'#':>3}  {'seed':>22}  {'game_id':>10}  {'opp':>8}  score        tags")
    print("-" * 90)
    for i, r in enumerate(items):
        print(
            f"{i:3}  {str(r.get('seed', '')):>22}  "
            f"{str(r.get('game_id', '')):>10}  "
            f"{str(r.get('opponent', '')):>8}  "
            f"{r.get('my_score', '?'):>4} vs {r.get('opp_score', '?'):<4}  "
            f"{','.join(r.get('tags', [])[:5])}"
        )
        print(f"      replay: {r.get('replay_cmd')}")

    print(f"\nIDE: {ide_url(challenge)}")

    out_dir = ROOT / cfg.get("results_dir", "results")
    export_path = args.export or out_dir / "weak_index.json"
    export_path.write_text(json.dumps(items, indent=2), encoding="utf-8")
    print(f"Index: {export_path}")

    md_path = args.md or out_dir / "WEAK.md"
    write_markdown(md_path, items, challenge)
    print(f"Markdown: {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
