"""Explicit second-round commands; no formal experiment can be launched here."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from legal_skill_guard.rr.schema_validation import prepare, run

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run", "continue"])
    args = parser.parse_args()
    result = prepare(ROOT) if args.command == "prepare" else run(ROOT, continue_after_gate=args.command == "continue")
    print(json.dumps({k: v for k, v in result.items() if k not in {"ledger", "protected_files", "config"}}, indent=2))


if __name__ == "__main__":
    main()
