#!/usr/bin/env python3
"""Submit bot only if evaluate.py gates pass (unless --force)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "scripts" / "evaluate.py"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=Path, default=ROOT / "scoring.yaml")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Submit even if gates fail",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Submit without running evaluate (not recommended)",
    )
    args = parser.parse_args()

    if not args.skip_tests:
        cmd = [sys.executable, str(EVAL), "-c", str(args.config)]
        print("Running evaluation before submit...")
        rc = subprocess.call(cmd)
        if rc != 0 and not args.force:
            print("Submit aborted (gates failed). Use --force to override.", file=sys.stderr)
            return 1

    sys.path.insert(0, str(ROOT / "scripts"))
    from cg_lib import api, token  # noqa: E402
    import yaml  # noqa: E402

    with args.config.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    challenge = cfg["challenge"]
    bot_path = ROOT / cfg["bot"]
    language = cfg["language"]
    code = bot_path.read_text()
    body = {"language": language, "code": code}
    resp = api("POST", f"/challenges/{challenge}/submissions", body=body)
    sid = resp.get("submission_id")
    print(f"Submitted {sid} to {challenge}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
