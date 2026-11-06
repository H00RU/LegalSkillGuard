"""Source-linked execution tests, with artificial tasks rather than real test labels."""
import hashlib
import json
from fractions import Fraction

import pytest

from legal_skill_guard.rr.coverage import (
    FiniteTheory,
    SourceLedger,
    certificate,
    complete,
    evaluate,
)
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.engine import analyze, messages, source_text
from legal_skill_guard.rr.ledger import DATASETS, BudgetError
from legal_skill_guard.rr.partitions import Source, preflight_sources, split_sources


def proposal(kind="unsupported", body=None, answer=100, compiled=None):
    return {"answer": answer, "program": {"kind": kind, "body": body or {}},
            "compiled_units": compiled or [], "unsupported_units": [], "interfaces": []}


def test_deep_or_truncated_model_json_is_a_bounded_parse_failure_not_a_process_crash():
    source = {"dataset": "RuleArena_Airline", "public": {"rules": "Cost rule.", "prompt": "A flight."}}
    for content in ['{"a":' * 2000, '[' * 2000 + '0' + ']' * 2000]:
        result = analyze(source, content)
        assert result["program_status"] == "parse_failure" and not result["structural_pass"]
        assert result["certificate_status"] != "completion_stable"
        assert any("bounded JSON nesting" in x for x in result["diagnostics"])


def test_braces_and_escaped_quotes_inside_strings_do_not_count_as_json_nesting():
    from legal_skill_guard.rr.engine import _decode_proposal
    value = {"text": 'quoted \\" ' + '{[' * 1000}
    assert _decode_proposal(json.dumps(value)) == value


def test_native_oe_contract_is_visible_and_typed_without_gold_names():
    import jsonschema

    from legal_skill_guard.rr.engine import PROPOSAL_SCHEMA, proposal_schema, wire_messages
    native = proposal_schema("OpenExempt")
    valid = proposal(answer={"EC": {"arbitrary public asset": []}, "EV": {
        "arbitrary public asset": [{"citation": "arbitrary public citation", "claim_value": 100}]}})
    jsonschema.validate(valid, native)
    valid["answer"]["EV"]["arbitrary public asset"] = [{"label": "arbitrary public citation", "value": 100}]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(valid, native)
    source = {"dataset": "OpenExempt", "public": {"views": {"EC": "Synthetic fact.", "EV": "Synthetic fact."}}}
    prompt = wire_messages(source)
    assert "claim_value" in prompt[0]["content"] and "citation" in prompt[0]["content"]
    for dataset in ["RuleArena_Airline", "SARA_v2_Binary", "ProofWriter_OWA_depth5", "ContractNLI"]:
        assert proposal_schema(dataset) == PROPOSAL_SCHEMA


def test_source_linked_arithmetic_is_executed_and_output_not_rewritten_by_model():
    source = {"dataset": "RuleArena_Airline", "public": {"rules": "Total is base plus fee.", "prompt": "Base 80; fee 20."}}
    body = {"bindings": [{"name": "base", "value": 80, "type": "integer", "source": "s1"},
                          {"name": "fee", "value": 20, "type": "integer", "source": "s1"}],
            "query": {"op": "add", "args": [{"var": "base"}, {"var": "fee"}]},
            "source_links": {"s0": ["query"], "s1": ["binding:base", "binding:fee"]}}
    r = analyze(source, json.dumps(proposal("expression", body, answer=999, compiled=["s0", "s1"])))
    assert r["answer"] == 100 and r["certificate_status"] == "completion_stable"
    assert r["certificate"]["conditional_reference_containment"]
    assert not r["certificate"]["natural_language_faithfulness_proven"]


def test_unlinked_exception_keeps_residual_and_uses_fixed_uncertified_fallback():
    source = {"dataset": "RuleArena_Airline", "public": {"rules": "Total is base.\nExcept on waived flights.",
                                                           "prompt": "The base is 80."}}
    body = {"bindings": [{"name": "base", "value": 80, "type": "integer", "source": "s2"}],
            "query": {"op": "add", "args": [{"var": "base"}, 0]},
            "source_links": {"s0": ["query"], "s2": ["binding:base"]}}
    r = analyze(source, json.dumps(proposal("expression", body, answer=0, compiled=["s0", "s2"])))
    assert r["candidate_answer"] == 80 and r["answer"] == 0
    assert r["residual_units"] == ["s1"] and r["fallback_used"]
    assert r["certificate_status"] == "translation_unresolved"


def test_copied_answer_or_made_up_witness_is_not_a_compiled_rule():
    source = {"dataset": "SARA_v2_Binary", "public": {"rules": "An A exists.", "facts": "Boolean output true.", "query": "Does the rule apply?"}}
    body = {"bindings": [{"name": "a", "value": 1, "type": "integer", "source": "s0"}],
            "query": "Entailment", "source_links": {"s0": ["query"]}}
    r = analyze(source, json.dumps(proposal("expression", body, "Entailment", ["s0"])))
    assert r["program_status"] == "invalid_IR" and not r["structural_pass"]
    body = {"bindings": [{"name": "A", "type": "relation", "source": "s0", "value": {
                "columns": ["x"], "rows": [["InventedAlice"]], "closed": True}}],
            "candidates": [{"op": "project_exists", "inputs": [{"slot": "A"}]}], "source_links": {}}
    r = analyze(source, json.dumps(proposal("connector", body, "Entailment")))
    assert r["program_status"] == "invalid_IR" and any("witness" in d for d in r["diagnostics"])


def test_candidate_graph_agreement_never_certifies_omega():
    source = {"dataset": "SARA_v2_Binary", "public": {"rules": "Alice is named.", "facts": "Alice exists.", "query": "Does it apply?"}}
    body = {"bindings": [{"name": "A", "type": "relation", "source": "s0", "value": {
                "columns": ["x"], "rows": [["Alice"]], "closed": True}}],
            "candidates": [{"op": "project_exists", "inputs": [{"slot": "A"}]}],
            "source_links": {"s0": ["connector:0"], "s1": ["connector:0"], "s2": ["connector:0"]}}
    r = analyze(source, json.dumps(proposal("connector", body, "Entailment", ["s0", "s1", "s2"])))
    assert r["program_status"] == "candidate_pool_agreement_only"
    assert r["certificate_status"] != "completion_stable"


def test_exact_rationals_structured_outputs_and_no_float_sampling():
    assert evaluate({"op": "divide_constant", "args": [1, 3]}, {}) == Fraction(1, 3)
    result = evaluate({"op": "object", "args": [{"op": "pair", "args": ["value",
                      {"op": "add", "args": [{"var": "x"}, 1]}]}]}, {"x": Fraction(1, 3)})
    assert result == {"value": Fraction(4, 3)}
    with pytest.raises(ValueError):
        evaluate({"op": "scale", "args": [{"var": "x"}, {"var": "y"}]}, {"x": 2, "y": 3})
    ledger = SourceLedger.from_text("")
    theory = FiniteTheory(ledger, {}, {}, {"op": "divide_constant", "args": [1, 3]}, [])
    proof = certificate(theory, complete(theory))
    assert proof["answer"] == {"exact_rational": [1, 3]}
    assert json.loads(json.dumps(proof)) == proof


def test_engine_threaded_allowance_preserves_usage_trace_and_rejects_cloning():
    source = {"dataset": "RuleArena_Airline", "public": {"rules": "Synthetic shared allowance 100.",
                                                           "prompt": "Two synthetic amounts 80 and 80."}}
    amounts = [{"value": 80, "unit": "dollar", "owner": "family", "period": "year",
                "lineage": [f"item{i}"], "stage": "element"} for i in range(2)]
    entry = {"key": ["rule", "family", "year"], "balance": 100, "policy": "input_order", "order_observable": False}
    body = {"bindings": [
        {"name": "items", "type": "amounts", "value": amounts, "source": "s1"},
        {"name": "bank", "type": "allowance_bank", "value": [entry], "source": "s0"},
        {"name": "key", "type": "resource_key", "value": entry["key"], "source": "s0"}],
        "candidates": [{"op": "fold_reduce", "params": {"primitive": "sum_amounts"}, "inputs": [
            {"op": "thread_allowance", "params": {"bank_slot": "bank", "key_slot": "key"},
             "inputs": [{"slot": "items"}]}]}], "project": "amount_value", "source_links": {}}
    r = analyze(source, json.dumps(proposal("connector", body, 60)))
    assert r["candidate_answer"] == 60
    events = r["execution_states"][0]["bank"]["events"]
    assert [e["used"] for e in events] == [80, 20] and events[-1]["balance"] == 0
    assert r["certificate_status"] != "completion_stable"
    body["bindings"][1]["value"] = [entry, entry]
    assert analyze(source, json.dumps(proposal("connector", body, 60)))["program_status"] == "invalid_IR"


def test_contract_nli_has_no_formal_certificate_and_messages_never_take_grading_inputs():
    source = {"dataset": "ContractNLI", "public": {"document": "Party A may disclose.", "query": "It must disclose."}}
    r = analyze(source, json.dumps(proposal(answer="NotMentioned")))
    assert r["certificate_status"] == "unsupported_no_certificate" and r["structural_pass"]
    prompt = messages(source, previous=r)
    assert "NotMentioned" in prompt[0]["content"]  # public answer vocabulary only
    assert "reference_program" not in prompt[1]["content"]
    assert len(SourceLedger.from_text(source_text(source)).clauses) == 2


def fake_data(tmp_path):
    sources = [Source(d, str(i), {"text": f"{d} public {i}"}) for d in DATASETS for i in range(80)]
    split = split_sources(sources)
    index = {s.key: s for s in sources}
    rows = []
    for dataset in DATASETS:
        for r in split["datasets"][dataset]["train"]:
            s = index[r["key"]]
            rows.append({"key": s.key, "dataset": s.dataset, "public": s.public, "content_hash": s.content_key})
    root = tmp_path / "data/packets/rr_v2"
    (root / "grading_only").mkdir(parents=True)
    public = {"split": "train", "contains_gold_or_reference_program": False, "sources": rows}
    grading = {"split": "train", "never_to_actor_or_teacher": True, "sources": {r["key"]: {"answer": "private fixture"} for r in rows}}
    (root / "public_train.json").write_text(json.dumps(public))
    (root / "grading_only/train.json").write_text(json.dumps(grading))
    files = {"public_train": hashlib.sha256((root / "public_train.json").read_bytes()).hexdigest(),
             "grading_train": hashlib.sha256((root / "grading_only/train.json").read_bytes()).hexdigest()}
    allowlist = preflight_sources(split)
    from legal_skill_guard.rr.coverage import digest
    manifest = {"split": split, "allowlist": allowlist,
                "pilot_order": [s for v in allowlist.values() for s in v],
                "packet_sha256": files, "data_hash": digest(files)}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, manifest


def test_preflight_data_access_is_fixed_to_twenty_train_sources_and_hashes(tmp_path):
    path, manifest = fake_data(tmp_path)
    store = PreflightData(tmp_path, path)
    key = manifest["pilot_order"][0]
    assert "private fixture" not in str(store.public(key))
    assert store.grade(key)["answer"] == "private fixture"
    for operation in [lambda: store.grade("test-source"), lambda: store.public("extra-train-source"),
                      lambda: store.public_prediction_partition("test")]:
        with pytest.raises(BudgetError):
            operation()
    public = tmp_path / "data/packets/rr_v2/public_train.json"
    public.write_text(public.read_text() + " ")
    with pytest.raises(BudgetError, match="hash"):
        PreflightData(tmp_path, path)
