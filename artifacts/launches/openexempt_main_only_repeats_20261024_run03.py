"""User-approved finite queue: adopt current45, first-commit45, main145/245.
ACE/Text extra builds are deferred, not retried or relabelled as successes.
"""
from __future__ import annotations
import argparse
import copy
import fcntl
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import selectors
import signal
import sys
import time
import traceback

ROOT = Path("/media/sangfor/vdb/legal-skill-evolve")
sys.path.insert(0, str(ROOT))
PHASE_FILE = ROOT / "artifacts/launches/openexempt_text45_legacy_ablations_then_phase_repeats_20261024_run02.py"
PHASE_SHA = "19a6ef15787a4fe07efc8d48876051fe128525a20804b09781dfc7a612551948"
spec = importlib.util.spec_from_file_location("preserved_phase_handoff_ops", PHASE_FILE)
phase = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phase)
OLD_OUT = phase.OUT
OLD_PID, OLD_START = 3019419, "477802191"
CHILD_PID, CHILD_START = 4100472, "482117804"
OUT = ROOT / "artifacts/launches/openexempt_main_only_repeats_20261024_run03"
RUN = "legal_openexempt_main_only_repeats_20261024_run03"
PROTOCOL = "docs/research/OPENEXEMPT_SINGLE_BASELINE_BUILD_AMENDMENT_20261024.md"
COMMITS = (*phase.COMMITS, "ebfc0328c867132802850d98832e3e5924778cdf")
ORIGINAL_STAGES = copy.deepcopy(phase.old.STAGES)
STAGES = [copy.deepcopy(ORIGINAL_STAGES[i]) for i in (0, 1, 2, 4)]
STAGES[3]["ceiling"] = 4119
DEFERRED = [s for s in ORIGINAL_STAGES if s["learner"] != "main"]
phase.OUT, phase.RUN, phase.PROTOCOL = OUT, RUN, PROTOCOL
phase.old.STAGES = STAGES

def state(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[0], fields[19]
    except (FileNotFoundError, ProcessLookupError):
        return None, None

def archive(label):
    names = [str(p.relative_to(ROOT)) for p in OUT.rglob("*")
             if p.is_file() and p.name != "progress.json"]
    names += [str(Path(__file__).relative_to(ROOT)), str(PHASE_FILE.relative_to(ROOT)),
              str(phase.OLD.relative_to(ROOT)), PROTOCOL, phase.OLD_ENV,
              str(phase.NEW_UNIT.relative_to(ROOT)), "ops/legal-qwen3-8b.service"]
    names += [str(p.relative_to(ROOT)) for p in OLD_OUT.glob("*.json")
              if p.name != "progress.json"]
    for s in STAGES:
        p = ROOT / s["path"]
        names += [str(p.relative_to(ROOT)), str(p.with_suffix(".frozen.json").relative_to(ROOT))]
        newer = ROOT / s["path"].replace("20261023_run02", "20261023_run03")
        names += [str(p.relative_to(ROOT)) for p in (newer, newer.with_suffix(".frozen.json")) if p.is_file()]
    versions = ROOT / "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/runtime_versions_20261023"
    names += [str(p.relative_to(ROOT)) for p in versions.glob("*.py")]
    receipt = phase.preserve(RUN, label, sorted(set(names)))
    if len({Path(v["path"]).stat().st_dev for v in receipt["paths"]}) != 2:
        raise RuntimeError("Require two preservation devices")
    phase.save(label + "_preservation", receipt)

phase.archive = archive

def plan():
    if phase.sha(PHASE_FILE) != PHASE_SHA or phase.sha(phase.OLD) != phase.OLD_SHA:
        raise RuntimeError("Original controllers changed")
    old_queued = phase.read(OLD_OUT / "queued.json")
    for name, digest in old_queued["controller_sources"].items():
        if phase.sha(ROOT / name) != digest:
            raise RuntimeError("Preserve the exact original queue source: " + name)
    if (state(OLD_PID)[1] != OLD_START or state(CHILD_PID)[1] != CHILD_START
            or phase.old.ticks(phase.old.MODEL_PID) != phase.old.MODEL_START):
        raise RuntimeError("Adopt only the exact current controller, learner and original model")
    for reader, writer in ((3, 1), (5, 2)):
        if os.readlink(f"/proc/{OLD_PID}/fd/{reader}") != os.readlink(f"/proc/{CHILD_PID}/fd/{writer}"):
            raise RuntimeError("Captured child output pipe identity changed")
    packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    if packages != old_queued["packages"]:
        raise RuntimeError("Do not change the Python environment during adoption")
    ledger = ROOT / phase.read(phase.old.FIRST)["teacher"]["ledger"]
    if phase.read(ledger)["max_invocations"] != 4023:
        raise RuntimeError("Current45 ceiling must remain4023")
    for s in ORIGINAL_STAGES:
        p = ROOT / s["path"]
        if phase.sha(p) != s["config_sha256"] or phase.sha(p.with_suffix(".frozen.json")) != s["frozen_sha256"]:
            raise RuntimeError("Do not overwrite any old profile")
    if any((ROOT / "runs" / s["run_id"]).exists() for s in DEFERRED):
        raise RuntimeError("Deferred builds must be genuinely unstarted")
    return {"controller_sources": {str(p.relative_to(ROOT)): phase.sha(p) for p in
                (Path(__file__), PHASE_FILE, phase.OLD, ROOT / PROTOCOL, phase.NEW_UNIT)},
            "original_model": [phase.old.MODEL_PID, phase.old.MODEL_START],
            "original_queue": [OLD_PID, OLD_START], "adopted_learner": [CHILD_PID, CHILD_START],
            "stages": STAGES, "deferred_unstarted": DEFERRED, "packages": packages,
            "source_promotion": list(COMMITS), "active_ceiling_unchanged": 4023,
            "final_ceiling": 4119, "formal_real_arms": 12, "TEST_sources": 128}

def adopt_current(queued):
    selector = selectors.DefaultSelector()
    logs = []
    for reader, filename in ((3, "adopted_whole45_stdout.log"), (5, "adopted_whole45_stderr.log")):
        fd = os.open(f"/proc/{OLD_PID}/fd/{reader}", os.O_RDONLY | os.O_NONBLOCK)
        log = (OUT / filename).open("xb")
        selector.register(fd, selectors.EVENT_READ, log)
        logs.append(log)
    # Only the orchestration parent is held. Its actual child is never signalled.
    if state(OLD_PID)[1] != OLD_START or state(CHILD_PID)[1] != CHILD_START:
        raise RuntimeError("Live handles changed before the exact handoff")
    os.kill(OLD_PID, signal.SIGSTOP)
    for _ in range(50):
        if state(OLD_PID)[0] in ("T", "t"):
            break
        time.sleep(0.1)
    if state(OLD_PID)[0] not in ("T", "t"):
        raise RuntimeError("Original controller did not enter its hold")
    phase.save("original_controller_held_child_uninterrupted", {
        "original_queue": [OLD_PID, OLD_START], "child": [CHILD_PID, CHILD_START],
        "original_model": queued["original_model"], "only_signalled_original_queue_parent": True,
        "captured_stdout_stderr_drained_by_successor": True,
        "deferred_builds_cannot_be_launched_by_the_held_controller": True})
    while True:
        for key, _ in selector.select(timeout=15):
            try:
                data = os.read(key.fd, 65536)
            except BlockingIOError:
                continue
            if data:
                key.data.write(data)
                key.data.flush()
            else:
                selector.unregister(key.fd)
                os.close(key.fd)
        status, ticks = state(CHILD_PID)
        if ticks != CHILD_START or status == "Z":
            break
        if state(OLD_PID)[1] != OLD_START or state(OLD_PID)[0] not in ("T", "t"):
            raise RuntimeError("The superseded controller must stay held")
        phase.RunStore.atomic_json(OUT / "progress.json", {
            "at": phase.now(), "state": "adopting_existing_whole45",
            "child_pid": CHILD_PID, "child_start_ticks": CHILD_START,
            "no_learner_restart_or_model_call": True})
    for key in list(selector.get_map().values()):
        while True:
            try:
                data = os.read(key.fd, 65536)
            except BlockingIOError:
                break
            if not data:
                break
            key.data.write(data)
        selector.unregister(key.fd)
        os.close(key.fd)
    selector.close()
    for log in logs:
        log.close()
    # The original child has naturally exited. Never kill a live learner/cgroup.
    if state(CHILD_PID)[1] == CHILD_START and state(CHILD_PID)[0] != "Z":
        raise RuntimeError("Cannot retire an owner while its original learner is live")
    if state(OLD_PID)[1] == OLD_START:
        os.kill(OLD_PID, signal.SIGKILL)
    phase.save("superseded_controller_retired_after_child_natural_exit", {
        "old_queue_pid": OLD_PID, "no_learner_or_model_signal": True,
        "intentional_scheduler_retirement_not_failed_training": True})
    complete = phase.old.terminal(ROOT / STAGES[0]["path"])
    phase.save("adopted_whole45_complete", complete)
    archive("adopted_whole45_complete")

def transition(queued):
    for config in (phase.old.FIRST, *(ROOT / s["path"] for s in STAGES[:2])):
        phase.old.terminal(config)
    phase.verify_recovery()
    if {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()} != queued["packages"]:
        raise RuntimeError("Python package environment changed")
    if phase.command([phase.GIT, "status", "--porcelain", "--untracked-files=no"], env=phase.GIT_ENV).stdout:
        raise RuntimeError("Preserve unrelated tracked changes before source promotion")
    phase.save("before_source_transition", {"original_source_HEAD":
        phase.command([phase.GIT, "rev-parse", "HEAD"], env=phase.GIT_ENV).stdout.strip(),
        "approved_commits": list(COMMITS)})
    archive("before_source_transition")
    for commit in COMMITS:
        phase.command([phase.GIT, "-c", "user.name=Codex", "-c", "user.email=codex@localhost", "cherry-pick", commit], env=phase.GIT_ENV)
    phase.command([str(ROOT / ".venv/bin/python"), "-c",
        "from pathlib import Path;from legal_skill_guard.learning import runtime_sources as s;"
        "root=Path.cwd();s.validate_bundle(root);"
        "[s.verify_revision(root,n,h) for n,vs in s.HISTORICAL.items() for h in vs]"])
    capture = phase.capture_service(queued)
    phase.timing_only(capture)
    run_map = {s["run_id"]: s["run_id"].replace("20261023_run02", "20261023_run03") for s in STAGES[2:]}
    actual = []
    for ordinal, stage in enumerate(STAGES[2:], 3):
        path = ROOT / stage["path"]
        if (phase.sha(path) != stage["config_sha256"]
                or phase.sha(path.with_suffix(".frozen.json")) != stage["frozen_sha256"]
                or (ROOT / "runs" / stage["run_id"]).exists()):
            raise RuntimeError("Original prospective main profile is not untouched")
        cfg = phase.new_profile(phase.read(path), stage, phase.ENVIRONMENT, run_map)
        cfg["teacher"]["total_invocation_budget"] = stage["ceiling"]
        cfg["source_rebase_reason"] = (
            "User-approved baseline-repeat deferral: only fresh main145/245; unchanged learning "
            "policy, source data, teacher settings and per-answer budgets. Cumulative ceilings4087/4119; "
            "all historical reservations and superseded profiles retained.")
        cfg["prospective_serial_order_after_current_ACE_and_static"] = ordinal
        target = ROOT / stage["path"].replace("20261023_run02", "20261023_run03")
        phase.RunStore.immutable_json(target, cfg)
        code = ("from pathlib import Path;from experiments.openexempt_online import freeze;"
                "from legal_skill_guard.learning import runtime_sources as s;"
                "root=Path.cwd();cfg=Path(" + repr(str(target)) + ");"
                "extras=[root/n for n in s.CURRENT];"
                "extras+=list((root/s.SNAPSHOTS).glob('*.py'));"
                "extras+=list(root.glob('third_party/ace/prompts/*.py'));"
                "extras+=[root/'third_party/ace/LICENSE.txt',root/'third_party/ace/NOTICE.md',"
                "root/'experiments/openexempt_frozen_eval.py',root/s.PROTOCOL,"
                "root/" + repr(PROTOCOL) + ",root/" + repr(str(Path(__file__).relative_to(ROOT))) + ","
                "root/" + repr(str(PHASE_FILE.relative_to(ROOT))) + ",root/'ops/" + phase.UNIT + "'];"
                "freeze(cfg,additional_sources=extras)")
        phase.command([str(ROOT / ".venv/bin/python"), "-c", code])
        actual.append({**stage, "path": str(target.relative_to(ROOT)), "run_id": cfg["run_id"],
            "config_sha256": phase.sha(target), "frozen_sha256": phase.sha(target.with_suffix(".frozen.json"))})
    phase.save("two_actual_new_frozen_main_profiles", {"stages": actual, "actual_model": capture,
        "deferred_ACE_Text_profiles_not_created_or_frozen": True, "quota_not_extended_during_freeze": True})
    archive("new_execution_and_two_main_profiles")
    return actual

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("inspect", "run"))
    args = parser.parse_args()
    queued = plan()
    if args.action == "inspect":
        print(json.dumps({"plan_valid": True, "adopt_current_without_restart": True,
            "remaining_learning_flows": 4, "deferred_builds": len(DEFERRED),
            "formal_arms": 12, "final_ceiling": 4119, "no_state_change_or_model_call": True}))
        return
    OUT.mkdir(exist_ok=False)
    phase.save("queued", queued)
    ledger = ROOT / phase.read(phase.old.FIRST)["teacher"]["ledger"]
    baseline = phase.read(ledger)
    phase.save("ledger_at_queue_unchanged", baseline)
    archive("queued")
    adopt_current(queued)
    predecessor, ceiling = ROOT / STAGES[0]["path"], 4023
    first = STAGES[1]
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        phase.old.unchanged(first, phase.OLD_SHA, queued["packages"])
        phase.extend(ledger, baseline, ceiling, first, predecessor, queued)
    phase.command([str(ROOT / ".venv/bin/python"), "-u", "-m", first["module"], "run", str(ROOT / first["path"])])
    phase.save("first_commit45_completed", phase.old.terminal(ROOT / first["path"]))
    predecessor, ceiling = ROOT / first["path"], first["ceiling"]
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stages = transition(queued)
    for stage in stages:
        with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            path = ROOT / stage["path"]
            if (phase.sha(path) != stage["config_sha256"]
                    or phase.sha(path.with_suffix(".frozen.json")) != stage["frozen_sha256"]
                    or (ROOT / "runs" / stage["run_id"]).exists()
                    or any(phase.sha(ROOT / n) != h for n, h in phase.read(path.with_suffix(".frozen.json"))["files"].items())):
                raise RuntimeError("Require exact fresh main profiles and frozen sources")
            phase.extend(ledger, baseline, ceiling, stage, predecessor, queued)
        phase.command([str(ROOT / ".venv/bin/python"), "-u", "-m", stage["module"], "run", str(path)])
        phase.save(stage["run_id"] + "_completed", phase.old.terminal(path))
        predecessor, ceiling = path, stage["ceiling"]
    phase.save("all_four_retained_learning_flows_complete_NOT_TEST", {
        "runs": [STAGES[0]["run_id"], STAGES[1]["run_id"]] + [s["run_id"] for s in stages],
        "deferred": [s["run_id"] for s in DEFERRED],
        "final_TEST_requires_all12_actual_arms_and_frozen_analysis": True})
    archive("all_four_retained_learning_flows_complete_NOT_TEST")

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if OUT.is_dir() and not (OUT / "handoff_failed.json").exists():
            phase.save("handoff_failed", {"error": repr(error), "traceback": traceback.format_exc(),
                "no_failed_stage_success_retry_or_TEST": True})
            archive("failed_handoff_terminal")
        raise

