"""Durable text-baseline contract checks; no model calls or task-score fitting."""

import copy

import pytest

from legal_skill_guard.learning.trace2skill_text import (
    EDIT_FIELDS, INITIAL_FILES, actor_bank, apply_patch, merge_groups, validate_files,
)


def edit(op, **fields):
    value = {key: "" for key in EDIT_FIELDS}
    value.update(file="SKILL.md", op=op)
    value.update(fields)
    return value


def patch(*edits):
    return {"reasoning": "Contract fixture, not a learned legal procedure.",
            "edits": list(edits), "changelog_entries": []}


def test_scaffold_is_preserved_by_explicit_noop():
    original = copy.deepcopy(INITIAL_FILES)
    assert apply_patch(original, patch()) == original == INITIAL_FILES
    validate_files(original)
    assert actor_bank(original) == []


def test_balanced_groups_cover_every_original_patch_and_declared_cost_bound():
    for count in range(1, 257):
        groups = merge_groups(range(count), 5)
        assert sorted(item for group in groups for item in group) == list(range(count))
        assert len(groups) < count or count == 1
    remaining, calls, levels = 256, 0, 0
    while remaining > 1:
        remaining = len(merge_groups(range(remaining), 5))
        calls += remaining
        levels += 1
    assert (calls, levels, 256 + calls + 1) == (64, 4, 321)
    assert [len(group) for group in merge_groups(range(11), 5)] == [6, 5]


def test_independent_original_sections_apply_without_mutating_parent():
    original = copy.deepcopy(INITIAL_FILES)
    value = apply_patch(original, patch(
        edit("append_to_section", target_section="## Procedures", content="Fixture procedure."),
        edit("append_to_section", target_section="## Guardrails", content="Fixture exception.")))
    assert original == INITIAL_FILES
    assert "Fixture procedure." in value["SKILL.md"]
    assert "Fixture exception." in value["SKILL.md"]


def test_overlapping_original_edits_fail_instead_of_dropping_one():
    with pytest.raises(ValueError, match="overlapping"):
        apply_patch(INITIAL_FILES, patch(
            edit("append_to_section", target_section="## Procedures", content="First fixture."),
            edit("append_to_section", target_section="## Procedures", content="Second fixture.")))


def test_reference_and_root_link_are_atomic_and_preloaded_verbatim():
    value = apply_patch(INITIAL_FILES, patch(
        edit("append_to_section", target_section="## Procedures",
             content="See [Fixture](references/fixture.md)."),
        edit("create", file="references/fixture.md", content="# Fixture\nUnique fixture text.")))
    bank = actor_bank(value)
    text = bank[0]["guidance"]["by_task"][0]["procedure"]
    assert "Unique fixture text." in text and value["SKILL.md"] in text
    assert bank[0]["hypothesis_ids"] == ["EC", "EV"]
    assert bank[0]["guidance"]["jurisdiction"] == "ALL"
    assert bank[0]["guidance"]["operators"] == []


@pytest.mark.parametrize("bad", [
    edit("create", file="references/orphan.md", content="Unlinked fixture."),
    edit("append_to_section", target_section="## Procedures", content="[Missing](references/missing.md)"),
    edit("create", file="../outside.md", content="Outside fixture."),
    edit("delete_file"),
    edit("insert_after", target_text="absent fixture", content="New fixture."),
])
def test_invalid_skill_patch_stops_without_repair_or_old_patch_fallback(bad):
    with pytest.raises(ValueError):
        apply_patch(INITIAL_FILES, patch(bad))


def test_insert_replace_and_delete_use_original_unique_targets():
    files = copy.deepcopy(INITIAL_FILES)
    files["SKILL.md"] += "\n## Fixture\nOriginal fixture.\n"
    updated = apply_patch(files, patch(edit("replace_in_section", target_section="## Fixture",
                                          old_text="Original fixture.", content="Replacement fixture.")))
    assert "Replacement fixture." in updated["SKILL.md"]
    deleted = apply_patch(updated, patch(edit("delete_section", target_section="## Fixture")))
    assert "## Fixture" not in deleted["SKILL.md"]


def test_reference_delete_also_requires_removing_its_root_link():
    files = copy.deepcopy(INITIAL_FILES)
    files["SKILL.md"] += "\n## Fixture\n[Fixture](references/fixture.md)\n"
    files["references/fixture.md"] = "# Fixture\nFixture reference.\n"
    removed = apply_patch(files, patch(
        edit("delete_section", target_section="## Fixture"),
        edit("delete_file", file="references/fixture.md")))
    assert set(removed) == {"SKILL.md"}
    with pytest.raises(ValueError, match="reference"):
        apply_patch(files, patch(edit("delete_file", file="references/fixture.md")))


def test_full_offline_stage_order_and_all321_calls_without_any_model(monkeypatch, tmp_path):
    import experiments.openexempt_trace2skill as module

    learner = module.Trace2Skill.__new__(module.Trace2Skill)
    learner.rows = [{"case_id": case, "family": family, "batch": (case - 1) // 16 + 1}
                    for case in range(1, 129) for family in ("EC", "EV")]
    learner.cfg = {"grading_directory": "synthetic-grading", "merge_batch_size": 5,
                   "max_merge_levels": 5, "library_token_hard_cap": 8192,
                   "planned_teacher_responses_max": 321}
    learner.out = tmp_path / "fixture-run"
    learner.files, learner.bank = copy.deepcopy(INITIAL_FILES), []
    learner.native, learner.teachers, learner.teacher_attempts = [], [], 0
    answers, teacher_inputs = [], []

    class Meter:
        def token_count(self, **kwargs):
            assert "Fixture learned procedure." in kwargs["text"]
            return 100

    learner.meter = Meter()

    def answer(row, bank, stage, arm):
        assert stage in ("source_first_forecasts", "final_TRAIN_replay")
        if stage == "source_first_forecasts":
            assert bank == [] and teacher_inputs == []
        else:
            assert len(teacher_inputs) == 321 and bank == learner.bank
        record = {"case_id": row["case_id"], "family": row["family"], "stage": stage,
                  "parsed": {"answer": {}}, "parse_error": None,
                  "raw_call_path": f"synthetic-native/{row['case_id']}_{row['family']}.json"}
        answers.append((stage, row["case_id"], row["family"]))
        return record

    def grade(records):
        assert len(answers) >= 256
        for index, record in enumerate(records):
            record["score"] = {"full_output_claim_fp": 0,
                               "full_output_claim_fn": index % 2}
        return records

    def read_fixture(path):
        path = str(path)
        if path.endswith(".input.json"):
            return {"messages": [{"role": "user", "content": "Synthetic public fixture."}],
                    "schema": {"type": "object"}}
        if "synthetic-grading" in path:
            assert len(answers) == 256
            return {"targets": {"EC": {}, "EV": {}}}
        assert "synthetic-native" in path
        return {"response": {"content": "{}", "reasoning": "Synthetic trace."}}

    def teacher(name, system, body, schema):
        assert len(answers) == 256
        teacher_inputs.append((name, system, copy.deepcopy(body)))
        learner.teachers.append({"name": name})
        if name.startswith("map_"):
            assert body["immutable_initial_files"] == INITIAL_FILES
            assert body["outcome"] in ("success", "failure")
        elif name.startswith("merge_"):
            assert body["immutable_initial_files"] == INITIAL_FILES
            assert len(body["all_patches_in_this_ordered_group"]) >= 2
        else:
            assert name == "translate_final_patch"
        return patch(edit("append_to_section", target_section="## Procedures",
                          content="Fixture learned procedure."))

    learner.answer, learner.grade, learner.teacher_call = answer, grade, teacher
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "read", read_fixture)
    monkeypatch.setattr(module, "metrics", lambda values: {"synthetic_task_count": len(values)})
    result = learner.execute()
    assert len(answers) == 512 and len(teacher_inputs) == 321
    assert sum(name.startswith("map_") for name, _, _ in teacher_inputs) == 256
    assert sum(name.startswith("merge_") for name, _, _ in teacher_inputs) == 64
    assert result["source_first_forecasts"] == {"synthetic_task_count": 256}
    assert result["final_TRAIN_replay_is_not_unseen_case_or_TEST"] is True
    assert (learner.out / "publications/final.json").is_file()
