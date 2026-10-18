"""Past-source skill induction and complete, paired two-target transfer.

One frozen lawyer natively decides relations, then selects original members.
The relation-only/dual-policy arms share their identical native decision, not
their evidence calls. Both actual physical cost and logical endpoint cost are
recorded. No efficacy admission, label repair or current evaluation feedback.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import pickle
import signal
import traceback
import zipfile
from pathlib import Path

from jsonschema import ValidationError, validate

from legal_skill_guard.data import source_components
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.acquisition import source_messages
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.decision_evidence import (
    DECISION_SYSTEM, EVIDENCE_SYSTEM, GUIDANCE_SCHEMA, assemble_native,
    channel_criteria, convert_parent, decision_payload, evidence_payload,
)
from legal_skill_guard.learning.evidence_programs import evidence_proposals
from legal_skill_guard.learning.experiment import Comparison, ROOT, now, points, read, sha
from legal_skill_guard.learning.member_contract import teacher_sources
from legal_skill_guard.learning.member_learning import paired_effect
from legal_skill_guard.learning.packing import table
from legal_skill_guard.learning.publication import (
    apply_differential_publication, differential_schema, publication_statistics,
)
from legal_skill_guard.task import original_feedback

ARMS = ("joint_empty", "factored_empty", "relation_only", "dual_skills")
WRITER = (
    "Learn reusable legal skills from ONLY the complete already-seen original "
    "TRAIN contracts, original annotations and actual historical own public "
    "observations supplied here. No tools, new sources, private reasoning or "
    "outside law. This is label-assisted external skill learning, not model "
    "fine-tuning or canonical TF-GRPO. The SAME frozen8B lawyer decides every "
    "original legal label and every final citation natively. The task NOW has "
    "two native actions, corresponding to its two existing benchmark outputs: "
    "first relation choices and public reasons for all17 exact hypotheses; "
    "then original-SPAN evidence arrays for those actual native choices. The "
    "second action cannot revise labels. Both see the COMPLETE contract and "
    "the same fallible ordinary membership candidates fitted on these same42 "
    "past sources. They can reject candidates and cite any original index. "
    "This ordinary supervised tool is shared with all controls, not your gain. "
    "Each skill guidance has relation_criterion and evidence_criterion, each "
    "nullable but at least one meaningful. Only relation_criterion reaches "
    "action1; only evidence_criterion reaches action2. First-action reasons and "
    "relation prose are NOT passed to action2; only its native choices are. "
    "These are task-output channels, not fixed skill topics, fixed skill types "
    "or a fixed number of records. Learn compact operational legal decision "
    "boundaries for relation guidance; learn source-observable evidence member "
    "inclusion AND exclusion boundaries for evidence guidance. Merely useful "
    "definitions, context, neighbours and section headers are not automatically "
    "original annotated members. Conversely retain independently responsive "
    "redundant members when the original training annotations warrant them. "
    "Compare semantic proof versus observed annotation membership across all "
    "supplied positive/negative cases, including correct-label wrong-evidence "
    "observations. Do not fix evidence errors by blindly reversing relations "
    "or expanding all read context. Avoid circular 'include if annotated' "
    "instructions: runtime Gold does not exist. Unannotated spans are benchmark "
    "nonmembers, not universal legal falsehoods. Runtime guidance must not "
    "contain case IDs, span indices, parties, dates, answer tables, memorized "
    "quotations, special document fingerprints or output tricks. Audit source "
    "IDs/rationales never reach the lawyer. The exact terminal procedural R3 "
    "parent was mechanically renamed: its old full text is relation_criterion; "
    "evidence_criterion is null. This is NOT evidence that its mixed text is "
    "correct for action1. You may revise its boundaries and assign learned "
    "member-selection guidance to action2 using the supplied sources. Historical "
    "observations retain their ACTUAL old stages/banks; they are not new "
    "factorized rollouts and have not been fabricated or relabeled. Review all "
    "complete sources, original labels and actual observations, including "
    "successes and failures, before editing. Publish CREATE/UPDATE/DELETE/MERGE "
    "against the exact parent, or explicit NOOP; no forced growth/count/topics "
    "and no score-based acceptance or rollback. Unmentioned skills remain "
    "verbatim. UPDATE preserves its target ID. Targets are distinct unconsumed "
    "original parent IDs, not forward references; CREATE targets[]; UPDATE and "
    "DELETE one target; MERGE>=2; only DELETE skill=null. Other resulting skills "
    "contain both guidance keys with at least one non-null concise criterion. "
    "Cite only supplied source_case_ids in audit rationales. Fit the complete "
    "serialized library in <=3200 target tokens under4096 hard cap, without "
    "truncation or retry. Return exactly the requested differential JSON."
)


def prepare(config):
    config = Path(config).resolve()
    cfg = read(config)
    assert cfg["method"] == "native_decision_evidence_skill_channels"
    assert not config.with_suffix(".frozen.json").exists()
    assert not (ROOT / "runs" / cfg["run_id"]).exists()
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    original = {r["id"]: r for r in author["documents"]}
    manifest = read(ROOT / cfg["ordinary_manifest"])
    seen, future = manifest["seen_original_source_ids"], cfg["development_ids"]
    assert len(seen) == len(set(seen)) == 42
    assert len(future) == len(set(future)) == 16 and not set(seen) & set(future)
    assert not any(set(g) & set(seen) and set(g) & set(future)
                   for g in source_components(author["documents"]))
    assert sha(manifest["path"]) == manifest["pickle_sha256"]
    parent = read(ROOT / cfg["parent_publication"])["publication"]
    converted = convert_parent(parent, author["labels"])
    original_parent_cfg = read(ROOT / cfg["parent_config"])
    old_cfg = read(ROOT / cfg["historical_query_config"])
    assert seen == original_parent_cfg["training_ids"][:24] + old_cfg["training_ids"]
    paths = [ROOT / cfg["parent_run"] / f"ungraded_answers/b3_after_all_seen/skills/{d}.json"
             for d in original_parent_cfg["training_ids"][:24]]
    paths += sorted((ROOT / cfg["historical_query_run"]).glob("batch*_*/evolving_memory/*.public.json"))
    paths = [p for p in paths if read(p)["document_id"] in seen]
    observations = []
    for path in paths:
        unit = read(path)
        r = unit["response"]
        observations.append({"document_id": unit["document_id"],
            "actual_historical_metadata": {k: unit[k] for k in (
                "stage", "condition", "arm", "bank_sha256", "published_library_sha256") if k in unit},
            "actual_public_answer": {k: r[k] for k in ("content", "finish_reason", "raw_id")},
            "actual_unit_path": str(path), "actual_unit_sha256": sha(path),
            "not_a_new_two_action_rollout": True})
    assert {o["document_id"] for o in observations} == set(seen)
    public = lambda d: {k: original[d][k] for k in ("id", "text", "spans")}
    train_gold = {str(d): original[d]["annotation_sets"][0]["annotations"] for d in seen}
    teacher = {"public_hypotheses": author["labels"], "current_parent_library": converted,
        "complete_past42_original_sources_and_Gold": teacher_sources([public(d) for d in seen], train_gold),
        "actual_historical_own_public_observations": table(observations),
        "same42_common_ordinary_model_manifest": manifest,
        "future_action1_system": DECISION_SYSTEM, "future_action2_system": EVIDENCE_SYSTEM,
        "no_new16_source_annotation_or_score_or_private_reasoning": True,
        "encoding_legend": "Source and observation tables zip ordered columns with rows. Source text is complete with original SPAN markers; original annotations are keyed tables. Every original source character and annotation is preserved."}
    RunStore.immutable_json(ROOT / cfg["teacher_body"], teacher)
    RunStore.immutable_json(ROOT / cfg["input_packet"], {
        "public_hypotheses": author["labels"], "documents": [public(d) for d in future],
        "converted_actual_parent": converted, "past_seen_ids": seen,
        "already_developer_exposed_TRAIN_not_independent_heldout": True})
    RunStore.immutable_json(ROOT / cfg["grading_only"], {
        "original_TRAIN_annotations": {str(d): original[d]["annotation_sets"][0]["annotations"] for d in future},
        "not_read_until_all16_all4_logical_arm_answers_exist": True})
    files = list((ROOT / "legal_skill_guard").rglob("*.py"))
    files += [Path(__file__).resolve(), config, ROOT / "tests/test_learning_contract.py", Path(manifest["path"])]
    files += paths + [ROOT / cfg[k] for k in ("source_archive", "parent_config", "parent_publication",
        "historical_query_config", "ordinary_manifest", "input_packet", "grading_only", "teacher_body",
        "inference_environment", "method_protocol")]
    ledger = read(ROOT / cfg["teacher"]["ledger"])
    assert max(r["sequence"] for r in ledger["reservations"]) + 1 <= ledger["max_invocations"]
    RunStore.immutable_json(config.with_suffix(".frozen.json"), {
        "config_sha256": sha(config), "files": {str(p.resolve()): sha(p) for p in files}})
    print(json.dumps({"prepared": cfg["run_id"], "past_sources": len(seen),
        "historical_own_observations": len(observations), "future_sources": len(future),
        "planned_physical_native_teacher_calls": [96, 1], "planned_logical_call_uses": 112}), flush=True)


class DecisionEvidenceTransfer(Comparison):
    def __init__(self, config):
        self.cfg, self.config_path = read(config), Path(config).resolve()
        frozen = read(self.config_path.with_suffix(".frozen.json"))
        assert frozen["config_sha256"] == sha(self.config_path)
        self.bindings = {**frozen["files"], str(self.config_path.with_suffix(".frozen.json")):
                         sha(self.config_path.with_suffix(".frozen.json"))}
        self.run_id, self.out = self.cfg["run_id"], ROOT / "runs" / self.cfg["run_id"]
        assert not self.out.exists()
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.documents, self.parent = packet["public_hypotheses"], packet["documents"], packet["converted_actual_parent"]
        self.native, self.teachers, self.units, self.answers = [], [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 0, False
        self.meter = WireClient(self.cfg["generation"])
        self.manifest = read(ROOT / self.cfg["ordinary_manifest"])
        with Path(self.manifest["path"]).open("rb") as stream:
            self.model = pickle.load(stream)
        assert not self.model.programs and set(self.model.corpus_.doc_ids) == set(str(d) for d in packet["past_seen_ids"])
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def record(self, name, value):
        path = self.out / name
        RunStore.immutable_json(path, value)
        self.bindings[str(path)] = sha(path)
        return path

    def progress(self, stage, **extra):
        Comparison.progress(self, stage, completed_logical_answers=len(self.answers), **extra)

    def generate(self, row, role, messages, schema):
        path = self.record(f"inputs/{row['id']}/{role}.json", {"messages": messages, "schema": schema})
        response = self.call(self.out / f"native/{row['id']}/{role}.json", messages, schema,
            self.cfg["generation"]["max_tokens"], {"stage": "complete16_two_target_transfer",
                "arm": role, "document_id": row["id"], "call_role": role, "input_payload": str(path)})
        return response

    def logical(self, row, arm, response):
        item = {"document_id": row["id"], "condition": arm, "response": response,
                "not_scored_until_all16_all4_arms_exist": True}
        self.record(f"logical_answers/{row['id']}/{arm}.json", item)
        self.answers.append(item)

    def factored(self, row, proposals, arms):
        bank = [] if arms == ("factored_empty",) else self.bank
        messages, ds = decision_payload(row, self.labels, proposals, bank)
        decision = self.generate(row, "empty_decision" if arms == ("factored_empty",) else "shared_skill_decision", messages, ds)
        valid = decision["finish_reason"] == "stop"
        try:
            validate(json.loads(decision["content"]), ds)
        except (ValueError, TypeError, ValidationError):
            valid = False
        for arm in arms:
            evidence, es = None, {}
            if valid:
                messages, es = evidence_payload(row, self.labels, proposals, decision, ds,
                                               self.bank if arm == "dual_skills" else [])
                evidence = self.generate(row, arm+"_evidence", messages, es)
            self.logical(row, arm, assemble_native(decision, evidence, ds, es, self.labels))

    def execute(self):
        self.check()
        self.record("declaration.json", {"at": now(), "config": self.cfg,
            "frozen_bindings": self.bindings.copy(), "converted_actual_parent": self.parent,
            "not_independent_online_repeat_or_official_TEST": True})
        teacher = read(ROOT / self.cfg["teacher_body"])
        seen = self.manifest["seen_original_source_ids"]
        schema = differential_schema(self.labels, self.parent, seen, guidance_schema=GUIDANCE_SCHEMA)
        value = self.teacher_call("dual_channel_source_update", WRITER, teacher, schema)
        self.bank = apply_differential_publication(self.parent, value, self.labels, seen, guidance_schema=GUIDANCE_SCHEMA)
        for channel in ("relation_criterion", "evidence_criterion"):
            channel_criteria(self.bank, self.labels, channel)
        tokens = self.meter.token_count(text=json.dumps(self.bank, ensure_ascii=False, separators=(",", ":")))
        assert tokens <= self.cfg["library_token_hard_cap"], "No trimming, retry or bank selection"
        self.record("publication.json", {"at": now(), "parent": self.parent, "delta": value,
            "publication": self.bank, "statistics": publication_statistics(self.parent, value, self.bank, tokens),
            "all_valid_CRUD_NOOP_publish_without_efficacy_admission": True})
        for index, row in enumerate(self.documents):
            proposals = evidence_proposals(self.model, row, self.labels)
            self.record(f"common_candidates/{row['id']}.json", proposals)
            joint = lambda: self.logical(row, "joint_empty", self.generate(row, "joint_empty",
                *source_messages(row, self.labels, self.cfg["bundled_solver_system"], [], proposals)[:2]))
            if index % 2 == 0:
                joint()
                self.factored(row, proposals, ("factored_empty",))
                self.factored(row, proposals, ("relation_only", "dual_skills"))
            else:
                self.factored(row, proposals, ("dual_skills", "relation_only"))
                self.factored(row, proposals, ("factored_empty",))
                joint()
        assert len(self.answers) == 64 and len(self.teachers) == 1 and len(self.native) <= 96
        actual_ids = [n["response"]["raw_id"] for n in self.native]
        assert len(set(actual_ids)) == len(actual_ids)
        gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        rows = {r["id"]: r for r in self.documents}
        for item in self.answers:
            row, g = rows[item["document_id"]], gold[str(item["document_id"])]
            score = original_feedback(item["response"], row, g, list(self.labels))
            audit = original_score(item["response"], row, g, list(self.labels))
            close(audit, {k: score[k] for k in audit})
            self.units.append({**item, **score})
        groups = {a: [u for u in self.units if u["condition"] == a] for a in ARMS}
        for d in rows:
            a, b = (next(u for u in groups[x] if u["document_id"] == d) for x in ("relation_only", "dual_skills"))
            assert a["response"]["actual_native_raw_ids"][0] == b["response"]["actual_native_raw_ids"][0]
        logical_uses = sum(len(u["response"].get("actual_native_raw_ids", [u["response"]["raw_id"]])) for u in self.units)
        result = {"at": now(), "run_id": self.run_id, "metrics": {a: points(u) for a,u in groups.items()},
            "effects": {a: paired_effect(groups[a], groups["dual_skills"], seed=2026101800+i, replicates=5000)
                        for i,a in enumerate(ARMS[:-1])},
            "actual_new_native_teacher_calls": [len(self.native), len(self.teachers)],
            "logical_endpoint_native_call_uses": logical_uses,
            "shared_actual_decisions_not_free_extra_deployment_calls": True,
            "invalid_logical_answers": {a: sum(not u["public_valid"] for u in units) for a,units in groups.items()},
            "units": self.units, "final_bank": self.bank,
            "all_original_denominators_and_adverse_results_retained": True,
            "not_independent_heldout_or_complete_online_learning_or_official_TEST": True}
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
        study = DecisionEvidenceTransfer(args.config)
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
