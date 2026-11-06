"""Continue the authorized existing preflight; never launch training/evaluation."""
import argparse
import json
from pathlib import Path

from legal_skill_guard.rr.cumulative_repair import prepare, run_one


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['prepare', 'one'])
    p.add_argument('--revision', required=True)
    p.add_argument('--change')
    p.add_argument('--source-index', type=int)
    p.add_argument('--mode', choices=['validation', 'continuation'], default='validation')
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.action == 'prepare':
        if not args.change:
            p.error('--change is required')
        result = prepare(root, args.revision, args.change)
    else:
        if args.source_index is None or not 0 <= args.source_index < 20:
            p.error('--source-index must select the original fixed20')
        result = run_one(root, args.revision, args.source_index, mode=args.mode)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
