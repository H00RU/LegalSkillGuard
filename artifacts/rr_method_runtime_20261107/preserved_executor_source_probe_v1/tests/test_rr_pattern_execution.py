"""Offline tests of actual library invocation; these are not model evidence."""
from copy import deepcopy
import json

import pytest

from legal_skill_guard.rr.compilation import source_theory
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.engine import analyze
from legal_skill_guard.rr.learning import SkillLibrary


def case():
    source = {'dataset': 'SARA_v2_Binary', 'public': {
        'rules': 'The same person must pay and receive.',
        'facts': 'Alice paid Alice.', 'query': 'Is the payer the same person as the payee?'}}
    pattern = {'fields': ['entity_equality'], 'graphs': [{'op': 'join_on',
        'inputs': [{'slot': 'slot0'}, {'slot': 'slot1'}], 'params': {'keys': ['column0']}}],
        'basis': 'observed_source_collisions', 'universal_semantic_equivalence_claim': False}
    library = SkillLibrary()
    key = library.add(pattern, source='ProofWriter_OWA_depth5:offline_unit_fixture')
    library.frozen = True
    call = {'pattern': key, 'variant': 0, 'slots': {'slot0': 'payer', 'slot1': 'payee'},
            'columns': {'column0': 'person'}}
    graph = {'op': 'project_exists', 'inputs': [call]}
    bindings = [{'name': name, 'type': 'relation', 'source': 's1', 'value': {
        'columns': ['person'], 'rows': [['Alice']], 'closed': True}} for name in ('payer', 'payee')]
    proposal = {'answer': 'Contradiction', 'program': {'kind': 'connector', 'body': {
        'bindings': bindings, 'candidates': [graph], 'selected': 0, 'project': 'entailment_label',
        'source_links': {k: ['query'] for k in ('s0', 's1', 's2')}}},
        'compiled_units': ['s0', 's1', 's2'], 'unsupported_units': [], 'interfaces': []}
    return source, proposal, library.export(), key


def test_explicit_pattern_is_instantiated_and_executed_with_source_roles():
    source, proposal, library, key = case()
    before = digest(library)
    result = analyze(source, json.dumps(proposal), library=library)
    assert result['answer'] == 'Entailment' and not result['fallback_used']
    assert result['certificate_basis'] == 'source_completion_selected_connector_not_H'
    assert result['proposal'] == proposal
    use, = result['pattern_uses']
    assert use['pattern_hash'] == key and use['status'] == 'executed_main_program'
    assert use['role_bindings'] == {'slot0': 'payer', 'slot1': 'payee'}
    assert use['supporting_training_sources'] == ['ProofWriter_OWA_depth5:offline_unit_fixture']
    expanded = result['executable_proposal']['program']['body']['candidates'][0]
    assert expanded['inputs'][0]['op'] == 'join_on'
    assert 'pattern' not in expanded['inputs'][0]
    assert source_theory(source, result).version == result['completion_assessment']['theory_hash']
    assert digest(library) == before


def test_same_graph_without_library_reference_is_not_counted_as_reuse():
    source, proposal, library, _ = case()
    proposal['program']['body']['candidates'][0]['inputs'][0] = {'op': 'join_on',
        'inputs': [{'slot': 'payer'}, {'slot': 'payee'}], 'params': {'keys': ['person']}}
    result = analyze(source, json.dumps(proposal), library=library)
    assert result['answer'] == 'Entailment'
    assert result['pattern_uses'] == []


def test_library_mask_cannot_silently_supply_a_missing_pattern():
    source, proposal, _, _ = case()
    result = analyze(source, json.dumps(proposal), library={'patterns': []})
    assert result['program_status'] == 'invalid_IR'
    assert 'certificate' not in result
    assert any('unavailable' in d for d in result['diagnostics'])


@pytest.mark.parametrize('change', ['missing_slot', 'missing_column', 'unknown_column', 'unknown_variant'])
def test_pattern_application_does_not_invent_missing_semantics(change):
    source, proposal, library, _ = case()
    call = proposal['program']['body']['candidates'][0]['inputs'][0]
    if change == 'missing_slot':
        call['slots']['slot1'] = 'not_extracted'
    elif change == 'missing_column':
        call['columns'] = {}
    elif change == 'unknown_column':
        call['columns']['column0'] = 'not_a_public_column'
    else:
        call['variant'] = 2
    result = analyze(source, json.dumps(proposal), library=library)
    assert result['program_status'] == 'invalid_IR'
    assert 'certificate' not in result


def test_expanding_an_unselected_candidate_is_not_main_path_use():
    source, proposal, library, _ = case()
    graph = deepcopy(proposal['program']['body']['candidates'][0])
    proposal['program']['body']['candidates'] = [
        {'op': 'project_exists', 'inputs': [{'slot': 'payer'}]}, graph]
    result = analyze(source, json.dumps(proposal), library=library)
    assert result['answer'] == 'Entailment'
    use, = result['pattern_uses']
    assert use['candidate'] == 1
    assert use['status'] == 'expanded_unselected_candidate'
