"""Repair the native consumer's return/destroy material-scope asymmetry.

Existing TRAIN source outputs are untouched; the same candidate consumer is
applied to both acquisition arms. No generation, source acquisition or DEV.
"""
import ast
from copy import deepcopy
import hashlib
from pathlib import Path

from experiments import legal_skill_evolution_source_projection_runtime as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.span_compiler import execute_json

ROOT = current.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_native_consumer_symmetry_20261115'
FIX = '''def d_full_disposal(action):
    if isinstance(action,list) and len(action)>=3 and action[0] in ('action_alternative','acquired_action_alternative_v3','authorized_action_alternative'):
        return d_full_disposal_leaf(action[1]) and d_full_disposal_leaf(action[2])
    return d_full_disposal_leaf(action)
'''


def revised(program):
    tree = ast.parse(program)
    found = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'd_full_disposal']
    assert len(found) == 1
    old = found[0]
    assert "not d_has(action, 'return_to') or d_has(action, 'destroy')" in ast.unparse(old)
    tree.body[tree.body.index(old)] = ast.parse(FIX).body[0]
    return ast.unparse(ast.fix_missing_locations(tree))


def batch(program, cases):
    tree = ast.parse(program)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'apply':
            node.name = 'native_consumer'
    tree.body += ast.parse('''def apply(inputs,premises):
    values=[]
    for case in inputs['cases']:
        values.append(native_consumer(case['query'],case['premises']))
    return {'values':values}
''').body
    return execute_json(ast.unparse(ast.fix_missing_locations(tree)), {'cases': cases}, {}, allow_helpers=True)['values']


def run():
    read = current.update.train.read
    public = {s['key']: s for s in read(current.update.train.parent.PREPARED / 'public.json') if s['dataset'] == 'ContractNLI'}
    grading = read(current.update.train.parent.PREPARED / 'grading.json')
    results = {}
    for arm in ('ConstraintAcquire', 'FreeUpdate'):
        library = read(current.OUT / arm / 'library.json')
        old = library['spec']['decision_program']
        new = revised(old)
        immutable_json(OUT / arm / 'consumer_candidate.json', {'original_sha256': hashlib.sha256(old.encode()).hexdigest(),
            'candidate_sha256': hashlib.sha256(new.encode()).hexdigest(), 'program': new,
            'source_library_unchanged_not_promoted': True})
        cases, metadata = [], []
        for path in sorted((current.OUT / arm / 'results').glob('*.json')):
            actual = read(path)
            source = public[actual['source']]
            assert source['split'] == 'train'
            nodes = [{'id': i, 'term': deepcopy(row['term']), 'child_ids': []}
                     for i, row in enumerate(actual['source_output']['statements'])]
            saved = {r['view']: r for r in actual['feedback']['views']}
            for view in source['views']:
                cases.append({'query': {'task_id': view['id'], 'question': view['public']['question']},
                    'premises': {'nodes': nodes, 'roots': list(range(len(nodes)))}})
                metadata.append({'source': source['key'], 'view': view,
                    'old_value': saved[view['id']]['execution']['value']})
        before, after = batch(old, cases), batch(new, cases)
        assert before == [m['old_value'] for m in metadata]
        rows = []
        for m, a, b in zip(metadata, before, after):
            sid, view = m['source'], m['view']
            rows.append({'source': sid, 'view': view['id'], 'before': a, 'after': b,
                'before_score': grade_view('ContractNLI', view, grading[sid][view['id']], a['answer']) if a['handled'] else None,
                'after_score': grade_view('ContractNLI', view, grading[sid][view['id']], b['answer']) if b['handled'] else None})
        result = {'rows': rows, 'original_full_execution_parity': True,
            'native_correct_before': sum(bool(r['before_score'] and r['before_score']['correct']) for r in rows),
            'native_correct_after': sum(bool(r['after_score'] and r['after_score']['correct']) for r in rows),
            'changed_views': [r for r in rows if r['before'] != r['after']], 'new_model_calls': 0}
        immutable_json(OUT / arm / 'result.json', result)
        results[arm] = {k: v for k, v in result.items() if k != 'rows'}
    immutable_json(OUT / 'result.json', {'arms': results, 'new_model_calls': 0,
        'only_original_TRAIN_outputs': True, 'DEV_TEST_accessed': False,
        'same_consumer_repair_both_arms': True, 'no_source_outputs_rules_or_scores_overwritten': True,
        'not_a_C_learning_advantage_or_goal_completion': True, 'goal_complete': False})
    print(results)


if __name__ == '__main__':
    run()
