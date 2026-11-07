"""Real rejected queries and current task-only compiler messages."""
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from legal_skill_guard.rr.source_program import compiler_prompt, program_schema


ROOT = Path(__file__).resolve().parents[1]


def material():
    fixture = json.loads((ROOT / 'tests/fixtures/rr_actual_method_c6_native_queries.json').read_text())
    public = json.loads((ROOT / 'data/packets/rr_v2/public_train.json').read_text())
    return fixture, {source['key']: source for source in public['sources']}


def test_actual_wrong_native_queries_are_rejected_without_changing_responses():
    fixture, sources = material()
    assert len(fixture['records']) == 3
    for record in fixture['records']:
        assert hashlib.sha256(record['content'].encode()).hexdigest() == record['content_sha256']
        program = json.loads(record['content'])
        jsonschema.Draft202012Validator(fixture['old_query_schema']).validate(program['query'])
        schema = program_schema(sources[record['source']])
        query = {'$defs': schema['$defs'], **schema['properties']['query']}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(query).validate(program['query'])


def test_current_prompt_preserves_actual_units_and_removes_unrelated_semantics():
    fixture, sources = material()
    for record in fixture['records']:
        _, user = compiler_prompt(sources[record['source']])
        payload = json.loads(user)
        assert payload['units'] == record['old_units']
        assert list(payload)[-1] == 'units'
        assert 'format_only_example' not in payload
        assert payload['previous_candidate'] is None
        schema = program_schema(sources[record['source']])
        for binding in schema['$defs']['binding']['anyOf']:
            assert list(binding['properties']) == ['name', 'type', 'sources', 'value']
            assert binding['required'] == ['name', 'type', 'sources', 'value']


def test_result_type_constraints_preserve_strings_inside_comparisons():
    _, sources = material()
    for dataset, answer in [('SARA_v2_Binary', 'Entailment'), ('ProofWriter_OWA_depth5', 'Unknown'),
                            ('ContractNLI', 'NotMentioned'), ('RuleArena_Airline', 0), ('OpenExempt', None)]:
        source = next(s for s in sources.values() if s['dataset'] == dataset)
        schema = program_schema(source)
        query_schema = {'$defs': schema['$defs'], **schema['properties']['query']}
        # These are syntax witnesses only, not benchmark answers or core proofs.
        query = {'op': 'if', 'args': [{'op': 'eq', 'args': ['ordinary public string', 'Entailment']}, answer, answer]}
        jsonschema.Draft202012Validator(query_schema).validate(query)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(query_schema).validate({'op': 'if', 'args': [True, answer]})
