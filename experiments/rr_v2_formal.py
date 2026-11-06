"""Future formal entry; current configuration permits dry-run only."""
import argparse
import json
from pathlib import Path

from legal_skill_guard.rr.formal import FormalRun, dry_run

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["dry-run", "train", "dev", "test", "B1-test", "native-empty", "diagnostics"])
    parser.add_argument("--public-packet", type=Path)
    parser.add_argument("--grading-packet", type=Path)
    args = parser.parse_args()
    if args.command == "dry-run":
        result = dry_run(ROOT)
    else:
        partition = "train" if args.command == "train" else "test" if args.command in {"B1-test", "native-empty", "diagnostics"} else args.command
        run = FormalRun(ROOT, partition=partition)
        if args.command == "diagnostics":
            if not args.public_packet or not args.grading_packet:
                parser.error("diagnostics requires committed public and grading packets")
            result = run.diagnostics(args.public_packet, args.grading_packet)
        else:
            result = run.train() if args.command == "train" else run.native_empty() if args.command == "native-empty" else run.evaluate("B1" if args.command == "B1-test" else "B8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
