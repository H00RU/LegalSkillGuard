from copy import deepcopy
import json

import jsonschema

from experiments import legal_skill_evolution_observation_component_execute as execution
from legal_skill_guard.skill_evolution.decoder_constraints import decoding_schema


def test_real_teacher_conditional_retains_structural_checks_and_original_host():
    library = execution.libraries()['CoverageRecombine/1']
    component = next(c for c in library['components'] if c['id'] == 'source_native_facts')
    original = json.loads(component['schema_json'])
    before = deepcopy(original)
    wire, checks = decoding_schema(original)
    assert original == before
    assert any('/allOf/' in path for path in checks)
    assert 'allOf' not in wire['properties']['views']['items']
    assert wire['properties']['views']['items']['properties']['facts']['items']['oneOf']
    # Conditional constraints are still enforced by the unchanged host schema.
    invalid = {'views': [{'extraction_status': 'complete', 'facts': None,
        'negative_givens': None, 'witnesses': []}]}
    assert list(jsonschema.Draft202012Validator(original).iter_errors(invalid))


def test_supported_nonconditional_allof_is_not_discarded():
    original = {'allOf': [{'type': 'integer'}, {'minimum': 3}]}
    wire, checks = decoding_schema(original)
    assert wire == original and checks == []
