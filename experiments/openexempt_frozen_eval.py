"""Frozen EC/EV comparison: existing actors/scorer, no teacher or skill updates.

This entry point is not used until methods, publications and the complete matrix
are fixed. It never imports a TEST packet at module import or plan validation.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import signal
import traceback
from pathlib import Path

from experiments.openexempt_ace_online import ACEOnline
from experiments.openexempt_online import Online, freeze, paired_effect, preserve
from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.learning.experiment import Comparison, now, read, sha
from legal_skill_guard.learning.task_scoped_skills import validate_scoped_bank
from legal_skill_guard.openexempt import FAMILIES, ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

SHARED_ACTOR_FILES = (
    "experiments/openexempt_online.py",
    "legal_skill_guard/openexempt.py",
    "legal_skill_guard/learning/legal_namespace.py",
    "legal_skill_guard/learning/task_scoped_skills.py",
)
ACE_ACTOR_FILES = ("experiments/openexempt_ace_online.py", "legal_skill_guard/learning/openexempt_ace.py")
ROLES = {"strong_empty", "evolved", "B1_frozen", "experience", "ablation"}


def fixed_banks(cfg):
    """Check completed TRAIN provenance without loading TEST questions/targets."""
    if (cfg.get("evaluation_role") != "sealed_frozen_comparison"
            or cfg.get("final_matrix_frozen") is not True
            or cfg.get("no_validation_set") is not True
            or "teacher" in cfg
            or cfg.get("execution_contract") != "direct_statutory_claims"
            or cfg.get("execution_contract_version") != 14):
        raise ValueError("Declare a frozen inference-only common14 comparison, without a teacher")
    safe_component(cfg["run_id"])
    for key in ("source_cases", "training_source_cases", "training_batch_source_cases"):
        if type(cfg.get(key)) is not int or cfg[key] < 1:
            raise ValueError("Positive complete evaluation/training source counts are required")
    if not (ROOT / cfg["statistics_plan"]).is_file():
        raise FileNotFoundError("Freeze the explicit statistics plan before TEST prediction")
    arms = cfg["arms"]
    names = [safe_component(a["name"]) for a in arms]
    if len(names) != len(set(names)) or not ROLES.issuperset(a["role"] for a in arms):
        raise ValueError("Unique comparison names and declared roles are required")
    if not {"strong_empty", "evolved", "B1_frozen", "experience"} <= {a["role"] for a in arms}:
        raise ValueError("Include strong empty, evolution, B1-frozen and experience controls")
    empty = [a for a in arms if a["role"] == "strong_empty"]
    if len(empty) != 1 or empty[0]["name"] != cfg["reference_arm"]:
        raise ValueError("Declare exactly one strong-empty reference")
    banks, train_keys, extras, sources = {}, set(), {ROOT / cfg["statistics_plan"]}, {}
    for arm in arms:
        name, role = arm["name"], arm["role"]
        if role == "strong_empty":
            if arm["backend"] != "direct" or arm.get("source_config"):
                raise ValueError("Strong empty must have no learned publication")
            banks[name] = []
            continue
        if arm["backend"] != ("ace" if role == "experience" else "direct"):
            raise ValueError("Use the declared direct/ACE task adapter, not a hidden answer selector")
        config_path = ROOT / arm["source_config"]
        source, frozen = read(config_path), read(config_path.with_suffix(".frozen.json"))
        if sha(config_path) != arm["source_config_sha256"] or frozen["config_sha256"] != sha(config_path):
            raise ValueError("Learning source config differs from the declared frozen source")
        if (source["execution_contract"] != "direct_statutory_claims"
                or source["execution_contract_version"] != 14
                or source["source_cases"] != cfg["training_source_cases"]
                or source["batch_source_cases"] != cfg["training_batch_source_cases"]
                or source["planned_batches"] * source["batch_source_cases"] != source["source_cases"]
                or frozen["files"][source["input_packet"]] != cfg["training_packet_sha256"]):
            raise ValueError("Final controls must share the full TRAIN packet and common14 interface")
        for key in ("model", "model_root", "context_tokens", "max_tokens"):
            if source["generation"][key] != cfg["generation"][key]:
                raise ValueError("Source executor or inference budget differs: " + key)
        for name_ in SHARED_ACTOR_FILES + (ACE_ACTOR_FILES if arm["backend"] == "ace" else ()):
            if frozen["files"][name_] != sha(ROOT / name_):
                raise ValueError("Shared task actor/scorer changed since learning: " + name_)
        out = ROOT / "runs" / source["run_id"]
        complete = read(out / "completion.json")
        status = ("completed_declared_ACE_adaptation_stream" if arm["backend"] == "ace"
                  else "completed_bounded_mechanism_study")
        if complete["status"] != status or len(complete["batch_summary"]) != source["planned_batches"]:
            raise ValueError("Incomplete or failed learning is not a final learned bank")
        total = (complete["prequential"]["ace"] if arm["backend"] == "ace"
                 else complete["prequential_skills"])
        if any(total[f]["tasks"] != cfg["training_source_cases"] for f in FAMILIES):
            raise ValueError("Learning did not evaluate every declared source in both tasks")
        batch = 1 if role == "B1_frozen" else source["planned_batches"]
        publication = out / "publications" / f"b{batch}.json"
        published = read(publication)
        field = "playbook" if arm["backend"] == "ace" else "bank"
        bank = published[field]
        if csha(bank) != arm["bank_sha256"]:
            raise ValueError("Do not select or rewrite a different learned bank")
        if role != "B1_frozen":
            final_field = "final_playbook" if arm["backend"] == "ace" else "bank"
            if bank != complete[final_field]:
                raise ValueError("Use the final publication, not a winning intermediate checkpoint")
        if arm["backend"] == "direct":
            validate_scoped_bank(bank)
            if any(s["guidance"]["operators"] for s in bank):
                raise ValueError("The common direct actor has no numerical skill interpreter")
        elif not isinstance(bank, str):
            raise ValueError("ACE must use its actual text playbook")
        receipt_path = (ROOT / source["input_packet"]).parent / "preselection.json"
        receipt = read(receipt_path)
        if (receipt["source_cases"] != cfg["training_source_cases"]
                or receipt["input_packet_sha256"] != cfg["training_packet_sha256"]
                or len(set(receipt["source_keys"])) != cfg["training_source_cases"]
                or frozen["files"][str(receipt_path.relative_to(ROOT))] != sha(receipt_path)):
            raise ValueError("Learning receipt source count differs")
        train_keys.update(receipt["source_keys"])
        banks[name], sources[name] = bank, source["run_id"]
        extras.update((config_path, config_path.with_suffix(".frozen.json"), publication,
                       out / "completion.json", receipt_path))
    for arm in arms:
        if arm["role"] == "evolved" and not any(
                other["role"] == "B1_frozen" and other["source_config"] == arm["source_config"]
                and sources[other["name"]] == sources[arm["name"]]
                for other in arms):
            raise ValueError("Each evolved run needs its own actual B1-frozen control")
    for role in ("evolved", "experience", "B1_frozen"):
        run_ids = [sources[a["name"]] for a in arms if a["role"] == role]
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("Repeated names for one learning run are not independent repeats")
    return banks, train_keys, extras


class FrozenEvaluation:
    check = Comparison.check
    call = Comparison.call
    grade = Online.grade

    def __init__(self, config_path):
        self.cfg = read(config_path)
        self.banks, self.train_keys, _ = fixed_banks(self.cfg)
        frozen = read(config_path.with_suffix(".frozen.json"))
        if frozen["config_sha256"] != sha(config_path):
            raise ValueError("Final evaluation matrix changed after freeze")
        self.bindings, self.run_id = frozen["files"], self.cfg["run_id"]
        self.out = ROOT / "runs" / self.run_id
        if self.out.exists():
            raise FileExistsError("Never overwrite or resume selected TEST answers")
        self.native, self.request_cache, self.reuse_events = [], {}, []
        self.current_batch, self.stop = 0, False
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))
        self.check()

    def progress(self, stage, **extra):
        RunStore.atomic_json(self.out / "progress.json", {
            "at": now(), "run_id": self.run_id, "stage": stage,
            "completed_native_calls": len(self.native), "teacher_calls": 0,
            "exact_wire_reuses_not_independent_draws": len(self.reuse_events), **extra})

    def execute(self):
        self.rows = read(ROOT / self.cfg["input_packet"])["rows"]
        groups = {}
        for row in self.rows:
            if row["source_key"] in self.train_keys:
                raise ValueError("TEST source overlaps a learning source; do not drop/resample it")
            groups.setdefault(row["source_key"], []).append((row["case_id"], row["family"]))
        if len(groups) != self.cfg["source_cases"] or any(
                len(pair) != 2 or len({i for i, _ in pair}) != 1
                or {f for _, f in pair} != set(FAMILIES) for pair in groups.values()):
            raise ValueError("Evaluate the complete declared source-paired EC/EV packet")
        if len({row["case_id"] for row in self.rows}) != len(groups):
            raise ValueError("Each TEST source must have its own case identity")
        records = {a["name"]: [] for a in self.cfg["arms"]}
        for row in self.rows:
            arms = self.cfg["arms"]
            offset = (row["case_id"] + FAMILIES[row["family"]]) % len(arms)
            for arm in arms[offset:] + arms[:offset]:
                name = arm["name"]
                stage = "frozen_" + name
                bank = self.banks[name]
                record = (ACEOnline.answer(self, row, stage, playbook=bank)
                          if arm["backend"] == "ace" else
                          Online.answer(self, row, bank, stage, name))
                records[name].append(record)
        # The only grading path is below all arms/all sources' immutable answers.
        RunStore.immutable_json(self.out / "predictions_before_any_grading.json", records)
        self.check()
        self.grade([r for values in records.values() for r in values])
        RunStore.immutable_json(self.out / "scored_records.json", records)
        reference = records[self.cfg["reference_arm"]]
        return {"status": "completed_frozen_comparison", "at": now(),
            "metrics": {name: metrics(values) for name, values in records.items()},
            "paired_vs_strong_empty": {name: paired_effect(reference, values)
                                       for name, values in records.items()},
            "paired_vs_own_B1_frozen": {arm["name"]: paired_effect(
                records[next(a["name"] for a in self.cfg["arms"]
                             if a["role"] == "B1_frozen"
                             and a["source_config"] == arm["source_config"])],
                records[arm["name"]]) for arm in self.cfg["arms"] if arm["role"] == "evolved"},
            "bank_sha256": {name: csha(bank) for name, bank in self.banks.items()},
            "actual_native_calls": len(self.native), "teacher_calls": 0,
            "exact_wire_reuses_not_independent_draws": self.reuse_events,
            "native_prompt_tokens": sum(r["response"]["prompt_tokens"] for r in self.native),
            "native_completion_tokens": sum(r["response"]["completion_tokens"] for r in self.native),
            "statistics_plan": self.cfg["statistics_plan"],
            "source_pair_uncertainty_and_learning_repeat_analysis_not_computed_here": True}

    def run(self):
        self.out.mkdir(parents=True, exist_ok=False)
        RunStore.immutable_json(self.out / "evaluation_started.json", {
            "at": now(), "matrix_frozen_before_packet_load": True,
            "no_teacher_or_learning": True, "arms": self.cfg["arms"]})
        try:
            result = self.execute()
            RunStore.immutable_json(self.out / "completion.json", result)
            self.progress("terminal", state=result["status"])
        except Exception as exc:
            RunStore.immutable_json(self.out / "failure.json", {
                "at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
                "actual_native_calls": len(self.native), "teacher_calls": 0,
                "no_retry_or_answer_selection": True})
            self.progress("terminal", state="failed")
            raise
        finally:
            names = [str(p.relative_to(ROOT)) for p in self.out.rglob("*") if p.is_file()]
            RunStore.immutable_json(self.out / "terminal_preservation.json",
                                    preserve(self.run_id, "actual-terminal", names))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    path = args.config.resolve()
    os.chdir(ROOT)
    cfg = read(path)
    _, _, sources = fixed_banks(cfg)
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "freeze":
            freeze(path, additional_sources=(*sources, Path(__file__).resolve(),
                ROOT / "experiments/openexempt_ace_online.py",
                *ROOT.glob("third_party/ace/prompts/*.py")))
        else:
            FrozenEvaluation(path).run()


if __name__ == "__main__":
    main()
