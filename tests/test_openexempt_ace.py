"""Small native-role adapter checks, not ACE accuracy or a second harness."""

import copy
import json

import pytest
from jsonschema import ValidationError, validate

from legal_skill_guard.learning.experiment import INITIAL_PLAYBOOK, bullets
from legal_skill_guard.learning.openexempt_ace import (
    commit_additions,
    curator_request,
    decode_generator,
    generator_payload,
    reflector_request,
    validate_reflection,
)


def row(family="EV"):
    return {"case_id": 1, "family": family, "solution": "SECRET", "components": {
        "instruction": "Find all applicable exemptions.", "meta_instruction": "Only public law.",
        "statutes": "Ariz. Rev. Stat. § 33-1123\nHousehold property up to $15,000.",
        "solved_steps": "The Debtor may claim property exemptions under Arizona statutes.",
        "facts": "A (hereinafter the Debtor) owns a watch worth $40.",
        "response_format": "EXAMPLE_CAR_NOT_AN_ACTUAL_ASSET", "format_reminder": "format only"}}


BOOK = INITIAL_PLAYBOOK + "\n[misc-00001] helpful=0 harmful=0 :: inspect actual public conditions"


@pytest.mark.parametrize("direct", [False, True])
def test_ace_generator_keeps_native_bullet_reporting_without_hidden_prior_or_target(direct):
    source = row()
    messages, schema = generator_payload(source, BOOK, direct_numeric=direct)
    text = "\n".join(message["content"] for message in messages)
    assert "SECRET" not in text and "EXAMPLE_CAR_NOT_AN_ACTUAL_ASSET" not in text
    assert all(source["components"][k] in text for k in ("facts", "statutes", "solved_steps"))
    assert "misc-00001" in text and "no current-case feedback" in text
    assert "chain of thought / reasoning" not in text
    submitted = {"reasoning": "public explanation", "bullet_ids": ["misc-00001"],
        "final_answer": {"assets": [{"asset_name": "unchanged unsupported name", "asset_value": 999,
            "claims": [{"citation_ref": "Ariz. Rev. Stat. section 33-1123",
                        "limit_expression": "min(V,30)"}]}]}}
    if direct:
        submitted["final_answer"] = {"unchanged unsupported name": [{
            "citation_ref": "Ariz. Rev. Stat. section 33-1123", "claim_value": 999}]}
        assert "limit_expression" not in str(schema)
    validate(submitted, schema)
    result = decode_generator(source, BOOK, submitted, direct_numeric=direct)
    assert result["used_bullet_ids"] == ["misc-00001"]
    assert result["answer"] == {"unchanged unsupported name": [{
        "citation": "Ariz. Rev. Stat. § 33-1123", "claim_value": 999 if direct else 30}]}
    if direct:
        assert result["execution_receipt"] is None and result["native_program"] is None
    else:
        assert result["execution_receipt"]["actually_executed_operator_ids"] == []
        assert result["native_program"]["assets"][0]["asset_value"] == 999
    invalid = copy.deepcopy(submitted)
    if direct:
        invalid["final_answer"]["unchanged unsupported name"][0]["claim_value"] = "min(V,30)"
    else:
        invalid["final_answer"]["assets"][0]["claims"][0]["limit_expression"] = None
    with pytest.raises(ValidationError):
        decode_generator(source, BOOK, invalid, direct_numeric=direct)
    invalid = copy.deepcopy(submitted)
    invalid["bullet_ids"] = ["unknown"]
    with pytest.raises(ValidationError):
        decode_generator(source, BOOK, invalid, direct_numeric=direct)
    _, empty_schema = generator_payload(source, INITIAL_PLAYBOOK, direct_numeric=direct)
    with pytest.raises(ValidationError):
        validate(submitted, empty_schema)


def test_native_reflector_tags_only_actual_citations_and_retains_train_targets():
    observation = {"case_id": 1, "family": "EV", "used_bullet_ids": ["misc-00001"],
                   "answer": {}, "parse_error": None, "public_rationale": "actual saved text"}
    prompt, schema, cited = reflector_request(row(), observation, {"watch": []}, BOOK,
                                             {"original_F1": 0.0})
    assert "actual saved text" in prompt and '"watch"' in prompt and "misc-00001" in prompt
    reflection = {k: "public finding" for k in (
        "reasoning", "error_identification", "root_cause_analysis", "correct_approach", "key_insight")}
    reflection["bullet_tags"] = [{"id": "misc-00001", "tag": "harmful"}]
    validate_reflection(reflection, schema, cited)
    bad = copy.deepcopy(reflection)
    bad["bullet_tags"] = []
    with pytest.raises(ValidationError):
        validate_reflection(bad, schema, cited)
    with pytest.raises(ValueError):
        reflector_request(row(), {**observation, "case_id": 2}, {}, BOOK, {})
    with pytest.raises(ValueError):
        reflector_request(row(), {**observation, "used_bullet_ids": None}, {}, BOOK, {})
    _, no_tags_schema, no_tags = reflector_request(row(), {**observation,
        "used_bullet_ids": None, "parse_error": "actual malformed output"}, {}, BOOK, {})
    reflection["bullet_tags"] = []
    validate_reflection(reflection, no_tags_schema, no_tags)


def test_native_counter_last_tag_and_add_only_curator_are_not_our_score_gate():
    reflections = [{"bullet_tags": [{"id": "misc-00001", "tag": tag}]}
                   for tag in ("helpful", "harmful")]
    prompt, schema, counted = curator_request(BOOK, reflections, [row()],
        current_step=1, total_samples=8, token_budget=4096)
    assert bullets(counted)["misc-00001"]["helpful"] == 0
    assert bullets(counted)["misc-00001"]["harmful"] == 1
    assert "chain of thought / reasoning" not in prompt
    value = {"reasoning": "public rationale", "operations": [{"type": "ADD", "section": "others",
              "content": "Check the applicable public legal condition before valuation."}]}
    committed = commit_additions(counted, value, schema, token_count=lambda **kwargs: 300,
                                 token_budget=4096)
    actual = bullets(committed["playbook"])
    assert len(actual) == 2 and actual["misc-00001"]["content"] == bullets(BOOK)["misc-00001"]["content"]
    assert "misc-00002" in actual and committed["next_id"] == 3
    bad = copy.deepcopy(value)
    bad["operations"][0]["type"] = "DELETE"
    with pytest.raises(ValidationError):
        commit_additions(counted, bad, schema, token_count=lambda **kwargs: 300, token_budget=4096)
    with pytest.raises(ValueError, match="exceeds capacity"):
        commit_additions(counted, value, schema, token_count=lambda **kwargs: 4097, token_budget=4096)
    assert len(bullets(counted)) == 1  # No mutation, truncation or score-selected publication.


@pytest.mark.parametrize("direct", [False, True])
def test_complete_online_ACE_batch_releases_labels_only_after_all_native_predictions(
        tmp_path, monkeypatch, direct):
    from types import SimpleNamespace

    import experiments.openexempt_ace_online as ace
    import experiments.openexempt_online as common
    from legal_skill_guard.openexempt import evaluate

    monkeypatch.setattr(ace, "ROOT", tmp_path)
    monkeypatch.setattr(common, "ROOT", tmp_path)
    study = ace.ACEOnline.__new__(ace.ACEOnline)
    study.cfg = {"source_cases": 1, "batch_source_cases": 1, "grading_directory": "grading",
        "execution_contract": ("direct_statutory_claims" if direct
                               else "source_grounded_claim_operations"),
        "generation": {"seed": 45, "max_tokens": 100},
        "library_token_hard_cap": 4096}
    study.rows = [{**row(family), "batch": 1, "source_key": "fixture", "prompt": "public"}
                  for family in ("EC", "EV")]
    study.out, study.playbook = tmp_path / "out", INITIAL_PLAYBOOK
    study.native, study.teachers, study.teacher_attempts, study.summaries = [], [], 0, []
    study.request_cache, study.reuse_events, study.current_batch = {}, [], 0
    study.episodes = {arm: [] for arm in ("ace", "empty", "empty_direct_numeric")}
    study.check, study.progress = lambda: None, lambda *a, **k: None
    study.meter = SimpleNamespace(token_count=lambda **kwargs: 100)
    citation, reference = "Ariz. Rev. Stat. § 33-1123", "Ariz. Rev. Stat. section 33-1123"

    def call(dest, messages, schema, max_tokens, metadata):
        study.native.append(metadata)
        final = ({"watch": [reference]} if metadata["family"] == "EC" else
                 {"watch": [{"citation_ref": reference, "claim_value": 40}]}
                 if direct or metadata["arm"] == "empty_direct_numeric" else
                 {"assets": [{"asset_name": "watch", "asset_value": 40,
                    "claims": [{"citation_ref": reference, "limit_expression": "min(V,15000)"}]}]})
        value = ({"reasoning": "public finding", "bullet_ids": [], "final_answer": final}
                 if metadata["arm"] == "ace" else final)
        return {"content": json.dumps(value), "finish_reason": "stop"}

    def released_targets(path):
        assert len(list((study.out / "native/b1_prequential").glob("*.answer.json"))) == 6
        return {"targets": {"EC": {"watch": [citation]},
                            "EV": {"watch": [{"citation": citation, "claim_value": 40}]}}}

    def grade(records):
        for rec in records:
            target = released_targets(None)["targets"][rec["family"]]
            rec["score"] = evaluate(rec, rec["parsed"]["answer"], target)
        return records

    def teacher(name, system, prompt, schema):
        assert (study.out / "batches/b1_prequential.json").exists()
        study.teachers.append(name)
        study.teacher_attempts += 1
        if name.endswith("reflector"):
            value = {k: "public finding" for k in (
                "reasoning", "error_identification", "root_cause_analysis", "correct_approach", "key_insight")}
            return {**value, "bullet_tags": []}
        return {"reasoning": "public finding", "operations": [{"type": "ADD", "section": "others",
            "content": "Check the public statutory conditions before valuing an eligible pair."}]}

    monkeypatch.setattr(ace, "read", released_targets)
    study.call, study.grade, study.teacher_call = call, grade, teacher
    assert study.execute() == "completed_declared_ACE_adaptation_stream"
    assert len(study.native) == (4 if direct else 5)  # Native controls share exact wires only.
    assert len(study.teachers) == 3  # Reflect both real tasks, then curate once.
    assert len(bullets(study.playbook)) == 1
    assert len(study.episodes["ace"]) == 2
    assert (study.out / "publications/b1.json").exists()
