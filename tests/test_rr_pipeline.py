"""State-machine acceptance on artificial data; never real model evidence."""
import hashlib
import json
import sqlite3
import tarfile
from pathlib import Path

import pytest

from legal_skill_guard.rr.controls import ARMS
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.engine import analyze
from legal_skill_guard.rr.engine import wire_messages as messages
from legal_skill_guard.rr.formal import FormalLedger, FormalRun, diagnostic_plan, dry_run
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.ledger import DATASETS, BudgetError, BudgetLedger
from legal_skill_guard.rr.partitions import Source, preflight_sources, split_sources
from legal_skill_guard.rr.preflight import Preflight, create_seal, seal_parser_repair
from legal_skill_guard.rr.public_horn import parse_public
from legal_skill_guard.rr.repair import seal_native_contract_repair, seal_oracle_processing_repair
from legal_skill_guard.rr.routing import apply_interfaces, route_prediction
from legal_skill_guard.rr.source_learning import DurableOracle, OracleUnavailable, learn_source

ROOT = Path(__file__).resolve().parents[1]


def test_actual_duplicate_asset_keys_are_rejected_without_merging_claims():
    from legal_skill_guard.rr.engine import proposal_schema
    from legal_skill_guard.rr.strict_contract import close_expression_inputs, strict_proposal_schema
    from legal_skill_guard.rr.wire_validation import WireValidator
    actual = json.loads(json.loads((ROOT / 'tests/fixtures/rr_actual_failure_95.json').read_text())['content'])
    before = json.loads(json.dumps(actual))
    schema = strict_proposal_schema('OpenExempt', proposal_schema('OpenExempt'), source_unit_ids=['s159'])
    schema = close_expression_inputs(schema, actual['program']['body']['bindings'])
    assert WireValidator(schema).is_valid(actual)
    from legal_skill_guard.rr.coverage import evaluate, Unsupported
    body = actual['program']['body']
    from legal_skill_guard.rr.engine import decode_slots
    slots, _ = decode_slots(body, {'s159'}, {'s159': 'Public input'})
    with pytest.raises(Unsupported, match='Duplicate'):
        evaluate(body['query'], slots)
    assert actual == before  # no merging/reordering/repairing the rejected program


def test_actual_invalid_JSON_cannot_be_consumed_by_citation_pattern():
    import re

    from legal_skill_guard.rr.strict_contract import CITATION_PATTERN
    actual = json.loads((ROOT / 'tests/fixtures/rr_actual_failure_94.json').read_text())
    with pytest.raises(json.JSONDecodeError):
        json.loads(actual['content'])
    malformed = 'A§B" } trailing§invalid'
    assert re.fullmatch(r'.+§.+', malformed)
    assert not re.fullmatch(CITATION_PATTERN, malformed)
    assert re.fullmatch(CITATION_PATTERN, '11 U.S.C. § 522(d)(3)')


def test_real_strict_failure_has_pathful_type_diagnostics_and_is_not_adaptable():
    import jsonschema

    from legal_skill_guard.rr.engine import decode_slots, proposal_schema
    from legal_skill_guard.rr.ir_types import IRTypeError, check_expression
    from legal_skill_guard.rr.raw_recovery import recover_format
    failure = json.loads((ROOT / 'tests/fixtures/rr_strict_actual_failure.json').read_text())
    content = failure['raw_response']['choices'][0]['message']['content']
    p = json.loads(content)
    source = {'dataset': 'OpenExempt', 'public': {'views': {}}}
    # Preserve the actual unit ID without any answer-driven change.
    from legal_skill_guard.rr.strict_contract import strict_proposal_schema
    schema = strict_proposal_schema('OpenExempt', proposal_schema(source['dataset']), source_unit_ids=['s157'])
    assert not jsonschema.Draft202012Validator(schema).is_valid(p)
    body = p['program']['body']
    slots, _ = decode_slots(body, {'s157'}, {'s157': 'Original full source stays in its immutable packet.'})
    with pytest.raises(IRTypeError) as caught:
        check_expression(body, slots)
    diagnostics = caught.value.diagnostics
    assert {'path': 'program.body.query.args[0]', 'expected': 'boolean', 'actual': ['string']} in diagnostics
    assert any(d['path'] == 'program.body.source_links.s157[0]' for d in diagnostics)
    adapted = recover_format(content)
    assert adapted['proposal'] == p and not adapted['missing_semantics_synthesized']


def test_prompt_examples_pass_schema_static_types_and_exact_execution():
    from legal_skill_guard.rr.compiler_prompt import format_examples
    from legal_skill_guard.rr.engine import _program, proposal_schema
    from legal_skill_guard.rr.strict_contract import strict_proposal_schema
    from legal_skill_guard.rr.wire_validation import validate_wire
    for example in format_examples():
        p = example['proposal']
        dataset = 'OpenExempt' if isinstance(p['answer'], dict) else 'SARA_v2_Binary' if isinstance(p['answer'], str) else 'RuleArena_Airline'
        schema = strict_proposal_schema(dataset, proposal_schema(dataset), source_unit_ids=['s0', 's1'])
        validate_wire(p, schema)
        value = _program(p['program'], {'s0', 's1'}, dict(zip(['s0', 's1'], example['public_text'].splitlines())))
        assert value['candidate_answer'] == p['answer']


def test_static_checker_checks_inactive_branches_and_variable_operand_types():
    from legal_skill_guard.rr.ir_types import IRTypeError, check_expression
    body = {'query': {'op': 'if', 'args': [True, 7, {'op': 'and', 'args': [{'var': 'text'}]}]}}
    with pytest.raises(IRTypeError) as caught:
        check_expression(body, {'text': 's0'})
    assert caught.value.diagnostics[0]['path'] == 'program.body.query.args[2].args[0]'


def test_new_real_failures_reject_numeric_keys_and_unbounded_generation():
    from copy import deepcopy

    from legal_skill_guard.rr.compiler_prompt import format_examples
    from legal_skill_guard.rr.engine import _decode_proposal, proposal_schema
    from legal_skill_guard.rr.strict_contract import EXPRESSION_DEPTH, strict_proposal_schema
    from legal_skill_guard.rr.wire_validation import WireValidator
    for number in [86, 87]:
        record = json.loads((ROOT / f'tests/fixtures/rr_actual_failure_{number}.json').read_text())
        if number == 87:
            with pytest.raises(ValueError, match='bounded JSON nesting'):
                _decode_proposal(record['content'])
        else:
            p = json.loads(record['content'])
            schema = strict_proposal_schema('OpenExempt', proposal_schema('OpenExempt'), source_unit_ids=['s159', 's160'])
            assert not WireValidator(schema).is_valid(p)
    p = deepcopy(format_examples()[0]['proposal'])
    schema = strict_proposal_schema('RuleArena_Airline', proposal_schema('RuleArena_Airline'), source_unit_ids=['s0', 's1'])
    assert list(schema['properties'])[0] == 'program'
    query = {'var': 'n_count'}
    for _ in range(EXPRESSION_DEPTH + 1):
        query = {'op': 'add', 'args': [query, 0]}
    p['program']['body']['query'] = query
    assert not WireValidator(schema).is_valid(p)
    p['program']['body']['query'] = {'op': 'add', 'args': [{'var': 's_count'}, 0]}
    assert not WireValidator(schema).is_valid(p)
    # A numeric variable can never serve as a string object key in the wire grammar.
    p = deepcopy(format_examples()[2]['proposal'])
    p['program']['body']['query']['args'][0]['args'][0] = {'var': 'n_value'}
    schema = strict_proposal_schema('OpenExempt', proposal_schema('OpenExempt'), source_unit_ids=['s0', 's1'])
    assert not WireValidator(schema).is_valid(p)


def test_actual_task_contract_omissions_expose_target_claim_and_total_cost():
    from legal_skill_guard.rr.engine import wire_messages
    failure = json.loads((ROOT / 'tests/fixtures/rr_actual_failure_89.json').read_text())
    assert failure['call_id'].startswith('cumulative:typed_contract_v2:SARA_v2_Binary:')
    # Verbatim public query, no expected label or reference program.
    query = 'Section 3306(b)(10)(A) applies to the payment of $12980 that Alice made in 2019.'
    source = {'dataset': 'SARA_v2_Binary', 'public': {'rules': 'Public rules.', 'facts': 'Public facts.', 'query': query}}
    prompt = wire_messages(source)
    assert prompt[1]['content'].endswith(json.dumps(query, ensure_ascii=False))
    assert 'not an additional fact' in prompt[0]['content']
    airline = wire_messages({'dataset': 'RuleArena_Airline', 'public': {'rules': '', 'prompt': 'A public trip.'}})
    assert 'including the supplied flight ticket' in airline[0]['content']


def test_actual_unbacked_boolean_cannot_enter_source_bound_wire_contract():
    from copy import deepcopy

    from legal_skill_guard.rr.engine import proposal_schema
    from legal_skill_guard.rr.wire_validation import WireValidator
    record = json.loads((ROOT / 'tests/fixtures/rr_actual_failure_90.json').read_text())
    p = json.loads(record['content'])
    source = {'dataset': 'SARA_v2_Binary', 'public': {'rules': '\n'.join(['No boolean literal.'] * 52),
        'facts': 'A payment of 12980 upon disability.', 'query': 'Does the rule apply?'}}
    schema = proposal_schema(source['dataset'], source=source)
    assert not WireValidator(schema).is_valid(p)
    assert all(b['properties']['value'].get('type') != 'boolean' for b in schema['$defs']['expression_binding']['anyOf'])
    source = deepcopy(source)
    source['public']['facts'] = 'The explicit input flag is true.'
    schema = proposal_schema(source['dataset'], source=source)
    boolean_branches = [b for b in schema['$defs']['expression_binding']['anyOf'] if b['properties']['value'].get('enum') == [True]]
    assert len(boolean_branches) == 1 and boolean_branches[0]['properties']['source']['enum'] == ['s52']


def test_real_missing_variable_repair_closes_inputs_without_inventing_citations():
    from copy import deepcopy

    from legal_skill_guard.rr.engine import proposal_schema
    from legal_skill_guard.rr.strict_contract import close_expression_inputs, strict_proposal_schema
    from legal_skill_guard.rr.wire_validation import WireValidator
    original = json.loads(json.loads((ROOT / 'tests/fixtures/rr_actual_failure_92.json').read_text())['content'])
    bindings = original['program']['body']['bindings']
    schema = strict_proposal_schema('OpenExempt', proposal_schema('OpenExempt'), source_unit_ids=['s159'])
    schema = close_expression_inputs(schema, bindings)
    assert not WireValidator(schema).is_valid(original)
    p = deepcopy(original)
    p['program']['body']['query'] = {'op': 'object', 'args': [
        {'op': 'pair', 'args': [family, {'op': 'object', 'args': [
            {'op': 'pair', 'args': [{'var': name}, {'op': 'array', 'args': []}]} for name in ['s_asset1', 's_asset2']]}]}
        for family in ['EC', 'EV']]}
    assert WireValidator(schema).is_valid(p)
    assert p['program']['body']['bindings'] == bindings
    bad = deepcopy(p)
    bad['program']['body']['query']['args'][0]['args'][1]['args'][0]['args'][0]['var'] = 's_citation1'
    assert not WireValidator(schema).is_valid(bad)
    bad = deepcopy(p)
    bad['program']['body']['bindings'][1]['value'] = 801
    assert not WireValidator(schema).is_valid(bad)


def test_real_native_output_type_failure_rejects_asset_citation_and_boolean_amount():
    from copy import deepcopy

    from legal_skill_guard.rr.compiler_prompt import format_examples
    from legal_skill_guard.rr.engine import proposal_schema
    from legal_skill_guard.rr.strict_contract import strict_proposal_schema
    from legal_skill_guard.rr.wire_validation import WireValidator
    actual = json.loads(json.loads((ROOT / 'tests/fixtures/rr_actual_failure_93.json').read_text())['content'])
    schema = strict_proposal_schema('OpenExempt', proposal_schema('OpenExempt'), source_unit_ids=['s159'])
    assert not WireValidator(schema).is_valid(actual)
    schema = strict_proposal_schema('OpenExempt', proposal_schema('OpenExempt'), source_unit_ids=['s0', 's1'])
    good = format_examples()[2]['proposal']
    assert WireValidator(schema).is_valid(good)
    bad = deepcopy(good)
    bad['program']['body']['query']['args'][1]['args'][1]['args'][0]['args'][1]['args'][0]['args'][1]['args'][1] = False
    assert not WireValidator(schema).is_valid(bad)


def test_cumulative_override_preserves_stop_history_and_caps_all_physical_requests(tmp_path):
    ledger, payloads, calls = round2_ledger_fixture(tmp_path)
    cid = next(iter(calls))
    source = calls[cid]['source']
    ledger.reserve(cid, role='executor', purpose='preflight_bug_retry', source=source,
                   request={'thinking': True, 'payload': payloads[cid]})
    ledger.finish(cid, status='completed', result={'raw': 'actual failure fixture shape'})
    ledger.record_strict_schema_validation(cid, {'pass': False, 'systemic_failure': True, 'reason': 'type failure'})
    with ledger.transaction() as db:
        old_rows = db.execute('SELECT * FROM calls').fetchall()
        old_meta = dict(db.execute('SELECT * FROM meta'))
    authorization = json.loads((ROOT / 'docs/rr_v2/cumulative_repair_authorization.json').read_text())
    ledger.register_cumulative_policy(authorization)
    ledger.register_repair_revision('v1', new_binding={'code_hash': 'v1', 'config_hash': 'f'},
                                    change='typed operands', offline_evidence_hash='checked')
    b = BudgetLedger(ledger.path, sources=ledger.spec['sources'], code_hash='v1', config_hash='f')
    plan = {'thinking': True, 'payload': {'revision': 'v1'}}
    b.register_repair_request('new0', revision='v1', source=source, payload_hash=digest(plan['payload']))
    b.reserve('new0', role='executor', purpose='preflight_bug_retry', source=source, request=plan)
    with pytest.raises(BudgetError, match='exact registered'):
        b.reserve('unplanned', role='executor', purpose='preflight_bug_retry', source=source, request=plan)
    b.finish('new0', status='failed', result={'wire': 'failed and charged'})
    b.record_repair_outcome('new0', {'pass': False, 'reason': 'typed error'})
    with pytest.raises(BudgetError, match='different'):
        b.register_repair_request('same', revision='v1', source=source, payload_hash='different')
    good = {'pass': True, 'typed_schema_pass': True, 'model_IR_executed': True,
            'source_grounding': {'pass': True}, 'program_native_score': {'task_correct': True}}
    # New revisions need actual change/evidence; this synthetic loop exercises the cap, not model quality.
    for i in range(1, 11):
        revision = f'v{i+1}'
        b.register_repair_revision(revision, new_binding={'code_hash': revision, 'config_hash': 'f'},
                                   change='specific recorded defect', offline_evidence_hash=str(i))
        b = BudgetLedger(b.path, sources=b.spec['sources'], code_hash=revision, config_hash='f')
        b.register_repair_request(f'new{i}', revision=revision, source=source, payload_hash=digest(plan['payload']))
        b.reserve(f'new{i}', role='executor', purpose='preflight_bug_retry', source=source, request=plan)
        b.finish(f'new{i}', status='completed', result={})
        b.record_repair_outcome(f'new{i}', good)
    assert b.export()['executor_used'] == 96
    b.register_repair_request('over', revision=revision, source=list(calls.values())[1]['source'], payload_hash=digest(plan['payload']), mode='continuation')
    with pytest.raises(BudgetError, match='Cumulative96'):
        b.reserve('over', role='executor', purpose='preflight_bug_retry', source=list(calls.values())[1]['source'], request=plan)
    with b.transaction() as db:
        assert db.execute('SELECT * FROM calls LIMIT 87').fetchall() == old_rows
        assert all(dict(db.execute('SELECT * FROM meta'))[k] == v for k, v in old_meta.items())


def test_union_pruning_preserves_standard_schema_acceptance():
    from jsonschema import Draft202012Validator

    from legal_skill_guard.rr.wire_validation import WireValidator
    schema = {'$defs': {'operation': {'anyOf': [
        {'type': 'object', 'required': ['op', 'args'], 'additionalProperties': False,
         'properties': {'op': {'enum': [op]}, 'args': {'type': 'array', 'items': {'type': kind},
                                                   'minItems': 1, 'maxItems': 2}}}
        for op, kind in [('and', 'boolean'), ('add', 'integer')]]}},
        'anyOf': [{'$ref': '#/$defs/operation'}, {'type': 'null'}]}
    standard, pruned = Draft202012Validator(schema), WireValidator(schema)
    from itertools import product
    for op, first, second in product(['and', 'add', 'unknown'], [1, True, 's0'], [2, False, None]):
        value = {'op': op, 'args': [first, second]}
        assert standard.is_valid(value) == pruned.is_valid(value)
    for value in [None, False, {}, [], {'op': 'and'}, {'op': 'add', 'args': [1], 'extra': 2}]:
        assert standard.is_valid(value) == pruned.is_valid(value)


def proposal(answer=100):
    return {"answer": answer, "program": {"kind": "unsupported", "body": {}},
            "compiled_units": [], "unsupported_units": [], "interfaces": []}


def ordinary_connector_case(left, right, key, *, slot_names=("left", "right"), column="person"):
    """Artificial closed-relation example; no research labels or model calls."""
    names = sorted(set(left + right))
    source = {"key": key, "dataset": "RuleArena_Airline", "public": {
        "rules": "Entities: " + " ".join(names), "prompt": "Check a shared witness."}}
    exact = {"op": "join_on", "params": {"keys": [column]},
             "inputs": [{"slot": slot_names[0]}, {"slot": slot_names[1]}]}
    erased = {"op": "join_on", "params": {"keys": []}, "inputs": [
        {"slot": slot_names[0]}, {"op": "bind_rename", "params": {"from": [column], "to": [column + "_other"]},
                                 "inputs": [{"slot": slot_names[1]}]}]}
    graphs = [{"op": "project_exists", "inputs": [g]} for g in (exact, erased)]
    bindings = [{"name": name, "type": "relation", "source": "s0", "value": {
        "columns": [column], "rows": [[x] for x in values], "closed": True}}
        for name, values in zip(slot_names, (left, right))]
    p = {**proposal(), "program": {"kind": "connector", "body": {"bindings": bindings, "candidates": graphs}}}
    record = {"source": key, "learning": {"oracle_views": []}, "calls": [{"analysis": {"proposal": p}}]}
    return source, record, {"answer": bool(set(left) & set(right))}


def test_MB_ordinary_examples_remove_wrong_connector_with_no_collision_fields_or_test_label():
    from legal_skill_guard.rr.example_synthesis import filter_shared_examples, fit_shared_examples
    examples = [ordinary_connector_case(["Bob"], ["Alice"], "train0"),
                ordinary_connector_case(["Bob"], ["Bob"], "train1")]
    model = fit_shared_examples({s["key"]: s for s, _, _ in examples},
                               [r for _, r, _ in examples], {s["key"]: y for s, _, y in examples})
    source, record, _ = ordinary_connector_case(["Eve"], ["John"], "unlabeled_new")
    p = record["calls"][0]["analysis"]["proposal"]
    filtered, evidence = filter_shared_examples(p, source, model)
    assert p["interfaces"] == [] and evidence["removed"] == 1
    assert len(filtered["program"]["body"]["candidates"]) == 1
    assert model["content"]["families"][0]["examples"] == 2
    assert not any(name in json.dumps(model) for name in ["Bob", "Alice", "Eve", "John", "train0", "train1"])
    assert not model["content"]["finite_candidate_pool_is_Omega"]


def test_MB_example_preparation_is_alpha_invariant_and_preserves_unresolved_graphs():
    from legal_skill_guard.rr.example_synthesis import filter_shared_examples, fit_shared_examples
    def fit(case):
        s, r, y = case
        return fit_shared_examples({s["key"]: s}, [r], {s["key"]: y})
    original = fit(ordinary_connector_case(["Bob"], ["Bob"], "sourceA"))
    renamed = fit(ordinary_connector_case(["Eve"], ["Eve"], "sourceB", slot_names=("a", "b"), column="entity"))
    assert original == renamed
    source, record, _ = ordinary_connector_case(["Eve"], ["John"], "unlabeled_new")
    p = record["calls"][0]["analysis"]["proposal"]
    filtered, evidence = filter_shared_examples(p, source, original)
    assert evidence["removed"] == 0 and len(filtered["program"]["body"]["candidates"]) == 2
    from legal_skill_guard.rr.engine import decode_slots
    from legal_skill_guard.rr.interfaces import Connector, ConnectorPool
    env, _ = decode_slots(p["program"]["body"], {"s0"}, {"s0": "Entities: Eve John"})
    result = ConnectorPool([Connector(g) for g in filtered["program"]["body"]["candidates"]]).predict(env)
    assert result["status"] == "ambiguous_connector" and result["answer"] is None


def test_MB_runtime_route_consumes_frozen_examples_without_writing_back():
    from legal_skill_guard.rr.example_synthesis import fit_shared_examples
    s, r, y = ordinary_connector_case(["Bob"], ["Alice"], "train0")
    model = fit_shared_examples({s["key"]: s}, [r], {s["key"]: y})
    source, record, _ = ordinary_connector_case(["Eve"], ["John"], "new0")
    frozen_hash = digest(model)
    def generate(*args, **kwargs):
        return {"content": json.dumps(record["calls"][0]["analysis"]["proposal"])}
    generate.is_offline_mock = True
    result = route_prediction(source, arm="MB", library=SkillLibrary(frozen=True).export(), generate=generate,
                              protocol={}, partition="train", offline_mock=True, example_model=model)
    assert result["history"][0]["ordinary_example_synthesis"]["removed"] == 1
    assert result["model_calls"] == 3 and digest(model) == frozen_hash
    model["content"]["families"] = []
    from legal_skill_guard.rr.example_synthesis import filter_shared_examples
    with pytest.raises(ValueError, match="frozen"):
        filter_shared_examples(record["calls"][0]["analysis"]["proposal"], source, model)


def test_MB_ordinary_Horn_synthesis_uses_the_same_paid_view_without_collision_refinement():
    from legal_skill_guard.rr.example_synthesis import fit_shared_examples, ordinary_horn_prediction
    public = {"answer_type": "three_valued_owa", "facts": ["Bob is red.", "Bob is nice."],
              "rules": ["If someone is red and nice then they are young."], "query": "Bob is young."}
    view = {**public, "facts": ["Bob is red.", "Alice is nice."]}
    source = {"key": "artificial_train", "dataset": "ProofWriter_OWA_depth5", "public": public}
    record = {"source": source["key"], "calls": [], "learning": {"oracle_views": [
        {"view": {"public": view}, "answer": "Unknown"}]}}
    model = fit_shared_examples({source["key"]: source}, [record], {source["key"]: {"answer": "True"}})
    family = model["content"]["horn_families"][0]
    assert family["examples"] == 2 and len(family["accepted_masks"]) == 1
    assert model["content"]["budgeted_views_used_in_public_grammar_synthesis"] == 1
    assert "Bob" not in json.dumps(model) and "Alice" not in json.dumps(model)
    result = ordinary_horn_prediction({**source, "public": view}, model)
    assert result["answer"] == "Unknown" and not result["is_Omega"]
    record["learning"]["oracle_views"] = []
    ambiguous = fit_shared_examples({source["key"]: source}, [record], {source["key"]: {"answer": "True"}})
    result = ordinary_horn_prediction({**source, "public": view}, ambiguous)
    assert result["status"] == "ambiguous_connector" and result["answer"] is None


def test_MB_rejects_identity_metadata_and_does_not_truncate_oversized_H():
    from legal_skill_guard.rr.example_synthesis import filter_shared_examples, fit_shared_examples
    s, r, y = ordinary_connector_case(["Bob"], ["Bob"], "private_case_id")
    p = r["calls"][0]["analysis"]["proposal"]
    for graph in p["program"]["body"]["candidates"]:
        graph["params"] = {"scope": "Bob"}
    model = fit_shared_examples({s["key"]: s}, [r], {s["key"]: y})
    assert model["content"]["families"] == [] and "Bob" not in json.dumps(model)
    p["program"]["body"]["candidates"] *= 17
    after, evidence = filter_shared_examples(p, s, model)
    assert evidence["candidate_bound_exceeded"] and after == p


def test_formal_preparation_rejects_mock_even_with_claimed_completion(tmp_path):
    from legal_skill_guard.rr.readiness import prepare
    fixture_root(tmp_path)
    config = json.loads((tmp_path / "configs/rr_v2_preflight.json").read_text())
    stage = tmp_path / config["artifact_directory"]
    (stage / "pilot_completion.json").write_text(json.dumps({"sources": 20,
        "restore_verified": True, "teacher_batch_record_accepted": True}))
    with pytest.raises(ValueError, match="actual"):
        prepare(tmp_path)
    assert not (tmp_path / "reports/rr_v2_evidence/formal_readiness.json").exists()


def test_formal_only_execution_binding_preserves_original_rows_and_budgets(tmp_path):
    manifest = fixture_root(tmp_path)
    path = tmp_path / "formal-budget"
    origin = BudgetLedger(path, sources=manifest["allowlist"], code_hash="old", config_hash="f")
    source = manifest["pilot_order"][0]
    origin.reserve("original", role="executor", purpose="pilot_ingestion", source=source, request={})
    origin.finish("original", status="completed", result={"actual_old_result": True})
    old = origin.export()["calls"]
    protocol = json.loads((ROOT / "reports/legalskillguard_rule_reasoning_protocol_v2.json").read_text())
    protocol["run_enabled"] = True
    ledger = FormalLedger(path, sources=manifest["allowlist"], code_hash="formal_only", config_hash="f",
        protocol=protocol, manifest=manifest, partition="train", origin_binding={"code_hash": "old", "config_hash": "f"})
    assert ledger.spec["code_hash"] == "old" and ledger.execution_binding["code_hash"] == "formal_only"
    authorize_formal_fixture(ledger)
    for step in range(2):
        cid=f'formal:{source}:{step}'
        ledger.reserve(cid, role="executor", purpose="formal_train", source=source, request={})
        ledger.finish(cid,status='completed',result={})
    assert ledger.export()["calls"][:1] == old and ledger.export()["executor_used"] == 3
    with pytest.raises(BudgetError, match="two physical"):
        ledger.reserve("formal:extra", role="executor", purpose="formal_train", source=source, request={})


def test_raw_recovery_is_reversible_and_never_invents_missing_program_semantics():
    from legal_skill_guard.rr.raw_recovery import recover_format
    p = {**proposal(80), "program": {"kind": "expression", "body": {
        "bindings": [{"name": "fee", "value": "80", "type": "integer", "source": "s0"}]}}}
    recovered = recover_format(json.dumps(p))
    assert recovered["reversible"] and recovered["proposal"]["program"]["body"]["bindings"][0]["value"] == 80
    assert "query" not in recovered["proposal"]["program"]["body"]
    assert not recovered["missing_semantics_synthesized"] and not recovered["labels_used"]
    p["answer"] = {"literal": "do not reinterpret answer data"}
    assert recover_format(json.dumps(p))["proposal"]["answer"] == p["answer"]
    duplicate = '{"program":{},"program":{"kind":"unsupported"}}'
    assert recover_format(duplicate)["status"] == "unrecoverable_format"
    assert recover_format('{"program":')["status"] == "unrecoverable_format"


def test_source_strict_contract_rejects_missing_branches_and_fake_provenance():
    import jsonschema

    from legal_skill_guard.rr.engine import proposal_schema
    source = {"dataset": "RuleArena_Airline", "public": {"rules": "The fee is80.", "prompt": "Apply."}}
    schema = proposal_schema(source["dataset"], source=source)
    p = {**proposal(80), "program": {"kind": "expression", "body": {
        "bindings": [{"name": "n_fee", "value": 80, "type": "integer", "source": "s0"}],
        "query": {"op": "if", "args": [True]}, "source_links": {}}}}
    assert not jsonschema.Draft202012Validator(schema).is_valid(p)
    p["program"]["body"]["query"] = {"op": "add", "args": [{"var": "n_fee"}, 0]}
    assert jsonschema.Draft202012Validator(schema).is_valid(p)
    p["program"]["body"]["source_links"] = {"unit": ["s0"]}
    assert not jsonschema.Draft202012Validator(schema).is_valid(p)
    p["program"]["body"]["source_links"] = {}
    p["program"]["body"]["bindings"][0]["source"] = "Facts"
    assert not jsonschema.Draft202012Validator(schema).is_valid(p)


def test_round2_semantics_checks_execution_instead_of_model_answer_or_gold_copy():
    from legal_skill_guard.rr.schema_validation import validate_response
    source = {"dataset": "RuleArena_Airline", "public": {"rules": "The fee is 80.", "prompt": "Apply."}}
    p = {**proposal(999), "program": {"kind": "expression", "body": {
        "bindings": [{"name": "n_fee", "value": 80, "type": "integer", "source": "s0"}],
        "query": {"op": "add", "args": [{"var": "n_fee"}, 0]}, "source_links": {}}}}
    good = validate_response(source, {"answer": 80}, json.dumps(p))
    assert good["pass"] and good["program_answer"] == 80
    wrong_reference = validate_response(source, {"answer": 81}, json.dumps(p))
    assert not wrong_reference["pass"] and wrong_reference["model_IR_executed"]
    copied = json.loads(json.dumps(p))
    copied["program"]["body"]["query"] = {"op": "add", "args": [80, 0]}
    assert not validate_response(source, {"answer": 80}, json.dumps(copied))["pass"]
    wrong_public_source = {**source, "public": {"rules": "The fee is 79.", "prompt": "Apply."}}
    result = validate_response(wrong_public_source, {"answer": 80}, json.dumps(p))
    assert not result["pass"] and not result["source_grounding"]["pass"]


def round2_ledger_fixture(tmp_path):
    from legal_skill_guard.rr.ledger import DATASETS
    sources = {d: [f"{d}:artificial{i}" for i in range(4)] for d in DATASETS}
    path = tmp_path / "round2.sqlite3"
    ledger = BudgetLedger(path, sources=sources, code_hash="old", config_hash="f")
    with ledger.transaction() as db:
        for i in range(84):
            purpose, bucket = ("thinking_probe", "thinking_comparison") if i < 40 else \
                ("preflight_bug_retry", "shared_retries_and_recovery") if i < 48 else ("pilot_ingestion", "full_build_including_pilot")
            db.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?)",
                (f"old{i:03}", "executor", purpose, bucket, sources["OpenExempt"][0], str(i), "completed", float(i), '{}'))
        for i in range(2):
            db.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?)",
                (f"teacher{i}", "teacher", "pilot_teacher_summary", "teacher", sources["OpenExempt"][0], str(i),
                 "failed" if i == 0 else "completed", 84.0+i, '{}'))
        db.execute("INSERT INTO meta VALUES ('model_rerun', ?)", (json.dumps({"calls": {}}),))
    planned = [s for d in DATASETS[:3] for s in sources[d]]
    payloads = {f"strict_contract_fix:{s}:True": {"marker": s} for s in planned}
    calls = {cid: {"source": s, "payload_hash": digest(payloads[cid])}
             for cid, s in zip(payloads, planned)}
    auth = {"authority": "explicit_user_chat_authorization", "allowed_repair_rounds": 2,
            "max_new_physical_executor_requests": 12, "initial_gate_max_requests": 2, "teacher_calls_added": 0}
    ledger.register_strict_schema_round2(new_binding={"code_hash": "new", "config_hash": "f"},
        authorization=auth, calls=calls, order=list(payloads), forensic_hash="artificial_forensics")
    revised = BudgetLedger(path, sources=sources, code_hash="new", config_hash="f")
    return revised, payloads, calls


def test_round2_first_failed_gate_stops_and_keeps_old_charge_and_unused11(tmp_path):
    ledger, payloads, calls = round2_ledger_fixture(tmp_path)
    ids = list(payloads)
    before = ledger.export()["calls"]
    cid = ids[0]
    ledger.reserve(cid, role="executor", purpose="preflight_bug_retry", source=calls[cid]["source"],
                   request={"thinking": True, "payload": payloads[cid]})
    with pytest.raises(BudgetError, match="reconciliation"):
        ledger.reserve(ids[1], role="executor", purpose="preflight_bug_retry", source=calls[ids[1]]["source"],
                       request={"thinking": True, "payload": payloads[ids[1]]})
    ledger.finish(cid, status="failed", result={"artificial_failure": True})
    state = ledger.record_strict_schema_validation(cid, {"pass": False, "systemic_failure": True, "reason": "wire_failed"})
    assert state["phase"] == "stopped" and not state["gate_passed"]
    with pytest.raises(BudgetError, match="stopped"):
        ledger.reserve(ids[1], role="executor", purpose="preflight_bug_retry", source=calls[ids[1]]["source"],
                       request={"thinking": True, "payload": payloads[ids[1]]})
    after = ledger.export()
    assert after["executor_used"] == 85 and after["teacher_used"] == 2
    assert after["calls"][:86] == before


def test_round2_two_gate_successes_are_required_and_twelfth_call_is_total96(tmp_path):
    ledger, payloads, calls = round2_ledger_fixture(tmp_path)
    good = {"pass": True, "systemic_failure": False, "typed_schema_pass": True, "model_IR_executed": True,
            "source_grounding": {"pass": True}, "program_native_score": {"task_correct": True}}
    for i, cid in enumerate(payloads):
        ledger.reserve(cid, role="executor", purpose="preflight_bug_retry", source=calls[cid]["source"],
                       request={"thinking": True, "payload": payloads[cid]})
        ledger.finish(cid, status="completed", result={"artificial_success": True})
        if i == 0:
            with pytest.raises(BudgetError, match="evidence"):
                ledger.record_strict_schema_validation(cid, {"pass": True, "systemic_failure": False})
        state = ledger.record_strict_schema_validation(cid, good)
        assert state["gate_passed"] == (i >= 1)
    assert state["phase"] == "complete" and ledger.export()["executor_used"] == 96
    with pytest.raises(BudgetError, match="outside"):
        ledger.reserve("extra", role="executor", purpose="thinking_probe", source=next(iter(calls.values()))["source"],
                       request={"thinking": True, "payload": {}})
    assert ledger.export()["teacher_used"] == 2


def public_data(dataset, i):
    if dataset == "OpenExempt":
        return {"views": {"EC": f"Synthetic assets {i}", "EV": "Synthetic values"}}
    if dataset == "ProofWriter_OWA_depth5":
        return {"answer_type": "three_valued_owa", "facts": ["Bob is red."],
                "rules": [], "query": "Bob is red.", "fixture_number": i}
    if dataset == "ContractNLI":
        return {"document": f"Synthetic contract {i}.", "query": "Disclosure is required."}
    if dataset == "RuleArena_Airline":
        return {"rules": "Synthetic cost is 100.", "prompt": f"Passenger {i}."}
    return {"rules": "Synthetic rule.", "facts": f"Synthetic person {i}.", "query": "Applies?"}


def answer_for(dataset):
    return {"OpenExempt": {"EC": {}, "EV": {}}, "RuleArena_Airline": 100,
            "SARA_v2_Binary": "Entailment", "ProofWriter_OWA_depth5": "True",
            "ContractNLI": "NotMentioned"}[dataset]


def fixture_root(tmp_path):
    sources = [Source(d, str(i), public_data(d, i)) for d in DATASETS for i in range(80)]
    split = split_sources(sources)
    index = {s.key: s for s in sources}
    rows = [{"key": s.key, "dataset": s.dataset, "public": s.public, "content_hash": s.content_key}
            for d in DATASETS for r in split["datasets"][d]["train"] for s in [index[r["key"]]]]
    packet = tmp_path / "data/packets/rr_v2"
    (packet / "grading_only").mkdir(parents=True)
    (packet / "public_train.json").write_text(json.dumps({"split": "train", "contains_gold_or_reference_program": False, "sources": rows}))
    grades = {r["key"]: ({"targets": answer_for(r["dataset"])} if r["dataset"] == "OpenExempt" else {"answer": answer_for(r["dataset"])}) for r in rows}
    (packet / "grading_only/train.json").write_text(json.dumps({"split": "train", "never_to_actor_or_teacher": True, "sources": grades}))
    hashes = {"public_train": hashlib.sha256((packet / "public_train.json").read_bytes()).hexdigest(),
              "grading_train": hashlib.sha256((packet / "grading_only/train.json").read_bytes()).hexdigest()}
    allow = preflight_sources(split)
    order = [allow[d][i] for i in range(4) for d in DATASETS]
    manifest = {"split": split, "allowlist": allow, "pilot_order": order,
                "formal_train_order": order + [r["key"] for r in rows if r["key"] not in order],
                "packet_sha256": hashes, "data_hash": digest(hashes)}
    for name in ["configs/rr_v2_preflight.json", "configs/rr_v2_formal.json", "reports/legalskillguard_rule_reasoning_protocol_v2.json"]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
        # These are historical preflight controller fixtures, with closed gates,
        # independent of the newly authorized real formal-build configuration.
        obj=json.loads(target.read_text())
        if name.endswith('protocol_v2.json'):
            obj['run_enabled']=False
            obj['execution_request']['full_build_enabled']=False
        elif name.endswith('rr_v2_formal.json'):
            obj['run_enabled']=False;obj['full_build_enabled']=False
        elif name.endswith('rr_v2_preflight.json'):
            obj['formal_run_enabled']=False
        target.write_text(json.dumps(obj))
    evidence = tmp_path / "reports/rr_v2_evidence"
    evidence.mkdir()
    (evidence / "data_manifest.json").write_text(json.dumps(manifest))
    (evidence / "offline_latest.json").write_text(json.dumps({"exit_code": 0, "network_blocked": True, "files": {}}))
    create_seal(tmp_path, offline_mock=True)
    return manifest


class MockExecutor:
    is_offline_mock = True

    def generate(self, call_id, *, source, purpose, messages, thinking, schema):
        request = {"messages": messages, "thinking": thinking, "schema": schema}
        ticket = self.ledger.reserve(call_id, role="executor", purpose=purpose, source=source, request=request)
        if not ticket["dispatch"]:
            return ticket["result"]
        dataset = source.split(":")[0]
        content = getattr(self, "content_override", {}).get(call_id, json.dumps(proposal(answer_for(dataset))))
        result = {"request_hash": ticket["request_hash"], "content": content,
                  "usage": {"prompt_tokens": 100, "completion_tokens": 40 if thinking else 20},
                  "elapsed_seconds": 2 if thinking else 1, "reasoning_content": "artificial reasoning" if thinking else None}
        self.ledger.finish(call_id, status="completed", result=result)
        return result


class MockTeacher:
    is_offline_mock = True

    def summarize(self, call_id, **kwargs):
        ticket = self.ledger.reserve(call_id, role="teacher", purpose="pilot_teacher_summary",
                                     source=kwargs["source_ids"][0], request=kwargs)
        if not ticket["dispatch"]:
            return ticket["result"]
        result = {"value": {"patterns": [], "notes": "artificial transport only"}}
        self.ledger.finish(call_id, status="completed", result=result)
        return result


def mock_learning(source, grade, oracle, *, proposal=None):
    return {"status": "artificial_transport_check", "oracle_views": [],
            "learned_pattern": {"fields": ["entity_equality"], "graphs": [],
                                "basis": "observed_source_collisions", "universal_semantic_equivalence_claim": False}}


def test_whole_twenty_source_preflight_resume_freeze_and_tamper_rejection(tmp_path):
    manifest = fixture_root(tmp_path)
    actor, teacher = MockExecutor(), MockTeacher()
    run = Preflight(tmp_path, executor=actor, teacher=teacher, learner=mock_learning)
    actor.ledger = teacher.ledger = run.ledger
    assert not run.thinking()["selected_thinking"]
    result = run.pilot()
    assert result["sources"] == 20 and result["restore_verified"] and not result["formal_B8"]
    assert result["offline_mock"] and result["teacher_batch_record_accepted"]
    before = run.ledger.export()
    assert before["executor_used"] == 76 and before["teacher_used"] == 1
    run.thinking()
    assert run.pilot() == result and run.ledger.export() == before
    projections = next((run.artifacts / "arm_shared_material").glob("*.json"))
    values = json.loads(projections.read_text())
    assert len({v["shared_material_hash"] for v in values.values()}) == 1
    path = run.artifacts / "pilot_sources" / f"{digest(manifest['pilot_order'][0])}.json"
    changed = json.loads(path.read_text())
    changed["score"]["task_correct"] = False
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="altered"):
        run.pilot()
    assert run.ledger.export() == before


def test_mock_seal_cannot_dispatch_real_clients_and_false_formal_gate_is_early(tmp_path):
    fixture_root(tmp_path)
    with pytest.raises(ValueError, match="mock seal"):
        Preflight(tmp_path)
    with pytest.raises(BudgetError, match="disabled"):
        FormalRun(tmp_path, partition="test")
    plan = dry_run(tmp_path)
    assert not plan["executed"] and plan["model_calls"] == 0 and plan["batches"] == 8
    registered = diagnostic_plan(json.loads((tmp_path / "reports/rr_v2_evidence/data_manifest.json").read_text()))
    assert len(registered) == 32 and len({r["source"] for r in registered}) == 32
    assert {r["comparator"] for r in registered} == {"MA", "MB"}


def test_unrelated_opaque_horn_condition_retains_source_but_permits_stability():
    public = {"answer_type": "three_valued_owa", "facts": ["Bob is red."],
              "rules": ["If the opaque condition applies then Bob is blue."], "query": "Bob is red."}
    parsed = parse_public(public)
    result = parsed.assess(len, 100)
    assert parsed.residuals and result["status"] == "completion_stable" and result["answer"] == "True"
    assert all(c["verified_query_irrelevant"] for c in result["residual_contracts"].values())
    public["rules"].append("If someone is blue then they are red.")
    relevant = parse_public(public).assess(len, 100)
    assert relevant["status"] != "completion_stable"
    assert relevant["planning_status"] == "conservative_full_source_no_separation_claim"


def test_unknown_residual_write_scope_does_not_erase_other_residual_dependencies():
    parsed = parse_public({"answer_type": "three_valued_owa", "facts": ["Bob is red."],
        "rules": ["If opaque then Bob is blue.", "An unrecognized override may affect anything."], "query": "Bob is red."})
    assert parsed.assess(len, 100)["status"] != "completion_stable"
    assert not any(c["verified_query_irrelevant"] for c in parsed.residual_contracts.values())


def test_full_compilation_arm_does_not_use_partial_early_stop():
    source = {"dataset": "ProofWriter_OWA_depth5", "public": {
        "answer_type": "three_valued_owa", "facts": ["Bob is red."],
        "rules": ["If opaque condition applies then Bob is blue."], "query": "Bob is red."}}
    def generate(*args, **kwargs):
        return {"content": json.dumps(proposal("True"))}
    generate.is_offline_mock = True
    args = dict(library=SkillLibrary(frozen=True).export(), generate=generate, protocol={}, partition="train", offline_mock=True)
    assert route_prediction(source, arm="M10", **args)["model_calls"] == 1
    full = route_prediction(source, arm="M00", **args)
    assert full["model_calls"] == 3 and full["result"]["certificate_status"] != "completion_stable"


def test_all_six_routes_share_three_call_limit_and_require_frozen_library():
    source = {"dataset": "RuleArena_Airline", "public": public_data("RuleArena_Airline", 0)}
    lib = SkillLibrary(frozen=True).export()
    def generate(*args, **kwargs):
        return {"content": json.dumps(proposal())}
    generate.is_offline_mock = True
    protocol = json.loads((ROOT / "reports/legalskillguard_rule_reasoning_protocol_v2.json").read_text())
    for arm in ARMS:
        result = route_prediction(source, arm=arm, library=lib, generate=generate,
                                  protocol=protocol, partition="test", offline_mock=True)
        assert result["model_calls"] == 3 and result["call_purposes"] == ["parse", "repair", "fallback"]
        assert result["frozen_library_unchanged"]
        with pytest.raises(ValueError, match="disabled"):
            route_prediction(source, arm=arm, library=lib, generate=generate, protocol=protocol, partition="test")
    with pytest.raises(ValueError, match="real model"):
        route_prediction(source, arm="M11", library=lib, generate=lambda *a, **k: {}, protocol=protocol,
                         partition="train", offline_mock=True)


def test_equality_interface_filters_witness_erasure_without_baseline_gold_fields():
    graph = {"op": "join_on", "params": {"keys": []}, "inputs": [{"slot": "A"},
        {"op": "bind_rename", "params": {"from": ["x"], "to": ["y"]}, "inputs": [{"slot": "B"}]}]}
    p = {**proposal(), "program": {"kind": "connector", "body": {"candidates": [graph]}},
         "interfaces": [{"fields": ["entity_equality"]}]}
    lib = {"patterns": [{"pattern": {"fields": ["entity_equality"]}}]}
    assert apply_interfaces(p, "M00", lib)["program"]["body"]["candidates"] == [graph]
    assert apply_interfaces(p, "M11", lib)["program"]["body"]["candidates"] == []
    assert apply_interfaces(p, "MB", {})["program"]["body"]["candidates"] == []
    p["interfaces"] = []
    assert apply_interfaces(p, "MB", lib)["program"]["body"]["candidates"] == [graph]


def test_source_local_collision_learning_queries_no_more_than_four_and_parameterizes():
    source = {"key": "ProofWriter_OWA_depth5:artificial", "dataset": "ProofWriter_OWA_depth5", "public": {
        "answer_type": "three_valued_owa", "facts": ["Bob is red.", "Alice is nice."],
        "rules": ["If someone is red and nice then they are young."], "query": "Bob is young."}}
    class Oracle:
        views = []
        def cached_views(self): return []
        def query(self, view):
            self.views.append(view)
            return parse_public(view["public"]).execute()["answer"]
    oracle = Oracle()
    result = learn_source(source, {"answer": "Unknown"}, oracle)
    assert 0 < len(oracle.views) <= 4
    assert result["learned_pattern"]["fields"] == ["entity_equality"]
    assert result["learned_pattern"]["graphs"]
    assert "Bob" not in str(result["learned_pattern"]) and "Alice" not in str(result["learned_pattern"])
    assert not result["finite_candidate_pool_is_Omega"]


def test_durable_oracle_reserves_before_reference_dispatch_and_reuses_record(tmp_path, monkeypatch):
    allow = {d: [f"{d}:train{i}" for i in range(4)] for d in DATASETS}
    ledger = BudgetLedger(tmp_path / "ledger", sources=allow, code_hash="c", config_hash="f")
    source = {"key": allow["RuleArena_Airline"][0], "dataset": "RuleArena_Airline"}
    def reference(s, g, v):
        assert any(row[1] == digest(v) for row in ledger.export()["oracle_views"])
        return v["i"]
    monkeypatch.setattr("legal_skill_guard.rr.source_learning.evaluate_reference", reference)
    oracle = DurableOracle(ledger, tmp_path, source, {"artificial": True})
    for i in range(4):
        assert oracle.query({"i": i}) == i
    assert oracle.query({"i": 0}) == 0
    with pytest.raises(BudgetError, match="budget"):
        oracle.query({"i": 4})
    cnli = DurableOracle(ledger, tmp_path, {"key": allow["ContractNLI"][0], "dataset": "ContractNLI"}, {})
    with pytest.raises(BudgetError, match="no automatic"):
        cnli.query({"i": 0})


def authorize_formal_fixture(ledger):
    with ledger.transaction() as db:
        db.execute('insert into meta values (?,?)',('formal_run:'+ledger.run_id,json.dumps({
            'execution_binding':ledger.execution_binding,'allocation':ledger.allocation})))


def test_formal_ledger_preserves_history_and_uses_fresh_source_cap(tmp_path):
    manifest = fixture_root(tmp_path)
    allow = manifest["allowlist"]
    path = tmp_path / "formal-budget"
    before = BudgetLedger(path, sources=allow, code_hash="c", config_hash="f")
    source = manifest["pilot_order"][0]
    for i in range(2):
        before.reserve(f"pilot{i}", role="executor", purpose="pilot_ingestion", source=source, request={})
        before.finish(f'pilot{i}',status='completed',result={})
    protocol = json.loads((ROOT / "reports/legalskillguard_rule_reasoning_protocol_v2.json").read_text())
    protocol["run_enabled"] = True
    ledger = FormalLedger(path, sources=allow, code_hash="c", config_hash="f", protocol=protocol,
                          manifest=manifest, partition="train")
    authorize_formal_fixture(ledger)
    for i in range(2):
        ledger.reserve(f'formal:{source}:{i}', role="executor", purpose="formal_train", source=source, request={})
        ledger.finish(f'formal:{source}:{i}',status='completed',result={})
    with pytest.raises(BudgetError,match='two physical'):
        ledger.reserve('formal:third',role='executor',purpose='formal_train',source=source,request={})
    protocol['execution_request']['formal_eval_enabled']=True  # artificial ledger-cap fixture only
    ledger = FormalLedger(path, sources=allow, code_hash="c", config_hash="f", protocol=protocol,
                          manifest=manifest, partition="dev")
    source = manifest["split"]["datasets"]["OpenExempt"]["dev"][0]["key"]
    for i in range(3):
        ledger.reserve(f"pred:arm:{source}:{i}", role="executor", purpose="formal_dev", source=source, request={})
        ledger.finish(f'pred:arm:{source}:{i}',status='completed',result={})
    with pytest.raises(BudgetError, match="index"):
        ledger.reserve(f"pred:arm:{source}:3", role="executor", purpose="formal_dev", source=source, request={})
    assert ledger.export()["executor_used"] == 7


def test_processing_only_parser_repair_preserves_generation_hashes_and_does_not_repeat_calls(tmp_path):
    # Entirely artificial original/repaired source snapshots and response bytes.
    module = tmp_path / "legal_skill_guard/rr"
    module.mkdir(parents=True)
    current_engine = (ROOT / "legal_skill_guard/rr/engine.py").read_text()
    old_engine = current_engine.replace("proposal = _decode_proposal(content)", "proposal = json.loads(content)")
    (module / "engine.py").write_text(old_engine)
    (module / "client.py").write_bytes((ROOT / "legal_skill_guard/rr/client.py").read_bytes())
    manifest = fixture_root(tmp_path)
    actor, teacher = MockExecutor(), MockTeacher()
    run = Preflight(tmp_path, executor=actor, teacher=teacher, learner=mock_learning)
    actor.ledger = teacher.ledger = run.ledger
    actor.content_override = {f"thinking:{manifest['pilot_order'][1]}:{thinking}": '{"a":' * (80 if thinking else 2000)
                              for thinking in (True, False)}
    for source_id in manifest["pilot_order"][:2]:
        for thinking in (True, False):
            source = run.data.public(source_id)
            wire = run._call(call_id=f"thinking:{source_id}:{thinking}", source=source, purpose="thinking_probe",
                             prompt=messages(source), thinking=thinking)
            if source_id == manifest["pilot_order"][1] and not thinking:
                continue
            analysis = analyze(source, wire["content"])
            if source_id == manifest["pilot_order"][1]:
                analysis["diagnostics"] = ["Unterminated original artificial JSON"]
            target = run.artifacts / "thinking" / f"{digest((source_id, thinking))}.json"
            target.parent.mkdir(exist_ok=True)
            target.write_text(json.dumps({"source": source_id, "analysis": analysis,
                                          "wire_request_hash": wire["request_hash"]}))
    preserved = run.artifacts / "preserved_before_parser_fix"
    preserved.mkdir()
    (preserved / "seal.json").write_text(json.dumps(run.seal))
    archive_path = preserved / "frozen_scientific_files.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name in run.seal["protected_files"]:
            archive.add(tmp_path / name, arcname=name)
    (preserved / "receipt.json").write_text(json.dumps({"client_terminal_verified": True,
        "client_pid": 2147483647, "error": "RecursionError during JSON decoding of the fourth completed wire response",
        "frozen_archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest()}))
    (module / "engine.py").write_text(current_engine)
    old_rows = run.ledger.export()["calls"]
    repaired = seal_parser_repair(tmp_path)
    assert repaired["offline_mock"] and repaired["binding"] != run.seal["binding"]
    assert len(repaired["processing_repair"]["unaffected_analyses_verified"]) == 2
    resumed = Preflight(tmp_path, executor=actor, teacher=teacher, learner=mock_learning)
    actor.ledger = teacher.ledger = resumed.ledger
    assert not resumed.thinking()["engineering_block"]
    after = resumed.ledger.export()["calls"]
    assert len(after) == 40 and after[:4] == old_rows
    assert len(list((resumed.artifacts / "thinking_parser_fix").glob("*.json"))) == 40
    assert len(list((resumed.artifacts / "thinking").glob("*.json"))) == 3
    with sqlite3.connect(resumed.ledger.path) as db:
        assert db.execute("select count(*) from meta where key='bugfix'").fetchone()[0] == 1


def test_historical_native_migration_rejects_current_contract_without_rebilling(tmp_path):
    import shutil
    module = tmp_path / "legal_skill_guard/rr"
    module.mkdir(parents=True)
    for name in ("engine.py", "client.py", "preflight.py", "source_learning.py"):
        (module / name).write_bytes((ROOT / "legal_skill_guard/rr" / name).read_bytes())
    fixture_root(tmp_path)
    actor, teacher = MockExecutor(), MockTeacher()
    original = Preflight(tmp_path, executor=actor, teacher=teacher, learner=mock_learning)
    actor.ledger = teacher.ledger = original.ledger
    original.thinking()
    old_rows = original.ledger.export()["calls"]
    saved = original.artifacts / "preserved_before_native_contract_fix"
    saved.mkdir()
    (saved / "seal.json").write_text(json.dumps(original.seal))
    shutil.copytree(original.artifacts / "thinking", saved / "thinking_records")
    archive_path = saved / "frozen_scientific_files.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name in original.seal["protected_files"]:
            archive.add(tmp_path / name, arcname=name)
    (saved / "receipt.json").write_text(json.dumps({"client_terminal_verified": True,
        "client_pid": 2147483647, "executor_charged": 40, "teacher_charged": 0,
        "paid_model_rerun_rounds_used": 0, "wire_artifact_hashes": {},
        "generation_binding": original.seal["binding"],
        "frozen_archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest()}))
    (module / "repair.py").write_text('# artificial source revision for the repair state-machine test\n')
    # The historical migration assumes every non-OE adapter uses the old base
    # schema. Current label/partial-Horn contracts intentionally differ. Keep
    # its refusal intact; the current repair uses a new bound processing stage.
    with pytest.raises(ValueError, match="unaffected response schema changed"):
        seal_native_contract_repair(tmp_path)
    assert original.ledger.export()["calls"] == old_rows
    assert len(old_rows) == 40


def test_failed_reference_view_is_charged_quarantined_and_does_not_stop_learning(tmp_path, monkeypatch):
    allow = {d: [f"{d}:train{i}" for i in range(4)] for d in DATASETS}
    ledger = BudgetLedger(tmp_path / "budget", sources=allow, code_hash="c", config_hash="f")
    source = {"key": allow["ProofWriter_OWA_depth5"][0], "dataset": "ProofWriter_OWA_depth5", "public": {
        "answer_type": "three_valued_owa", "facts": ["Bob is red.", "Alice is nice.", "Charlie is blue.", "Dave is green."],
        "rules": ["If someone is red and nice then they are young."], "query": "Bob is young."}}
    dispatched = []
    def reference(s, grade, view):
        dispatched.append(view)
        if len(dispatched) == 1:
            raise RuntimeError("artificial native empty output")
        return parse_public(view["public"]).execute()["answer"]
    monkeypatch.setattr("legal_skill_guard.rr.source_learning.evaluate_reference", reference)
    oracle = DurableOracle(ledger, tmp_path, source, {"answer": "Unknown"})
    result = learn_source(source, {"answer": "Unknown"}, oracle)
    assert len(dispatched) == len(result["oracle_views"]) == 4
    assert result["reference_failures"] == 1
    assert len(ledger.export()["oracle_views"]) == 4
    failed = next(v["view"] for v in result["oracle_views"] if v.get("status") == "reference_failed")
    with pytest.raises(OracleUnavailable, match="not re-dispatched"):
        oracle.query(failed)
    assert len(dispatched) == len(ledger.export()["oracle_views"]) == 4


def test_common_train_and_six_arm_repair_share_grounded_input_contract(tmp_path):
    from legal_skill_guard.rr.engine import proposal_schema, reusable_inputs
    from legal_skill_guard.rr.preflight import ingest_source
    from legal_skill_guard.rr.wire_validation import validate_wire
    source={'key':'SARA_v2_Binary:synthetic','dataset':'SARA_v2_Binary','content_hash':'fixed',
            'public':{'rules':'Compare the amount with 10.','facts':'Payment was 7.','query':'Payment was below 10.'}}
    p={'program':{'kind':'expression','body':{'bindings':[
        {'name':'n_paid','type':'integer','value':7,'source':'s1'}],
        'query':{'op':'if','args':[{'op':'lt','args':[{'var':'n_paid'},10]},'Entailment','Contradiction']},
        'source_links':{'s0':['query']}}},'answer':'Entailment',
        'compiled_units':[], 'unsupported_units':[], 'interfaces':[]}
    public_snapshot=json.dumps(source,sort_keys=True)
    first=analyze(source,json.dumps(p))
    assert reusable_inputs(source,first)==p['program']['body']['bindings']
    schema=proposal_schema(source['dataset'],source=source,previous=first)
    validate_wire(p,schema)
    wrong= json.loads(json.dumps(p));wrong['program']['body']['bindings'][0]['value']=8
    from jsonschema import ValidationError
    with pytest.raises(ValidationError):validate_wire(wrong,schema)
    unquoted=json.loads(json.dumps(first));unquoted['proposal']['program']['body']['bindings'][0]['value']=999
    assert reusable_inputs(source,unquoted)==[]
    train=[]
    def call(**kwargs):
        train.append(kwargs);return {'content':json.dumps(p),'request_hash':str(len(train)),
                                    'usage':{},'elapsed_seconds':0}
    class Scope:
        def _source(self,key):assert key==source['key']
    learning={'status':'unresolved','oracle_views':[]}
    record=ingest_source(source=source,grade={'answer':'Entailment'},library=SkillLibrary(),thinking=True,
        call=call,learner=lambda *args, **kwargs:learning,ledger=Scope(),artifacts=tmp_path,binding={},
        purpose='pilot_ingestion',id_prefix='synthetic',offline_mock=True)
    assert len(train)==len(record['calls'])==2
    assert train[1]['schema']==schema and 'n_paid' in train[1]['prompt'][1]['content']
    lib=SkillLibrary(frozen=True).export()
    for arm in ARMS:
        captured=[]
        def generate(prompt,**kwargs):
            captured.append((prompt,kwargs));return {'content':json.dumps(p)}
        generate.is_offline_mock=True
        result=route_prediction(source,arm=arm,library=lib,generate=generate,protocol={},partition='train',offline_mock=True)
        assert result['model_calls']==3
        assert captured[0][1]['schema']==train[0]['schema']
        assert captured[1][1]['schema']==schema
    assert json.dumps(source,sort_keys=True)==public_snapshot


def test_strict_adapter_examples_do_not_change_public_horn_or_native_nli_prompt():
    from legal_skill_guard.rr.engine import messages as original_messages
    for dataset in ('ProofWriter_OWA_depth5','ContractNLI'):
        source={'dataset':dataset,'public':public_data(dataset,0)}
        previous={'proposal':proposal(),'program_status':'invalid_IR','residual_units':['s0'],'diagnostics':['actual failure']}
        assert messages(source)==original_messages(source)
        assert messages(source,previous=previous)==original_messages(source,previous=previous)
        assert 'Number of parcels' not in messages(source)[0]['content']


def test_real_B_algorithm_trace_executes_connector_semantics_without_cached_learning_result():
    source={'key':'synthetic:trace','dataset':'ProofWriter_OWA_depth5','public':{
        'answer_type':'three_valued_owa','facts':['Bob is red.','Alice is nice.','Charlie is blue.','Dave is green.'],
        'rules':['If someone is red and nice then they are young.'],'query':'Bob is young.'}}
    class NativeOracle:
        def cached_views(self): return []
        def query(self,view):return parse_public(view['public']).execute()['answer']
    trace={}
    result=learn_source(source,{'answer':'Unknown'},NativeOracle(),trace=trace)
    assert trace['initial_candidates']>trace['base_retained']
    assert trace['events'] and trace['selected_connector_semantics']
    assert all(x['prediction']==x['reference_answer'] for x in trace['selected_connector_semantics'])
    assert result['learned_pattern']['fields']==['entity_equality']
    assert result['learned_pattern']['graphs'] and not result['finite_candidate_pool_is_Omega']


def test_core_acceptance_excludes_fallback_and_does_not_require_H_shrinkage():
    from copy import deepcopy
    from experiments.rr_v2_core_preflight import checks
    record={'analysis':{'certificate_status':'translation_unresolved'},'score':{'task_correct':True},
            'learning':{'status':'identified_on_observed_collisions','learned_pattern':{
                'fields':['entity_equality'],'graphs':[{'slot':'real_role'}]}}}
    trace={'initial_candidates':8,'base_retained':8,'retained_candidates':8,'events':[],
           'refinement':{'collisions':[{'distinguishing_fields':['entity_equality']}]},
           'selected_connector_semantics':[{'prediction':'True','reference_answer':'True'}]}
    result=checks(record,trace)
    assert not result['A']['semantic_pass'] and result['A']['fallback']
    assert result['B']['semantic_pass'] and result['B']['rejected_wrong_candidates']==0
    assert not checks(record,{})['B']['semantic_pass']
    wrong=deepcopy(trace);wrong['selected_connector_semantics'][0]['prediction']='False'
    assert not checks(record,wrong)['B']['semantic_pass']
    unseparated=deepcopy(trace);unseparated['refinement']['collisions'][0]['distinguishing_fields']=['membership']
    assert not checks(record,unseparated)['B']['semantic_pass']


def test_completed_pilot_restore_preserves_later_charged_recovery_without_rewriting_snapshot(tmp_path):
    manifest=fixture_root(tmp_path);actor,teacher=MockExecutor(),MockTeacher()
    run=Preflight(tmp_path,executor=actor,teacher=teacher,learner=mock_learning)
    actor.ledger=teacher.ledger=run.ledger
    run.thinking();result=run.pilot();before=run.ledger.export()
    sid=manifest['pilot_order'][0]
    run.ledger.start_bugfix_round(reason='charged recovery after saved completion',affected_sources=[sid])
    run.ledger.reserve('later_recovery',role='executor',purpose='preflight_bug_retry',source=sid,request={'thinking':False})
    run.ledger.finish('later_recovery',status='failed',result={'error':'preserved failure'})
    assert run.pilot()==result
    assert run.ledger.export()['executor_used']==before['executor_used']+1
