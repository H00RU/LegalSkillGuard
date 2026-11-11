"""Publishable TRAIN-only evidence and physical costs; no evaluation dispatch."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from .formal_cost_footprints import usage, used_physical_ids

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = Path('/home/yndx/hhy/legal-skill-redesign-20261109')
FOLDER = ROOT / 'artifacts/legal_skill_evolution_activation_repair_20261112'
REPORT = ROOT / 'reports/legal_skill_evolution_run_20261111'


def read(path):return json.loads(path.read_text())


def main():
    original = read(FOLDER / 'completed.json')
    replay = read(FOLDER / 'body_adapter_replay/completed.json')
    with sqlite3.connect('file:' + str(ORIGINAL / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        ledger = {i: {'id': i, 'role': role, 'status': status, 'result': json.loads(raw) if raw else {}}
                  for i, role, status, raw in db.execute('select id,role,status,result from calls')}
    prefix = ('legal_skill_evolution_activation_repair_20261112:',
              'legal_skill_evolution_activation_body_adapter_20261112:')
    actual = [r for i, r in ledger.items() if i.startswith(prefix)]
    if any(r['status'] != 'completed' for r in actual):raise ValueError('Unsettled or failed diagnostic request')
    if sum(r['role'] == 'teacher' for r in actual) != 3:raise ValueError('Unexpected teacher dispatch count')
    evidence, entries = REPORT / 'activation_evidence', []
    teacher_ids = {r['result']['request_sha256']: i for i, r in ledger.items()
                   if r['role'] == 'teacher' and r['result'].get('request_sha256')}
    for path in sorted(FOLDER.rglob('*.json')):
        relative = path.relative_to(FOLDER)
        if 'teacher_adapter_cache' in relative.parts or relative.name == 'original_boundary_hold.json':continue
        body = path.read_bytes()
        omitted = []
        if relative.name == 'wire_request.json':
            content = json.loads(body);content.pop('endpoint', None);omitted = ['endpoint']
            body = (json.dumps(content, ensure_ascii=False, indent=2) + '\n').encode()
        destination = evidence / relative;destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        entries.append({'path': str(destination.relative_to(REPORT)), 'sha256': hashlib.sha256(body).hexdigest(),
            'original_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'private_fields_omitted': omitted})
    cohort = set(read(FOLDER / 'protocol.json')['independent_acquisition']['sources'])
    cohort.update(read(FOLDER / 'protocol.json')['lift'][k] for k in ('trigger', 'history'))
    public = read(ORIGINAL / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
    grading = read(ORIGINAL / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    source_path = evidence / 'original_TRAIN_sources.json'
    source_path.write_text(json.dumps({
        'public': [r for r in public if r['key'] in cohort],
        'grading': {k: grading[k] for k in sorted(cohort)}, 'new_sources': 0,
        'already_seen_TRAIN_not_held_out': True}, ensure_ascii=False, indent=2) + '\n')
    old_path = evidence / 'original_Full_B4.json'
    old_path.write_bytes((ORIGINAL / 'artifacts/legal_skill_evolution_20261111/formal_v5/Full/B4.json').read_bytes())
    for path in (source_path, old_path):
        entries.append({'path': str(path.relative_to(REPORT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    arms = {}
    for arm, final in replay['arms'].items():
        folder = FOLDER / 'body_adapter_replay' / arm
        response = read(folder / 'teacher_B1.json')
        consumed = {teacher_ids[response['request_sha256']]}
        for path in folder.rglob('*.json'):
            consumed.update(used_physical_ids(read(path), ledger))
        consumed.update(used_physical_ids(final['parents'], ledger))
        uses = [{'source': parent['source'], 'view': view['view'], 'event': event}
                for parent in final['parents'] for view in parent['views']
                for event in view['execution'].get('events', []) if event.get('kind') == 'USE']
        arms[arm] = {'skill_count': final['skill_count'], 'dependency_ports': final['dependency_ports'],
            'pattern_count': final['pattern_count'], 'actual_USE_events': uses,
            'source_results': [{'source': p['source'], 'native_grade': p['native_grade'],
                'core_correct': p['native_core_correct'], 'fallback_views': p['native_fallback_views']}
                for p in final['parents']],
            'consumed_response_ids': sorted(consumed), 'consumed_footprint': usage([ledger[i] for i in consumed]),
            'cost_interpretation': 'Includes the one original independent teacher and all used physical responses, including exact prior cache. Do not add arm footprints into physical spending.'}
    summary = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
        'offline_regression_tests_passed': 64, 'test_used_for_repair': False,
        'original_formal_results_replaced': False, 'teacher_calls': 3,
        'physical_accounting': usage(actual), 'actual_physical_requests': [
            {'id': r['id'], 'role': r['role'], 'status': r['status']} for r in actual],
        'independent_acquisition': arms, 'Lift_selected_mask': original['lift']['selected_mask'],
        'source_semantic_review': {
            'SARA_v2_Binary:cc82ab0fe40ca06245a9fdd00273c97ae8d8c2af9783b5618826de0125d41397': {
                'native_query': 'section 151(c)', 'Full': 'Native answer correct, but terminal §152(b)(1) helper is out of scope; reader returned claim_is_affirmative=True from a §151(c) question. Excluded from valid mechanism evidence.',
                'FreeEvolution': 'Reader marks the absent §152(b)(1) claim unknown; direct fallback correct, not core evidence.'},
            'SARA_v2_Binary:a51930fd174465a9bc8bd24887336e753d1f76990c346645a1ae5cd8c074536d': {
                'native_query': 'section 152(b)(1)', 'both_arms': 'Real §152(a) producer -> §152(b)(1) consumer; typed factual inputs, source-anchored rules, actual USE and correct native answer. Genuine acquired rule dependency, not co-revision.'},
            'scores_preserved': True, 'valid_core_semantic_sources_per_arm': 1,
            'scope_validation_gap_resolved': False},
        'Lift_read_token_delta': original['lift']['read_tokens']['1'] - original['lift']['read_tokens']['0'],
        'conclusion': {'implementation_gaps_fixed': ['Small deterministic Lift operation and host scheduling',
            'Separate legal parameters, given intermediates and computed legal predicates during common acquisition',
            'Semantics-preserving complete function-body wrapper, applied equally to both arms'],
            'Lift_benefit_supported': False, 'CoRev_benefit_supported': False,
            'dependency_acquisition_supported': True,
            'dedicated_corevision_increment': 'Not shown: both independent arms acquired a real dependency; creation is not old-skill co-revision.',
            'next_decision': 'No further model probes on this repair. Finish preserved original matrix independently; assess whether fixed data contains a natural old-skill joint-revision witness before authorizing another research iteration.'},
        'cash': {'local_executor_incremental_api_usd': sum(r['result']['incremental_api_cash_usd']
            for r in actual if r['role'] == 'executor'), 'teacher_invoice_usd': None, 'GPU_cost_usd': None,
            'note': 'Unavailable invoices are not zero cost.'}, 'evidence_files': entries}
    (REPORT / 'activation_repair_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'physical': summary['physical_accounting'], 'scores': {
        a: [r['native_grade'] for r in x['source_results']] for a, x in arms.items()},
        'evidence_files': len(entries), 'goal_complete': False}))


if __name__ == '__main__':main()
