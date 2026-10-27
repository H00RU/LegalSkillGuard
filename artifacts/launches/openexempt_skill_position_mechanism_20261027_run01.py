"""Fixed B8 same-bank placement probe through the existing native actor path."""
import copy
import fcntl
import sys
import traceback
from pathlib import Path

from experiments.openexempt_online import Online, actor_payload, preserve
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read
from legal_skill_guard.openexempt import ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def main(config_path):
    cfg = read(config_path)
    assert cfg["study_kind"] == "same_bank_skill_placement_TRAIN_mechanism"
    assert cfg["planned_teacher_responses_max"] == 0
    out = ROOT / "runs" / cfg["run_id"]
    if out.exists():
        raise FileExistsError("Never overwrite or resume a chosen probe outcome")
    study = None
    try:
        study = Online(Path(config_path))
        assert csha(study.bank) == cfg["mechanism_bank_sha256"]
        source = ROOT / "runs" / cfg["mechanism_before_case_source_run"]
        rows = [r for r in study.rows if r["case_id"] in cfg["mechanism_source_case_ids"]]
        assert len(rows) == 32 and {r["family"] for r in rows} == {"EC", "EV"}
        before = []
        for row in rows:
            stem = f"{row['case_id']}_{row['family']}_candidate"
            original = read(source / "native/b8_candidate1_replay" / (stem + ".input.json"))
            record = read(source / "native/b8_candidate1_replay" / (stem + ".answer.json"))
            messages, schema, supplied = actor_payload(row, study.bank,
                grounded=True, direct_numeric=True, asset_references=True)
            expected = [original["messages"][0], original["messages"][-1]]
            if supplied:
                guide = dict(original["messages"][1])
                guide["content"] = guide["content"].replace("The current legal case follows. ", "", 1)
                expected.append(guide)
            assert messages == expected and schema == original["schema"]
            assert original["bank_sha256"] == record["bank_sha256"] == csha(study.bank)
            raw = read(ROOT / record["raw_call_path"])
            call = raw["calls"][0]
            assert call["request"]["messages"] == original["messages"]
            assert call["request"]["response_format"]["json_schema"]["schema"] == schema
            assert all(call["request"][k] == cfg["generation"][k] for k in
                       ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"))
            key = csha({"messages": original["messages"], "schema": schema,
                        "generation": cfg["generation"]})
            assert key not in study.request_cache
            study.request_cache[key] = {"response": copy.deepcopy(raw["response"]),
                                        "raw_call_path": record["raw_call_path"]}
            before.append(record)
        study.current_batch = 8
        RunStore.immutable_json(out / "mechanism_started.json", {
            "at": now(), "fixed_source_case_ids": cfg["mechanism_source_case_ids"],
            "bank_sha256": csha(study.bank), "same_bank_before_after": True,
            "skill_bodies_case_system_and_schema_unchanged": True,
            "only_position_and_temporal_link_changed": True,
            "teacher_calls_planned": 0, "not_formal_learning_or_TEST": True})
        after = study._dispatch.native(lambda r: study.answer(
            r, study.bank, "b8_position_only", "skills_after_case"), rows)
        study.grade(before + after)
        RunStore.immutable_json(out / "paired_records.json", {"before": before, "after": after})
        result = {"at": now(), "status": "completed_bounded_TRAIN_skill_position_probe",
            "bank_sha256": csha(study.bank), "fixed_sources": 16, "task_views": 32,
            "before_same_bank": metrics(before), "after_same_bank": metrics(after),
            "actual_original_parent9_B8": read(ROOT / cfg["mechanism_original_parent_run"] /
                "completion.json")["batch_summary"][7]["skills"],
            "actual_native_calls": len(study.native), "actual_teacher_responses": len(study.teachers),
            "exact_wire_reuses": len(study.reuse_events),
            "native_prompt_tokens": sum(r["response"]["prompt_tokens"] for r in study.native),
            "native_completion_tokens": sum(r["response"]["completion_tokens"] for r in study.native),
            "not_a_formal_main_result_TEST_or_independent_repeat": True}
        assert result["actual_native_calls"] <= 32 and result["actual_teacher_responses"] == 0
        RunStore.immutable_json(out / "completion.json", result)
        study.progress("mechanism_complete", state=result["status"])
    except BaseException as exc:
        RunStore.immutable_json(out / "failure.json", {"at": now(), "error": repr(exc),
            "traceback": traceback.format_exc(), "actual_native_calls": len(study.native) if study else 0})
        raise
    finally:
        names = [str(p.relative_to(ROOT)) for p in out.rglob("*") if p.is_file()]
        RunStore.immutable_json(out / "terminal_preservation.json", preserve(cfg["run_id"], "actual-terminal", names))


if __name__ == "__main__":
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main(sys.argv[1])
