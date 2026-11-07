"""Read-only source/response diagnosis for the one current fixed20 comparison."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.source_inference import _decode
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.source_validation import validation_feedback


def main():
    root = Path(__file__).resolve().parents[2]
    stage = root / 'artifacts/rr_method_runtime_20261107/method_runtime_c1_20261107'
    sources = {s['key']: s for s in json.loads(
        (root / 'data/packets/rr_v2/public_train.json').read_text())['sources']}
    findings = []
    stats = defaultdict(Counter)
    for path in sorted((stage / 'thinking/records').glob('*.json')):
        record = json.loads(path.read_text())
        source = sources[record['source']]
        mode = str(record['thinking']).lower()
        stats[mode]['complete_profiles'] += 1
        stats[mode]['structural_pass'] += bool(record['structural_pass'])
        stats[mode]['TRAIN_correct'] += bool(record['task_correct'])
        stats[mode]['elapsed_seconds'] += record['elapsed_seconds']
        if record['usage']:
            stats[mode].update(record['usage'])
        attempts = []
        for call in record['prediction']['calls']:
            raw = call['raw_content']
            attempt = {'step': call['step'], 'request_hash': call['request_hash'],
                       'usage': call['usage'], 'elapsed_seconds': call['elapsed_seconds'],
                       'recorded_analysis': call['analysis'],
                       'raw_content_sha256': hashlib.sha256(raw.encode()).hexdigest() if raw else None}
            try:
                program = _decode(raw)
                attempt['source_only_feedback'] = validation_feedback(source, program)
                try:
                    compile_source(source, program, library={'frozen': False, 'patterns': []})
                    attempt['offline_compile'] = 'accepted'
                except Exception as exc:
                    attempt['offline_compile'] = 'rejected'
                    attempt['offline_error'] = {'type': type(exc).__name__, 'message': str(exc)}
            except Exception as exc:
                attempt['decode_or_feedback_error'] = {'type': type(exc).__name__, 'message': str(exc)}
            attempts.append(attempt)
        findings.append({'source': source['key'], 'dataset': source['dataset'],
                         'thinking': record['thinking'], 'record': str(path.relative_to(root)),
                         'final_status': record['prediction']['result']['program_status'],
                         'TRAIN_correct': record['task_correct'], 'attempts': attempts})
    with sqlite3.connect('file:' + str(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        counts = dict(db.execute('select role,count(*) from calls group by role'))
        pending = db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    result = {'checked_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'completed current comparison profiles only; source-only offline diagnosis; no new labels or generation',
              'comparison_complete': len(findings) == 40, 'expected_profiles': 40,
              'completed_profiles': len(findings), 'stats': dict(stats), 'findings': findings,
              'ledger_counts': counts, 'pending': pending, 'new_model_calls_by_audit': 0,
              'semantic_acceptance': 'IR validity or TRAIN label match alone does not prove translation faithfulness',
              'full_goal_complete': False}
    out = root / 'reports/rr_method_runtime_20261107/current_thinking_response_audit.json'
    out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'findings'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
