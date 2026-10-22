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


@pytest.mark.parametrize("family", ["EC", "EV"])
@pytest.mark.parametrize("positive_asset", [False, True])
def test_native_TRAIN_success_handles_negative_assets_without_unnecessary_regeneration(
        family, positive_asset):
    from experiments.openexempt_ace_online import ACEOnline
    from legal_skill_guard.openexempt import evaluate

    source = {"case_id": 1, "family": family}
    law = "11 U.S.C. § 522(d)(5)"
    claim = law if family == "EC" else {"citation": law, "claim_value": 100}
    target = {"ineligible property": []}
    if positive_asset:
        target["eligible property"] = [claim]
    good = {"family": family, "parse_error": None, "score": evaluate(source, target, target)}
    if family == "EC" or not positive_asset:
        assert good["score"]["f1"] < 1
    assert ACEOnline.train_solved(good)
    bad = {**target, "ineligible property": [claim]}
    assert not ACEOnline.train_solved(
        {"family": family, "parse_error": None, "score": evaluate(source, bad, target)})
    assert not ACEOnline.train_solved(
        {"family": family, "parse_error": "invalid", "score": evaluate(source, None, target)})


@pytest.mark.parametrize("direct", [False, True])
def test_ace_generator_keeps_native_bullet_reporting_without_hidden_prior_or_target(direct):
    source = row()
    messages, schema = generator_payload(source, BOOK, direct_numeric=direct)
    text = "\n".join(message["content"] for message in messages)
    assert "SECRET" not in text and "EXAMPLE_CAR_NOT_AN_ACTUAL_ASSET" not in text
    assert all(source["components"][k] in text for k in ("facts", "statutes", "solved_steps"))
    assert "misc-00001" in text and "no current-case feedback" in text
    assert "chain of thought / reasoning" not in text
    assert "final_answer is the task-answer JSON object" in text
    assert '"final_answer": "[Your concise final answer here]"' not in text
    assert "calc-00001" not in text and "fin-00002" not in text
    train_messages, _ = generator_payload(source, BOOK, direct_numeric=direct,
        training_reflection={"correct_approach": "TRAIN_ONLY_MARKER"})
    assert "TRAIN_ONLY_MARKER" not in text
    assert "TRAIN_ONLY_MARKER" in str(train_messages)
    assert "released-TRAIN regeneration" in train_messages[0]["content"]
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


@pytest.mark.parametrize("family", ["EC", "EV"])
def test_repeated_native_provenance_preserves_legal_answer_and_tags_distinct_bullets_once(
        tmp_path, monkeypatch, family):
    from experiments.openexempt_ace_online import ACEOnline

    monkeypatch.setattr("legal_skill_guard.learning.legal_namespace.asset_description_lexicon",
                        lambda: ("watch",))
    monkeypatch.setattr("experiments.openexempt_ace_online.ROOT", tmp_path)
    source = {**row(family), "source_key": "fixture"}
    reference = "Ariz. Rev. Stat. section 33-1123"
    value = [reference] if family == "EC" else [{"citation_ref": reference, "claim_value": 999}]
    submitted = {"reasoning": "actual public explanation", "bullet_ids": ["misc-00001"] * 3,
                 "final_answer": {"A001": value}}
    original = copy.deepcopy(submitted)
    decoded = decode_generator(source, BOOK, submitted, direct_numeric=True, asset_references=True)
    unique = {**submitted, "bullet_ids": ["misc-00001"]}
    expected = decode_generator(source, BOOK, unique, direct_numeric=True, asset_references=True)
    assert decoded["answer"] == expected["answer"]
    assert decoded["used_bullet_ids"] == submitted["bullet_ids"]
    assert submitted == original

    study = ACEOnline.__new__(ACEOnline)
    study.cfg = {"execution_contract": "direct_statutory_claims", "execution_contract_version": 14,
                 "generation": {"seed": 45, "max_tokens": 100}}
    study.playbook, study.out, study.request_cache, study.reuse_events = BOOK, tmp_path, {}, []
    study.check = lambda: None
    study.call = lambda *a, **k: {"content": json.dumps(submitted), "finish_reason": "stop"}
    record = study.answer(source, "b2_prequential")
    assert record["parse_error"] is None
    assert record["parsed"] == {"answer": expected["answer"]}
    assert record["actual_wrapper_submission"] == original
    assert record["used_bullet_ids"] == original["bullet_ids"]

    observation = {**record, "answer": record["parsed"]["answer"]}
    prompt, schema, cited = reflector_request(source, observation, {}, BOOK, {},
        direct_numeric=True, asset_references=True)
    assert cited == ["misc-00001"]
    assert json.dumps(observation, ensure_ascii=False) in prompt
    assert schema["properties"]["bullet_tags"]["minItems"] == 1
    assert schema["properties"]["bullet_tags"]["maxItems"] == 1
    reflection = {k: "public finding" for k in (
        "reasoning", "error_identification", "root_cause_analysis", "correct_approach", "key_insight")}
    reflection["bullet_tags"] = [{"id": "misc-00001", "tag": "helpful"}]
    validate_reflection(reflection, schema, cited)


def test_generator_task_type_adaptation_never_removes_public_question_text():
    source = row()
    source["components"]["facts"] += (
        "\n**Answer in this exact JSON format:**\nPUBLIC_FACT_LITERAL_NOT_A_TEMPLATE")
    messages, _ = generator_payload(source, BOOK, direct_numeric=True)
    assert source["components"]["facts"] in messages[-1]["content"]
    assert messages[-1]["content"].count("**Output types:**") == 1


def test_generator_fails_closed_if_pinned_output_template_changes(monkeypatch):
    import legal_skill_guard.learning.openexempt_ace as adapter

    monkeypatch.setattr(adapter, "GENERATOR_PROMPT", "Unexpected changed upstream template")
    with pytest.raises(ValueError, match="Pinned ACE Generator output example changed"):
        generator_payload(row(), BOOK, direct_numeric=True)


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


@pytest.mark.parametrize("family", ["EC", "EV"])
def test_asset_reference_ACE_roles_share_the_common_public_encoding(monkeypatch, family):
    import legal_skill_guard.learning.legal_namespace as namespace
    from experiments.openexempt_online import actor_payload

    monkeypatch.setattr(namespace, "asset_description_lexicon", lambda: ("watch",))
    source = row(family)
    common, native_schema, _ = actor_payload(source, [], direct_numeric=True, asset_references=True)
    messages, schema = generator_payload(source, BOOK, direct_numeric=True, asset_references=True)
    assert schema["properties"]["final_answer"] == native_schema
    assert common[-1]["content"] in messages[-1]["content"]
    assert "SECRET" not in str(messages)
    ref = "Ariz. Rev. Stat. section 33-1123"
    value = [ref] if family == "EC" else [{"citation_ref": ref, "claim_value": 999}]
    submission = {"reasoning": "public finding", "bullet_ids": ["misc-00001"],
                  "final_answer": {"A001": value}}
    validate(submission, schema)
    decoded = decode_generator(source, BOOK, submission, direct_numeric=True, asset_references=True)
    expected = (["Ariz. Rev. Stat. § 33-1123"] if family == "EC" else
                [{"citation": "Ariz. Rev. Stat. § 33-1123", "claim_value": 999}])
    assert decoded["answer"] == {"watch": expected}
    assert decoded["native_program"] is decoded["execution_receipt"] is None
    observation = {"case_id": 1, "family": family, "used_bullet_ids": ["misc-00001"],
                   "answer": decoded["answer"], "parse_error": None}
    prompt, _, _ = reflector_request(source, observation, {"watch": []}, BOOK, {},
                                     direct_numeric=True, asset_references=True)
    assert '"A001"' in prompt
    prompt, _, _ = curator_request(BOOK, [{"bullet_tags": []}], [source],
        current_step=1, total_samples=2, token_budget=8192,
        direct_numeric=True, asset_references=True)
    assert "A001" in prompt


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


@pytest.mark.parametrize("profile", ["program", "direct", "asset_refs"])
@pytest.mark.parametrize("repair_after", [0, 2, None])
def test_complete_online_ACE_batch_releases_labels_only_after_all_native_predictions(
        tmp_path, monkeypatch, profile, repair_after):
    from types import SimpleNamespace

    import experiments.openexempt_ace_online as ace
    import experiments.openexempt_online as common
    from legal_skill_guard.openexempt import evaluate

    direct, asset_references = profile != "program", profile == "asset_refs"
    if asset_references:
        monkeypatch.setattr("legal_skill_guard.learning.legal_namespace.asset_description_lexicon",
                            lambda: ("watch",))
    monkeypatch.setattr(ace, "ROOT", tmp_path)
    monkeypatch.setattr(common, "ROOT", tmp_path)
    study = ace.ACEOnline.__new__(ace.ACEOnline)
    study.cfg = {"source_cases": 1, "batch_source_cases": 1, "grading_directory": "grading",
        "execution_contract": ("direct_statutory_claims" if direct
                               else "source_grounded_claim_operations"),
        "execution_contract_version": 14 if asset_references else 13 if direct else 12,
        "generation": {"seed": 45, "max_tokens": 100},
        "ace_max_TRAIN_reflection_rounds": 3,
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
        if metadata["arm"] == "ace" and repair_after != 0:
            number = (int(metadata["stage"].rsplit("round", 1)[1])
                      if "TRAIN_round" in metadata["stage"] else 0)
            if repair_after is None or number < repair_after:
                final = ({"assets": [{"asset_name": "watch", "asset_value": 40, "claims": []}]}
                         if metadata["family"] == "EV" and not direct else {"watch": []})
        if asset_references:
            final = {"A001": final["watch"]}
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
            value["correct_approach"] = "distinct actual TRAIN feedback " + name
            return {**value, "bullet_tags": []}
        return {"reasoning": "public finding", "operations": [{"type": "ADD", "section": "others",
            "content": "Check the public statutory conditions before valuing an eligible pair."}]}

    monkeypatch.setattr(ace, "read", released_targets)
    study.call, study.grade, study.teacher_call = call, grade, teacher
    assert study.execute() == "completed_declared_ACE_adaptation_stream"
    rounds = 0 if repair_after == 0 else repair_after or 3
    assert len(study.native) == (4 if direct else 5) + 2 * rounds
    assert len(study.teachers) == (3 if rounds == 0 else 2 * rounds + 1)
    assert len(bullets(study.playbook)) == 1
    assert len(study.episodes["ace"]) == 2
    assert (study.out / "publications/b1.json").exists()
    saved = json.loads((study.out / "batches/b1_records.json").read_text())
    expected_first_f1 = 1 if repair_after == 0 else 0
    assert all(x["score"]["f1"] == expected_first_f1 for x in saved["ace"])
    for family in ("EC", "EV"):
        trajectory = json.loads((study.out / "training" / f"b1_1_{family}.json").read_text())
        assert trajectory["TRAIN_finally_solved"] is (repair_after is not None)
        assert trajectory["initial_first_encounter_observation"]["score"]["f1"] == expected_first_f1
        assert len(trajectory["rounds"]) == (rounds or 1)
    with pytest.raises(ValueError, match="forbidden in first-encounter"):
        study.answer(study.rows[0], "forbidden", training_reflection={"correct_approach": "TRAIN_ONLY"})
