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
from legal_skill_guard.task import original_feedback, original_metrics


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
