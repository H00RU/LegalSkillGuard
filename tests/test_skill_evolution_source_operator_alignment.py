"""Current declared actions, actual TRAIN failures, and semantic counterexamples."""
import ast
from copy import deepcopy

import pytest

from experiments import legal_skill_evolution_C_TRAIN_runtime as study
from legal_skill_guard.skill_evolution.source_disposal_review import (
    align_source_disposal_consumer, branch_authorization_preserved,
    validate_reviewed_disposal,
)
from legal_skill_guard.skill_evolution.span_compiler import execute_json


@pytest.fixture(scope='module')
def actual():
    library = study.read(study.OUT / 'FreeTeacher/candidate.json')
    rows = [study.read(p) for p in (study.OUT / 'FreeTeacher/initial_rows').glob('*.json')]
    outputs = {prefix: next(r for r in rows if prefix in r['source'])
               for prefix in ('de427b', 'd50f9b', '4607c9')}
    # The unfitted Free proposal omitted de42. The actual C all-G replay kept
    # its complete OR; use that paid record, never fabricate a missing norm.
    diagnosis = study.read(study.OUT / 'all_G_paid_input_diagnosis.json')
    outputs['de427b'] = next(r for r in diagnosis['rows'] if 'de427b' in r['source'])
    c_library = study.read(study.OUT / 'C/candidate.json')
    assert c_library['spec']['decision_program'] == library['spec']['decision_program']
    return library, outputs


def full(program, action):
    tree = ast.parse(program)
    tree.body = [n for n in tree.body if n.name != 'apply']
    tree.body += ast.parse('def apply(inputs,premises):\n    return {"full":d_full_disposal(inputs["action"])}').body
    return execute_json(ast.unparse(tree), {'action': action}, {}, allow_helpers=True)['full']


def disposal(row):
    return next(s for s in row['source_output']['statements']
                if s['term'][0] == 'disposal_obligation')


def review(row):
    return [{'source': row['source'], 'source_unit_ids': disposal(row)['support_ids']}]


def test_real_ordinary_OR_retains_same_material_and_changes_no_other_function(actual):
    library, rows = actual
    old = library['spec']['decision_program']
    new = align_source_disposal_consumer(old)
    row = rows['de427b']
    action = disposal(row)['term'][2]
    assert action[0] == 'source_action_alternative'
    assert not full(old, action)
    assert full(new, action)
    assert not validate_reviewed_disposal(row['source_output'], review(row), new)
    before = {n.name: ast.dump(n) for n in ast.parse(old).body}
    after = {n.name: ast.dump(n) for n in ast.parse(new).body}
    assert before.keys() == after.keys()
    assert all(before[k] == after[k] for k in before if k != 'd_full_disposal')


def test_real_OR_plus_required_derivatives_is_not_strengthened_full_destroy(actual):
    library, rows = actual
    row = rows['d50f9b']
    action = disposal(row)['term'][2]
    assert action[0] == 'source_action_conjunction'
    program = align_source_disposal_consumer(library['spec']['decision_program'])
    assert full(program, action)
    assert not validate_reviewed_disposal(row['source_output'], review(row), program)
    changed = deepcopy(row['source_output'])
    term = disposal({'source_output': changed})['term']
    term[2][2] = deepcopy(term[2][1][2])
    assert any('strengthened' in x['violation']
               for x in validate_reviewed_disposal(changed, review(row), program))


def test_real_authorization_stays_on_destroy_and_plain_OR_cannot_hide_beside_it(actual):
    library, rows = actual
    row = rows['4607c9']
    output = row['source_output']
    units = disposal(row)['support_ids']
    assert disposal(row)['term'][2][0] == 'source_authorized_action_alternative'
    assert branch_authorization_preserved(output, units)
    program = align_source_disposal_consumer(library['spec']['decision_program'])
    assert full(program, disposal(row)['term'][2])
    swapped = deepcopy(output)
    action = disposal({'source_output': swapped})['term'][2]
    action[1], action[2] = action[2], action[1]
    assert not branch_authorization_preserved(swapped, units)
    plain = deepcopy(disposal(row))
    plain['term'][2][0] = 'source_action_alternative'
    assert not branch_authorization_preserved({'statements': [plain]}, units)
    assert not branch_authorization_preserved({'statements': output['statements'] + [plain]}, units)


@pytest.mark.parametrize('prefix', ['de427b', '4607c9'])
def test_partial_branch_stays_partial_even_when_source_quote_mentions_all_copies(actual, prefix):
    library, rows = actual
    action = deepcopy(disposal(rows[prefix])['term'][2])
    action[2][1] = ['confidential_information']
    program = align_source_disposal_consumer(library['spec']['decision_program'])
    assert not full(program, action)
    if prefix == 'de427b':
        output = deepcopy(rows[prefix]['source_output'])
        disposal({'source_output': output})['term'][2] = action
        assert validate_reviewed_disposal(output, review(rows[prefix]), program)


def test_atomic_full_branch_does_not_replace_reviewed_OR(actual):
    library, rows = actual
    row = rows['de427b']
    changed = deepcopy(row['source_output'])
    term = disposal({'source_output': changed})['term']
    term[2] = deepcopy(term[2][2])
    program = align_source_disposal_consumer(library['spec']['decision_program'])
    issues = validate_reviewed_disposal(changed, review(row), program)
    assert any('strengthened' in r['violation'] for r in issues)
    assert any('omitted' in r['violation'] for r in issues)
