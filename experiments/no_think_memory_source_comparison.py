"""One fixed-bank, whole16 source/decoder diagnosis; zero teacher calls."""

from __future__ import annotations

import argparse
import copy
import fcntl
import json
import shutil
import traceback
import zipfile
from pathlib import Path

from experiments.r3_access_channel_diagnosis import verified_archive
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.acquisition import AcquisitionStudy, compact
from legal_skill_guard.learning.experiment import ROOT, Comparison, now, points, read, sha
from legal_skill_guard.learning.member_contract import one_copy_criteria
from legal_skill_guard.learning.member_learning import MemberLearning, paired_effect
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

ARMS = ["no_think_M2_R2", "no_think_source_R2", "no_think_source_empty"]


def make_payload(cfg, row, arm, bank, meter):
    parent = ROOT / cfg["reference_run"]
    batch = 1 + cfg["training_ids"].index(row["id"]) // 8
    origin = (parent / f"prospective/b{batch}_before/strong_empty/{row['id']}.json"
        if arm == ARMS[2] else parent / f"prospective/b2_after_all_seen/skills/{row['id']}.json")
    p = copy.deepcopy(read(origin))
    body = json.loads(p["messages"][1]["content"])
    assert body["full_contract_with_original_span_markers"] == marked_text(row)
    if arm != ARMS[2]:
        assert p["bank"] == bank and body["evidence_selection_criteria"] == one_copy_criteria(bank)
    else:
        assert not p["bank"] and "evidence_selection_criteria" not in body
    if arm == ARMS[1]:
        for question in body["hypotheses"].values():
            question["fallible_evidence_candidates"] = []
            assert not question["additional_source_read_indices"]
        body["candidate_original_text"] = {}
        p["messages"][1]["content"] = compact(body)
        p["fixed_ordinary_model_state"] = None
        p["actual_factual_trace"] = {"actual_source_executions": {},
            "ordinary_retriever_used": False, "all_ordinary_hint_fields_removed": True,
            "original_source_remains_complete": True}
    p.update(arm=arm, reference_payload=str(origin), reference_payload_sha256=sha(origin),
        prompt_tokens=meter.token_count(messages=p["messages"]),
        bank=copy.deepcopy(bank) if arm != ARMS[2] else [],
        bank_sha256=csha(bank) if arm != ARMS[2] else csha([]),
        inference_disable_thinking=True, no_teacher_or_label_lookup_at_inference=True,
        stored_reference_ordinary_candidates_reused_not_refit=arm == ARMS[0])
    assert p["prompt_tokens"] + cfg["generation"]["max_tokens"] <= cfg["generation"]["context_tokens"]
    return p


def prepare(config):
    config = Path(config).resolve()
    cfg, frozen = read(config), config.with_suffix(".frozen.json")
    assert not frozen.exists() and not (ROOT / "runs" / cfg["run_id"]).exists()
    assert cfg["generation"]["disable_thinking"] is True
    assert cfg["planned_new_native_calls"] == 48 and cfg["planned_new_teacher_calls"] == 0
    assert cfg["diagnostic_arms"] == ARMS
    assert cfg["diagnostic_source_ids"] == [384] + [d for d in cfg["training_ids"][:16] if d != 384]
    parent = ROOT / cfg["reference_run"]
    assert read(parent / "failure.json")["actual_native_teacher_calls"] == [72, 2]
    terminal = read(ROOT / cfg["reference_terminal_preservation"])
    assert terminal["all_members_verified"] and sha(terminal["archive"]) == sha(terminal["rootdisk_copy"]) == terminal["archive_sha256"]
    previous_definition = read(ROOT / cfg["reference_control_directory"] / "terminal_preservation_definition.json")
    previous_generation = read(previous_definition["config"])["generation"]
    assert {k: v for k, v in cfg["generation"].items() if k != "disable_thinking"} == previous_generation
    for name in ("actual_launch.json", "terminal_preservation_actual_launch.json", "completed_boundary_observer_actual_launch.json"):
        launch = read(ROOT / cfg["reference_control_directory"] / name)
        proc = Path("/proc") / str(launch["pid"])
        if proc.exists():
            state = (proc / "stat").read_text().rsplit(")", 1)[1].split()
            assert state[0] == "Z" or state[19] != launch["process_start_ticks"]
    env = read(ROOT / cfg["inference_environment"])
    proc = Path("/proc") / str(env["pid"])
    assert (proc / "stat").read_text().rsplit(")", 1)[1].split()[19] == env["process_start_ticks"]
    assert [v.decode() for v in (proc / "cmdline").read_bytes().split(b"\0") if v] == env["actual_argv"]
    packet = read(ROOT / cfg["input_packet"])
    assert [v["id"] for v in packet["documents"]] == cfg["training_ids"]
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    original = {d["id"]: d for d in author["documents"]}
    assert packet["public_hypotheses"] == author["labels"]
    assert all(row == {k: original[row["id"]][k] for k in ("id", "text", "spans")} for row in packet["documents"])
    bank = read(ROOT / cfg["reference_publication"])["publication"]
    assert csha(bank) == cfg["reference_bank_canonical_sha256"]
    rows = {r["id"]: r for r in packet["documents"]}
    meter, counts, files = WireClient(cfg["generation"]), {}, set()
    for d in cfg["diagnostic_source_ids"]:
        rendered = {arm: make_payload(cfg, rows[d], arm, bank, meter) for arm in ARMS}
        a, b, empty = (json.loads(rendered[arm]["messages"][1]["content"]) for arm in ARMS)
        stripped = copy.deepcopy(a)
        for q in stripped["hypotheses"].values():
            q["fallible_evidence_candidates"] = []
        stripped["candidate_original_text"] = {}
        assert stripped == b
        assert b.pop("evidence_selection_criteria") == one_copy_criteria(bank) and b == empty
        assert len({compact(p["schema"]) for p in rendered.values()}) == 1
        assert len({p["messages"][0]["content"] for p in rendered.values()}) == 1
        for arm, p in rendered.items():
            counts[f"{d}:{arm}"] = p["prompt_tokens"]
            files.add(Path(p["reference_payload"]))
    references = read(parent / "scored_phases/b2_after_all_seen.json")["units"]
    references += [u for batch in (1, 2) for u in read(parent / f"b{batch}_before_complete.json")["units"] if u["condition"] == "strong_empty"]
    assert len(references) == len({u["response"]["raw_id"] for u in references}) == 32
    files.update(Path(u[k]) for u in references for k in ("payload", "raw_artifact"))
    files.update(parent / p for p in ("failure.json", "scored_phases/b2_after_all_seen.json", "b1_before_complete.json", "b2_before_complete.json"))
    receipt = ROOT / cfg["preparation_receipt"]
    RunStore.immutable_json(receipt, {"at": now(), "all48_source_schema_criteria_and_projection_checks_equal": True,
        "no_think_tokenizer_profile_matches_generation": True, "prospective_prompt_tokens": counts,
        "first_source384_replays_prior_failed_request_only_disabling_thinking": True,
        "actual_new_native_teacher_calls": [0, 0], "official_DEV_TEST_unopened": True})
    files.update(p for p in (ROOT / "legal_skill_guard").rglob("*.py") if p.is_file())
    files.update([config, Path(__file__).resolve(), receipt, ROOT / "experiments/r3_access_channel_diagnosis.py"])
    files.update(ROOT / cfg[k] for k in ("input_packet", "grading_only", "source_archive", "ordinary_manifest",
        "solver_system_reference", "inference_environment", "method_protocol", "reference_publication", "reference_terminal_preservation"))
    files.add(Path(read(ROOT / cfg["ordinary_manifest"])["path"]))
    RunStore.immutable_json(frozen, {"config_sha256": sha(config), "files": {str(p.resolve()): sha(p) for p in sorted(files)}})
    members = {str(p.relative_to(ROOT)): sha(p) for p in files}
    members[str(frozen.relative_to(ROOT))] = sha(frozen)
    members.update({str(p.relative_to(ROOT)): sha(p) for p in (ROOT / ".git").rglob("*") if p.is_file()})
    target = ROOT.parent / "legal-skill-backups" / (cfg["run_id"] + "-full-source-Git-before-native.tar.gz")
    count = verified_archive(target, members, {"at": now(), "files": members, "full_Git_included": True,
        "same_host_not_offsite_weights_or_auth": True, "actual_new_native_teacher_calls": [0, 0]})
    dest = Path(cfg["rootdisk_backup_directory"]) / target.name
    assert not dest.exists() and dest.parent.stat().st_dev != target.stat().st_dev
    shutil.copy2(target, dest)
    assert sha(dest) == sha(target)
    RunStore.immutable_json(ROOT / cfg["prelaunch_backup_receipt"], {"at": now(), "archive": str(target),
        "archive_sha256": sha(target), "rootdisk_copy": str(dest), "copy_sha256": sha(dest),
        "all_members_verified": True, "members": count, "different_filesystems_verified": True,
        "full_Git_included": True, "same_host_not_offsite_weights_or_auth": True})
    print(compact({"prepared": cfg["run_id"], "planned_new_native_teacher_calls": [48, 0],
        "maximum_prompt_tokens": max(counts.values()), "bound_files": len(files), "verified_archive_members": count}), flush=True)


class Study(MemberLearning):
    def __init__(self, config):
        AcquisitionStudy.__init__(self, config)
        assert self.cfg["generation"]["disable_thinking"] is True
        self.bank = read(ROOT / self.cfg["reference_publication"])["publication"]
        assert csha(self.bank) == self.cfg["reference_bank_canonical_sha256"]

    def progress(self, stage, **extra):
        Comparison.progress(self, stage, diagnostic_only=True, **extra)

    def payload(self, row, arm, bank):
        return make_payload(self.cfg, row, arm, bank, self.meter)

    def teacher_call(self, *args, **kwargs):
        raise AssertionError("No teacher calls in this declared fixed-bank comparison")

    def execute(self):
        self.check()
        self.record("declaration.json", {"at": now(), "config": self.cfg, "frozen_bindings": self.bindings.copy(),
            "all48_generated_before_unified_effect_grading": True, "first_replay_invalid_stops_without_effect_grading": True,
            "historical32_answers_are_references_not_new_calls": True})
        lookup = {row["id"]: row for row in self.training}
        entries = self.freeze_phase("fixed_R2_no_think", [lookup[d] for d in self.cfg["diagnostic_source_ids"]], ARMS)
        answers = []
        for index, entry in enumerate(entries):
            unit = self.answer(entry)
            answers.append(unit)
            if index == 0 and not unit["native_schema_valid"]:
                raise ValueError("First failed-case replay still invalid; raw retained, no retry or repair")
        scored = self.audit_and_grade(answers)
        parent = ROOT / self.cfg["reference_run"]
        references = {"old_think_M2_R2": read(parent / "scored_phases/b2_after_all_seen.json")["units"],
            "old_think_source_empty": [u for b in (1, 2) for u in read(parent / f"b{b}_before_complete.json")["units"] if u["condition"] == "strong_empty"]}
        groups = {arm: [u for u in scored if u["condition"] == arm] for arm in ARMS} | references
        assert all(len(v) == 16 for v in groups.values())
        contrasts = [(ARMS[2], ARMS[1]), (ARMS[0], ARMS[1]), ("old_think_source_empty", ARMS[1]), ("old_think_M2_R2", ARMS[0])]
        result = {"at": now(), "run_id": self.run_id, "actual_new_native_teacher_calls": [len(self.native), 0],
            "explicit_historical_reference_answers": 32, "metrics": {a: points(v) for a, v in groups.items()},
            "comparisons": {a + "__to__" + b: paired_effect(groups[a], groups[b],
                seed=self.cfg["analysis"]["seed"], replicates=self.cfg["analysis"]["bootstrap_replicates"]) for a, b in contrasts},
            "new_units": scored, "actual_new_native_usage": {k: sum(v["response"][k] for v in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "seen16_fixed_bank_development_not_online_training_independent_repeats_or_official_TEST": True,
            "old_invalid_reference_kept_in_original_denominators": True}
        assert len(self.native) == 48 and not self.teachers and self.teacher_attempts == 0
        self.check()
        self.record("completion.json", result)
        self.preserve_phase("complete_terminal")
        RunStore.atomic_json(self.out / "progress.json", {"state": "completed", **result})
        print(compact({"completed": self.run_id, "metrics": result["metrics"], "actual_new_native_teacher_calls": [48, 0]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.config)
        return
    with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        study = Study(args.config)
        try:
            study.execute()
        except BaseException as error:
            failure = {"at": now(), "error": repr(error), "traceback": traceback.format_exc(),
                "actual_native_teacher_calls": [len(study.native), len(study.teachers)],
                "all_raw_invalid_and_partial_costs_preserved_no_retry_or_repair": True}
            RunStore.immutable_json(study.out / "failure.json", failure)
            RunStore.atomic_json(study.out / "progress.json", {"state": "failed", **failure})
            raise


if __name__ == "__main__":
    main()
