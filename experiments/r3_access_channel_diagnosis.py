"""Bounded R3 delivery diagnosis; no editor, learned-state selection or repair.

Reuse the existing native executor, original scorer and two-filesystem phase
preservation. Only the two declared input interventions live in this research
entry point; they are not production switches or a new learning framework.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import io
import json
import shutil
import tarfile
import traceback
import zipfile
from pathlib import Path

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.acquisition import AcquisitionStudy, compact
from legal_skill_guard.learning.experiment import ROOT, Comparison, now, points, read, sha
from legal_skill_guard.learning.member_contract import one_copy_criteria
from legal_skill_guard.learning.member_learning import MemberLearning, paired_effect
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

ARMS = ["compact_full_R3", "ordinary_plus_same_R3_criteria"]
ROLES = ["literal_match", "explicit_neighbour", "possible_list_preamble"]
LEGEND = (
    "For each hypothesis, additional_source_read_indices maps each literal "
    "access role to its complete list of zero-based ORIGINAL SPAN indices. "
    "An index may appear in several role lists. These lists losslessly encode "
    "the literal_match, explicit_neighbour and possible_list_preamble booleans "
    "of individual records; membership is source-access provenance, not a "
    "legal verdict or an instruction to cite. The full original source and "
    "exact candidate text remain available."
)


def payload(cfg, row, arm, bank, meter):
    reference_arm = "skills" if arm == ARMS[0] else "ordinary"
    origin = ROOT / cfg["reference_run"] / f"prospective/b4_before/{reference_arm}/{row['id']}.json"
    original = read(origin)
    result = copy.deepcopy(original)
    before = json.loads(original["messages"][1]["content"])
    body = copy.deepcopy(before)
    assert before["full_contract_with_original_span_markers"] == marked_text(row)
    assert list(before["hypotheses"]) == list(read(ROOT / cfg["input_packet"])["public_hypotheses"])
    criteria = one_copy_criteria(bank)
    assert criteria
    if arm == ARMS[0]:
        assert original["bank"] == bank and before["evidence_selection_criteria"] == criteria
        for h, question in body["hypotheses"].items():
            records = question["additional_source_read_indices"]
            assert all(set(record) == {"original_span_index", *ROLES} for record in records)
            assert all(any(record[role] for role in ROLES) for record in records)
            assert all(type(record[role]) is bool for record in records for role in ROLES)
            lists = {role: [r["original_span_index"] for r in records if r[role]] for role in ROLES}
            indices = sorted({i for values in lists.values() for i in values})
            restored = [{"original_span_index": i, **{role: i in lists[role] for role in ROLES}} for i in indices]
            assert restored == records, "No deleted, reordered or reclassified access facts"
            question["additional_source_read_indices"] = lists
            check = copy.deepcopy(question)
            check["additional_source_read_indices"] = restored
            assert check == before["hypotheses"][h]
        body["source_access_encoding"] = LEGEND
        restored_body = copy.deepcopy(body)
        del restored_body["source_access_encoding"]
        for h in restored_body["hypotheses"]:
            restored_body["hypotheses"][h]["additional_source_read_indices"] = before["hypotheses"][h]["additional_source_read_indices"]
        assert restored_body == before
        encoding = "lossless_role_index_lists"
    else:
        assert arm == ARMS[1] and not original["bank"]
        assert "evidence_selection_criteria" not in body
        assert all(not q["additional_source_read_indices"] for q in body["hypotheses"].values())
        body["evidence_selection_criteria"] = criteria
        check = copy.deepcopy(body)
        del check["evidence_selection_criteria"]
        assert check == before, "Only the exact same learned criteria are appended"
        encoding = "no_incremental_query_reads"
    result["messages"][1]["content"] = compact(body)
    assert result["messages"][0] == original["messages"][0]
    result.update(arm=arm, bank=copy.deepcopy(bank), bank_sha256=csha(bank),
        prompt_tokens=meter.token_count(messages=result["messages"]),
        incremental_read_encoding=encoding,
        reference_payload=str(origin), reference_payload_sha256=sha(origin),
        stored_library_unchanged=True,
        served_criteria=criteria,
        reference_source_access_execution_reused_not_new_model_output=arm == ARMS[0],
        ordinary_deterministic_candidates_reused_without_refit=arm == ARMS[1],
        stored_queries_not_served_or_executed_in_this_condition=arm == ARMS[1])
    assert result["prompt_tokens"] + cfg["generation"]["max_tokens"] <= cfg["generation"]["context_tokens"]
    assert result["schema"] == original["schema"]
    assert body["candidate_original_text"] == before["candidate_original_text"]
    return result


def verified_archive(target, files, metadata):
    """Create once and stream-check every archived member, never extract."""
    encoded = compact(metadata).encode()
    expected = {"project/" + name: digest for name, digest in files.items()}
    expected["recovery_manifest.json"] = hashlib.sha256(encoded).hexdigest()
    with tarfile.open(target, "x:gz", compresslevel=2) as archive:
        for name in sorted(files):
            archive.add(ROOT / name, arcname="project/" + name, recursive=False)
        info = tarfile.TarInfo("recovery_manifest.json")
        info.size = len(encoded)
        archive.addfile(info, io.BytesIO(encoded))
    observed = {}
    with tarfile.open(target, "r|gz") as archive:
        for item in archive:
            assert item.isfile() and item.name in expected
            stream, digest = archive.extractfile(item), hashlib.sha256()
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
            observed[item.name] = digest.hexdigest()
            assert observed[item.name] == expected[item.name]
    assert observed == expected
    return len(expected)


def prepare(config):
    config = Path(config).resolve()
    cfg, frozen_path = read(config), config.with_suffix(".frozen.json")
    assert not frozen_path.exists() and not (ROOT / "runs" / cfg["run_id"]).exists()
    assert cfg["method"] == "fixed_R3_access_channel_diagnosis"
    assert cfg["diagnostic_arms"] == ARMS and cfg["planned_new_native_calls"] == 16
    assert cfg["planned_new_teacher_calls"] == 0
    parent = ROOT / cfg["reference_run"]
    prior = read(ROOT / cfg["reference_config"])
    assert cfg["generation"] == prior["generation"]
    assert cfg["diagnostic_source_ids"] == cfg["training_ids"][24:32] == [362, 472, 234, 430, 604, 246, 559, 624]
    failure = read(parent / "failure.json")
    assert failure["actual_native_teacher_calls"] == [120, 3]
    assert failure["error"] == "InterruptedError('Operator stop at artifact-safe boundary')"
    assert not (parent / "teacher/update_b4/wire_request.json").exists()
    launch = read(ROOT / cfg["reference_launch"])
    proc = Path("/proc") / str(launch["pid"])
    if proc.exists():
        state = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        assert state[0] == "Z" or state[19] != launch["process_start_ticks"]
    terminal = read(ROOT / cfg["reference_terminal_preservation"])
    assert terminal["all_members_verified"] and terminal["different_filesystems_verified"]
    assert sha(terminal["archive"]) == sha(terminal["rootdisk_copy"]) == terminal["archive_sha256"]
    previous_bindings = read((ROOT / cfg["reference_config"]).with_suffix(".frozen.json"))["files"]
    assert all(sha(p) == digest for p, digest in previous_bindings.items())
    environment = read(ROOT / cfg["inference_environment"])
    live = Path("/proc") / str(environment["pid"])
    assert [s.decode() for s in (live / "cmdline").read_bytes().split(b"\0") if s] == environment["actual_argv"]
    assert (live / "stat").read_text().rsplit(")", 1)[1].split()[19] == environment["process_start_ticks"]
    packet = read(ROOT / cfg["input_packet"])
    assert [r["id"] for r in packet["documents"]] == cfg["training_ids"]
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    sources = {r["id"]: r for r in author["documents"]}
    assert packet["public_hypotheses"] == author["labels"]
    assert all(set(r) == {"id", "text", "spans"} and r == {k: sources[r["id"]][k] for k in r} for r in packet["documents"])
    bank = read(ROOT / cfg["reference_publication"])["publication"]
    assert len(bank) == 15 and csha(bank) == cfg["reference_bank_canonical_sha256"]
    references = read(parent / "b4_before_complete.json")["units"]
    assert len(references) == 24 and len({u["response"]["raw_id"] for u in references}) == 24
    assert {u["document_id"] for u in references} == set(cfg["diagnostic_source_ids"])
    meter, token_counts = WireClient(cfg["generation"]), {}
    for u in references:
        p, raw = read(u["payload"]), read(u["raw_artifact"])
        request = raw["calls"][0]["request"]
        assert len(raw["calls"]) == 1 and raw["transport_error"] is None
        assert raw["response"] == u["response"] and u["response"]["finish_reason"] == "stop"
        assert request["messages"] == p["messages"] and request["response_format"]["json_schema"]["schema"] == p["schema"]
        assert all(request[k] == cfg["generation"][k] for k in ("model", "seed", "temperature", "top_p", "top_k", "max_tokens"))
        validate(json.loads(u["response"]["content"]), p["schema"])
        assert json.loads(p["messages"][1]["content"])["full_contract_with_original_span_markers"] == marked_text(sources[u["document_id"]])
    for row in packet["documents"][24:]:
        for arm in ARMS:
            token_counts[f"{row['id']}:{arm}"] = payload(cfg, row, arm, bank, meter)["prompt_tokens"]
    receipt = ROOT / cfg["preparation_receipt"]
    RunStore.immutable_json(receipt, {"at": now(), "prior_run_terminal_and_double_archive_verified": True,
        "prior_frozen_bindings_unchanged": len(previous_bindings), "original_TRAIN_full_source_and_schema_equal": True,
        "all24_reference_native_wires_audited": True, "compact_access_facts_roundtrip_exact": True,
        "ordinary_input_changed_only_by_same_verbatim_R3_criteria": True, "planned_new_native_teacher_calls": [16, 0],
        "actual_new_native_teacher_calls": [0, 0], "prospective_prompt_tokens": token_counts,
        "official_DEV_TEST_contents_unopened": True, "teacher_not_called": True})
    paths = {Path(p) for p in previous_bindings}
    paths.update(p for p in (ROOT / "legal_skill_guard").rglob("*.py") if p.is_file())
    paths.update([Path(__file__).resolve(), config, receipt])
    paths.update(ROOT / cfg[k] for k in ("method_protocol", "reference_config", "reference_publication", "reference_launch", "reference_terminal_preservation"))
    paths.update([parent / "b4_before_complete.json", parent / "failure.json", (ROOT / cfg["reference_config"]).with_suffix(".frozen.json")])
    paths.update(Path(u[k]) for u in references for k in ("payload", "raw_artifact"))
    bindings = {str(p.resolve()): sha(p) for p in sorted(paths)}
    RunStore.immutable_json(frozen_path, {"config_sha256": sha(config), "files": bindings})
    files = {str(Path(p).relative_to(ROOT)): digest for p, digest in bindings.items()}
    files[str(frozen_path.relative_to(ROOT))] = sha(frozen_path)
    files.update({str(p.relative_to(ROOT)): sha(p) for p in (ROOT / ".git").rglob("*") if p.is_file()})
    target = ROOT.parent / "legal-skill-backups" / (cfg["run_id"] + "-full-source-Git-before-native.tar.gz")
    members = verified_archive(target, files, {"at": now(), "files": files, "full_Git_included": True,
        "actual_new_native_teacher_calls": [0, 0], "same_host_not_offsite_weights_or_auth": True})
    destination = Path(cfg["rootdisk_backup_directory"]) / target.name
    assert not destination.exists() and destination.parent.stat().st_dev != target.stat().st_dev
    shutil.copy2(target, destination)
    assert sha(destination) == sha(target)
    RunStore.immutable_json(ROOT / cfg["prelaunch_backup_receipt"], {"at": now(), "archive": str(target),
        "archive_sha256": sha(target), "rootdisk_copy": str(destination), "copy_sha256": sha(destination),
        "all_members_verified": True, "members": members, "different_filesystems_verified": True,
        "full_Git_included": True, "same_host_not_offsite_weights_or_auth": True})
    print(compact({"prepared": cfg["run_id"], "bound_files": len(bindings), "all_members_verified": members,
        "planned_new_native_teacher_calls": [16, 0], "maximum_prompt_tokens": max(token_counts.values())}), flush=True)


class AccessChannelStudy(MemberLearning):
    def __init__(self, config):
        AcquisitionStudy.__init__(self, config)
        assert self.cfg["method"] == "fixed_R3_access_channel_diagnosis"
        assert self.cfg["planned_new_teacher_calls"] == 0
        self.bank = read(ROOT / self.cfg["reference_publication"])["publication"]
        assert csha(self.bank) == self.cfg["reference_bank_canonical_sha256"]

    def progress(self, stage, **extra):
        Comparison.progress(self, stage, diagnostic_only=True, referenced_actual_answers=24, **extra)

    def payload(self, row, arm, bank):
        return payload(self.cfg, row, arm, bank, self.meter)

    def teacher_call(self, *args, **kwargs):
        raise AssertionError("No teacher calls permitted in the declared delivery diagnosis")

    def execute(self):
        self.check()
        self.record("declaration.json", {"at": now(), "config": self.cfg, "frozen_bindings": self.bindings.copy(),
            "all16_answers_before_unified_grading": True, "same_R3_not_new_training": True,
            "reference_answers_reused_explicitly_not_new_calls": 24, "official_DEV_TEST_unopened": True})
        rows = [r for r in self.training if r["id"] in self.cfg["diagnostic_source_ids"]]
        assert [r["id"] for r in rows] == self.cfg["diagnostic_source_ids"]
        entries = self.freeze_phase("fixed_R3_delivery", rows, ARMS)
        scored = self.audit_and_grade([self.answer(entry) for entry in entries])
        references = read(ROOT / self.cfg["reference_run"] / "b4_before_complete.json")["units"]
        conditions = {arm: [u for u in (scored if arm in ARMS else references) if u["condition"] == arm]
            for arm in ["strong_empty", "ordinary", "skills", *ARMS]}
        assert all(len(values) == 8 for values in conditions.values())
        comparisons = {arm: {control: paired_effect(conditions[control], conditions[arm],
            seed=self.cfg["analysis"]["seed"], replicates=self.cfg["analysis"]["bootstrap_replicates"])
            for control in ("strong_empty", "ordinary", "skills")} for arm in ARMS}
        result = {"at": now(), "run_id": self.run_id, "actual_new_native_teacher_calls": [len(self.native), len(self.teachers)],
            "referenced_actual_answers_not_new_calls": 24, "source_ids": self.cfg["diagnostic_source_ids"],
            "metrics": {arm: points(values) for arm, values in conditions.items()}, "comparisons": comparisons,
            "bank_unchanged": self.bank, "all_new_units": scored,
            "actual_new_native_usage": {k: sum(r["response"][k] for r in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "not_online_training_independent_repeat_or_official_TEST": True,
            "compact_arm_changes_representation_and_legend_not_pure_length_only": True,
            "ordinary_arm_tests_existing_calibrated_candidates_plus_same_criteria_not_query_pruning": True}
        assert len(self.native) == 16 and not self.teachers and self.teacher_attempts == 0
        self.check()
        self.record("completion.json", result)
        self.preserve_phase("complete_terminal")
        RunStore.atomic_json(self.out / "progress.json", {"state": "completed", **result})
        print(compact({"completed": self.run_id, "metrics": result["metrics"], "actual_new_native_teacher_calls": [16, 0]}), flush=True)


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
        study = AccessChannelStudy(args.config)
        try:
            study.execute()
        except BaseException as error:
            failure = {"at": now(), "error": repr(error), "traceback": traceback.format_exc(),
                "actual_native_teacher_calls": [len(study.native), len(study.teachers)],
                "all_raw_partial_and_invalid_answers_and_costs_retained": True}
            RunStore.immutable_json(study.out / "failure.json", failure)
            RunStore.atomic_json(study.out / "progress.json", {"state": "failed", **failure})
            raise


if __name__ == "__main__":
    main()
