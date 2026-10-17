"""Bounded same-lawyer execution diagnosis; reuses the actual native runner.

Run only after the complete parent, not alongside it. No new teachers or fits.
"""

# ruff: noqa: E402 -- Research entrypoint binds its authoritative project first.
from __future__ import annotations

import copy
import fcntl
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jsonschema import ValidationError, validate
from native_membership import (
    compile_membership,
    encode_original_coordinate_view,
    original_coordinate_view,
)

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.acquisition import AcquisitionStudy, compact
from legal_skill_guard.learning.audit import original_score
from legal_skill_guard.learning.experiment import now, points, read, sha
from legal_skill_guard.learning.publication import paired
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

FOLDER = Path(__file__).resolve().parent
PARENT = ROOT / "runs/legal_contractnli_published_acquisition_continuation_20261017_run01"
IDS = [501, 164, 421, 132]
RUN_ID = "legal_contractnli_explicit_member_execution_20261017_run01"


def prepare_after_complete_parent():
    complete = read(PARENT / "completion.json")
    assert complete["completed_native_calls"] == 80 and complete["completed_teacher_calls"] == 1
    for phase in ("teacher", "retention"):
        report = read(PARENT / f"monitoring/{phase}_complete_original_author_wire_and_teacher_audit.json")
        assert report["all_phase_original_author_and_actual_wires_checked"]
    gap_path = PARENT / "monitoring/retention_matched_ordinary_gap_and_original_member_failure_decomposition.json"
    assert read(gap_path)["original_contract_count"] == 32
    parent_cfg_path = ROOT / "configs/contractnli_published_acquisition_continuation.json"
    parent, frozen = read(parent_cfg_path), read(parent_cfg_path.with_suffix(".frozen.json"))
    assert sha(parent_cfg_path) == frozen["config_sha256"]
    assert all(sha(p) == h for p, h in frozen["files"].items())
    assert IDS == parent["training_ids"][::8]
    old = ROOT / parent["published_prefix_run"]
    early = ROOT / read(old / "declaration.json")["config"]["prefix_feedback_run"]
    ordinary = [u for u in read(early / "complete32_native_and_original_scores.json")["units"] if u["condition"] == "ordinary"]
    ordinary += [u for u in read(old / "b3_before_complete.json")["units"] if u["condition"] == "ordinary"]
    ordinary += [u for u in read(PARENT / "b4_before_complete.json")["units"] if u["condition"] == "ordinary"]
    reference = [u for u in ordinary + read(PARENT / "b4_all_seen_retention.json")["units"] if u["document_id"] in IDS]
    assert len(reference) == 8 and {u["condition"] for u in reference} == {"ordinary", "skills"}
    reference_path = FOLDER / "actual_conventional_reference8_not_new_calls.json"
    RunStore.immutable_json(reference_path, {"units": reference})
    keep = ("generation", "inference_environment", "ordinary_manifest", "input_packet", "grading_only",
        "training_ids", "solver_system_reference", "library_token_hard_cap", "prelaunch_backup_receipt",
        "source_archive", "source_archive_sha256")
    cfg = {k: copy.deepcopy(parent[k]) for k in keep}
    cfg.update(method="explicit_member_execution_diagnosis", run_id=RUN_ID,
        planned_new_native_calls=12, planned_new_teacher_calls=0, incremental_source_encoding="scored_records",
        fixed_bank_publication=str(PARENT / "publications/b4.json"), diagnostic_source_ids=IDS,
        fixed_bank_publication_sha256=sha(PARENT / "publications/b4.json"), reference_units=str(reference_path),
        all_seen_development_not_new_case_transfer_or_official_TEST=True)
    cfg_path = FOLDER / "config.json"
    RunStore.immutable_json(cfg_path, cfg)
    files = {**frozen["files"]}
    extra = [parent_cfg_path, parent_cfg_path.with_suffix(".frozen.json"), cfg_path, reference_path,
        Path(__file__), FOLDER / "native_membership.py", FOLDER / "PROTOCOL.md",
        PARENT / "completion.json", PARENT / "publications/b4.json", gap_path,
        *(PARENT / f"monitoring/{p}_complete_original_author_wire_and_teacher_audit.json" for p in ("teacher", "retention"))]
    extra += [Path(u[k]) for u in reference for k in ("payload", "raw_artifact")]
    files.update({str(p.resolve()): sha(p) for p in extra})
    RunStore.immutable_json(cfg_path.with_suffix(".frozen.json"), {"config_sha256": sha(cfg_path), "files": files})
    return cfg_path


class ExplicitMemberStudy(AcquisitionStudy):
    def __init__(self, path):
        super().__init__(path)
        assert self.cfg["diagnostic_source_ids"] == IDS
        assert sha(self.cfg["fixed_bank_publication"]) == self.cfg["fixed_bank_publication_sha256"]
        self.bank = read(self.cfg["fixed_bank_publication"])["publication"]

    def payload(self, row, arm, bank):
        p = super().payload(row, arm, bank)
        p["canonical_actor_messages_sha256"] = csha(p["messages"])
        p["canonical_actor_schema_sha256"] = csha(p["schema"])
        p["messages"], p["schema"], p["evidence_check_order"] = compile_membership(p["messages"], len(row["spans"]))
        p["prompt_tokens"] = self.meter.token_count(messages=p["messages"])
        assert p["prompt_tokens"] + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"]
        p["representation"] = "explicit-native-evidence-members-v1"
        return p

    def native_answer(self, entry):
        p = read(entry["path"])
        raw_path = self.out / f"native/fixed_R3/{entry['arm']}/{entry['document_id']}.final.native.json"
        response = self.call(raw_path, p["messages"], p["schema"], self.cfg["generation"]["max_tokens"], {
            "stage": entry["stage"], "arm": entry["arm"], "document_id": entry["document_id"],
            "call_role": "final", "bank_sha256": p["bank_sha256"]})
        raw = read(raw_path)
        wire = raw["calls"][0]
        assert wire["request"]["messages"] == p["messages"]
        assert wire["request"]["response_format"]["json_schema"]["schema"] == p["schema"]
        assert wire["response"]["model"] == self.cfg["generation"]["model"]
        assert wire["response"]["choices"][0]["message"]["reasoning_content"]
        view, invalid = None, None
        try:
            if response["finish_reason"] != "stop":
                raise ValueError("Incomplete native answer, not repaired")
            value = json.loads(response["content"])
            validate(value, p["schema"])
            view = original_coordinate_view(value, p["evidence_check_order"], p["schema"])
            assert original_coordinate_view(encode_original_coordinate_view(view, p["evidence_check_order"]),
                p["evidence_check_order"], p["schema"]) == view
        except (ValueError, TypeError, KeyError, ValidationError) as exc:
            invalid = str(exc)
        unit = {"stage": entry["stage"], "condition": entry["arm"], "document_id": entry["document_id"],
            "payload": entry["path"], "raw_artifact": str(raw_path), "response": response,
            "bank_sha256": p["bank_sha256"], "exact_same_run_cold_alias": False,
            "original_coordinate_view_not_native_response": view, "representation_failure": invalid,
            "native_content_never_overwritten": True}
        path = self.out / f"ungraded_views/{entry['arm']}/{entry['document_id']}.json"
        RunStore.immutable_json(path, unit)
        self.bindings.update({str(raw_path): sha(raw_path), str(path): sha(path)})
        return unit

    def execute(self):
        self.check()
        selected = [r for r in self.training if r["id"] in IDS]
        assert [r["id"] for r in selected] == IDS
        RunStore.immutable_json(self.out / "declaration.json", {"at": now(), "config": self.cfg,
            "frozen_bindings": self.bindings, "fixed_latest_actual_R3": self.cfg["fixed_bank_publication_sha256"],
            "not_online_learning_or_independent_transfer_TEST": True})
        entries = self.freeze_phase("fixed_R3", selected, ["strong_empty", "ordinary", "skills"])
        reference = read(self.cfg["reference_units"])["units"]
        for u in reference:
            p = self.payload(next(r for r in selected if r["id"] == u["document_id"]), u["condition"], self.bank)
            original_payload, raw = read(u["payload"]), read(u["raw_artifact"])
            assert raw["response"] == u["response"] and len(raw["calls"]) == 1
            assert raw["calls"][0]["request"]["messages"] == original_payload["messages"]
            assert csha(original_payload["messages"]) == p["canonical_actor_messages_sha256"]
            assert csha(original_payload["schema"]) == p["canonical_actor_schema_sha256"]
            assert original_payload["bank_sha256"] == p["bank_sha256"]
            assert original_payload["actual_factual_trace"] == p["actual_factual_trace"]
            original = json.loads(u["response"]["content"])
            expected = {h: {**v, "spans": sorted(set(v["spans"]))} for h, v in original.items()}
            assert original_coordinate_view(encode_original_coordinate_view(original, p["evidence_check_order"]),
                p["evidence_check_order"], p["schema"]) == expected
        RunStore.immutable_json(self.out / "actual_reference8_set_roundtrip_no_generation.json", {"at": now(),
            "actual_historical_references": 8, "native_or_teacher_calls_for_check": 0,
            "all_source_indices_choices_reasons_preserved_at_set_level": True})
        units, cutoffs = [], 0
        for entry in entries:
            u = self.native_answer(entry)
            units.append(u)
            cutoffs += u["response"]["finish_reason"] == "length"
            if cutoffs >= 2:
                raise RuntimeError("Two output cutoffs; execution infeasible, no partial effect grading or retry")
        assert len(units) == len(self.native) == 12 and not self.teachers
        gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        for u in units:
            row = next(r for r in selected if r["id"] == u["document_id"])
            view = u["original_coordinate_view_not_native_response"]
            # This is an explicitly named scoring view, not another native response.
            scoring_view = {"content": compact(view), "finish_reason": "stop" if view is not None else None}
            u.update(original_score(scoring_view, row, gold[str(row["id"])], list(self.labels)))
        results = {a: points([u for u in units if u["condition"] == a]) for a in ("strong_empty", "ordinary", "skills")}
        consistency = [{"source": u["document_id"], "arm": u["condition"], "hypothesis": h,
            "choice": v["choice"], "spans": v["spans"]}
            for u in units if (view := u["original_coordinate_view_not_native_response"]) is not None
            for h, v in view.items() if (v["choice"] == "NotMentioned") != (not v["spans"])]
        RunStore.immutable_json(self.out / "complete12_native_and_original_scores.json", {"units": units})
        complete = {"at": now(), "run_id": self.run_id, "completed_native_calls": 12,
            "completed_teacher_calls": 0, "actual_development_contracts": 4, "results": results,
            "historical_reference_not_new_calls": {a: points([u for u in reference if u["condition"] == a]) for a in ("ordinary", "skills")},
            "paired_against_actual_conventional_reference": {a: paired(
                [u for u in reference if u["condition"] == a], [u for u in units if u["condition"] == a]) for a in ("ordinary", "skills")},
            "native_relation_evidence_inconsistencies_not_repaired": consistency,
            "invalid_native_answers_included_in_original_denominators": sum(not u["public_valid"] for u in units),
            "actual_native_usage": {k: sum(u["response"][k] for u in units) for k in ("prompt_tokens", "completion_tokens")},
            "not_new_case_transfer_or_independent_learning_or_official_TEST": True}
        self.check()
        RunStore.immutable_json(self.out / "completion.json", complete)
        RunStore.atomic_json(self.out / "progress.json", {"state": "completed", **complete})


def main():
    # The queue/launcher must verify parent exit and exact source hashes first.
    with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = prepare_after_complete_parent()
        study = ExplicitMemberStudy(path)
        try:
            study.execute()
        except BaseException as exc:
            failure = {"at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
                "completed_native_calls": len(study.native), "completed_teacher_calls": 0,
                "no_retry_or_partial_effect_grading": True}
            RunStore.immutable_json(study.out / "failure.json", failure)
            RunStore.atomic_json(study.out / "progress.json", {"state": "failed", **failure})
            raise


if __name__ == "__main__":
    main()
