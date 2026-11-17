"""Resume the fixed pilot after one observed annotation process terminates.

Waits on the actual process identity, then verifies complete settled cohort
evidence. Missing/failed annotations never cause an automatic teacher restart.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

from legal_skill_guard.rr.checkpoint import immutable_json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/two_method_followthrough_20261116'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--annotation-pid', type=int, required=True)
    args = parser.parse_args()
    if args.annotation_pid <= 1:
        parser.error('An observed actual annotation process PID is required')
    first = True
    while True:
        path = Path('/proc') / str(args.annotation_pid) / 'cmdline'
        try:
            command = path.read_bytes().split(b'\0')
        except FileNotFoundError:
            break
        if b'experiments.two_method_annotate' not in command:
            if first:
                raise RuntimeError('The supplied process is not the observed annotation worker')
            break
        first = False
        if (BASE / 'pilot_reads_v3/HOLD_GENERATION').exists():
            print(json.dumps({'event': 'held_before_pilot_start'}), flush=True)
            return
        time.sleep(5)
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        pending = db.execute("select id from calls where status='reserved'").fetchall()
        calls = db.execute("select status,count(*) from calls where id like 'two_method_annotation_v1_20261116:%' group by status").fetchall()
    checks = [json.loads(p.read_text()) for p in (BASE / 'annotation_v1/proposed_references').glob('*/source_checks.json')]
    lock = json.loads((BASE / 'pilot_lock.json').read_text())
    if pending or {c['source'] for c in checks} != {r['key'] for r in lock['rows']}:
        raise RuntimeError('Annotation work is not fully settled for the fixed cohort; do not restart or overlap jobs')
    if (BASE / 'pilot_reads_v3/HOLD_GENERATION').exists():
        print(json.dumps({'event': 'held_before_pilot_start'}), flush=True)
        return
    from experiments.two_method_pilot_reads import prepare
    protocol, pilot, sources, train = prepare()
    for name, expected in protocol['source_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Frozen pilot sources changed before scheduled dispatch')
    receipt = {'time_utc': datetime.now(timezone.utc).isoformat(),
        'annotation_pid_observed_terminal': args.annotation_pid, 'annotation_counts': calls,
        'cohort_sources': len(checks), 'reserved': 0,
        'source_proposals_not_automatically_gold': True,
        'pilot_protocol_sha256': hashlib.sha256((BASE / 'pilot_reads_v3/protocol.json').read_bytes()).hexdigest(),
        'command': [sys.executable, '-m', 'experiments.two_method_pilot_reads'],
        'no_teacher_restart': True}
    immutable_json(BASE / 'pilot_reads_v3/annotation_to_pilot_boundary.json', receipt)
    print(json.dumps({'event': 'annotation_finished_starting_locked_pilot', 'sources': len(checks)}), flush=True)
    outcome = subprocess.run(receipt['command'], cwd=ROOT, check=False)
    print(json.dumps({'event': 'locked_pilot_process_terminal', 'returncode': outcome.returncode}), flush=True)
    raise SystemExit(outcome.returncode)


if __name__ == '__main__':
    main()
