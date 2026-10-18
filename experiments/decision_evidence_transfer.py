"""Legal skill induction, disclosed ablations and current ranked online learning.

One frozen lawyer natively decides relations, then selects original members.
The relation-only/dual-policy arms share their identical native decision, not
their evidence calls. Both actual physical cost and logical endpoint cost are
recorded. No efficacy admission, label repair or current evaluation feedback.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import json
import pickle
import signal
import traceback
import zipfile
from pathlib import Path

import numpy as np
from jsonschema import ValidationError, validate

from legal_skill_guard.data import source_components
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.decision_evidence import (
    DECISION_SYSTEM, EVIDENCE_SYSTEM, GUIDANCE_SCHEMA, assemble_native,
    channel_criteria, convert_parent, decision_payload, evidence_payload, joint_payload,
)
from legal_skill_guard.learning.evidence_programs import evidence_proposals, fit_program_model
from legal_skill_guard.learning.experiment import Comparison, ROOT, now, points, read, sha
from legal_skill_guard.learning.member_contract import teacher_sources
from legal_skill_guard.learning.member_learning import paired_effect
from legal_skill_guard.learning.packing import table
from legal_skill_guard.learning.publication import (
    apply_differential_publication, differential_schema, publication_statistics,
)
from legal_skill_guard.task import original_feedback
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

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
        self.phase = "complete16_two_target_transfer"
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
        path = self.record(f"inputs/{self.phase}/{row['id']}/{role}.json", {"messages": messages, "schema": schema})
        response = self.call(self.out / f"native/{self.phase}/{row['id']}/{role}.json", messages, schema,
            self.cfg["generation"]["max_tokens"], {"stage": self.phase,
                "arm": role, "document_id": row["id"], "call_role": role, "input_payload": str(path)})
        return response

    def logical(self, row, arm, response):
        item = {"document_id": row["id"], "condition": arm, "response": response,
                "stage": self.phase, "bank_sha256": csha(self.bank) if arm in ("relation_only", "dual_skills", "skills") else csha([]),
                "not_scored_until_all16_all4_arms_exist": True}
        self.record(f"logical_answers/{self.phase}/{row['id']}/{arm}.json", item)
        self.answers.append(item)
        return item

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
                *joint_payload(row, self.labels, proposals, self.cfg["bundled_solver_system"])))
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


ONLINE_WRITER = (
    "Update the exact current legal skill library using ONLY the "
    "complete already-seen original TRAIN sources, unmodified author labels "
    "and actual current-parent own public answers supplied here. No tools, "
    "outside law, private reasoning, future cases or invented rollouts. One "
    "frozen8B lawyer NOW generates all17 original choice/spans/reason answers "
    "together in ONE native call. Both relation_criterion and evidence_criterion "
    "are visible together, with their public hypothesis scopes. There is no "
    "separate evidence-only actor or frozen first-action verdict. It reads the "
    "COMPLETE source plus exact candidate-original-text reading anchors. The main "
    "ordinary tool is fixed on the same42 "
    "past sources; its binary candidates AND complete all-original-index "
    "membership rank ordering are now visible. Ranking is a fallible search "
    "order, not a citation set; its tail can contain real members. Learn "
    "source-observable inclusion and exclusion boundaries and legal relation "
    "procedures, not a global numeric threshold, case lookup or index pattern. "
    "A correct relation with wrong members needs a member-boundary correction, "
    "not blind label reversal or a whole-section citation expansion. Consider "
    "independently responsive repeated evidence versus merely related context. "
    "Benchmark nonmembers are not universal legal falsehoods. Every current "
    "parent own episode answer is actual, including successes and failures; "
    "the earlier42 complete source/Gold remain supplied but their obsolete "
    "other-interface rollouts are not presented as current-parent answers. "
    "Review all supplied sources and parent records. Publish explicit CREATE, "
    "UPDATE, DELETE, MERGE or NOOP; no efficacy gate, best-bank rollback, forced "
    "growth/count/topic, second teacher or retry. Unmentioned skills remain "
    "verbatim. UPDATE keeps its target ID. Targets are distinct unconsumed "
    "original parent IDs; CREATE[]; UPDATE/DELETE one; MERGE>=2; only DELETE "
    "skill=null. Each resulting skill has id, distinct public hypothesis_ids, "
    "and guidance with required nullable relation_criterion/evidence_criterion, "
    "at least one meaningful. Runtime guidance must not contain parties, dates, "
    "case IDs, span integers, memorized quotations, answer tables or impossible "
    "runtime-Gold tests. Cite actual supplied source_case_ids only in audit "
    "rationale, not runtime. Keep complete serialized library <=3200 target "
    "tokens under4096 hard cap, without truncation. Return exact delta JSON."
)


def online_writer(complete_order):
    if complete_order:
        return ONLINE_WRITER
    return ONLINE_WRITER.replace(
        "past sources; its binary candidates AND complete all-original-index "
        "membership rank ordering are now visible. Ranking is a fallible search "
        "order, not a citation set; its tail can contain real members. Learn ",
        "past sources; only its fallible binary candidates and exact source "
        "anchors are visible, alongside the complete original contract. No "
        "complete rank-order list or source-size output quota is supplied. "
        "Candidates are not compulsory citations. The earlier ranked interface "
        "caused large-scale copied indices and is no longer used. Every own "
        "episode answer NOW supplied was really generated with this same "
        "canonical interface and exact parent bank, not copied from that failed "
        "interface. Learn ")


def prepare_online(config):
    config = Path(config).resolve()
    cfg = read(config)
    assert cfg["method"] in ("ranked_joint_online24_forward8", "canonical_joint_online_continuation")
    start = cfg.get("start_batch", 1)
    assert start in (1, 2)
    if start == 2:
        assert cfg["method"] == "canonical_joint_online_continuation" and not cfg["show_complete_member_order"]
    assert not config.with_suffix(".frozen.json").exists() and not (ROOT / "runs" / cfg["run_id"]).exists()
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    original = {r["id"]: r for r in author["documents"]}
    manifest = read(ROOT / cfg["ordinary_manifest"])
    past = manifest["seen_original_source_ids"]
    assert len(past) == len(set(past)) == 42 and sha(manifest["path"]) == manifest["pickle_sha256"]
    reference = read(ROOT / cfg["development_reference_config"])
    exclude = set(past + reference["development_ids"] + read(ROOT / cfg["excluded_parent_config"])["training_ids"])
    components = source_components(author["documents"])
    excluded = set().union(*(set(g) for g in components if set(g) & exclude))
    eligible = sorted(d for d in original if d not in excluded)
    ids = np.random.default_rng(cfg["source_only_seed"]).choice(eligible, size=32, replace=False).tolist()
    assert ids == cfg["episode_ids"] and not any(len(set(g) & set(ids)) > 1 for g in components)
    terminal = read(ROOT / cfg["parent_terminal_preservation"])
    assert terminal["state"] == "terminal_results_preserved" and terminal["all_members_verified"]
    assert sha(terminal["archive"]) == sha(terminal["rootdisk_copy"]) == terminal["archive_sha256"]
    bank = read(ROOT / cfg["parent_publication"])["publication"]
    for channel in ("relation_criterion", "evidence_criterion"):
        channel_criteria(bank, author["labels"], channel)
    public = lambda d: {k: original[d][k] for k in ("id", "text", "spans")}
    RunStore.immutable_json(ROOT / cfg["input_packet"], {
        "public_hypotheses": author["labels"], "documents": [public(d) for d in ids],
        "past_documents": [public(d) for d in past], "past_seen_ids": past,
        "converted_actual_parent": bank, "parent_already_two_channel_no_conversion_or_selection": True,
        "source_only_selection": {"seed": cfg["source_only_seed"], "eligible_ids": eligible,
            "excluded_original_and_source_component_ids": sorted(excluded),
            "no_selection_using_labels_or_outcomes": True},
        "episode_has_three_learning_batches_then_forward8": True,
        "this_run_inherits_first_episode_batch": start == 2})
    RunStore.immutable_json(ROOT / cfg["grading_only"], {
        "original_TRAIN_annotations": {str(d): original[d]["annotation_sets"][0]["annotations"] for d in past+ids},
        "teacher_gets_only_revealed_past42_and_episode_prefix": True,
        "all_current_batch_answers_precede_current_batch_grading": True})
    ledger = read(ROOT / cfg["teacher"]["ledger"])
    teachers = 4-start
    expected_calls = 136 if start == 1 else 120
    assert max(r["sequence"] for r in ledger["reservations"]) + teachers <= ledger["max_invocations"]
    assert cfg["planned_new_native_calls"] == expected_calls and cfg["planned_new_teacher_calls"] == teachers
    files = list((ROOT / "legal_skill_guard").rglob("*.py"))
    files += [Path(__file__).resolve(), config, ROOT / "tests/test_learning_contract.py", Path(manifest["path"])]
    files += [ROOT / cfg[k] for k in ("source_archive", "input_packet", "grading_only", "ordinary_manifest",
        "parent_publication", "parent_terminal_preservation", "development_reference_config",
        "excluded_parent_config", "inference_environment", "method_protocol")]
    if start == 2:
        prefix_path = ROOT / cfg["initial_ordinary_prefix_manifest"]
        prefix = read(prefix_path)
        assert prefix["source_ids"] == past+ids[:8] and sha(prefix["path"]) == prefix["sha256"]
        publication = read(ROOT / cfg["parent_publication"])
        assert publication["original_seen_source_ids"] == prefix["source_ids"]
        files += [prefix_path, Path(prefix["path"])]
    RunStore.immutable_json(config.with_suffix(".frozen.json"), {
        "config_sha256": sha(config), "files": {str(p.resolve()): sha(p) for p in files}})
    print(json.dumps({"prepared": cfg["run_id"], "new_episode_ids": ids,
        "inherited_episode_labels": (start-1)*8, "new_original_train_label_updates": teachers*8,
        "forward_readout": 8, "planned_native_teacher_CPUfits": [expected_calls, teachers, teachers]}), flush=True)


class RankedOnline(DecisionEvidenceTransfer):
    def __init__(self, config):
        super().__init__(config)
        self.bank = copy.deepcopy(self.parent)
        packet = read(ROOT / self.cfg["input_packet"])
        self.past, self.prefix_model = packet["past_documents"], self.model
        self.own_current, self.batch_summaries, self.fit_records = {}, [], []
        self.prefix_ids = list(packet["past_seen_ids"])
        if self.cfg.get("start_batch", 1) == 2:
            prefix = read(ROOT / self.cfg["initial_ordinary_prefix_manifest"])
            assert sha(prefix["path"]) == prefix["sha256"]
            with Path(prefix["path"]).open("rb") as stream:
                self.prefix_model = pickle.load(stream)
            self.prefix_ids = prefix["source_ids"]
            assert not self.prefix_model.programs
            assert self.prefix_ids == [r["id"] for r in self.past+self.documents[:8]]

    def logical(self, row, arm, response):
        if self.phase.endswith("_fixed_tool_control"):
            assert arm == "joint_empty"
            arm = "fixed_tool_empty"
        item = super().logical(row, arm, response)
        if arm == "skills":
            self.own_current[row["id"]] = item
        return item

    def score(self, answers):
        rows = {r["id"]: r for r in self.documents}
        gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        units = []
        for item in answers:
            row, g = rows[item["document_id"]], gold[str(item["document_id"])]
            f = original_feedback(item["response"], row, g, list(self.labels))
            audit = original_score(item["response"], row, g, list(self.labels))
            close(audit, {k: f[k] for k in audit})
            units.append({**item, **f})
        return units

    def update_online(self, seen):
        parent = copy.deepcopy(self.bank)
        assert all(self.own_current[r["id"]]["bank_sha256"] == csha(parent) for r in seen)
        gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        own = [self.own_current[r["id"]] for r in seen]
        before = self.score(own)
        ranked_observations = []
        complete_order = self.cfg.get("show_complete_member_order", True)
        for row in seen:
            source = evidence_proposals(self.model, row, self.labels)
            members = {h: {"binary_candidate_members": [v["original_span_index"] for v in p["candidates"]]}
                       for h,p in source["by_hypothesis"].items()}
            if complete_order:
                for h,p in source["by_hypothesis"].items():
                    members[h]["complete_original_member_rank_order"] = sorted(
                        range(len(p["raw_scores"])), key=lambda i: (-p["raw_scores"][i], i))
            ranked_observations.append({"document_id": row["id"], "by_hypothesis": members})
        body = {"public_hypotheses": self.labels, "current_parent_library": parent,
            "complete_original_past42_and_revealed_episode_sources_and_Gold": teacher_sources(self.past+seen, gold),
            "actual_current_parent_episode_public_answers": table(own),
            "actual_original_component_feedback": [{"document_id": u["document_id"],
                "by_hypothesis": {q["hypothesis_id"]: {k: q[k] for k in (
                    "label_correct", "evidence_tp", "evidence_fp", "evidence_fn", "joint_exact")}
                    for q in u["queries"]}, "public_valid": u["public_valid"]} for u in before],
            "actual_fixed42_visible_candidate_information": table(ranked_observations),
            "numeric_candidate_scores_archived_in_actual_inputs_not_resupplied_as_threshold_targets": True,
            "main_ordinary_tool_remains_fixed_on_original42": self.manifest,
            "future_joint_system": joint_payload(seen[0], self.labels,
                evidence_proposals(self.model, seen[0], self.labels),
                self.cfg["bundled_solver_system"], parent, complete_order=complete_order)[0][0]["content"],
            "complete_membership_rank_order_visible_in_single_joint_action": complete_order,
            "no_future_episode_sources_answers_annotations_or_official_DEV_TEST": True}
        name = f"online_b{self.current_batch}"
        self.record(f"learning_inputs/{name}.json", body)
        seen_ids = [r["id"] for r in self.past+seen]
        schema = differential_schema(self.labels, parent, seen_ids, guidance_schema=GUIDANCE_SCHEMA)
        value = self.teacher_call(name, online_writer(complete_order), body, schema)
        self.bank = apply_differential_publication(parent, value, self.labels, seen_ids, guidance_schema=GUIDANCE_SCHEMA)
        for channel in ("relation_criterion", "evidence_criterion"):
            channel_criteria(self.bank, self.labels, channel)
        tokens = self.meter.token_count(text=json.dumps(self.bank, ensure_ascii=False, separators=(",", ":")))
        assert tokens <= self.cfg["library_token_hard_cap"], "No repair, trimming, selected bank or retry"
        stats = publication_statistics(parent, value, self.bank, tokens)
        self.record(f"publications/b{self.current_batch}.json", {"at": now(), "parent": parent,
            "delta": value, "publication": self.bank, "statistics": stats,
            "original_seen_source_ids": seen_ids,
            "actual_current_parent_own_episode_answers": len(own),
            "all_valid_edits_publish_without_efficacy_admission": True})
        self.phase = f"b{self.current_batch}_after_seen"
        start = len(self.answers)
        for row in seen:
            self.joint(row, "skills", evidence_proposals(self.model, row, self.labels))
        after = self.score(self.answers[start:])
        self.units.extend(after)
        effect = paired_effect(before, after, seed=2026101810+self.current_batch, replicates=5000)
        self.record(f"update_effects/b{self.current_batch}.json", {"at": now(), "statistics": stats,
            "effect": effect, "parent_own_answers_selected_by_latest_bank_not_outcome": True,
            "fixed_tool_and_rank_interface_unchanged_across_paired_update": True})
        return stats, effect

    def fit_prefix(self, seen):
        import time

        gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        rows = [{**r, "annotation_sets": [{"annotations": gold[str(r["id"])]}]} for r in self.past+seen]
        started = time.monotonic()
        model = fit_program_model(rows, self.labels, [])
        path = self.out / f"ordinary_controls/after_b{self.current_batch}.pickle"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            pickle.dump(model, stream)
        manifest = {"at": now(), "path": str(path), "sha256": sha(path),
            "source_ids": [r["id"] for r in rows], "actual_CPU_fit_seconds": time.monotonic()-started,
            "same_original_labels_and_ordinary_parameters_no_future_sources": True,
            "not_a_skill_gain_or_main_tool_replacement": True}
        self.record(f"ordinary_controls/after_b{self.current_batch}.json", manifest)
        self.bindings[str(path)] = sha(path)
        self.fit_records.append(manifest)
        self.prefix_model, self.prefix_ids = model, manifest["source_ids"]

    def joint(self, row, arm, proposals):
        bank = self.bank if arm == "skills" else []
        self.logical(row, arm, self.generate(row, arm, *joint_payload(
            row, self.labels, proposals, self.cfg["bundled_solver_system"], bank,
            complete_order=self.cfg.get("show_complete_member_order", True))))

    def execute(self):
        self.check()
        start_batch = self.cfg.get("start_batch", 1)
        self.record("declaration.json", {"at": now(), "config": self.cfg,
            "exact_actual_terminal_parent": self.bank, "frozen_bindings": self.bindings.copy(),
            "no_best_bank_rollback_or_future_case_tuning": True,
            "start_batch": start_batch, "inherited_episode_labels": (start_batch-1)*8,
            "new_label_teaching": (4-start_batch)*8, "forward_readout_not_taught": 8})
        self.record("publications/initial.json", {"at": now(), "publication": self.bank,
            "actual_inherited_teacher_sources": self.prefix_ids, "not_empty_start_independent_repeat": True})
        if start_batch > 1:
            self.phase = "initial_parent_canonical_retention"
            first = len(self.answers)
            for row in self.documents[:(start_batch-1)*8]:
                self.joint(row, "skills", evidence_proposals(self.model, row, self.labels))
            initial = self.score(self.answers[first:])
            self.units.extend(initial)
            self.record("initial_retention.json", {"at": now(), "metrics": points(initial),
                "not_unseen_evaluation_or_teacher_update_gain": True,
                "refresh_all_inherited_episode_own_answers_in_actual_new_interface": True})
        for batch in range(start_batch, 5):
            self.current_batch = batch
            rows, seen = self.documents[(batch-1)*8:batch*8], self.documents[:batch*8]
            start = len(self.answers)
            main_phase = f"b{batch}_prequential"
            for index, row in enumerate(rows):
                self.phase = main_phase
                fixed = evidence_proposals(self.model, row, self.labels)
                prefix = fixed if batch == 1 else evidence_proposals(self.prefix_model, row, self.labels)
                self.record(f"common_candidates/b{batch}/{row['id']}.json", {"fixed42": fixed,
                    "ordinary_revealed_prefix": prefix, "ordinary_prefix_source_ids": self.prefix_ids})
                order = ("joint_empty", "skills")
                if index % 2:
                    order = tuple(reversed(order))
                for arm in order:
                    self.joint(row, arm, fixed if arm == "skills" else prefix)
                if batch == 1:
                    native = next(u for u in self.answers[start:] if u["stage"] == main_phase
                        and u["document_id"] == row["id"] and u["condition"] == "joint_empty")
                    self.phase = f"b{batch}_fixed_tool_control"
                    alias = self.logical(row, "joint_empty", native["response"])
                    assert self.prefix_model is self.model
                    self.record(f"exact_aliases/b{batch}/{row['id']}.json", {
                        "original": native, "alias": alias,
                        "same_model_proposals_full_input_and_decoding": True,
                        "no_new_native_calls_not_independent_duplicate": True})
                else:
                    self.phase = f"b{batch}_fixed_tool_control"
                    self.joint(row, "joint_empty", fixed)
            units = self.score(self.answers[start:])
            self.units.extend(units)
            groups = {a: [u for u in units if u["condition"] == a] for a in (
                "joint_empty", "fixed_tool_empty", "skills")}
            summary = {"at": now(), "batch": batch, "new_source_ids": [r["id"] for r in rows],
                "current_bank_sha256": csha(self.bank), "current_skill_count": len(self.bank),
                "ordinary_prefix_source_ids": self.prefix_ids,
                "prequential_metrics": {a: points(u) for a,u in groups.items()},
                "same_case_skill_effects": {a: paired_effect(groups[a], groups["skills"],
                    seed=2026101820+batch*4+i, replicates=5000) for i,a in enumerate(groups) if a != "skills"},
                "current_batch_fully_generated_before_any_current_Gold_grading_or_teacher": True,
                "forward_only_no_update" : batch == 4}
            self.batch_summaries.append(summary)
            self.record(f"batch_summaries/b{batch}_before.json", summary)
            print(json.dumps({"batch": batch, "metrics": summary["prequential_metrics"]}), flush=True)
            if batch <= 3:
                stats, effect = self.update_online(seen)
                self.record(f"batch_summaries/b{batch}_complete.json", {
                    **summary, "publication_statistics": stats, "paired_seen_update_effect": effect})
                self.fit_prefix(seen)
        assert len(self.native) == self.cfg.get("planned_new_native_calls", 136 if start_batch == 1 else 120)
        assert len(self.teachers) == len(self.fit_records) == 4-start_batch
        prequential = [u for u in self.units if u["stage"].endswith("_prequential") or u["stage"].endswith("_fixed_tool_control")]
        groups = {a: [u for u in prequential if u["condition"] == a] for a in (
            "joint_empty", "fixed_tool_empty", "skills")}
        assert all(len(v) == (5-start_batch)*8 for v in groups.values())
        result = {"at": now(), "run_id": self.run_id, "batch_summaries": self.batch_summaries,
            "aggregate_prequential_metrics": {a: points(u) for a,u in groups.items()},
            "actual_new_native_teacher_CPUfits": [len(self.native), len(self.teachers), len(self.fit_records)],
            "final_bank": self.bank, "units": self.units, "ordinary_prefix_fits": self.fit_records,
            "inherited_episode_labels": (start_batch-1)*8, "new_taught_labels": (4-start_batch)*8,
            "inherited42_plus_episode24_taught_forward8_not_taught": True,
            "all_adverse_results_and_original_denominators_retained": True,
            "not_independent_algorithmic_repeat_or_official_TEST": True}
        self.record("completion.json", result)
        RunStore.atomic_json(self.out / "progress.json", {"state": "completed", **result})
        print(json.dumps({"completed": self.run_id, "metrics": result["aggregate_prequential_metrics"]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    online = read(args.config)["method"] in ("ranked_joint_online24_forward8", "canonical_joint_online_continuation")
    if args.command == "prepare":
        (prepare_online if online else prepare)(args.config)
        return
    with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        study = (RankedOnline if online else DecisionEvidenceTransfer)(args.config)
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
