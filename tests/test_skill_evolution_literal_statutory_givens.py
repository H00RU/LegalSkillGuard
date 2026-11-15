"""Actual paid TRAIN errors: source citation guards before and after decoding."""
from copy import deepcopy

import jsonschema
import pytest

from experiments import legal_skill_evolution_mixed_component_training as train
from legal_skill_guard.skill_evolution.generic_event_observation import schema_for
from legal_skill_guard.skill_evolution.literal_statutory_givens import admissible, constrain, validate_givens
from legal_skill_guard.skill_evolution.observation_component_library import observation_schema


@pytest.fixture(scope='module')
def actual():
    bank = train.actor.acquisition.previous.parent.OUT
    public = {s['key']: s['views'][0]['public'] for s in train.read(bank / 'SARA_corrected_TRAIN_views.json')}
    kernels = {r['source']: train.actor.acquisition.current_case_interface(r['kernel'])
               for r in train.read(bank / 'SARA_native_kernel_bank.json')}
    rows = train.read(train.ROOT / 'artifacts/legal_skill_evolution_observation_TRAIN_replay_20261115/result.json')['rows']
    checkpoint = train.read(train.OUT / 'B8/checkpoint.json')
    libraries = {arm: train.read(train.ROOT / checkpoint['libraries'][arm]['path']) for arm in train.ARMS}
    return public, kernels, rows, libraries


@pytest.mark.parametrize('arm,cid', [('CoverageRecombine', 'source_economic_legal_ledger_b8'),
                                   ('FreeGlobalUpdate', 'explicit_legal_givens')])
def test_actual_paid_general_151_response_is_rejected_by_source_guarded_schema(actual, arm, cid):
    public, kernels, rows, libraries = actual
    row = next(r for r in rows if r['candidate'] == arm and r['source'].startswith('SARA_v2_Binary:1ff7'))
    sid = row['source']
    raw = {cid: row['observation'][cid]}
    before = observation_schema(libraries[arm], [cid])
    assert jsonschema.Draft202012Validator(before).is_valid(raw)
    after = constrain(before, public[sid], kernels[sid])
    assert not jsonschema.Draft202012Validator(after).is_valid(raw)
    assert admissible(public[sid]) == set()
    # Unknown remains unknown; the compiler does not turn null into an empty
    # successfully extracted channel.
    unread = deepcopy(raw)
    unread[cid]['views'][0]['extraction_status'] = 'unread'
    unread[cid]['views'][0]['exact_givens'] = None
    assert jsonschema.Draft202012Validator(after).is_valid(unread)


def test_actual_valid_152c1_observation_survives_unchanged(actual):
    public, kernels, rows, libraries = actual
    row = next(r for r in rows if r['candidate'] == 'CoverageRecombine'
               and r['source'].startswith('SARA_v2_Binary:a519'))
    sid, cid = row['source'], 'source_economic_legal_ledger_b8'
    value = {cid: row['observation'][cid]}
    schema = constrain(observation_schema(libraries['CoverageRecombine'], [cid]), public[sid], kernels[sid])
    jsonschema.validate(value, schema)
    assert value[cid]['views'][0]['exact_givens']
    assert all(g['predicate'] == 's152_c_1' for g in value[cid]['views'][0]['exact_givens'])
    validate_givens(row['grounded']['bindings'][0]['inputs'], public[sid])


def test_question_and_statute_citations_cannot_enable_case_premises(actual):
    public, kernels, rows, _ = actual
    sid = next(s for s in public if s.startswith('SARA_v2_Binary:1ff7'))
    pub = {**public[sid], 'question': 'Section 151(b) applies?', 'source_text': 'Section 151(b)'}
    assert admissible(pub) == set()
    schema = schema_for(kernels[sid], pub)
    assert schema['properties']['givens']['maxItems'] == 0
    assert schema['properties']['status']['enum'] == ['complete', 'unread']


def test_fabricated_exact_given_is_rejected_for_both_polarities(actual):
    public, _, _, _ = actual
    pub = next(v for k, v in public.items() if k.startswith('SARA_v2_Binary:1ff7'))
    given = {'predicate': 's151_b', 'arguments': ['Alice', 2000, 2017]}
    for field in ('facts', 'negative_givens'):
        binding = {'facts': [], 'negative_givens': [], 'extraction_status': 'complete'}
        binding[field].append(given)
        with pytest.raises(ValueError, match='literal citation'):
            validate_givens(binding, pub)


def test_given_decoder_mask_is_common_to_generic_and_acquired_representations(actual):
    public, kernels, _, _ = actual
    sid = next(s for s in public if s.startswith('SARA_v2_Binary:30b162'))
    schema = schema_for(kernels[sid], public[sid])
    allowed = {branch['properties']['predicate']['enum'][0]
               for branch in schema['properties']['givens']['items']['oneOf']}
    assert allowed == {'s151_b', 's151_b_applies'}
