import json
from types import SimpleNamespace

import pytest

from experiments import convergence_oe_conditioned_value_probe as conditioned_probe
from experiments.convergence_oe_scoped_proposal import (
    OWNERSHIP_FIELD, PROJECTION_FIELD, SCOPED_SCHEMA, native_asset_counts, projection_policy, scoped_program,
)
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.openexempt import answer_schema
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor


def test_full_native_read_does_not_receive_local_title_policy(tmp_path):
    projection = 'Local policy for the single requested title component.'
    ownership = 'Keep source-supported title distinct from possession.'
    reply = {'predicate_prompt': 'Evaluate the complete public asset list.', 'schema_mode': 'native',
             'predicate_schema_json': '{}', 'rationale': '', OWNERSHIP_FIELD: ownership, PROJECTION_FIELD: projection,
             'compose_source': 'def compose(inputs, predict, extractors):\n    return predict("read", inputs)\n'}
    assert not strict_output_schema_issues(SCOPED_SCHEMA)
    program = scoped_program(reply, ['synthetic_train_source'])
    legacy = {key: value for key, value in program.items() if key != PROJECTION_FIELD}
    query = {'requested_component': 'forwarded', 'independently_verified_source_facts': {'stated_value_dollars': 500}}
    assert projection_policy(program, query) == ownership + '\nRequested-component computation:\n' + projection
    assert projection_policy(legacy, query) == reply['predicate_prompt'] + '\nSource-level ownership rules:\n' + ownership
    with pytest.raises(ValueError, match='local source-conditioned input'):
        projection_policy(program, {'requested_component': 'forwarded'})

    public = {'original_input': '11 U.S.C. § 522(d)\nSolved Reasoning Steps: The debtor may claim property exemptions '
                                'under Federal statutes.\nFacts:\nA table costs $500.00 and a lamp costs $70.00.'}
    source = {'dataset': 'OpenExempt', 'key': 'synthetic_train_source',
              'views': [{'id': 'EV', 'public': public, 'answer_schema': answer_schema('EV')}]}
    assets = [{'asset': 'table', 'claims': []}, {'asset': 'lamp', 'claims': []}]
    request_messages = []

    def generate(_call_id, **kwargs):
        request_messages.extend(kwargs['messages'])
        value = {'EV': {'answer': assets, 'evidence_sentence_ids': []}}
        return {'content': json.dumps({'value': value}), 'finish_reason': 'stop', 'usage': {'total_tokens': 2},
                'elapsed_seconds': 0}

    executor = SimpleNamespace(ledger=SimpleNamespace(run_id='synthetic_scope_test'), generate=generate)
    actor = ProgramActor(executor, tmp_path, max_calls=1, physical_verifier=lambda **_kwargs: None)
    result = actor.execute(program, source, 'skill_actor')
    assert result['native']['EV']['answer'] == {'table': [], 'lamp': []}
    assert ownership in request_messages[0]['content']
    assert all(projection not in row['content'] for row in request_messages)
    assert native_asset_counts([source], {source['key']: result}, {source['key']: {'EV': {'answer': {'a': [], 'b': []}}}}) == [
        {'source': source['key'], 'view': 'EV', 'reference_asset_count': 2, 'returned_asset_count': 2},
    ]


def test_projection_prompt_cannot_store_visible_case_identifier():
    reply = {'predicate_prompt': 'Read the case.', 'schema_mode': 'native', 'predicate_schema_json': '{}',
             'rationale': '', 'compose_source': '', OWNERSHIP_FIELD: 'Distinguish title from possession.',
             PROJECTION_FIELD: 'Apply this to private_case_identity.'}
    with pytest.raises(ValueError, match='projection policy must be reusable'):
        scoped_program(reply, ['private_case_identity'])


def test_conditioned_read_uses_projection_policy_and_preserves_legacy_wire(tmp_path, monkeypatch):
    native = 'Read every asset in the supplied native facts.'
    local = 'Return the requested title-filtered part from the audited amount.'
    previous = {'predicates': [{'prompt': native}]}
    scoped = {**previous, PROJECTION_FIELD: local}
    source = {'text': 'The debtor possesses a lamp worth $70.00.'}
    case = SimpleNamespace(source_id='synthetic_variant', root_id='synthetic_train_source', public=source)
    query = {'source': source['text'], 'requested_component': 'withheld',
             'independently_verified_source_facts': {'stated_value_dollars': 70}}
    messages = []

    def generate(_call_id, **kwargs):
        assert kwargs['thinking'] is False and kwargs['schema'] == conditioned_probe.SCHEMA
        messages.append(kwargs['messages'])
        return {'content': '{"value": 0}', 'finish_reason': 'stop', 'usage': {'total_tokens': 1}}

    monkeypatch.setattr(conditioned_probe, 'verify_physical_response', lambda *_args, **_kwargs: None)
    reader = SimpleNamespace(ledger=SimpleNamespace(run_id='offline_projection_scope'), generate=generate)
    for program in (previous, scoped):
        result, = conditioned_probe._measure(reader, tmp_path, [case], [query], program)
        assert result['value'] == 0

    assert messages[0] == [
        {'role': 'system', 'content': conditioned_probe.SYSTEM},
        {'role': 'user', 'content': json.dumps({**query, 'quoted_reader_policy': native}, ensure_ascii=False, sort_keys=True)},
    ]
    assert json.loads(messages[1][1]['content']) == {**query, 'quoted_reader_policy': local}


def test_literal_read_has_own_instructions_and_preserves_historical_request(tmp_path, monkeypatch):
    from experiments import convergence_m2_update_probe as update

    native = 'Return the full native answer for every case asset.'
    shared = 'Measured possession alone does not establish ownership.'
    derived = 'Compute only the requested derived title component.'
    reply = {'predicate_prompt': native, 'schema_mode': 'native', 'predicate_schema_json': '{}', 'rationale': '',
             'compose_source': 'def compose(inputs, predict, extractors):\n    return predict("read", inputs)\n',
             OWNERSHIP_FIELD: shared, PROJECTION_FIELD: derived}
    versions = (scoped_program(reply, ()), scoped_program(reply, (), literal_wire=True))
    assert versions[0]['predicates'] == versions[1]['predicates']
    assert versions[0][PROJECTION_FIELD] == versions[1][PROJECTION_FIELD]
    assert OWNERSHIP_FIELD not in versions[0] and versions[1][OWNERSHIP_FIELD] == shared
    public = {'text': 'The debtor possesses a lamp valued at $70.00.', 'asset': 'lamp'}
    case = SimpleNamespace(source_id='synthetic_variant', root_id='synthetic_train_source', public=public)
    requests = []

    def generate(identity, *, source, purpose, messages, thinking, schema):
        requests.append((identity, messages, schema))
        assert (source, purpose, thinking) == (case.root_id, 'skill_actor', False)
        return {'content': '{"ownership":null,"stated_value":70}', 'finish_reason': 'stop',
                'usage': {'total_tokens': 5}}

    monkeypatch.setattr(update, 'verify_physical_response', lambda *_args, **_kwargs: None)
    reader = SimpleNamespace(ledger=SimpleNamespace(run_id='offline_literal_projection'), generate=generate)
    for program in versions:
        output, _ = update.measure_natural_projection(reader, tmp_path, program, case)
        assert output == {'ownership': None, 'stated_value': 70}

    assert native in requests[0][1][0]['content']
    assert json.loads(requests[0][1][1]['content']) == public
    assert requests[1][1][0]['content'] == update.LITERAL_PROJECTION_SYSTEM
    assert json.loads(requests[1][1][1]['content']) == {**public, 'quoted_ownership_policy': shared}
    assert native not in json.dumps(requests[1][1]) and derived not in json.dumps(requests[1][1])
    assert requests[0][0] != requests[1][0] and requests[0][2] == requests[1][2]
