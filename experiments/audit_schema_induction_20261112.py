"""Zero-call accounting and source-grounding trace for the fixed candidate test."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.skill_evolution.native import source_spans


def audit(root):
    folder = root / 'artifacts/legal_skill_evolution_schema_induction_20261112'
    protocol = json.loads((folder / 'protocol.json').read_text())
    repaired = root / 'artifacts/legal_skill_evolution_schema_wire_recovery_20261112'
    result = json.loads(((repaired if (repaired / 'completed.json').exists() else folder) / 'completed.json').read_text())
    public = {s['key']: s for s in json.loads((root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json').read_text())}
    with sqlite3.connect('file:' + str(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        rows = [dict(zip(('id', 'role', 'purpose', 'source', 'status', 'reserved_at', 'result'), row))
                for row in db.execute('select id,role,purpose,source,status,reserved_at,result from calls where id like ? or id like ? order by reserved_at', (protocol['run_id'] + ':%', 'legal_skill_evolution_schema_wire_recovery_20261112:%'))]
        cumulative = {role: n for role, n in db.execute('select role,count(*) from calls group by role')}
        pending = db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    accounting, requests = {}, []
    for role in ('executor', 'teacher'):
        calls = [r for r in rows if r['role'] == role]
        totals = Counter()
        for row in calls:
            body = json.loads(row['result']) if row['result'] else {}
            usage = (body.get('usage') or {}) if role == 'executor' else body.get('invocation', {}).get('usage', {})
            totals.update({k: v for k, v in usage.items() if isinstance(v, (int, float))})
            requests.append({k: v for k, v in row.items() if k != 'result'} | {
                'usage': usage, 'elapsed_seconds': body.get('elapsed_seconds'),
                'finish_reason': body.get('finish_reason'), 'thinking_requested': body.get('thinking_requested'),
                'billing_basis': body.get('billing_basis'), 'error': body.get('error')})
        accounting[role] = {'physical_requests': len(calls), 'status': dict(Counter(r['status'] for r in calls)),
            'usage': dict(totals), 'summed_request_seconds': sum((json.loads(r['result']).get('elapsed_seconds', 0) if r['result'] else 0) for r in calls),
            'incremental_API_cash_usd': 0 if role == 'executor' else None,
            'total_cash_usd': None, 'cash_note': 'Existing local service / authorized CLI; no per-request teacher invoice or GPU cash allocation. Unknown is not zero.'}
    summaries, traces = {}, []
    for arm, calibration in result['calibration'].items():
        items = list(calibration.values()) + result['frozen_TRAIN_probes'][arm]
        summaries[arm] = {'parents': len(items), 'native_views': sum(len(s['views']) for s in items),
            'core_executed': sum(v['core_executed'] for s in items for v in s['views']),
            'core_native_correct': sum(s['native_core_correct'] for s in items),
            'fallback_views': sum(s['native_fallback_views'] for s in items),
            'calibration_mean': sum(s['native_grade'] for s in calibration.values()) / len(calibration),
            'probe_mean': sum(s['native_grade'] for s in result['frozen_TRAIN_probes'][arm]) / len(result['frozen_TRAIN_probes'][arm]),
            'accepted_by_numeric_gate': result['updates'][arm]['accepted'],
            'semantic_review_required_before_contribution_credit': True}
        for item in items:
            source = public[item['source']]
            material = source['views'][0]['public']
            spans = source_spans({'source_text': material['source_text'], 'sentence_spans': material['sentence_spans']})
            event = next((v['source_event'] for v in item['views'] if v['source_event']), {})
            traces.append({'arm': arm, 'source': item['source'], 'native_grade': item['native_grade'],
                'views': [{k: v.get(k) for k in ('view', 'answer', 'score', 'core_executed', 'fallback', 'error')} for v in item['views']],
                'source_fields': {name: {**value, 'support_texts': [spans[i]['text'] for i in value['support_ids']]}
                                  for name, value in event.get('fields', {}).items()},
                'unresolved_fields': event.get('unresolved_fields', [])})
    checks = []
    for name, sha in protocol['code_sha256'].items():
        target = folder / 'source_snapshot' / name
        if not target.exists():target = root / name
        checks.append({'path': name, 'preserved_location': str(target.relative_to(root)),
            'unchanged': hashlib.sha256(target.read_bytes()).hexdigest() == sha})
    original = root / 'artifacts/legal_skill_evolution_20261111'
    fixed = root / 'history/fixed_study_20261111'
    frozen_checks = []
    for path in (original / 'formal_v5/execution_manifest.json', original / 'frozen_test_v1/freeze_manifest.json'):
        manifest = json.loads(path.read_text())
        for section in ('code', 'data'):
            for name, sha in manifest[section].items():
                target = (root if name.startswith('artifacts/') else fixed) / name
                frozen_checks.append({'manifest': path.name, 'path': name,
                    'unchanged': target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == sha})
    evidence = {'new_requests': accounting, 'cumulative': cumulative, 'pending': pending,
        'summaries': summaries, 'actual_requests': requests, 'bound_code': checks,
        'original_frozen_files': frozen_checks, 'no_new_model_calls_by_audit': True,
        'goal_complete': False}
    (folder / 'cost_and_integrity.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    (folder / 'source_semantic_review_material.json').write_text(json.dumps(traces, ensure_ascii=False, indent=2) + '\n')
    return evidence


if __name__ == '__main__':
    x = audit(Path(__file__).resolve().parents[1])
    print(json.dumps({k: x[k] for k in ('new_requests', 'cumulative', 'pending', 'summaries')}, ensure_ascii=False))
