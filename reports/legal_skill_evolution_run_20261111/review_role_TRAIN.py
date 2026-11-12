"""Read-only finite diagnostic accounting; never calls models or opens DEV/TEST."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.skill_evolution.objects import Library, digest

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / 'artifacts/legal_skill_evolution_role_TRAIN_20261112'
ORIGINAL = Path('/home/yndx/hhy/legal-skill-redesign-20261109')
REPORT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def outcome(row):
    return {'source': row['source'], 'native_grade': row['native_grade'],
        'core_correct': row['native_core_correct'], 'fallback_views': row['native_fallback_views'],
        'views': [{'view': v['view'], 'grade': v['score']['grade'],
                   'answer': v['execution']['answer'],
                   'core': v['execution']['core_executed'], 'fallback': v['execution']['fallback'],
                   'terminal': v['execution'].get('terminal_skill'),
                   'failures': v['execution'].get('failed_candidates', []),
                   'role_bound_USE': [e for e in v['execution']['events']
                                      if e.get('kind') == 'USE' and e.get('producer_arguments')],
                   'APPLY': [e for e in v['execution']['events'] if e.get('kind') == 'APPLY']}
                  for v in row['views'] if not v.get('controlled')]}


def main():
    protocol = read(FOLDER / 'protocol.json')
    ledger = ORIGINAL / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:' + str(ledger) + '?mode=ro', uri=True) as db:
        all_counts = {(r, s): n for r, s, n in db.execute('select role,status,count(*) from calls group by role,status')}
        rows = db.execute('select id,role,status,result from calls where id like ? order by reserved_at',
                          (protocol['run_id'] + ':%',)).fetchall()
    requests = []
    usage = {'executor': Counter(), 'teacher': Counter()}
    for identity, role, state, raw in rows:
        result = json.loads(raw or '{}')
        tokens = ((result.get('invocation') or {}).get('usage') if role == 'teacher'
                  else result.get('usage')) or {}
        usage[role].update({k: v for k, v in tokens.items() if isinstance(v, (int, float))})
        requests.append({'id': identity, 'role': role, 'status': state, 'usage': tokens,
            **{k: result.get(k) for k in ('elapsed_seconds', 'finish_reason', 'error')}})
    arms = {}
    for arm in protocol['arms']:
        initial, updates, libraries, candidates = [], [], [], []
        for b in (1, 2):
            p = FOLDER / arm / f'initial_B{b}.json'
            if p.exists():
                initial.append({'batch': b, 'results': [outcome(r) for r in read(p)['results']]})
            p = FOLDER / arm / f'update_B{b}.json'
            if p.exists():
                updates.append(read(p))
            p = FOLDER / arm / f'B{b}.json'
            if p.exists():
                library = Library.load(p)
                libraries.append({'batch': b, 'hash': library.hash, 'skills': [
                    {'id': s.id, 'hash': s.hash, 'intent': s.intent, 'version': s.version,
                     'argument_inputs': {n: p for n, p in s.inputs.items() if p['mode'] == 'argument'},
                     'dependencies': {n: p for n, p in s.inputs.items() if p['mode'] == 'skill'},
                     'procedure': s.procedure, 'source_provenance': s.source_provenance}
                    for s in library.skills.values()],
                    'learned_patterns': library.revision_patterns})
            for p in sorted((FOLDER / arm / f'B{b}_candidates').glob('*.json')):
                candidate = read(p)
                table = candidate.get('table') or {}
                candidates.append({'batch': b, 'candidate': p.stem, 'error': candidate.get('error'),
                    'selection_exclusion': candidate.get('selection_exclusion'),
                    'scheduled_lift': candidate.get('planned_lift'),
                    'selected_mask': candidate.get('selected_mask'),
                    'classification': table.get('classification'), 'complete': table.get('complete'),
                    'revisions': candidate.get('revisions'),
                    'cells': [{k: c[k] for k in ('mask', 'source', 'native_parent_grade', 'measured')}
                              for c in table.get('mixed_version_table', [])]})
        arms[arm] = {'initial': initial, 'updates': updates, 'libraries': libraries, 'candidates': candidates}
    completed = FOLDER / 'completed.json'
    if completed.exists():
        for arm, parents in read(completed)['reuse_results'].items():
            arms[arm]['frozen_TRAIN_reuse'] = [outcome(row) for row in parents]
    value = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
        'protocol_hash': digest(protocol), 'controller': read(FOLDER / 'status.json'),
        'full_training_or_matrix_restarted': False, 'DEV_TEST_loaded': False,
        'arms': arms, 'requests': requests,
        'request_counts': {role: dict(Counter(s for _, r, s, _ in rows if r == role)) for role in usage},
        'usage_by_original_field': {role: dict(v) for role, v in usage.items()},
        'reasoning_tokens_not_added_again_to_output_tokens': True,
        'cumulative_ledger': {role: {'total': sum(n for (r, _), n in all_counts.items() if r == role),
            **{s: n for (r, s), n in all_counts.items() if r == role}} for role in usage},
        'actual_GPU_and_teacher_cash_invoice': None,
        'semantic_review': 'Pending manual review of actual source, role bindings and learned procedures. Native correctness or support selection alone is not credited as mechanism success.',
        'Lift_independent_contribution_established': False,
        'CoRev_independent_contribution_established': False}
    (REPORT / 'role_TRAIN_current_results.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'phase': value['controller']['phase'], 'new_requests': value['request_counts'],
        'updates_completed': {a: len(v['updates']) for a, v in arms.items()},
        'cumulative_ledger': value['cumulative_ledger'], 'goal_complete': False}))


if __name__ == '__main__':
    main()
