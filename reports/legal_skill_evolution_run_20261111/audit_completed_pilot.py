"""Source-level first-pass evidence; scores are read, never recomputed to tune."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent
PILOT = ROOT / 'artifacts/legal_skill_evolution_20261111/pilot_v11'
ARMS = ('Full', 'FreeEvolution', 'AllPorts+CoRev', 'Lift+GenericJoint')


def load(p):return json.loads(p.read_text())


def candidates(arm, batch):
    paths = sorted((PILOT / arm / f'B{batch}_candidates').glob('*.json'))
    if paths:return [(int(p.stem), load(p)) for p in paths]
    library = load(PILOT / arm / f'B{batch}.json')
    return [(r['candidate_index'], r) for r in library['provisional_edits'] if r['batch'] == batch]


def main():
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'pilot_learning_passes': 1, 'independent_parent_count': 20, 'native_views': 50,
        'controlled_views': 32, 'arms': {}, 'goal_complete': False}
    for arm in ARMS:
        metrics, failures, errors = Counter(), Counter(), []
        first_core, teacher_coverage, triggers, accepted = [], set(), set(), []
        source_rows = []
        for batch in range(1, 5):
            initial = load(PILOT / arm / f'initial_B{batch}.json')
            for parent in initial['results']:
                source_rows.append({k: parent[k] for k in ('source', 'dataset', 'native_grade', 'selection_grade',
                    'native_core_correct', 'native_fallback_views')} | {'batch': batch})
                for v in parent['views']:
                    tag = 'controlled' if v['controlled'] else 'native'
                    metrics[tag + '_views'] += 1
                    metrics[tag + '_fully_correct_views'] += bool(v['score']['correct'])
                    metrics[tag + '_grade_sum'] += v['score']['grade'] or 0
                    metrics[tag + '_fallback_views'] += bool(v['execution']['fallback'])
                    metrics[tag + '_core_executions'] += bool(v['execution']['core_executed'])
                    metrics[tag + '_correct_core_executions'] += bool(v['score']['correct'] and v['execution']['core_executed'])
                    if v['execution']['core_executed']:
                        first_core.append({'batch': batch, 'source': parent['source'], 'view': v['view'],
                            'grade': v['score']['grade'], 'terminal_skill': v['execution'].get('terminal_skill')})
            context_path = PILOT / arm / f'update_context_B{batch}.json'
            if context_path.exists():
                cohort = load(context_path)['cohort']
            else:
                exported = next(c['table'] for _, c in candidates(arm, batch) if c.get('table'))
                cohort = exported['trigger'] + exported['history']
            teacher_coverage.update(cohort)
            # Original tables preserve the actual trigger/history split.
            for i, c in candidates(arm, batch):
                if c.get('error'):errors.append({'batch': batch, 'candidate': i, 'error': c['error']})
                table = c.get('table') or {}
                triggers.update(table.get('trigger', []))
                for cell in table.get('mixed_version_table', []):
                    for v in (cell.get('trace') or {}).get('views', []):
                        for failure in v['execution'].get('failed_candidates', []):
                            failures[failure['error'].split('\n')[0]] += 1
            update = load(PILOT / arm / f'update_B{batch}.json')
            accepted.append({k: update[k] for k in ('batch', 'selected_candidate', 'selected_mask',
                'skill_count', 'pattern_count', 'learned_pattern_ids', 'logical_candidate_parent_executions')})
        all_keys = {r['source'] for r in source_rows}
        result['arms'][arm] = {'first_attempt_metrics': dict(metrics), 'first_attempt_core_uses': first_core,
            'source_rows': source_rows, 'settled_updates': accepted,
            'teacher_context_parents': sorted(teacher_coverage), 'teacher_context_parent_count': len(teacher_coverage),
            'never_in_teacher_context': sorted(all_keys - teacher_coverage),
            'trigger_parents': sorted(triggers), 'compile_failures': errors,
            'execution_failure_cell_counts': dict(failures),
            'failure_cells_not_independent_sources_or_physical_calls': True}
    result['decision'] = {'engineering_path_has_real_learning': True,
        'dedicated_Lift_transfer_validated': False, 'CoRev_learned_pattern_transfer_validated': False,
        'formal_training_ready_under_current_entry_conditions': False,
        'controlled_baseline_ceiling': '32/32 already correct before learning; not evidence of method benefit',
        'next_work': 'consolidated implementation repair and fixed affected-candidate validation; no new learning epoch'}
    (REPORT / 'completed_pilot_audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({a: {'skills': result['arms'][a]['settled_updates'][-1]['skill_count'],
        'patterns': result['arms'][a]['settled_updates'][-1]['pattern_count'],
        'new_parent_correct_core_views': result['arms'][a]['first_attempt_metrics']['native_correct_core_executions'],
        'teacher_context_parents': result['arms'][a]['teacher_context_parent_count']} for a in ARMS}))


if __name__ == '__main__':main()
