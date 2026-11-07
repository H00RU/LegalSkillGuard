"""Fake transports test guards/accounting only; no claim of real backend effects."""
import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from legal_skill_guard.inference.codex_cli_client import StructuredCodexResponse
from legal_skill_guard.rr.client import ExecutorClient, TeacherClient, WireError
from legal_skill_guard.rr.interfaces import Connector, OracleViews, Relation
from legal_skill_guard.rr.learning import SkillLibrary, learn_interfaces, parameterize_graph
from legal_skill_guard.rr.ledger import DATASETS, BudgetError, BudgetLedger
from legal_skill_guard.rr.public_horn import parse_atom, parse_public, parse_rule
from legal_skill_guard.rr.thinking import select_thinking


def sources():
    return {d: [f"{d}:train{i}" for i in range(4)] for d in DATASETS}


def budget(tmp_path):
    return BudgetLedger(tmp_path / "ledger.sqlite3", sources=sources(), code_hash="code", config_hash="cfg")


def config(*, thinking=False):
    return {"base_url": "http://127.0.0.1:8000/v1", "model": "Qwen/Qwen3-8B",
            "model_retries": 0, "model_root": "/fake/model", "context_tokens": 32768,
            "max_tokens": 4096, "temperature": .6, "top_p": .95, "top_k": 20,
            "seed": 45, "timeout_seconds": 30, "enable_thinking": thinking}


class FakeTransport:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def open(self, req, timeout):
        payload = json.loads(req.data) if req.data else {}
        self.calls.append((req.full_url, payload))
        if req.full_url.endswith("/tokenize"):
            value = {"count": 3, "tokens": [1, 2, 3], "max_model_len": 32768}
        elif req.full_url.endswith("/models"):
            value = {"data": [{"id": "Qwen/Qwen3-8B", "root": "/fake/model", "max_model_len": 32768}]}
        else:
            if self.fail:
                raise HTTPError(req.full_url, 400, "bad schema", {}, io.BytesIO(b"invalid schema"))
            thinking = payload["chat_template_kwargs"]["enable_thinking"]
            value = {"id": "fake", "choices": [{"finish_reason": "stop", "message": {
                "content": '{"answer": "Unknown"}', "reasoning_content": "fake reasoning" if thinking else None}}],
                     "usage": {"prompt_tokens": 3, "completion_tokens": 7, "total_tokens": 10}}
        return io.BytesIO(json.dumps(value).encode())


def test_wire_payloads_persist_and_completed_resume_never_connects(tmp_path):
    transport, b = FakeTransport(), budget(tmp_path)
    c = ExecutorClient(b, tmp_path / "artifacts", config(thinking=True), opener=transport)
    assert c.readiness()["ready"]
    args = dict(source=sources()[DATASETS[0]][0], purpose="thinking_probe",
                messages=[{"role": "user", "content": "artificial fixture"}], thinking=True)
    first = c.generate("id", **args)
    assert not first["cache_hit"]
    previous_calls = len(transport.calls)
    assert c.generate("id", **args)["cache_hit"]
    assert len(transport.calls) == previous_calls and b.export()["executor_used"] == 1
    raw = Path(first["artifact_directory"])
    assert (raw / "wire_response.json").exists() and (raw / "request.json").exists()
    assert transport.calls[-1][1]["chat_template_kwargs"] == {"enable_thinking": True}
    assert json.loads((raw / "request.json").read_text())["generation_call_already_reserved"]


def test_explicit_off_profile_rejects_on_before_network_and_billing(tmp_path):
    transport, b = FakeTransport(), budget(tmp_path)
    c = ExecutorClient(b, tmp_path, config(), opener=transport)
    with pytest.raises(BudgetError, match="thinking differs"):
        c.generate("forbidden", source=sources()[DATASETS[0]][0], purpose="thinking_probe",
                   messages=[], thinking=True)
    assert not transport.calls and b.export()["executor_used"] == 0
    result = c.generate("off", source=sources()[DATASETS[0]][0], purpose="thinking_probe",
                        messages=[], thinking=False)
    assert result['thinking_requested'] is False and result['reasoning_content'] is None
    assert transport.calls[-1][1]['chat_template_kwargs']['enable_thinking'] is False


def test_unknown_source_and_purpose_are_rejected_before_any_tokenization(tmp_path):
    transport = FakeTransport()
    c = ExecutorClient(budget(tmp_path), tmp_path, config(), opener=transport)
    for source, purpose in [("test-source", "thinking_probe"), (sources()[DATASETS[0]][0], "formal_test")]:
        with pytest.raises(BudgetError):
            c.generate("bad", source=source, purpose=purpose, messages=[], thinking=False)
    assert not transport.calls


def test_failed_http_call_keeps_raw_diagnostic_one_charge_and_no_hidden_retry(tmp_path):
    transport, b = FakeTransport(fail=True), budget(tmp_path)
    c = ExecutorClient(b, tmp_path, config(), opener=transport)
    args = dict(source=sources()[DATASETS[0]][0], purpose="thinking_probe", messages=[], thinking=False)
    with pytest.raises(WireError, match="Charged"):
        c.generate("id", **args)
    assert len(transport.calls) == 2  # one tokenizer request + one generation
    assert b.export()["executor_used"] == 1
    failure = next(tmp_path.glob("calls/*/failure.json"))
    assert json.loads(failure.read_text())["reserved_and_charged"]
    with pytest.raises(BudgetError, match="implicit"):
        c.generate("id", **args)
    assert len(transport.calls) == 2


def test_one_repair_binding_preserves_origin_bills_and_cannot_start_new_sweep(tmp_path):
    b, source = budget(tmp_path), sources()[DATASETS[0]][0]
    b.reserve("old", role="executor", purpose="pilot_ingestion", source=source, request={})
    b.finish("old", status="failed", result={"error": "implementation bug"})
    b.start_bugfix_round(reason="wrong request schema field", affected_sources=[source], new_code_hash="fixed")
    fixed = BudgetLedger(b.path, sources=sources(), code_hash="fixed", config_hash="cfg")
    assert fixed.export()["executor_used"] == 1
    fixed.reserve("repair", role="executor", purpose="preflight_bug_retry", source=source, request={})
    assert fixed.export()["executor_used"] == 2
    with pytest.raises(BudgetError, match="fresh sweep"):
        fixed.reserve("sweep", role="executor", purpose="thinking_probe", source=source, request={"thinking": False})
    with pytest.raises(BudgetError):
        fixed.reserve("unaffected", role="executor", purpose="preflight_bug_retry",
                      source=sources()[DATASETS[1]][0], request={})


def test_teacher_calls_are_in_the_same_ledger_and_resume_is_free(tmp_path):
    class FakeTeacher:
        count = 0
        def generate_json(self, **kwargs):
            self.count += 1
            return StructuredCodexResponse(value={"patterns": []}, model="fake",
                request_sha256="request", response_sha256="response", cache_hit=False, invocation={"usage": {}})
    adapter, b = FakeTeacher(), budget(tmp_path)
    c = TeacherClient(b, tmp_path, {"retries": 0}, adapter=adapter)
    args = dict(source_ids=[sources()[DATASETS[0]][0]], system_prompt="fixture", user_prompt="fixture", output_schema={})
    c.summarize("teacher1", **args)
    assert c.summarize("teacher1", **args)["ledger_cache_hit"]
    assert adapter.count == 1 and b.export()["teacher_used"] == 1


def test_public_grammar_shared_variables_not_independent_exists_and_explicit_negative():
    public = {"answer_type": "three_valued_owa", "facts": ["The cat is red.", "The cow is nice."],
              "rules": ["If something is red and nice then it is young."], "query": "The cat is young."}
    p = parse_public(public)
    assert not p.residuals
    assert p.execute()["answer"] == "Unknown"
    public["facts"].append("The cat is nice.")
    assert parse_public(public).assess(lambda x: len(x), 100)["answer"] == "True"
    assert not parse_atom("The bald eagle does not visit the tiger.").positive
    assert parse_atom("The bald eagle visits the tiger.").arguments == ("bald eagle", "tiger")
    assert len(parse_rule("Nice, blue people are quiet.", "s1").body) == 2


def test_unparsed_source_rule_still_blocks_early_stability_even_with_support_proof():
    public = {"answer_type": "three_valued_owa", "facts": ["Bob is red."],
              "rules": ["Bob may be different under an unrecognized exception."], "query": "Bob is red."}
    p = parse_public(public)
    result = p.assess(lambda s: len(s), 100)
    assert result["status"] != "completion_stable" and result["batch"] == p.residuals


def graphs():
    join = Connector({"op": "project_exists", "inputs": [{"op": "join_on", "params": {"keys": ["x"]},
                       "inputs": [{"slot": "A"}, {"slot": "B"}]}]})
    coarse = Connector({"op": "fold_reduce", "params": {"primitive": "all"}, "inputs": [{"op": "map",
                       "params": {"primitive": "exists"}, "inputs": [{"slot": "relations"}]}]})
    return join, coarse


def view(left, right):
    a, b = Relation(("x",), ((left,),)), Relation(("x",), ((right,),))
    return {"A": a, "B": b, "relations": [a, b]}


def test_collision_learning_to_frozen_role_parameterized_library(tmp_path):
    base, different = view("alice", "alice"), view("alice", "bob")
    charged = []
    oracle = OracleViews("train", "ProofWriter_OWA_depth5", "train",
                         lambda s, h: charged.append(h), lambda v: graphs()[0].execute(v))
    def metadata(v):
        return {"entity_equality": [{"entity": v["A"].rows[0][0]}, {"entity": v["B"].rows[0][0]}]}
    result = learn_interfaces(base_view=base, base_answer=True, candidates=list(graphs()),
                              fact_views=[different], coarse=lambda v: [r.exists() for r in v["relations"]],
                              metadata=metadata, oracle=oracle)
    assert len(charged) == 1 and result["learned_pattern"]["fields"] == ["entity_equality"]
    assert not result["finite_candidate_pool_is_Omega"] and len(result["retained_graphs"]) == 1
    lib = SkillLibrary()
    lib.add(result["learned_pattern"], source="provenance_source")
    frozen = lib.freeze(tmp_path / "library.json")
    restored = SkillLibrary.restore(tmp_path / "library.json")
    assert "alice" not in str(frozen["content"]["patterns"][0]["pattern"])
    assert restored.export() == lib.export()
    with pytest.raises(ValueError, match="Frozen"):
        restored.add(result["learned_pattern"], source="test_feedback")


def test_graph_role_parameterization_is_alpha_invariant_and_idempotent():
    first = graphs()[0].graph
    renamed = json.loads(json.dumps(first).replace('"A"', '"PersonOne"').replace('"B"', '"PersonTwo"').replace('"x"', '"who"'))
    assert parameterize_graph(first) == parameterize_graph(renamed)
    assert parameterize_graph(parameterize_graph(first)) == parameterize_graph(first)


def paired_records():
    ids = [s for v in sources().values() for s in v]
    return ids, [{"source": s, "thinking": t, "structural_pass": True, "task_correct": True,
                   "usage": {"prompt_tokens": 10, "completion_tokens": 20 if t else 10},
                   "elapsed_seconds": 2 if t else 1, "actual_backend_effect_verified": True}
                  for s in ids for t in (True, False)]


def test_thinking_selection_fixed_rule_and_no_equivalence_claim():
    ids, rows = paired_records()
    r = select_thinking(rows, ids)
    assert not r["selected_thinking"] and not r["engineering_block"]
    assert not r["quality_equivalence_claim"] and not r["extra_sweep_authorized"]
    rows[1]["task_correct"] = False
    r = select_thinking(rows, ids)
    assert r["selected_thinking"] and r["on_correct_off_incorrect_sources"] == [ids[0]]


def test_missing_switch_evidence_or_incomplete_pairs_cannot_choose_off():
    ids, rows = paired_records()
    rows[0]["actual_backend_effect_verified"] = False
    r = select_thinking(rows, ids)
    assert r["engineering_block"] and r["selected_thinking"]
    with pytest.raises(ValueError, match="incomplete"):
        select_thinking(rows[:-1], ids)


def test_backend_switch_observation_does_not_require_every_enabled_answer_to_reason():
    ids, rows = paired_records()
    for i, r in enumerate(rows):
        r["template_profile_observed"] = True
        r["reasoning_present"] = r["thinking"] and i == 0
    assert select_thinking(rows, ids)["actual_backend_switch_verified"]
    rows[1]["reasoning_present"] = True
    assert select_thinking(rows, ids)["engineering_block"]
