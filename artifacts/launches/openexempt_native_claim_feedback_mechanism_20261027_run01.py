"""One bounded TRAIN revision through the existing learner; not a paper build."""
import copy
import fcntl
import sys
import traceback
from pathlib import Path

from experiments.openexempt_online import Online, preserve
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read
from legal_skill_guard.openexempt import ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def main(config_path):
    cfg = read(config_path)
    assert cfg["study_kind"] == "single_mature_parent_TRAIN_revision_not_formal_learning"
    assert cfg["max_candidate_attempts"] == cfg["planned_teacher_responses_max"] == 1
    out = ROOT / "runs" / cfg["run_id"]
    if out.exists():
        raise FileExistsError("Never overwrite or resume a selected mechanism outcome")
    study = None
    try:
        source = ROOT / "runs" / cfg["mechanism_training_record_source_run"]
        source_cfg = read(ROOT / cfg["mechanism_training_source_config"])
        assert all(source_cfg[k] == cfg[k] for k in ("generation", "input_packet", "grading_directory"))
        study = Online(Path(config_path))
        observations, empty = {}, []
        for batch in range(1, 9):
            records = read(source / "batches" / f"b{batch}_prequential_records.json")
            empty.extend(records["empty"])
            observations.update({(r["case_id"], r["family"]): r for r in records["skills"]})
            for decision in read(source / "publications" / f"b{batch}.json")["training_decisions"]:
                if decision.get("accepted"):
                    observations = {(r["case_id"], r["family"]): r for r in decision["actual_replay"]}
        assert len(observations) == len(empty) == 256
        parent_sha = csha(study.bank)
        assert parent_sha == cfg["mechanism_parent_bank_sha256"]
        assert all(r["bank_sha256"] == parent_sha for r in observations.values())
        # All origins are imported, without quality selection; no cached score is an answer.
        originals = 0
        for path in sorted((source / "native").rglob("*.json")):
            if path.name.endswith((".input.json", ".answer.json")):
                continue
            raw, supplied = read(path), read(path.with_suffix(".input.json"))
            assert raw.get("transport_error") is None and len(raw["calls"]) == 1
            wire, response = raw["calls"][0]["request"], raw["calls"][0]["response"]
            assert wire["messages"] == supplied["messages"]
            assert wire["response_format"]["json_schema"]["schema"] == supplied["schema"]
            assert all(wire[k] == cfg["generation"][k] for k in
                       ("model", "temperature", "top_p", "top_k", "max_tokens", "seed"))
            assert wire.get("chat_template_kwargs", {}).get("enable_thinking", True) == (
                not cfg["generation"]["disable_thinking"])
            assert response["id"] == raw["response"]["raw_id"]
            assert response["usage"]["completion_tokens"] == raw["response"]["completion_tokens"]
            assert response["usage"]["prompt_tokens"] == raw["response"]["prompt_tokens"]
            assert (response["choices"][0]["message"].get("content") or "").strip() == raw["response"]["content"]
            key = csha({"messages": supplied["messages"], "schema": supplied["schema"],
                        "generation": cfg["generation"]})
            assert key not in study.request_cache
            study.request_cache[key] = {"response": copy.deepcopy(raw["response"]),
                                        "raw_call_path": str(path.relative_to(ROOT))}
            originals += 1
        assert originals == read(source / "completion.json")["actual_native_calls"]
        study.latest = dict(observations)
        study.prequential_empty = empty
        # This probe's initial frozen comparator really is the inherited final bank.
        study.prequential_frozen = list(observations.values())
        study.current_batch = cfg["mechanism_current_batch"]
        previous = read(source / "publications" / "b7.json")
        assert previous["bank_sha256"] == parent_sha
        RunStore.immutable_json(out / "publications" / "b7.json", previous)
        current = [r for r in study.rows if r["batch"] == study.current_batch]
        RunStore.immutable_json(out / "mechanism_started.json", {
            "at": now(), "source_run": source.name, "actual_parent_bank_sha256": parent_sha,
            "all128_previously_seen_TRAIN_sources": True, "all_raw_origins_hash_bound": originals,
            "not_empty_start_or_an_independent_learning_repeat": True,
            "no_TEST_cases_or_old_teacher_response_import": True})
        publication = study.update(current, study.rows,
            [observations[(r["case_id"], r["family"])] for r in current])
        result = {"at": now(), "status": "completed_bounded_TRAIN_teacher_mechanism_not_formal_learning",
            "parent_bank_sha256": parent_sha, "final_bank_sha256": csha(study.bank),
            "parent_all128_TRAIN": metrics(list(observations.values())),
            "actual_after_all128_TRAIN": metrics(list(study.latest.values())),
            "accepted": any(d.get("accepted") for d in publication["training_decisions"]),
            "actual_native_calls": len(study.native), "prior_raw_origins_not_new_calls": originals,
            "exact_wire_reuses_not_independent_draws": len(study.reuse_events),
            "actual_teacher_responses": len(study.teachers), "actual_teacher_attempts": study.teacher_attempts,
            "native_prompt_tokens": sum(r["response"]["prompt_tokens"] for r in study.native),
            "native_completion_tokens": sum(r["response"]["completion_tokens"] for r in study.native),
            "not_a_TEST_result_or_permission_to_seed_formal_learning_with_this_bank": True}
        RunStore.immutable_json(out / "completion.json", result)
        study.progress("mechanism_complete", state=result["status"])
    except BaseException as exc:
        RunStore.immutable_json(out / "failure.json", {
            "at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
            "actual_native_calls": len(study.native) if study else 0,
            "actual_teacher_attempts": study.teacher_attempts if study else 0,
            "no_retry_or_answer_selection": True})
        raise
    finally:
        names = [str(p.relative_to(ROOT)) for p in out.rglob("*") if p.is_file()]
        RunStore.immutable_json(out / "terminal_preservation.json", preserve(cfg["run_id"], "actual-terminal", names))


if __name__ == "__main__":
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main(sys.argv[1])
