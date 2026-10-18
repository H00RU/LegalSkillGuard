"""Small permanent boundary tests; no model/teacher calls or held-out data."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from legal_skill_guard.data import source_components
from legal_skill_guard.experiment.storage import ImmutableArtifactConflictError, RunStore
from legal_skill_guard.inference.codex_cli_client import CodexCLIClient, CodexInvocationError
from legal_skill_guard.learning.ace_native import update_bullet_counts
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.catalog import decode_teacher_body, encode_teacher_body
from legal_skill_guard.learning.encoding import decode_receipts, encode_receipts
from legal_skill_guard.learning.experiment import scope_plan
from legal_skill_guard.learning.interface import (
    compact_receipts,
    execute_plan,
    final_messages,
    publish,
)
from legal_skill_guard.learning.packing import pack_cases
from legal_skill_guard.learning.review import checked_messages, review_messages
from legal_skill_guard.learning.source_condition_audit import (
    checked_source_audit,
    source_audit_input,
)
from legal_skill_guard.report import write_report
from legal_skill_guard.task import (
    coherent_native_schema,
    original_feedback,
    original_metrics,
    output_schema,
)


def fixture():
    clauses = [
        "Recipient shall not disclose secrets.",
        "Recipient may retain an archive.",
        "Purpose is evaluation.",
    ]
    text = "\n".join(clauses)
    spans = []
    cursor = 0
    for clause in clauses:
        spans.append([cursor, cursor + len(clause)])
        cursor += len(clause) + 1
    labels = {k: {"hypothesis": k, "short_description": k} for k in ("h1", "h2", "h3")}
    gold = {
        "h1": {"choice": "Entailment", "spans": [0, 2]},
        "h2": {"choice": "Contradiction", "spans": [1]},
        "h3": {"choice": "NotMentioned", "spans": []},
    }
    row = {
        "id": 1,
        "text": text,
        "spans": spans,
        "url": "source1",
        "annotation_sets": [{"annotations": gold, "CANARY": "GOLD_MUST_NOT_ENTER_SOLVER"}],
    }
    return row, labels, gold


def test_stop_during_teacher_retains_response_but_prevents_publication(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from legal_skill_guard.learning import experiment as module

    study = module.Comparison.__new__(module.Comparison)
    study.cfg = {"teacher":{"model":"synthetic-only", "reasoning_effort":"high",
        "timeout_seconds":1, "ledger":"unused", "total_invocation_budget":1, "max_input_tokens":1000}}
    study.out, study.run_id = tmp_path, "synthetic-stop-only"
    study.stop, study.teacher_attempts, study.teachers = False, 0, []
    def check():
        if study.stop:
            raise InterruptedError("Operator stop at artifact-safe boundary")
    study.check, study.progress = check, lambda *a,**k:None
    def generate(**kwargs):
        study.stop = True
        return {"value":{"ok":True}, "cache_hit":False, "invocation":{}}
    monkeypatch.setattr(module, "CodexCLIClient", lambda **k:SimpleNamespace(
        request_payload=lambda **r:{}, generate_json=generate))
    monkeypatch.setattr(module, "asdict", lambda r:r)
    with pytest.raises(InterruptedError,match="Operator stop"):
        study.teacher_call("stopped", "Synthetic instructions.", {}, {"type":"object"})
    assert study.teacher_attempts == len(study.teachers) == 1
    assert (tmp_path/"teacher/stopped/response.json").is_file()


def skill(sid="s1", scope=None):
    return {
        "id": sid,
        "hypothesis_ids": scope or ["h1"],
        "guidance": "Inspect actor and exception scope.",
        "queries": [
            {
                "all_phrases": ["shall not"],
                "any_phrases": [],
                "none_phrases": [],
                "before": 0,
                "after": 1,
            }
        ],
    }


def response(answer, finish="stop"):
    return {
        "content": json.dumps(answer),
        "finish_reason": finish,
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "raw_id": "native-test",
    }


def test_source_condition_audit_input_withholds_annotations_and_outcomes():
    row, labels, _ = fixture()

    class UnreadableAnnotations(dict):
        def __getitem__(self, key):
            if key == "annotation_sets":
                raise AssertionError("Audit-input construction must not read annotations")
            return super().__getitem__(key)

    value = source_audit_input([skill()], [UnreadableAnnotations(row)], labels)
    assert "GOLD_MUST_NOT_ENTER_SOLVER" not in json.dumps(value)
    source = value["complete_original_sources_without_annotation_sets"][0]
    assert set(source) == {"document_id", "full_original_contract_with_spans"}
    assert "Recipient shall not disclose secrets." in source["full_original_contract_with_spans"]


def test_source_condition_audit_retains_semantic_conflicts_but_checks_all_references():
    row, labels, _ = fixture()
    bank = [skill()]
    original = copy.deepcopy(bank)
    report = {"skill_reports": [{"skill_id": "s1", "finding": "Synthetic test finding, not a model output",
                                "checks": [{"d": 1, "h": "h1", "r": "Contradiction", "s": [0]}]}]}
    summary = checked_source_audit(report, bank, [row], labels)
    assert len(summary["nonnull_claim_original_training_label_differences"]) == 1
    assert bank == original  # A label conflict is data, not rejection/edit/rollback.
    report["skill_reports"][0]["checks"][0]["r"] = None
    assert checked_source_audit(report, bank, [row], labels)["nonnull_condition_claims"] == 0
    report["skill_reports"][0]["checks"][0]["s"] = [99]
    with pytest.raises(ValueError, match="original spans"):
        checked_source_audit(report, bank, [row], labels)
    report["skill_reports"][0]["checks"] = []
    with pytest.raises(ValueError, match="source/scope pairs"):
        checked_source_audit(report, bank, [row], labels)


def test_original_binary_metrics_and_independent_audit():
    row, labels, gold = fixture()
    answer = copy.deepcopy(gold)
    answer["h1"]["spans"] = [0, 1]
    r = response(answer)
    feedback = original_feedback(r, row, gold, list(labels))
    expected = original_score(r, row, gold, list(labels))
    close(expected, {k: feedback[k] for k in expected})
    m = original_metrics([{"response": r, **feedback}])
    assert m["label_accuracy"] == 1
    assert (m["evidence_tp"], m["evidence_fp"], m["evidence_fn"]) == (2, 1, 1)
    assert m["evidence_micro_f1_gold_non_neutral"] == pytest.approx(2 / 3)
    assert m["joint_exact_correct"] == 2


def test_native_choice_evidence_consistency_is_not_a_post_answer_repair():
    from jsonschema import validate

    row, labels, gold = fixture()
    raw = output_schema(row, list(labels), [])
    saved = copy.deepcopy(raw)
    schema = coherent_native_schema(raw)
    answer = {
        k: {**v, "reason": "Source decision.", "used_skill_ids": []}
        for k, v in copy.deepcopy(gold).items()
    }
    validate(answer, schema)
    assert raw == saved
    bad = copy.deepcopy(answer)
    bad["h3"]["spans"] = [0]
    with pytest.raises(ValidationError):
        validate(bad, schema)
    # The historical score is neither cleared nor changed by the new generator
    # schema: the exact bad native answer still loses this joint endpoint.
    observed = response(bad)
    feedback = original_feedback(observed, row, gold, list(labels))
    assert feedback["public_valid"]
    assert not feedback["queries"][2]["joint_exact"]
    assert feedback["parsed"]["h3"]["spans"] == [0]
    assert json.loads(observed["content"])["h3"]["spans"] == [0]
    bad = copy.deepcopy(answer)
    bad["h1"]["spans"] = []
    with pytest.raises(ValidationError):
        validate(bad, schema)


def test_executable_query_features_are_source_only_scoped_and_not_answer_rules():
    import numpy as np

    from legal_skill_guard.learning.evidence_programs import (
        program_queries,
        program_solver_messages,
        query_features,
    )

    row, labels, _ = fixture()
    bank = [skill()]
    queries = program_queries(bank, list(labels))
    texts = [row["text"][a:b] for a, b in row["spans"]]
    values, trace = query_features(texts, "h1", queries)
    np.testing.assert_array_equal(values, [[1, 1], [0, 1], [0, 0]])
    assert trace[0]["direct_matches"] == [0] and trace[0]["context"] == [0, 1]
    unrelated, other_trace = query_features(texts, "h2", queries)
    assert not unrelated.any() and other_trace == []
    messages, schema = program_solver_messages(row, labels, "Original task.", None)
    assert "GOLD_MUST_NOT_ENTER_SOLVER" not in json.dumps(messages)
    assert bank[0]["guidance"] not in json.dumps(messages)
    assert program_solver_messages(
        {**row, "annotation_sets": "FORBIDDEN"}, labels, "Original task.", None
    ) == (messages, schema)
    with pytest.raises(ValueError, match="factual query"):
        program_queries([{**skill(), "queries": []}], list(labels))


@pytest.mark.parametrize("disable_thinking", [False, True])
def test_native_generation_and_server_token_count_use_one_thinking_profile(disable_thinking):
    import io
    from types import SimpleNamespace

    from legal_skill_guard.inference.native import WireClient
    from legal_skill_guard.inference.openai_client import GenerationConfig

    cfg = {"base_url": "http://127.0.0.1:1/v1", "model": "synthetic",
        "timeout_seconds": 1, "model_root": "synthetic", "context_tokens": 32768,
        "disable_thinking": disable_thinking}
    client, requests = WireClient(cfg), []
    def tokenize(req, **_kwargs):
        requests.append(json.loads(req.data))
        return io.BytesIO(json.dumps({"count": 7, "tokens": [1] * 7,
            "max_model_len": 32768}).encode())
    client.opener = SimpleNamespace(open=tokenize)
    assert client.token_count(messages=[{"role": "user", "content": "Task"}]) == 7
    def generate(_method, _path, payload):
        requests.append(payload)
        return {"id": "synthetic-native", "choices": [{"message": {"content": "{}"},
            "finish_reason": "stop"}], "usage": {"prompt_tokens": 7, "completion_tokens": 1}}
    client._request = generate
    config = GenerationConfig(temperature=.6, top_p=.95, max_tokens=32, seed=45,
        disable_thinking=disable_thinking)
    assert client.generate([{"role": "user", "content": "Task"}], config).content == "{}"
    assert requests[0]["chat_template_kwargs"] == {"enable_thinking": not disable_thinking}
    assert requests[1].get("chat_template_kwargs") == ({"enable_thinking": False} if disable_thinking else None)
    with pytest.raises(ValueError, match="profiles differ"):
        client.generate([], GenerationConfig(temperature=.6, top_p=.95, max_tokens=32,
            seed=45, disable_thinking=not disable_thinking))
    assert len(requests) == 2, "A mismatch fails before spending a generation"


def test_member_guidance_contains_only_complete_inspection_not_query_windows():
    from jsonschema import validate

    from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
    from legal_skill_guard.learning.member_contract import EDIT_GUIDANCE
    from legal_skill_guard.learning.publication import differential_schema

    inspection = {"evidence_criterion": "Check the operative exception."}
    validate(inspection, EDIT_GUIDANCE)
    with pytest.raises(ValidationError):
        validate({"evidence_criterion": None}, EDIT_GUIDANCE)
    with pytest.raises(ValidationError):
        validate({**inspection, "source_queries": []}, EDIT_GUIDANCE)
    assert not strict_output_schema_issues(
        differential_schema(["h1"], [], [1], guidance_schema=EDIT_GUIDANCE))


def test_member_own_and_control_share_full_source_without_retriever(monkeypatch):
    from types import SimpleNamespace

    from legal_skill_guard.learning import acquisition, member_learning

    row, labels, _ = fixture()
    source = {k: row[k] for k in ("id", "text", "spans")}
    study = member_learning.MemberLearning.__new__(member_learning.MemberLearning)
    study.labels, study.system = labels, "Original task."
    study.cfg = {"generation": {"max_tokens": 8192, "context_tokens": 32768}}
    study.meter = SimpleNamespace(token_count=lambda **_: 50)

    def candidates(*args):
        raise AssertionError("Source-only learning must never call a candidate model")
    monkeypatch.setattr(acquisition, "evidence_proposals", candidates)
    bank = [{"id": "s1", "hypothesis_ids": ["h1"], "guidance": {
        "evidence_criterion": "Inspect actor and exception scope."}}]
    payload = study.payload(source, "skills", bank)
    body = json.loads(payload["messages"][1]["content"])
    assert payload["full_original_source_only"] and not hasattr(study, "model")
    assert "fixed_ordinary_model_state" not in payload and "candidate_original_text" not in body
    assert all(set(v) == {"original_hypothesis", "original_public_short_description"}
        for v in body["hypotheses"].values())
    assert body["evidence_selection_criteria"] == [{"hypothesis_ids": ["h1"],
        "criterion": bank[0]["guidance"]["evidence_criterion"]}]
    assert all("evidence_selection_criteria" not in h for h in body["hypotheses"].values())
    empty = study.payload(source, "strong_empty", bank)
    baseline = json.loads(empty["messages"][1]["content"])
    assert "evidence_selection_criteria" not in baseline
    assert {k: v for k, v in body.items() if k != "evidence_selection_criteria"} == baseline
    assert empty["messages"][0] == payload["messages"][0]
    assert empty["schema"] == payload["schema"]
    with pytest.raises(AssertionError):
        study.payload(source, "ordinary", bank)
    assert "GOLD_MUST_NOT_ENTER_SOLVER" not in json.dumps(payload["messages"])


def test_execution_blocks_follow_public_applicability_not_fixed_topics():
    from legal_skill_guard.learning.member_contract import execution_blocks, project_criteria

    _, labels, _ = fixture()
    bank = [{"id": "a", "hypothesis_ids": ["h1", "h2"],
             "guidance": {"evidence_criterion": "Keep complete procedure A."}},
            {"id": "b", "hypothesis_ids": ["h3"],
             "guidance": {"evidence_criterion": "Keep complete procedure B."}}]
    assert execution_blocks(bank, labels) == [["h1", "h2"], ["h3"]]
    assert execution_blocks([], labels) == [["h1", "h2", "h3"]]
    projected = project_criteria(bank, ["h2"])
    assert projected == [{**bank[0], "hypothesis_ids": ["h2"]}]
    assert bank[0]["hypothesis_ids"] == ["h1", "h2"], "Never mutate the actual published library"


def test_grouped_member_payload_preserves_scope_locality_and_empty_pair():
    from types import SimpleNamespace
    from legal_skill_guard.learning.member_learning import MemberLearning

    row, labels, _ = fixture()
    study = MemberLearning.__new__(MemberLearning)
    study.labels, study.system = labels, "Answer only the supplied original keys."
    study.cfg = {"generation": {"max_tokens": 8192, "context_tokens": 32768}}
    study.meter = SimpleNamespace(token_count=lambda **_: 50)
    bank = [{"id": "a", "hypothesis_ids": ["h1", "h2"],
             "guidance": {"evidence_criterion": "Keep complete procedure A."}},
            {"id": "b", "hypothesis_ids": ["h3"],
             "guidance": {"evidence_criterion": "Unrelated procedure B."}}]
    keys = ["h1", "h2"]
    row = {k: row[k] for k in ("id", "text", "spans")}
    own = study.payload(row, "skills", bank, hypothesis_ids=keys)
    empty = study.payload(row, "strong_empty", bank, hypothesis_ids=keys)
    a, b = (json.loads(v["messages"][1]["content"]) for v in (own, empty))
    assert set(a["hypotheses"]) == set(keys)
    assert len(a.pop("evidence_selection_criteria")) == 1 and a == b
    assert own["schema"] == empty["schema"]
    assert "GOLD_MUST_NOT_ENTER_SOLVER" not in json.dumps(own["messages"])
    changed = copy.deepcopy(bank)
    changed[1]["guidance"]["evidence_criterion"] = "Changed unrelated procedure completely."
    assert study.payload(row, "skills", changed, hypothesis_ids=keys) == own
    with pytest.raises(ValueError, match="Distinct original"):
        study.payload(row, "skills", bank, hypothesis_ids=["h1", "h1"])


def test_native_block_join_never_fills_failed_answers_or_drops_denominators():
    from legal_skill_guard.learning.member_contract import combine_block_responses

    row, labels, gold = fixture()
    fragments = []
    for i, keys in enumerate((["h1", "h2"], ["h3"])):
        r = {**response({h: gold[h] for h in keys}), "raw_id": f"real-fragment-{i}"}
        fragments.append({"response": r, "hypothesis_ids": keys,
                          "schema": output_schema(row, keys, [], reporting=False)})
    combined = combine_block_responses(fragments, labels)
    assert json.loads(combined["content"]) == gold
    assert combined["raw_id"] is None and combined["actual_native_raw_ids"] == ["real-fragment-0", "real-fragment-1"]
    assert original_feedback(combined, row, gold, list(labels))["public_valid"]
    bad = copy.deepcopy(fragments)
    bad[1]["response"]["finish_reason"] = "length"
    failed = combine_block_responses(bad, labels)
    assert "h3" not in json.loads(failed["content"]), "No replacement NM or missing-answer repair"
    feedback = original_feedback(failed, row, gold, list(labels))
    metrics = original_metrics([{"response": failed, **feedback}])
    assert not feedback["public_valid"] and metrics["hypotheses"] == 3
    assert metrics["label_correct"] == 0 and metrics["evidence_fn"] == 3


def test_member_one_copy_preserves_complete_long_procedure_and_global_budget():
    from types import SimpleNamespace

    from jsonschema import validate

    from legal_skill_guard.learning.acquisition import source_messages
    from legal_skill_guard.learning.member_contract import (
        EDIT_GUIDANCE,
        actor_messages,
        one_copy_criteria,
    )
    from legal_skill_guard.learning.member_learning import MemberLearning

    row, labels, _ = fixture()
    criterion = "Inspect the named actor and resolve the stated exception before deciding. " * 20
    row = {k: row[k] for k in ("id", "text", "spans")}
    assert len(criterion) > 1200
    bank = [{"id": "shared-inspection", "hypothesis_ids": list(labels), "guidance": {
        "evidence_criterion": criterion}}]
    validate(bank[0]["guidance"], EDIT_GUIDANCE)
    canonical, schema, _ = source_messages(row, labels, "Original task.", [], None)
    messages = actor_messages(canonical, bank, labels)
    body = json.loads(messages[1]["content"])
    assert body["evidence_selection_criteria"] == one_copy_criteria(bank)
    assert messages[1]["content"].count(criterion) == 1
    assert "shared-inspection" not in json.dumps(messages)
    assert all("evidence_selection_criteria" not in h for h in body["hypotheses"].values())
    assert schema == source_messages(row, labels, "Original task.", [], None)[1]
    empty, _, empty_trace = source_messages(row, labels, "Original task.", [], None)
    rendered = actor_messages(empty, [], labels)
    assert json.loads(rendered[1]["content"]) == {
        k: v for k, v in body.items() if k != "evidence_selection_criteria"}
    assert "candidate_original_text" not in json.loads(rendered[1]["content"])
    study = MemberLearning.__new__(MemberLearning)
    study.labels, study.cfg = labels, {"library_token_hard_cap": 4096}
    study.meter = SimpleNamespace(token_count=lambda **_: 100)
    assert study.capacity(bank)["actual_one_copy_criteria"] == 100
    study.meter = SimpleNamespace(token_count=lambda **_: 4097)
    with pytest.raises(AssertionError, match="No pruning"):
        study.capacity(bank)




def test_member_teacher_visibility_is_complete_source_actual_own_and_members(tmp_path):
    from types import SimpleNamespace

    from legal_skill_guard.learning.member_contract import expand_member_contrasts
    from legal_skill_guard.learning.member_learning import MemberLearning
    from legal_skill_guard.learning.packing import expand
    from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

    row, labels, gold = fixture()
    source = {k: row[k] for k in ("id", "text", "spans")}
    study = MemberLearning.__new__(MemberLearning)
    study.labels, study.system, study.out = labels, "Original task.", tmp_path
    study.meter = SimpleNamespace(token_count=lambda **_: 50)
    study.cfg = {"generation": {"max_tokens": 8192, "context_tokens": 32768},
                 "teacher_evidence_view": "source_only_original_member_tables",
                 "library_token_hard_cap": 4096, "historical_publications": [],
                 "grading_only": str(tmp_path / "gold.json")}
    study.bank = [{"id": "s1", "hypothesis_ids": ["h1"], "guidance": {
        "evidence_criterion": "Inspect actor and exception scope."}}]
    study.banks = {csha(study.bank): copy.deepcopy(study.bank)}
    payload = study.payload(source, "skills", study.bank)
    answer = {h: {**g, "reason": "Synthetic source decision."} for h, g in gold.items()}
    answer["h1"]["spans"] = [0]
    own = response(answer)
    pp, rp = tmp_path / "own_payload.json", tmp_path / "own_native.json"
    RunStore.immutable_json(pp, payload)
    RunStore.immutable_json(rp, {"response": own})
    RunStore.immutable_json(tmp_path / "gold.json", {"original_TRAIN_annotations": {"1": gold}})
    study.own_history = [{"document_id": 1, "condition": "skills", "stage": "b1_before",
        "bank_sha256": csha(study.bank), "native_schema_valid": True,
        "payload": str(pp), "raw_artifact": str(rp), "response": own}]
    value = study.teacher_body([source])
    body = expand(value["body"])
    assert "actual_visible_ordinary_candidates_by_source" not in body
    assert "shared_fixed_ordinary_model_state" not in body
    assert not hasattr(study, "model") and body["source_only_actor_without_retrieval"]
    assert body["actual_own_public_observations"][0]["actual_public_answer"] == answer
    contrast = expand_member_contrasts(body["member_contrasts_by_hypothesis"],
                                      body["complete_cumulative_original_TRAIN_sources_and_Gold"])
    assert {m["original_span_index"] for m in contrast["h1"][0]["members"]} == {0, 2}
    assert all(set(m) == {"original_span_index", "original_member", "actually_cited", "original_text"}
        for m in contrast["h1"][0]["members"])
    profile = body["hypothesis_error_profiles"]["h1"]
    assert profile["label_correct"] == 1 and profile["true_cited_members"] == 1
    assert profile["omitted_members"] == profile["omitted_members_with_correct_relation"] == 1
    assert profile["omitted_members_with_wrong_relation"] == profile["joint_exact"] == 0


def test_procedural_delivery_is_real_system_guidance_without_current_gold():
    from legal_skill_guard.learning.procedures import procedure_messages

    row, labels, _ = fixture()
    bank = [{k: v for k, v in skill().items() if k != "queries"}]
    messages, schema = procedure_messages(row, labels, "Original task.", bank, None)
    assert bank[0]["guidance"] in messages[0]["content"]
    assert "GOLD_MUST_NOT_ENTER_SOLVER" not in json.dumps(messages)
    assert procedure_messages(
        {**row, "annotation_sets": "FORBIDDEN"}, labels, "Original task.", bank, None
    ) == (messages, schema)
    body = json.loads(messages[1]["content"])
    assert body["output_contract"]["common_schema_for_each_hypothesis"]["properties"]["spans"][
        "items"
    ] == {"type": "integer"}
    assert schema["properties"]["h1"]["anyOf"][0]["properties"]["spans"]["items"]["enum"] == [
        0,
        1,
        2,
    ]


def test_local_executor_trace_requires_exact_native_identity_and_content(tmp_path):
    from legal_skill_guard.learning.procedures import local_executor_trace

    public = response({})
    path = tmp_path / "local.native.json"
    native = {
        "response": public,
        "calls": [
            {
                "response": {
                    "id": public["raw_id"],
                    "choices": [
                        {
                            "message": {
                                "content": public["content"],
                                "reasoning_content": "Untrusted local model text.",
                            }
                        }
                    ],
                }
            }
        ],
    }
    RunStore.immutable_json(path, native)
    unit = {"response": public, "raw_artifact": str(path)}
    assert local_executor_trace(unit) == {
        "raw_id": public["raw_id"],
        "reasoning_content_verbatim": "Untrusted local model text.",
    }
    with pytest.raises(ValueError, match="identity mismatch"):
        local_executor_trace({**unit, "response": {**public, "raw_id": "another-native"}})
    missing = copy.deepcopy(native)
    del missing["calls"][0]["response"]["choices"][0]["message"]["reasoning_content"]
    missing_path = tmp_path / "no-trace.native.json"
    RunStore.immutable_json(missing_path, missing)
    with pytest.raises(ValueError, match="unavailable"):
        local_executor_trace({**unit, "raw_artifact": str(missing_path)})


def test_atomic_boundaries_are_native_conditional_guidance_not_host_verdicts():
    from jsonschema import validate

    from legal_skill_guard.learning.procedures import (
        BOUNDARY_GUIDANCE_SCHEMA,
        boundary_skill_schema,
        procedure_messages,
    )
    from legal_skill_guard.learning.publication import apply_differential_publication

    row, labels, _ = fixture()
    rule = {
        "id": "prohibition-support",
        "hypothesis_ids": ["h1"],
        "guidance": {
            "when": "The source establishes the same prohibition as the hypothesis.",
            "inspection": "Check actor, action, scope and exceptions against the statement.",
            "relation_if_established": "Entailment",
            "evidence_requirement": "Retain the operative clause and its governing scope.",
        },
    }
    validate(rule, boundary_skill_schema(labels))
    edit = {
        "operations": [
            {
                "operation": "CREATE",
                "target_ids": [],
                "skill": rule,
                "source_case_ids": [1],
                "rationale": "Seen relative-polarity boundary.",
            }
        ],
        "noop_reason": None,
    }
    bank = apply_differential_publication(
        [], edit, labels, [1], guidance_schema=BOUNDARY_GUIDANCE_SCHEMA
    )
    proposal = {
        "selection": "fixed p>.5",
        "by_hypothesis": {
            k: {"candidates": [{"original_span_index": 0, "membership_score": 0.8}]} for k in labels
        },
    }
    messages, schema = procedure_messages(row, labels, "Original task.", bank, proposal)
    body = json.loads(messages[1]["content"])
    assert "GOLD_MUST_NOT_ENTER_SOLVER" not in json.dumps(messages)
    assert body["hypotheses"]["h1"]["original_hypothesis"] == labels["h1"]["hypothesis"]
    assert body["hypotheses"]["h1"]["applicable_published_skill_ids"] == [rule["id"]]
    assert body["hypotheses"]["h2"]["applicable_published_skill_ids"] == []
    assert (
        body["hypotheses"]["h1"]["fallible_evidence_candidates"]
        == proposal["by_hypothesis"]["h1"]["candidates"]
    )
    assert "candidate_members_by_hypothesis" not in body["learned_source_evidence_tool"]
    assert messages[0]["content"].count(rule["guidance"]["when"]) == 1
    # Native choices still include E/C/NM. The learned rule does not force E.
    choices = schema["properties"]["h1"]["anyOf"]
    assert choices[0]["properties"]["choice"]["enum"] == ["Entailment", "Contradiction"]
    assert choices[1]["properties"]["choice"]["enum"] == ["NotMentioned"]
    assert procedure_messages(
        {**row, "annotation_sets": "FORBIDDEN"}, labels, "Original task.", bank, proposal
    ) == (messages, schema)
    helper = copy.deepcopy(rule)
    helper["guidance"]["relation_if_established"] = None
    validate(helper, boundary_skill_schema(labels))


def test_capacity_counts_exact_delivered_library_not_whitespace_expanded_json():
    from legal_skill_guard.learning.procedures import ProcedureStudy, procedure_messages
    from legal_skill_guard.task import render_library

    row, labels, _ = fixture()
    bank = [
        {
            "id": "boundary",
            "hypothesis_ids": ["h1"],
            "guidance": {
                "when": "The original source establishes the condition.",
                "inspection": "Check actor, scope and exceptions.",
                "relation_if_established": None,
                "evidence_requirement": "Keep all supporting original spans.",
            },
        }
    ]
    messages, _ = procedure_messages(row, labels, "Original task.", bank, None)
    delivered = messages[0]["content"].split("\nReusable skills: ", 1)[1]
    assert delivered == render_library(bank)
    assert json.loads(delivered) == bank
    assert len(delivered) < len(json.dumps(bank, ensure_ascii=False))
    study = object.__new__(ProcedureStudy)
    study.labels = labels
    study.cfg = {"library_token_hard_cap": len(delivered)}

    class ExactPayloadMeter:
        def token_count(self, *, text):
            assert text == delivered
            return len(text)  # Pure payload spy; not a replacement production tokenizer.

    study.meter = ExactPayloadMeter()
    assert study.validate_library(bank) == len(delivered)
    study.cfg["library_token_hard_cap"] -= 1
    with pytest.raises(ValueError, match="exceeds capacity"):
        study.validate_library(bank)


def test_teacher_preserves_all_seen_sources_but_only_exact_parent_current_observations():
    from legal_skill_guard.learning.procedures import ProcedureStudy
    from legal_skill_guard.utils.hashing import canonical_json_sha256

    row, _, _ = fixture()
    study = object.__new__(ProcedureStudy)
    study.training = [
        {**copy.deepcopy(row), "id": i, "batch": (i - 1) // 6 + 1} for i in range(1, 19)
    ]
    study.bank, study.state = [], "ordinary-parent"

    def unit(i, valid):
        return {
            "id": i,
            "public_valid": valid,
            "published_library": [],
            "published_library_sha256": canonical_json_sha256([]),
            "actual_factual_trace": {"ordinary_model_state": study.state},
        }

    study.before = {i: unit(i, i % 2 == 0) for i in range(13, 19)}
    study.after = {i: unit(i, i % 2 == 0) for i in range(7, 13)}
    study.observation = lambda u, include_trace: {
        "id": u["id"],
        "public_valid": u["public_valid"],
        "trace": include_trace,
    }
    cases = study.teacher_cases(3, include_trace=True)
    assert [r["document_id"] for r in cases] == list(range(1, 19))
    assert {r["observation_kind"] for r in cases} == {
        "current_batch_first_encounter",
        "previous_batch_post_update",
        "earlier_original_source_without_current_parent_observation",
    }
    assert all(r["actual_own_same_parent_observation"] is None for r in cases[:6])
    observed = [r["actual_own_same_parent_observation"] for r in cases[6:]]
    assert len(observed) == 12 and sum(r["public_valid"] for r in observed) == 6
    assert all("original_annotations" in r for r in cases)
    # A stale tool or library is rejected, not silently replaced or ignored.
    study.after[7]["actual_factual_trace"]["ordinary_model_state"] = "stale-tool"
    with pytest.raises(ValueError, match="exact current parent"):
        study.teacher_cases(3, include_trace=True)


def test_library_management_describes_merge_delete_and_noop_without_growth():
    from legal_skill_guard.learning.publication import (
        apply_differential_publication,
        publication_statistics,
    )

    _, labels, _ = fixture()
    parent = [{k: v for k, v in skill(sid).items() if k != "queries"} for sid in ("s1", "s2", "s3")]
    value = {
        "operations": [
            {
                "operation": "MERGE",
                "target_ids": ["s1", "s2"],
                "skill": parent[0],
                "source_case_ids": [1],
                "rationale": "Same actual boundary.",
            },
            {
                "operation": "DELETE",
                "target_ids": ["s3"],
                "skill": None,
                "source_case_ids": [1],
                "rationale": "Contradicted by seen evidence.",
            },
        ],
        "noop_reason": None,
    }
    bank = apply_differential_publication(parent, value, labels, [1])
    assert bank == parent[:1]
    stats = publication_statistics(parent, value, bank, 100)
    assert stats["removed_ids"] == ["s2", "s3"]
    assert stats["operation_counts"] == {"CREATE": 0, "UPDATE": 0, "DELETE": 1, "MERGE": 1}
    noop = {"operations": [], "noop_reason": "No warranted boundary change."}
    assert apply_differential_publication(bank, noop, labels, [1]) == bank
    assert publication_statistics(bank, noop, bank, 100)["explicit_noop"]


def test_external_scoring_includes_original_nm_negatives_and_real_query_columns():
    import numpy as np

    from legal_skill_guard.learning.evidence_programs import evidence_proposals, fit_program_model

    row, labels, _ = fixture()
    rows = [{**copy.deepcopy(row), "id": i} for i in range(1, 5)]
    base = fit_program_model(rows, labels, [])
    model = fit_program_model(rows, labels, [skill()])
    assert len(model.scoring_pairs_) == 12
    assert sum(a["label"] == "NotMentioned" for a in model.scoring_pairs_) == 4
    assert model.n_full_ == base.n_full_
    assert model.n_free_ == base.n_free_
    assert not any(n.startswith("program_") for n in model.feature_names_)
    learned = model.program_feature_coefficients_["h1"]["coefficients"]
    assert abs(learned["program_s1__q0_match"]) > 1e-8
    assert abs(learned["program_s1__q0_context"]) > 1e-8
    assert not any(model.program_feature_coefficients_["h2"]["coefficients"].values())
    assert model.feature_protocol == "joint_word_query_contract_oof_calibration_v2"
    # Queries must enter both the final word/query fit and contract-held-out
    # fits used to train the calibration head, not only final inference.
    assert model.stage1_design_widths_["h1"] == base.X1_.shape[1] + 2
    assert model.lr_["h1"].coef_.shape[1] == model.stage1_design_widths_["h1"]
    assert any(not np.allclose(base.oof_s1_[k], model.oof_s1_[k], equal_nan=True)
               for k in base.oof_s1_ if k[1] == "h1")
    assert len(model.stage1_oof_source_partitions_) == 12
    for partition in model.stage1_oof_source_partitions_:
        assert not set(partition["training_doc_ids"]) & set(partition["scored_doc_ids"])
        assert partition["design_width"] == model.stage1_design_widths_[partition["hypothesis_key"]]
        assert partition["training_doc_ids"] and partition["scored_doc_ids"]
    assert base.m2_free_.booster_.model_to_string() == model.m2_free_.booster_.model_to_string()
    # Annotations of the currently scored source are not even accepted by the
    # public-document adapter. Only the saved TRAIN state supplies supervision.
    p = evidence_proposals(model, row, labels)
    q = evidence_proposals(model, {**row, "annotation_sets": "FORBIDDEN"}, labels)
    assert p == q
    for record in p["by_hypothesis"].values():
        assert np.isfinite(record["raw_scores"]).all()
        assert [c["original_span_index"] for c in record["candidates"]] == [
            i for i, s in enumerate(record["raw_scores"]) if s > 0.5
        ]
    assert evidence_proposals(None, row, labels) is None


def test_pure_executable_features_preserve_source_and_original_fold_contract():
    import numpy as np

    from legal_skill_guard.learning.executable_features import (
        execute_source_features, fit_feature_model, validate_library,
    )

    row, labels, _ = fixture()
    program = {
        "id": "source_surface",
        "hypothesis_ids": ["h1"],
        "guidance": {
            "feature_names": ["contains_shall", "terminal_period"],
            "python_source": "def span_features(text, spans):\n"
            "    return [[float('shall' in text[a:b].lower()), "
            "float(text[a:b].strip().endswith('.'))] for a, b in spans]\n",
        },
    }
    validate_library([program], labels)
    matrix, receipt = execute_source_features(program, row)
    other, other_receipt = execute_source_features(
        program, {**row, "annotation_sets": "FORBIDDEN", "id": "NOT_PASSED"})
    np.testing.assert_array_equal(matrix, other)
    assert receipt == other_receipt
    assert matrix.shape == (len(row["spans"]), 2)
    rows = [{**copy.deepcopy(row), "id": i} for i in range(1, 5)]
    ordinary = fit_feature_model(rows, labels, [])
    learned = fit_feature_model(rows, labels, [program])
    assert learned.n_full_ == ordinary.n_full_
    assert learned.stage1_design_widths_["h1"] == ordinary.X1_.shape[1]
    assert len(learned.residual_coefficients["h1"]) == 2
    assert learned.base_fit_count == 5
    for partition in learned.outer_source_partitions:
        assert not set(partition["training_doc_ids"]) & set(partition["scored_doc_ids"])
    for partition in learned.stage1_oof_source_partitions_:
        assert not set(partition["training_doc_ids"]) & set(partition["scored_doc_ids"])
    assert learned.source_execution_receipts
    assert not learned._source_feature_cache


def test_anchored_source_probability_has_exact_zero_identity_not_error_fallback():
    import numpy as np

    from legal_skill_guard.learning.executable_features import anchored_probability

    base = np.array([.1, .5, .9])
    features = np.array([[0., 0.], [1., 0.], [0., 0.]])
    result = anchored_probability(base, features, np.array([1., -1.]))
    np.testing.assert_array_equal(result[[0, 2]], base[[0, 2]])
    assert result[1] > base[1]
    with pytest.raises(ValueError):
        anchored_probability(np.array([0.]), np.zeros((1, 2)), np.zeros(2))


def test_semantic_source_features_use_one_complete_public_request_without_answers():
    import numpy as np

    from legal_skill_guard.learning.executable_features import (
        execute_semantic_features, semantic_feature_request, validate_library,
    )

    row, labels, _ = fixture()
    library = [{"id": "semantic", "hypothesis_ids": ["h1"], "guidance": {
        "feature_names": ["retention_permission", "duty_of_confidence"],
        "source_predicates": ["Recipient is expressly permitted to retain a copy.",
                              "Recipient has a duty not to disclose confidential information."]}}]
    validate_library(library, labels)
    messages, schema, _ = semantic_feature_request(library, row)
    encoded = json.dumps(messages)
    assert "GOLD_MUST_NOT_ENTER_SOLVER" not in encoded
    assert "annotation_sets" not in encoded and "source_case_id" not in encoded
    assert "Recipient may retain an archive." in encoded
    assert "Purpose is evaluation." in encoded
    calls = []

    def native(msg, contract, document):
        calls.append((msg, contract))
        assert document["text"] == row["text"]
        return response({"f0": [1], "f1": [0]})

    values, receipt = execute_semantic_features(library, row, native)
    assert calls == [(messages, schema)]
    np.testing.assert_array_equal(values["semantic"], [[0, 1], [1, 0], [0, 0]])
    assert receipt["one_actual_native_call_no_Gold_ID_scores_or_final_verdict"]
    assert receipt["raw_id"] == "native-test"
    bad = copy.deepcopy(library)
    bad[0]["guidance"]["source_predicates"].pop()
    with pytest.raises(ValueError, match="exactly one"):
        validate_library(bad, labels)
    with pytest.raises(ValueError, match="Duplicate semantic"):
        execute_semantic_features(library, row, lambda *_: response({"f0": [1, 1], "f1": []}))
    with pytest.raises(ValueError, match="Incomplete semantic"):
        execute_semantic_features(library, row, lambda *_: response({"f0": [], "f1": []}, finish="length"))
    with pytest.raises(ValidationError):
        execute_semantic_features(library, row, lambda *_: response({"f0": [99], "f1": []}))


def test_semantic_feature_model_scopes_batches_and_requires_explicit_transport():
    import pickle
    import numpy as np

    from legal_skill_guard._vendor.scienceclaw_contracts import _Corpus
    from legal_skill_guard.learning.evidence_programs import public_document
    from legal_skill_guard.learning.executable_features import AnchoredFeatureModel

    row, labels, _ = fixture()
    library = [{"id": "semantic", "hypothesis_ids": ["h1"], "guidance": {
        "feature_names": ["retention_permission"],
        "source_predicates": ["Recipient is expressly permitted to retain a copy."]}}]
    calls = []
    def native(*args):
        calls.append(args)
        return response({"f0": [1]})
    model = AnchoredFeatureModel(library, labels, semantic_caller=native)
    corpus = _Corpus([public_document(row)])
    np.testing.assert_array_equal(model.source_features(corpus, "h1"), [[0], [1], [0]])
    assert not model.source_features(corpus, "h2").any()
    assert len(calls) == 1, "Scope application must not repeat the semantic call per hypothesis"
    restored = pickle.loads(pickle.dumps(model))
    assert restored._semantic_caller is None
    restored._source_feature_cache.clear()
    with pytest.raises(ValueError, match="explicit same-model"):
        restored.source_features(corpus, "h1")


@pytest.mark.parametrize("body", [
    "import os\ndef span_features(text, spans):\n    return []\n",
    "def span_features(text, spans):\n    return open('/etc/passwd').read()\n",
    "def span_features(text, spans):\n    return ().__class__.__base__\n",
])
def test_executable_feature_code_rejects_external_capabilities(body):
    from legal_skill_guard.learning.executable_features import validate_source

    with pytest.raises(ValueError):
        validate_source(body)


@pytest.mark.parametrize("finish", ["length", "stop"])
def test_invalid_keeps_all_denominators(finish):
    row, labels, gold = fixture()
    r = response({}, finish)
    feedback = original_feedback(r, row, gold, list(labels))
    m = original_metrics([{"response": r, **feedback}])
    assert not feedback["public_valid"]
    assert m["hypotheses"] == 3 and m["label_correct"] == 0
    assert m["evidence_fn"] == 3 and m["joint_exact_correct"] == 0


def test_scope_and_original_text_never_gold_or_legal_verdict():
    row, labels, _ = fixture()
    bank = [skill()]
    plan = scope_plan(labels, bank)
    trace = execute_plan(row, labels, bank, plan)
    hit = trace["h1"]["published_skill_invocations"][0]["receipts"][0]
    assert hit["matched_original_span_indices"] == [0]
    assert [c["original_span_index"] for c in hit["context_original_clauses"]] == [0, 1]
    assert trace["h2"]["published_skill_invocations"] == []
    assert not {"choice", "gold", "annotation_sets"} & hit.keys()
    messages, _ = final_messages(row, labels, bank, "Original task.", trace)
    assert "GOLD_MUST_NOT_ENTER_SOLVER" not in json.dumps(messages)
    assert "Recipient may retain an archive." in messages[1]["content"]
    encoded = encode_receipts(compact_receipts(trace))
    assert decode_receipts(encoded) == compact_receipts(trace)
    assert execute_plan({**row, "annotation_sets": "FORBIDDEN"}, labels, bank, plan) == trace


def test_teacher_catalog_roundtrip_keeps_bad_answers_and_duplicate_actions():
    row, labels, gold = fixture()
    bank = [skill(scope=["h1", "h2"])]
    plan = scope_plan(labels, bank)
    trace = compact_receipts(execute_plan(row, labels, bank, plan))
    observation = {
        "stage": "before",
        "public_valid": False,
        "public_error": "bad answer",
        "parsed_public_answer": None,
        "unparsed_public_content": "wrong",
        "actual_plan": plan,
        "actual_factual_trace": trace,
        "policy_version_sha256": "old",
        "original_component_feedback": [{"hypothesis_id": k, "evidence_fn": 1} for k in labels],
        "raw_id": "native-test",
        "plan_raw_id": None,
        "raw_artifact": "public.json",
        "plan_native_artifact": None,
    }
    cases = [
        {
            "document_id": 1,
            "original_full_contract_with_spans": row["text"],
            "original_annotations": gold,
            "actual_before_publication_observations": [observation],
            "actual_prior_post_publication_observations": [],
        }
    ]
    original = {
        "all_seen_train_cases": pack_cases(cases),
        "actual_historical_policy_versions": {"old": bank},
    }
    decoded = decode_teacher_body(encode_teacher_body(original))
    assert decoded["all_seen_train_cases"] == cases
    assert decoded["actual_historical_policy_versions"] == {"old": bank}


def test_review_receives_exact_untrusted_draft_scoped_checks_and_never_gold():
    row, labels, gold = fixture()
    draft = response(gold)
    bank = [{"id": "inspect1", "hypothesis_ids": ["h1"], "guidance": "Check the trigger."}]
    messages, schema = review_messages(row, labels, bank, "Original task.", draft)
    body = json.loads(messages[1]["content"])
    assert "GOLD_MUST_NOT_ENTER_SOLVER" not in json.dumps(messages)
    assert body["untrusted_actual_initial_answer"]["content"] == draft["content"]
    assert body["learned_inspection_skills_by_hypothesis"]["h1"] == [
        {"id": "inspect1", "guidance": "Check the trigger."}
    ]
    assert body["learned_inspection_skills_by_hypothesis"]["h2"] == []
    assert "Recipient may retain an archive." in body["full_contract_with_original_span_markers"]
    fields = schema["properties"]
    assert fields["h1"]["properties"]["used_skill_ids"]["items"]["enum"] == ["inspect1"]
    assert fields["h2"]["properties"]["used_skill_ids"]["maxItems"] == 0
    poisoned = {**row, "annotation_sets": "FORBIDDEN"}
    assert review_messages(poisoned, labels, bank, "Original task.", draft) == (messages, schema)
    # Review is mandatory on malformed drafts too; no valid-answer fallback or
    # gold-assisted repair replaces the actual earlier model output.
    malformed = response({}, finish="length")
    broken_messages, _ = review_messages(row, labels, [], "Original task.", malformed)
    assert json.loads(broken_messages[1]["content"])["untrusted_actual_initial_answer"] == {
        "content": "{}",
        "finish_reason": "length",
    }


def test_empty_review_is_exact_cold_skill_review_contract():
    row, labels, gold = fixture()
    draft = response(gold)
    a, schema = review_messages(row, labels, [], "Original task.", draft)
    b, other = review_messages(row, labels, [], "Original task.", draft)
    assert a == b and schema == other
    # Only source, public task, exact draft and learned bank enter the function;
    # final metrics still score the native response, including harmful changes.
    altered = copy.deepcopy(gold)
    altered["h1"] = {"choice": "NotMentioned", "spans": []}
    r = response(altered)
    metrics = original_metrics([{"response": r, **original_feedback(r, row, gold, list(labels))}])
    assert metrics["label_correct"] == 2 and metrics["evidence_fn"] == 2


def test_source_checks_are_required_before_final_and_never_receive_gold_or_draft():
    row, labels, gold = fixture()
    bank = [{"id": "inspect1", "hypothesis_ids": ["h1"], "guidance": "Which text binds the actor?"}]
    messages, schema = checked_messages(row, labels, bank)
    body = json.loads(messages[1]["content"])
    assert "GOLD_MUST_NOT_ENTER_SOLVER" not in json.dumps(messages)
    assert "draft" not in body
    assert body["source_check_questions_by_hypothesis"]["h1"] == {
        "inspect1": "Which text binds the actor?"
    }
    assert set(body["source_check_questions_by_hypothesis"]["h2"]) == {"public_task"}
    assert checked_messages({**row, "annotation_sets": "FORBIDDEN"}, labels, bank) == (
        messages,
        schema,
    )
    fields = schema["properties"]
    assert list(fields["h1"]["properties"]) == [
        "checks",
        "choice",
        "spans",
        "reason",
        "used_skill_ids",
    ]
    assert fields["h1"]["properties"]["checks"]["required"] == ["inspect1"]
    assert fields["h2"]["properties"]["checks"]["required"] == ["public_task"]
    answer = copy.deepcopy(gold)
    for key, value in answer.items():
        sid = "inspect1" if key == "h1" else "public_task"
        value.update(
            checks={sid: {"observations": [], "finding": "No matching condition found."}},
            reason="Native decision.",
            used_skill_ids=["inspect1"] if key == "h1" else [],
        )
    from jsonschema import validate

    validate(answer, schema)
    # Even an inconsistent inspection finding does not rewrite the native final
    # answer. The original scorer reads its unchanged choice/spans fields.
    feedback = original_feedback(response(answer), row, gold, list(labels))
    assert feedback["public_valid"]
    assert all(q["joint_exact"] for q in feedback["queries"])
    del answer["h1"]["checks"]["inspect1"]
    with pytest.raises(ValidationError):
        validate(answer, schema)


def test_source_check_scope_never_borrows_another_hypothesis_key():
    row, labels, _ = fixture()
    bank = [
        {"id": "a", "hypothesis_ids": ["h1"], "guidance": "Check permission wording."},
        {"id": "b", "hypothesis_ids": ["h2"], "guidance": "Check the termination trigger."},
    ]
    _, schema = checked_messages(row, labels, bank)
    fields = schema["properties"]
    assert set(fields["h1"]["properties"]["checks"]["properties"]) == {"a"}
    assert set(fields["h2"]["properties"]["checks"]["properties"]) == {"b"}
    assert fields["h1"]["properties"]["used_skill_ids"]["items"]["enum"] == ["a"]
    assert fields["h2"]["properties"]["used_skill_ids"]["items"]["enum"] == ["b"]
    assert fields["h3"]["properties"]["used_skill_ids"]["maxItems"] == 0


def op(kind, targets, candidate):
    return {
        "operation": kind,
        "target_ids": targets,
        "skill": candidate,
        "source_case_ids": [1],
        "rationale": "Source-derived boundary correction.",
    }


def test_atomic_publication_preserves_unmentioned_and_supports_full_lifecycle():
    ids = ["h1", "h2", "h3"]
    a, b = skill("a"), skill("b")
    parent = [a, b]
    saved = copy.deepcopy(parent)
    changed = {**a, "guidance": "Preserve full exception scope."}
    result = publish(
        parent, {"operations": [op("UPDATE", ["a"], changed)], "noop_reason": None}, ids, [1]
    )
    assert result == [changed, b] and parent == saved
    merged = publish(
        parent, {"operations": [op("MERGE", ["a", "b"], skill("m"))], "noop_reason": None}, ids, [1]
    )
    assert merged == [skill("m")]
    deleted = publish(
        parent, {"operations": [op("DELETE", ["a"], None)], "noop_reason": None}, ids, [1]
    )
    assert deleted == [b]
    created = publish([], {"operations": [op("CREATE", [], a)], "noop_reason": None}, ids, [1])
    assert created == [a]
    assert (
        publish(parent, {"operations": [], "noop_reason": "No justified change."}, ids, [1])
        == parent
    )
    with pytest.raises(ValueError):
        publish(
            parent,
            {
                "operations": [op("DELETE", ["a"], None), op("UPDATE", ["a"], changed)],
                "noop_reason": None,
            },
            ids,
            [1],
        )
    assert parent == saved
    with pytest.raises(ValidationError):
        publish([], {"operations": [op("CREATE", [], a)], "noop_reason": None}, ids, [2])


def test_source_components_are_transitive_without_annotations():
    rows = [
        {"id": 1, "url": "u", "text": "A!"},
        {"id": 2, "url": "u", "text": "B"},
        {"id": 3, "url": "other", "text": " b "},
        {"id": 4, "url": "", "text": "Z"},
    ]
    assert sorted(source_components(rows)) == [[1, 2, 3], [4]]


def test_ace_preserves_authors_last_duplicate_tag():
    text = "## OTHERS\n[oth-00001] helpful=0 harmful=0 :: Inspect source."
    changed = update_bullet_counts(
        text, [{"id": "oth-00001", "tag": "helpful"}, {"id": "oth-00001", "tag": "harmful"}]
    )
    assert "helpful=0 harmful=1" in changed


def test_immutable_artifact_conflict_is_not_overwrite(tmp_path):
    p = tmp_path / "output.json"
    RunStore.immutable_json(p, {"a": 1})
    RunStore.immutable_json(p, {"a": 1})
    with pytest.raises(ImmutableArtifactConflictError):
        RunStore.immutable_json(p, {"a": 2})
    assert json.loads(p.read_text()) == {"a": 1}


def test_lost_ledger_prefix_is_accounted_but_not_fabricated(tmp_path):
    ledger = tmp_path / "ledger.json"
    RunStore.immutable_json(
        ledger,
        {
            "schema_version": 2,
            "model": "gpt-5.6-sol",
            "max_invocations": 10,
            "historical_count_lower_bound": 8,
            "reservations": [],
        },
    )
    client = CodexCLIClient(
        model="gpt-5.6-sol",
        cache_root=tmp_path / "cache",
        invocation_budget_path=ledger,
        max_invocations=10,
    )
    assert client.invocation_budget_status()["available"] == 2
    r = client._reserve_invocation(
        purpose="contract-test", request_sha256="not-model-call", attempt=0
    )
    assert r["sequence"] == 9 and r["new_epoch_sequence"] == 1
    assert len(json.loads(ledger.read_text())["reservations"]) == 1
    assert client.invocation_budget_status()["available"] == 1


def test_finite_schedule_is_the_latest_not_the_consultation_task():
    cfg = json.loads(
        (Path(__file__).resolve().parents[1] / "configs/contractnli_main.json").read_text()
    )
    assert sum(cfg["native_schedule"].values()) == cfg["planned_new_native_calls"] == 388
    assert sum(cfg["teacher_schedule"].values()) == cfg["planned_new_teacher_calls"] == 57
    assert cfg["learning_batches"] == 8 and cfg["generation"]["seed"] == 44


def test_unsupported_schema_is_rejected_before_teacher_request(tmp_path):
    def forbidden_request(*args, **kwargs):
        raise AssertionError("A local schema rejection must not invoke a process")

    client = CodexCLIClient(
        model="gpt-5.6-sol", cache_root=tmp_path, command_runner=forbidden_request, retries=0
    )
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["tags"],
        "properties": {"tags": {"type": "array", "items": {"type": "string"}, "uniqueItems": True}},
    }
    with pytest.raises(CodexInvocationError, match="uniqueItems_not_supported"):
        client.generate_json(
            purpose="local-schema-check",
            system_prompt="No call.",
            user_prompt="",
            output_schema=schema,
        )


def test_report_uses_saved_denominators_and_separates_probe(tmp_path):
    def metrics(documents):
        return {
            "arm": {
                "documents": documents,
                "hypotheses": documents * 17,
                "label_accuracy": 0.5,
                "evidence_micro_f1_gold_non_neutral": 0.25,
                "joint_exact_accuracy": 0.125,
            }
        }

    cases = {
        "legacy": {"development": metrics(8)},
        "adaptive": {"results": metrics(8)},
        "fork": {"main_results": metrics(8), "probe_results": metrics(4)},
    }
    for name, completion in cases.items():
        run = tmp_path / name
        RunStore.immutable_json(run / "completion.json", completion)
        write_report(run)
        text = (run / "results.md").read_text()
        assert "每条件8份合同、136个命题" in text and "24个不同TRAIN" not in text
        assert ("每条件4份合同、68个命题" in text) == (name == "fork")
        assert json.loads((run / "completion.json").read_text()) == completion


@pytest.mark.parametrize("tamper", [False, True])
def test_auth_completion_replays_exact_failed_editor_without_repeating_audit(tmp_path, tamper):
    from legal_skill_guard.learning.conditioned import (
        EDITOR_AUDIT_INSTRUCTION, GUIDANCE_SCHEMA, HISTORY_TEACHER_SYSTEM, ConditionedCompletion,
    )
    from legal_skill_guard.learning.publication import differential_schema
    from legal_skill_guard.utils.hashing import canonical_json_sha256

    row, labels, _ = fixture()
    study = object.__new__(ConditionedCompletion)
    study.parent, study.out = tmp_path / "parent", tmp_path / "completion"
    study.bank, study.labels, study.training = [], labels, [row]
    study.cfg = {"teacher": {"model": "gpt-5.6-sol", "reasoning_effort": "high"}}
    audit = {"complete_original_audit": True}
    body = {
        "complete_actual_parent_library": [],
        "actual_parent_library_sha256": "changed" if tamper else canonical_json_sha256([]),
        "cumulative_seen_original_train_cases": [{"document_id": row["id"]}],
        "training_only_parent_source_condition_audit": audit,
    }
    request = {
        **study.cfg["teacher"],
        "system_prompt": HISTORY_TEACHER_SYSTEM + EDITOR_AUDIT_INSTRUCTION,
        "user_prompt": json.dumps(body, indent=3) + "\n",
        "output_schema": differential_schema(labels, [], [row["id"]], guidance_schema=GUIDANCE_SCHEMA),
    }
    RunStore.immutable_json(study.parent / "teacher/source_conditioned_b4/wire_request.json", request)
    RunStore.immutable_json(study.parent / "source_condition_audits/b4.json", audit)
    RunStore.immutable_json(study.parent / "failure.json", {"teacher_attempts": 7})
    calls = []
    value = {"operations": [], "noop_reason": "No change supported."}

    def teacher(name, system, user, schema):
        calls.append((name, system, user, schema))
        return value

    study.teacher_call = teacher
    study.validate_library = lambda bank: 0
    if tamper:
        with pytest.raises(ValueError, match="immutable parent"):
            study.complete_failed_editor()
        assert calls == []
    else:
        bank, stats = study.complete_failed_editor()
        assert bank == [] and stats["explicit_noop"]
        assert calls == [("source_conditioned_b4", request["system_prompt"], request["user_prompt"], request["output_schema"])]
        transaction = json.loads((study.out / "update_transactions/b4.json").read_text())
        assert transaction["source_condition_audit_teacher_call"] == "source_condition_audit_b4"


def local_skill():
    return {
        "id": "archive", "hypothesis_ids": ["h2"],
        "guidance": {
            "when": "A source condition, not a retrieval keyword.",
            "inspection": "Inspect the original source and its exceptions.",
            "relation_if_established": None,
            "evidence_requirement": "Keep all original governing evidence.",
            "source_operations": [],
        },
    }


def test_task_local_full_scope_without_source_gate_or_solver_gold():
    from legal_skill_guard.learning.task_local import task_local_messages

    row, labels, _ = fixture()
    messages, schema, delivery = task_local_messages(row, labels, "Review.", [local_skill()], None)
    body = json.loads(messages[1]["content"])
    assert "GOLD_MUST_NOT_ENTER_SOLVER" not in json.dumps(messages)
    assert "annotation_sets" not in json.dumps(messages)
    assert body["hypotheses"]["h1"]["applicable_published_skills"] == []
    assert body["hypotheses"]["h2"]["applicable_published_skills"][0]["id"] == "archive"
    assert body["hypotheses"]["h3"]["applicable_published_skills"] == []
    for h in labels:
        for branch in schema["properties"][h]["anyOf"]:
            used = branch["properties"]["used_skill_ids"]
            assert used["items"]["enum"] == ["archive"] if h == "h2" else used["maxItems"] == 0
    assert list(body["hypotheses"]) == list(labels)
    assert delivery["all17_tasks_remain_in_one_context_not_semantic_isolation"]
    obsolete = local_skill()
    obsolete["guidance"]["source_triggers"] = [["absent"]]
    with pytest.raises(ValueError, match="obsolete routing"):
        task_local_messages(row, labels, "Review.", [obsolete], None)


def test_bounded_teacher_uses_actual_current_and_previous_parent_only():
    from legal_skill_guard.learning.task_local import bounded_teacher_packet, task_local_messages
    from legal_skill_guard.utils.hashing import canonical_json_sha256

    row, labels, gold = fixture()
    bank = [local_skill()]
    training = [{**copy.deepcopy(row), "id": i, "batch": i} for i in range(1, 5)]
    units = {}
    for r in training:
        _, _, delivery = task_local_messages(r, labels, "Review.", bank, None)
        parsed = {h: {**g, "reason": "Observed.", "used_skill_ids": []} for h, g in gold.items()}
        units[r["id"]] = {
            "document_id": r["id"], "stage": f"batch{r['batch']}_{'before' if r['batch'] == 3 else 'after'}", "published_library": bank,
            "published_library_sha256": canonical_json_sha256(bank),
            "public_valid": True, "parsed": parsed,
            "response": {"raw_id": f"r{r['id']}", "finish_reason": "stop", "content": json.dumps(parsed)},
            "actual_factual_trace": {"ordinary_model_state": "M2", "proposals": None, "task_local_delivery": delivery},
        }
    packet = bounded_teacher_packet(training, 3, labels, bank, "M2", {3: units[3]}, {2: units[2]}, master_tokens=100, cap=4096)
    assert packet["supplied_original_witness_ids"] == [2, 3]
    cases = packet["original_cases_and_actual_same_parent_observations"]
    assert [r["document_id"] for r in cases] == [2, 3]
    assert all(r["original_annotations"] == gold for r in cases)
    assert [r["observation_kind"] for r in cases] == ["previous_batch_after", "current_batch_before"]
    assert all(len(rows) == 2 for rows in packet["hypothesis_indexed_original_feedback"].values())
    proposals = {
        "selection": "actual selection",
        "by_hypothesis": {h: {
            "candidates": [{"original_span_index": 0, "membership_score": 0.625}],
            "raw_scores": [0.625, 0.2, 0.1],
            "same_fixed_model_without_query_terms": {"raw_scores": [0.625, 0.2, 0.1]},
            "private_debug_canary": "NOT_A_LAWYER_OBSERVATION" * 50000,
        } for h in labels},
    }
    original_proposals = copy.deepcopy(proposals)
    for u in units.values():
        u["actual_factual_trace"]["proposals"] = proposals
    compact = bounded_teacher_packet(training, 3, labels, bank, "M2", {3: units[3]}, {2: units[2]}, master_tokens=100, cap=4096)
    for case in compact["original_cases_and_actual_same_parent_observations"]:
        view = case["actual_ordinary_proposals"]
        assert set(view) == {"selection", "by_hypothesis"}
        assert view["selection"] == proposals["selection"]
        assert all(v == {"candidates": proposals["by_hypothesis"][h]["candidates"]} for h, v in view["by_hypothesis"].items())
    assert "NOT_A_LAWYER_OBSERVATION" not in json.dumps(compact)
    assert proposals == original_proposals  # Raw archived diagnostics are untouched.
    units[3]["actual_factual_trace"]["ordinary_model_state"] = "stale"
    with pytest.raises(ValueError, match="exact current parent"):
        bounded_teacher_packet(training, 3, labels, bank, "M2", {3: units[3]}, {2: units[2]}, master_tokens=100, cap=4096)


@pytest.mark.parametrize("literal_view,fixed_static,witness_view,source_program_view", [(False, False, False, False), (True, False, False, False), (True, True, False, False), (True, True, True, False), (True, False, False, True)])
def test_task_local_complete_schedule_without_model_calls(tmp_path, monkeypatch, literal_view, fixed_static, witness_view, source_program_view):
    from types import SimpleNamespace
    import legal_skill_guard.learning.task_local as module

    row, labels, gold = fixture()
    from legal_skill_guard.learning.literal_evidence import LiteralEvidenceStudy
    from legal_skill_guard.learning.witness_grounding import WitnessGroundedStudy
    from legal_skill_guard.learning.source_programs import SourceProgramStudy
    study = object.__new__(SourceProgramStudy if source_program_view else WitnessGroundedStudy if witness_view else LiteralEvidenceStudy if literal_view else module.TaskLocalStudy)
    study.cfg = {
        "generation": {"model": "frozen-test", "temperature": 0.6, "top_p": 0.95, "top_k": 20, "max_tokens": 8192, "seed": 45},
        "teacher": {"model": "teacher-test", "ledger": "unused", "total_invocation_budget": 5},
        "library_token_hard_cap": 4096, "planned_new_native_calls": 148, "planned_new_teacher_calls": 4 if fixed_static else 5,
        "bundled_solver_system": "Review.",
    }
    study.out, study.run_id = tmp_path, "scheduler-only-no-generations"
    study.labels, study.bindings = labels, {}
    study.training = [{**copy.deepcopy(row), "id": i, "batch": (i - 1) // 6 + 1} for i in range(1, 25)]
    study.future = [{k: v for k, v in {**row, "id": i}.items() if k != "annotation_sets"} for i in range(25, 33)]
    study.native, study.teachers, study.units, study.aliases, study.summaries = [], [], [], [], []
    study.inherited_native, study.inherited_teachers = [], []
    study.prefix_answers, study.prefix_teachers, study.prefix_slots = {}, {}, set()
    study.bank, study.static, study.before, study.after, study.state_versions = [], [], {}, {}, {}
    study.model, study.state, study.current_batch, study.teacher_attempts, study.stop = None, None, 0, 0, False
    study.meter = SimpleNamespace(token_count=lambda **kwargs: 1, readiness=lambda: {"ready": True})
    monkeypatch.setattr(module, "CodexCLIClient", lambda **kwargs: SimpleNamespace(preflight=lambda: {"ready": True}, invocation_budget_status=lambda: {"available": 5}))
    study.check = lambda: None
    study.fit_ordinary = lambda batch: None
    study.audit_units = lambda units, name: None
    teacher_windows = []

    def teacher(name, system, body, schema):
        if fixed_static and name == "static_public_task_only":
            study.inherited_teachers.append({"name": name})
            return {"library": []}
        study.teacher_attempts += 1
        study.teachers.append({"name": name})
        if name == "static_public_task_only":
            return {"library": []}
        teacher_windows.append(len(body["original_cases_and_actual_same_parent_observations"]))
        value = {"operations": [], "noop_reason": "Schedule simulation only."}
        if witness_view:
            cases = body["original_cases_and_actual_same_parent_observations"]
            value["training_evidence_accounts"] = {
                h: {str(c["document_id"]): {str(i): "Simulation only: original evidence function." for i in c["original_annotations"][h]["spans"]} for c in cases}
                for h in labels
            }
        return value

    def native(dest, messages, schema, max_tokens, metadata):
        answer = {h: {**g, "reason": "Simulation.", "used_skill_ids": []} for h, g in gold.items()}
        response = {"content": json.dumps(answer), "finish_reason": "stop", "prompt_tokens": 1, "completion_tokens": 1, "raw_id": f"sim-{len(study.native)}"}
        wire = {k: study.cfg["generation"][k] for k in ("model", "temperature", "top_p", "top_k", "max_tokens", "seed")}
        wire.update(messages=messages, response_format={"type": "json_schema", "json_schema": {"name": "contractnli_callable_final", "strict": True, "schema": schema}})
        record = {"calls": [{"request": wire}], "response": response, **metadata}
        RunStore.immutable_json(dest, record)
        study.native.append(record)
        return response

    study.teacher_call, study.call = teacher, native
    observed = {}
    study.finish = lambda later: observed.update({"later": later, "native": len(study.native), "teachers": len(study.teachers), "aliases": len(study.aliases), "logical": len(study.units) + len(study.aliases)})
    study.execute()
    assert (observed["native"], observed["teachers"], observed["aliases"], observed["logical"]) == (148, 4 if fixed_static else 5, 18, 166)
    assert len(study.inherited_teachers) == int(fixed_static)
    static_metadata = json.loads((tmp_path / "static_procedures.json").read_text())
    assert static_metadata["explicit_historical_public_only_static_reference"] == fixed_static
    assert all(len(units) == 8 for units in observed["later"].values())
    assert teacher_windows == [6, 12, 12, 12]
    assert len({u["response"]["raw_id"] for u in study.units + study.aliases if u["arm"] == "skill_memory"}) == 62


@pytest.mark.parametrize("tamper", [False, True])
def test_task_local_teacher_prefix_is_exact_historical_input_not_new_call(tmp_path, tamper):
    from legal_skill_guard.learning.task_local import TaskLocalStudy
    from legal_skill_guard.utils.hashing import canonical_json_sha256

    source = tmp_path / "parent"
    body, value, schema = {"observations": "unchanged"}, {"operations": []}, {"type": "object"}
    wire = {"model": "teacher-test", "reasoning_effort": "high", "system_prompt": "Original system.",
            "user_prompt": json.dumps(body, separators=(",", ":")), "output_schema": schema}
    events = {"event_log": "original successful event"}
    result = {"model": "teacher-test", "value": value, "request_sha256": canonical_json_sha256(wire),
              "response_sha256": canonical_json_sha256(value), "cache_hit": False,
              "invocation": {"returncode": 0, "attempt": 1, "tool_events_detected": False,
                             "event_log_sha256": canonical_json_sha256(events)}}
    for name, data in (("wire_request.json", wire), ("response.json", result), ("event_log.json", events)):
        RunStore.immutable_json(source / name, data)
    study = object.__new__(TaskLocalStudy)
    study.out = tmp_path / "child"
    study.cfg = {"teacher": {"model": "teacher-test", "reasoning_effort": "high"}, "continuation_parent": "explicit"}
    study.prefix_teachers = {"task_local_b1": source}
    study.inherited_teachers = []
    if tamper:
        with pytest.raises(ValueError, match="exact original"):
            study.teacher_call("task_local_b1", "Changed system.", body, schema)
        assert study.inherited_teachers == []
    else:
        assert study.teacher_call("task_local_b1", "Original system.", body, schema) == value
        assert len(study.inherited_teachers) == 1
        assert json.loads((study.out / "teacher/task_local_b1/response.json").read_text()) == result
        assert (study.out / "teacher/task_local_b1/explicit_historical_reference.json").exists()


def test_literal_candidates_bind_original_text_without_annotations_or_selection_changes():
    from legal_skill_guard.learning.literal_evidence import literal_candidate_view

    row, labels, _ = fixture()

    class NoGold(dict):
        def __getitem__(self, key):
            if key == "annotation_sets":
                raise AssertionError("Inference must not read current Gold")
            return super().__getitem__(key)

    proposals = {"selection": "same", "by_hypothesis": {h: {
        "candidates": [{"original_span_index": 0, "membership_score": 0.625}],
        "raw_scores": [0.625, 0.2, 0.1],
    } for h in labels}}
    original = copy.deepcopy(proposals)
    value = literal_candidate_view(NoGold(row), proposals)
    assert proposals == original
    for h in labels:
        quoted = value["by_hypothesis"][h]["candidates"][0]
        assert quoted == {**original["by_hypothesis"][h]["candidates"][0], "literal_original_text": "Recipient shall not disclose secrets."}
        assert value["by_hypothesis"][h]["raw_scores"] == original["by_hypothesis"][h]["raw_scores"]
    assert literal_candidate_view(NoGold(row), None) is None
    proposals["by_hypothesis"]["h1"]["candidates"][0]["original_span_index"] = 99
    with pytest.raises(ValueError, match="original source span"):
        literal_candidate_view(NoGold(row), proposals)


def test_literal_teacher_feedback_preserves_all_cases_and_handles_polarity_only_error():
    from legal_skill_guard.learning.literal_evidence import literal_feedback_view

    row, labels, gold = fixture()
    pred = {h: {**g, "reason": "Actual.", "used_skill_ids": []} for h, g in gold.items()}
    pred["h1"]["spans"] = [1, 2]  # One missing and one extra, not a new answer.
    pred["h2"]["choice"] = "Entailment"  # Same evidence, wrong relation.
    cases = [{"document_id": 1, "original_annotations": gold, "actual_public_valid": True,
              "actual_public_response": response(pred), "complete_source": row["text"]}]
    index = {h: [{"document_id": 1, "original_Gold_choice": g["choice"], "original_Gold_span_indices": g["spans"],
                  "label_matches_original": pred[h]["choice"] == g["choice"]}] for h, g in gold.items()}
    packet = {"original_cases_and_actual_same_parent_observations": cases, "hypothesis_indexed_original_feedback": index}
    original = copy.deepcopy(packet)
    view = literal_feedback_view(packet, [row])
    assert packet == original
    assert view["original_cases_and_actual_same_parent_observations"] == cases
    h1 = view["hypothesis_indexed_original_feedback"]["h1"][0]["literal_original_evidence_comparison"]
    assert [(q["original_span_index"], q["original_Gold_member"], q["actual_public_answer_member"]) for q in h1] == [(0, True, False), (1, False, True), (2, True, True)]
    assert h1[0]["literal_original_text"] == "Recipient shall not disclose secrets."
    h2 = view["hypothesis_indexed_original_feedback"]["h2"][0]["literal_original_evidence_comparison"]
    assert [q["original_span_index"] for q in h2] == [1]
    assert view["hypothesis_indexed_original_feedback"]["h3"][0]["literal_original_evidence_comparison"] == []
    correct = copy.deepcopy(packet)
    correct["original_cases_and_actual_same_parent_observations"][0]["actual_public_response"] = response(gold)
    for records in correct["hypothesis_indexed_original_feedback"].values():
        records[0]["label_matches_original"] = True
    grounded_success = literal_feedback_view(correct, [row])
    assert [q["original_span_index"] for q in grounded_success["hypothesis_indexed_original_feedback"]["h1"][0]["literal_original_evidence_comparison"]] == [0, 2]


def test_literal_actual_payload_changes_only_source_view_for_every_matched_tool_arm(monkeypatch):
    from types import SimpleNamespace
    import legal_skill_guard.learning.literal_evidence as literal
    import legal_skill_guard.learning.task_local as local

    row, labels, _ = fixture()

    class NoGold(dict):
        def __getitem__(self, key):
            if key == "annotation_sets":
                raise AssertionError("Inference payload must not read Gold")
            return super().__getitem__(key)

    proposals = {"selection": "unchanged", "by_hypothesis": {h: {
        "candidates": [{"original_span_index": 0, "membership_score": 0.625}],
        "raw_scores": [0.625, 0.2, 0.1],
    } for h in labels}}
    proposal = lambda model, row, labels: copy.deepcopy(proposals) if model is not None else None
    monkeypatch.setattr(literal, "evidence_proposals", proposal)
    monkeypatch.setattr(local, "evidence_proposals", proposal)
    study = object.__new__(literal.LiteralEvidenceStudy)
    study.cfg, study.labels = {"bundled_solver_system": "Review."}, labels
    study.meter = SimpleNamespace(token_count=lambda **kwargs: 1)
    for arm in ("strong_empty", "ordinary_memory", "unconditional_layout", "static_procedures", "skill_memory"):
        bank = [local_skill()] if arm in ("static_procedures", "skill_memory") else []
        old_messages, old_schema, _, _ = local.TaskLocalStudy.make_payload(study, arm, NoGold(row), bank, object(), "M1")
        messages, schema, _, trace = study.make_payload(arm, NoGold(row), bank, object(), "M1")
        assert schema == old_schema and messages[0] == old_messages[0]
        assert "GOLD_MUST_NOT_ENTER_SOLVER" not in json.dumps(messages)
        body, old_body = json.loads(messages[1]["content"]), json.loads(old_messages[1]["content"])
        for question in body["hypotheses"].values():
            for candidate in question["fallible_evidence_candidates"] or []:
                assert candidate.pop("literal_original_text") == "Recipient shall not disclose secrets."
        assert body == old_body  # No changed candidates, skills, layout, verdicts or source.
        assert trace["task_local_delivery"]["candidate_source_view"] == "literal_original_span_v1"


@pytest.mark.parametrize("flags,expected", [
    ({}, "task_local"),
    ({"candidate_source_view": "literal_original_span_v1", "teacher_feedback_view": "literal_evidence_comparisons_v1"}, "literal"),
    ({"candidate_source_view": "literal_original_span_v1"}, None),
    ({"teacher_feedback_view": "literal_evidence_comparisons_v1"}, None),
    ({"candidate_source_view": "unknown", "teacher_feedback_view": "literal_evidence_comparisons_v1"}, None),
    ({"candidate_source_view": "literal_original_span_v1", "teacher_feedback_view": "literal_evidence_comparisons_v1", "teacher_publication_format": "explicit_witness_accounts_v2", "skill_delivery_encoding": "scoped_lossless_table_v1"}, "witness_table"),
    ({"candidate_source_view": "literal_original_span_v1", "teacher_feedback_view": "literal_evidence_comparisons_v1", "teacher_publication_format": "source_acquisition_programs_v1", "skill_delivery_encoding": "named_source_programs_v1"}, "source_programs"),
    ({"candidate_source_view": "literal_original_span_v1", "teacher_feedback_view": "literal_evidence_comparisons_v1", "teacher_publication_format": "source_acquisition_programs_v2", "skill_delivery_encoding": "one_copy_named_source_programs_v2"}, "source_programs"),
    ({"candidate_source_view": "literal_original_span_v1", "teacher_feedback_view": "literal_evidence_comparisons_v1", "teacher_publication_format": "source_acquisition_programs_v1", "skill_delivery_encoding": "scoped_lossless_table_v1"}, None),
    ({"candidate_source_view": "literal_original_span_v1", "teacher_feedback_view": "literal_evidence_comparisons_v1", "teacher_publication_format": "explicit_witness_accounts_v2"}, None),
    ({"candidate_source_view": "literal_original_span_v1", "teacher_feedback_view": "literal_evidence_comparisons_v1", "teacher_publication_format": "explicit_witness_coverage_v1", "skill_delivery_encoding": "scoped_lossless_table_v1"}, None),
])
def test_cli_requires_exact_explicit_literal_views_without_silent_old_method(tmp_path, monkeypatch, flags, expected):
    import legal_skill_guard.cli as cli
    import legal_skill_guard.learning.literal_evidence as literal
    import legal_skill_guard.learning.task_local as local
    import legal_skill_guard.learning.witness_grounding as witness
    import legal_skill_guard.learning.source_programs as programs

    config = tmp_path / "candidate.json"
    RunStore.immutable_json(config, {"method": "task_local_memory", **flags})
    monkeypatch.setattr(local, "TaskLocalStudy", lambda config, run_id: ("task_local", config, run_id))
    monkeypatch.setattr(literal, "LiteralEvidenceStudy", lambda config, run_id: ("literal", config, run_id))
    monkeypatch.setattr(witness, "WitnessGroundedStudy", lambda config, run_id: ("witness_table", config, run_id))
    monkeypatch.setattr(programs, "SourceProgramStudy", lambda config, run_id: ("source_programs", config, run_id))
    if expected is None:
        with pytest.raises(ValueError, match="Unknown or incomplete"):
            cli.study_for(config, "declared")
    else:
        assert cli.study_for(config, "declared") == (expected, config, "declared")


def witness_operation_fixture():
    from legal_skill_guard.learning.witness_grounding import witness_publication_schema
    from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues

    row, labels, gold = fixture()
    candidate = local_skill()
    candidate["hypothesis_ids"] = ["h1"]
    candidate["guidance"]["relation_if_established"] = "Contradiction"  # Deliberately conflicts with this Gold E.
    op = {"operation": "CREATE", "target_ids": [], "skill": candidate, "source_case_ids": [row["id"]], "rationale": "Fixture only.",
          "witness_checks": {str(row["id"]): {
              "source_condition_status": "established", "source_condition_evidence": [0],
              "brief_boundary_fact": "An inspectable source condition, not private reasoning.",
          }}}
    assert not strict_output_schema_issues(witness_publication_schema(labels, [], [row]))
    accounts = {h: {str(row["id"]): {str(i): "Original governing or operative support." for i in gold[h]["spans"]}} for h in labels}
    return row, labels, {"training_evidence_accounts": accounts, "operations": [op], "noop_reason": None}


def test_training_witness_disagreement_is_archived_but_never_a_semantic_admission_gate():
    from legal_skill_guard.learning.witness_grounding import publish_with_training_witnesses

    row, labels, value = witness_operation_fixture()
    original = copy.deepcopy(value)
    bank, projection, audit = publish_with_training_witnesses([], value, labels, [row])
    assert value == original
    assert bank == [value["operations"][0]["skill"]]
    assert bank[0]["guidance"]["relation_if_established"] == "Contradiction"
    assert "witness_checks" not in projection["operations"][0]
    assert "witness_checks" not in json.dumps(bank)
    assert len(audit["claimed_established_with_different_original_label"]) == 1
    assert audit["nonnull_records_without_claimed_same_label_positive_witness"] == [bank[0]["id"]]
    assert audit["original_Gold_members_explicitly_accounted_once_not_proven_retrieved"] == 3


def test_training_witness_contract_binds_all_members_cases_scope_and_original_coordinates():
    from jsonschema import ValidationError
    from legal_skill_guard.learning.witness_grounding import publish_with_training_witnesses

    row, labels, value = witness_operation_fixture()
    missing = copy.deepcopy(value)
    del missing["training_evidence_accounts"]["h1"][str(row["id"])]["2"]
    with pytest.raises(ValidationError):
        publish_with_training_witnesses([], missing, labels, [row])
    invalid = copy.deepcopy(value)
    invalid["operations"][0]["witness_checks"][str(row["id"])]["source_condition_evidence"] = [99]
    with pytest.raises(ValidationError):
        publish_with_training_witnesses([], invalid, labels, [row])
    incomplete = copy.deepcopy(value)
    incomplete["operations"][0]["witness_checks"] = {}
    with pytest.raises(ValueError, match="every supplied original source"):
        publish_with_training_witnesses([], incomplete, labels, [row])
    noop = {"training_evidence_accounts": value["training_evidence_accounts"], "operations": [], "noop_reason": "No justified generic edit."}
    assert publish_with_training_witnesses([], noop, labels, [row])[:2] == ([], {k: v for k, v in noop.items() if k != "training_evidence_accounts"})


def test_lossless_skill_table_retains_shared_scope_nulls_order_and_exact_fields():
    from legal_skill_guard.learning.skill_tables import encode_skill_projection, decode_skill_projection
    from legal_skill_guard.learning.task_local import task_skill_projection

    _, labels, _ = fixture()
    bank = [local_skill()]
    bank[0]["hypothesis_ids"] = ["h1", "h2"]
    bank[0]["guidance"]["relation_if_established"] = None
    projection = task_skill_projection(bank, labels)
    original = copy.deepcopy(projection)
    table = encode_skill_projection(projection)
    assert decode_skill_projection(table) == projection == original
    assert table["by_hypothesis"]["h1"] == table["by_hypothesis"]["h2"]
    assert table["by_hypothesis"]["h1"][0][3] is None
    damaged = copy.deepcopy(table)
    damaged["by_hypothesis"]["h1"][0].pop()
    with pytest.raises(ValueError, match="no padding"):
        decode_skill_projection(damaged)
    extra = copy.deepcopy(projection)
    extra["h1"][0]["unexpected"] = "must not silently disappear"
    with pytest.raises(ValueError, match="never drop extras"):
        encode_skill_projection(extra)


def test_witness_packed_wire_preserves_native_schema_source_and_empty_controls():
    from types import SimpleNamespace
    from legal_skill_guard.learning.literal_evidence import LiteralEvidenceStudy
    from legal_skill_guard.learning.witness_grounding import WitnessGroundedStudy
    from legal_skill_guard.learning.skill_tables import decode_skill_projection, scoped_budget_view

    row, labels, _ = fixture()
    old, new = object.__new__(LiteralEvidenceStudy), object.__new__(WitnessGroundedStudy)
    for study in (old, new):
        study.labels = labels
        study.cfg = {"bundled_solver_system": "Original system."}
        study.meter = SimpleNamespace(token_count=lambda **kwargs: len(kwargs["text"]))
    for arm in ("strong_empty", "ordinary_memory", "unconditional_layout", "skill_memory"):
        bank = [local_skill()] if arm == "skill_memory" else []
        old_messages, old_schema, _, old_trace = old.make_payload(arm, row, bank, None, None)
        messages, schema, _, trace = new.make_payload(arm, row, bank, None, None)
        assert schema == old_schema
        assert "GOLD_MUST_NOT_ENTER_SOLVER" not in json.dumps(messages)
        delivery = trace["task_local_delivery"]
        assert delivery["actual_task_local_projection"] == old_trace["task_local_delivery"]["actual_task_local_projection"]
        if bank:
            assert decode_skill_projection(delivery["actual_wire_skill_table"]) == delivery["actual_task_local_projection"]
            body, old_body = json.loads(messages[1]["content"]), json.loads(old_messages[1]["content"])
            assert body["full_contract_with_original_span_markers"] == old_body["full_contract_with_original_span_markers"]
            for h in labels:
                question, original = body["hypotheses"][h], old_body["hypotheses"][h]
                assert {k: v for k, v in question.items() if k != "applicable_published_skills"} == {k: v for k, v in original.items() if k != "applicable_published_skills"}
        else:
            assert messages == old_messages  # Actual no-skill input is not weakened.
        assert delivery["actual_scoped_delivery_tokens"] == len(json.dumps(scoped_budget_view(delivery["actual_task_local_projection"]), ensure_ascii=False, separators=(",", ":")))


def source_program_skill():
    return {"id": "archive", "hypothesis_ids": ["h2"], "guidance": {
        "inspection": "Inspect the original source and retain complete evidence.",
        "source_queries": [{"all_phrases": [term], "any_phrases": [], "none_phrases": [],
                            "include_list_preamble": False} for term in ("shall not", "retain")],
    }}


def test_direct_source_programs_are_named_source_only_and_do_not_change_native_answer_contract():
    from types import SimpleNamespace
    from legal_skill_guard.learning.literal_evidence import LiteralEvidenceStudy
    from legal_skill_guard.learning.source_programs import SourceProgramStudy, one_copy_memory, program_projection

    row, labels, _ = fixture()

    class NoGold(dict):
        def __getitem__(self, key):
            if key == "annotation_sets":
                raise AssertionError("Direct source program read inference Gold")
            return super().__getitem__(key)

    old, new = object.__new__(LiteralEvidenceStudy), object.__new__(SourceProgramStudy)
    for obj in (old, new):
        obj.cfg, obj.labels = {"bundled_solver_system": "Original."}, labels
        obj.meter = SimpleNamespace(token_count=lambda **kwargs: len(kwargs["text"]))
    for bank in ([], [source_program_skill()]):
        original = copy.deepcopy(bank)
        before, original_schema, _, _ = old.make_payload("skill_memory", NoGold(row), [], None, None)
        messages, schema, _, trace = new.make_payload("skill_memory", NoGold(row), bank, None, None)
        assert bank == original
        assert "GOLD_MUST_NOT_ENTER_SOLVER" not in json.dumps(messages)
        delivery = trace["task_local_delivery"]
        assert delivery["actual_task_local_projection"] == program_projection(bank, labels)
        if not bank:
            assert messages == before and schema == original_schema
            continue
        body, old_body = json.loads(messages[1]["content"]), json.loads(before[1]["content"])
        restored = body["full_contract_with_original_span_markers"]
        for tag in delivery["source_lead_tags_by_original_span"].values():
            restored = restored.replace(tag, "", 1)
        assert restored == old_body["full_contract_with_original_span_markers"]
        assert body["published_source_programs"] == bank
        assert messages[1]["content"].count('"inspection"') == 1
        h2 = body["hypotheses"]["h2"]
        assert h2["applicable_published_skills"] == [{"id": "archive"}]
        assert body["source_program_query_receipts"]["archive"][0]["matched_original_span_indices"] == [0]
        assert body["source_program_query_receipts"]["archive"][1]["matched_original_span_indices"] == [1]
        assert delivery["source_program_executions"]["h2"]["literal_original_clauses"][0]["literal_original_text"] == "Recipient shall not disclose secrets."
        assert body["hypotheses"]["h1"]["applicable_published_skills"] == []
        assert body["hypotheses"]["h3"]["applicable_published_skills"] == []
        assert delivery["actual_scoped_delivery_tokens"] == len(json.dumps(one_copy_memory(bank, labels), ensure_ascii=False, separators=(",", ":")))
        for h, wrapped in schema["properties"].items():
            for branch in wrapped["anyOf"]:
                allowed = branch["properties"]["used_skill_ids"]
                assert allowed["items"]["enum"] == ["archive"] if h == "h2" else allowed["maxItems"] == 0


def test_direct_source_programs_return_empty_hits_unchanged_and_publish_noisy_queries():
    from jsonschema import validate
    from legal_skill_guard.learning.publication import apply_differential_publication, differential_schema
    from legal_skill_guard.learning.source_programs import PROGRAM_GUIDANCE_SCHEMA, source_program_messages
    from legal_skill_guard.learning.task_local import task_local_messages

    row, labels, _ = fixture()
    candidate = source_program_skill()
    for query in candidate["guidance"]["source_queries"]:
        query["all_phrases"] = ["nonexistent phrase"]
    value = {"operations": [{"operation": "CREATE", "target_ids": [], "skill": candidate, "source_case_ids": [1], "rationale": "Synthetic negative only."}], "noop_reason": None}
    schema = differential_schema(labels, [], [1], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
    validate(value, schema)
    bank = apply_differential_publication([], value, labels, [1], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
    assert bank == [candidate]  # No evidence utility admission.
    messages, _, delivery = task_local_messages(row, labels, "Original.", [], None)
    answer, trace = source_program_messages(messages, delivery, row, bank, labels, system="Original.")
    body = json.loads(answer[1]["content"])
    receipts = body["source_program_query_receipts"]["archive"]
    assert receipts[0]["matched_original_span_indices"] == []
    assert all(not e["returned_original_span_indices"] for e in receipts)
    assert trace["source_lead_tags_by_original_span"] == {}
    assert len(trace["source_program_execution_by_skill"][candidate["id"]]) == 2
    bad = copy.deepcopy(value)
    bad["operations"][0]["skill"]["guidance"]["relation_if_established"] = "Entailment"
    with pytest.raises(ValidationError):
        validate(bad, schema)
    wide = copy.deepcopy(value)
    wide["operations"][0]["skill"]["guidance"]["source_queries"][0]["before"] = 40
    with pytest.raises(ValidationError):
        validate(wide, schema)


def test_direct_source_program_feedback_covers_all_tasks_and_preserves_extra_members():
    from legal_skill_guard.learning.source_programs import program_member_feedback, source_program_messages
    from legal_skill_guard.learning.task_local import task_local_messages

    row, labels, _ = fixture()
    bank = [source_program_skill()]
    messages, _, delivery = task_local_messages(row, labels, "Original.", [], None)
    _, delivery = source_program_messages(messages, delivery, row, bank, labels, system="Original.")
    unit = {"published_library": bank, "response": {"raw_id": "synthetic"}, "actual_factual_trace": {"task_local_delivery": delivery}}
    value = program_member_feedback(unit, row, labels)
    assert list(value["all_original_hypotheses"]) == list(labels)
    h2 = value["all_original_hypotheses"]["h2"]
    assert h2["original_Gold_members_reached"] == [1]
    assert h2["returned_non_Gold_members"] == [0]
    assert value["all_original_hypotheses"]["h1"]["original_Gold_members_not_reached"] == [0, 2]
    del delivery["source_program_executions"]["h1"]
    with pytest.raises(ValueError, match="every public-task receipt"):
        program_member_feedback(unit, row, labels)


def program_feedback_fixture():
    from legal_skill_guard.learning.source_programs import program_member_feedback, source_program_messages
    from legal_skill_guard.learning.task_local import task_local_messages

    row, labels, gold = fixture()
    bank = [source_program_skill()]
    messages, _, trace = task_local_messages(row, labels, "Original.", [], None)
    _, delivery = source_program_messages(messages, trace, row, bank, labels, system="Original.")
    unit = {"published_library": bank, "response": {"raw_id": "synthetic"}, "actual_factual_trace": {"task_local_delivery": delivery}}
    return {"complete_actual_parent_library": bank,
        "original_cases_and_actual_same_parent_observations": [{"document_id": row["id"],
            "full_source": row["text"], "original_annotations": gold,
            "actual_factual_source_operations": delivery["actual_source_operations"]}],
        "actual_parent_source_program_member_feedback": [program_member_feedback(unit, row, labels)]}


def test_program_teacher_receipts_one_copy_and_full_original_byte_roundtrip():
    from legal_skill_guard.learning.source_programs import pack_program_feedback, unpack_program_feedback

    body = program_feedback_fixture()
    original = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    packed = pack_program_feedback(body)
    assert json.dumps(body, ensure_ascii=False, separators=(",", ":")) == original
    assert json.dumps(unpack_program_feedback(packed), ensure_ascii=False, separators=(",", ":")) == original
    catalog = packed["actual_parent_source_program_receipt_catalog"]
    assert len(catalog) == 2
    assert all("actual_query_arguments" not in r["actual_receipt"] for r in catalog.values())
    case = packed["original_cases_and_actual_same_parent_observations"][0]
    feedback = packed["actual_parent_source_program_member_feedback"][0]["all_original_hypotheses"]["h2"]
    assert case["actual_factual_source_operations"]["h2"]["source_query_receipts"] == feedback["actual_source_receipts"]
    with pytest.raises(ValueError, match="only once"):
        pack_program_feedback(packed)


@pytest.mark.parametrize("damage", ["arguments", "duplicate", "cross_source", "dangling"])
def test_program_teacher_receipts_reject_inexact_execution_identity(damage):
    from legal_skill_guard.learning.source_programs import pack_program_feedback, unpack_program_feedback

    body = program_feedback_fixture()
    if damage in ("arguments", "duplicate"):
        receipt = body["actual_parent_source_program_member_feedback"][0]["all_original_hypotheses"]["h2"]["actual_source_receipts"][0]
        if damage == "arguments":
            receipt["actual_query_arguments"] = {"invented": True}
        else:
            # Break only this view, without mutating the other shared Python object.
            feedback = body["actual_parent_source_program_member_feedback"][0]["all_original_hypotheses"]["h2"]
            feedback["actual_source_receipts"] = copy.deepcopy(feedback["actual_source_receipts"])
            altered = copy.deepcopy(receipt)
            altered["matched_original_span_indices"] = [99]
            feedback["actual_source_receipts"][0] = altered
        with pytest.raises(ValueError):
            pack_program_feedback(body)
    else:
        packed = pack_program_feedback(body)
        if damage == "cross_source":
            packed["actual_parent_source_program_receipt_catalog"]["r0"]["document_id"] = 999
        else:
            del packed["actual_parent_source_program_receipt_catalog"]["r0"]
        with pytest.raises(ValueError):
            unpack_program_feedback(packed)


def test_executable_acquisition_only_returns_source_and_never_serves_program_advice():
    from jsonschema import validate

    from legal_skill_guard.learning.acquisition import execute_library, source_messages

    pieces = ["Heading.", "No copies except for the Purpose.", "Return every copy on request."]
    position, spans = 0, []
    for piece in pieces:
        spans.append([position, position + len(piece)])
        position += len(piece) + 1
    row = {"id": 1, "text": "\n".join(pieces), "spans": spans}
    labels = {h: {"hypothesis": h, "short_description": h} for h in ("h1", "h2")}
    query = {"all_phrases": ["copies"], "any_phrases": [], "none_phrases": [],
        "before": 1, "after": 0, "include_list_preamble": False}
    bank = [{"id": "copy-acquisition", "hypothesis_ids": ["h1"], "guidance": {"source_queries": [query]}}]
    receipts = execute_library(row, bank)
    assert receipts["copy-acquisition"][0]["matched"] == [1]
    assert receipts["copy-acquisition"][0]["neighbour"] == [0]
    messages, schema, trace = source_messages(row, labels, "Common system.", bank, None)
    body = json.loads(messages[1]["content"])
    assert "source_queries" not in messages[1]["content"]
    assert "all_phrases" not in messages[1]["content"]
    assert "copy-acquisition" not in json.dumps([messages, schema])
    assert "SOURCE_LEADS" not in messages[1]["content"]
    assert body["hypotheses"]["h1"]["additional_source_read_indices"] == [0, 1]
    assert body["hypotheses"]["h2"]["additional_source_read_indices"] == []
    assert body["candidate_original_text"] == {"0": pieces[0], "1": pieces[1]}
    assert trace["actual_source_executions"] == receipts
    assert trace["original_source_unchanged_without_global_query_tags"]
    # No skill applicability or hit is allowed to choose the legal relation.
    for choice in ("Entailment", "Contradiction", "NotMentioned"):
        value = {h: {"choice": choice, "spans": [] if choice == "NotMentioned" else [2],
            "reason": ""} for h in labels}
        validate(value, schema)
    with pytest.raises(AssertionError):
        execute_library({**row, "annotation_sets": "must not be read"}, bank)


def test_acquisition_actor_input_depends_only_on_returned_facts_not_bank_metadata():
    from legal_skill_guard.learning.acquisition import source_messages

    text = "No copies.\nReturn items."
    row = {"id": 1, "text": text, "spans": [[0, 10], [11, len(text)]]}
    labels = {h: {"hypothesis": h, "short_description": h} for h in ("h1", "h2")}
    query = {"all_phrases": ["copies"], "any_phrases": [], "none_phrases": [],
        "before": 0, "after": 0, "include_list_preamble": False}
    empty = {**query, "all_phrases": ["nonexistent"]}
    first = [{"id": "alpha", "hypothesis_ids": ["h1"], "guidance": {"source_queries": [query]}}]
    equivalent = [
        {"id": "changed-name", "hypothesis_ids": ["h1"], "guidance": {"source_queries": [query, query]}},
        {"id": "more-metadata", "hypothesis_ids": ["h1", "h2"], "guidance": {"source_queries": [empty]}},
    ]
    def render(bank, proposals=None):
        return source_messages(row, labels, "Common.", bank, proposals)[:2]

    assert render(first) == render(equivalent)
    assert render([]) == render([equivalent[1]])
    proposals = {"by_hypothesis": {
        "h1": {"candidates": [{"original_span_index": 0, "membership_score": .8}]},
        "h2": {"candidates": []}}}
    assert render([], proposals) == render(first, proposals)


def test_executable_acquisition_publication_rejects_advice_and_empty_search():
    from jsonschema import ValidationError

    from legal_skill_guard.learning.acquisition import GUIDANCE_SCHEMA, execute_library
    from legal_skill_guard.learning.publication import apply_differential_publication

    query = {"all_phrases": ["copies"], "any_phrases": [], "none_phrases": [],
        "before": 0, "after": 0, "include_list_preamble": False}
    skill = {"id": "copy-acquisition", "hypothesis_ids": ["h1"], "guidance": {"source_queries": [query]}}
    delta = {"operations": [{"operation": "CREATE", "target_ids": [], "skill": skill,
        "source_case_ids": [1], "rationale": "Acquisition only."}], "noop_reason": None}
    assert apply_differential_publication([], delta, ["h1"], [1], guidance_schema=GUIDANCE_SCHEMA) == [skill]
    invalid = copy.deepcopy(delta)
    invalid["operations"][0]["skill"]["guidance"]["inspection"] = "Always emit a legal label."
    with pytest.raises(ValidationError):
        apply_differential_publication([], invalid, ["h1"], [1], guidance_schema=GUIDANCE_SCHEMA)
    empty = copy.deepcopy(skill)
    empty["guidance"]["source_queries"][0]["all_phrases"] = []
    with pytest.raises(ValueError, match="empty catch-all"):
        execute_library({"id": 1, "text": "", "spans": []}, [empty])


def test_native_member_feedback_distinguishes_reading_from_actual_false_citation():
    from legal_skill_guard.learning.acquisition import native_member_feedback

    roles = {"matched": {1}, "neighbour": {2, 3}, "preamble": set()}
    value = {"choice": "Entailment", "spans": [1, 2], "reason": "Public native reason."}
    original = copy.deepcopy(value)
    feedback = native_member_feedback({"choice": "Entailment", "spans": [1, 3]}, value, {1, 3}, roles)
    assert feedback["Gold_omitted_despite_program_access"] == [3]
    assert feedback["Gold_omitted_despite_ordinary_candidate"] == [3]
    assert feedback["nonGold_final_citations_for_original_NN_only"] == [2]
    assert feedback["nonGold_citations_in_context_only"] == [2]
    assert value == original
    neutral = native_member_feedback({"choice": "NotMentioned", "spans": []},
        {"choice": "NotMentioned", "spans": [], "reason": ""}, set(), roles)
    assert neutral["nonGold_final_citations_for_original_NN_only"] == []
    assert neutral["reading_context_itself_is_not_an_error"]
    assert not neutral["original_NM_but_native_chose_relation"]


def test_incremental_records_preserve_all_facts_and_only_add_existing_fixed_scores():
    from legal_skill_guard.learning.acquisition import source_messages

    text = "Header.\nCopies exist.\nReturn items."
    row = {"id": 1, "text": text, "spans": [[0, 7], [8, 21], [22, len(text)]]}
    labels = {"h1": {"hypothesis": "h1", "short_description": "h1"}}
    query = {"all_phrases": ["copies"], "any_phrases": [], "none_phrases": [],
        "before": 1, "after": 0, "include_list_preamble": False}
    bank = [{"id": "hidden", "hypothesis_ids": ["h1"], "guidance": {"source_queries": [query]}}]
    proposals = {"by_hypothesis": {"h1": {
        "candidates": [{"original_span_index": 2, "membership_score": .9}],
        "raw_scores": [.00001, .2, .9]}}}
    results = {encoding: source_messages(row, labels, "Common.", bank, proposals,
        incremental_encoding=encoding) for encoding in ("indices", "records", "scored_records")}
    bodies = {k: json.loads(v[0][1]["content"]) for k, v in results.items()}
    assert bodies["indices"]["hypotheses"]["h1"]["additional_source_read_indices"] == [0, 1]
    assert bodies["records"]["hypotheses"]["h1"]["additional_source_read_indices"] == [
        {"original_span_index": 0}, {"original_span_index": 1}]
    assert bodies["scored_records"]["hypotheses"]["h1"]["additional_source_read_indices"] == [
        {"original_span_index": 0, "membership_score": .00001},
        {"original_span_index": 1, "membership_score": .2}]
    for k, (messages, schema, trace) in results.items():
        assert messages[0] == results["indices"][0][0]
        assert schema == results["indices"][1] and trace == results["indices"][2]
        bodies[k]["hypotheses"]["h1"].pop("additional_source_read_indices")
        assert bodies[k] == bodies["indices"]
        empty = source_messages(row, labels, "Common.", [], proposals, incremental_encoding=k)
        assert empty == source_messages(row, labels, "Common.", [], proposals)
    missing = copy.deepcopy(proposals)
    missing["by_hypothesis"]["h1"].pop("raw_scores")
    with pytest.raises(KeyError):
        source_messages(row, labels, "Common.", bank, missing, incremental_encoding="scored_records")


def test_readable_acquisition_teacher_keeps_all_information_and_opposite_case_index():
    from legal_skill_guard.learning.acquisition import readable_teacher_view
    from legal_skill_guard.learning.packing import expand

    body = {"public_hypotheses": {"h": {"hypothesis": "Same original question"}},
        "complete_cumulative_original_TRAIN_sources_and_Gold": [
            {"id": 1, "text": "Full first source.", "spans": [[0, 18]], "original_annotations": {"h": {"choice": "Entailment", "spans": [0]}}},
            {"id": 2, "text": "Full opposed source.", "spans": [[0, 20]], "original_annotations": {"h": {"choice": "Contradiction", "spans": [0]}}}],
        "current_parent_native_member_feedback": {"1": {"h": {"missing": [0], "false": []}}},
        "current_parent_acquisition_member_feedback_not_legal_predictions": {"1": {"h": {"Gold": [0]}}},
        "actual_own_public_observations": [{"actual_public_answer": {"h": {"choice": "NotMentioned", "spans": [], "reason": "actual failure"}}, "actual_incremental_read_encoding": "scored_records"}],
        "actual_source_execution_catalogue": {"bank:1": {"skill": [{"matched": [0], "neighbour": []}]}},
        "actual_visible_ordinary_candidates_by_source": {"1": {"h": []}},
        "actual_visible_incremental_reads_by_source": {"1": {"h": [{"original_span_index": 0, "membership_score": .00001}]}},
        "current_parent_library": [], "observed_libraries": {"bank": []},
        "published_edit_history_not_individual_edit_effects": [{"actual_delta": {"operations": []}}]}
    preserved = copy.deepcopy(body)
    view = readable_teacher_view(body)
    assert body == preserved and expand(view["body"]) == preserved
    assert view["cross_source_relation_index"] == {"h": {"Entailment": [1], "Contradiction": [2], "NotMentioned": []}}


def test_acquisition_history_encoding_is_explicit_for_new_and_declared_for_legacy():
    from legal_skill_guard.learning.acquisition import incremental_encoding

    assert incremental_encoding({"arm": "skills"}) == "indices"
    assert incremental_encoding({"arm": "scored_records"}) == "scored_records"
    assert incremental_encoding({"arm": "skills", "incremental_read_encoding": "scored_records"}) == "scored_records"
    with pytest.raises(AssertionError):
        incremental_encoding({"arm": "ordinary"})


def test_two_target_skills_preserve_parent_and_never_cross_runtime_channels():
    from legal_skill_guard.learning.decision_evidence import (
        channel_criteria, convert_parent, decision_payload, evidence_payload,
    )

    original, labels, gold = fixture()
    row = {k: original[k] for k in ("id", "text", "spans")}
    parent = [{"id": "s", "hypothesis_ids": ["h1"],
               "guidance": {"evidence_criterion": "RELATION_ONLY_CANARY"}}]
    saved = copy.deepcopy(parent)
    bank = convert_parent(parent, labels)
    assert parent == saved and bank[0]["guidance"] == {
        "relation_criterion": "RELATION_ONLY_CANARY", "evidence_criterion": None}
    bank[0]["guidance"]["evidence_criterion"] = "EVIDENCE_ONLY_CANARY"
    messages, schema = decision_payload(row, labels, None, bank)
    wire = json.dumps(messages)
    assert "RELATION_ONLY_CANARY" in wire and "EVIDENCE_ONLY_CANARY" not in wire
    assert "GOLD_MUST_NOT_ENTER_SOLVER" not in wire
    answer = {h: {"choice": v["choice"], "reason": "FIRST_REASON_ONLY_CANARY"} for h,v in gold.items()}
    response = {"content": json.dumps(answer), "finish_reason": "stop", "raw_id": "actual1"}
    evidence, es = evidence_payload(row, labels, None, response, schema, bank)
    wire = json.dumps(evidence)
    assert "EVIDENCE_ONLY_CANARY" in wire and "RELATION_ONLY_CANARY" not in wire
    assert "FIRST_REASON_ONLY_CANARY" not in wire and "GOLD_MUST_NOT_ENTER_SOLVER" not in wire
    assert json.loads(evidence[1]["content"])["native_relation_choices"] == {h:v["choice"] for h,v in gold.items()}
    assert es["properties"]["h3"]["properties"]["spans"]["maxItems"] == 0
    bank[0]["guidance"] = {"relation_criterion": None, "evidence_criterion": None}
    with pytest.raises(ValueError, match="empty skill"):
        channel_criteria(bank, labels, "evidence_criterion")


def test_two_native_targets_copy_wrong_decisions_and_members_without_repair():
    from legal_skill_guard.learning.decision_evidence import (
        assemble_native, decision_payload, evidence_payload,
    )

    original, labels, gold = fixture()
    row = {k: original[k] for k in ("id", "text", "spans")}
    _, ds = decision_payload(row, labels, None, [])
    a = {h: {"choice": v["choice"], "reason": "Original native reason."} for h,v in gold.items()}
    a["h1"]["choice"] = "Contradiction"  # wrong answer must survive assembly
    d = {"content": json.dumps(a), "finish_reason": "stop", "raw_id": "actual_d",
         "prompt_tokens": 5, "completion_tokens": 6}
    _, es = evidence_payload(row, labels, None, d, ds, [])
    b = {h: {"spans": v["spans"]} for h,v in gold.items()}
    b["h1"]["spans"] = [1]  # wrong member must survive assembly
    e = {"content": json.dumps(b), "finish_reason": "stop", "raw_id": "actual_e",
         "prompt_tokens": 7, "completion_tokens": 8}
    value = assemble_native(d, e, ds, es, labels)
    assert json.loads(value["content"]) == {h: {**a[h], **b[h]} for h in labels}
    assert value["raw_id"] is None and value["actual_native_raw_ids"] == ["actual_d", "actual_e"]
    assert value["prompt_tokens"] == 12 and value["completion_tokens"] == 14
    bad = assemble_native(d, None, ds, {}, labels)
    score = original_score(bad, row, gold, list(labels))
    assert len(score["queries"]) == 3 and all(not q["joint_exact"] for q in score["queries"])
    assert bad["component_errors"] and bad["finish_reason"] is None


def test_two_target_shared_prefix_is_one_actual_decision_two_actual_evidence_calls():
    from experiments.decision_evidence_transfer import DecisionEvidenceTransfer

    original, labels, gold = fixture()
    row = {k: original[k] for k in ("id", "text", "spans")}
    study = DecisionEvidenceTransfer.__new__(DecisionEvidenceTransfer)
    study.labels, study.bank = labels, []
    called, results = [], []

    def generate(source, role, messages, schema):
        called.append(role)
        answer = {h: ({"choice": v["choice"], "reason": "Native."} if role.endswith("decision")
                       else {"spans": v["spans"]}) for h,v in gold.items()}
        return {"content": json.dumps(answer), "finish_reason": "stop", "raw_id": role,
                "prompt_tokens": 10, "completion_tokens": 10}

    study.generate = generate
    study.logical = lambda source, arm, response: results.append((arm, response))
    study.factored(row, None, ("relation_only", "dual_skills"))
    assert called == ["shared_skill_decision", "relation_only_evidence", "dual_skills_evidence"]
    assert len(results) == 2 and results[0][1]["actual_native_raw_ids"][0] == results[1][1]["actual_native_raw_ids"][0]
    assert sum(len(r["actual_native_raw_ids"]) for _,r in results) == 4 and len(called) == 3


def test_complete_member_order_delivers_tail_without_changing_binary_candidates():
    from legal_skill_guard.learning.decision_evidence import decision_payload, joint_payload

    original, labels, _ = fixture()
    row = {k: original[k] for k in ("id", "text", "spans")}
    proposals = {"by_hypothesis": {h: {"candidates": [
        {"original_span_index": 2, "membership_score": .9}], "raw_scores": [.1, .1, .9]}
        for h in labels}}
    saved = copy.deepcopy(proposals)
    for messages, _ in (decision_payload(row, labels, proposals, []),
                         joint_payload(row, labels, proposals, "Same task.")):
        body = json.loads(messages[1]["content"])
        for h in labels:
            assert body["hypotheses"][h]["ordinary_membership_rank_order"] == [2, 0, 1]
            assert body["hypotheses"][h]["fallible_evidence_candidates"] == saved["by_hypothesis"][h]["candidates"]
    assert proposals == saved


@pytest.mark.parametrize("start_batch,program,draft,resume,procedure", [
    (1, False, False, False, False), (2, False, False, False, False), (1, True, False, False, False),
    (1, True, True, False, False), (1, True, True, True, False), (1, True, "native", False, False),
    (1, True, "native", True, False), (1, True, "linked", False, False), (1, False, False, False, True),
    (1, False, False, False, "feedback"), (1, False, False, False, "observed")])
def test_online_chronology_replays_prefix_and_never_teaches_forward_batch(tmp_path, monkeypatch, start_batch, program, draft, resume, procedure):
    from types import SimpleNamespace

    from experiments import decision_evidence_transfer as module
    from legal_skill_guard.learning.packing import expand

    original, labels, gold = fixture()
    observed = procedure == "observed"
    feedback = procedure in ("feedback","observed")
    past_ids = list(range(1000,1202)) if observed else list(range(100,142))
    public = {k: original[k] for k in ("id", "text", "spans")}
    study = module.RankedOnline.__new__(module.RankedOnline)
    study.documents = [{**copy.deepcopy(public), "id": d} for d in range(1, 129 if observed else 33)]
    study.past = [{**copy.deepcopy(public), "id": d} for d in past_ids]
    gold_path = tmp_path / "gold.json"
    RunStore.immutable_json(gold_path, {"original_TRAIN_annotations": {
        str(r["id"]): gold for r in study.past+study.documents}})
    study.cfg = {"grading_only": str(gold_path), "bundled_solver_system": "Same task.",
                 "library_token_hard_cap": 4096, "start_batch": start_batch,
                 "show_complete_member_order": start_batch == 1 and not program}
    study.labels, study.bank = labels, [{"id": "s", "hypothesis_ids": list(labels),
        "guidance": {"relation_criterion": "Inspect the source.", "evidence_criterion": "Select actual members."}}]
    study.bindings, study.run_id, study.out = {}, "synthetic_only", tmp_path / "run"
    study.manifest = {"synthetic": True}
    study.model = study.prefix_model = object()
    study.prefix_ids = past_ids.copy()
    if start_batch == 2:
        study.prefix_model = object()
        study.prefix_ids += list(range(1, 9))
    study.meter = SimpleNamespace(token_count=lambda **_: 100)
    study.native, study.teachers, study.units, study.answers = [], [], [], []
    study.own_current, study.batch_summaries, study.fit_records = {}, [], []
    study.program_cost = {}
    study.resumed = None
    study.current_batch = 0
    records = {}
    study.record = lambda name, value: records.setdefault(name, value)
    study.check = lambda: None
    study.progress = lambda *args, **kwargs: None

    def proposals(model, row, public_labels):
        return {"by_hypothesis": {h: {"candidates": [{"original_span_index":0,"membership_score":.73}] if observed else [],
                                     "raw_scores": [.1, .2, .3]} for h in public_labels}}

    monkeypatch.setattr(module, "evidence_proposals", proposals)
    if procedure:
        study.cfg.update(method=module.OBSERVED_METHOD if observed else module.EDIT_FEEDBACK_METHOD if feedback else module.PROCEDURE_METHOD,
                         show_complete_member_order=False)
        if feedback:
            study.cfg["public_reason_words"] = 64
        study.bank = [{"id":"p","hypothesis_ids":list(labels),"guidance":{"procedure":"Check the actual operative source conditions."}}]
        if observed:
            study.bank=[]
            study.cfg.update(learning_batches=16,episode_size=128,
                initial_guidance_migration="independent_empty_new_source_observed_learning")
    if program:
        from legal_skill_guard.learning.member_contract import teacher_sources

        study.cfg["method"] = (module.LINKED_METHOD if draft == "linked" else
                               module.NATIVE_DRAFT_METHOD if draft == "native" else
                               module.DRAFT_METHOD if draft else module.PROGRAM_METHOD)
        study.bank = ([{"id":"p","hypothesis_ids":list(labels),"guidance":{"python_source":
            "def propose_members(text, spans, public_hypothesis_key):\n    return []\n"}}] if draft else [])
        if draft == "linked":
            study.bank[0]["guidance"]["procedure"] = None
        initial_path = tmp_path / "initial_program_teacher.json"
        RunStore.immutable_json(initial_path, {"current_parent_library": [],
            "complete_original_past_sources_and_Gold": teacher_sources(study.past,
                {str(r["id"]):gold for r in study.past})})
        study.cfg["initial_teacher_body"] = str(initial_path)

        def synthetic_program_replay(bank, source, public_labels, *, allow_procedures=False):
            assert allow_procedures == (draft == "linked")
            return {h:[] for h in public_labels}, []

        def synthetic_program_payload(source, public_labels, leads, system, bank, *, allow_procedures=False):
            assert allow_procedures == (draft == "linked")
            messages,schema=module.joint_payload(source, public_labels, leads, system, complete_order=False)
            return messages,schema,{"synthetic_chronology_not_effectiveness":True,
                                    "actual_member_program_executions":[]}

        monkeypatch.setattr(module,"execute_member_programs",synthetic_program_replay)
        monkeypatch.setattr(module,"member_program_payload",synthetic_program_payload)

    epoch = "original"
    interrupt_revision = resume
    failed_batch = 1 if draft == "native" else 2
    interrupted = {}

    def generate(row, role, messages, schema):
        study.native.append({"role": role, "phase": study.phase})
        if role.endswith("decision"):
            answer = {h: {"choice": a["choice"], "reason": "Native."} for h,a in gold.items()}
        elif role.endswith("evidence"):
            answer = {h: {"spans": a["spans"]} for h,a in gold.items()}
        else:
            answer = {h: {**a, "reason": "Native."} for h,a in gold.items()}
        response={"raw_id": f"{epoch}{len(study.native)}", "finish_reason": "stop",
                  "content": json.dumps(answer), "prompt_tokens": 10, "completion_tokens": 10}
        study.native[-1]['synthetic_response']=copy.deepcopy(response)
        return response

    study.generate = generate

    def teacher(name, system, body, schema):
        if body.get("encoding") == "lossless-teacher-catalog-v2":
            body=decode_teacher_body(body)
        if interrupt_revision and name == f"online_b{failed_batch}_revision":
            interrupted["schema"] = copy.deepcopy(schema)
            raise ValueError("Synthetic character guard before the final teacher invocation")
        if name == "initial_source_program_induction":
            sources=expand(body["complete_original_past_sources_and_Gold"])
            assert {s["id"] for s in sources} == set(range(100,142))
            assert not study.answers and not study.bank
            study.teachers.append(name)
            return {"operations":[{"operation":"CREATE","target_ids":[],"source_case_ids":[100],
                "rationale":"Synthetic publication fixture, not efficacy evidence.",
                "skill":{"id":"p","hypothesis_ids":list(labels),"guidance":{"python_source":
                    "def propose_members(text, spans, public_hypothesis_key):\n    return []\n"}}}],
                "noop_reason":None}
        count = study.current_batch*8
        if draft == "linked" or procedure:
            sources = expand(body["complete_new_and_previous_batch_original_sources_and_Gold"])
            expected_ids = set(range(max(1,count-15),count+1))
            assert {s["id"] for s in sources} == expected_ids
            assert body["literal_replay_window"]["all_new_source_ids"] == list(range(count-7,count+1))
            assert body["literal_replay_window"]["all_immediately_previous_episode_batch_ids"] == list(range(max(1,count-15),count-7))
            assert "all_earlier_original_source_witness_replay_NOT_full_contracts" not in body
            assert body["current_common_ordinary_tool_source_ids"] == study.prefix_ids
            if procedure:
                assert "actual_current_parent_source_program_component_replays" not in body
                assert name == f"online_b{study.current_batch}"
                if feedback:
                    transition = body["previous_actual_matched_published_update_all_gains_and_harms"]
                    if study.current_batch == 1:
                        assert transition is None
                    else:
                        assert transition["learning_batch"] == study.current_batch-1
                        assert transition["all8_source_ids"] == list(range(count-15,count-7))
                        assert transition["actual_common_ordinary_tool_source_ids_before_and_after"] == past_ids+list(range(1,count-15))
                        assert len(expand(transition["before_all8_actual_native_answers_and_original_feedback"])) == 8
                        assert len(expand(transition["after_all8_actual_native_answers_and_original_feedback"])) == 8
                    assert "most15 words" not in system
                    assert "TWO native actions" not in system
                    assert "most64 words" in system and "worked legal distinction" in system
                    if observed:
                        assert "current_parent_library" in system and "are inherited unchanged" not in system
                        assert "only one original source" not in system
                        assert body['ordinary202_prior_supervision_not_skill_teacher_experience']
                        assert bool(body['current_parent_library']) == (study.current_batch>1)
        elif program:
            sources=expand(body["complete_newly_revealed_original_sources_and_Gold"])
            assert {s["id"] for s in sources}==set(range(count-7,count+1))
            replay=expand(body["all_earlier_original_source_witness_replay_NOT_full_contracts"])
            assert {s["id"] for s in replay}==set(range(100,142)) | set(range(1,count-7))
            assert all(s["original_annotations"]==gold and
                       s["complete_original_contract_not_repeated_in_teacher_context"] for s in replay)
        else:
            sources = expand(body["complete_original_past_and_revealed_episode_sources_and_Gold"])
            assert {s["id"] for s in sources} == set(range(100,142)) | set(range(1,count+1))
        own = expand(body["actual_current_parent_episode_public_answers"])
        if observed:
            pairs=expand(body['actual_current_batch_matched_empty_and_memory'])
            assert [p['document_id'] for p in pairs]==list(range(count-7,count+1))
            assert body['matched_policy_contrast_uses_all_current8_not_an_admission_gate']
            for pair in pairs:
                empty,own_memory=pair['actual_empty'],pair['actual_memory']
                assert empty['document_id']==own_memory['document_id']==pair['document_id']
                assert empty['ordinary_tool_source_ids']==own_memory['ordinary_tool_source_ids']==study.prefix_ids
                assert pair['same_physical_cold_alias_not_independent_rollout']==(study.current_batch==1)
            for observation in own:
                visible=observation['response']['actual_visible_ordinary_evidence_observation']
                assert visible['from_actual_native_input_not_recomputed_or_current_Gold']
                assert list(visible['by_hypothesis'])==list(labels)
                assert visible['candidate_original_text']=={'0':study.documents[0]['text'][slice(*study.documents[0]['spans'][0])]}
        assert {u["document_id"] for u in own} == set(range(max(1,count-15) if draft == "linked" or procedure else 1,count+1))
        assert body["complete_membership_rank_order_visible_in_single_joint_action"] == (start_batch == 1 and not program and not procedure)
        if start_batch == 2:
            assert "no longer used" in system
            assert "complete_original_member_rank_order" not in json.dumps(body)
        if program:
            replays=expand(body["actual_current_parent_source_program_component_replays"])
            assert {r["document_id"] for r in replays} == set(range(100,142)) | set(range(1,count+1))
        if draft:
            assert "publications/induction.json" not in records
            assert study.bank[0]["id"] == "p"  # Drafts never replace the published parent.
            if name.endswith("_revision"):
                draft_feedback=expand(body["actual_unpublished_draft_CPU_feedback"]["all_seen_sources_and_hypotheses"])
                assert {r["document_id"] for r in draft_feedback} == set(range(100,142)) | set(range(1,count+1))
                if draft in ("native", "linked"):
                    native = body["actual_unpublished_draft_native_training_feedback"]
                    draft_observations = expand(native["all8_actual_native_draft_observations"])
                    assert {r["document_id"] for r in draft_observations} == set(range(count-7,count+1))
                    expected_answer = {h:{**a,"reason":"Native."} for h,a in gold.items()}
                    assert all(r["public_valid"] and expand(r["actual_original_public_answer"]) == expected_answer
                               for r in draft_observations)
                    assert len([u for u in study.answers
                        if u["stage"] == f"b{study.current_batch}_unpublished_draft_training"]) == 8
                    assert all(u["condition"] == "skills" for u in study.own_current.values())
                if resume and study.resumed and study.current_batch == failed_batch:
                    assert (Path(study.resumed["executed_draft"]).parent.parent/f"program_replays/b{failed_batch}_draft.json").exists()
                    assert f"program_replays/b{failed_batch}_draft.json" not in records
                else:
                    assert f"program_replays/b{study.current_batch}_draft.json" in records
            else:
                assert name.endswith("_draft") and "actual_unpublished_draft_CPU_feedback" not in body
        assert len([u for u in study.answers if u["stage"] == f"b{study.current_batch}_prequential"]) == 16
        study.teachers.append(name)
        if observed and study.current_batch in (1,2):
            return {"operations":[{"operation":"CREATE" if study.current_batch==1 else "UPDATE",
                "target_ids":[] if study.current_batch==1 else ["p"],
                "source_case_ids":[1 if study.current_batch==1 else 9],
                "rationale":"Synthetic lifecycle, not efficacy.",
                "skill":{"id":"p","hypothesis_ids":["h1"],"guidance":{"procedure":
                    "Inspect the current original source." if study.current_batch==1 else "Inspect the exact current original source condition."}}}],"noop_reason":None}
        return {"operations": [], "noop_reason": "Synthetic chronology fixture, no live teacher."}

    study.teacher_call = teacher

    def fit(seen):
        study.fit_records.append({"synthetic_only": True})
        study.prefix_model = object()
        study.prefix_ids = past_ids + [r["id"] for r in seen]

    study.fit_prefix = fit
    if resume:
        with pytest.raises(ValueError,match="Synthetic character guard"):
            study.execute()
        inherited = [24,1,0] if draft == "native" else [48,3,1]
        assert [len(study.native),len(study.teachers),len(study.fit_records)]==inherited
        old=tmp_path/"original_failed";old_records=copy.deepcopy(records)
        for name,value in old_records.items():
            RunStore.immutable_json(old/name,value)
        writer=old/"saved_final_writer.json"
        RunStore.immutable_json(writer,{"system_prompt":"Original synthetic final writer.",
                                        "output_schema":interrupted["schema"]})
        study.resumed={"source_run_directory":str(old),"resume_batch":failed_batch,
            "inherited_actual_native_teacher_CPUfits":inherited,
            "logical_answer_paths":[str(old/name) for name in old_records if name.startswith("logical_answers/")],
            "batch_summary_paths":[str(old/f"batch_summaries/b{b}_before.json") for b in range(1,failed_batch+1)],
            "pending_final_revision_body":str(old/f"learning_inputs/online_b{failed_batch}_revision.json"),
            "pending_final_system_request":str(writer),"pending_final_schema_reference":str(writer),
            "executed_draft":str(old/f"drafts/b{failed_batch}.json")}
        study.cfg.update(planned_new_native_calls=(160 if draft == "native" else 136)-inherited[0],
            planned_new_teacher_calls=6-inherited[1],planned_new_CPU_fits=3-inherited[2])
        study.native,study.teachers,study.units,study.answers=[],[],[],[]
        study.own_current,study.batch_summaries,study.fit_records={},[],[]
        study.out=tmp_path/"resumed";records={};epoch="resumed";interrupt_revision=False
    study.execute()
    result = records["completion.json"]
    expected=([136,5,3] if draft == "native" else [88,3,2]) if resume else ([160 if draft in ("native", "linked") else 136,6 if draft else (4 if program else 3),3] if start_batch == 1 else [120,2,2])
    assert result["actual_new_native_teacher_CPUfits"] == ([376,16,16] if observed else [88,3,3] if feedback else expected)
    assert len(study.answers) == (384 if observed else 88 if feedback else (168 if draft in ("native", "linked") else 144) if start_batch == 1 else 120)
    assert len([k for k in records if k.startswith("exact_aliases/")]) == (8 if observed or (start_batch == 1 and not resume and not feedback) else 0)
    assert len(records["publications/b3.json"]["original_seen_source_ids"]) == len(past_ids)+24
    assert ("publications/b4.json" in records) == observed
    if observed:
        assert len(records["publications/b16.json"]["original_seen_source_ids"]) == 330
        assert records["publications/initial.json"]['actual_inherited_teacher_sources']==[]
        assert result['new_episode_original_sources_taught']==result['new_taught_labels']==128
        assert result['total_original_sources_taught_at_terminal']==128
        assert result['total_common_ordinary_supervised_sources_at_terminal']==330
        assert not result['episode24_taught_forward8_not_taught']
        assert all(u['response']['raw_id'] and u['response']['observation_metadata_only_native_content_and_raw_id_unchanged'] for u in study.answers)
        native_by_id={n['synthetic_response']['raw_id']:n['synthetic_response'] for n in study.native}
        assert all(u['response']['content']==native_by_id[u['response']['raw_id']]['content'] for u in study.answers)
        assert records['guidance_delivery/b2_prequential/9/skills.json']['visible_procedures']
    if program:
        if draft:
            expected_teachers = ([f"online_b{failed_batch}_revision"]+
                [f"online_b{b}_{stage}" for b in range(failed_batch+1,4) for stage in ("draft","revision")]
                if resume else [f"online_b{b}_{stage}" for b in (1,2,3) for stage in ("draft","revision")])
            assert study.teachers == expected_teachers
            assert all(f"drafts/b{b}.json" in records for b in (range(failed_batch+1,4) if resume else (1,2,3)))
            if resume:
                assert result["total_same_episode_actual_native_teacher_CPUfits"]==[160 if draft == "native" else 136,6,3]
                assert result["new_original_episode_label_exposures"]==(3-failed_batch)*8
                assert len({u["response"]["raw_id"] for u in study.answers})==(160 if draft == "native" else 136)
        else:
            assert records["publications/induction.json"]["new_episode_labels_taught"] == 0
            assert records["publications/induction.json"]["new_representation_learning_not_best_bank_rollback"]
        assert records["source_executions/b4_prequential/32/skills.json"]["synthetic_chronology_not_effectiveness"]
    assert all(v["documents"] == (128 if observed else 32 if start_batch == 1 else 24) for v in result["aggregate_prequential_metrics"].values())
    if draft == "linked" or procedure:
        for batch in (range(1,17) if observed else (1,2,3)):
            update = records[f"update_effects/b{batch}.json"]
            assert update["paired_scope"] == "current8_same_common_tool_training_only"
            assert update["paired_source_ids"] == list(range(batch*8-7,batch*8+1))
            if feedback:
                assert update["all_seen_system_retention_not_pure_skill_effect"] is None
                assert update["reanswered_source_ids"] == update["paired_source_ids"]
        for item in study.answers:
            if item["stage"].endswith("_prequential"):
                batch = int(item["stage"].split("_")[0][1:])
                assert item["ordinary_tool_source_ids"] == past_ids+list(range(1,(batch-1)*8+1))
        if procedure:
            assert study.teachers == [f"online_b{b}" for b in (range(1,17) if observed else (1,2,3))]
            assert not any(k.startswith(("drafts/","program_replays/","draft_native_training/","source_executions/")) for k in records)
    if start_batch == 2:
        assert records["initial_retention.json"]["not_unseen_evaluation_or_teacher_update_gain"]
        assert result["inherited_episode_labels"] == 8 and result["new_taught_labels"] == 16


def test_joint_skills_share_original_task_preserve_anchors_and_bound_set_cardinality():
    from legal_skill_guard.learning.decision_evidence import joint_payload
    from legal_skill_guard.task import marked_text

    original, labels, _ = fixture()
    row = {k: original[k] for k in ("id", "text", "spans")}
    bank = [{"id": "not_runtime", "hypothesis_ids": ["h1"], "guidance": {
        "relation_criterion": "RELATION_CANARY", "evidence_criterion": "MEMBER_CANARY"}}]
    empty, a = joint_payload(row, labels, None, "Original task.", [])
    skills, b = joint_payload(row, labels, None, "Original task.", bank)
    assert a == b and empty[0] == skills[0]
    x,y = (json.loads(m[1]["content"]) for m in (empty,skills))
    assert x["full_contract_with_original_span_markers"] == marked_text(row)
    assert "candidate_original_text" in x and "candidate_original_text" in y
    assert "RELATION_CANARY" in skills[1]["content"] and "MEMBER_CANARY" in skills[1]["content"]
    assert "not_runtime" not in skills[1]["content"]
    y.pop("learned_inspection_criteria")
    assert x == y
    for h in labels:
        for branch in a["properties"][h]["anyOf"]:
            p = branch["properties"]
            assert p["spans"]["maxItems"] == (0 if p["choice"]["enum"] == ["NotMentioned"] else len(row["spans"]))


def test_canonical_joint_removes_citation_like_rank_lists_not_source_or_candidate_anchors():
    from legal_skill_guard.learning.acquisition import source_messages
    from legal_skill_guard.learning.decision_evidence import joint_payload

    original, labels, _ = fixture()
    row = {k: original[k] for k in ("id", "text", "spans")}
    proposals = {"by_hypothesis": {h: {"candidates": [
        {"original_span_index": 2, "membership_score": .9}], "raw_scores": [.1, .1, .9]}
        for h in labels}}
    bank = [{"id": "NOT_RUNTIME", "hypothesis_ids": ["h1"], "guidance": {
        "relation_criterion": "RELATION_CANARY", "evidence_criterion": "EVIDENCE_CANARY"}}]
    reference, expected_schema, _ = source_messages(row, labels, "Task.", [], proposals)
    empty, a = joint_payload(row, labels, proposals, "Task.", complete_order=False)
    skills, b = joint_payload(row, labels, proposals, "Task.", bank, complete_order=False)
    assert a == b == expected_schema and empty[0] == skills[0]
    x,y = [json.loads(m[1]["content"]) for m in (empty, skills)]
    assert x == json.loads(reference[1]["content"])
    assert "ordinary_membership_rank_order" not in json.dumps(empty)
    assert "descending ordinary membership" not in json.dumps(empty)
    assert "maxItems" not in json.dumps(x["output_contract"])
    assert skills[1]["content"].count("RELATION_CANARY") == 1
    assert skills[1]["content"].count("EVIDENCE_CANARY") == 1
    assert "NOT_RUNTIME" not in skills[1]["content"]
    y.pop("learned_inspection_criteria")
    assert x == y and x["candidate_original_text"]["2"] == row["text"][slice(*row["spans"][2])]


def test_direct_member_programs_are_actual_source_computation_not_native_answers():
    from legal_skill_guard.learning.executable_features import execute_member_programs
    from legal_skill_guard.learning.decision_evidence import member_program_payload

    original, labels, _ = fixture()
    row = {k: original[k] for k in ("id", "text", "spans")}
    source = ("def propose_members(text, spans, public_hypothesis_key):\n"
              "    return [i for i, (a,b) in enumerate(spans) if 'retain' in text[a:b].lower()]\n")
    bank = [{"id": "NEVER_SERVED", "hypothesis_ids": ["h1"], "guidance": {"python_source": source}}]
    proposals = {"by_hypothesis": {h: {"candidates": [{"original_span_index": 0, "membership_score": .9}],
        "raw_scores": [.9, .1, .1]} for h in labels}}
    reads, receipts = execute_member_programs(bank, {**row, "annotation_sets": "NOT_CHILD_INPUT"}, labels)
    assert reads == {"h1": [1], "h2": [], "h3": []} and len(receipts) == 1
    empty,a,_ = member_program_payload(row, labels, proposals, "Task.", [])
    messages,b,trace = member_program_payload(row, labels, proposals, "Task.", bank)
    assert a == b and empty[0] == messages[0]
    body=json.loads(messages[1]["content"])
    assert body["hypotheses"]["h1"]["additional_source_read_indices"] == [{"original_span_index": 1}]
    assert body["hypotheses"]["h2"]["additional_source_read_indices"] == []
    assert body["candidate_original_text"]["1"] == row["text"][slice(*row["spans"][1])]
    assert trace["per_hypothesis_proposed_original_indices"] == reads
    assert "NEVER_SERVED" not in json.dumps(messages) and "propose_members" not in json.dumps(messages)
    assert "NOT_CHILD_INPUT" not in json.dumps(messages) and "choice" not in trace


def test_linked_source_and_procedure_keep_native_judgment_and_explicit_execution_boundaries():
    from jsonschema import ValidationError
    from legal_skill_guard.learning.executable_features import execute_member_programs, validate_member_programs
    from legal_skill_guard.learning.decision_evidence import member_program_payload

    original, labels, _ = fixture()
    row = {k: original[k] for k in ("id", "text", "spans")}
    procedure = "Check whether the retention exception actually applies to the recipient and stated purpose."
    text_skill = {"id": "PRIVATE_AUDIT_ID", "hypothesis_ids": ["h1"],
                  "guidance": {"python_source": None, "procedure": procedure}}
    with pytest.raises(ValidationError):
        validate_member_programs([text_skill], labels)
    reads, receipts = execute_member_programs([text_skill], row, labels, allow_procedures=True)
    assert all(not v for v in reads.values()) and receipts == []
    empty, a, _ = member_program_payload(row, labels, None, "Original task.", [], allow_procedures=True)
    learned, b, trace = member_program_payload(row, labels, None, "Original task.", [text_skill], allow_procedures=True)
    assert a == b and empty[0] == learned[0]
    left, right = [json.loads(m[1]["content"]) for m in (empty, learned)]
    assert left.pop("learned_legal_procedures") == []
    assert right.pop("learned_legal_procedures") == [{"hypothesis_ids": ["h1"], "procedure": procedure}]
    assert left == right and learned[1]["content"].count(procedure) == 1
    assert "PRIVATE_AUDIT_ID" not in json.dumps(learned) and "python_source" not in json.dumps(learned)
    assert trace["actually_delivered_procedures"][0]["procedure"] == procedure
    mixed = {**text_skill, "guidance": {"procedure": procedure, "python_source":
        "def propose_members(text, spans, public_hypothesis_key):\n    return [1]\n"}}
    mixed_reads, mixed_receipts = execute_member_programs([mixed], row, labels, allow_procedures=True)
    assert mixed_reads["h1"] == [1] and len(mixed_receipts) == 1
    for bad in (None, "  "):
        with pytest.raises(ValueError):
            validate_member_programs([{**text_skill,"guidance":{"python_source":None,"procedure":bad}}], labels, allow_procedures=True)
    invalid = copy.deepcopy(mixed)
    invalid["guidance"]["python_source"] = "def propose_members(text, spans, public_hypothesis_key):\n    return [1, 1]\n"
    with pytest.raises(ValueError, match="Duplicate"):
        execute_member_programs([invalid], row, labels, allow_procedures=True)




def test_direct_procedure_changes_only_public_reason_order_and_guidance_not_legal_task():
    from legal_skill_guard.learning.decision_evidence import joint_payload,procedure_payload

    original,labels,_=fixture();row={k:original[k] for k in ("id","text","spans")}
    bank=[{"id":"AUDIT_NOT_RUNTIME","hypothesis_ids":["h1"],"guidance":{"procedure":"Inspect the operative trigger before deciding."}}]
    old,old_schema=joint_payload(row,labels,None,"Same task.",complete_order=False)
    empty,schema=procedure_payload(row,labels,None,"Same task.",[])
    guided,guided_schema=procedure_payload(row,labels,None,"Same task.",bank)
    longer,longer_schema=procedure_payload(row,labels,None,"Same task.",bank,public_reason_words=64)
    assert longer_schema==guided_schema and longer[1]==guided[1]
    assert "most64 words" in longer[0]["content"] and "most15 words" not in longer[0]["content"]
    assert schema==guided_schema and empty[0]==guided[0]
    x,y=[json.loads(v[1]["content"]) for v in (empty,guided)]
    assert x.pop("learned_legal_procedures")==[]
    assert y.pop("learned_legal_procedures")==[{"hypothesis_ids":["h1"],"procedure":bank[0]["guidance"]["procedure"]}]
    assert x==y and "AUDIT_NOT_RUNTIME" not in guided[1]["content"]
    assert "python_source" not in guided[1]["content"]
    def canonical(value):
        if isinstance(value,dict):
            return {k:(sorted(v) if k=="required" else canonical(v)) for k,v in value.items()}
        if isinstance(value,list):return [canonical(v) for v in value]
        return value
    assert canonical(schema)==canonical(old_schema)
    assert canonical(x)==canonical(json.loads(old[1]["content"]))
    for spec in schema["properties"].values():
        for branch in spec["anyOf"]:
            assert list(branch["properties"])==["reason","choice","spans"]
            assert branch["required"]==["reason","choice","spans"]


@pytest.mark.parametrize("result", ["[True]", "[1, 1]", "[999]", "{'h1': [1]}"])
def test_direct_member_program_invalid_outputs_stop_without_repair(result):
    from legal_skill_guard.learning.executable_features import execute_member_programs

    original, labels, _ = fixture()
    row = {k: original[k] for k in ("id", "text", "spans")}
    bank = [{"id": "s", "hypothesis_ids": ["h1"], "guidance": {"python_source":
        "def propose_members(text, spans, public_hypothesis_key):\n    return " + result + "\n"}}]
    with pytest.raises(ValueError):
        execute_member_programs(bank, row, labels)


def test_direct_member_empty_match_is_not_failure_substitution():
    from legal_skill_guard.learning.executable_features import execute_member_programs

    original, labels, _ = fixture()
    row = {k: original[k] for k in ("id", "text", "spans")}
    bank = [{"id": "s", "hypothesis_ids": ["h1"], "guidance": {"python_source":
        "def propose_members(text, spans, public_hypothesis_key):\n    return []\n"}}]
    reads, receipts=execute_member_programs(bank, row, labels)
    assert reads == {h:[] for h in labels} and len(receipts) == 1


def test_teacher_member_view_expands_every_original_member_without_case_selection():
    from legal_skill_guard.learning.member_contract import annotated_sources
    from legal_skill_guard.learning.packing import expand

    original,labels,gold=fixture()
    row={k:original[k] for k in ("id","text","spans")}
    prefix,tail="序\n","\n尾。"
    row["text"]=prefix+row["text"]+tail
    row["spans"]=[[a+len(prefix),b+len(prefix)] for a,b in row["spans"]]
    other={**row,"id":2}
    cases=expand(annotated_sources([row,other],labels,{"1":gold,"2":gold}))
    assert [c["id"] for c in cases]==[1,2]
    for case in cases:
        assert case["original_annotations"]==gold
        segments=case["source_segments_with_original_membership"]
        restored="".join(s["gap_before"]+s["literal_original_text"] for s in segments)+case["trailing_original_text"]
        assert restored==row["text"]
        for i,s in enumerate(segments):
            assert s["original_span_index"]==i
            assert s["literal_original_text"]==row["text"][slice(*row["spans"][i])]
            assert s["original_member_for"]==[h for h in labels if i in gold[h]["spans"]]


def test_equivalent_member_program_access_preserves_native_input_despite_code_and_id_changes():
    from legal_skill_guard.learning.decision_evidence import member_program_payload

    original,labels,_=fixture()
    row={k:original[k] for k in ("id","text","spans")}
    def bank(sid,method):
        return [{"id":sid,"hypothesis_ids":["h1"],"guidance":{"python_source":
            "def propose_members(text, spans, public_hypothesis_key):\n"
            "    return [i for i,(a,b) in enumerate(spans) if 'retain' in text[a:b]."+method+"()]\n"}}]
    a=member_program_payload(row,labels,None,"Same task.",bank("old_identity","lower"))
    b=member_program_payload(row,labels,None,"Same task.",bank("new_identity","casefold"))
    assert a[:2]==b[:2]
    assert a[2]["per_hypothesis_proposed_original_indices"]==b[2]["per_hypothesis_proposed_original_indices"]
    assert a[2]["actual_member_program_executions"][0]["program_sha256"]!=b[2]["actual_member_program_executions"][0]["program_sha256"]


def test_draft_feedback_reconstructs_every_actual_proposal_without_selected_cases():
    from legal_skill_guard.learning.member_contract import draft_member_feedback, member_replay_cases
    from legal_skill_guard.learning.packing import expand

    _,labels,gold=fixture()
    a={"h1":[0],"h2":[],"h3":[1]};b={"h1":[0,1,2],"h2":[1],"h3":[]}
    parents=[{"document_id":i,"by_hypothesis":member_replay_cases(a,gold,labels)} for i in (1,2)]
    drafts=[{"document_id":i,"by_hypothesis":member_replay_cases(b,gold,labels)} for i in (1,2)]
    feedback=draft_member_feedback(parents,drafts,labels)
    decoded=expand(feedback["all_seen_sources_and_hypotheses"])
    assert [r["document_id"] for r in decoded]==[1,2]
    for row in decoded:
        assert list(row["by_hypothesis"])==list(labels)
        for h,delta in row["by_hypothesis"].items():
            restore=lambda runs:{v for x,y in runs for v in range(x,y+1)}
            assert sorted((set(a[h])-restore(delta["removed_original_index_runs"])) |
                          restore(delta["added_original_index_runs"]))==b[h]
    assert feedback["Gold_non_neutral_read_proposal_counts_NOT_native_performance"]["draft"]["tp"]==6
    assert "accept" not in feedback and "improves" not in feedback
    with pytest.raises(ValueError,match="identical complete"):
        draft_member_feedback(parents,drafts[:1],labels)


def test_generic_teacher_catalog_preserves_program_feedback_and_all_literal_values():
    from legal_skill_guard.learning.member_contract import member_replay_cases
    from legal_skill_guard.learning.packing import keyed,table

    _,labels,gold=fixture()
    feedback=member_replay_cases({"h1":[0,1],"h2":[1],"h3":[]},gold,labels)
    text='Original literal source: "shall not"; all characters and newlines.\n'
    body={"full_current_sources":[text,text],"original_annotations":keyed(gold),
          "actual_current_parent_source_program_component_replays":table([
              {"document_id":i,"by_hypothesis":keyed(feedback)} for i in (1,2)]),
          "explicitly_partial_historical_context":True,"unchanged_empty_array":[]}
    encoded=encode_teacher_body(body)
    assert decode_teacher_body(encoded)==body
    assert text in encoded["verbatim_text_catalog"]  # Two long repetitions must also be shared losslessly.
    assert "all_seen_train_cases" not in decode_teacher_body(encoded)
    assert "derived_original_member_feedback" in json.dumps(encoded)
    bad=copy.deepcopy(body)
    nested=bad["actual_current_parent_source_program_component_replays"]["rows"][0][1]
    nested["rows"][0][0]=[2]  # Inconsistent metadata must fail, not be normalized.
    with pytest.raises(ValueError,match="Inconsistent member feedback"):
        encode_teacher_body(bad)


def test_historical_witness_skills_preserve_original_members_and_exclude_same_source():
    from legal_skill_guard.learning.decision_evidence import (
        training_witness_catalog,materialize_witness_skills,witnessed_skill_payload,witness_knowledge_view)
    source,labels,gold=fixture();row={k:source[k] for k in ('id','text','spans')}
    catalog=training_witness_catalog([row],labels,{'1':gold})
    assert set(catalog)=={'1:h1','1:h2'}  # Partial excerpts do not demonstrate NM.
    bank=[{'id':'past_grounded_skill','hypothesis_ids':['h1'],'guidance':{
        'procedure':'Inspect the actual operative condition.','witness_refs':['1:h1']}}]
    compiled=materialize_witness_skills(bank,labels,catalog)
    assert compiled[0]['witnesses'][0]['complete_original_evidence_texts']==[
        row['text'][a:b] for i,(a,b) in enumerate(row['spans']) if i in (0,2)]
    unseen={**row,'id':2,'text':row['text']+' Different source.'}
    p={'by_hypothesis':{h:{'candidates':[],'raw_scores':[.1,.2,.3]} for h in labels}}
    outputs={}
    for mode in ('empty','procedure_only','witnesses_only','combined'):
        messages,schema,receipt=witnessed_skill_payload(unseen,labels,p,'Same task.',compiled,mode=mode)
        outputs[mode]=(json.loads(messages[1]['content']),schema,receipt)
        assert receipt['historical_source_IDs_hashes_refs_and_span_coordinates_not_served']
        assert '1:h1' not in messages[1]['content'] and 'source_case_id' not in messages[1]['content']
        assert 'original_span_index' not in json.dumps(outputs[mode][0].get('historical_evidence_demonstrations',[]))
    assert outputs['empty'][1]==outputs['combined'][1]  # Original native output, no adapter.
    assert 'historical_evidence_demonstrations' not in outputs['procedure_only'][0]
    assert outputs['witnesses_only'][0]['learned_legal_procedures']==[]
    assert outputs['combined'][0]['historical_evidence_demonstrations'][0]['original_training_label']=='Entailment'
    knowledge=witness_knowledge_view(compiled)
    assert knowledge['historical_evidence_demonstrations']==outputs['combined'][0]['historical_evidence_demonstrations']
    assert knowledge['learned_legal_procedures']==outputs['combined'][0]['learned_legal_procedures']
    changed=copy.deepcopy(compiled);changed[0]['id']='different_audit_id'
    changed[0]['witnesses'][0]['source_sha256']='different_audit_hash'
    assert witness_knowledge_view(changed)==knowledge  # Audit storage is not delivered linguistic knowledge.
    for same in (row,{**row,'id':999},{**row,'text':row['text']+' Changed source.'}):
        messages,_,receipt=witnessed_skill_payload(same,labels,p,'Same task.',compiled,mode='combined')
        assert not receipt['served_historical_witness_refs']
        assert receipt['excluded_same_source_witness_refs']==['1:h1']
        assert 'historical_evidence_demonstrations' not in json.loads(messages[1]['content'])
    assert source['annotation_sets'][0]['annotations']==gold


@pytest.mark.parametrize('kind',['future','duplicate','scope'])
def test_invalid_historical_witness_references_fail_without_substitution(kind):
    from legal_skill_guard.learning.decision_evidence import training_witness_catalog,materialize_witness_skills
    source,labels,gold=fixture();row={k:source[k] for k in ('id','text','spans')}
    catalog=training_witness_catalog([row],labels,{'1':gold})
    skill={'id':'s','hypothesis_ids':['h1'],'guidance':{
        'procedure':'Source check.','witness_refs':['1:h1']}}
    if kind=='future':skill['guidance']['witness_refs']=['2:h1']
    elif kind=='duplicate':skill['guidance']['witness_refs']*=2
    else:skill['hypothesis_ids']=['h2']
    with pytest.raises((ValueError,ValidationError)):
        materialize_witness_skills([skill],labels,catalog)


@pytest.mark.parametrize("invalid", [False,True])
def test_fixed_draft_executes_once_and_final_is_not_selected_by_training_score(invalid):
    from types import SimpleNamespace
    from experiments import decision_evidence_transfer as module
    from legal_skill_guard.learning.executable_features import MEMBER_PROGRAM_GUIDANCE_SCHEMA
    from legal_skill_guard.learning.member_contract import member_replay_cases
    from legal_skill_guard.learning.publication import apply_differential_publication,differential_schema

    original,labels,gold=fixture();row={k:original[k] for k in ("id","text","spans")}
    def bank(result):
        return [{"id":"p","hypothesis_ids":["h1"],"guidance":{"python_source":
            "def propose_members(text, spans, public_hypothesis_key):\n    return "+result+"\n"}}]
    parent=bank("[0]")
    def delta(result):
        return {"operations":[{"operation":"UPDATE","target_ids":["p"],"skill":bank(result)[0],
            "source_case_ids":[1],"rationale":"Synthetic CPU protocol fixture, not efficacy evidence."}],"noop_reason":None}
    draft,final=delta("[1,1]" if invalid else "[0,2]"),delta("[1]")
    study=module.RankedOnline.__new__(module.RankedOnline)
    study.labels,study.bank,study.current_batch=labels,copy.deepcopy(parent),1
    study.cfg={"method":module.DRAFT_METHOD,"library_token_hard_cap":4096};study.program_cost={};records={};calls=[]
    study.meter=SimpleNamespace(token_count=lambda **_:100)
    study.record=lambda name,value:records.setdefault(name,value)
    study.progress=lambda *args,**kwargs:None;study.check=lambda:None
    parents=[{"document_id":1,"by_hypothesis":member_replay_cases({"h1":[0],"h2":[],"h3":[]},gold,labels)}]
    body={"current_parent_library":parent,"actual_current_parent_source_program_component_replays":parents}
    def teacher(name,system,value,schema):
        calls.append(name)
        assert study.bank==parent
        return copy.deepcopy(draft if name.endswith("_draft") else final)
    study.teacher_call=teacher
    schema=differential_schema(labels,parent,[1],guidance_schema=MEMBER_PROGRAM_GUIDANCE_SCHEMA)
    invoke=lambda:study.draft_execution_update("online_b1",body,schema,parent,[row],{"1":gold},parents)
    if invalid:
        with pytest.raises(ValueError,match="Duplicate"):
            invoke()
        assert calls==["online_b1_draft"] and "program_replays/b1_draft.json" not in records
    else:
        value=invoke()
        assert calls==["online_b1_draft","online_b1_revision"]
        assert study.program_cost["one_unpublished_draft_training_replay_not_native"]["CPU_subprocesses"]==1
        assert records["program_replays/b1_draft.json"]["complete_actual_CPU_replays"][0]["by_hypothesis"]["h1"]["original_member_hits"]==[0,2]
        # Final[1] is worse than both parent[0] and draft[0,2] for Gold[0,2].
        # Nevertheless it is the final delta, not the scored-best candidate.
        published=apply_differential_publication(parent,value,labels,[1],guidance_schema=MEMBER_PROGRAM_GUIDANCE_SCHEMA)
        assert published==bank("[1]") and study.bank==parent
