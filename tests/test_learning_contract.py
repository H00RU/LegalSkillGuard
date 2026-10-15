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
