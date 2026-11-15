"""Material-scope helper conformance, not additional contract training cases."""
import ast

from experiments import legal_skill_evolution_native_consumer_symmetry as repair
from legal_skill_guard.skill_evolution.span_compiler import execute_json


def scopes(program, actions):
    tree = ast.parse(program)
    tree.body = [n for n in tree.body if not isinstance(n, ast.FunctionDef) or n.name != 'apply']
    tree.body += ast.parse("def apply(inputs,premises):\n    return {'scopes':[d_full_disposal(a) for a in inputs['actions']]}\n").body
    return execute_json(ast.unparse(ast.fix_missing_locations(tree)), {'actions': actions}, {}, allow_helpers=True)['scopes']


def test_full_return_and_destroy_have_symmetric_scope_but_partial_or_branches_do_not():
    path = repair.current.OUT / 'ConstraintAcquire/library.json'
    original = repair.current.update.train.read(path)['spec']['decision_program']
    full = ['acquired_material_v3', 'confidential_information_and_copies', 'unit-test material scope']
    partial = ['acquired_material_v3', 'some_information', 'unit-test partial scope']
    returned = ['return_to', ['disclosing_party'], full]
    destroyed = ['destroy', full]
    actions = [returned, destroyed, ['destroy', partial],
        ['action_alternative', returned, destroyed],
        ['action_alternative', returned, ['destroy', partial]]]
    assert scopes(original, actions) == [True, False, False, True, False]
    assert scopes(repair.revised(original), actions) == [True, True, False, True, False]
