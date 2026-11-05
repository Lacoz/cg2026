#!/usr/bin/env python3
"""Append our current CodinGame ranking to ranking.csv and print the last rows.

Usage: python3 scripts/rank_log.py [note...]
`percentage` < 100 means the ranking games of the submission are still running (rank not final).
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cg_lib import RANKING_CSV, log_rank  # noqa: E402


def main() -> int:
    cfg = yaml.safe_load((ROOT / "scoring.yaml").open(encoding="utf-8"))
    log_rank(cfg["challenge"], " ".join(sys.argv[1:]))
    lines = RANKING_CSV.read_text(encoding="utf-8").splitlines()
    print("\n".join(lines[:1] + lines[1:][-10:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
