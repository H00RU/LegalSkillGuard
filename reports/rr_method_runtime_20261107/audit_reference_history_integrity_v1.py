"""Recheck preserved unsuccessful runs and settled physical ledger rows."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
REPORTS = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger-baseline', type=Path, required=True)
    args = parser.parse_args()
    cases = [
        ('reference_ast_controller_cutover_preservation_v1.json', 'old_run_id', 'all_preserved_file_hashes'),
        ('reference_uniform_v5_boundary_hold_v1.json', 'run_id', 'files'),
        ('reference_uniform_v6_boundary_hold_v1.json', 'run_id', 'files'),
        ('reference_uniform_v7_cache_boundary_hold_v1.json', 'run_id', 'files'),
        ('reference_uniform_v8_completed_cutover_preservation_v25.json', 'preserved_run_id', 'preserved_run_files'),
        ('reference_v9_sparse_execution_boundary_preservation_v26.json', 'run_id', 'critical_files'),
    ]
    rows = []
    for name, id_key, hashes_key in cases:
        path = REPORTS / name
        proof = json.loads(path.read_text())
        stage = ROOT / 'artifacts/rr_method_runtime_20261107' / proof[id_key]
        for relative, expected in proof[hashes_key].items():
            assert hashlib.sha256((stage / relative).read_bytes()).hexdigest() == expected, (proof[id_key], relative)
        rows.append({'run_id': proof[id_key], 'all_preserved_bytes_unchanged': True,
            'files_checked': len(proof[hashes_key]), 'preservation_receipt': str(path.relative_to(ROOT)),
            'preservation_receipt_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    with sqlite3.connect('file:' + str(args.ledger_baseline.resolve()) + '?mode=ro', uri=True) as db:
        old = {table: db.execute('select * from ' + table).fetchall() for table in ('calls', 'meta', 'oracle_views')}
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
    with sqlite3.connect('file:' + str((ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3').resolve()) + '?mode=ro', uri=True) as db:
        db.execute('begin')
        for table, records in old.items():
            assert set(records) <= set(db.execute('select * from ' + table).fetchall()), table
        counts = dict(db.execute('select role,count(*) from calls group by role'))
        pending = db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    value = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'preserved_runs': rows,
        'settled_baseline_rows_identical': {table: len(records) for table, records in old.items()},
        'settled_baseline_sqlite_sha256': hashlib.sha256(args.ledger_baseline.read_bytes()).hexdigest(),
        'cumulative_counts': counts, 'pending_at_snapshot': pending, 'ledger_reset': False,
        'new_model_or_oracle_calls': 0, 'DEV_or_TEST_labels_opened': False}
    (REPORTS / 'reference_history_integrity_final_current.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(value, ensure_ascii=False))


if __name__ == '__main__':
    main()
