"""Preserve the completed repair prefix after a cache-only performance change."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parents[2]


def main():
    root = ROOT / 'artifacts/legal_skill_evolution_20261111'
    old, new = root / 'repair_v12', root / 'repair_v13'
    with sqlite3.connect(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        physical = db.execute('select role,status,count(*) from calls group by role,status').fetchall()
    load = lambda p: json.loads(p.read_text())
    assert load(old / 'repair_queue.json')['queue'] == load(new / 'repair_queue.json')['queue']
    assert load(old / 'repair_queue.json')['groups'] == load(new / 'repair_queue.json')['groups']
    assert load(ROOT / 'reports/legal_skill_evolution_run_20261111/actual_method_opportunity_audit.json')['arms']['Full']['operation_counts'].get('lift', 0) == 0
    copied = []
    paths = list(old.glob('*/B*_c*.json')) + list((old / 'view_results').glob('*.json'))
    for path in paths:
        target = new / path.relative_to(old)
        body = path.read_bytes()
        if target.exists():assert target.read_bytes() == body
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        copied.append({'from': str(path.relative_to(ROOT)), 'to': str(target.relative_to(ROOT)),
                       'sha256': hashlib.sha256(body).hexdigest()})
    with sqlite3.connect(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        assert db.execute('select role,status,count(*) from calls group by role,status').fetchall() == physical
    receipt = {'new_model_calls': 0, 'source_queue_and_revisions_identical': True,
        'complete_candidates_copied': len(list(old.glob('*/B*_c*.json'))),
        'view_results_copied': len(list((old / 'view_results').glob('*.json'))),
        'partial_candidate_views_preserved': True, 'ledger_counts_unchanged': physical,
        'behavior_change': 'index original physical requests once; still compare literal wire and earliest settled ledger entry',
        'local_record_candidate_addition_does_not_change_original_proposals': 'no original lift operation; helper programs and read payloads unchanged',
        'copied_files': copied}
    target = new / 'state_import.json'
    if target.exists():assert load(target) == receipt
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    (Path(__file__).with_name('indexed_repair_state_import.json')).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ('new_model_calls', 'complete_candidates_copied', 'view_results_copied', 'source_queue_and_revisions_identical')}))


if __name__ == '__main__':main()
