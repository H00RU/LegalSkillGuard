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
    np.testing.assert_array_equal(
        base.lr_["h1"].coef_[0], model.lr_["h1"].coef_[0][: base.X1_.shape[1]]
    )
    assert base.m2_.booster_.model_to_string() == model.m2_.booster_.model_to_string()
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
