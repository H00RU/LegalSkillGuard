"""Small boundary tests for the new task, not a second evaluation framework."""

import copy

from experiments.openexempt_online import Online, acceptance, actor_payload
from legal_skill_guard.openexempt import (
    ACTIVE_CASE_FIELDS,
    active_case_input,
    answer_schema,
    evaluate,
    metrics,
    public_case_key,
)


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
    bank = [{"id": "EC1", "hypothesis_ids": ["EC"], "guidance": "EC instruction"},
            {"id": "EV1", "hypothesis_ids": ["EV"], "guidance": "EV instruction"}]
    row = {"family": "EC", "prompt": "original public text", "solution": "SECRET",
           "components": {**{key: key + " public content" for key in ACTIVE_CASE_FIELDS},
                          "response_format": "EXAMPLE_CAR", "format_reminder": "FORMAT_ONLY"}}
    messages, schema, supplied = actor_payload(row, bank)
    assert messages[-1]["content"] == active_case_input(row)
    assert "EXAMPLE_CAR" not in str(messages) and "FORMAT_ONLY" not in str(messages)
    assert "EC instruction" in messages[1]["content"]
    assert all(row["components"][key] in messages[-1]["content"] for key in ACTIVE_CASE_FIELDS)
    assert "SECRET" not in str(messages)
    assert "EV instruction" not in str(messages)
    assert [s["id"] for s in supplied] == ["EC1"]
    assert schema["additionalProperties"]["items"] == {"type": "string"}
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
                   "components": {key: key + " public content" for key in ACTIVE_CASE_FIELDS}}
                  for f in ("EC", "EV")]
    study.bank = [{"id": "s", "hypothesis_ids": ["EC", "EV"], "guidance": {
        "when": "public condition", "procedure": "inspect", "avoid_when": "other", "operators": []}}]
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
