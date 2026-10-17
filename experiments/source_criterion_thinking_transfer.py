"""Actual terminal-last bank versus empty on new TRAIN sources, same thinking8B.

Finite execution-affordance diagnosis, not online training or an official TEST.
The production source payload, native call, scoring and preservation are reused.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import json
import signal
import traceback
import zipfile
from pathlib import Path

from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.acquisition import compact
from legal_skill_guard.learning.experiment import ROOT, now, points, read, sha
from legal_skill_guard.learning.member_learning import ARMS, MemberLearning, paired_effect
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def prepare(config):
    config = Path(config).resolve()
    cfg = read(config)
    assert cfg["method"] == "fixed_terminal_source_criterion_thinking_transfer"
    assert cfg["generation"]["disable_thinking"] is False
    assert cfg["planned_new_native_calls"] == 34 and cfg["planned_new_teacher_calls"] == 0
    assert not config.with_suffix(".frozen.json").exists()
    assert not (ROOT / "runs" / cfg["run_id"]).exists()
    parent = ROOT / cfg["reference_run"]
    launch = read(ROOT / cfg["reference_control_directory"] / "actual_launch.json")
    proc = Path("/proc") / str(launch["pid"]) / "stat"
    if proc.exists():
        state = proc.read_text().rsplit(")", 1)[1].split()
        assert state[0] == "Z" or state[19] != launch["process_start_ticks"]
    terminal = read(ROOT / cfg["reference_terminal_preservation"])
    assert terminal["state"] == "terminal_results_preserved" and terminal["all_members_verified"]
    assert sha(terminal["archive"]) == sha(terminal["rootdisk_copy"]) == terminal["archive_sha256"]
    publications = sorted((parent / "publications").glob("b*.json"), key=lambda p: int(p.stem[1:]))
    assert publications[-1].resolve() == (ROOT / cfg["reference_publication"]).resolve()
    bank = read(publications[-1])["publication"]
    assert csha(bank) == cfg["reference_bank_canonical_sha256"]
    parent_cfg = read(ROOT / cfg["reference_config"])
    expected = {**parent_cfg["generation"], "disable_thinking": False}
    assert cfg["generation"] == expected
    assert cfg["bundled_solver_system"] == parent_cfg["bundled_solver_system"]
    packet, selection = read(ROOT / cfg["input_packet"]), read(ROOT / cfg["source_selection_record"])
    assert cfg["known_failure_source_ids"] == [89]
    assert cfg["training_ids"] == [89] + selection["selected_source_ids_in_fixed_order"] == [r["id"] for r in packet["documents"]]
    assert len(cfg["training_ids"]) == len(set(cfg["training_ids"])) == 17
    new_ids = cfg["training_ids"][1:]
    assert not set(new_ids) & (set(selection["excluded_ids"]) | set(parent_cfg["training_ids"]))
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    original = {r["id"]: r for r in author["documents"]}
    assert packet["public_hypotheses"] == author["labels"]
    for row in packet["documents"]:
        assert row == {k: original[row["id"]][k] for k in ("id", "text", "spans")}
    RunStore.immutable_json(ROOT / cfg["grading_only"], {
        "original_TRAIN_annotations": {str(d): original[d]["annotation_sets"][0]["annotations"] for d in cfg["training_ids"]},
        "no_teacher_or_lawyer_receives_this_store": True})
    # Only allocate the ordinary source-study state. No old evidence model,
    # publication editor or generation is initialized in preparation.
    preview = object.__new__(MemberLearning)
    preview.cfg, preview.labels, preview.system = cfg, packet["public_hypotheses"], cfg["bundled_solver_system"]
    preview.meter = WireClient(cfg["generation"])
    counts = {}
    for row in packet["documents"]:
        empty, learned = (preview.payload(row, arm, bank) for arm in ARMS)
        a, b = (json.loads(p["messages"][1]["content"]) for p in (empty, learned))
        assert b.pop("evidence_selection_criteria") == learned["served_criteria"] and b == a
        assert empty["schema"] == learned["schema"] and empty["messages"][0] == learned["messages"][0]
        if row["id"] == 89:
            for arm, payload in zip(ARMS, (empty, learned), strict=True):
                reference = read(ROOT / cfg["known_failure_reference_payloads"][arm])
                assert payload["messages"] == reference["messages"] and payload["schema"] == reference["schema"]
        counts[str(row["id"])] = {"empty": empty["prompt_tokens"], "skills": learned["prompt_tokens"]}
    receipt = ROOT / cfg["preparation_receipt"]
    RunStore.immutable_json(receipt, {"at": now(), "all17_original_sources_and_34_input_projections_equal": True,
        "sixteen_new_sources_and_one_predeclared_known_failure_reported_separately": True,
        "actual_terminal_last_bank_not_best_bank": True, "parent_completed_four_batches": (parent / "completion.json").exists(),
        "source_only_selection_no_annotation_or_outcome_filter": True, "prompt_tokens": counts,
        "actual_new_native_teacher_calls": [0, 0], "official_DEV_TEST_unopened": True})
    files = [p for p in (ROOT / "legal_skill_guard").rglob("*.py") if p.is_file()]
    files += [config, Path(__file__).resolve(), receipt, ROOT / "pyproject.toml"]
    files += [ROOT / cfg[k] for k in ("input_packet", "source_selection_record", "grading_only", "source_archive",
        "reference_publication", "reference_config", "reference_terminal_preservation", "inference_environment", "method_protocol")]
    files += [ROOT / p for p in cfg["supporting_evidence"]]
    files += [ROOT / p for p in cfg["known_failure_reference_payloads"].values()]
    RunStore.immutable_json(config.with_suffix(".frozen.json"), {
        "config_sha256": sha(config), "files": {str(p.resolve()): sha(p) for p in files}})
    print(compact({"prepared": cfg["run_id"], "planned_new_native_teacher_calls": [34, 0],
        "maximum_prompt_tokens": max(max(v.values()) for v in counts.values()), "frozen_files": len(set(files))}), flush=True)


class ThinkingTransfer(MemberLearning):
    def __init__(self, config):
        # A fixed-bank evaluator, with exactly the production payload/call/score
        # methods. It never invokes the online editor or loads another model.
        self.cfg, self.config_path = read(config), Path(config).resolve()
        frozen = self.config_path.with_suffix(".frozen.json")
        binding = read(frozen)
        assert binding["config_sha256"] == sha(self.config_path)
        self.bindings = {**binding["files"], str(frozen): sha(frozen)}
        self.run_id = safe_component(self.cfg["run_id"])
        self.out = ROOT / "runs" / self.run_id
        assert not self.out.exists(), "Never restart or overwrite a Run ID"
        assert self.cfg["method"] == "fixed_terminal_source_criterion_thinking_transfer"
        assert self.cfg["generation"]["disable_thinking"] is False
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["documents"]
        assert [r["id"] for r in self.training] == self.cfg["training_ids"]
        self.system = self.cfg["bundled_solver_system"]
        self.bank = read(ROOT / self.cfg["reference_publication"])["publication"]
        assert csha(self.bank) == self.cfg["reference_bank_canonical_sha256"]
        self.banks = {csha(self.bank): copy.deepcopy(self.bank)}
        self.native, self.teachers, self.own, self.first, self.units = [], [], [], [], []
        self.teacher_attempts, self.current_batch, self.stop, self.inherited_count = 0, 0, False, 0
        self.meter, self.summaries = WireClient(self.cfg["generation"]), []
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def teacher_call(self, *args, **kwargs):
        raise AssertionError("Zero teacher or learning updates in this fixed-bank transfer")

    def execute(self):
        self.check()
        self.record("declaration.json", {"at": now(), "config": self.cfg, "frozen_bindings": self.bindings.copy(),
            "bank_is_actual_terminal_last_not_best_or_rollback": True,
            "parent_was_safely_stopped_not_completed_four_batch_training": True,
            "all34_generated_before_unified_grading": True, "no_teacher_or_future_label_at_inference": True,
            "known_source89_is_explicit_diagnostic_not_an_unseen_case": True})
        entries = self.freeze_phase("known1_and_new16_thinking_transfer", self.training, ARMS)
        units = self.audit_and_grade([self.answer(e) for e in entries])
        assert len(self.native) == len(units) == len({u["response"]["raw_id"] for u in units}) == 34
        assert not self.teachers and self.teacher_attempts == 0
        groups = {a: [u for u in units if u["condition"] == a] for a in ARMS}
        new_groups = {a: [u for u in v if u["document_id"] != 89] for a, v in groups.items()}
        result = {"at": now(), "run_id": self.run_id, "actual_new_native_teacher_calls": [34, 0],
            "metrics": {a: points(v) for a, v in groups.items()},
            "new16_metrics": {a: points(v) for a, v in new_groups.items()},
            "known1_metrics": {a: points([u for u in v if u["document_id"] == 89]) for a, v in groups.items()},
            "new16_skill_effect": paired_effect(new_groups["strong_empty"], new_groups["skills"],
                seed=self.cfg["analysis"]["seed"], replicates=self.cfg["analysis"]["bootstrap_replicates"]),
            "new_units": units, "bank_unchanged": self.bank,
            "actual_native_usage": {k: sum(u["response"][k] for u in units) for k in ("prompt_tokens", "completion_tokens")},
            "new_TRAIN_transfer_not_official_TEST_or_online_learning_or_independent_repeats": True,
            "no_causal_no_think_think_interaction_claim_without_same_sources_both_modes": True}
        self.check()
        self.record("completion.json", result)
        self.preserve_phase("complete_terminal")
        RunStore.atomic_json(self.out / "progress.json", {"state": "completed", **result})
        print(compact({"completed": self.run_id, "metrics": result["metrics"],
            "new16_metrics": result["new16_metrics"], "actual_new_native_teacher_calls": [34, 0]}), flush=True)


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
        study = ThinkingTransfer(args.config)
        try:
            study.execute()
        except BaseException as exc:
            failure = {"at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
                "actual_native_teacher_calls": [len(study.native), 0],
                "all_raw_invalid_partial_phases_and_costs_retained_no_retry_or_repair": True}
            RunStore.immutable_json(study.out / "failure.json", failure)
            RunStore.atomic_json(study.out / "progress.json", {"state": "failed", **failure})
            raise


if __name__ == "__main__":
    main()
