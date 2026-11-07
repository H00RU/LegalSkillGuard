"""Business-entry regressions for the readiness gaps, using artificial TRAIN microcases."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.engine import analyze, proposal_schema
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.preflight import ingest_source
from legal_skill_guard.rr.routing import route_prediction
from legal_skill_guard.rr.source_learning import learn_source

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'configs/rr_v2_preflight.json').read_text())['executor']


def artificial_counter(prompt):
    # Mock cost only: exact serving-token costs are checked separately, never
    # reported from this artificial byte counter as measured model tokens.
    return {'count': len(json.dumps(prompt, ensure_ascii=False).encode())}


def xor_case():
    source = {'key': 'artificial:existing_xor', 'dataset': 'RuleArena_Airline', 'public': {
        'rules': 'General rule: pay the base iff exception XOR gift.\nBoolean b_exception = true.\nBoolean b_gift = false.\nBoolean b_unrelated = true.',
        'prompt': 'Base is 80.'}}
    source['content_hash'] = digest(source['public'])
    first = {'answer': 0, 'program': {'kind': 'expression', 'body': {
        'bindings': [{'name': 'n_base', 'type': 'integer', 'value': 80, 'source': 's4'}],
        'query': {'op': 'if', 'args': [{'op': 'xor', 'args': [{'var': 'b_exception'}, {'var': 'b_gift'}]}, {'var': 'n_base'}, 0]},
        'source_links': {'s0': ['query'], 's4': ['binding:n_base']}}},
        'compiled_units': ['s0', 's4'], 'unsupported_units': [], 'interfaces': []}
    second = deepcopy(first)
    second['program']['body']['bindings'] += [
        {'name': 'b_exception', 'type': 'scalar', 'value': True, 'source': 's1'},
        {'name': 'b_gift', 'type': 'scalar', 'value': False, 'source': 's2'}]
    second['compiled_units'] += ['s1', 's2']
    return source, [first, second]


class Scope:
    def __init__(self): self.views = []
    def _source(self, source): assert source.startswith('artificial:')
    def reserve_oracle(self, source, key):
        self._source(source)
        assert (source, key) not in self.views and len(self.views) < 4
        self.views.append((source, key))


def test_actual_OFF_125_failure_cannot_pass_current_wire_program_contract():
    from legal_skill_guard.rr.data_store import PreflightData
    from legal_skill_guard.rr.wire_validation import WireValidator
    failure=json.loads((ROOT/'tests/fixtures/rr_actual_failure_125.json').read_text())
    data=PreflightData(ROOT,ROOT/'reports/rr_v2_evidence/data_manifest.json')
    source=data.public(failure['source'])
    proposal=json.loads(failure['raw_content'])
    assert proposal==failure['proposal'] and failure['thinking_requested'] is False
    assert proposal['program']['body']['bindings'][0]['type']=='string'
    assert 'query' not in proposal['program']['body']
    schema=proposal_schema(source['dataset'],source=source)
    assert not WireValidator(schema).is_valid(proposal)
    # Test the actual binding's type failure independently of missing query and
    # other invalid fields; do not adapt the old response into a passing result.
    v=jsonschema.Draft202012Validator({'$defs':schema['$defs'],'$ref':'#/$defs/expression_binding'})
    assert not v.is_valid(proposal['program']['body']['bindings'][0])
    assert analyze(source,failure['raw_content'])['program_status']=='invalid_IR'
    assert json.loads(failure['raw_content'])==failure['proposal']


def test_A_ingestion_and_frozen_prediction_plan_actual_second_request(tmp_path):
    source, proposals = xor_case()
    calls = []
    def call(**kw):
        step = int(kw['call_id'].rsplit(':', 1)[1])
        jsonschema.validate(proposals[step], kw['schema'])
        calls.append(kw)
        return {'content': json.dumps(proposals[step]), 'request_hash': digest(kw['prompt']), 'usage': {}, 'elapsed_seconds': 0}
    trace = {}
    def learner(s, grade, oracle, *, proposal=None):
        return learn_source(s, grade, oracle, proposal=proposal, trace=trace)
    record = ingest_source(source=source, grade={'answer': 80, 'reference_arguments': {'bag_list': []}},
        library=SkillLibrary(), thinking=True, call=call, learner=learner, ledger=Scope(), artifacts=tmp_path,
        binding={}, purpose='pilot_ingestion', id_prefix='artificial', offline_mock=True,
        tokenize=artificial_counter, request_config=CONFIG)
    assert record['calls'][0]['analysis']['program_status'] == 'partially_compiled_expression'
    assert record['calls'][0]['analysis']['candidate_answer'] is None
    action = record['translation_actions'][0]
    assert action['joint_separation_complete'] and action['selected'] == ['s1', 's2']
    assert action['context_closure'] == ['s0', 's1', 's2', 's4']
    sent = calls[1]['prompt'][1]['content']
    assert 'Boolean b_unrelated' not in sent
    assert sent.count('General rule:') == sent.count('Base is 80.') == 1
    assert record['analysis']['answer'] == 80 and record['analysis']['certificate_status'] == 'completion_stable'
    assert record['analysis']['residual_units'] == ['s3']
    assert action['batch_plan']['cost'] == artificial_counter(calls[1]['prompt'])['count']
    assert trace['candidate_generator_invoked'] and trace['candidate_generation_status'] == 'typed_inputs_unavailable'
    # The actual frozen prediction route independently reconstructs the theory;
    # no precomputed plan, assessment, learner result or source snapshot is injected.
    generated = []
    def generate(prompt, **kw):
        generated.append(prompt)
        return {'content': json.dumps(proposals[kw['step']])}
    generate.is_offline_mock = True
    routed = route_prediction(source, arm='M11', library=SkillLibrary(frozen=True).export(), generate=generate,
        protocol={}, partition='train', offline_mock=True, tokenize=artificial_counter, request_config=CONFIG)
    assert routed['model_calls'] == 2 and routed['result']['answer'] == 80
    assert routed['translation_actions'][0]['selected'] == ['s1', 's2']
    assert 'Boolean b_unrelated' not in generated[1][1]['content']


def test_A_does_not_turn_unknown_scope_or_wrong_public_literal_into_completion():
    source, proposals = xor_case()
    wrong = deepcopy(proposals[1])
    wrong['program']['body']['bindings'][-1]['value'] = True
    assert analyze(source, json.dumps(wrong))['certificate_status'] != 'completion_stable'
    source['public']['rules'] += '\nUnless an unmodeled exception overrides everything.'
    # The old prompt is now s5 rather than s4. Preserve correct provenance;
    # the new unrecognized clause must remain unknown, not silently disappear.
    changed = deepcopy(proposals[1])
    changed['program']['body']['bindings'][0]['source'] = 's5'
    changed['program']['body']['source_links'].pop('s4')
    changed['program']['body']['source_links']['s5'] = ['binding:n_base']
    changed['compiled_units'] = ['s0', 's1', 's2', 's5']
    result = analyze(source, json.dumps(changed))
    assert result['certificate_status'] != 'completion_stable'
    assert result['completion_assessment']['unknown_scope'] == ['s4']


def test_A_partial_public_ProofWriter_grammar_reaches_joint_batch_and_stable_remainder():
    source = {'key': 'artificial:existing_same_witness', 'dataset': 'ProofWriter_OWA_depth5', 'public': {
        'answer_type': 'three_valued_owa', 'facts': ['Bob is red.', 'Bob is nice.', 'Alice is blue.'],
        'rules': ['If someone is red and nice then they are young.'], 'query': 'Bob is young.'}}
    first = {'answer': 'Unknown', 'program': {'kind': 'public_horn', 'body': {}},
             'compiled_units': ['s3', 's4'], 'unsupported_units': [], 'interfaces': []}
    second = {**first, 'answer': 'True', 'compiled_units': ['s0', 's1', 's3', 's4']}
    requests = []
    def generate(prompt, **kw):
        proposal = [first, second][kw['step']]
        jsonschema.validate(proposal, kw['schema'])
        requests.append(prompt)
        return {'content': json.dumps(proposal)}
    generate.is_offline_mock = True
    result = route_prediction(source, arm='M11', library=SkillLibrary(frozen=True).export(), generate=generate,
        protocol={}, partition='train', offline_mock=True, tokenize=artificial_counter, request_config=CONFIG)
    action = result['translation_actions'][0]
    assert action['selected'] == ['s0', 's1'] and action['joint_separation_complete']
    assert action['context_closure'] == ['s0', 's1', 's3', 's4']
    assert 'Alice is blue.' not in requests[1][1]['content']
    assert result['model_calls'] == 2 and result['result']['answer'] == 'True'
    assert result['result']['residual_units'] == ['s2'] and not result['result']['fallback_used']
    assert result['result']['certificate']['completion_count'] == 2
    assert result['result']['certificate_basis'] == 'partial_public_Horn_complete_fact_observations_not_H'


def allowance_case():
    source = {'key': 'artificial:existing_allowance_order', 'dataset': 'RuleArena_Airline', 'public': {
        'rules': 'Each checked bag costs its weight in dollar. Owner family, period year, shared allowance 100, input_order. Return first remainder plus twice the second.',
        'prompt': '1. A carry-on: 10 x 10 x 10 inches, 10 lbs;\n2. First checked bag: 20 x 20 x 20 inches, 80 lbs;\n3. Second checked bag: 30 x 30 x 30 inches, 120 lbs;'}}
    source['content_hash'] = digest(source['public'])
    def amount(name, value, src):
        return {'name': name, 'type': 'amount', 'source': src, 'value': {'value': value,
            'unit': 'dollar', 'owner': 'family', 'period': 'year', 'lineage': [name], 'stage': 'element'}}
    key = ['shared', 'family', 'year']
    bindings = [amount('first', 80, 's2'), amount('second', 120, 's3'),
        {'name': 'items', 'type': 'slot_list', 'value': ['first', 'second'], 'source': 's0'},
        {'name': 'bank', 'type': 'allowance_bank', 'source': 's0', 'value': [
            {'key': key, 'balance': 100, 'policy': 'input_order', 'order_observable': True}]},
        {'name': 'key', 'type': 'resource_key', 'source': 's0', 'value': key}]
    graph = {'op': 'thread_allowance', 'inputs': [{'slot': 'items'}], 'params': {'bank_slot': 'bank', 'key_slot': 'key'}}
    proposal = {'answer': 200, 'program': {'kind': 'connector', 'body': {
        'bindings': bindings, 'candidates': [graph], 'selected': 0, 'project': 'amount_values', 'source_links': {},
        'query': {'op': 'add', 'args': [{'var': 'n_result_0'}, {'op': 'scale', 'args': [2, {'var': 'n_result_1'}]}]}}},
        'compiled_units': [], 'unsupported_units': [], 'interfaces': []}
    grade = {'answer': 200, 'reference_arguments': {'bag_list': [
        {'size': [10, 10, 10], 'weight': 10}, {'size': [20, 20, 20], 'weight': 80}, {'size': [30, 30, 30], 'weight': 120}]}}
    return source, proposal, grade


def test_B_non_ProofWriter_learning_executes_candidates_through_ingestion_and_freezes(tmp_path, monkeypatch):
    source, proposal, grade = allowance_case()
    # Only the artificial microcase's reference is supplied. The production
    # learner, candidate generator, binder, execution and durable accounting run.
    def reference(s, g, view):
        first, second = [b['weight'] for b in view['arguments']['bag_list'][1:]]
        used_first = min(first, 100)
        return first - used_first + 2 * max(0, second - (100 - used_first))
    monkeypatch.setattr('legal_skill_guard.rr.source_learning.evaluate_reference', reference)
    scope, trace = Scope(), {}
    def learner(s, g, oracle, *, proposal=None):
        return learn_source(s, g, oracle, proposal=proposal, trace=trace)
    def call(**kw):
        jsonschema.validate(proposal, kw['schema'])
        return {'content': json.dumps(proposal), 'request_hash': digest(kw['prompt']), 'usage': {}, 'elapsed_seconds': 0}
    record = ingest_source(source=source, grade=grade, library=SkillLibrary(), thinking=True, call=call,
        learner=learner, ledger=scope, artifacts=tmp_path, binding={}, purpose='pilot_ingestion',
        id_prefix='artificial', offline_mock=True)
    learned = record['learning']
    assert trace['candidate_generator_invoked'] and trace['initial_candidates'] > 1
    assert {'membership', 'owner_period_keys', 'contribution_lineage', 'aggregation_stage',
            'balance', 'allocation_policy', 'order_observable'} <= set(trace['typed_metadata_fields'])
    assert learned['connector_synthesis_status'] == 'executed_typed_source_candidates'
    # Swapping observable ordered amounts is not a same-I/O collision. This
    # fixture validates execution/allocation, not collision-driven learning.
    assert not learned['refinement']['collisions'] and learned['learned_pattern'] is None
    assert trace['selected_connector_semantics']
    assert all(x['prediction'] == x['reference_answer'] for x in trace['selected_connector_semantics'])
    assert len(scope.views) == 0
    assert record['analysis']['candidate_answer'] == 200
    assert record['analysis']['certificate_status'] != 'completion_stable'  # H is not Omega
    library = SkillLibrary()
    path = tmp_path / 'partial_library.frozen.json'
    library.freeze(path)
    assert SkillLibrary.restore(path).export() == library.export()


def test_original_malformed_interfaces_are_rejected_by_both_wire_and_parser():
    from legal_skill_guard.rr.data_store import PreflightData
    data = PreflightData(ROOT, ROOT / 'reports/rr_v2_evidence/data_manifest.json')
    rows = json.loads((ROOT / 'reports/rr_v2_evidence/semantic_preflight/source_status.json').read_text())
    for index in [4, 9, 14, 19]:
        item = rows[index]
        source = data.public(item['source'])
        record = json.loads((ROOT / item['source_record']).read_text())
        raw = record['calls'][-1]['raw_content']
        if index != 19:
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(json.loads(raw), proposal_schema(source['dataset'], source=source))
            result = analyze(source, raw)
            assert result['program_status'] == 'parse_failure'
            assert result['answer'] == 'NotMentioned'  # separately marked native fallback
            assert result['certificate_status'] != 'completion_stable'
        else:
            jsonschema.validate(json.loads(raw), proposal_schema(source['dataset'], source=source))
            assert analyze(source, raw)['certificate_status'] == 'unsupported_no_certificate'


def test_original_invalid_programs_reach_repair_without_becoming_a_planning_theory():
    from legal_skill_guard.rr.data_store import PreflightData
    from legal_skill_guard.rr.compilation import prepare_request
    data = PreflightData(ROOT, ROOT / 'reports/rr_v2_evidence/data_manifest.json')
    rows = json.loads((ROOT / 'reports/rr_v2_evidence/semantic_preflight/source_status.json').read_text())
    checked = 0
    for item in rows:
        source = data.public(item['source'])
        record = json.loads((ROOT / item['source_record']).read_text())
        for call in record['calls']:
            previous = analyze(source, call['raw_content'])
            if previous['program_status'] not in {'invalid_IR', 'parse_failure'}:
                continue
            request = prepare_request(source, previous=previous)
            assert request['action']['selection_basis'] in {'conservative_full_source_no_separation_claim', 'full_source_IR_repair'}
            assert request['messages']
            checked += 1
    assert checked >= 3


def test_MB_keeps_the_same_numeric_projection_and_paid_view_as_B_without_field_refinement():
    from legal_skill_guard.rr.example_synthesis import fit_shared_examples, filter_shared_examples
    source, proposal, grade = allowance_case()
    args = deepcopy(grade['reference_arguments'])
    args['bag_list'][1]['weight'], args['bag_list'][2]['weight'] = 120, 80
    record = {'source': source['key'], 'calls': [{'analysis': {'proposal': proposal}}],
        'learning': {'oracle_views': [{'view': {'kind': source['dataset'], 'arguments': args}, 'answer': 180}]}}
    model = fit_shared_examples({source['key']: source}, [record], {source['key']: grade})
    assert model['content']['families'] and model['content']['families'][0]['examples'] == 2
    assert model['content']['families'][0]['accepted_graphs']
    filtered, evidence = filter_shared_examples(proposal, source, model)
    assert filtered['program']['body']['candidates'] == proposal['program']['body']['candidates']
    assert evidence['removed'] == 0 and model['content']['extra_model_calls'] == 0
    assert 'refinement' not in model['content']


def test_B_SARA_uses_a_renderable_fact_edit_and_real_join_execution(tmp_path, monkeypatch):
    source = {'key': 'artificial:existing_entity_join', 'dataset': 'SARA_v2_Binary', 'public': {
        'rules': 'The claim holds iff the same person paid and received.',
        'facts': 'Alice paid Bob.', 'query': 'Did the same person pay and receive?'}}
    source['content_hash'] = digest(source['public'])
    prefix = 'agent_(payment,"Alice").\npatient_(payment,"Bob").\nperson_("Alice").\nperson_("Bob").\n'
    monkeypatch.setattr('legal_skill_guard.rr.source_learning.sara_case', lambda grade: (prefix, 'same_person'))
    def reference(s, g, view):
        left, right = 'Alice', 'Bob'
        edit = view['edit']
        assert edit['scope'] == 'all_fact_occurrences'
        left = edit['new'] if left == edit['old'] else left
        right = edit['new'] if right == edit['old'] else right
        return 'Entailment' if left == right else 'Contradiction'
    monkeypatch.setattr('legal_skill_guard.rr.source_learning.evaluate_reference', reference)
    bindings = [{'name': name, 'type': 'relation', 'source': 's1', 'value': {
        'columns': ['person'], 'rows': [[person]], 'closed': True}} for name, person in [('payer','Alice'),('payee','Bob')]]
    graph = {'op': 'project_exists', 'inputs': [{'op': 'join_on', 'inputs': [{'slot': 'payer'},{'slot': 'payee'}],
             'params': {'keys': ['person']}}]}
    proposal = {'answer': 'Contradiction', 'program': {'kind': 'connector', 'body': {
        'bindings': bindings, 'candidates': [graph], 'selected': 0, 'project': 'entailment_label', 'source_links': {}}},
        'compiled_units': [], 'unsupported_units': [], 'interfaces': []}
    trace = {}
    def learner(s, g, oracle, *, proposal=None):
        return learn_source(s, g, oracle, proposal=proposal, trace=trace)
    def call(**kw):
        jsonschema.validate(proposal, kw['schema'])
        return {'content': json.dumps(proposal), 'request_hash': digest(kw['prompt']), 'usage': {}, 'elapsed_seconds': 0}
    scope = Scope()
    record = ingest_source(source=source, grade={'answer':'Contradiction'}, library=SkillLibrary(), thinking=True,
        call=call, learner=learner, ledger=scope, artifacts=tmp_path, binding={},
        purpose='pilot_ingestion', id_prefix='artificial', offline_mock=True)
    assert trace['candidate_generator_invoked'] and trace['retained_candidates']
    assert record['learning']['connector_synthesis_status'] == 'executed_typed_source_candidates'
    assert record['learning']['learned_pattern']['fields'] == ['entity_equality']
    assert len(scope.views) == 2 and not trace['unbound_primitive_views']
    assert all(x['prediction'] == x['reference_answer'] for x in trace['selected_connector_semantics'])
