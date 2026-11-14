"""Shared consumer repair for already declared source-absence observations.

No source absence is inferred here. The old active consumer had no branch for
three constructors already defined by its own schema. Explicit reader judgments
remain different from no matched rule or an unparsed source residual.
"""
from copy import deepcopy
import ast
import json
from pathlib import Path

from experiments import legal_skill_evolution_source_gap_acquisition as old
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure, execute_json


ROOT = old.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_source_absence_consumer_20261114'


def read(path):
    return json.loads(path.read_text())


def repair(program):
    lines = program.splitlines(keepends=True)
    node = next(node for node in ast.parse(program).body if node.name == 'apply')
    body = ''.join(lines[node.lineno - 1:node.end_lineno])
    changes = [
        ('    residual=[]\n', '    residual=[]\n    absence_disclosure=[]\n    absence_disposal=[]\n    absence_retention=[]\n'),
        ("        elif term[0]=='source_residual_observation_v3':\n", "        elif term[0]=='complete_source_no_disclosure_permission':\n            absence_disclosure.append(root)\n        elif term[0]=='complete_source_no_disposal_obligation':\n            absence_disposal.append(root)\n        elif term[0]=='complete_source_no_retention_effect':\n            absence_retention.append(root)\n        elif term[0]=='source_residual_observation_v3':\n"),
        ("        if relevant:\n            return {'handled':True,'answer':'NotMentioned','used_nodes':d_unique(relevant+definition_roots)}\n", "        if relevant or absence_disclosure:\n            return {'handled':True,'answer':'NotMentioned','used_nodes':d_unique(relevant+definition_roots+absence_disclosure)}\n"),
        ("        if endpoint:\n            return {'handled':True,'answer':'Entailment','used_nodes':d_unique(endpoint)}\n", "        if endpoint:\n            return {'handled':True,'answer':'Entailment','used_nodes':d_unique(endpoint)}\n        if absence_disposal and not relevant:\n            return {'handled':True,'answer':'NotMentioned','used_nodes':d_unique(absence_disposal)}\n"),
        ("    if full_return:\n        return {'handled':True,'answer':'Contradiction','used_nodes':d_unique(full_return)}\n", "    if full_return:\n        return {'handled':True,'answer':'Contradiction','used_nodes':d_unique(full_return)}\n    if absence_retention:\n        return {'handled':True,'answer':'NotMentioned','used_nodes':d_unique(absence_retention)}\n"),
    ]
    for before, after in changes:
        assert body.count(before) == 1
        body = body.replace(before, after, 1)
    updated = ''.join(lines[:node.lineno - 1]) + body + ''.join(lines[node.end_lineno:])
    validate_procedure(updated, allow_helpers=True)
    return updated


def software_checks(program):
    result = []
    for task, tag in [('nda-5', 'complete_source_no_disclosure_permission'),
                      ('nda-7', 'complete_source_no_disclosure_permission'),
                      ('nda-16', 'complete_source_no_disposal_obligation'),
                      ('nda-20', 'complete_source_no_retention_effect')]:
        # Constructor-interface unit probes, not synthetic benchmark cases,
        # acquired facts or claims of a learned source judgment.
        value = execute_json(program, {'task_id': task}, {
            'nodes': [{'id': 0, 'term': [tag], 'child_ids': []}], 'roots': [0]}, allow_helpers=True)
        assert value == {'handled': True, 'answer': 'NotMentioned', 'used_nodes': [0]}
        empty = execute_json(program, {'task_id': task}, {'nodes': [], 'roots': []}, allow_helpers=True)
        assert not empty['handled'] and empty['answer'] is None
        result.append({'task': task, 'declared_constructor': tag,
                       'explicit_absence_handled': True, 'no_observation_remains_unresolved': True})
    return result


def run():
    current = read(old.OUT / 'unbound_provenance_replay/library.json')
    before = current['spec']['decision_program']
    after = repair(before)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, code in [('before.py', before), ('after.py', after)]:
        path = OUT / name
        if path.exists():
            assert path.read_text() == code
        else:
            path.write_text(code)
    checks = software_checks(after)
    public = {source['key']: source for source in read(old.previous.prior.prior.PUBLIC)}
    grading = read(old.previous.prior.prior.GRADING)
    task = read(old.OUT / 'teacher_task.json')
    rows = []
    for arm in old.ARMS:
        original = current if arm == 'ConstraintAcquire' else read(old.OUT / 'FreeUpdate/compiled.json')
        library = deepcopy(original)
        library['spec']['decision_program'] = after
        for entry in task['tasks']:
            key = entry['source_id']
            observation = read(old.OUT / 'unbound_pure_preview' / arm / old.name_for(key))['observation']
            actual = old.previous.prior.prior.evaluate_source(library, observation, public[key], grading[key])
            immutable_json(OUT / 'execution' / arm / old.name_for(key), actual)
            rows.append({'arm': arm, 'source': key,
                'correct': sum(bool(v['score'] and v['score']['correct']) for v in actual['feedback']['views']),
                'unresolved': sum(not v['core_executed'] for v in actual['feedback']['views'])})
    result = {'common_repair_not_method_gain': True, 'new_model_calls': 0,
        'source_programs_legal_terms_and_G_unchanged': True,
        'before_consumer_sha256': digest(before), 'after_consumer_sha256': digest(after),
        'software_constructor_probes': checks, 'rows': rows,
        'correct': {arm: sum(row['correct'] for row in rows if row['arm'] == arm) for arm in old.ARMS},
        'no_TEST_DEV_or_new_sources': True, 'goal_complete': False}
    immutable_json(OUT / 'result.json', result)
    print(json.dumps({'correct_after_shared_consumer_fix': result['correct'],
                      'software_constructor_probes': len(checks), 'new_model_calls': 0}), flush=True)


if __name__ == '__main__':
    run()
