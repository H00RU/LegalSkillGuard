"""Small boundary tests for the new task, not a second evaluation framework."""

import copy
import json

import pytest

from experiments.openexempt_online import Online, acceptance, actor_payload
from legal_skill_guard.learning.legal_namespace import (
    active_bank,
    allowable_namespaces,
    decode_claim_plan,
    decode_classification,
    decode_reference,
    public_catalog,
)
from legal_skill_guard.openexempt import (
    ACTIVE_CASE_FIELDS,
    active_case_input,
    answer_schema,
    evaluate,
    metrics,
    public_case_key,
)

COMPONENTS = {
    "instruction": "For every asset select all applicable exemptions.",
    "meta_instruction": "Use only public statutes and facts.",
    "statutes": ("Ariz. Rev. Stat. § 33-1123\nHousehold property up to $15,000.\n"
                 "735 Ill. Comp. Stat. 5/12-1001(b)\nOther property up to $4,000."),
    "solved_steps": "The Debtor may claim property exemptions under Arizona statutes.",
    "facts": "A (hereinafter the Debtor) owns a watch worth $40.",
}


def guidance(text, jurisdiction="ALL"):
    return {"when": "public condition", "procedure": text,
            "avoid_when": "other", "operators": [], "jurisdiction": jurisdiction}


def test_public_case_group_does_not_depend_on_expert_answers():
    class Case:
        def __init__(self, target):
            self.target = target

        def serialize(self):
            return {"state_jurisdiction": "ARIZONA", "facts": "same public facts",
                    "assets": [{"description": "watch", "dollar_value": 40,
                                "category_hints": ["private"],
                                "applicable_exemptions": self.target}]}

    assert public_case_key(Case(["private A"])) == public_case_key(Case(["private B"]))


def test_actor_gets_only_original_prompt_and_scoped_knowledge():
    bank = [{"id": "EC1", "hypothesis_ids": ["EC"], "guidance": guidance("EC instruction")},
            {"id": "EV1", "hypothesis_ids": ["EV"], "guidance": guidance("EV instruction")}]
    row = {"family": "EC", "prompt": "original public text", "solution": "SECRET",
           "components": {**copy.deepcopy(COMPONENTS),
                          "response_format": "EXAMPLE_CAR", "format_reminder": "FORMAT_ONLY"}}
    messages, schema, supplied = actor_payload(row, bank)
    assert messages[-1]["content"].endswith(active_case_input(row))
    assert "EXAMPLE_CAR" not in str(messages) and "FORMAT_ONLY" not in str(messages)
    assert "EC instruction" in messages[1]["content"]
    assert all(row["components"][key] in messages[-1]["content"] for key in ACTIVE_CASE_FIELDS)
    assert "SECRET" not in str(messages)
    assert "EV instruction" not in str(messages)
    assert [s["id"] for s in supplied] == ["EC1"]
    assert schema["additionalProperties"]["items"] == {
        "type": "string", "enum": list(public_catalog(row))}
    assert answer_schema("EC")["type"] == "object"
    assert "public_checks" not in str(schema)


def record(family, value):
    return {"family": family, "score": {"precision": value, "recall": value,
            "f1": value, "exact_target": value == 1, "invalid_format": 0}}


def test_train_acceptance_requires_real_improvement_and_past_retention():
    parent = [record("EC", 0.4), record("EV", 0.3)]
    improved = [record("EC", 0.6), record("EV", 0.3)]
    assert acceptance(parent, improved, [], [])["accepted"]
    assert not acceptance(parent, parent, [], [])["accepted"]
    assert not acceptance(parent, improved, parent,
                          [record("EC", 0.2), record("EV", 0.3)])["accepted"]
    assert metrics(copy.deepcopy(parent))["mean_family_f1"] == 0.35
    unsafe = copy.deepcopy(improved)
    unsafe[1]["score"]["full_output_f1"] = 0.1
    assert not acceptance(parent, unsafe, [], [])["accepted"]
    safer = copy.deepcopy(parent)
    safer[1]["score"]["full_output_f1"] = 0.5
    assert acceptance(parent, safer, [], [])["accepted"]


def test_original_official_scoring_not_a_new_semantic_judge():
    ec = {"case_id": 1, "family": "EC"}
    target = {"watch": ["11 U.S.C. § 522(d)(5)"]}
    assert evaluate(ec, target, target)["f1"] == 1
    assert evaluate(ec, {}, target)["f1"] == 0
    assert evaluate(ec, None, target)["invalid_format"] == 1
    ev = {"case_id": 1, "family": "EV"}
    target = {"watch": [{"citation": "11 U.S.C. § 522(d)(5)", "claim_value": 1000}]}
    wrong = {"watch": [{"citation": "11 U.S.C. § 522(d)(5)", "claim_value": 500}]}
    assert evaluate(ev, target, target)["f1"] == 1
    assert evaluate(ev, wrong, target)["f1"] == 0
    extra = {**target, "nonexempt extra asset": [
        {"citation": "11 U.S.C. § 522(d)(5)", "claim_value": 100}]}
    audit = evaluate(ev, extra, target)
    assert audit["f1"] == 1  # Preserve the original metric, including its limitation.
    assert audit["officially_unscored_predicted_claims"] == 1
    assert audit["full_output_f1"] == 2 / 3
    assert audit["full_output_claim_tp"] == 1
    assert audit["full_output_claim_fp"] == 1


def test_frozen_initial_control_shares_only_identical_wire_requests(monkeypatch, tmp_path):
    from legal_skill_guard.experiment.storage import RunStore
    from legal_skill_guard.utils.hashing import canonical_json_sha256

    study = Online.__new__(Online)
    study.cfg = {"batch_source_cases": 1, "source_cases": 1, "generation": {"seed": 45}}
    study.rows = [{"case_id": 17, "source_key": "source17", "family": f, "batch": 1,
                   "prompt": "original public input",
                   "components": copy.deepcopy(COMPONENTS)}
                  for f in ("EC", "EV")]
    study.bank = [{"id": "s", "hypothesis_ids": ["EC", "EV"],
                   "guidance": guidance("inspect")}]
    study.frozen_bank = copy.deepcopy(study.bank)
    study.native, study.summaries = [], []
    study.prequential_empty, study.prequential_skills, study.prequential_frozen = [], [], []
    study.out = tmp_path
    written = {}
    monkeypatch.setattr(RunStore, "immutable_json", lambda p, v: written.update({str(p): copy.deepcopy(v)}))
    monkeypatch.setattr(RunStore, "atomic_json", lambda p, v: None)
    study.progress = lambda *a, **k: None

    def answer(row, bank, stage, arm):
        study.native.append((row["family"], arm))
        return {"case_id": 17, "source_key": "source17", "family": row["family"], "arm": arm,
                "bank_sha256": canonical_json_sha256(bank), "raw_call_path": f"{row['family']}/{arm}"}

    def grade(records):
        for r in records:
            r["score"] = record(r["family"], 0.5)["score"]
        return records

    study.answer, study.grade = answer, grade
    study.update = lambda *args: {"bank_sha256": canonical_json_sha256(study.bank),
                                 "parent_bank_sha256": canonical_json_sha256(study.bank)}
    assert study.execute() == "completed_bounded_mechanism_study"
    assert len(study.native) == 4  # Two families x empty/initial, not six requests.
    assert study.summaries[0]["prequential_actual_new_native_calls"] == 4
    assert study.summaries[0]["online_minus_frozen"]["mean_f1_difference"] == 0
    assert len(study.prequential_frozen) == len(study.prequential_skills) == 2


def test_irrelevant_namespace_updates_do_not_change_the_actual_request():
    row = {"family": "EV", "components": copy.deepcopy(COMPONENTS)}
    bank = [{"id": "az", "hypothesis_ids": ["EC", "EV"],
             "guidance": guidance("Arizona procedure", "ARIZONA")},
            {"id": "il", "hypothesis_ids": ["EC", "EV"],
             "guidance": guidance("Illinois before", "ILLINOIS")}]
    changed = copy.deepcopy(bank)
    changed[1]["guidance"]["procedure"] = "A substantial irrelevant Illinois revision"
    assert actor_payload(row, bank) == actor_payload(row, changed)
    assert [s["id"] for s in active_bank(row, changed)] == ["az"]
    changed[0]["guidance"]["procedure"] = "A relevant Arizona revision"
    assert actor_payload(row, bank) != actor_payload(row, changed)
    assert allowable_namespaces({"components": {"solved_steps":
        "The Debtors may claim property exemptions under Federal and Oregon statutes."}}) == {
            "FEDERAL", "OREGON"}
    with pytest.raises(ValueError):
        allowable_namespaces({"components": {"solved_steps": "Guess from domicile facts."}})


def test_public_label_decoding_is_not_a_legal_answer_repair():
    row = {"family": "EV", "components": copy.deepcopy(COMPONENTS)}
    catalog = public_catalog(row)
    assert catalog == {"L001": "Ariz. Rev. Stat. § 33-1123"}
    assert decode_classification({"unchanged name": ["L001"]}, catalog) == {
        "unchanged name": ["Ariz. Rev. Stat. § 33-1123"]}
    raw = {"assets": [{"asset_name": "even an unsupported asset is not corrected",
            "asset_value": 9999, "claims": [
                {"citation_ref": "L001", "limit_expression": "min(V,999999)"}]}]}
    decoded = decode_claim_plan(raw, catalog)
    assert decoded["assets"][0]["asset_value"] == 9999
    assert decoded["assets"][0]["claims"][0] == {
        "citation": "Ariz. Rev. Stat. § 33-1123", "limit_expression": "min(V,999999)"}
    assert "citation_ref" in raw["assets"][0]["claims"][0]  # Never mutate a native submission.
    for invalid in ("L002", "L999", "Ariz. Rev. Stat. § 33-1125(1)(p)"):
        with pytest.raises(ValueError):
            decode_reference(invalid, catalog)


def test_cross_stage_cache_reuses_only_identical_wire_without_reference_feedback(tmp_path, monkeypatch):
    monkeypatch.setattr("experiments.openexempt_online.ROOT", tmp_path)
    study = Online.__new__(Online)
    study.cfg = {"execution_contract": "source_grounded_claim_operations",
                 "generation": {"seed": 45, "max_tokens": 100}}
    study.out, study.request_cache, study.reuse_events, study.native = tmp_path, {}, [], []
    study.check = lambda: None
    study.progress = lambda *a, **k: None

    def call(dest, messages, schema, max_tokens, metadata):
        study.native.append(metadata)
        return {"content": json.dumps({"watch": ["L001"]}), "finish_reason": "stop"}

    study.call = call
    row = {"case_id": 1, "source_key": "first", "family": "EC",
           "prompt": "public original", "components": copy.deepcopy(COMPONENTS)}
    first = study.answer(row, [], "first", "empty")
    first["score"] = {"private_feedback": "must not propagate into a later prediction"}
    second_row = {**copy.deepcopy(row), "case_id": 2, "source_key": "second"}
    irrelevant = [{"id": "il", "hypothesis_ids": ["EC", "EV"],
                   "guidance": guidance("New Illinois-only instructions", "ILLINOIS")}]
    second = study.answer(second_row, irrelevant, "second", "candidate")
    assert len(study.native) == 1 and len(study.reuse_events) == 1
    assert "score" not in second and second["case_id"] == 2
    assert first["parsed"] == second["parsed"]
    assert second["physical_alias_of_identical_wire"]["not_an_independent_generation"]
    assert second["raw_call_path"] == first["raw_call_path"]
    study.cfg["generation"]["seed"] = 46
    study.answer(row, [], "different_profile", "empty")
    assert len(study.native) == 2  # No cache match after a real generation-profile change.
