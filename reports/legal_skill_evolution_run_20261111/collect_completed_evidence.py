"""Copy settled evidence; frozen TEST outputs only after its complete matrix.

Never copy sealed preparation packets, the ledger DB, or machine PID records.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent


def main():
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        settled_folders = {digest(r[0]) for r in db.execute("select id from calls where status in ('completed','failed')")}
    sources = []
    versions = ['pilot_v11', 'repair_v12', 'repair_v13', 'formal_v1', 'formal_v2', 'formal_v3', 'formal_v4', 'formal_v5']
    frozen = ROOT / 'artifacts/legal_skill_evolution_20261111/frozen_test_v1'
    if (frozen / 'TEST_completed.json').exists():
        versions.append('frozen_test_v1')
    for version in versions:
        folder = ROOT / 'artifacts/legal_skill_evolution_20261111' / version
        for name in ('execution_manifest.json', 'preflight.json', 'repair_queue.json', 'completed.json',
                     'state_import.json', 'resumption_preflight.json', 'training_DEV_completed.json'):
            if (folder / name).exists():sources.append((folder, folder / name))
        patterns = ('teacher_prefetch_B*.json', '*/initial_B*.json', '*/update_B*.json', '*/teacher_B*.json', '*/B[0-8].json',
                    '*/B*_candidates/*.json', '*/B*_c*.json', 'source_snapshot/**/*.py', 'dev/*/B*.json')
        if version == 'frozen_test_v1':
            patterns += ('freeze_manifest.json', 'native_materialization.json', 'preflight.json',
                'TEST_completed.json', '*_native_summary.json', 'primary_four_contrasts.json',
                'Full_accepted_lineage.json', 'registered_transfer_masks.json', 'libraries/*.json',
                'predictions/*/*.json')
            if (folder / 'transfer/completed.json').exists():
                patterns += ('transfer/*.json', 'predictions/Full_foreign_off/*/*.json')
        for pattern in patterns:sources.extend((folder, p) for p in folder.glob(pattern))
        for request in (folder / 'calls').glob('*/request.json'):
            if request.parent.name not in settled_folders:continue
            if not any((request.parent / n).exists() for n in ('result.json', 'failure.json')):continue
            for name in ('request.json', 'wire_request.json', 'wire_response.json', 'result.json', 'failure.json'):
                path = request.parent / name
                if path.exists():sources.append((folder, path))
    receipt = []
    for folder, path in sorted(set(sources)):
        relative = path.relative_to(folder)
        target = REPORT / 'evidence' / folder.name / relative
        body = path.read_bytes()
        if target.exists() and target.read_bytes() != body:raise ValueError('Settled evidence changed: ' + str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        receipt.append({'original_path': str(path.relative_to(ROOT)), 'public_path': str(target.relative_to(ROOT)),
            'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(), 'byte_identical': True})
    (REPORT / 'settled_evidence_manifest.json').write_text(json.dumps({
        'captured_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'scope': 'settled original TRAIN pilot, fixed repair queue, formal TRAIN and readonly DEV; completed frozen TEST outputs and completed registered transfer if available; no sealed preparation packets, SQLite or machine-operation records copied',
        'files': receipt}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'copied_files': len(receipt), 'bytes': sum(r['bytes'] for r in receipt)}))


if __name__ == '__main__':main()
