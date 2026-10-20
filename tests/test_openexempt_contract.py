"""Small boundary tests for the new task, not a second evaluation framework."""

import copy
import json

import pytest

from experiments.openexempt_online import (
    Online,
    acceptance,
    actor_payload,
    task_admission,
    teacher_evidence_rows,
)
from legal_skill_guard.learning.legal_namespace import (
    active_bank,
    allowable_namespaces,
    decode_claim_plan,
    decode_classification,
    decode_reference,
    public_catalog,
)
from legal_skill_guard.learning.task_scoped_skills import (
    compose_task_edits,
    import_blind_prior,
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


def test_teacher_packet_is_bounded_but_current_sources_and_full_replay_are_not_dropped(monkeypatch):
    from types import SimpleNamespace

    from legal_skill_guard.utils.hashing import canonical_json_sha256

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
    study.cfg = {"execution_contract": "source_grounded_claim_operations",
                 "grading_directory": "synthetic_labels_only", "library_token_hard_cap": 4096}
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


def test_strong_direct_numeric_empty_is_not_a_program_or_host_repaired_answer(tmp_path, monkeypatch):
    from jsonschema import validate

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
    with pytest.raises(ValueError):
        actor_payload(row, [{"id": "not empty"}], direct_numeric=True)
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


def test_full_update_commits_ev_only_and_reexecutes_composition_without_new_native_calls(
        tmp_path, monkeypatch):
    from types import SimpleNamespace

    from legal_skill_guard.utils.hashing import canonical_json_sha256

    monkeypatch.setattr("experiments.openexempt_online.ROOT", tmp_path)
    study = Online.__new__(Online)
    study.cfg = {"execution_contract": "source_grounded_claim_operations",
                 "generation": {"seed": 45, "max_tokens": 100},
                 "max_candidate_attempts": 1, "library_token_hard_cap": 4096}
    study.current_batch, study.latest = 1, {}
    study.out, study.native, study.request_cache, study.reuse_events = tmp_path, [], {}, []
    study.meter = SimpleNamespace(token_count=lambda **kwargs: 300)
    study.check, study.progress = lambda: None, lambda *a, **k: None
    study.rows = [{"case_id": 1, "source_key": "synthetic", "family": family,
                   "prompt": "public original", "components": copy.deepcopy(COMPONENTS)}
                  for family in ("EC", "EV")]
    study.bank = [{"id": "az", "hypothesis_ids": ["EC", "EV"],
                   "guidance": guidance("original procedure", "ARIZONA")}]
    study.bank[0]["guidance"]["operators"] = [{"id": "cap",
        "citation": "Ariz. Rev. Stat. § 33-1123", "limit_expression": "min(V,30)"}]
    proposed = copy.deepcopy(study.bank)
    proposed[0]["guidance"]["by_task"][0]["procedure"] = "new procedure"
    proposed[0]["guidance"]["operators"][0]["limit_expression"] = "min(V,15)"
    ref = "Ariz. Rev. Stat. section 33-1123"

    def call(dest, messages, schema, max_tokens, metadata):
        study.native.append(metadata)
        if metadata["family"] == "EC":
            answer = {} if "new procedure" in str(messages) else {"watch": [ref]}
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
    assert decision["accepted"] and decision["accepted_tasks"] == ["EV"]
    assert not decision["proposed_whole_bank_acceptance"]["accepted"]
    assert len(study.native) == 4  # Parent2 + proposed2; composed2 are raw aliases only.
    assert task_view(study.bank, "EC") == task_view(original, "EC")
    assert task_view(study.bank, "EV") == task_view(proposed, "EV")
    assert study.latest[(1, "EC")]["parsed"] == parent[0]["parsed"]
    ev = study.latest[(1, "EV")]
    assert ev["parsed"]["answer"]["watch"][0]["claim_value"] == 15
    assert ev["execution_receipt"]["execution_bank_sha256"] == canonical_json_sha256(study.bank)
    assert decision["current_family_nonregression"] and decision["current_full_output_nonregression"]
    study.request_cache.clear()
    with pytest.raises(ValueError, match="changed an evaluated native wire"):
        study.composed_replay(original, proposed, ["EV"], study.rows, "missing")
    study.meter = SimpleNamespace(token_count=lambda **kwargs: 4097)
    with pytest.raises(ValueError, match="exceeds total token cap"):
        study.composed_replay(original, proposed, ["EV"], study.rows, "oversized")
    assert len(study.native) == 4
