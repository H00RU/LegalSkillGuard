"""Summarize settled study artifacts and the continuous physical ledger."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from experiments.legal_skill_evolution import PROFILE

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def main():
    profile = read(PROFILE)
    folder = ROOT / profile['artifacts']
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        rows = db.execute('select id,role,purpose,status,reserved_at,result from calls').fetchall()
    total, goal, usage = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    pending, attempts = [], []
    for identity, role, purpose, status, at, raw in rows:
        total[role][status] += 1
        if status == 'reserved':
            pending.append({'id': identity, 'role': role, 'purpose': purpose, 'reserved_at': at})
        if not identity.startswith('legal_skill_evolution_'):
            continue
        goal[role][status] += 1
        result = json.loads(raw) if raw else {}
        tokens = result.get('usage') or result.get('invocation', {}).get('usage') or {}
        usage[role].update({k: v for k, v in tokens.items() if isinstance(v, (int, float))})
        usage[role]['elapsed_seconds_settled'] += result.get('elapsed_seconds', 0)
        attempts.append({'id': identity, 'role': role, 'purpose': purpose, 'status': status,
            'reserved_at': at, 'finish_reason': result.get('finish_reason'),
            'usage': tokens, 'elapsed_seconds': result.get('elapsed_seconds'),
            'error': result.get('error'), 'request_hash': result.get('request_hash') or result.get('request_sha256')})
    updates, candidate_validation = [], []
    for arm in profile['pilot_arms']:
        for path in sorted((folder / arm).glob('update_B*.json')):
            receipt = read(path)
            updates.append(receipt)
            candidate_folder = folder / arm / ('B' + str(receipt['batch']) + '_candidates')
            candidates = [(int(p.stem), read(p)) for p in sorted(candidate_folder.glob('*.json'))]
            if not candidates:
                library = read(folder / arm / ('B' + str(receipt['batch']) + '.json'))
                candidates = [(e['candidate_index'], e) for e in library['provisional_edits']
                              if e['batch'] == receipt['batch']]
            for candidate_index, candidate in candidates:
                cells = []
                for cell in candidate.get('table', {}).get('mixed_version_table', []):
                    views = (cell.get('trace') or {}).get('views', [])
                    for view in views:
                        if view['execution']['core_executed']:
                            cells.append({'mask': cell['mask'], 'source': cell['source'],
                                'view': view['view'], 'controlled': view['controlled'],
                                'grade': view['score']['grade'], 'correct': view['score']['correct'],
                                'fallback': view['execution']['fallback']})
                candidate_validation.append({'arm': arm, 'batch': receipt['batch'],
                    'candidate_index': candidate_index, 'error': candidate.get('error'),
                    'selected_mask': candidate.get('selected_mask'),
                    'finally_accepted_candidate': receipt['selected_candidate'] == candidate_index,
                    'actual_core_execution_cells': cells,
                    'note': 'Version-table cells are repeated assignments, not independent sources or fresh physical requests.'})
    first = []
    for arm in profile['pilot_arms']:
        for path in sorted((folder / arm).glob('initial_B*.json')):
            batch = read(path)
            for parent in batch['results']:
                first.append({'arm': arm, 'batch': batch['binding']['batch'], 'source': parent['source'],
                    'native_grade': parent['native_grade'], 'selection_grade': parent['selection_grade'],
                    'core_correct': parent['native_core_correct'], 'fallback_views': parent['native_fallback_views'],
                    'views': [{'view': v['view'], 'controlled': v['controlled'], 'score': v['score'],
                        'core_executed': v['execution']['core_executed'], 'fallback': v['execution']['fallback']}
                        for v in parent['views']]})
    snapshot = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'goal_status': 'active',
        'goal_complete': False, 'stage': 'fixed_20_TRAIN_pilot', 'profile': str(PROFILE.relative_to(ROOT)),
        'thinking': False, 'model_parameter_updates': False,
        'ledger_start': {'executor': 1893, 'teacher': 74},
        'cumulative_physical_requests': {k: sum(v.values()) for k, v in total.items()},
        'cumulative_statuses': total, 'goal_physical_statuses': goal, 'goal_usage': usage,
        'pending': pending, 'physical_attempts_this_goal': attempts,
        'completed_update_receipts': updates, 'candidate_validation': candidate_validation,
        'first_attempt_parent_rows': first,
        'independent_parent_count_is_not_multiplied_by_arms_or_views': True,
        'formal_128_training_started': False, 'DEV_started': False, 'TEST_started': False,
        'cash_cost': {'executor_incremental_API_cash_usd': 0,
            'teacher_cash_invoice_usd': None, 'GPU_invoice_usd': None,
            'note': 'Token/time usage measured; subscription and GPU cash invoices unavailable, not asserted free.'},
        'limitations': ['First pilot pass completed; not evidence of two independent contributions.',
            'Unfinished and rejected candidates retained; fallback never counts as core success.',
            'Historical exposure reconciliation remains incomplete outside the specifically audited stores.']}
    repair = ROOT / 'artifacts/legal_skill_evolution_20261111/repair_v13'
    if (repair / 'repair_queue.json').exists():
        queue = read(repair / 'repair_queue.json')
        receipts = sorted(repair.glob('*/B*_c*.json'))
        snapshot['repair_validation'] = {'profile': 'configs/legal_skill_evolution_repair_v13_20261111.json',
            'fixed_candidate_slots': len(queue['queue']), 'settled_candidates': len(receipts),
            'complete': (repair / 'completed.json').exists(), 'new_teacher_requests_planned': 0,
            'new_learning_epoch': False, 'original_first_pass_history_preserved': True,
            'receipts': [{k: v for k, v in read(p).items() if k in
                         ('arm', 'batch', 'candidate', 'selected_mask', 'selection', 'logical_executions', 'compile_error')}
                         for p in receipts]}
    formal = ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v1'
    if (formal / 'execution_manifest.json').exists():
        formal_calls = [r for r in attempts if r['id'].startswith('legal_skill_evolution_formal_')]
        dev = [read(p) for p in sorted((formal / 'dev').glob('*/B*.json'))]
        source_checkpoints = list(formal.glob('*/initial_B*/*.json'))
        snapshot['formal_fixed_study'] = {'profile': 'configs/legal_skill_evolution_formal_v1_20261111.json',
            'run_started': bool(formal_calls), 'frozen_model_external_skill_learning': True,
            'source_count': 128, 'batch_count': 8, 'sources_per_batch': 16,
            'native_TRAIN_DEV_input_preflight_passed': (formal / 'preflight.json').exists(),
            'source_first_attempt_checkpoints_by_arm': Counter(p.parent.parent.name for p in source_checkpoints),
            'update_receipts': [read(p) for p in sorted(formal.glob('*/update_B*.json'))],
            'settled_DEV_points': [{k: r[k] for k in ('arm', 'batch', 'library_hash',
                'native_parent_means_by_dataset', 'equal_dataset_macro')} for r in dev],
            'physical_call_statuses': Counter(r['status'] for r in formal_calls),
            'training_and_DEV_complete': (formal / 'training_DEV_completed.json').exists(),
            'pilot_skills_imported': False, 'teacher_DEV_access': False, 'TEST_started': False}
        snapshot['formal_128_training_started'] = bool(source_checkpoints)
        snapshot['DEV_started'] = any(r['purpose'] == 'skill_dev' for r in formal_calls)
        snapshot['stage'] = 'fixed_128_parent_skill_learning_and_DEV' if formal_calls else 'formal_input_preflight_passed'
    (REPORT / 'pilot_progress.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
    (REPORT / 'current_status.json').write_text(json.dumps({k: snapshot[k] for k in (
        'captured_utc', 'goal_status', 'goal_complete', 'thinking', 'model_parameter_updates',
        'cumulative_physical_requests', 'pending', 'formal_128_training_started', 'DEV_started', 'TEST_started')}
        | {'first_pilot_pass_complete': len(updates) == 16,
           'repair_validation': snapshot.get('repair_validation'),
           'formal_fixed_study': snapshot.get('formal_fixed_study')}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'cumulative': snapshot['cumulative_physical_requests'], 'pending': len(pending),
        'completed_updates': len(updates), 'goal_status': 'active'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
