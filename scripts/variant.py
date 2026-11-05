#!/usr/bin/env python3
"""Make a bot variant with overridden params: python3 scripts/variant.py experiments/v.py '{"FW": 0.5}' [base.py]"""
import json
import sys
from pathlib import Path

out, over = sys.argv[1], json.loads(sys.argv[2])
base = Path(sys.argv[3] if len(sys.argv) > 3 else Path(__file__).resolve().parents[1] / "bot.py").read_text()
marker = "\n\ndef ints():"
assert marker in base
Path(out).parent.mkdir(parents=True, exist_ok=True)
Path(out).write_text(base.replace(marker, f"\nP.update({over!r})\n{marker}", 1))
