import json

from experiments.convergence_revision5_cni_use_and_license import ABSENT, ROLES, YES, contract, decode, layouts
from legal_skill_guard.paired_interfaces import residual


def test_fixed_and_derived_relations_read_identical_public_input():
    case = {'data': {'indexed_spans': [{'id': 0, 'text': 'one'}], 'document': 'one', 'questions': {}}}
    assert len({contract(case, role)[0][1]['content'] for role in ROLES}) == 1
    module, assets = layouts()
    assert len(module.states) == 729
    assert len(assets['fixed']['features']) == 6
    assert len(assets['synthesized']['features']) == 4


def test_operative_scope_requires_citations_and_preserves_an_unrelated_answer():
    case = {'data': {'indexed_spans': [{'id': 0, 'text': 'one'}]}}
    module, assets = layouts()
    reading = dict.fromkeys(module.fields, False)
    reading['use_limit_is_operative'] = reading['use_limit_binds_received_information'] = True
    for role, asset in assets.items():
        observations = residual.encode(asset['features'], reading)
        value = {'relations': observations, 'evidence': {'purpose_scope': [0, 0], 'no_rights_grant': []}}
        assert decode(case, role, {'finish_reason': 'stop', 'content': json.dumps(value)}) == (
            {'purpose_scope': {'answer': YES, 'evidence': [0]},
             'no_rights_grant': {'answer': ABSENT, 'evidence': []}}, None)
        value['evidence']['purpose_scope'] = []
        assert decode(case, role, {'finish_reason': 'stop', 'content': json.dumps(value)}) == (
            {'purpose_scope': {'answer': None, 'evidence': []},
             'no_rights_grant': {'answer': ABSENT, 'evidence': []}}, None)
