"""Offline audit of the settled teacher refactor; never starts a model call.

Replays only the two acquisition-case bindings already recorded by the real
reader. No later check cases, labels or question variants are consumed.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.callable_rules import evaluate, plan
from legal_skill_guard.skill_evolution.source_python import validate


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/legal_skill_evolution_callable_rule_refactor_20261113'
PARENT = ROOT / 'artifacts/legal_skill_evolution_teacher_proof_skills_20261113'


def read(path):
    return json.loads(path.read_text())


def trace(program, inputs):
    validate(program)
    worker = ROOT / 'legal_skill_guard/skill_evolution/span_compiler_worker.py'
    result = subprocess.run([sys.executable, '-I', '-S', str(worker)],
        input=json.dumps({'procedure': program, 'inputs': inputs,
                         'premises': {}, 'trace': True}),
        capture_output=True, text=True, timeout=4, cwd='/tmp',
        env={'LANG': 'C.UTF-8'}, close_fds=True)
    if result.returncode:
        raise ValueError(result.stderr[-1000:])
    return json.loads(result.stdout)


def run():
    library = read(OUT / 'library.json')
    protocol = read(OUT / 'protocol.json')
    material = read(PARENT / 'source_only_input.json')['law_material']
    teacher = read(OUT / 'teacher.json')
    replay = []
    for old_path in sorted((PARENT / 'revised_execution/calibration/Full').glob('*/result.json')):
        old = read(old_path)
        assert old['source'] in protocol['source_ids']
        planned = plan(library, old['question'], material)
        values = old['validated_case_values']
        assert set(values) <= set(planned['fields'])
        result = evaluate(library, planned, values)
        execution = trace(library['program'], {'unit': planned['unit'], 'facts': values})
        assert result['value'] == execution['result']['value']
        assert result['answer'] == old['execution']['result']['answer']
        immutable_json(OUT / 'acquisition_replay' / old_path.parent.name / 'execution.json', execution)
        replay.append({'source': old['source'], 'plan': planned,
            'reused_actual_reader_bindings': values, 'result': result,
            'old_answer_preserved': True, 'new_model_call': False,
            'independent_validation_or_new_task_gain': False})
    assert len(replay) == 2
    units = []
    for unit in library['units'].values():
        execution = trace(library['program'], {'unit': unit['id'], 'facts': {}})
        assert execution['result']['value'] is None
        assert unit['function'] in {c['function'] for c in execution['calls']}
        units.append({'id': unit['id'], 'clause': unit['clause'], 'kind': unit['kind'],
            'declared_function_actually_called': True, 'empty_inputs_unknown': True})
    # Applicability and quantitative effect are distinct properties. There is
    # no generic semantics-preserving conversion from a number to applicability.
    # This inventory diagnoses missing public heads without adding legal rules.
    heads = {(u['clause'], u['kind']) for u in library['units'].values()}
    quantity_only = sorted(clause for clause, kind in heads
                           if kind == 'quantity' and (clause, 'predicate') not in heads)
    snapshot = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
                for name, expected in protocol['source_sha256'].items()}
    assert all(snapshot.values())
    db = sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True)
    rows = [list(r) for r in db.execute('select * from calls order by id')]
    before = read(OUT / 'ledger_before.json')['rows']
    current = {r[0]: r for r in rows}
    assert all(current[r[0]] == r for r in before)
    new = [r for r in rows if r[0] not in {b[0] for b in before}]
    assert len(new) == 1 and new[0][1] == 'teacher' and new[0][6] == 'completed'
    assert not any(r[6] == 'reserved' for r in rows)
    summary = {'checked_utc': datetime.now(timezone.utc).isoformat(),
        'same_goal_active_incomplete': True, 'unit_count': len(units),
        'unit_entry_checks': units, 'acquisition_binding_replays': replay,
        'source_snapshot_unchanged': snapshot,
        'quantity_heads_without_independent_applicability': quantity_only,
        'semantic_completeness_established': False,
        'fresh_validation_executed': False, 'contribution_gain_established': False,
        'next_concrete_gap': 'Distinct applicability conditions are not exposed for quantitative clauses; do not use value>0 as a generic substitute or claim property-count growth as method gain.',
        'new_physical_requests': dict(Counter(r[1] for r in new)),
        'cumulative': dict(Counter(r[1] for r in rows)),
        'old_rows_unchanged': len(before), 'ledger_rows': len(rows), 'pending': 0,
        'ledger_sha256': hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',', ':')).encode()).hexdigest(),
        'teacher_usage': teacher['invocation']['usage'],
        'teacher_service_seconds': teacher['elapsed_seconds'],
        'teacher_cash_invoice_available': False}
    immutable_json(OUT / 'semantic_interface_audit.json', summary)
    print(json.dumps({k: summary[k] for k in ('unit_count', 'quantity_heads_without_independent_applicability',
        'new_physical_requests', 'cumulative', 'old_rows_unchanged', 'ledger_rows', 'pending')},ensure_ascii=False))


if __name__ == '__main__':
    run()
