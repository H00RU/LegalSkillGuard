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
    task_admission,
    teacher_evidence_rows,
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
    assert messages[-1] == other[-1] and row["components"]["facts"] in messages[-1]["content"]
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
    delivered = json.loads(messages[1]["content"].split("\n", 1)[1])
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
        assert "asset_ref" in body["actual_actor_system"]
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
                assert "claim_value" in str(context["EV"]["response_schema"])
                assert "limit_expression" not in str(context["EV"]["response_schema"])
    assert body["full_serialized_library_token_budget"]["actual_parent_tokens"] == 4008
    assert body["full_serialized_library_token_budget"]["net_growth_headroom"] == 88
    assert {r["source_case_id"] for r in body["already_seen_training"]} == ids
    assert set(read_cases) == ids
    assert set(native_read_cases) == ids  # Never load omitted or future native evidence.
    emitted_case = next(c for c in body["already_seen_training"]
                        if c["source_case_id"] == 21 and c["family"] == "EV")
    emitted = emitted_case["actual_parent_answer"]["source_model_emitted_evidence"]
    assert emitted["emitted_by_executor_unverified"] and emitted["finish_reason"] == "length"
    assert emitted["completion_tokens"] == emitted["max_completion_tokens"] == 8192
    assert emitted["reasoning"]["text"] == model_trace[-1024:]
    assert emitted["reasoning"]["canonical_text_sha256"] == canonical_json_sha256(model_trace)
    assert emitted["reasoning"]["truncated_to_tail"]
    preview = emitted["failed_native_final"]
    assert preview["head"] == failed_output[:256] and preview["tail"] == failed_output[-256:]
    assert preview["canonical_text_sha256"] == canonical_json_sha256(failed_output)
    assert preview["middle_omitted"] and preview["characters"] == len(failed_output)
    assert "source_model_emitted_evidence" not in emitted_case["actual_same_case_empty_answer"]
    assert "source_model_emitted_evidence" not in emitted_case["actual_same_case_frozen_initial_answer"]
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
    assert skilled_messages[-1] == messages[-1]
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
                 "skill_commit_policy": policy}
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
    study.teacher_call = lambda *args: {"noop_reason": None, "operations": [{
        "operation": "UPDATE", "target_ids": ["az"], "skill": proposed[0],
        "source_case_ids": [1], "rationale": "synthetic task conflict"}]}
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
                 "skill_commit_policy": policy,
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
    study.teacher_call = lambda *args: {"noop_reason": None, "operations": [{
        "operation": "UPDATE", "target_ids": [s["id"]], "skill": s,
        "source_case_ids": [1, 2], "rationale": "synthetic public-scope interference"} for s in proposed]}
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
        "skill_commit_policy": policy,
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
    study.teacher_call = lambda *args: {"noop_reason": None, "operations": [
        {"operation": "UPDATE", "target_ids": [s["id"]], "skill": s,
         "source_case_ids": [1, 2, 3, 4], "rationale": "Synthetic complementary TRAIN changes"}
        for s in proposed]}
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
@pytest.mark.parametrize("closed_loop,second_good", [(False, True), (True, True), (True, False)])
def test_partial_commit_refinement_and_next_batch_feedback_are_real_train_only(
        tmp_path, monkeypatch, closed_loop, second_good, contract_version):
    from types import SimpleNamespace

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
        "library_token_hard_cap": 4096, "skill_commit_policy": "legal_scope"}
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

    def body(current, seen, observations, rejected):
        return {"current_parent_library": copy.deepcopy(study.bank),
            "rejected_candidate_feedback": copy.deepcopy(rejected),
            "training_evidence_manifest": {"selected_source_ids": sorted({r["case_id"] for r in seen})}}

    def teacher(name, system, request, schema):
        prompts.append((name, copy.deepcopy(request)))
        if name.startswith("b2_"):
            return {"operations": [], "noop_reason": "No additional synthetic TRAIN repair"}
        proposed = (book("EC_FIXED", "EV_FIXED") if second_good else book("EC_INITIAL", "EV_BAD")) \
            if name.endswith("candidate2") else book("EC_FIXED", "EV_BAD")
        return {"noop_reason": None, "operations": [{"operation": "UPDATE", "target_ids": ["az"],
            "skill": proposed[0], "source_case_ids": [1], "rationale": "Synthetic partial-repair contract"}]}

    study.call, study.grade, study.teacher_body, study.teacher_call = call, grade, body, teacher
    first = grade([study.answer(r, study.bank, "first_encounter", "skills") for r in study.rows])
    first_saved = copy.deepcopy(first)
    publication = study.update(study.rows, study.rows, first)
    assert first == first_saved  # TRAIN refinement never replaces first predictions/scores.
    assert publication["parent_bank_sha256"] == csha(original)
    assert publication["training_decisions"][0]["accepted_legal_coordinates"] == ["EC:ARIZONA"]
    assert len(publication["training_decisions"]) == (2 if closed_loop else 1)
    assert len(study.native) == (5 if closed_loop and second_good else 4)
    assert metrics(list(study.latest.values()))["EC"]["f1"] == 1
    assert metrics(list(study.latest.values()))["EV"]["f1"] == (1 if closed_loop and second_good else .5)
    if closed_loop:
        second = prompts[1][1]
        assert second["candidate_feedback_contract"]["attempt"] == 2
        assert task_view(second["current_parent_library"], "EC") == task_view(book("EC_FIXED", "EV_INITIAL"), "EC")
        assert task_view(second["current_parent_library"], "EV") == task_view(original, "EV")
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
    assert bool(carried) == closed_loop
    if closed_loop:
        assert len(carried) == (1 if second_good else 2)
        assert carried[0]["accepted"] and carried[0]["partially_committed"]
        assert carried[0]["candidate_feedback_origin"]["batch"] == 1
        assert all(r["case_id"] == 1 for r in carried[0]["feedback_witness_replay"])
        if not second_good:
            assert not carried[1]["accepted"] and not carried[1]["partially_committed"]
