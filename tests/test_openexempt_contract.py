"""Small boundary tests for the new task, not a second evaluation framework."""

import copy
import json

import pytest

from experiments.openexempt_online import (
    Online,
    acceptance,
    actor_payload,
    balanced_replay_gain,
    candidate_feedback,
    legal_scope_admission,
    native_claim_feedback,
    task_admission,
    teacher_evidence_rows,
    TEACHER_EVIDENCE_CONTRACT,
    EXECUTION_EXAMPLE_MARKER,
    EXECUTABLE_GUIDANCE,
    validate_edit_diagnoses,
)
from legal_skill_guard.learning.legal_namespace import (
    active_bank,
    allowable_namespaces,
    decode_asset_references,
    decode_claim_plan,
    decode_classification,
    decode_reference,
    public_asset_catalog,
    public_catalog,
)
from legal_skill_guard.learning.phase_dispatch import PhaseDispatch
from legal_skill_guard.learning.task_scoped_skills import (
    compose_legal_edits,
    compose_task_edits,
    import_blind_prior,
    legal_edit_coordinates,
    task_view,
    validate_scoped_bank,
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


def guidance(text, jurisdiction="ALL", tasks=("EC", "EV")):
    return {"by_task": [{"tasks": list(tasks), "when": "public condition",
                         "procedure": text, "avoid_when": "other"}],
            "operators": [], "jurisdiction": jurisdiction}


def diagnosed_test_reply(study, delta):
    """Synthetic teachers explicitly use the production classified-edit interface."""
    from legal_skill_guard.learning.publication import apply_differential_publication
    ids = sorted({i for op in delta["operations"] for i in op["source_case_ids"]})
    candidate = apply_differential_publication(study.bank, delta, ("EC", "EV"), ids,
                                               guidance_schema=EXECUTABLE_GUIDANCE)
    before = {(s["id"], f): s for f in ("EC", "EV") for s in task_view(study.bank, f)}
    after = {(s["id"], f): s for f in ("EC", "EV") for s in task_view(candidate, f)}
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    return {"delta": delta, "diagnoses": [{"skill_id": sid, "task": task,
        "kind": "SKILL_DEFECT", "rule_anchor": "", "source_case_ids": ids}
        for sid, task in changed]}


def test_execution_diagnosis_preserves_knowledge_and_replaces_example_without_growth():
    rule = "Retain every independently applicable legal alternative."
    parent = [{"id": "rule", "hypothesis_ids": ["EC"],
               "guidance": guidance(rule, tasks=("EC",))}]
    proposed = copy.deepcopy(parent)
    proposed[0]["guidance"]["by_task"][0]["procedure"] += EXECUTION_EXAMPLE_MARKER + " Both citations."
    audit = [{"skill_id": "rule", "task": "EC", "kind": "EXECUTION_LAPSE",
              "rule_anchor": rule, "source_case_ids": [1]}]
    assert validate_edit_diagnoses(parent, proposed, audit, [1])["kinds"]["EXECUTION_LAPSE"] == 1
    revised = copy.deepcopy(proposed)
    revised[0]["guidance"]["by_task"][0]["procedure"] = rule + EXECUTION_EXAMPLE_MARKER + " One compact revised example."
    validate_edit_diagnoses(proposed, revised, audit, [1])
    assert revised[0]["guidance"]["by_task"][0]["procedure"].count(EXECUTION_EXAMPLE_MARKER) == 1
    bad = copy.deepcopy(proposed)
    bad[0]["guidance"]["by_task"][0]["when"] = "different eligibility"
    with pytest.raises(ValueError, match="protected legal field"):
        validate_edit_diagnoses(parent, bad, audit, [1])
    bad = copy.deepcopy(proposed)
    bad[0]["guidance"]["by_task"][0]["procedure"] = "Rewritten law" + EXECUTION_EXAMPLE_MARKER + " example"
    with pytest.raises(ValueError, match="knowledge prefix"):
        validate_edit_diagnoses(parent, bad, audit, [1])


def test_classified_new_knowledge_is_possible_from_empty_and_bad_anchors_do_not_pass():
    bank = [{"id": "new", "hypothesis_ids": ["EC"],
             "guidance": guidance("New source-supported procedure", tasks=("EC",))}]
    audit = [{"skill_id": "new", "task": "EC", "kind": "SKILL_DEFECT",
              "rule_anchor": "", "source_case_ids": [1]}]
    assert validate_edit_diagnoses([], bank, audit, [1])["kinds"]["SKILL_DEFECT"] == 1
    with pytest.raises(ValueError, match="actual changed"):
        validate_edit_diagnoses([], bank, [], [1])
    with pytest.raises(ValueError, match="supplied TRAIN"):
        validate_edit_diagnoses([], bank, audit, [2])
    audit[0]["rule_anchor"] = "invented existing law"
    with pytest.raises(ValueError, match="actual parent"):
        validate_edit_diagnoses([], bank, audit, [1])


def test_operational_skill_defect_can_rewrite_true_but_circular_task_guidance():
    rule = "For an eligible citation, report the amount under that citation."
    parent = [{"id": "rule", "hypothesis_ids": ["EV"],
               "guidance": guidance(rule, tasks=("EV",))}]
    candidate = copy.deepcopy(parent)
    block = candidate[0]["guidance"]["by_task"][0]
    block["when"] = "The supplied public jurisdiction permits this property alternative."
    block["procedure"] = "Check the factual eligibility condition, retain each independent alternative, then calculate its amount."
    diagnosis = [{"skill_id": "rule", "task": "EV", "kind": "SKILL_DEFECT",
                  "rule_anchor": rule, "source_case_ids": [1]}]
    assert validate_edit_diagnoses(parent, candidate, diagnosis, [1])["kinds"]["SKILL_DEFECT"] == 1
    diagnosis[0]["kind"] = "EXECUTION_LAPSE"
    with pytest.raises(ValueError, match="protected legal field"):
        validate_edit_diagnoses(parent, candidate, diagnosis, [1])


def test_placement_launcher_checks_run_path_before_calls_and_does_not_follow_rejection(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    from legal_skill_guard.experiment.storage import RunStore

    source = Path(__file__).resolve().parents[1] / "artifacts/launches/openexempt_skill_position_mechanism_20261027_run01.py"
    spec = importlib.util.spec_from_file_location("position_launcher_contract", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    cfg = {"study_kind": "task_conditioned_skill_placement_TRAIN_mechanism",
        "planned_teacher_responses_max": 0, "run_id": "probe", "mechanism_original_parent_run": "parent",
        "on_success_formal_config": "formal.json"}
    config = RunStore.immutable_json(tmp_path / "config.json", cfg)
    seen = []

    def checked_read(path):
        if Path(path) == tmp_path / "runs/parent/completion.json":
            seen.append(Path(path))
            raise RuntimeError("deliberate pre-generation stop")
        return json.loads(Path(path).read_text())

    def unexpected(*args, **kwargs):
        pytest.fail("No model initialization or formal freeze is permitted here")

    monkeypatch.setattr(module, "read", checked_read)
    monkeypatch.setattr(module, "Online", unexpected)
    monkeypatch.setattr(module, "freeze", unexpected)
    monkeypatch.setattr(module, "preserve", lambda run, stage, names: {"stage": stage, "files": len(names), "paths": []})
    with pytest.raises(RuntimeError, match="pre-generation stop"):
        module.run_probe(config)
    assert seen == [tmp_path / "runs/parent/completion.json"]
    assert json.loads((tmp_path / "runs/probe/progress.json").read_text())["state"] == "failed"
    assert json.loads((tmp_path / "runs/probe/failure.json").read_text())["actual_native_calls"] == 0
    RunStore.immutable_json(tmp_path / "formal.json", {"run_id": "formal"})
    module.follow_up(SimpleNamespace(cfg=cfg), {"formal_adoption_accepted": False})
    decision = json.loads((tmp_path / "artifacts/launches/probe/formal_decision.json").read_text())
    assert not decision["will_start_if_boundary_checks_pass"]
    assert not (tmp_path / "runs/formal").exists()


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
    bank = [{"id": "EC1", "hypothesis_ids": ["EC"],
             "guidance": guidance("EC instruction", tasks=("EC",))},
            {"id": "EV1", "hypothesis_ids": ["EV"],
             "guidance": guidance("EV instruction", tasks=("EV",))}]
    row = {"family": "EC", "prompt": "original public text", "solution": "SECRET",
           "components": {**copy.deepcopy(COMPONENTS),
                          "response_format": "EXAMPLE_CAR", "format_reminder": "FORMAT_ONLY"}}
    messages, schema, supplied = actor_payload(row, bank)
    assert messages[-1]["content"].endswith(active_case_input(row))
    assert "EXAMPLE_CAR" not in str(messages) and "FORMAT_ONLY" not in str(messages)
    assert "EC instruction" in messages[1]["content"]
    assert all(row["components"][key] in messages[-1]["content"] for key in ACTIVE_CASE_FIELDS)
    assert len(messages) == 3 and "The current legal case follows" in messages[1]["content"]
    assert "SECRET" not in str(messages)
    assert "EV instruction" not in str(messages)
    assert [s["id"] for s in supplied] == ["EC1"]
    assert schema["additionalProperties"]["items"] == {
        "type": "string", "enum": list(public_catalog(row))}
    assert answer_schema("EC")["type"] == "object"
    assert "public_checks" not in str(schema)


def record(family, value):
    return {"family": family, "score": {"precision": value, "recall": value,
            "f1": value, "exact_target": value == 1, "invalid_format": 0,
            "full_output_f1": value, "negative_target_asset_predicted_claims": 0}}


def utility_cohorts():
    """Paired current16/prior112 records; no generated or relabeled answers."""
    def cohort(first, count, ec, ev):
        return [{**record(family, value), "case_id": case}
                for case in range(first, first + count)
                for family, value in (("EC", ec), ("EV", ev))]
    current = cohort(1, 16, .87, .86)
    prior = cohort(17, 112, .89, .89)
    return current, copy.deepcopy(current), prior, copy.deepcopy(prior)


def test_utility_admission_retains_net_gain_despite_small_prior_full_loss():
    from experiments.openexempt_online import UTILITY_ADMISSION

    current, proposed, prior, replay = utility_cohorts()
    for r in proposed:
        if r["family"] == "EC":
            r["score"].update(f1=.94, full_output_f1=.94)
    for r in replay:
        if r["family"] == "EC":
            r["score"].update(f1=.892, full_output_f1=.8884)
    assert not acceptance(current, proposed, prior, replay)["accepted"]
    result = acceptance(current, proposed, prior, replay, contract=UTILITY_ADMISSION)
    assert result["accepted"] and not result["prior_full_output_nonregression"]
    assert result["prior_full_output_within_risk_bound"]
    assert result["all_seen_family_nonregression"] and result["all_seen_full_output_nonregression"]
    assert task_admission(current, proposed, prior, replay,
                          contract=UTILITY_ADMISSION)["EC"]["accepted"]
    coordinate = [{"id": "EC:ALL", "task": "EC", "source_case_ids": list(range(1, 129))}]
    assert legal_scope_admission(coordinate, current, proposed, prior, replay,
                                 contract=UTILITY_ADMISSION)["EC:ALL"]["accepted"]


def test_utility_admission_keeps_invalid_and_false_claim_penalties_without_count_veto():
    from experiments.openexempt_online import UTILITY_ADMISSION

    current, proposed, prior, replay = utility_cohorts()
    for r in proposed:
        if r["family"] == "EV":
            r["score"].update(f1=.96, full_output_f1=.96)
    for r in replay:
        if r["family"] == "EV":
            r["score"].update(f1=.91, full_output_f1=.91)
    failure = next(r for r in replay if r["case_id"] == 17 and r["family"] == "EV")
    failure["score"].update(f1=0, full_output_f1=0, invalid_format=1)
    extra = next(r for r in replay if r["case_id"] == 18 and r["family"] == "EV")
    extra["score"].update(full_output_f1=.85, officially_unscored_predicted_claims=1)
    original = copy.deepcopy((current, proposed, prior, replay))
    assert not acceptance(current, proposed, prior, replay)["accepted"]
    result = acceptance(current, proposed, prior, replay, contract=UTILITY_ADMISSION)
    assert result["accepted"] and not result["prior_negative_asset_and_format_nonregression"]
    assert result["candidate_prior"]["EV"]["invalid_format"] == 1
    assert result["candidate_prior"]["EV"]["negative_or_unscored_asset_claims"] == 1
    assert failure["score"]["f1"] == failure["score"]["full_output_f1"] == 0
    assert (current, proposed, prior, replay) == original


@pytest.mark.parametrize("kind", ["excess_prior_loss", "all_seen_loss", "current_loss"])
def test_utility_admission_rejects_real_quality_loss(kind):
    from experiments.openexempt_online import UTILITY_ADMISSION

    current, proposed, prior, replay = utility_cohorts()
    for r in proposed:
        if r["family"] == "EV":
            r["score"].update(f1=.99 if kind == "excess_prior_loss" else .861,
                              full_output_f1=.99 if kind == "excess_prior_loss" else .861)
    for r in replay:
        if r["family"] == "EV":
            value = .875 if kind == "excess_prior_loss" else .881
            r["score"].update(f1=value, full_output_f1=value)
    if kind == "current_loss":
        for r in proposed:
            if r["family"] == "EC":
                r["score"].update(f1=.86, full_output_f1=.86)
        for r in replay:
            r["score"].update(f1=.99, full_output_f1=.99)
    assert not acceptance(current, proposed, prior, replay, contract=UTILITY_ADMISSION)["accepted"]


def test_utility_admission_and_full_output_ranking_require_real_paired_records():
    from experiments.openexempt_online import UTILITY_ADMISSION

    before = [{**record(f, .5), "case_id": 1} for f in ("EC", "EV")]
    a, b = copy.deepcopy(before), copy.deepcopy(before)
    for r in a:
        r["score"].update(f1=.8, full_output_f1=.51)
    for r in b:
        r["score"].update(f1=.6, full_output_f1=.55)
    assert balanced_replay_gain(before, a) > balanced_replay_gain(before, b)
    assert (balanced_replay_gain(before, a, contract=UTILITY_ADMISSION)
            < balanced_replay_gain(before, b, contract=UTILITY_ADMISSION))
    with pytest.raises(ValueError, match="distinct"):
        acceptance(before + before, a + a, [], [], contract=UTILITY_ADMISSION)
    with pytest.raises(ValueError, match="Unknown"):
        acceptance(before, a, [], [], contract="unfrozen_policy")


def test_utility_teacher_system_matches_gate_anchor_and_historical_feedback_contract():
    from experiments.openexempt_online import (
        CANDIDATE_FEEDBACK_ADDITION, DIRECT_AUTHOR_SYSTEM, EXECUTION_AWARE_ADDITION,
        LEGACY_ADMISSION, TASK_PROJECTION_TEACHING, UTILITY_ADMISSION, teaching_system_contract,
    )

    original = (DIRECT_AUTHOR_SYSTEM + EXECUTION_AWARE_ADDITION + TASK_PROJECTION_TEACHING
                + CANDIDATE_FEEDBACK_ADDITION)
    system = teaching_system_contract(original, UTILITY_ADMISSION)
    assert "one percentage point" in system
    assert "individual counts are diagnostics" in system
    assert "minimum EC/EV complete-output-F1 gain" in system
    assert "including a split or a MERGE into a new ID" in system
    assert "NOT a new replay from the current parent" in system
    assert "minimum EC/EV native-F1 gain" not in system
    strict = teaching_system_contract(original, LEGACY_ADMISSION)
    assert "avoid increases in claims on negative/unscored assets" in strict
    assert "one percentage point" not in strict
    assert "avoid increases in claims on negative/unscored assets" in original


def test_retained_candidate_feedback_survives_noop_success_and_stays_one_per_task(tmp_path):
    from experiments.openexempt_online import retained_candidate_feedback
    from legal_skill_guard.experiment.storage import RunStore
    from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

    before, later = [], [{"id": "later_wisconsin_update"}]
    observations = {(1, f): {**record(f, .8), "case_id": 1} for f in ("EC", "EV")}

    def failed(task, path):
        return {"accepted": False, "teaching_task": task, "candidate": [{"id": "bad"}],
                "delta": {"operations": [], "noop_reason": None},
                "actual_replay": [{**record(task, .1), "case_id": 1, "raw_call_path": path}]}

    def publication(batch, parent, bank, decisions):
        RunStore.immutable_json(tmp_path / "publications" / f"b{batch}.json", {
            "parent_bank_sha256": csha(parent), "bank_sha256": csha(bank),
            "training_decisions": decisions})

    old = failed("EV", "native/real_old_failed_EV.json")
    publication(1, before, before, [failed("EC", "native/real_old_failed_EC.json"), old])
    publication(2, before, before, [{"accepted": False, "teaching_task": "EV", "explicit_noop": True}])
    publication(3, before, later, [{"accepted": True, "teaching_task": "EV",
        "candidate": later, "proposed_bank": later, "proposal_fully_committed": True}])
    retained = retained_candidate_feedback(tmp_path, 4, observations, csha(later))
    assert len(retained) == 2 and {v["teaching_task"] for v in retained} == {"EC", "EV"}
    ev = next(v for v in retained if v["teaching_task"] == "EV")
    assert ev["candidate_feedback_origin"]["batch"] == 1
    assert ev["candidate_feedback_origin"]["historical_attempt_parent_bank_sha256"] == csha(before)
    assert ev["candidate_feedback_origin"]["current_reference_parent_bank_sha256"] == csha(later)
    assert ev["candidate_feedback_origin"]["historical_candidate_not_rerun"]
    assert ev["feedback_witness_replay"] == old["actual_replay"]
    assert len(ev["feedback_witness_replay"]) <= 8
    newer = failed("EV", "native/real_newer_failed_EV.json")
    publication(4, later, later, [newer])
    retained = retained_candidate_feedback(tmp_path, 5, observations, csha(later))
    assert len(retained) == 2
    ev = next(v for v in retained if v["teaching_task"] == "EV")
    assert ev["candidate_feedback_origin"]["batch"] == 4
    assert ev["feedback_witness_replay"] == newer["actual_replay"]


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


@pytest.mark.parametrize("family", ["EC", "EV"])
def test_public_asset_refs_only_project_descriptions_and_literal_mentions(tmp_path, monkeypatch, family):
    from jsonschema import ValidationError, validate

    import legal_skill_guard.openexempt as bridge

    path = tmp_path / "data/assets/assets.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps({"description": name,
        "dollar_value": 9999997, "applicable_exemptions": ["SECRET_LAW"],
        "category_hints": ["PRIVATE_CATEGORY"]}) for name in ("watch", "gold ring", "ring")))
    monkeypatch.setattr(bridge, "UPSTREAM", tmp_path)
    row = {"family": family, "solution": "PRIVATE_ANSWER", "case": {"private": "PRIVATE_CASE"},
           "components": {**copy.deepcopy(COMPONENTS), "facts": (
               "Facts:\nA (hereinafter the Debtor) owns a WATCH and a gold ring. "
               "A separate ring is on loan. The dog watched quietly.")}}
    catalog = public_asset_catalog(row)
    assert catalog == {"A001": "WATCH", "A002": "gold ring", "A003": "ring"}
    messages, schema, _ = actor_payload(row, [], direct_numeric=True, asset_references=True)
    other, other_schema, _ = actor_payload(row, [{"id": "skill", "hypothesis_ids": [family],
        "guidance": guidance("public procedure", tasks=(family,))}],
        direct_numeric=True, asset_references=True)
    assert schema == other_schema and messages[0] == other[0]
    case_message = other[-1] if family == "EC" else other[1]
    assert messages[-1] == case_message and row["components"]["facts"] in case_message["content"]
    assert all(secret not in str(messages) for secret in (
        "9999997", "SECRET_LAW", "PRIVATE_CATEGORY", "PRIVATE_ANSWER", "PRIVATE_CASE"))
    assert "ownership" in messages[0]["content"]
    final_contract = messages[-1]["content"].rsplit("\n\nOutput contract:", 1)[1]
    assert "asset_ref keys" in final_contract and "asset descriptions" not in final_contract
    assert schema["additionalProperties"] is False and schema["required"] == list(catalog)
    reference = "Ariz. Rev. Stat. section 33-1123"
    value = [reference] if family == "EC" else [{"citation_ref": reference, "claim_value": 999}]
    submitted = {"A001": value, "A002": [], "A003": []}
    validate(submitted, schema)
    decoded = decode_asset_references(submitted, catalog)
    assert decoded == {"WATCH": value, "gold ring": [], "ring": []}
    assert submitted == {"A001": value, "A002": [], "A003": []}  # No mutation or monetary fix.
    for bad in ({"A001": value}, {**submitted, "735 Ill. Comp. Stat. 5/12-1001(b)": []}):
        with pytest.raises(ValidationError):
            validate(bad, schema)
        with pytest.raises(ValueError, match="exactly the declared"):
            decode_asset_references(bad, catalog)
    _, old_schema, _ = actor_payload(row, [], direct_numeric=True)
    assert isinstance(old_schema["additionalProperties"], dict)
    with pytest.raises(ValueError, match="common direct-answer"):
        actor_payload(row, [], asset_references=True)
    row["components"]["facts"] = "Facts:\nNo lexicon item appears."
    with pytest.raises(ValueError, match="No literal public asset mention"):
        public_asset_catalog(row)


@pytest.mark.parametrize("family", ["EC", "EV"])
def test_v14_native_answer_decodes_public_asset_ids_without_repair(tmp_path, monkeypatch, family):
    import legal_skill_guard.learning.legal_namespace as namespace

    monkeypatch.setattr(namespace, "asset_description_lexicon", lambda: ("watch", "bowl"))
    monkeypatch.setattr("experiments.openexempt_online.ROOT", tmp_path)
    study = Online.__new__(Online)
    study.cfg = {"execution_contract": "direct_statutory_claims", "execution_contract_version": 14,
                 "generation": {"seed": 45, "max_tokens": 100}}
    study.out, study.native, study.request_cache, study.reuse_events = tmp_path, [], {}, []
    study.check, study.progress = lambda: None, lambda *a, **k: None
    row = {"case_id": 1, "source_key": "fixture", "family": family, "prompt": "public original",
           "components": {**copy.deepcopy(COMPONENTS), "facts": (
               "Facts:\nA (hereinafter the Debtor) owns a watch worth $40 and a bowl worth $20.")}}
    reference = "Ariz. Rev. Stat. section 33-1123"
    value = [reference] if family == "EC" else [{"citation_ref": reference, "claim_value": 999}]

    def call(dest, messages, schema, max_tokens, metadata):
        study.native.append(metadata)
        assert schema["required"] == ["A001", "A002"]
        return {"content": json.dumps({"A001": value, "A002": []}), "finish_reason": "stop"}

    study.call = call
    answer = study.answer(row, [], "first", "skills")
    second = study.answer(row, [], "control", "empty")
    expected = (["Ariz. Rev. Stat. § 33-1123"] if family == "EC" else
                [{"citation": "Ariz. Rev. Stat. § 33-1123", "claim_value": 999}])
    assert answer["parsed"]["answer"] == {"watch": expected, "bowl": []}
    assert answer["public_label_submission"] == {"A001": value, "A002": []}
    assert answer["native_program"] is answer["execution_receipt"] is None
    assert second["parsed"] == answer["parsed"] and len(study.native) == 1


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


def test_ec_empty_target_false_claim_keeps_native_score_but_fails_complete_output_retention():
    row = {"case_id": 1, "family": "EC"}
    law = "11 U.S.C. § 522(d)(5)"
    target = {"eligible property": [law], "ineligible property": []}
    bad = {"eligible property": [law], "ineligible property": [law]}
    before, after = evaluate(row, target, target), evaluate(row, bad, target)
    assert before["f1"] == after["f1"] == 0.5  # Never alter the official score.
    assert before["full_output_f1"] == 1 and after["full_output_f1"] == 2 / 3
    assert after["negative_target_asset_predicted_claims"] == 1
    prior = [{"family": "EC", "score": before}, record("EV", 1)]
    harm = [{"family": "EC", "score": after}, record("EV", 1)]
    current = [record("EC", 0.4), record("EV", 0.4)]
    improved = [record("EC", 0.7), record("EV", 0.4)]
    assert not acceptance(current, improved, prior, harm)["accepted"]
    assert not task_admission(current, improved, prior, harm)["EC"]["accepted"]


@pytest.mark.parametrize("family", ["EC", "EV"])
def test_entirely_negative_case_and_invalid_output_are_not_hidden_by_zero_f1(family):
    row = {"case_id": 1, "family": family}
    law = "11 U.S.C. § 522(d)(5)"
    target = {"ineligible property": []}
    claim = law if family == "EC" else {"citation": law, "claim_value": 100}
    good, bad = evaluate(row, target, target), evaluate(row, {"ineligible property": [claim]}, target)
    assert good["f1"] == bad["f1"] == good["full_output_f1"] == bad["full_output_f1"] == 0
    a, b = {"family": family, "score": good}, {"family": family, "score": bad}
    other = "EV" if family == "EC" else "EC"
    def bundle(r):
        return [r, record(other, 1)]

    assert not task_admission(bundle(a), bundle(b), [], [])[family]["accepted"]
    assert task_admission(bundle(b), bundle(a), [], [])[family]["accepted"]
    assert not acceptance([a, record(other, 0.4)], [b, record(other, 0.7)], [], [])["accepted"]
    invalid = {"family": family, "score": evaluate(row, None, target)}
    assert not task_admission(bundle(a), bundle(invalid), [], [])[family]["accepted"]
    assert not acceptance([a, record(other, 0.4)], [invalid, record(other, 0.7)], [], [])["accepted"]


@pytest.mark.parametrize("online_cap", [30, 15])
def test_frozen_initial_control_shares_native_plan_not_computed_answer(monkeypatch, tmp_path,
                                                                    online_cap):
    from legal_skill_guard.experiment.storage import RunStore
    from legal_skill_guard.utils.hashing import canonical_json_sha256

    study = Online.__new__(Online)
    monkeypatch.setattr("experiments.openexempt_online.ROOT", tmp_path)
    study.cfg = {"batch_source_cases": 1, "source_cases": 1,
                 "execution_contract": "source_grounded_claim_operations",
                 "generation": {"seed": 45, "max_tokens": 100}}
    study._dispatch = PhaseDispatch(study.cfg)
    study.rows = [{"case_id": 17, "source_key": "source17", "family": f, "batch": 1,
                   "prompt": "original public input",
                   "components": copy.deepcopy(COMPONENTS)}
                  for f in ("EC", "EV")]
    study.bank = [{"id": "s", "hypothesis_ids": ["EC", "EV"],
                   "guidance": guidance("inspect")}]
    study.bank[0]["guidance"]["operators"] = [{
        "id": "cap", "citation": "Ariz. Rev. Stat. § 33-1123",
        "limit_expression": f"min(V,{online_cap})"}]
    study.bank[0]["guidance"]["jurisdiction"] = "ARIZONA"
    study.frozen_bank = copy.deepcopy(study.bank)
    study.frozen_bank[0]["guidance"]["operators"][0]["limit_expression"] = "min(V,30)"
    study.native, study.summaries = [], []
    study.request_cache, study.reuse_events = {}, []
    study.prequential_empty, study.prequential_skills, study.prequential_frozen = [], [], []
    study.prequential_direct = []
    study.out = tmp_path
    written = {}
    monkeypatch.setattr(RunStore, "immutable_json", lambda p, v: written.update({str(p): copy.deepcopy(v)}))
    monkeypatch.setattr(RunStore, "atomic_json", lambda p, v: None)
    study.progress = lambda *a, **k: None
    study.check = lambda: None

    def call(dest, messages, schema, max_tokens, metadata):
        study.native.append(metadata)
        ref = "Ariz. Rev. Stat. section 33-1123"
        if metadata["family"] == "EC":
            value = {"watch": [ref]}
        elif metadata["arm"] == "empty_direct_numeric":
            value = {"watch": [{"citation_ref": ref, "claim_value": 30}]}
        else:
            value = {"assets": [{"asset_name": "watch", "asset_value": 40, "claims": [{
                "citation_ref": ref,
                "limit_expression": "min(V,30)" if metadata["arm"] == "empty" else None}]}]}
        return {"content": json.dumps(value), "finish_reason": "stop"}

    def grade(records):
        for r in records:
            r["score"] = record(r["family"], 0.5)["score"]
        return records

    study.call, study.grade = call, grade
    study.update = lambda *args: {"bank_sha256": canonical_json_sha256(study.bank),
                                 "parent_bank_sha256": canonical_json_sha256(study.bank)}
    assert study.execute() == "completed_bounded_mechanism_study"
    assert len(study.native) == 5  # EC direct shares empty; EV numeric is genuinely new.
    assert study.summaries[0]["prequential_actual_new_native_calls"] == 5
    assert study.summaries[0]["online_minus_frozen"]["mean_f1_difference"] == 0
    assert len(study.prequential_frozen) == len(study.prequential_skills) == 2
    frozen_ev = study.prequential_frozen[1]
    online_ev = study.prequential_skills[1]
    assert frozen_ev["parsed"]["answer"]["watch"][0]["claim_value"] == 30
    assert online_ev["parsed"]["answer"]["watch"][0]["claim_value"] == online_cap
    assert frozen_ev["raw_call_path"] == online_ev["raw_call_path"]
    assert online_ev["execution_receipt"]["execution_bank_sha256"] == canonical_json_sha256(study.bank)
    assert frozen_ev["execution_receipt"]["execution_bank_sha256"] == canonical_json_sha256(study.frozen_bank)
    assert len(study.prequential_direct) == 2
    assert study.prequential_direct[1]["parsed"]["answer"]["watch"][0]["claim_value"] == 30


def test_irrelevant_namespace_updates_do_not_change_the_actual_request():
    row = {"family": "EV", "components": copy.deepcopy(COMPONENTS)}
    bank = [{"id": "az", "hypothesis_ids": ["EC", "EV"],
             "guidance": guidance("Arizona procedure", "ARIZONA")},
            {"id": "il", "hypothesis_ids": ["EC", "EV"],
             "guidance": guidance("Illinois before", "ILLINOIS")}]
    changed = copy.deepcopy(bank)
    changed[1]["guidance"]["by_task"][0]["procedure"] = "A substantial irrelevant Illinois revision"
    assert actor_payload(row, bank) == actor_payload(row, changed)
    assert [s["id"] for s in active_bank(row, changed)] == ["az"]
    changed[0]["guidance"]["by_task"][0]["procedure"] = "A relevant Arizona revision"
    assert actor_payload(row, bank) != actor_payload(row, changed)
    assert allowable_namespaces({"components": {"solved_steps":
        "The Debtors may claim property exemptions under Federal and Oregon statutes."}}) == {
            "FEDERAL", "OREGON"}
    with pytest.raises(ValueError):
        allowable_namespaces({"components": {"solved_steps": "Guess from domicile facts."}})


@pytest.mark.parametrize("enabled,first_update", [(False, True), (True, True), (True, False)])
def test_first_batch_frozen_control_is_time_fixed_and_never_update_feedback(
        monkeypatch, tmp_path, enabled, first_update):
    from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

    monkeypatch.setattr("experiments.openexempt_online.ROOT", tmp_path)
    study = Online.__new__(Online)
    study.cfg = {"batch_source_cases": 1, "source_cases": 3,
        "execution_contract": "direct_statutory_claims",
        "frozen_after_first_batch_control": enabled,
        "generation": {"seed": 45, "max_tokens": 100}}
    study._dispatch = PhaseDispatch(study.cfg)
    study.rows = [{"case_id": i, "source_key": f"source{i}", "family": family,
                   "batch": i, "prompt": "public input", "components": {
                       **copy.deepcopy(COMPONENTS),
                       "facts": f"Person{i} (hereinafter the Debtor) owns a watch worth $40."}}
                  for i in (1, 2, 3) for family in ("EC", "EV")]
    study.out = tmp_path
    study.bank, study.frozen_bank, study.first_batch_frozen_bank = [], [], []
    study.native, study.summaries, study.reuse_events = [], [], []
    study.request_cache = {}
    study.prequential_empty, study.prequential_skills = [], []
    study.prequential_frozen, study.prequential_direct = [], []
    study.prequential_first_batch_frozen = []
    study.check, study.progress = lambda: None, lambda *a, **k: None
    updates, labels_released = [], []

    def call(dest, messages, schema, max_tokens, metadata):
        study.native.append(metadata)
        ref = "Ariz. Rev. Stat. section 33-1123"
        value = ({"watch": [ref]} if metadata["family"] == "EC" else
                 {"watch": [{"citation_ref": ref, "claim_value": 40}]})
        return {"content": json.dumps(value), "finish_reason": "stop"}

    def grade(records):
        saved = list((tmp_path / "native" / f"b{study.current_batch}_prequential")
                     .glob("*.answer.json"))
        assert len(saved) == (10 if enabled else 8)
        labels_released.append(study.current_batch)
        for rec in records:
            target = ({"watch": ["Ariz. Rev. Stat. § 33-1123"]} if rec["family"] == "EC" else
                      {"watch": [{"citation": "Ariz. Rev. Stat. § 33-1123", "claim_value": 40}]})
            rec["score"] = evaluate(rec, rec["parsed"]["answer"], target)
        return records

    def update(current, seen, observations):
        assert labels_released[-1] == study.current_batch
        assert len(observations) == 2 and all(rec["arm"] == "skills" for rec in observations)
        updates.append(study.current_batch)
        before = csha(study.bank)
        if study.current_batch != 1 or first_update:
            if not study.bank:
                study.bank.append({"id": "learned", "hypothesis_ids": ["EC", "EV"],
                                   "guidance": guidance("first procedure")})
            # Deliberately mutate the live record to detect shallow snapshots.
            study.bank[0]["guidance"]["by_task"][0]["procedure"] = f"procedure{study.current_batch}"
        return {"parent_bank_sha256": before, "bank_sha256": csha(study.bank)}

    study.call, study.grade, study.update = call, grade, update
    assert study.execute() == "completed_bounded_mechanism_study"
    assert updates == labels_released == [1, 2, 3]
    snapshot = tmp_path / "frozen_after_B1.json"
    if not enabled:
        assert not snapshot.exists() and not study.prequential_first_batch_frozen
        assert all("frozen_after_B1" not in item for item in study.summaries)
        assert len(study.native) == 10
        return
    frozen = json.loads(snapshot.read_text())
    assert frozen["freeze_after_exactly_batch"] == 1
    assert frozen["source_case_ids_seen"] == [1]
    assert frozen["bank_sha256"] == csha(study.first_batch_frozen_bank)
    assert frozen["bank_sha256"] != csha(study.bank)
    assert (frozen["bank"][0]["guidance"]["by_task"][0]["procedure"] == "procedure1"
            if first_update else frozen["bank"] == [])
    for batch in (2, 3):
        item = study.summaries[batch - 1]
        assert item["frozen_after_B1_bank_sha256"] == frozen["bank_sha256"]
        assert item["frozen_after_B1_snapshot_already_taken"]
        assert item["frozen_after_B1_evaluation_only_not_teacher_feedback"]
    first = study.summaries[0]
    assert not first["frozen_after_B1_snapshot_already_taken"]
    second = json.loads((tmp_path / "batches/b2_prequential_records.json").read_text())
    for a, b in zip(second["skills"], second["frozen_after_B1"], strict=True):
        assert a["raw_call_path"] == b["raw_call_path"]
    third = json.loads((tmp_path / "batches/b3_prequential_records.json").read_text())
    assert all(rec["bank_sha256"] == frozen["bank_sha256"] for rec in third["frozen_after_B1"])
    assert all(rec["bank_sha256"] != frozen["bank_sha256"] for rec in third["skills"])
    assert len(study.native) == (12 if first_update else 8)


def test_public_label_decoding_is_not_a_legal_answer_repair():
    row = {"family": "EV", "components": copy.deepcopy(COMPONENTS)}
    catalog = public_catalog(row)
    reference = "Ariz. Rev. Stat. section 33-1123"
    assert catalog == {reference: "Ariz. Rev. Stat. § 33-1123"}
    assert reference.isascii() and all(key.isascii() for key in catalog)
    assert decode_classification({"unchanged name": [reference]}, catalog) == {
        "unchanged name": ["Ariz. Rev. Stat. § 33-1123"]}
    raw = {"assets": [{"asset_name": "even an unsupported asset is not corrected",
            "asset_value": 9999, "claims": [
                {"citation_ref": reference, "limit_expression": "min(V,999999)"}]}]}
    decoded = decode_claim_plan(raw, catalog)
    assert decoded["assets"][0]["asset_value"] == 9999
    assert decoded["assets"][0]["claims"][0] == {
        "citation": "Ariz. Rev. Stat. § 33-1123", "limit_expression": "min(V,999999)"}
    assert "citation_ref" in raw["assets"][0]["claims"][0]  # Never mutate a native submission.
    for invalid in ("L001", "L999", "Ariz. Rev. Stat. § 33-1123",
                    "Ariz. Rev. Stat. section 33-1125(1)(p)"):
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
        return {"content": json.dumps({"watch": ["Ariz. Rev. Stat. section 33-1123"]}),
                "finish_reason": "stop"}

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


def test_compiled_action_schema_hides_bodies_but_preserves_all_legal_choices():
    from jsonschema import ValidationError, validate

    components = copy.deepcopy(COMPONENTS)
    components["statutes"] += "\nAriz. Rev. Stat. § 33-1125(1)\nApparel up to $500."
    row = {"family": "EV", "components": components}
    bank = [{"id": "az", "hypothesis_ids": ["EC", "EV"],
             "guidance": guidance("Classify according to the supplied law.", "ARIZONA")}]
    bank[0]["guidance"]["operators"] = [{"id": "cap",
        "citation": "Ariz. Rev. Stat. § 33-1123", "limit_expression": "min(V,12345)"}]
    messages, schema, supplied = actor_payload(row, bank)
    assert "12345" not in str(messages)
    assert "12345" in str(supplied)  # Interpreter, not actor, receives the program.
    delivered = json.loads(messages[-1]["content"].split("\n", 1)[1])
    assert delivered[0]["guidance"]["operators"] == [
        {"citation_ref": "Ariz. Rev. Stat. section 33-1123"}]
    assert "limit_expression" not in delivered[0]["guidance"]["operators"][0]
    claims = schema["properties"]["assets"]["items"]["properties"]["claims"]["items"]
    assert len(claims["anyOf"]) == 2
    refs = {r for branch in claims["anyOf"]
            for r in branch["properties"]["citation_ref"]["enum"]}
    assert refs == set(public_catalog(row))  # No eligibility or Gold filtering.

    def plan(reference, expression):
        return {"assets": [{"asset_name": "unchanged unsupported name", "asset_value": 40,
                 "claims": [{"citation_ref": reference, "limit_expression": expression}]}]}

    cached = "Ariz. Rev. Stat. section 33-1123"
    inline = "Ariz. Rev. Stat. section 33-1125(1)"
    validate(plan(cached, None), schema)
    validate(plan(inline, "min(V,500)"), schema)
    with pytest.raises(ValidationError):
        validate(plan(cached, "min(V,12345)"), schema)
    with pytest.raises(ValidationError):
        validate(plan(inline, None), schema)
    for invalid in ("", "1" * 513, ": 1875", "Shear(500,V,500)", "}]}]}}%20",
                    "/11 U.S.C. section 522(d)(6)"):
        with pytest.raises(ValidationError):
            validate(plan(inline, invalid), schema)
    validate(plan(inline, "1" * 512), schema)  # Syntax/type, not legal truth.
    validate(plan(inline, "unlimited"), schema)
    validate(plan(inline, "min(V,50000 if N==2 else 40000)"), schema)
    validate(plan(inline, "max(.5*V,1e2)"), schema)
    validate(plan(inline, "sin(V)"), schema)  # Lexical alphabet is NOT AST validation.
    changed = copy.deepcopy(bank)
    changed[0]["guidance"]["operators"][0]["limit_expression"] = "min(V,54321)"
    assert actor_payload(row, bank)[:2] == actor_payload(row, changed)[:2]
    ec_row = {**row, "family": "EC"}
    assert actor_payload(ec_row, bank)[:2] == actor_payload(ec_row, changed)[:2]
    ec_payload = json.loads(actor_payload(ec_row, bank)[0][1]["content"].split("\n", 1)[1])
    assert "operators" not in ec_payload[0]["guidance"]
    changed[0]["guidance"]["operators"] = []
    assert actor_payload(row, bank)[:2] != actor_payload(row, changed)[:2]


def test_reused_native_call_executes_new_body_and_never_reuses_answer_or_error(tmp_path,
                                                                          monkeypatch):
    from legal_skill_guard.utils.hashing import canonical_json_sha256

    monkeypatch.setattr("experiments.openexempt_online.ROOT", tmp_path)
    study = Online.__new__(Online)
    study.cfg = {"execution_contract": "source_grounded_claim_operations",
                 "generation": {"seed": 45, "max_tokens": 100}}
    study.out, study.request_cache, study.reuse_events, study.native = tmp_path, {}, [], []
    study.check = lambda: None
    study.progress = lambda *a, **k: None
    native_plan = {"assets": [{"asset_name": "watch", "asset_value": 40, "claims": [{
        "citation_ref": "Ariz. Rev. Stat. section 33-1123", "limit_expression": None}]}]}

    def call(dest, messages, schema, max_tokens, metadata):
        study.native.append(metadata)
        return {"content": json.dumps(native_plan), "finish_reason": "stop"}

    study.call = call
    row = {"case_id": 1, "source_key": "synthetic", "family": "EV",
           "prompt": "public original", "components": copy.deepcopy(COMPONENTS)}
    bank = [{"id": "az", "hypothesis_ids": ["EC", "EV"],
             "guidance": guidance("Inspect the public legal conditions.", "ARIZONA")}]
    bank[0]["guidance"]["operators"] = [{"id": "cap",
        "citation": "Ariz. Rev. Stat. § 33-1123", "limit_expression": "min(V,30)"}]
    first = study.answer(row, bank, "first", "skills")
    assert first["parsed"]["answer"]["watch"][0]["claim_value"] == 30
    # None of these interpreted/graded fields belongs in the native-response cache.
    first["score"] = {"secret_feedback": "not a prediction"}
    first["parsed"]["answer"]["watch"][0]["claim_value"] = 999
    first["execution_receipt"]["actually_executed_operator_ids"] = ["not a real call"]
    changed = copy.deepcopy(bank)
    changed[0]["guidance"]["operators"][0]["limit_expression"] = "min(V,15)"
    second = study.answer(row, changed, "replay", "candidate")
    assert len(study.native) == 1 and len(study.reuse_events) == 1
    assert "score" not in second
    assert second["parsed"]["answer"]["watch"][0]["claim_value"] == 15
    assert second["execution_receipt"]["actually_executed_operator_ids"] == ["az/cap"]
    assert second["execution_receipt"]["execution_bank_sha256"] == canonical_json_sha256(changed)
    assert second["raw_call_path"] == first["raw_call_path"]
    assert not second["physical_alias_of_identical_wire"]["execution_receipt_is_from_original_call"]
    broken = copy.deepcopy(changed)
    broken[0]["guidance"]["operators"][0]["limit_expression"] = "V/0"
    failed = study.answer(row, broken, "bad_body", "candidate")
    assert failed["execution_error"] is not None and failed["parse_error"] is not None
    assert len(study.native) == 1  # No regeneration or old-answer fallback.
    restored = study.answer(row, changed, "restored_body", "candidate")
    assert restored["parse_error"] is None and restored["execution_error"] is None
    assert restored["parsed"]["answer"]["watch"][0]["claim_value"] == 15
    assert len(study.native) == 1  # An old execution error is not a cached raw failure.


@pytest.mark.parametrize("profile", ["program", "direct", "asset_refs"])
def test_teacher_packet_is_bounded_but_current_sources_and_full_replay_are_not_dropped(
        monkeypatch, profile):
    from types import SimpleNamespace

    from legal_skill_guard.utils.hashing import canonical_json_sha256

    direct = profile != "program"
    asset_references = profile == "asset_refs"
    if asset_references:
        monkeypatch.setattr("legal_skill_guard.learning.legal_namespace.asset_description_lexicon",
                            lambda: ("watch",))
    seen, observations = [], {}
    for case in range(1, 25):
        components = copy.deepcopy(COMPONENTS)
        if case == 19:
            components["solved_steps"] = "The Debtor may claim property exemptions under Illinois statutes."
        for family in ("EC", "EV"):
            seen.append({"case_id": case, "family": family, "components": components})
            observations[(case, family)] = {"case_id": case, "family": family,
                "score": record(family, 0.2 if case == 1 else 0.8)["score"],
                "parse_error": None, "parsed": {"answer": {"watch": []}},
                "raw_call_path": f"native/{case}_{family}.json"}
    failed_parent = observations[(21, "EV")]
    failed_parent["parse_error"] = "Incomplete native output: length"
    failed_parent["parsed"] = None
    failed_parent["score"] = {**record("EV", 0)["score"], "invalid_format": 1}
    current = [r for r in seen if r["case_id"] >= 21]
    replay = copy.deepcopy(list(observations.values()))
    for r in replay:
        if r["case_id"] == 20 and r["family"] == "EV":
            r["score"]["full_output_f1"] = 0.1  # Harm in the additional EV audit also counts.
    rejected = [{"accepted": False, "actual_replay": replay}]
    partial = candidate_feedback({"accepted": True, "candidate": [],
        "proposed_bank": [{"id": "uncommitted"}], "proposed_replay": replay,
        "accepted_legal_coordinates": ["EC:ARIZONA"]}, observations,
        {"batch": 1, "attempt": 1})
    assert partial["accepted"] and partial["partially_committed"]
    assert len(partial["feedback_witness_replay"]) == 8
    assert partial["full_proposed_replay_task_count"] == 48
    rejected.append(partial)
    selected, manifest = teacher_evidence_rows(current, seen, observations, rejected)
    ids = {r["case_id"] for r in selected}
    assert {21, 22, 23, 24}.issubset(ids)
    assert len(ids - {21, 22, 23, 24}) == 16
    assert {1, 19, 20}.issubset(ids)  # Parent failure, public context, and actual harm.
    assert manifest["full_seen_TRAIN_replay_and_acceptance_unchanged"]
    assert manifest["all_seen_source_ids"] == list(range(1, 25))
    assert len(seen) == len(replay) == 48  # Selection never mutates training/replay inputs.
    smaller = [r for r in seen if r["case_id"] <= 8]
    all_eight, _ = teacher_evidence_rows(smaller[-4:], smaller, observations, [])
    assert all_eight == smaller  # Small pilots retain all evidence and its order.

    study = Online.__new__(Online)
    study.cfg = {"execution_contract": ("direct_statutory_claims" if direct
                                         else "source_grounded_claim_operations"),
                 "grading_directory": "synthetic_labels_only", "library_token_hard_cap": 4096,
                 "skill_commit_policy": "task_local"}
    if asset_references:
        study.cfg["execution_contract_version"] = 14
    # Opaque target-tokenizer measurement, not the teacher's inferred token count.
    study.meter = SimpleNamespace(token_count=lambda **kwargs: 4008)
    study.bank = []
    study.prequential_empty = list(observations.values())
    study.prequential_frozen = list(observations.values())
    read_cases, native_read_cases = [], []
    model_trace = "untrusted emitted text " * 100 + "wrong premise from source model"
    failed_output = '{"assets":' + "repeated malformed fragment" * 100
    def synthetic_grade(path):
        if path.parent.name == "native":
            native_read_cases.append(int(path.stem.split("_")[0]))
            failed = path.stem == "21_EV"
            return {"calls": [{"request": {"max_tokens": 8192}, "response": {
                "id": path.stem, "usage": {"prompt_tokens": 20,
                    "completion_tokens": 8192 if failed else 100},
                "choices": [{"finish_reason": "length" if failed else "stop", "message": {
                    "reasoning_content": model_trace, "content": failed_output if failed else "{}"}}]}}]}
        read_cases.append(int(path.stem))
        return {"targets": {"EC": {"watch": []}, "EV": {"watch": []}}}
    monkeypatch.setattr("experiments.openexempt_online.read", synthetic_grade)
    body = study.teacher_body(current, seen, observations, rejected)
    if asset_references:
        assert any("asset_ref" in system for system in body["actual_actor_systems"].values())
        encoding = body["task_boundary"]["asset_reference_encoding"]
        assert encoding["case_local_IDs_reset_per_case"]
        assert encoding["public_description_only_literal_mentions_not_ownership_or_eligibility"]
        assert encoding["do_not_store_instance_asset_IDs_as_reusable_law_or_amount_answers"]
        assert all(";asset_mentions=1" in key for key in
                   body["actual_system_and_response_schema_by_public_context"])
        assert all(case["public_asset_reference_catalog"] == {"A001": "watch"}
                   for case in body["already_seen_training"])
    else:
        assert "asset_reference_encoding" not in body["task_boundary"]
        assert all("public_asset_reference_catalog" not in case
                   for case in body["already_seen_training"])
    if direct:
        for context in body["actual_system_and_response_schema_by_public_context"].values():
            if "EV" in context:
                schema = body["actual_response_schemas"][context["EV"]["response_schema_ref"]]
                assert "claim_value" in str(schema)
                assert "limit_expression" not in str(schema)
    for row in seen:
        key = "+".join(sorted(allowable_namespaces(row)))
        if asset_references:
            key += ";asset_mentions=1"
        reference = body["actual_system_and_response_schema_by_public_context"][key][row["family"]]
        messages, schema, _ = actor_payload(row, study.bank, grounded=True,
            direct_numeric=direct, asset_references=asset_references)
        assert body["actual_actor_systems"][reference["system_ref"]] == messages[0]["content"]
        assert body["actual_response_schemas"][reference["response_schema_ref"]] == schema
        skill_message = next((m["content"] for m in messages
                              if m["content"].startswith("Background reusable skills.")), None)
        if skill_message is None:
            assert reference["skill_message_ref"] is None
            assert reference["skill_message_position"] is None
        else:
            assert body["actual_actor_skill_messages"][reference["skill_message_ref"]] == skill_message
            assert reference["skill_message_position"] == ("before_case" if row["family"] == "EC" else "after_case")
    assert body["actor_visibility_contract"]["EV_also_decides_eligibility_not_only_numeric_amounts"]
    assert body["execution_teaching_contract"]["recurrent_failure_requires_instruction_reconsideration"]
    assert body["full_serialized_library_token_budget"]["actual_parent_tokens"] == 4008
    assert body["full_serialized_library_token_budget"]["net_growth_headroom"] == 88
    assert {r["source_case_id"] for r in body["already_seen_training"]} == ids
    assert set(read_cases) == ids
    assert set(native_read_cases) == ids  # Never load omitted or future native evidence.
    emitted_case = next(c for c in body["already_seen_training"]
                        if c["source_case_id"] == 21 and c["family"] == "EV")
    emitted = emitted_case["actual_parent_answer"]["source_model_emitted_evidence"]
    assert emitted["emitted_by_executor_unverified"] and emitted["finish_reason"] == "length"
    assert emitted["reasoning"]["text"] == model_trace[-1024:]
    assert emitted["reasoning"]["truncated_to_tail"]
    assert emitted["reasoning"]["characters"] == len(model_trace)
    assert not {"response_id", "canonical_call_sha256", "prompt_tokens", "completion_tokens"} & emitted.keys()
    preview = emitted["failed_native_final"]
    assert preview["head"] == failed_output[:256] and preview["tail"] == failed_output[-256:]
    assert preview["middle_omitted"] and preview["characters"] == len(failed_output)
    assert "source_model_emitted_evidence" not in emitted_case["actual_same_case_empty_answer"]
    assert "actual_same_case_frozen_initial_answer" not in emitted_case
    assert emitted_case["frozen_initial_answer_alias_of"] == "actual_same_case_empty_answer"
    assert emitted_case["actual_parent_answer"]["native_claim_feedback"]["invalid_response"]
    assert body["teacher_evidence_contract"] == TEACHER_EVIDENCE_CONTRACT
    feedback = body["rejected_candidate_feedback"][0]
    assert feedback["full_replay_task_count"] == 48
    assert len(feedback["actual_replay"]) == 40
    assert {r["case_id"] for r in feedback["actual_replay"]} == ids
    assert all("source_model_emitted_evidence" in r for r in feedback["actual_replay"])
    carried = body["rejected_candidate_feedback"][1]
    assert carried["accepted"] and carried["partially_committed"]
    assert carried["bounded_feedback_witness_task_count"] == 8
    assert carried["bounded_feedback_reference_task_count"] == 8
    for field in ("feedback_witness_replay", "feedback_reference_replay"):
        assert {r["case_id"] for r in carried[field]} <= ids
    assert all("source_model_emitted_evidence" in r for r in carried["feedback_witness_replay"])
    for ref in carried["feedback_reference_replay"]:
        assert ref["reference_is_this_request_parent"]
        assert ref["record_sha256"] == canonical_json_sha256(observations[(ref["case_id"], ref["family"])])
        assert "source_model_emitted_evidence" not in ref
    future = copy.deepcopy(replay[:1])
    future[0]["case_id"] = 99
    with pytest.raises(ValueError, match="already-seen TRAIN"):
        candidate_feedback({"accepted": False, "actual_replay": future}, observations, {})

    study.prequential_frozen = copy.deepcopy(study.prequential_frozen)
    distinct = next(r for r in study.prequential_frozen if r["case_id"] == 22 and r["family"] == "EV")
    distinct["bank_sha256"] = "distinct-initial-library"
    again = study.teacher_body(current, seen, observations, rejected)
    distinct_case = next(c for c in again["already_seen_training"]
                         if c["source_case_id"] == 22 and c["family"] == "EV")
    assert "actual_same_case_frozen_initial_answer" in distinct_case
    assert "frozen_initial_answer_alias_of" not in distinct_case

    study.bank = [{"id": "task-visibility", "hypothesis_ids": ["EC", "EV"],
        "guidance": {"jurisdiction": "ALL", "operators": [], "by_task": [
            {"tasks": ["EC"], "when": "public EC condition", "procedure": "EC_ONLY_INSTRUCTION",
             "avoid_when": "unsupported EC condition"},
            {"tasks": ["EV"], "when": "public EV condition", "procedure": "EV_ONLY_INSTRUCTION",
             "avoid_when": "unsupported EV condition"}]}}]
    projected = study.teacher_body(current, seen, observations, rejected)
    assert len(projected["actual_actor_skill_messages"]) == 2
    for context in projected["actual_system_and_response_schema_by_public_context"].values():
        for family, reference in context.items():
            message = projected["actual_actor_skill_messages"][reference["skill_message_ref"]]
            assert family + "_ONLY_INSTRUCTION" in message
            assert ({"EC": "EV", "EV": "EC"}[family] + "_ONLY_INSTRUCTION") not in message
            assert reference["skill_message_position"] == ("before_case" if family == "EC" else "after_case")
    for family in ("EC", "EV"):
        targeted = study.teacher_body(current, seen, observations, [], teaching_task=family)
        assert targeted["teaching_task"] == family
        assert targeted["training_evidence_manifest"]["other_task_predictions_and_targets_not_supplied"]
        assert set(targeted["task_contracts"]) == {family}
        assert {c["family"] for c in targeted["already_seen_training"]} == {family}
        assert len(targeted["actual_actor_skill_messages"]) == 1
        assert all(set(context) == {family} for context in
                   targeted["actual_system_and_response_schema_by_public_context"].values())
        assert {r["source_case_id"] for r in targeted["already_seen_training"]} >= {21, 22, 23, 24}
    focused_feedback = candidate_feedback({"accepted": False, "teaching_task": "EV",
        "actual_replay": replay}, observations, {"batch": 1, "attempt": 2})
    assert focused_feedback["teaching_task"] == "EV"
    assert focused_feedback["full_proposed_replay_task_count"] == 24
    assert len(focused_feedback["feedback_witness_replay"]) == 8
    assert all(r["family"] == "EV" for r in focused_feedback["feedback_witness_replay"])
    if direct:
        from experiments.openexempt_online import CONSOLIDATION_PHASE

        study.cfg.update({"training_phase": CONSOLIDATION_PHASE, "batch_source_cases": 4})
        consolidated = study.teacher_body(seen, seen, observations, [], teaching_task="EV")
        manifest = consolidated["training_evidence_manifest"]
        scope = manifest["consolidation_scope"]
        assert scope["all_optimization_source_ids"] == list(range(1, 25))
        assert len(scope["communication_focus_source_ids"]) == 4
        assert len(consolidated["already_seen_training"]) <= 4 + 16
        assert len(consolidated["already_seen_training"]) < 24
        assert {c["family"] for c in consolidated["already_seen_training"]} == {"EV"}
        assert scope["original_gate_applied_to_all_seen_sources_together"]
        assert scope["all_sources_previously_observed_TRAIN"]
        assert scope["no_new_cases_or_TEST_labels"]
        assert len(seen) == 48 and len(observations) == 48
        study.cfg["teacher_update_policy"] = "joint_fixed_steps"
        joint = study.teacher_body(seen, seen, observations, [])
        joint_manifest = joint["training_evidence_manifest"]
        assert joint["teaching_task"] is None
        assert not joint["task_projection_update_contract"]["enabled"]
        assert {case["family"] for case in joint["already_seen_training"]} == {"EC", "EV"}
        assert len(joint["already_seen_training"]) <= 4 + 16
        assert joint_manifest["consolidation_scope"]["all_optimization_source_ids"] == list(range(1, 25))
        assert len(joint_manifest["consolidation_scope"]["communication_focus_source_ids"]) == 2
        assert joint_manifest["matched_task_record_budget"]["historical_source_limit"] == 8
        assert joint_manifest["matched_task_record_budget"]["limit"] == 20
        with pytest.raises(ValueError, match="silently project"):
            study.teacher_body(seen, seen, observations, [], teaching_task="EC")


@pytest.mark.parametrize("family", ["EC", "EV"])
def test_task_coordinate_edit_preserves_other_actor_projection(family):
    from experiments.openexempt_online import validate_task_projection_edit

    parent = [{"id": "one-book", "hypothesis_ids": ["EC", "EV"], "guidance": {
        "by_task": [{"tasks": ["EC", "EV"], "when": "public condition",
                     "procedure": "original rule", "avoid_when": "unsupported condition"}],
        "operators": [], "jurisdiction": "ARIZONA"}}]
    candidate = copy.deepcopy(parent)
    blocks = candidate[0]["guidance"]["by_task"]
    blocks[:] = [{**copy.deepcopy(blocks[0]), "tasks": [f],
                  "procedure": "repaired rule" if f == family else "original rule"}
                 for f in ("EC", "EV")]
    audit = validate_task_projection_edit(parent, candidate, family)
    assert audit["other_task_projection_unchanged"]
    wrong = copy.deepcopy(candidate)
    other = "EV" if family == "EC" else "EC"
    next(b for b in wrong[0]["guidance"]["by_task"] if other in b["tasks"])["procedure"] = "unrelated rewrite"
    with pytest.raises(ValueError, match="unselected actor projection"):
        validate_task_projection_edit(parent, wrong, family)
    with pytest.raises(ValueError, match="Declare one original public task"):
        validate_task_projection_edit(parent, candidate, "inferred_route")


@pytest.mark.parametrize("family", ["EC", "EV"])
def test_native_claim_feedback_preserves_original_matching_and_never_repairs_answer(family):
    az, il, fed = "Ariz. Rev. Stat. § 33-1123", "735 Ill. Comp. Stat. 5/12-1001(b)", "11 U.S.C. § 522(d)(5)"
    if family == "EC":
        target = {"watch": [az, il], "bowl": []}
        answer = {"watch": [az, az, fed], "bowl": [il], "unlisted satellite": [az]}
        expected = {"correct": 1, "missing": 1, "incorrect_value": 0, "extra_or_duplicate": 3}
    else:
        target = {"watch": [{"citation": citation, "claim_value": amount}
                            for citation, amount in [(az, 100), (il, 20), (fed, 50)]], "bowl": []}
        answer = {"watch": [{"citation": citation, "claim_value": amount}
                            for citation, amount in [(az, 50), (il, 10), (il, 20), (il, 20),
                                                     ("Or. Rev. Stat. § 18.362", 10)]],
                  "bowl": [{"citation": az, "claim_value": 20}],
                  "unlisted satellite": [{"citation": az, "claim_value": 30}]}
        expected = {"correct": 1, "missing": 1, "incorrect_value": 1, "extra_or_duplicate": 4}
    row = {"case_id": 1, "family": family}
    record_value = {**row, "parsed": {"answer": answer}, "parse_error": None,
                    "score": evaluate(row, answer, target)}
    unchanged = copy.deepcopy((record_value, target))
    feedback = native_claim_feedback(record_value, target)
    assert all(feedback[k] == v for k, v in expected.items())
    assert feedback["correct"] == record_value["score"]["full_output_claim_tp"]
    assert feedback["missing"] + feedback["incorrect_value"] == record_value["score"]["full_output_claim_fn"]
    assert feedback["extra_or_duplicate"] + feedback["incorrect_value_predictions"] == record_value["score"]["full_output_claim_fp"]
    assert (record_value, target) == unchanged
    if family == "EV":
        mismatch = next(e for e in feedback["errors"] if e["kind"] == "incorrect_value")
        assert mismatch["expected_value"] == 100 and mismatch["observed_values"] == [50]
        assert feedback["incorrect_value_predictions"] == 2
    invalid = {**record_value, "parse_error": "actual malformed native output", "parsed": None}
    assert native_claim_feedback(invalid, target)["invalid_response"]
    inconsistent = copy.deepcopy(record_value)
    inconsistent["score"]["full_output_claim_fn"] += 1
    with pytest.raises(ValueError, match="disagrees"):
        native_claim_feedback(inconsistent, target)


@pytest.mark.parametrize("amount,correct", [(100, True), (96, True), (95, False)])
def test_native_claim_feedback_uses_original_five_percent_epsilon_rule(amount, correct):
    citation = "Ariz. Rev. Stat. § 33-1123"
    target = {"watch": [{"citation": citation, "claim_value": 100}]}
    answer = {"watch": [{"citation": citation, "claim_value": amount}]}
    row = {"case_id": 1, "family": "EV"}
    result = native_claim_feedback({**row, "parse_error": None, "parsed": {"answer": answer},
                                   "score": evaluate(row, answer, target)}, target)
    assert result["correct"] == int(correct)
    assert result["incorrect_value"] == int(not correct)


def test_strong_direct_numeric_empty_is_not_a_program_or_host_repaired_answer(tmp_path, monkeypatch):
    from jsonschema import ValidationError, validate

    from experiments.openexempt_online import DIRECT_GUIDANCE

    row = {"case_id": 1, "source_key": "synthetic", "family": "EV", "prompt": "public",
           "solution": "SECRET", "components": copy.deepcopy(COMPONENTS)}
    messages, schema, supplied = actor_payload(row, [], direct_numeric=True)
    assert not supplied and "SECRET" not in str(messages)
    assert "limit_expression" not in str(schema) and "asset_value" not in str(schema)
    assert all(row["components"][key] in messages[-1]["content"] for key in ACTIVE_CASE_FIELDS)
    numeric = {"unsupported original name": [{"citation_ref":
        "Ariz. Rev. Stat. section 33-1123", "claim_value": 999}]}
    validate(numeric, schema)
    ec = {**row, "family": "EC"}
    assert actor_payload(ec, [])[:2] == actor_payload(ec, [], direct_numeric=True)[:2]
    bank = [{"id": "az", "hypothesis_ids": ["EC", "EV"],
             "guidance": guidance("Check the statutory eligibility condition", "ARIZONA")}]
    skilled_messages, skilled_schema, _ = actor_payload(row, bank, direct_numeric=True)
    assert skilled_schema == schema and skilled_messages[0] == messages[0]
    assert skilled_messages[1] == messages[-1]
    assert "Check the statutory eligibility condition" in str(skilled_messages)
    assert "operators" not in str(skilled_messages)
    bad_bank = copy.deepcopy(bank)
    bad_bank[0]["guidance"]["operators"] = [{"id": "cap",
        "citation": "Ariz. Rev. Stat. § 33-1123", "limit_expression": "min(V,30)"}]
    with pytest.raises(ValueError, match="cannot publish numerical programs"):
        actor_payload(row, bad_bank, direct_numeric=True)
    with pytest.raises(ValidationError):
        validate(bad_bank[0]["guidance"], DIRECT_GUIDANCE)
    monkeypatch.setattr("experiments.openexempt_online.ROOT", tmp_path)
    study = Online.__new__(Online)
    study.cfg = {"execution_contract": "source_grounded_claim_operations",
                 "generation": {"seed": 45, "max_tokens": 100}}
    study.out, study.request_cache, study.reuse_events, study.native = tmp_path, {}, [], []
    study.check = lambda: None
    study.progress = lambda *a, **k: None
    study.call = lambda *args, **kwargs: {"content": json.dumps(numeric), "finish_reason": "stop"}
    result = study.answer(row, [], "direct", "empty_direct_numeric")
    assert result["parsed"]["answer"] == {"unsupported original name": [
        {"citation": "Ariz. Rev. Stat. § 33-1123", "claim_value": 999}]}
    assert result["native_program"] is None and result["execution_receipt"] is None
    study.cfg["execution_contract"] = "direct_statutory_claims"
    monkeypatch.setattr("experiments.openexempt_online.execute_claims",
                        lambda *a, **k: pytest.fail("Direct answers must not execute programs"))
    learned = study.answer(row, bank, "learned_direct", "skills")
    assert learned["parsed"] == result["parsed"]
    assert learned["native_program"] is None and learned["execution_receipt"] is None
    assert learned["delivered_skill_ids"] == ["az"]


@pytest.mark.parametrize("accepted_task", ["EC", "EV"])
def test_task_commit_preserves_the_other_tasks_exact_native_wire(accepted_task):
    parent = [{"id": "az", "hypothesis_ids": ["EC", "EV"],
               "guidance": guidance("Original shared instructions", "ARIZONA")}]
    proposed = copy.deepcopy(parent)
    proposed[0]["guidance"]["by_task"][0]["procedure"] = "Changed shared instructions"
    proposed[0]["guidance"]["operators"] = [{"id": "cap",
        "citation": "Ariz. Rev. Stat. § 33-1123", "limit_expression": "min(V,30)"}]
    actual = compose_task_edits(parent, proposed, [accepted_task])
    for family in ("EC", "EV"):
        row = {"family": family, "components": copy.deepcopy(COMPONENTS)}
        expected = proposed if family == accepted_task else parent
        assert task_view(actual, family) == task_view(expected, family)
        assert actor_payload(row, actual) == actor_payload(row, expected)
    assert len(actual[0]["guidance"]["by_task"]) == 2


def test_task_composition_handles_real_crud_without_changing_unaccepted_ids_or_order():
    from legal_skill_guard.learning.publication import apply_differential_publication
    from legal_skill_guard.learning.task_scoped_skills import SCOPED_GUIDANCE_SCHEMA

    parent = [{"id": name, "hypothesis_ids": ["EC", "EV"],
               "guidance": guidance(name)} for name in ("z", "a", "d")]
    merged = {"id": "m", "hypothesis_ids": ["EC", "EV"], "guidance": guidance("merged")}
    created = {"id": "c", "hypothesis_ids": ["EV"],
               "guidance": guidance("created", tasks=("EV",))}
    delta = {"noop_reason": None, "operations": [
        {"operation": "MERGE", "target_ids": ["z", "a"], "skill": merged,
         "source_case_ids": [1], "rationale": "generic consolidation"},
        {"operation": "DELETE", "target_ids": ["d"], "skill": None,
         "source_case_ids": [1], "rationale": "generic deletion"},
        {"operation": "CREATE", "target_ids": [], "skill": created,
         "source_case_ids": [1], "rationale": "generic creation"}]}
    proposed = apply_differential_publication(parent, delta, ("EC", "EV"), [1],
                                             guidance_schema=SCOPED_GUIDANCE_SCHEMA)
    actual = compose_task_edits(parent, proposed, ["EV"])
    assert [s["id"] for s in task_view(actual, "EC")] == ["a", "d", "z"]
    assert [s["id"] for s in task_view(actual, "EV")] == ["c", "m"]
    assert task_view(actual, "EC") == task_view(parent, "EC")
    assert task_view(actual, "EV") == task_view(proposed, "EV")
    coordinates = legal_edit_coordinates(parent, proposed, scope_rows())
    accepted = [c["id"] for c in coordinates if c["task"] == "EV"]
    assert compose_legal_edits(parent, proposed, coordinates, accepted) == actual


def test_scoped_guidance_has_no_missing_task_default_or_conflicting_jurisdiction():
    parent = [{"id": "s", "hypothesis_ids": ["EC", "EV"], "guidance": guidance("old")}]
    missing = copy.deepcopy(parent)
    missing[0]["guidance"]["by_task"][0]["tasks"] = ["EV"]
    with pytest.raises(ValueError, match="Exactly one"):
        validate_scoped_bank(missing)
    repeated = copy.deepcopy(parent)
    repeated[0]["guidance"]["by_task"].append(copy.deepcopy(repeated[0]["guidance"]["by_task"][0]))
    with pytest.raises(ValueError, match="Exactly one"):
        validate_scoped_bank(repeated)
    conflict = copy.deepcopy(parent)
    conflict[0]["guidance"]["jurisdiction"] = "ARIZONA"
    with pytest.raises(ValueError, match="conflicting legal jurisdictions"):
        compose_task_edits(parent, conflict, ["EV"])


def test_blind_prior_conversion_is_explicit_lossless_and_not_a_runtime_fallback():
    from jsonschema import ValidationError

    legacy = [{"id": "s", "hypothesis_ids": ["EC", "EV"], "guidance": {
        "when": "public condition", "procedure": "unchanged blind law knowledge",
        "avoid_when": "other", "operators": [], "jurisdiction": "ALL"}}]
    converted = import_blind_prior(legacy)
    assert converted[0]["guidance"]["by_task"][0]["procedure"] == legacy[0]["guidance"]["procedure"]
    assert "by_task" not in legacy[0]["guidance"]
    with pytest.raises(ValueError, match="legacy blind prior"):
        import_blind_prior(converted)
    with pytest.raises(ValidationError):
        actor_payload({"family": "EC", "components": copy.deepcopy(COMPONENTS)}, legacy)


def test_task_admission_retains_original_family_and_full_output_protection():
    parent = [record("EC", 0.8), record("EV", 0.5)]
    proposed = [record("EC", 0.6), record("EV", 0.7)]
    decisions = task_admission(parent, proposed, parent, parent)
    assert not acceptance(parent, proposed, parent, parent)["accepted"]
    assert not decisions["EC"]["accepted"] and decisions["EV"]["accepted"]
    actual = [parent[0], proposed[1]]
    assert acceptance(parent, actual, parent, parent)["accepted"]
    unsafe = copy.deepcopy(proposed)
    unsafe[1]["score"]["full_output_f1"] = 0.4
    assert not task_admission(parent, unsafe, [], [])["EV"]["accepted"]
    old_harm = [record("EC", 0.8), record("EV", 0.4)]
    assert not task_admission(parent, proposed, parent, old_harm)["EV"]["accepted"]
    assert not any(d["accepted"] for d in task_admission(parent, parent, [], []).values())


@pytest.mark.parametrize("policy", ["task_local", "whole_bank", "legal_scope"])
@pytest.mark.parametrize("direct", [False, True])
def test_full_update_task_local_vs_whole_bank_differs_only_in_commit_policy(
        tmp_path, monkeypatch, policy, direct):
    from types import SimpleNamespace

    from legal_skill_guard.utils.hashing import canonical_json_sha256

    monkeypatch.setattr("experiments.openexempt_online.ROOT", tmp_path)
    study = Online.__new__(Online)
    study.cfg = {"execution_contract": ("direct_statutory_claims" if direct
                                         else "source_grounded_claim_operations"),
                 "generation": {"seed": 45, "max_tokens": 100},
                 "max_candidate_attempts": 1, "library_token_hard_cap": 4096,
                 "skill_commit_policy": policy, "teacher_update_policy": "joint_bounded_refinement"}
    study._dispatch = PhaseDispatch(study.cfg)
    study.current_batch, study.latest = 1, {}
    study.out, study.native, study.request_cache, study.reuse_events = tmp_path, [], {}, []
    study.meter = SimpleNamespace(token_count=lambda **kwargs: 300)
    study.check, study.progress = lambda: None, lambda *a, **k: None
    study.rows = [{"case_id": 1, "source_key": "synthetic", "family": family,
                   "prompt": "public original", "components": copy.deepcopy(COMPONENTS)}
                  for family in ("EC", "EV")]
    study.bank = [{"id": "az", "hypothesis_ids": ["EC", "EV"],
                   "guidance": guidance("original procedure", "ARIZONA")}]
    if not direct:
        study.bank[0]["guidance"]["operators"] = [{"id": "cap",
            "citation": "Ariz. Rev. Stat. § 33-1123", "limit_expression": "min(V,30)"}]
    proposed = copy.deepcopy(study.bank)
    proposed[0]["guidance"]["by_task"][0]["procedure"] = "new procedure"
    if not direct:
        proposed[0]["guidance"]["operators"][0]["limit_expression"] = "min(V,15)"
    ref = "Ariz. Rev. Stat. section 33-1123"

    def call(dest, messages, schema, max_tokens, metadata):
        study.native.append(metadata)
        if metadata["family"] == "EC":
            answer = {} if "new procedure" in str(messages) else {"watch": [ref]}
        elif direct:
            answer = {"watch": [{"citation_ref": ref,
                                  "claim_value": 15 if "new procedure" in str(messages) else 30}]}
        else:
            answer = {"assets": [{"asset_name": "watch", "asset_value": 40,
                       "claims": [{"citation_ref": ref, "limit_expression": None}]}]}
        return {"content": json.dumps(answer), "finish_reason": "stop"}

    def grade(records):
        for value in records:
            target = ({"watch": ["Ariz. Rev. Stat. § 33-1123"]} if value["family"] == "EC"
                      else {"watch": [{"citation": "Ariz. Rev. Stat. § 33-1123", "claim_value": 15}]})
            value["score"] = evaluate(value, value["parsed"]["answer"], target)
        return records

    study.call, study.grade = call, grade
    study.teacher_body = lambda *args: {"training_evidence_manifest": {"selected_source_ids": [1]}}
    study.teacher_call = lambda *args: diagnosed_test_reply(study, {"noop_reason": None, "operations": [{
        "operation": "UPDATE", "target_ids": ["az"], "skill": proposed[0],
        "source_case_ids": [1], "rationale": "synthetic task conflict"}]})
    parent = study.grade([study.answer(r, study.bank, "parent", "skills") for r in study.rows])
    original = copy.deepcopy(study.bank)
    publication = study.update(study.rows, study.rows, parent)
    decision = publication["training_decisions"][0]
    assert decision["skill_commit_policy"] == publication["skill_commit_policy"] == policy
    assert not decision["proposed_whole_bank_acceptance"]["accepted"]
    assert len(study.native) == 4  # Parent2 + proposed2; composed2 are raw aliases only.
    if policy == "whole_bank":
        assert not decision["accepted"] and not decision["accepted_tasks"]
        assert decision["reason"] == "whole_proposal_failed_original_full_gate"
        assert study.bank == original
        assert publication["parent_bank_sha256"] == publication["bank_sha256"]
        return
    assert decision["accepted"] and decision["accepted_tasks"] == ["EV"]
    assert task_view(study.bank, "EC") == task_view(original, "EC")
    assert task_view(study.bank, "EV") == task_view(proposed, "EV")
    assert study.latest[(1, "EC")]["parsed"] == parent[0]["parsed"]
    ev = study.latest[(1, "EV")]
    assert ev["parsed"]["answer"]["watch"][0]["claim_value"] == 15
    if direct:
        assert ev["execution_receipt"] is None and ev["native_program"] is None
    else:
        assert ev["execution_receipt"]["execution_bank_sha256"] == canonical_json_sha256(study.bank)
    assert decision["current_family_nonregression"] and decision["current_full_output_nonregression"]
    study.request_cache.clear()
    with pytest.raises(ValueError, match="changed an evaluated native wire"):
        study.composed_replay(original, proposed, ["EV"], study.rows, "missing")
    study.meter = SimpleNamespace(token_count=lambda **kwargs: 4097)
    with pytest.raises(ValueError, match="exceeds total token cap"):
        study.composed_replay(original, proposed, ["EV"], study.rows, "oversized")
    assert len(study.native) == 4


def scope_rows():
    return [{"case_id": index, "family": family, "components": {
        **copy.deepcopy(COMPONENTS),
        "solved_steps": f"The Debtor may claim property exemptions under {namespace} statutes."}}
        for index, namespace in [(1, "Arizona"), (2, "Illinois")] for family in ("EC", "EV")]


def test_legal_coordinates_use_public_coviews_moves_and_task_local_ALL_changes():
    parent = [{"id": name, "hypothesis_ids": ["EC", "EV"], "guidance": guidance("old", ns)}
              for name, ns in [("shared", "ALL"), ("az", "ARIZONA"), ("il", "ILLINOIS")]]
    proposed = copy.deepcopy(parent)
    proposed[0]["guidance"]["by_task"] = [
        {"tasks": ["EC"], "when": "public condition", "procedure": "new", "avoid_when": "other"},
        {"tasks": ["EV"], "when": "public condition", "procedure": "old", "avoid_when": "other"}]
    coordinates = legal_edit_coordinates(parent, proposed, scope_rows())
    assert {c["id"] for c in coordinates} == {
        "EC:ALL+ARIZONA+ILLINOIS", "EV:ARIZONA", "EV:ILLINOIS"}
    moved = copy.deepcopy(parent)
    moved[1]["guidance"]["jurisdiction"] = "ILLINOIS"
    assert {c["id"] for c in legal_edit_coordinates(parent, moved, scope_rows())} == {
        "EC:ARIZONA+ILLINOIS", "EV:ARIZONA+ILLINOIS"}
    together = copy.deepcopy(scope_rows())
    together[0]["components"]["solved_steps"] = (
        "The Debtor may claim property exemptions under Arizona and Illinois statutes.")
    assert any(c["id"] == "EC:ARIZONA+ILLINOIS"
               for c in legal_edit_coordinates(parent, parent, together))


def test_legal_composition_keeps_one_bank_and_each_disjoint_actual_native_wire():
    parent = [{"id": name, "hypothesis_ids": ["EC", "EV"], "guidance": guidance("old", ns)}
              for name, ns in [("shared", "ALL"), ("az", "ARIZONA"), ("il", "ILLINOIS")]]
    proposed = copy.deepcopy(parent)
    for skill in proposed[1:]:
        skill["guidance"]["by_task"][0]["procedure"] = "new"
    coordinates = legal_edit_coordinates(parent, proposed, scope_rows())
    actual = compose_legal_edits(parent, proposed, coordinates, ["EC:ILLINOIS", "EV:ILLINOIS"])
    for row in scope_rows():
        expected = proposed if row["case_id"] == 2 else parent
        assert actor_payload(row, actual) == actor_payload(row, expected)
    assert next(s for s in actual if s["id"] == "az") == parent[1]
    with pytest.raises(ValueError, match="nonempty set"):
        compose_legal_edits(parent, proposed, coordinates, ["EC:INVENTED"])
    with pytest.raises(ValueError, match="overlap"):
        compose_legal_edits(parent, proposed, coordinates + [coordinates[0]], [coordinates[0]["id"]])


def test_legal_scope_admission_keeps_all_sources_prior_and_full_output_protection():
    coordinates = [{"id": "EV:ILLINOIS", "task": "EV", "jurisdictions": ["ILLINOIS"],
                    "source_case_ids": [1, 2]},
                   {"id": "EC:OREGON", "task": "EC", "jurisdictions": ["OREGON"],
                    "source_case_ids": []}]
    parent = [{**record("EV", score), "case_id": index} for index, score in [(1, 0.4), (2, 0.7)]]
    proposed = [{**record("EV", score), "case_id": index} for index, score in [(1, 0.8), (2, 0.6)]]
    result = legal_scope_admission(coordinates, parent, proposed, [], [])
    assert result["EV:ILLINOIS"]["accepted"] and result["EV:ILLINOIS"]["current_tasks"] == 2
    assert result["EC:OREGON"]["reason"] == "no_current_sources"
    unsafe = copy.deepcopy(proposed)
    unsafe[0]["score"]["full_output_f1"] = 0
    assert not legal_scope_admission(coordinates, parent, unsafe, [], [])["EV:ILLINOIS"]["accepted"]
    assert not legal_scope_admission(coordinates, parent, proposed, proposed, parent)["EV:ILLINOIS"]["accepted"]
    with pytest.raises(ValueError, match="fully paired"):
        legal_scope_admission(coordinates, parent, proposed[:1], [], [])


@pytest.mark.parametrize("policy", ["legal_scope", "adaptive_legal"])
def test_full_legal_scope_update_retains_unrelated_law_without_extra_generation(tmp_path, monkeypatch, policy):
    from types import SimpleNamespace
    from legal_skill_guard.learning.phase_dispatch import PhaseDispatch

    monkeypatch.setattr("experiments.openexempt_online.ROOT", tmp_path)
    study = Online.__new__(Online)
    study.cfg = {"execution_contract": "source_grounded_claim_operations",
                 "generation": {"seed": 45, "max_tokens": 100},
                 "max_candidate_attempts": 1, "library_token_hard_cap": 4096,
                 "skill_commit_policy": policy, "teacher_update_policy": "joint_bounded_refinement",
                 "adaptive_commit_objective": "seen_source_min_family_gain_then_mean_v1"}
    study._dispatch = PhaseDispatch({})
    study.current_batch, study.latest = 1, {}
    study.out, study.native, study.request_cache, study.reuse_events = tmp_path, [], {}, []
    study.meter = SimpleNamespace(token_count=lambda **kwargs: 300)
    study.check, study.progress = lambda: None, lambda *a, **k: None
    study.rows = [{**r, "source_key": f"fixture{r['case_id']}", "prompt": "public original"}
                  for r in scope_rows()]
    citations = {1: "Ariz. Rev. Stat. § 33-1123", 2: "735 Ill. Comp. Stat. 5/12-1001(b)"}
    study.bank = [{"id": sid, "hypothesis_ids": ["EC", "EV"],
                   "guidance": guidance("original procedure", ns)}
                  for sid, ns in [("az", "ARIZONA"), ("il", "ILLINOIS")]]
    for index, skill in enumerate(study.bank, 1):
        skill["guidance"]["operators"] = [{"id": "cap", "citation": citations[index],
                                             "limit_expression": "min(V,30)"}]
    original = copy.deepcopy(study.bank)
    proposed = copy.deepcopy(study.bank)
    for skill in proposed:
        skill["guidance"]["by_task"][0]["procedure"] = "new procedure"
        skill["guidance"]["operators"][0]["limit_expression"] = "min(V,15)"

    def call(dest, messages, schema, max_tokens, metadata):
        study.native.append(metadata)
        case_id = metadata["document_id"]
        reference = citations[case_id].replace("§", "section")
        if metadata["family"] == "EC":
            right = ("new procedure" in str(messages)) == (case_id == 2)
            answer = {"watch": [reference]} if right else {}
        else:
            answer = {"assets": [{"asset_name": "watch", "asset_value": 40,
                       "claims": [{"citation_ref": reference, "limit_expression": None}]}]}
        return {"content": json.dumps(answer), "finish_reason": "stop"}

    def grade(records):
        for value in records:
            case_id = value["case_id"]
            target = ({"watch": [citations[case_id]]} if value["family"] == "EC" else
                      {"watch": [{"citation": citations[case_id],
                                  "claim_value": 30 if case_id == 1 else 15}]})
            value["score"] = evaluate(value, value["parsed"]["answer"], target)
        return records

    study.call, study.grade = call, grade
    study.teacher_body = lambda *args: {"training_evidence_manifest": {"selected_source_ids": [1, 2]}}
    study.teacher_call = lambda *args: diagnosed_test_reply(study, {"noop_reason": None, "operations": [{
        "operation": "UPDATE", "target_ids": [s["id"]], "skill": s,
        "source_case_ids": [1, 2], "rationale": "synthetic public-scope interference"} for s in proposed]})
    parent = study.grade([study.answer(r, study.bank, "parent", "skills") for r in study.rows])
    publication = study.update(study.rows, study.rows, parent)
    decision = publication["training_decisions"][0]
    assert decision["accepted"] and not decision["proposed_whole_bank_acceptance"]["accepted"]
    assert decision["accepted_legal_coordinates"] == ["EC:ILLINOIS", "EV:ILLINOIS"]
    assert len(study.native) == 8  # Parent4 + proposal4; composed4 only exact-wire reexecution.
    assert next(s for s in study.bank if s["id"] == "az") == original[0]
    assert decision["candidate_current"]["EC"]["f1"] == 1
    assert decision["candidate_current"]["EV"]["f1"] == 1


@pytest.mark.parametrize("policy", ["legal_scope", "adaptive_legal"])
def test_adaptive_commit_can_keep_a_valid_joint_repair_without_local_gate_cherrypicking(
        tmp_path, monkeypatch, policy):
    from types import SimpleNamespace
    from legal_skill_guard.learning.phase_dispatch import PhaseDispatch
    from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

    monkeypatch.setattr("experiments.openexempt_online.ROOT", tmp_path)
    study = Online.__new__(Online)
    study.cfg = {"execution_contract": "direct_statutory_claims",
        "max_candidate_attempts": 1, "library_token_hard_cap": 4096,
        "skill_commit_policy": policy, "teacher_update_policy": "joint_bounded_refinement",
        "adaptive_commit_objective": "seen_source_min_family_gain_then_mean_v1"}
    study._dispatch = PhaseDispatch({})
    study.out, study.current_batch = tmp_path, 2
    study.meter = SimpleNamespace(token_count=lambda **kwargs: 100)
    study.bank = [{"id": sid, "hypothesis_ids": ["EC", "EV"],
                   "guidance": guidance("old", namespace)}
                  for sid, namespace in [("az", "ARIZONA"), ("il", "ILLINOIS")]]
    parent_bank = copy.deepcopy(study.bank)
    proposed = copy.deepcopy(study.bank)
    for skill in proposed:skill["guidance"]["by_task"][0]["procedure"] = "new"
    rows = [{**r, "case_id": r["case_id"] + offset}
            for offset in (0, 2) for r in scope_rows()]
    calls = []

    def answer(row, bank, *args):
        calls.append((row["case_id"], row["family"]))
        changed = bank[0]["guidance"]["by_task"][0]["procedure"] == "new"
        baseline = {1: .2, 2: .8, 3: .8, 4: .2}
        revised = {1: .8, 2: .7, 3: .7, 4: .8}
        value = (revised if changed else baseline)[row["case_id"]] if row["family"] == "EC" else .5
        return {**record(row["family"], value), "case_id": row["case_id"],
                "bank_sha256": csha(bank)}

    study.answer, study.grade = answer, lambda records: records
    parent = [answer(r, study.bank) for r in rows]
    study.latest = {(r["case_id"], r["family"]): r for r in parent if r["case_id"] <= 2}
    current = [r for r in rows if r["case_id"] > 2]
    study.teacher_body = lambda *args: {"training_evidence_manifest": {"selected_source_ids": [1, 2, 3, 4]}}
    study.teacher_call = lambda *args: diagnosed_test_reply(study, {"noop_reason": None, "operations": [
        {"operation": "UPDATE", "target_ids": [s["id"]], "skill": s,
         "source_case_ids": [1, 2, 3, 4], "rationale": "Synthetic complementary TRAIN changes"}
        for s in proposed]})
    publication = study.update(current, rows, [r for r in parent if r["case_id"] > 2])
    decision = publication["training_decisions"][0]
    assert decision["proposed_whole_bank_acceptance"]["accepted"]
    assert not any(g["accepted"] for g in decision["legal_scope_admission"].values())
    assert len(calls) == 16  # Eight parent and eight proposed observations, no extra answers.
    assert decision["accepted"] == (policy == "adaptive_legal")
    assert study.bank == (proposed if policy == "adaptive_legal" else parent_bank)
    if policy == "adaptive_legal":
        assert decision["adaptive_commit_selection"]["selected"] == "joint"
        assert decision["proposal_fully_committed"]
        assert not decision["accepted_legal_coordinates"]  # Never claim that failed local gates passed.


@pytest.mark.parametrize("policy", ["whole_bank", "legal_scope", "adaptive_legal"])
@pytest.mark.parametrize("teacher_policy", ["joint_bounded_refinement", "joint_fixed_steps"])
@pytest.mark.parametrize("first_noop", [False, True])
def test_joint_teacher_opportunities_obey_declared_early_stop_or_fixed_steps(
        tmp_path, monkeypatch, policy, teacher_policy, first_noop):
    from types import SimpleNamespace
    from legal_skill_guard.learning.phase_dispatch import PhaseDispatch

    monkeypatch.setattr("experiments.openexempt_online.ROOT", tmp_path)
    monkeypatch.setattr("legal_skill_guard.learning.legal_namespace.asset_description_lexicon",
                        lambda: ("watch",))
    study = Online.__new__(Online)
    study.cfg = {"execution_contract": "direct_statutory_claims",
        "execution_contract_version": 14,
        "candidate_feedback_policy": "carry_partial_and_refine",
        "generation": {"seed": 45, "max_tokens": 100}, "max_candidate_attempts": 2,
        "library_token_hard_cap": 4096, "skill_commit_policy": policy,
        "teacher_update_policy": teacher_policy,
        "adaptive_commit_objective": "seen_source_min_family_gain_then_mean_v1"}
    study._dispatch = PhaseDispatch({})
    study.current_batch, study.latest = 1, {}
    study.out, study.native, study.request_cache, study.reuse_events = tmp_path, [], {}, []
    study.meter = SimpleNamespace(token_count=lambda **kwargs: 300)
    study.check, study.progress = lambda: None, lambda *a, **k: None
    study.rows = [{**row, "source_key": f"fixture{row['case_id']}", "prompt": "public original"}
                  for row in scope_rows()]
    study.bank = [{"id": sid, "hypothesis_ids": ["EC", "EV"],
                   "guidance": guidance("INITIAL_PROCEDURE", namespace)}
                  for sid, namespace in [("z_arizona", "ARIZONA"), ("a_illinois", "ILLINOIS")]]
    proposed = copy.deepcopy(study.bank)
    for skill in proposed:
        skill["guidance"]["by_task"] = [
            guidance("FIXED_PROCEDURE", tasks=(family,))["by_task"][0]
            for family in ("EC", "EV")]
    citations = {1: "Ariz. Rev. Stat. § 33-1123", 2: "735 Ill. Comp. Stat. 5/12-1001(b)"}
    teachers = []

    def call(dest, messages, schema, max_tokens, metadata):
        study.native.append(metadata)
        fixed = "FIXED_PROCEDURE" in str(messages)
        reference = citations[metadata["document_id"]].replace("§", "section")
        answer = ({"A001": [reference] if fixed else []} if metadata["family"] == "EC" else
                  {"A001": [{"citation_ref": reference, "claim_value": 30 if fixed else 1}]})
        return {"content": json.dumps(answer), "finish_reason": "stop"}

    def grade(records):
        for rec in records:
            citation = citations[rec["case_id"]]
            target = ({"watch": [citation]} if rec["family"] == "EC" else
                      {"watch": [{"citation": citation, "claim_value": 30}]})
            rec["score"] = evaluate(rec, rec["parsed"]["answer"], target)
        return records

    def teacher(name, *args):
        teachers.append(name)
        if (name.endswith("candidate1") and first_noop) or (
                name.endswith("candidate2") and not first_noop):
            return diagnosed_test_reply(study, {"operations": [],
                "noop_reason": "Synthetic fixed-step opportunity without another edit"})
        return diagnosed_test_reply(study, {"noop_reason": None, "operations": [
            {"operation": "UPDATE", "target_ids": [skill["id"]], "skill": skill,
             "source_case_ids": [1, 2], "rationale": "Synthetic complete two-task repair"}
            for skill in proposed]})

    study.call, study.grade, study.teacher_call = call, grade, teacher
    study.teacher_body = lambda *args: {"training_evidence_manifest": {"selected_source_ids": [1, 2]}}
    parent = grade([study.answer(row, study.bank, "parent", "skills") for row in study.rows])
    publication = study.update(study.rows, study.rows, parent)
    fixed = teacher_policy == "joint_fixed_steps"
    assert teachers == (["b1_candidate1", "b1_candidate2"] if fixed else ["b1_candidate1"])
    assert len(publication["training_decisions"]) == (2 if fixed else 1)
    if first_noop and not fixed:
        assert publication["training_decisions"][0]["explicit_noop"]
        assert len(study.native) == 4
        return
    decision = publication["training_decisions"][int(first_noop)]
    assert decision["accepted"] and decision["proposal_fully_committed"]
    assert all(task_view(study.bank, family) == task_view(proposed, family) for family in ("EC", "EV"))
    assert len(study.native) == 8  # Four parent + four proposed; composition only reuses exact wires.
    if policy != "adaptive_legal":
        assert study.bank != proposed  # Sorting/merging record blocks does not justify another proposal.


def test_adaptive_replay_objective_keeps_pairing_and_task_balance_explicit():
    before = [{**record(family, .5), "case_id": 1} for family in ("EC", "EV")]
    after = [{**record("EC", .6), "case_id": 1}, {**record("EV", .7), "case_id": 1}]
    assert balanced_replay_gain(before, after) == pytest.approx((.1, .15))
    with pytest.raises(ValueError, match="Unpaired"):
        balanced_replay_gain(before, after[:1])
    with pytest.raises(ValueError, match="distinct"):
        balanced_replay_gain(before + before, after + after)


def test_teacher_history_budget_never_drops_bounded_candidate_witnesses():
    seen = [{**r, "case_id": case} for case in range(1, 45) for r in scope_rows()[:2]]
    observations = {(r["case_id"], r["family"]): {**record(r["family"], .8), "case_id": r["case_id"]}
                    for r in seen}
    rejected = [{"feedback_witness_replay": [observations[(case, "EC")]
                 for case in range(start, start + 8)]} for start in (1, 9, 17)]
    selected, manifest = teacher_evidence_rows(seen[-8:], seen, observations, rejected)
    assert {r["case_id"] for r in selected} == set(range(1, 25)) | set(range(41, 45))
    assert manifest["historical_source_limit"] == 24
    assert manifest["historical_background_source_limit"] == 16
    assert manifest["all_bounded_feedback_witnesses_included"]
    with pytest.raises(ValueError, match="already-seen"):
        teacher_evidence_rows(seen[-8:], seen, observations,
            [{"feedback_witness_replay": [{"case_id": 99, "family": "EC"}]}])


@pytest.mark.parametrize("contract_version", [13, 14])
@pytest.mark.parametrize("closed_loop,second_good,coordinate", [
    (False, True, False), (True, True, False), (True, False, False),
    (True, True, True), (True, False, True)])
def test_partial_commit_refinement_and_next_batch_feedback_are_real_train_only(
        tmp_path, monkeypatch, closed_loop, second_good, coordinate, contract_version):
    from types import SimpleNamespace

    from legal_skill_guard.learning.phase_dispatch import PhaseDispatch
    from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

    monkeypatch.setattr("experiments.openexempt_online.ROOT", tmp_path)
    if contract_version == 14:
        monkeypatch.setattr("legal_skill_guard.learning.legal_namespace.asset_description_lexicon",
                            lambda: ("watch", "bowl"))
    study = Online.__new__(Online)
    study.cfg = {"execution_contract": "direct_statutory_claims",
        "execution_contract_version": contract_version,
        "candidate_feedback_policy": ("carry_partial_and_refine" if closed_loop
                                      else "batch_only_first_commit"),
        "generation": {"seed": 45, "max_tokens": 100}, "max_candidate_attempts": 2,
        "library_token_hard_cap": 4096, "skill_commit_policy": "legal_scope",
        "teacher_update_policy": ("task_projection_coordinate" if coordinate else "joint_bounded_refinement"),
        "task_update_schedule": ["EC", "EV"]}
    study._dispatch = PhaseDispatch({})
    study.current_batch, study.latest = 1, {}
    study.out, study.native, study.request_cache, study.reuse_events = tmp_path, [], {}, []
    study.meter = SimpleNamespace(token_count=lambda **kwargs: 300)
    study.check, study.progress = lambda: None, lambda *a, **k: None

    def source(number):
        return [{"case_id": number, "source_key": f"source{number}", "family": family,
                 "prompt": "public original", "components": {**copy.deepcopy(COMPONENTS),
                    "facts": f"Person{number} (hereinafter the Debtor) owns a watch worth $40 and a bowl worth $20."}}
                for family in ("EC", "EV")]

    def book(ec, ev):
        return [{"id": "az", "hypothesis_ids": ["EC", "EV"], "guidance": {
            "by_task": [guidance(ec, tasks=("EC",))["by_task"][0],
                        guidance(ev, tasks=("EV",))["by_task"][0]],
            "operators": [], "jurisdiction": "ARIZONA"}}]

    study.rows = source(1)
    study.bank = book("EC_INITIAL", "EV_INITIAL")
    original = copy.deepcopy(study.bank)
    prompts = []
    reference, citation = "Ariz. Rev. Stat. section 33-1123", "Ariz. Rev. Stat. § 33-1123"

    def call(dest, messages, schema, max_tokens, metadata):
        study.native.append(metadata)
        if metadata["family"] == "EC":
            value = {name: [reference] if "EC_FIXED" in str(messages) else []
                     for name in ("watch", "bowl")}
        else:
            amounts = ((40, 20) if "EV_FIXED" in str(messages) else
                       (1, 1) if "EV_BAD" in str(messages) else (40, 1))
            value = {name: [{"citation_ref": reference, "claim_value": amount}]
                     for name, amount in zip(("watch", "bowl"), amounts, strict=True)}
        if contract_version == 14:
            value = {f"A{index:03d}": entries for index, entries in enumerate(value.values(), 1)}
        return {"content": json.dumps(value), "finish_reason": "stop"}

    def grade(records):
        for rec in records:
            target = ({name: [citation] for name in ("watch", "bowl")} if rec["family"] == "EC" else
                      {name: [{"citation": citation, "claim_value": amount}]
                       for name, amount in (("watch", 40), ("bowl", 20))})
            rec["score"] = evaluate(rec, rec["parsed"]["answer"], target)
        return records

    def body(current, seen, observations, rejected, *, teaching_task=None):
        return {"current_parent_library": copy.deepcopy(study.bank),
            "teaching_task": teaching_task,
            "rejected_candidate_feedback": copy.deepcopy([
                d for d in rejected if teaching_task is None or d.get("teaching_task") == teaching_task]),
            "training_evidence_manifest": {"selected_source_ids": sorted({r["case_id"] for r in seen})}}

    def teacher(name, system, request, schema):
        prompts.append((name, copy.deepcopy(request)))
        if name.startswith("b2_"):
            return diagnosed_test_reply(study, {"operations": [], "noop_reason": "No additional synthetic TRAIN repair"})
        proposed = (book("EC_FIXED", "EV_FIXED") if second_good else book("EC_INITIAL", "EV_BAD")) \
            if name.endswith("candidate2") else book("EC_FIXED", "EV_BAD")
        if coordinate:
            proposed = (book("EC_FIXED", "EV_FIXED" if second_good else "EV_BAD")
                        if name.endswith("candidate2") else book("EC_FIXED", "EV_INITIAL"))
        return diagnosed_test_reply(study, {"noop_reason": None, "operations": [{"operation": "UPDATE", "target_ids": ["az"],
            "skill": proposed[0], "source_case_ids": [1], "rationale": "Synthetic partial-repair contract"}]})

    study.call, study.grade, study.teacher_body, study.teacher_call = call, grade, body, teacher
    first = grade([study.answer(r, study.bank, "first_encounter", "skills") for r in study.rows])
    first_saved = copy.deepcopy(first)
    publication = study.update(study.rows, study.rows, first)
    assert first == first_saved  # TRAIN refinement never replaces first predictions/scores.
    assert publication["parent_bank_sha256"] == csha(original)
    assert publication["training_decisions"][0]["accepted_legal_coordinates"] == ["EC:ARIZONA"]
    assert len(publication["training_decisions"]) == (2 if closed_loop else 1)
    assert len(study.native) == (4 if coordinate else 5 if closed_loop and second_good else 4)
    assert metrics(list(study.latest.values()))["EC"]["f1"] == 1
    assert metrics(list(study.latest.values()))["EV"]["f1"] == (1 if closed_loop and second_good else .5)
    if closed_loop:
        second = prompts[1][1]
        assert second["candidate_feedback_contract"]["attempt"] == 2
        assert task_view(second["current_parent_library"], "EC") == task_view(book("EC_FIXED", "EV_INITIAL"), "EC")
        assert task_view(second["current_parent_library"], "EV") == task_view(original, "EV")
        if coordinate:
            assert not second["rejected_candidate_feedback"]
            assert [p[1]["teaching_task"] for p in prompts] == ["EC", "EV"]
            assert publication["training_decisions"][0]["proposal_fully_committed"]
            assert all(d["edit_audit"]["task_projection_boundary"]["other_task_projection_unchanged"]
                       for d in publication["training_decisions"])
        else:
            assert second["rejected_candidate_feedback"][0]["accepted"]
            assert second["rejected_candidate_feedback"][0]["partially_committed"]
        assert publication["training_decisions"][1]["attempt_parent_bank_sha256"] == csha(publication["training_decisions"][0]["candidate"])
        assert publication["training_decisions"][1]["accepted"] == second_good
    study.current_batch = 2
    current = source(2)
    study.rows += current
    parent = grade([study.answer(r, study.bank, "b2_first_encounter", "skills") for r in current])
    before_second_batch = copy.deepcopy(study.bank)
    next_publication = study.update(current, study.rows, parent)
    assert next_publication["parent_bank_sha256"] == csha(before_second_batch)
    assert study.bank == before_second_batch
    carried = prompts[-1][1]["rejected_candidate_feedback"]
    assert bool(carried) == (not second_good if coordinate else closed_loop)
    if coordinate:
        assert len(next_publication["training_decisions"]) == 2  # EC NOOP must not skip EV.
        assert [p[1]["teaching_task"] for p in prompts[-2:]] == ["EC", "EV"]
        if not second_good:
            assert len(carried) == 1 and carried[0]["teaching_task"] == "EV"
            assert not carried[0]["accepted"]
            assert all(r["family"] == "EV" for r in carried[0]["feedback_witness_replay"])
    elif closed_loop:
        assert len(carried) == (1 if second_good else 2)
        assert carried[0]["accepted"] and carried[0]["partially_committed"]
        assert carried[0]["candidate_feedback_origin"]["batch"] == 1
        assert all(r["case_id"] == 1 for r in carried[0]["feedback_witness_replay"])
        if not second_good:
            assert not carried[1]["accepted"] and not carried[1]["partially_committed"]
