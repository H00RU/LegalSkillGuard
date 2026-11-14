"""A shared, source-faithful disposal-alternative consumer correction at B4.

Do not select a label-fitting G that splits a legal OR into atomic obligations.
The same frozen source programs and G are executed for both arms with the same
public consumer change. Preserve all original B4 initial results and tasks.
"""
import ast
from copy import deepcopy
import json

from experiments import legal_skill_evolution_source_batch_initial as initial
from experiments import legal_skill_evolution_source_library_train as train
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure


OUT = train.OUT / 'B4/public_disposal_consumer_boundary'


def repair(code):
    tree = ast.parse(code)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'd_full_return_only')
    old = ast.get_source_segment(code, node)
    # Keep the exact previously supported direct-return behavior. The new case
    # uses only the two declared semantic Action children, never quoted metadata.
    new = '''def d_full_disposal_leaf(action):
    if not isinstance(action,list) or not action or action[0] not in ('return_to','destroy'):
        return False
    for item in d_subterms(action):
        if item[0]=='acquired_material_v3' and len(item)>1 and item[1] in ('all_source_stated_materials','confidential_information_and_copies','information_copies_and_derivatives'):
            return True
        if item[0]=='source_scoped_disposal_material' and len(item)>1 and item[1] in ('all_source_materials','confidential_information_and_copies','information_copies_and_derivatives'):
            return True
        if item[0]=='information_bundle' and d_has(item,'confidential_information') and d_has(item,'copies_of'):
            return True
    return False

def d_full_disposal(action):
    if isinstance(action,list) and len(action)>=3 and action[0] in ('action_alternative','acquired_action_alternative_v3'):
        return d_full_disposal_leaf(action[1]) and d_full_disposal_leaf(action[2])
'''
    # The old function's body follows the added alternative case verbatim.
    new += '\n'.join(old.splitlines()[1:])
    result = code.replace(old, new, 1).replace('d_full_return_only(term[2])', 'd_full_disposal(term[2])')
    validate_procedure(result, allow_helpers=True)
    assert "if task=='nda-16':" in code
    before_scope = code[code.index("if task=='nda-16':"):code.index('    if retention_permissions:')]
    after_scope = result[result.index("if task=='nda-16':"):result.index('    if retention_permissions:')]
    assert before_scope == after_scope
    return result


def run():
    old = {a: train.read(train.OUT / 'B3' / a / 'library.json') for a in train.ARMS}
    assert len({digest(lib['spec']['decision_program']) for lib in old.values()}) == 1
    code = repair(old['ConstraintAcquire']['spec']['decision_program'])
    task = train.read(train.OUT / 'B4/teacher_task.json')
    rows_by_arm = {}
    for arm in train.ARMS:
        library = deepcopy(old[arm])
        library['spec']['decision_program'] = code
        preservation = deepcopy(library)
        preservation['spec']['decision_program'] = old[arm]['spec']['decision_program']
        assert preservation == old[arm]
        immutable_json(OUT / arm / 'library.json', library)
        rows = [initial.evaluate(library, t['source_id'], arm, 4,
            OUT / arm / 'results' / train.previous.old.name_for(t['source_id'])) for t in task['tasks']]
        current = [r for r in rows if r['source'] in task['current_sources']]
        assert all('actual' in r for r in rows), 'Do not hide a new execution failure'
        old_rows = [train.read(train.OUT / 'B4' / arm / 'pre_update_seen' / train.previous.old.name_for(t['source_id'])) for t in task['tasks']]
        for before, after in zip(old_rows, rows):
            for v0, v1 in zip(before['actual']['feedback']['views'], after['actual']['feedback']['views']):
                if v0['view'] != 'nda-20':
                    assert v0['score'] == v1['score'] and v0['core_executed'] == v1['core_executed']
        assert sum(r['correct'] for r in current) == 12 and not sum(r['unresolved'] for r in current)
        rows_by_arm[arm] = {'current_correct': 12, 'current_total': 12,
            'seen_correct': sum(r['correct'] for r in rows), 'seen_total': 4 * len(rows),
            'unresolved': sum(r['unresolved'] for r in rows)}
        immutable_json(train.OUT / 'B4' / arm / 'library.json', library)
    receipt = {'batch': 4, 'same_shared_consumer_both_arms': True,
        'old_consumer_sha256': digest(old['ConstraintAcquire']['spec']['decision_program']),
        'new_consumer_sha256': digest(code), 'no_source_phi_G_or_planner_change': True,
        'nda16_scope_byte_identical_preserves_existing_residual_loss_bound': True,
        'source_OR_not_split_into_atomic_obligations': True,
        'actual_current_G_native_reachability_not_a_source_semantic_certificate': True,
        'before_current_by_arm': {a: train.read(train.OUT / 'B4' / a / 'initial_summary.json')['current_correct'] for a in train.ARMS},
        'after': rows_by_arm, 'new_model_calls': 0, 'new_C_learning_credit': False,
        'original_initial_outputs_and_undispatched_task_preserved': True,
        'operation': 'shared_consumer_correction_then_unchanged_source_and_G_checkpoint',
        'goal_complete': False}
    immutable_json(OUT / 'receipt.json', receipt)
    immutable_json(train.OUT / 'B4/update_receipt.json', receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    run()
