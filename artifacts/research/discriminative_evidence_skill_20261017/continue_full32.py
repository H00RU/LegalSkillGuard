"""Fixed actual bank on all32 taught contracts, not a new learning/test run.

Keep the complete8 comparison, inherit its16 byte-identical skills/ordinary
answers explicitly, and make48 new calls on ALL remaining24 original contracts.
No new teacher, bank edit, case selection, inference change or output repair.
"""

# ruff: noqa: E402 -- Bind the authoritative project and existing implementation.
from __future__ import annotations

import argparse
import copy
import fcntl
import json
import runpy
import sys
import traceback
import zipfile
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FOLDER))

from jsonschema import ValidationError, validate
from run_study import DiscriminativeEvidenceStudy

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.acquisition import AcquisitionStudy, compact
from legal_skill_guard.learning.audit import original_score
from legal_skill_guard.learning.experiment import now, points, read, sha
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

PARENT = ROOT / "runs/legal_contractnli_discriminative_evidence_skill_20261017_run03"
CONFIG = FOLDER / "full32_retention_config.json"
RUN_ID = "legal_contractnli_discriminative_evidence_full32_retention_20261017_run01"
ARMS = ["skills", "ordinary"]
ANALYSIS = PARENT / "monitoring/analyse_complete.py"


def prepare():
    assert not CONFIG.exists() and not (ROOT / "runs" / RUN_ID).exists()
    cfg_path = FOLDER / "config_run03.json"
    old, frozen = read(cfg_path), read(cfg_path.with_suffix(".frozen.json"))
    assert sha(cfg_path) == frozen["config_sha256"]
    assert all(sha(p) == h for p, h in frozen["files"].items())
    complete = read(PARENT / "completion.json")
    assert [complete["completed_native_calls"], complete["completed_teacher_calls"]] == [32, 1]
    assert read(PARENT / "monitoring/complete32_actual_wires_teacher_original_member_and_ablation_audit.json")[
        "all32_actual_wires_and_original_author_members_checked"]
    inherited = [u for u in read(PARENT / "complete32_native_and_original_scores.json")["units"] if u["condition"] in ARMS]
    assert len(inherited) == 16
    keep = ("generation", "inference_environment", "ordinary_manifest", "input_packet", "grading_only",
        "training_ids", "solver_system_reference", "library_token_hard_cap", "prelaunch_backup_receipt",
        "source_archive", "source_archive_sha256", "publication_step")
    cfg = {k: copy.deepcopy(old[k]) for k in keep}
    cfg.update(method="discriminative_evidence_full32_retention", run_id=RUN_ID,
        planned_new_native_calls=48, planned_new_teacher_calls=0, incremental_source_encoding="scored_records",
        fixed_publication=str(PARENT / "publications/b5.json"), fixed_publication_sha256=sha(PARENT / "publications/b5.json"),
        inherited_parent_units=str(PARENT / "complete32_native_and_original_scores.json"),
        inherited_source_ids=old["diagnostic_source_ids"], retention_arms=ARMS,
        all_original32_teacher_seen_TRAIN_not_transfer_independent_learning_or_official_TEST=True,
        source_selection="ALL32 original contracts; complete8 already observed, remaining24 without reselection.",
        logical_final_paired_answers=64, inherited_actual_answers_not_new_calls=16,
        unchanged_teacher_bank_and_native_interface=True,
        parent_protocol="docs/DISCRIMINATIVE_EVIDENCE_SKILL_PROTOCOL_20261017.md")
    extra = [cfg_path, cfg_path.with_suffix(".frozen.json"), Path(__file__), ANALYSIS,
        PARENT / "completion.json", PARENT / "complete32_native_and_original_scores.json", PARENT / "publications/b5.json",
        PARENT / "monitoring/complete32_actual_wires_teacher_original_member_and_ablation_audit.json",
        PARENT / "monitoring/complete32_paired_source_criterion_scope_and_native_member_analysis.json",
        PARENT / "monitoring/complete8_gain_concentration_all_damage_and_remaining_execution_gaps.json"]
    extra.extend(Path(u[k]) for u in inherited for k in ("payload", "raw_artifact"))
    RunStore.immutable_json(CONFIG, cfg)
    files = frozen["files"] | {str(p.resolve()): sha(p) for p in extra + [CONFIG]}
    RunStore.immutable_json(CONFIG.with_suffix(".frozen.json"), {"config_sha256": sha(CONFIG), "files": files})
    print(compact({"prepared": str(CONFIG), "frozen_bindings": len(files), "new_native_teacher_calls": [0, 0]}))


class FullRetention(DiscriminativeEvidenceStudy):
    def __init__(self, config):
        AcquisitionStudy.__init__(self, config)
        assert self.cfg["retention_arms"] == ARMS
        assert sha(self.cfg["fixed_publication"]) == self.cfg["fixed_publication_sha256"]
        self.bank = read(self.cfg["fixed_publication"])["publication"]
        self.banks = {csha(self.bank): copy.deepcopy(self.bank)}
        self.current_batch = self.cfg["publication_step"]

    def execute(self):
        self.check()
        inherited = [u for u in read(self.cfg["inherited_parent_units"])["units"] if u["condition"] in ARMS]
        sources = {r["id"]: r for r in self.training}
        for u in inherited:
            p = self.payload(sources[u["document_id"]], u["condition"], self.bank)
            old, raw = read(u["payload"]), read(u["raw_artifact"])
            for key in ("messages", "schema", "bank", "bank_sha256", "actual_factual_trace"):
                assert p[key] == old[key], "Inherited answer must be actual identical input, not a cold alias"
            assert raw["response"] == u["response"] and raw["calls"][0]["request"]["messages"] == p["messages"]
        RunStore.immutable_json(self.out / "declaration.json", {"at": now(), "config": self.cfg,
            "frozen_bindings": self.bindings, "actual_parent_answers_inherited_not_new_calls": len(inherited),
            "not_online_learning_curve_or_new_case_TEST": True})
        remaining = [r for r in self.training if r["id"] not in self.cfg["inherited_source_ids"]]
        assert len(remaining) == 24
        entries = self.freeze_phase("remaining24_fixed_bank", remaining, ARMS)
        new = [self.answer(entry) for entry in entries]
        assert len(new) == len(self.native) == 48 and not self.teachers
        units = inherited + new
        assert len({u["response"]["raw_id"] for u in units}) == len(units) == 64
        assert {(u["condition"], u["document_id"]) for u in units} == {(a, d) for a in ARMS for d in sources}
        # Original-author source/label content, opened only after all48 new calls.
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        originals = {r["id"]: r for r in author["documents"]}
        utilities = runpy.run_path(str(ANALYSIS))
        rows = {a: [] for a in ARMS}
        for u in units:
            d, arm = u["document_id"], u["condition"]
            original = originals[d]
            assert sources[d] == {k: original[k] for k in ("id", "text", "spans")}
            gold = original["annotation_sets"][0]["annotations"]
            p, raw = read(u["payload"]), read(u["raw_artifact"])
            assert raw["response"] == u["response"] and len(raw["calls"]) == 1 and raw["transport_error"] is None
            wire = raw["calls"][0]
            assert wire["request"]["messages"] == p["messages"]
            assert wire["request"]["response_format"]["json_schema"]["schema"] == p["schema"]
            assert wire["response"]["model"] == self.cfg["generation"]["model"]
            for k in ("temperature", "top_p", "top_k", "seed", "max_tokens"):
                assert wire["request"][k] == self.cfg["generation"][k]
            body = json.loads(p["messages"][1]["content"])
            assert body["full_contract_with_original_span_markers"] == marked_text(sources[d])
            assert p["bank"] == (self.bank if arm == "skills" else [])
            actual = None
            try:
                assert u["response"]["finish_reason"] == "stop"
                actual = json.loads(u["response"]["content"])
                validate(actual, p["schema"])
            except (AssertionError, ValueError, TypeError, ValidationError):
                actual = None
            assert (actual is not None) == u["native_schema_valid"]
            score_view = u["response"] if actual is not None else {"content": "", "finish_reason": None}
            u.update(original_score(score_view, sources[d], gold, list(self.labels)))
            for h in self.labels:
                g, v = gold[h], actual[h] if actual is not None else None
                choice, citations = (v["choice"], v["spans"]) if v is not None else (None, [])
                correct = choice == g["choice"]
                rows[arm].append({"document_id": d, "hypothesis_id": h, "Gold_choice": g["choice"],
                    "Gold_spans": g["spans"], "choice": choice, "spans": sorted(set(citations)),
                    "label_correct": correct, "joint_exact": correct and set(citations) == set(g["spans"]),
                    "ordinary": [r["original_span_index"] for r in body["hypotheses"][h]["fallible_evidence_candidates"]],
                    "additional": body["hypotheses"][h]["additional_source_read_indices"]})
        results = {a: points([u for u in units if u["condition"] == a]) for a in ARMS}
        for arm in ARMS:
            manual = utilities["counts"](rows[arm])
            assert all(results[arm][k] == v for k, v in manual.items() if k != "original_NN")
        RunStore.immutable_json(self.out / "complete64_actual_paired_native_and_original_scores.json", {"units": units})
        complete = {"at": now(), "run_id": self.run_id, "actual_new_native_teacher_calls": [48, 0],
            "inherited_actual_native_answers_not_new_calls": 16, "original_taught_contracts": 32,
            "results": results, "paired_skill_minus_ordinary": utilities["contrast"](rows["ordinary"], rows["skills"]),
            "conditional_source_intervals": utilities["intervals"](rows["ordinary"], rows["skills"], self.cfg["training_ids"]),
            "failure_decomposition": {a: utilities["failures"](v) for a, v in rows.items()},
            "by_original_eight_source_group_not_learning_curve": {str(b + 1): {a: utilities["counts"](
                [r for r in v if r["document_id"] in self.cfg["training_ids"][8*b:8*(b+1)]]) for a, v in rows.items()} for b in range(4)},
            "actual_new_native_usage": {k: sum(u["response"][k] for u in new) for k in ("prompt_tokens", "completion_tokens")},
            "parent_diagnostic_actual_native_teacher_calls_not_free": [32, 1],
            "earlier_stopped_contract_trial_actual_native_teacher_calls_not_free": [2, 1],
            "all64_wires_and_original_author_sets_independently_recounted": True,
            "invalid_native_answers_retained_in_original_denominators": sum(not u["native_schema_valid"] for u in units),
            "not_new_case_transfer_independent_learning_mature_method_comparison_or_official_TEST": True}
        self.check()
        RunStore.immutable_json(self.out / "completion.json", complete)
        RunStore.atomic_json(self.out / "progress.json", {"state": "completed", **complete})
        print(compact({"completed": self.run_id, "actual_new_native_teacher_calls": [48, 0], "results": results}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
        return
    with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        study = FullRetention(CONFIG)
        try:
            study.execute()
        except BaseException as exc:
            value = {"at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
                "completed_native_calls": len(study.native), "completed_teacher_calls": 0,
                "inherited_answers_not_new_calls": 16, "no_retry_or_partial_effect_grading": True}
            RunStore.immutable_json(study.out / "failure.json", value)
            RunStore.atomic_json(study.out / "progress.json", {"state": "failed", **value})
            raise


if __name__ == "__main__":
    main()
