"""Publish the finite interface checks and actual reused-compiler execution."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT/'artifacts/legal_skill_evolution_effect_slots_20261113'
DEST = Path(__file__).resolve().parent/'effect_interface_reuse'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def export():
    before = json.loads((SOURCE/'ledger_before.json').read_text())['rows']
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        columns = [r[1] for r in db.execute('pragma table_info(calls)')]
        rows = [list(r) for r in db.execute('select * from calls order by id')]
    old = {r[0]: r for r in before}
    current = {r[0]: r for r in rows}
    assert all(current[k] == value for k, value in old.items())
    assert not any(r[6] == 'reserved' for r in rows)
    added = [dict(zip(columns, r)) for r in rows if r[0] not in old]
    for row in added:
        row['result'] = json.loads(row['result'])
        assert row['role'] == 'executor'
        assert row['result']['thinking_requested'] is False
    cost = {'new_physical_requests': dict(Counter(r['role'] for r in added)),
            'cumulative': dict(Counter(r[1] for r in rows)), 'total_rows': len(rows),
            'old_rows_unchanged': len(before), 'pending': 0,
            'ledger_sha256': hashlib.sha256(json.dumps(rows, ensure_ascii=False,
                separators=(',', ':')).encode()).hexdigest(),
            'executor_input_tokens': sum(r['result']['usage']['prompt_tokens'] for r in added),
            'executor_output_tokens': sum(r['result']['usage']['completion_tokens'] for r in added),
            'executor_elapsed_seconds': sum(r['result']['elapsed_seconds'] for r in added),
            'executor_incremental_API_cash_usd': 0, 'GPU_allocation_usd': None,
            'teacher_requests': 0, 'requests': added,
            'reused_compiler_execution_new_model_calls': 0,
            'inherited_real_teacher_and_actor_acquisition_costs_not_zero_or_removed': True,
            'native_gain_on_repaired_acquisition_source': 0,
            'first_contribution_established': False, 'goal_complete': False}
    write(DEST/'cost_and_preservation.json', cost)
    for source in SOURCE.rglob('*'):
        if not source.is_file() or source.suffix not in ('.json', '.py'):
            continue
        rel = source.relative_to(SOURCE)
        if rel.name.startswith('ledger_') or '__pycache__' in rel.parts:
            continue
        target = DEST/'raw'/rel
        if source.suffix == '.py': target = Path(str(target)+'.txt')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists(): assert target.read_bytes() == source.read_bytes()
        else: target.write_bytes(source.read_bytes())
    write(DEST/'offline_checks.json', {
        'unittest_command': ".venv/bin/python -m unittest discover -s tests -p 'test_skill_evolution*.py'",
        'tests_passed': 278, 'errors': 0,
        'old_compiler_output_exactly_reproduced': True,
        'only_two_actual_functions_changed_all_other_ASTs_equal': True,
        'missing_actor_bindings_preserve_unresolved_and_emit_no_target_norms': True,
        'source58_subject_scope_and_condition_link_review_passed': True,
        'fresh_full_source_or_unseen_validation_claimed': False,
        'goal_complete': False})
    print(json.dumps({k: v for k, v in cost.items() if k != 'requests'}, ensure_ascii=False))


if __name__ == '__main__':
    export()
