"""CPU-only ordinary controls, gated by actual main publications, not scores.

No lawyer/teacher call, new encoder, program feature, main model replacement,
future-prefix fit or claimed native gain. Reuse the existing ordinary fitter.
"""

# ruff: noqa: E402 -- Bind the authoritative worktree for this standalone control.
from __future__ import annotations

import io
import json
import pickle
import shutil
import sys
import tarfile
import time
import traceback
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.evidence_programs import SCORER_PARAMETERS, fit_program_model
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def live(launch):
    path = Path("/proc") / str(launch["pid"]) / "stat"
    try:
        state = path.read_text().rsplit(")", 1)[1].split()
    except FileNotFoundError:
        return False
    return state[19] == launch["process_start_ticks"] and state[0] != "Z"


def preserve(batch, out, config, definition):
    files = [Path(__file__), FOLDER / "prefix_control_definition.json", FOLDER / "prefix_control_actual_launch.json"]
    files += [p for p in out.rglob("*") if p.is_file()]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in files}
    target = ROOT.parent / "legal-skill-backups" / f"{config['run_id']}-ordinary-label-prefix{batch}-CPU-control.tar.gz"
    copy = Path(config["rootdisk_backup_directory"]) / target.name
    assert not copy.exists() and target.parent.stat().st_dev != copy.parent.stat().st_dev
    metadata = json.dumps({"at": now(), "files": hashes, "main_full_source_Git_receipt": config["prelaunch_backup_receipt"],
        "same_host_not_offsite_weights_auth_or_whole_machine": True}, ensure_ascii=False, sort_keys=True).encode()
    with tarfile.open(target, "x:gz", compresslevel=2) as archive:
        for path in sorted(files):
            archive.add(path, arcname="project/" + str(path.relative_to(ROOT)), recursive=False)
        member = tarfile.TarInfo("control_manifest.json")
        member.size = len(metadata)
        archive.addfile(member, io.BytesIO(metadata))
    observed = set()
    with tarfile.open(target, "r|gz") as archive:
        for member in archive:
            assert member.isfile()
            data = archive.extractfile(member).read()
            if member.name == "control_manifest.json":
                assert data == metadata
            else:
                key = member.name.removeprefix("project/")
                assert key in hashes and __import__("hashlib").sha256(data).hexdigest() == hashes[key]
            observed.add(member.name)
    assert observed == {"project/" + p for p in hashes} | {"control_manifest.json"}
    shutil.copy2(target, copy)
    assert sha(target) == sha(copy)
    RunStore.immutable_json(out / "two_filesystem_preservation.json", {"at": now(), "archive": str(target),
        "archive_sha256": sha(target), "rootdisk_copy": str(copy), "copy_sha256": sha(copy),
        "all_members_verified": True, "different_filesystems_verified": True,
        "definition_sha256": sha(definition), "no_native_teacher_calls": True})


def main():
    definition_path = FOLDER / "prefix_control_definition.json"
    definition = read(definition_path)
    assert sha(__file__) == definition["fitter_sha256"]
    launch, cfg = read(FOLDER / "actual_launch.json"), read(definition["main_config"])
    assert sha(definition["main_config"]) == definition["main_config_sha256"]
    frozen = read(Path(definition["main_config"]).with_suffix(".frozen.json"))
    assert all(sha(p) == h for p, h in frozen["files"].items())
    background = read(ROOT / cfg["ordinary_manifest"])
    baseline_ids = background["seen_original_source_ids"]
    main_run = ROOT / "runs" / cfg["run_id"]
    controls = FOLDER / "revealed_prefix_ordinary_controls"
    assert not controls.exists()
    originals, labels = None, None
    for batch in range(1, 5):
        publication = main_run / f"publications/b{batch}.json"
        while not publication.exists():
            if not live(launch):
                RunStore.immutable_json(controls / "stopped_with_main_terminal.json", {
                    "at": now(), "waiting_batch": batch, "main_worker_terminal_verified": True,
                    "main_progress": read(main_run / "progress.json"), "no_native_teacher_calls": True})
                return
            RunStore.atomic_json(controls / "progress.json", {"at": now(), "state": "waiting_actual_publication",
                "batch": batch, "main_pid_and_ticks_currently_live": True, "no_native_teacher_calls": True})
            time.sleep(10)
        assert all(sha(p) == h for p, h in frozen["files"].items())
        seen = cfg["training_ids"][:8 * batch]
        assert read(publication)["complete_teaching_source_ids"] == seen
        ids = baseline_ids + seen
        future = cfg["training_ids"][8 * batch:]
        assert len(ids) == len(set(ids)) == 12 + 8 * batch and not set(ids) & set(future)
        if originals is None:
            assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
            with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
                author = json.loads(archive.read("contract-nli/train.json"))
            originals = {r["id"]: r for r in author["documents"]}
            labels = author["labels"]
        rows, out = [originals[d] for d in ids], controls / f"after_b{batch}"
        RunStore.immutable_json(out / "declaration.json", {"at": now(), "actual_main_publication": str(publication),
            "actual_publication_sha256": sha(publication), "background_ids": baseline_ids, "actual_new_seen_ids": seen,
            "original_fit_ids": ids, "excluded_future_ids": future, "original_training_rows_sha256": csha(rows),
            "same_scorer_parameters": SCORER_PARAMETERS, "original_scoring_pairs": len(ids) * 17,
            "matches_unique_source_label_access_not_compute_or_memory_capacity": True,
            "not_installed_in_main_method_or_a_native_performance_result": True,
            "TRAIN_container_parsed_source_prefix_values_only_used_for_fit_DEV_TEST_unopened": True})
        start = time.monotonic()
        model = fit_program_model(rows, labels, [])
        assert not model.programs and not model.queries and len(model.scoring_pairs_) == len(ids) * 17
        path = out / "ordinary.pkl"
        with path.open("xb") as stream:
            pickle.dump(model, stream, protocol=pickle.HIGHEST_PROTOCOL)
        state = {"path": str(path.resolve()), "pickle_sha256": sha(path), "seen_original_source_ids": ids,
            "original_training_rows_sha256": csha(rows), "parameters": SCORER_PARAMETERS, "programs": [], "queries": [],
            "original_scoring_pairs": len(ids) * 17}
        RunStore.immutable_json(out / "inference.manifest.json", {**state, "state_sha256": csha(state)})
        RunStore.immutable_json(out / "completion.json", {"at": now(), "batch": batch,
            "fit_seconds": time.monotonic() - start, "actual_source_count": len(ids),
            "actual_original_scoring_pairs": len(model.scoring_pairs_), "native_teacher_calls": [0, 0],
            "future_prefix_excluded": True, "main_M2_unchanged": sha(background["path"]) == background["pickle_sha256"],
            "not_a_claim_of_better_final_answers": True})
        preserve(batch, out, cfg, definition_path)
    RunStore.atomic_json(controls / "progress.json", {"at": now(), "state": "all_four_controls_fitted",
        "actual_fit_source_counts": [20, 28, 36, 44], "native_teacher_calls": [0, 0],
        "not_main_training_completion_or_comparator_native_results": True})


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        RunStore.immutable_json(FOLDER / "prefix_control_failure.json", {"at": now(), "error": repr(error),
            "traceback": traceback.format_exc(), "no_native_teacher_calls_or_main_changes": True})
        raise
