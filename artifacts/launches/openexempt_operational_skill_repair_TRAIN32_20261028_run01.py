"""One observed-prefix TRAIN repair through the actual Online.update implementation."""
import copy
import fcntl
import sys
from pathlib import Path

from artifacts.launches.openexempt_skill_position_mechanism_20261027_run01 import cache_origin
from experiments.openexempt_online import Online, acceptance, actor_payload, freeze, paired_effect
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read
from legal_skill_guard.openexempt import ROOT, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def inputs(config_path):
    cfg = read(config_path)
    assert cfg["study_kind"] == "single_teacher_task_local_operational_skill_repair_from_observed_fifth_B2"
    assert cfg["max_candidate_attempts"] == cfg["planned_teacher_responses_max"] == 1
    source = ROOT / "runs" / cfg["source_main_run"]
    original = read(ROOT / cfg["source_main_config"])
    assert all(cfg[k] == original[k] for k in
        ("generation", "phase_dispatch", "input_packet", "grading_directory", "inference_environment"))
    assert "Operator stop at artifact-safe boundary" in read(source / "failure.json")["error"]
    publication = read(ROOT / cfg["initial_library_publication"])
    parent = publication["bank"]
    assert csha(parent) == publication["bank_sha256"] == cfg["parent_bank_sha256"]
    records = next(d["actual_replay"] for d in reversed(publication["training_decisions"])
                   if d.get("actual_replay") and csha(d["candidate"]) == csha(parent))
    ids, current, prior = (set(cfg[k]) for k in
        ("mechanism_source_case_ids", "mechanism_current_source_case_ids", "mechanism_prior_source_case_ids"))
    assert ids == set(range(181, 213)) and current == set(range(197, 213))
    assert prior == set(range(181, 197)) and current | prior == ids and not current & prior
    assert len(records) == 64 and all(r["bank_sha256"] == csha(parent) for r in records)
    rows = [r for r in read(ROOT / cfg["input_packet"])["rows"] if r["case_id"] in ids]
    assert len(rows) == 64
    empty, extra = [], {Path(__file__).resolve(), ROOT / cfg["initial_library_publication"],
        ROOT / cfg["source_main_config"], source / "failure.json",
        ROOT / cfg["strong_reference_publication"], ROOT / cfg["implementation_evidence"],
        ROOT / "artifacts/launches/openexempt_skill_position_mechanism_20261027_run01.py"}
    by_key = {(r["case_id"], r["family"]): r for r in records}
    for batch in (1, 2):
        path = source / "batches" / f"b{batch}_prequential_records.json"
        empty.extend(read(path)["empty"])
        extra.add(path)
    assert len(empty) == 64
    for row in rows:
        record = by_key[row["case_id"], row["family"]]
        raw = ROOT / record["raw_call_path"]
        wire = read(raw.with_suffix(".input.json"))
        messages, schema, _ = actor_payload(row, parent, direct_numeric=True, asset_references=True)
        assert wire["messages"] == messages and wire["schema"] == schema
        extra.update((raw, raw.with_suffix(".input.json")))
    for record in empty:
        raw = ROOT / record["raw_call_path"]
        extra.update((raw, raw.with_suffix(".input.json")))
    return cfg, rows, records, empty, extra


class OperationalRepair(Online):
    def execute(self):
        cfg, rows, before, empty, _ = inputs(self.config_path)
        self.current_batch = 1  # One repair round, not a new first-encounter B1.
        self.latest = {(r["case_id"], r["family"]): copy.deepcopy(r) for r in before}
        self.prequential_empty = copy.deepcopy(empty)
        self.prequential_direct = copy.deepcopy(empty)
        self.prequential_frozen = copy.deepcopy(before)
        self.prequential_skills = copy.deepcopy(before)
        origins = set()
        for record in before:
            raw = ROOT / record["raw_call_path"]
            if raw not in origins:
                cache_origin(self, raw)
                origins.add(raw)
        RunStore.immutable_json(self.out / "mechanism_started.json", {
            "at": now(), "prior_source_exposure": 32, "parent_bank_sha256": csha(self.bank),
            "source_case_ids": cfg["mechanism_source_case_ids"],
            "parent_native_origins_reused_not_new_generations": len(origins),
            "all_before_and_empty_records_are_previously_observed_TRAIN": True,
            "not_formal_learning_or_TEST": True})
        current_ids = set(cfg["mechanism_current_source_case_ids"])
        current = [r for r in rows if r["case_id"] in current_ids]
        before_current = [r for r in before if r["case_id"] in current_ids]
        before_prior = [r for r in before if r["case_id"] not in current_ids]
        publication = self.update(current, rows, before_current)
        after = [self.latest[r["case_id"], r["family"]] for r in rows]
        after_current = [r for r in after if r["case_id"] in current_ids]
        after_prior = [r for r in after if r["case_id"] not in current_ids]
        gate = acceptance(before_current, after_current, before_prior, after_prior)
        reference = read(ROOT / cfg["strong_reference_publication"])
        ref_records = next(d["actual_replay"] for d in reversed(reference["training_decisions"])
            if d.get("actual_replay") and csha(d["candidate"]) == reference["bank_sha256"])
        ref_ev = metrics(ref_records)["EV"]["f1"]
        assert abs(ref_ev - cfg["required_prefix_native_EV_for_new_formal"]) < 1e-12
        qualified = gate["accepted"] and metrics(after)["EV"]["f1"] + 1e-12 >= ref_ev
        result = {"at": now(), "scope": "one observed TRAIN-prefix repair, not a new-case claim",
            "before": metrics(before), "after": metrics(after),
            "before_current": metrics(before_current), "after_current": metrics(after_current),
            "before_prior": metrics(before_prior), "after_prior": metrics(after_prior),
            "paired": paired_effect(before, after), "original_gate": gate,
            "bank_sha256": publication["bank_sha256"],
            "strong_reference_prefix_EV": ref_ev, "qualified_for_new_formal": qualified,
            "no_automatic_long_training_launch": True,
            "new_native_calls": len(self.native), "teacher_responses": len(self.teachers)}
        self.summaries.append(result)
        RunStore.immutable_json(self.out / "mechanism_result.json", result)
        return "completed_single_observed_TRAIN_operational_repair"


def main(config_path):
    cfg, _, _, _, extra = inputs(config_path)
    if (ROOT / "runs" / cfg["run_id"]).exists():
        raise FileExistsError("New mechanism Run ID required; never overwrite outcomes")
    with (ROOT / "artifacts/openexempt_training.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        freeze(config_path, additional_sources=extra)
        study = OperationalRepair(config_path)
        study.config_path = config_path
        study.run()


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
