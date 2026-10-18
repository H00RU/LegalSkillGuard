"""Complete four-arm test of published-skill execution, not online completion.

Uses the actual terminal R3, never a selected earlier bank. Public applicability
determines execution blocks, with the same blocks/calls for the empty control.
The original joint interface is an additional strong control, not discarded.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import signal
import traceback
import zipfile
from pathlib import Path

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import Comparison, ROOT, now, points, read, sha
from legal_skill_guard.learning.member_contract import combine_block_responses, execution_blocks
from legal_skill_guard.learning.member_learning import MemberLearning, paired_effect
from legal_skill_guard.task import original_feedback
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

ARMS = ("joint_empty", "joint_skills", "scope_empty", "scope_skills")


def prepare(config):
    config = Path(config).resolve()
    cfg = read(config)
    assert cfg["method"] == "published_skill_execution_blocks"
    assert not config.with_suffix(".frozen.json").exists()
    assert not (ROOT / "runs" / cfg["run_id"]).exists()
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    originals = {r["id"]: r for r in author["documents"]}
    parent_cfg = read(ROOT / cfg["parent_config"])
    parent = ROOT / cfg["parent_run"]
    publications = sorted((parent / "publications").glob("b*.json"))
    assert publications[-1].resolve() == (ROOT / cfg["parent_publication"]).resolve()
    terminal = read(ROOT / cfg["parent_terminal_preservation"])
    assert terminal["state"] == "terminal_results_preserved" and terminal["all_members_verified"]
    assert sha(terminal["archive"]) == sha(terminal["rootdisk_copy"]) == terminal["archive_sha256"]
    assert not (parent / "completion.json").exists(), "Parent was safely stopped, not completed"
    bank = read(publications[-1])["publication"]
    blocks = execution_blocks(bank, author["labels"])
    reference = read(ROOT / cfg["development_reference_config"])
    ids = cfg["development_ids"]
    assert ids == reference["development_ids"] and len(ids) == len(set(ids)) == 16
    assert not set(ids) & set(parent_cfg["training_ids"])
    assert cfg["planned_new_native_calls"] == len(ids) * (2 + 2*len(blocks))
    assert cfg["planned_new_teacher_calls"] == 0
    packet = {"public_hypotheses": author["labels"], "actual_terminal_bank": bank,
        "execution_blocks": blocks, "documents": [
            {k: originals[d][k] for k in ("id", "text", "spans")} for d in ids],
        "already_developer_exposed_TRAIN_not_independent_heldout": True}
    RunStore.immutable_json(ROOT / cfg["input_packet"], packet)
    RunStore.immutable_json(ROOT / cfg["grading_only"], {
        "original_TRAIN_annotations": {
            str(d): originals[d]["annotation_sets"][0]["annotations"] for d in ids},
        "never_read_by_payload_or_native_generation": True})
    files = list((ROOT / "legal_skill_guard").rglob("*.py"))
    files += [Path(__file__).resolve(), config, ROOT / "tests/test_learning_contract.py"]
    files += [ROOT / cfg[k] for k in ("source_archive", "parent_config", "parent_publication",
        "parent_terminal_preservation", "development_reference_config", "input_packet",
        "grading_only", "inference_environment", "method_protocol")]
    RunStore.immutable_json(config.with_suffix(".frozen.json"), {
        "config_sha256": sha(config), "files": {str(p.resolve()): sha(p) for p in files}})
    print(json.dumps({"prepared": cfg["run_id"], "blocks": blocks,
        "planned_native_teacher_calls": [cfg["planned_new_native_calls"], 0]}), flush=True)


class GroupedTransfer(MemberLearning):
    def __init__(self, config):
        # Reuse source payloads, original scoring and native calls, not the old
        # 32-source/four-batch constructor or any retriever/model/teacher setup.
        self.cfg, self.config_path = read(config), Path(config).resolve()
        binding = read(self.config_path.with_suffix(".frozen.json"))
        assert binding["config_sha256"] == sha(self.config_path)
        self.bindings = {**binding["files"], str(self.config_path.with_suffix(".frozen.json")):
                         sha(self.config_path.with_suffix(".frozen.json"))}
        self.run_id, self.out = self.cfg["run_id"], ROOT / "runs" / self.cfg["run_id"]
        assert not self.out.exists(), "New Run ID, never overwrite or retry"
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["documents"]
        self.bank, self.blocks = packet["actual_terminal_bank"], packet["execution_blocks"]
        assert self.blocks == execution_blocks(self.bank, self.labels)
        self.system, self.meter = self.cfg["bundled_solver_system"], WireClient(self.cfg["generation"])
        self.native, self.teachers, self.units = [], [], []
        self.teacher_attempts, self.current_batch, self.stop, self.inherited_count = 0, 0, False, 0
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def teacher_call(self, *args, **kwargs):
        raise AssertionError("No new teacher or bank selection in this execution test")

    def freeze_inputs(self):
        inputs = {}
        for index, row in enumerate(self.training):
            for arm in ARMS:
                blocks = self.blocks if arm.startswith("scope_") else [list(self.labels)]
                for b, keys in enumerate(blocks):
                    payload = self.payload(row, "skills" if arm.endswith("skills") else "strong_empty",
                                           self.bank, hypothesis_ids=keys)
                    path = self.record(f"inputs/{row['id']}/{arm}/block{b}.json", {
                        **payload, "condition": arm, "hypothesis_ids": keys})
                    inputs[(row["id"], arm, b)] = path
            # Same source, task, decoding, schema and partition. The only arm
            # content difference is the projected, verbatim skill procedures.
            for kind in ("joint", "scope"):
                blocks = self.blocks if kind == "scope" else [list(self.labels)]
                for b, _ in enumerate(blocks):
                    a, z = (read(inputs[(row["id"], kind+"_"+arm, b)]) for arm in ("empty", "skills"))
                    ac, zc = json.loads(a["messages"][1]["content"]), json.loads(z["messages"][1]["content"])
                    zc.pop("evidence_selection_criteria", None)
                    assert ac == zc and a["schema"] == z["schema"]
                    assert a["messages"][0] == z["messages"][0]
        assert len(inputs) == self.cfg["planned_new_native_calls"]
        self.record("all_inputs_frozen_before_generation.json", {
            "paths": [str(p) for p in inputs.values()], "exact_empty_skill_pair_checks": True,
            "actual_new_native_teacher_calls": [0, 0], "all_original17_in_every_logical_answer": True})
        return inputs

    def execute(self):
        self.check()
        self.record("declaration.json", {"at": now(), "config": self.cfg,
            "actual_terminal_bank": self.bank, "blocks": self.blocks,
            "frozen_bindings": self.bindings.copy(),
            "not_TFGRPO_rollout_groups_or_independent_online_learning": True,
            "no_current_Gold_answer_repair_or_effect_selection": True})
        inputs = self.freeze_inputs()
        answers = []
        for index, row in enumerate(self.training):
            # Fixed alternating order, never chosen from correctness.
            order = ARMS if index % 2 == 0 else tuple(reversed(ARMS))
            for arm in order:
                fragments = []
                blocks = self.blocks if arm.startswith("scope_") else [list(self.labels)]
                for b, keys in enumerate(blocks):
                    path = inputs[(row["id"], arm, b)]
                    payload = read(path)
                    dest = self.out / f"native/{row['id']}/{arm}/block{b}.json"
                    response = Comparison.call(self, dest, payload["messages"], payload["schema"],
                        self.cfg["generation"]["max_tokens"], {
                            "stage": "complete16_execution_transfer", "arm": arm,
                            "document_id": row["id"], "call_role": f"block_{b}",
                            "original_hypothesis_ids": keys, "input_payload": str(path)})
                    fragments.append({"response": response, "schema": payload["schema"],
                        "hypothesis_ids": keys, "native_artifact": str(dest), "payload": str(path)})
                logical = combine_block_responses(fragments, self.labels)
                value = {"document_id": row["id"], "condition": arm, "response": logical,
                         "fragments": fragments, "not_scored_until_all16_all4arms_exist": True}
                self.record(f"logical_answers/{row['id']}/{arm}.json", value)
                answers.append(value)
        assert len(self.native) == self.cfg["planned_new_native_calls"]
        assert len(answers) == 4*len(self.training)
        ids = [r["response"]["raw_id"] for r in self.native]
        assert len(set(ids)) == len(ids) and not self.teachers
        gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        documents = {r["id"]: r for r in self.training}
        for unit in answers:
            row, annotations = documents[unit["document_id"]], gold[str(unit["document_id"])]
            feedback = original_feedback(unit["response"], row, annotations, list(self.labels))
            audited = original_score(unit["response"], row, annotations, list(self.labels))
            close(audited, {k: feedback[k] for k in audited})
            self.units.append({**unit, **feedback})
        groups = {arm: [u for u in self.units if u["condition"] == arm] for arm in ARMS}
        result = {"at": now(), "run_id": self.run_id,
            "metrics": {arm: points(units) for arm, units in groups.items()},
            "scope_skill_effect": paired_effect(groups["scope_empty"], groups["scope_skills"],
                seed=2026101813, replicates=5000),
            "joint_skill_effect": paired_effect(groups["joint_empty"], groups["joint_skills"],
                seed=2026101814, replicates=5000),
            "actual_new_native_teacher_calls": [len(self.native), 0], "units": self.units,
            "invalid_logical_answers": {a: sum(not u["public_valid"] for u in v) for a,v in groups.items()},
            "all_original_denominators_and_adverse_results_retained": True,
            "not_independent_heldout_or_online_learning_or_official_TEST": True,
            "no_goal_achievement_or_breakthrough_claim_from_protocol_completion": True}
        self.record("completion.json", result)
        RunStore.atomic_json(self.out / "progress.json", {"state": "completed", **result})
        print(json.dumps({"completed": self.run_id, "metrics": result["metrics"]}), flush=True)


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
        study = GroupedTransfer(args.config)
        try:
            study.execute()
        except BaseException as error:
            failure = {"at": now(), "error": repr(error), "traceback": traceback.format_exc(),
                "actual_new_native_teacher_calls": [len(study.native), len(study.teachers)],
                "no_retry_answer_repair_or_bank_selection": True}
            study.record("failure.json", failure)
            RunStore.atomic_json(study.out / "progress.json", {"state": "failed", **failure})
            raise


if __name__ == "__main__":
    main()
