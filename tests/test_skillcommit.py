"""Small deterministic algorithm checks; no teacher, model or test cases."""

from legal_skill_guard.learning.skillcommit import (
    COMMON_ROLE,
    PATCH_ROLE,
    actor_bank,
    decode_teacher_reference,
    leakage_reason,
    memory,
    patch_schema,
    reference_schema,
    select_anchor_group,
    select_supported_version,
    solved,
)


def test_memory_author_language_matches_public_tasks_and_pinned_english_encoder():
    assert "Write all prose fields in English" in COMMON_ROLE
    assert "pinned English semantic encoder" in COMMON_ROLE
    assert "authored directly in English" in PATCH_ROLE


def test_instance_solution_flag_explicitly_excludes_training_only_fields():
    fields = patch_schema()["properties"]
    description = fields["contains_instance_solution"]["description"]
    assert "ONLY repair_memory" in description
    assert "not public_reference_explanation or failure_diagnosis" in description
    assert "ONLY repair_memory" in PATCH_ROLE
    assert "not assessed by contains_instance_solution" in fields[
        "public_reference_explanation"]["description"]


def test_true_instance_solution_flag_still_rejects_before_native_replay(monkeypatch, tmp_path):
    import experiments.openexempt_skillcommit as module

    study = module.SkillCommit.__new__(module.SkillCommit)
    study.cfg = {"patch_attempts": 3}
    study.out = tmp_path
    study.reference = lambda row: {"asset": ["citation"]}
    study.teacher_reference = lambda *args: {"actual_verification": {"passed": True}}
    study.teach = lambda *args: {"repairable": True, "repair_memory": "Instance answer",
                                "contains_instance_solution": True}
    seen = []
    study.event = lambda name, body: seen.append(name)
    study.replay = lambda *args: (_ for _ in ()).throw(AssertionError("Must not replay leaked repair"))
    monkeypatch.setattr(module, "read", lambda path: {
        "messages": [], "schema": {}, "response": {"content": "old public answer"}})
    row = {"case_id": 300, "family": "EC", "source_key": "source-unique-key"}
    first = {"parsed": None, "raw_call_path": "unused.json", "parse_error": None, "score": {}}
    assert study.patch(row, first) is None
    assert seen == ["patch_leakage_reject"] * 3


def test_reference_uses_independent_training_only_output_and_copies_original_schema():
    schema = {"type": "object", "properties": {"A001": {"type": "array"}}}
    wrapped = reference_schema(schema)
    assert set(wrapped["required"]) == {
        "reference_answer", "public_reference_explanation", "failure_diagnosis"}
    assert "repair_memory" not in wrapped["properties"]
    wrapped["properties"]["reference_answer"]["properties"].clear()
    assert schema["properties"]


def test_teacher_reference_uses_only_original_public_decoding_without_amount_repair():
    original = {"schema": {"type": "object", "additionalProperties": False,
                            "required": ["A001"], "properties": {
                                "A001": {"type": "array"}}},
                "public_asset_reference_catalog": {"A001": "a household item"},
                "public_citation_catalog": {"C001": "Public statute § 3"}}
    assert decode_teacher_reference("EC", {"A001": ["C001"]}, original) == {
        "answer": {"a household item": ["Public statute § 3"]}}
    assert decode_teacher_reference("EV", {"A001": [
        {"citation_ref": "C001", "claim_value": -7.25}]}, original) == {
            "answer": {"a household item": [
                {"citation": "Public statute § 3", "claim_value": -7.25}]}}


def test_unverified_teacher_reference_retains_actual_prediction_and_does_not_substitute_gold(
        monkeypatch, tmp_path):
    import experiments.openexempt_skillcommit as module

    study = module.SkillCommit.__new__(module.SkillCommit)
    study.out = tmp_path
    study.reference = lambda row: {"a household item": ["different gold citation"]}
    study.teach = lambda *args: {"reference_answer": {"A001": []},
                                "public_reference_explanation": "An observed explanation",
                                "failure_diagnosis": "An observed diagnosis"}
    original = {"messages": [], "schema": {"type": "object"},
                "public_asset_reference_catalog": {"A001": "a household item"},
                "public_citation_catalog": {}}
    def grade(records):
        assert records[0]["parsed"] == {"answer": {"a household item": []}}
        records[0]["score"] = {"f1": 0}
    study.grade = grade
    study.passes = lambda record: False
    events = []
    study.event = lambda name, body: events.append((name, body))
    monkeypatch.setattr(module, "read", lambda path: {"response": {"content": "failed"}})
    row = {"case_id": 300, "source_key": "unique", "family": "EC"}
    first = {"parsed": None, "parse_error": "invalid", "raw_call_path": "unused"}
    assert study.teacher_reference(row, first, original) is None
    assert [name for name, _ in events] == [
        "teacher_reference_validation", "unverified_reference_skip_patch"]
    assert events[0][1]["actual_verification"]["passed"] is False


def test_patch_cannot_be_authored_or_replayed_without_a_verified_reference(monkeypatch, tmp_path):
    import experiments.openexempt_skillcommit as module

    study = module.SkillCommit.__new__(module.SkillCommit)
    study.out = tmp_path
    study.cfg = {"patch_attempts": 3}
    study.reference = lambda row: {}
    study.teacher_reference = lambda *args: None
    study.teach = lambda *args: (_ for _ in ()).throw(AssertionError("Must not author patch"))
    study.replay = lambda *args: (_ for _ in ()).throw(AssertionError("Must not replay"))
    monkeypatch.setattr(module, "read", lambda path: {})
    assert study.patch({"case_id": 300, "family": "EC"}, {}) is None


def test_verified_reference_precedes_patch_and_only_repair_enters_source_replay(
        monkeypatch, tmp_path):
    import experiments.openexempt_skillcommit as module

    study = module.SkillCommit.__new__(module.SkillCommit)
    study.out = tmp_path
    study.cfg = {"patch_attempts": 3}
    study.reference = lambda row: {}
    order = []
    reference = {"reference": {"reference_answer": {"A001": ["C001"]}},
                 "actual_verification": {"passed": True}}
    def teacher_reference(*args):
        order.append("verified_reference")
        return reference
    def teach(role, system, body, schema):
        order.append(role)
        assert body["native_verifier_accepted_teacher_reference"] == reference
        return {"repairable": True, "repair_memory": "Check all independent grants.",
                "contains_instance_solution": False}
    def replay(item, rows, purpose):
        order.append("source_replay")
        assert "reference_answer" not in str(actor_bank([item]))
        assert "A001" not in str(actor_bank([item]))
        assert "C001" not in str(actor_bank([item]))
        return [{"passed": True}]
    study.teacher_reference, study.teach, study.replay = teacher_reference, teach, replay
    study.memories, study.residual = {"EC": {}}, {"EC": []}
    study.event = lambda *args: None
    monkeypatch.setattr(module, "read", lambda path: {
        "messages": [], "schema": {}, "response": {"content": "failed"}})
    row = {"case_id": 300, "family": "EC", "source_key": "unique"}
    first = {"parsed": None, "parse_error": None, "raw_call_path": "unused", "score": {}}
    assert study.patch(row, first) is not None
    assert order == ["verified_reference", "patch", "source_replay"]


def test_publication_does_not_render_training_support_or_other_task():
    m = memory("EC", "pattern", {"when": "When conditions match", "repair": "List alternatives",
                               "avoid_when": "Outside stated law"}, [299, 301])
    bank = actor_bank([m])
    assert bank[0]["hypothesis_ids"] == ["EC"]
    assert "sources" not in bank[0]
    assert "299" not in str(bank)
    assert "301" not in str(bank)
    assert bank[0]["guidance"]["operators"] == []


def test_native_ceiling_accounts_for_empty_target_assets_without_using_our_gate():
    record = {"parse_error": None, "parsed": {"answer": {"a": ["citation"]}},
              "score": {"f1": .75}}
    assert solved(record, .75)
    assert not solved(record, 1.0)
    record["parse_error"] = "length"
    assert not solved(record, .75)


def test_all_negative_native_zero_is_not_automatically_a_pass():
    base = {"parse_error": None, "score": {"f1": 0}}
    assert solved({**base, "parsed": {"answer": {"a": []}}}, 0)
    assert not solved({**base, "parsed": {"answer": {"a": ["invented"]}}}, 0)


def test_statutory_limit_is_not_mistaken_for_a_numeric_case_id():
    row = {"case_id": 300, "source_key": "distinctive-source-key"}
    assert leakage_reason("Apply the statutory $300 limit.", row, {}) is None
    assert leakage_reason("For each asset_ref, list all eligible citation_ref values.", row, {}) is None
    assert leakage_reason("For case 300, output this result.", row, {})
    assert leakage_reason("Use citation_ref for A1.", row, {})


def test_public_statutory_category_is_not_treated_as_a_private_asset_name():
    asset = "household goods held for personal and family use"
    row = {"case_id": 300, "source_key": "unique-key",
           "components": {"statutes": f"The exemption covers {asset}."}}
    assert leakage_reason(f"Check eligibility of {asset}.", row, {asset: []}) is None


def test_root_group_needs_incoming_and_behavioral_anchor_not_similarity_alone():
    transfers = {("old1", "new"): True, ("old1", "old2"): True}
    group = select_anchor_group("new", ["old1", "old2", "unrelated"], transfers,
                                {"old1": .5, "old2": .4, "unrelated": .99})
    assert group["members"] == ["new", "old1", "old2"]
    assert group["anchor"] == "old1"
    assert select_anchor_group("new", ["unrelated"], {}, {"unrelated": .99}) is None


def test_split_uses_maximal_recorded_support_and_earliest_tie():
    versions = [{"attempt": 1, "supported_sources": [1, 2, 3]},
                {"attempt": 2, "supported_sources": [1, 2, 4]},
                {"attempt": 3, "supported_sources": [1, 2]}]
    assert select_supported_version(versions)["attempt"] == 1
    assert select_supported_version([{"attempt": 1, "supported_sources": [1]}]) is None


def test_scope_and_version_identity_are_preserved_separately_from_actor_text():
    desc = {"when": "Condition", "repair": "Procedure", "avoid_when": "Exception"}
    parent = memory("EV", "pattern", desc, [1, 2])
    expanded = memory("EV", "pattern", desc, [1, 2, 3], parent=parent["id"])
    assert parent["id"] != expanded["id"]
    assert expanded["parent"] == parent["id"]
    assert expanded["sources"] == [1, 2, 3]


def test_scoped_bank_stays_empty_without_admitted_memories():
    assert actor_bank([]) == []


def test_full_support_replaces_parent_and_absorbs_patch():
    from experiments.openexempt_skillcommit import SkillCommit

    study = SkillCommit.__new__(SkillCommit)
    desc = {"when": "Condition", "repair": "Procedure", "avoid_when": "Exception"}
    parent = memory("EC", "pattern", desc, [1, 2])
    patch = memory("EC", "patch", desc, [3])
    child = memory("EC", "pattern", desc, [1, 2, 3], parent=parent["id"])
    study.memories = {"EC": {parent["id"]: parent, patch["id"]: patch}}
    study.patterns = {"EC": [parent["id"]]}
    study.residual = {"EC": [patch["id"]]}
    study.event = lambda *args: None
    assert study.commit("EC", child, [parent, patch], parent=parent, split=False)
    assert study.patterns["EC"] == [child["id"]]
    assert study.residual["EC"] == []
    assert parent["id"] in study.memories["EC"]


def test_split_preserves_parent_and_uncovered_incoming_patch():
    from experiments.openexempt_skillcommit import SkillCommit

    study = SkillCommit.__new__(SkillCommit)
    desc = {"when": "Condition", "repair": "Procedure", "avoid_when": "Exception"}
    parent = memory("EV", "pattern", desc, [1, 2, 3])
    patch = memory("EV", "patch", desc, [4])
    sibling = memory("EV", "pattern", desc, [1, 2], parent=parent["id"])
    study.memories = {"EV": {parent["id"]: parent, patch["id"]: patch}}
    study.patterns = {"EV": [parent["id"]]}
    study.residual = {"EV": [patch["id"]]}
    study.event = lambda *args: None
    assert study.commit("EV", sibling, [parent, patch], parent=parent, split=True)
    assert study.patterns["EV"] == [parent["id"], sibling["id"]]
    assert study.residual["EV"] == [patch["id"]]
