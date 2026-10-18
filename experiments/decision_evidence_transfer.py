"""Legal skill induction and online original-task evaluation.

The configured current modes use one frozen native joint lawyer with either
scoped prose criteria or actually executed source-member programs. Earlier
ranked/factored interfaces remain disclosed historical experiments, never
fallbacks. Physical and logical costs, adverse results and provenance remain
explicit. No efficacy admission, answer repair or current/future Gold at inference.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import json
import pickle
import signal
import tarfile
import traceback
import zipfile
from pathlib import Path

import numpy as np
from jsonschema import ValidationError, validate

from legal_skill_guard.data import source_components
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.inference.codex_cli_client import (
    CODEX_TURN_INPUT_CHARACTER_LIMIT, render_structured_codex_prompt,
)
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.catalog import encode_teacher_body
from legal_skill_guard.learning.decision_evidence import (
    DECISION_SYSTEM, EVIDENCE_SYSTEM, GUIDANCE_SCHEMA, assemble_native,
    channel_criteria, convert_parent, decision_payload, evidence_payload, joint_payload, member_program_payload,
    PROCEDURE_GUIDANCE_SCHEMA, procedure_payload, validate_procedures,
)
from legal_skill_guard.learning.evidence_programs import evidence_proposals, fit_program_model
from legal_skill_guard.learning.executable_features import (
    ATTRIBUTES, BUILTINS, MEMBER_PROGRAM_GUIDANCE_SCHEMA, LINKED_PROGRAM_GUIDANCE_SCHEMA,
    execute_member_programs, validate_member_programs,
)
from legal_skill_guard.learning.experiment import Comparison, ROOT, now, points, read, sha
from legal_skill_guard.learning.member_contract import (
    annotated_sources, draft_member_feedback, member_replay_cases,
    original_witness_replay, teacher_sources,
)
from legal_skill_guard.learning.member_learning import paired_effect
from legal_skill_guard.learning.packing import keyed, table
from legal_skill_guard.learning.publication import (
    apply_differential_publication, differential_schema, publication_statistics,
)
from legal_skill_guard.task import original_feedback
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

ARMS = ("joint_empty", "factored_empty", "relation_only", "dual_skills")
PROGRAM_METHOD = "direct_source_member_program_online"
DRAFT_METHOD = "source_member_draft_execution_online"
NATIVE_DRAFT_METHOD = "source_member_native_draft_feedback_online"
LINKED_METHOD = "linked_source_procedure_native_feedback_online"
PROCEDURE_METHOD = "source_grounded_direct_procedure_online"
EDIT_FEEDBACK_METHOD = "source_grounded_published_edit_feedback_online"
PROCEDURE_METHODS = (PROCEDURE_METHOD, EDIT_FEEDBACK_METHOD)
COMMON_TOOL_METHODS = (LINKED_METHOD, *PROCEDURE_METHODS)
NATIVE_FEEDBACK_METHODS = (NATIVE_DRAFT_METHOD, LINKED_METHOD)
DRAFT_METHODS = (DRAFT_METHOD, *NATIVE_FEEDBACK_METHODS)
PROGRAM_METHODS = (PROGRAM_METHOD, *DRAFT_METHODS)
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
        if self.cfg.get("method") in COMMON_TOOL_METHODS:
            source_ids = ([r["id"] for r in self.past] if arm == "fixed_tool_empty" else self.prefix_ids)
            item["ordinary_tool_source_ids"] = list(source_ids)
            item["ordinary_tool_source_ids_sha256"] = csha(source_ids)
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


PROGRAM_WRITER = (
    "Learn reusable executable source-inspection skills from ONLY the supplied "
    "already-seen original TRAIN sources, author annotations, actual historical "
    "public answers and current-parent feedback supplied here. This is label-"
    "assisted external program learning, not parameter training or canonical "
    "TF-GRPO. Do not add models, tools, outside law or invented rollouts. Each "
    "skill contains id, distinct public hypothesis_ids and guidance.python_source. "
    "Define propose_members(text, spans, public_hypothesis_key) returning a list "
    "of UNIQUE original integer indices. Helpers may use the documented pure "
    "text/container/regex API. Each function receives ONLY this original text, "
    "its original coordinates and one known public hypothesis key; never its ID, "
    "annotations, ordinary scores or a final answer. The function executes in a "
    "resource-limited CPU child. No imports, classes, decorators, globals, top-"
    "level assignments, I/O, files, network, models, reflection or dynamic eval. "
    "Empty matches are legitimate factual results; exceptions and invalid outputs "
    "STOP the experiment, with no fallback, retry, clipping or deduplication. "
    "The returned source locations are fallible READING PROPOSALS. The same "
    "frozen8B lawyer still generates every final original choice/spans/reason "
    "freely in one canonical call, alongside complete source and the common "
    "ordinary tool. No code, identity, past example, label or prose advice reaches "
    "the lawyer. Empty proposals are NOT NotMentioned. Do not return legal labels "
    "or probability arrays. Do not train another score head. Learn actual source-"
    "observable member boundaries: definitions and list structure, scoped actors "
    "and objects, operative conditions and exceptions, and independently "
    "responsive repeated provisions. A cross-span definition or scope dependency "
    "is not equivalent to a fixed neighbor window or synonym union. Distinguish "
    "annotated members from useful nonmember background, without treating "
    "benchmark nonmembership as universal legal falsity. Component hit/miss "
    "feedback is NOT an instruction to force all proposals into final answers. "
    "Inspect true current-parent native failures as well as proposal membership; "
    "do not mistake ordinary supervised-tool quality for your contribution. "
    "Previous prose-method history is explicitly labeled as such, not fabricated "
    "program executions. Previous prose is FALLIBLE: audit its exclusions against "
    "the original membership tags colocated with each literal span, not intuitive minimal-proof "
    "preferences. Do not mechanically translate an unsupported prose exclusion "
    "into code. Learn cross-source boundaries from ALL supplied members, without "
    "memorizing an exceptional source or pretending annotation variance is new "
    "law. Each teacher source gives every original segment, exact inter-span "
    "gaps and trailing text, with original_member_for tags and unchanged original "
    "annotations. Concatenate gaps/text/tail to recover the full source. Tags "
    "repeat existing Gold, not a new judge; NM has no evidence supervision. "
    "Initial induction receives all complete past sources. Subsequent updates "
    "receive the complete newly revealed8 contracts plus ALL earlier original "
    "labels and verbatim original member/proposed/cited witness excerpts. Those "
    "past excerpts are explicitly PARTIAL contexts, not full contracts or proofs "
    "of absence. All full past sources remain available to the actual source "
    "program execution and retention evaluation, NOT silently to this teacher. "
    "Preserve prior boundaries when partial past context cannot justify changing "
    "them. All past source cases and Gold members remain in replay, no selection. "
    "No case IDs, dates, parties, unique quotations, document "
    "fingerprints or hardcoded source-index/answer tables in runtime programs. "
    "Publish explicit CREATE/UPDATE/DELETE/MERGE or NOOP against the exact parent. "
    "Unmentioned records remain verbatim. UPDATE keeps its ID. Targets are "
    "distinct unconsumed original parent IDs, never forward references. CREATE "
    "has0, UPDATE/DELETE1 and MERGE>=2 targets; only DELETE has skill=null. Cite "
    "only supplied seen source_case_ids in audit rationales, not programs. All "
    "structurally valid edits publish, with no efficacy gate, forced count/topic/"
    "growth or best-bank rollback. Aim for the complete serialized library within "
    "3200 target8B tokens under4096 hard cap, without trimming or retry. Return "
    "exactly the requested differential JSON."
)


LINKED_WRITER = (
    "Learn reusable source-grounded legal skills for the actual frozen8B lawyer, "
    "using ONLY the supplied already-seen original TRAIN contracts/annotations, "
    "actual public answers, CPU execution and native training feedback. No tools, "
    "outside law, new models or invented executions. This is label-assisted "
    "external skill learning, not parameter training or canonical TF-GRPO. "
    "Each record has id, distinct public hypothesis_ids, and guidance containing "
    "required nullable python_source and procedure; at least ONE is meaningful. "
    "Code is a reusable source-inspection operation returning unique original "
    "integer reading locations. Define propose_members(text, spans, "
    "public_hypothesis_key); spans is a list of [start,end] character offsets. "
    "Use ONLY the documented pure API; no imports, classes, globals, I/O, "
    "models or reflection. Source code never returns labels or final answers. "
    "A procedure is concise fallible source-conditional legal interpretation "
    "or member-selection guidance, directly visible to the lawyer alongside "
    "executed read locations. It is NOT a current fact, supplied choice, "
    "mandatory citation or runtime-Gold test. The lawyer reads the COMPLETE "
    "original source and freely writes every original choice/spans/reason once. "
    "Programs, procedures or both may form a coherent skill; do not force "
    "a number, topic partition, one-per-hypothesis rule or library growth. "
    "Learn distinctions that the actual weak lawyer failed to apply: actor, "
    "action, object, quantifier, negation, permission versus obligation, "
    "condition and exception scope. Correct-source/wrong-relation errors need "
    "interpretation, not automatically more reading locations. Correct-label "
    "member omissions need complete responsive-member selection, not blind "
    "label reversal. Distinguish useful background from original annotated "
    "members; preserve independently responsive repetitions. Original labels "
    "and annotation conventions are benchmark supervision, not universal law. "
    "The source window contains ALL8 new contracts and, from B2, the immediately "
    "preceding8 episode contracts, selected by chronology, never by outcome. "
    "Earlier full sources remain archived and undergo actual CPU replay, but "
    "are NOT silently present in this teacher window. Their original member "
    "feedback remains supplied; do not infer missing old semantics from indices. "
    "Historical own answers retain their actual tool-source version metadata. "
    "Native parent/draft feedback on the new8 uses the SAME current common "
    "ordinary tool. Ordinary supervised improvement is shared with empty and "
    "is NOT your skill contribution. Prioritize original native classification, "
    "evidence and joint outcomes; CPU proposal counts are auxiliary, not native "
    "performance. Learn from successes AND harms without selecting cases. "
    "Preserve effective old source operations; do not rewrite a large program "
    "when the missing correction is a short conditional legal procedure. "
    "Do not merely repeat the generic solver prompt or replace a source "
    "condition by a memorized answer. Runtime records must contain no case "
    "IDs, parties, dates, original span numbers, answer tables, source hashes "
    "or memorized quotations. Audit source_case_ids/rationales are not served. "
    "Return differential CREATE/UPDATE/DELETE/MERGE or explicit NOOP against "
    "the exact supplied parent. Unmentioned records remain verbatim; UPDATE "
    "keeps its ID; targets are distinct unconsumed original IDs, not draft IDs. "
    "CREATE has0 targets, UPDATE/DELETE1, MERGE>=2; only DELETE has skill=null. "
    "Every structurally valid final edit publishes, even if worse: no score "
    "gate, selected older bank, retry, answer repair or extra solver. Aim for "
    "the entire serialized library<=3200 target8B tokens under4096 hard cap. "
    "Keep each coherent text procedure compact, roughly<=200 words, without "
    "clipping. Return exactly the requested delta JSON."
)

PROCEDURE_WRITER = (
    "Learn reusable source-grounded legal procedures from ONLY supplied complete "
    "already-seen original TRAIN contracts, original annotations and actual own "
    "frozen-lawyer public observations. No tools, new sources, outside law, "
    "private thinking or invented success. This is label-assisted external "
    "memory learning, not weight training or TF-GRPO. The source-reading program "
    "layer was removed after controlled adverse transfer; do not recreate "
    "retrieval code, keyword lists or mandatory citation sets. The actual latest "
    "text procedures, NOT a chosen older better bank, are inherited unchanged. "
    "The SAME frozen8B makes one original native answer per contract: for every "
    "exact hypothesis it FIRST writes a public source-grounded reason of at "
    "most15 words, THEN choice and spans. Both own and empty see the same full "
    "source and same growing ordinary membership tool. Tool improvement is not "
    "your gain. Every label/citation remains the lawyer's independent decision. "
    "This is ONE teacher invocation per learning batch. Your valid delta is "
    "published directly, then actually used for complete seen-source training "
    "reanswers; that exact published behavior feeds the NEXT batch. There is "
    "no unpublished draft, post-feedback speculative rewrite, gate or rollback. "
    "All new8 and immediately preceding8 episode contracts where available "
    "are supplied completely, selected by chronology not outcomes. Earlier "
    "full sources and observations are archived, not silently present here. "
    "Historical observations retain their actual common-tool source IDs. "
    "Inspect all supplied successes/failures and deterministic error profiles. "
    "Distinguish wrong relations from incomplete or excessive original members. "
    "Original Gold membership is benchmark supervision, not universal legal "
    "truth; a logical premise is not automatically a member, while an annotated "
    "governing introduction or repeated provision must not be dropped merely "
    "as background. Learn observable inclusion AND exclusion conditions. "
    "Do not infer opposition from absence or another topic, permission from a "
    "ban, or a trigger from mere survival. Ground actor, force, action, object, "
    "quantifier, trigger and exceptions in source conditions. Generic contrasts "
    "between supported, opposed and unresolved conditions are permitted; case "
    "answers, copied quotations, source IDs, parties, dates, span integers or "
    "document fingerprints in runtime guidance are not. Teach HOW to inspect "
    "and decide, not a current verdict or 'include if Gold'. A procedure record "
    "must express one coherent transferable distinction. Do not pack unrelated "
    "hypothesis-specific rules into one global checklist: use separate scoped "
    "records when their observable conditions differ. General checks may apply "
    "broadly. No fixed count/topics, one-per-hypothesis rule or forced growth. "
    "Preserve unchanged useful records verbatim. Revise/delete/merge obsolete "
    "rules rather than accumulate contradictory advice. Your only guidance "
    "field is procedure, a meaningful concise string; no unused code field. "
    "Return CREATE/UPDATE/DELETE/MERGE or explicit NOOP against the exact parent. "
    "Targets are distinct unconsumed parent IDs: CREATE0, UPDATE/DELETE1, "
    "MERGE>=2; UPDATE keeps ID; only DELETE skill=null. Audit rationales and "
    "supplied source_case_ids never reach the lawyer. Every valid edit publishes "
    "even if worse; no retry, selected bank, acceptance test or answer repair. "
    "Aim total serialized library<=3200 target8B tokens under4096 hard cap "
    "without truncation. Return exactly the required differential JSON."
)

PUBLISHED_EXPERIENCE_NOTICE = (
    "published directly, then actually used to reanswer ALL8 newly revealed "
    "contracts under the SAME ordinary tool. Those real published outcomes "
    "feed the NEXT batch. The previous batch's complete matched before/after "
    "transition, old bank and actual edit are supplied, including every gain "
    "and harm, not a success-filtered subset. Use them to identify which "
    "general instruction caused negative transfer. Older batches outside the "
    "chronological window are NOT reanswered or claimed as measured retention.")

EDIT_FEEDBACK_WRITER = PROCEDURE_WRITER.replace("most15 words", "most64 words").replace(
    "published directly, then actually used for complete seen-source training "
    "reanswers; that exact published behavior feeds the NEXT batch.",
    PUBLISHED_EXPERIENCE_NOTICE,
) + (
    " When correct prose was delivered but the actual lawyer still ignored "
    "the distinction, do not merely add another broad exhortation. Where "
    "the supplied complete sources warrant it, express a compact worked "
    "legal distinction: an anonymous generic clause pattern, what supported, "
    "opposed or unresolved consequence it has for the exact public hypothesis, "
    "and a nearby counterpattern explaining the observable boundary. These "
    "are reusable teaching examples inside ordinary procedure text, NOT "
    "current contract answers or copied source sentences. Do not invent "
    "outside-law rules or unsupported annotation conventions. Distinguish "
    "a complete responsive evidence member from nearby merely useful context. "
    "Use such an example only when it makes the failed behavior executable; "
    "no mandatory example count, separate layer or new schema. Inspect the "
    "actual before/after damage and remove or narrow contradictory rules "
    "instead of restating them at greater length. All unchanged skill words "
    "remain verbatim and all valid edits publish unconditionally. At the first "
    "step, initial_actual_parent_published_update_from_completed_run may give "
    "the actual latest prior episode's complete last8 edit transition and "
    "sources. Its original tool version and reason budget differ from the "
    "current interface and are disclosed; never invent new-interface outcomes "
    "for it. Use its real observed gains and damage, not an imagined failure.")


def program_api():
    return {"entrypoint": "propose_members(text, spans, public_hypothesis_key)",
        "allowed_builtins": list(BUILTINS), "allowed_attributes": sorted(ATTRIBUTES),
        "only_function_definitions_and_module_docstring_at_top_level": True,
        "CPU_seconds": 2, "memory_MiB": 192, "wall_seconds": 5,
        "return": "list of distinct original integer indices; [] is a legitimate match result"}


def sealed_interrupted_revision(cfg, bank, preserved_files):
    """Continue a sealed, unsent final revision in the fixed two-stage graph.

    Only a fresh episode stopped by the character guard is eligible. Nothing
    selects a better bank, replays a paid call, or resumes an arbitrary job.
    """
    source = ROOT / cfg["resume_failed_revision_run"]
    old_config = ROOT / cfg["resume_failed_revision_config"]
    old = read(old_config)
    assert old["method"] in (DRAFT_METHOD, NATIVE_DRAFT_METHOD) and cfg["method"] == old["method"]
    assert not old.get("resume_failed_revision_run"), "Nested recovery needs a separate provenance audit"
    native = old["method"] == NATIVE_DRAFT_METHOD
    for key in ("episode_ids", "source_only_seed", "generation", "ordinary_manifest", "teacher",
                "source_archive_sha256", "inference_environment"):
        assert old[key] == cfg[key], "Continuation cannot change the native task or shared tools"
    failure = read(source / "failure.json")
    assert "Complete teacher input exceeds character capacity" in failure["error"]
    assert read(source / "progress.json")["state"] == "failed"
    pending = [p for p in (source / "learning_inputs").glob("online_b*_revision.json")
               if not (source / "publications" / (p.stem.split("_")[1]+".json")).exists()
               and not (source / "teacher" / p.stem / "response.json").exists()]
    assert len(pending) == 1, "Exactly one unsent final revision, never a performance retry"
    pending = pending[0]
    batch = int(pending.stem.split("_")[1][1:])
    assert 1 <= batch <= 3
    expected_native = 16+24*(batch-1)+4*batch*(batch-1)+(8*batch if native else 0)
    inherited = [expected_native, 2*batch-1, batch-1]
    assert failure["actual_new_native_teacher_calls"] == inherited[:2]
    parent_path = source / "publications" / (f"b{batch-1}.json" if batch > 1 else "initial.json")
    assert read(parent_path)["publication"] == bank
    physical = sorted((source / "native").rglob("*.json"))
    answers = sorted((source / "logical_answers").rglob("*.json"))
    assert len(physical) == expected_native and len(answers) == expected_native+8
    responses = {read(p)["response"]["raw_id"]: read(p)["response"] for p in physical}
    assert len(responses) == expected_native
    assert all(read(p)["response"] == responses[read(p)["response"]["raw_id"]] for p in answers)
    teacher_responses = sorted((source / "teacher").glob("*/response.json"))
    fits = sorted((source / "ordinary_controls").glob("*.json"))
    assert len(teacher_responses) == inherited[1] and len(fits) == inherited[2]
    old_frozen = read(old_config.with_suffix(".frozen.json"))["files"]
    for name in ("learning/decision_evidence.py", "learning/executable_features.py",
                 "learning/evidence_programs.py", "learning/acquisition.py", "task.py",
                 "inference/native.py", "inference/openai_client.py", "inference/codex_cli_client.py"):
        p = ROOT / "legal_skill_guard" / name
        assert old_frozen[str(p)] == sha(p), "Never reuse answers after an inference change"
    refs = {"pending_final_revision_body": pending,
            "executed_draft": source / f"drafts/b{batch}.json",
            "executed_draft_replay": source / f"program_replays/b{batch}_draft.json",
            "pending_final_schema_reference": source / f"teacher/online_b{batch}_draft/wire_request.json"}
    writer = source / "teacher/online_b1_revision/wire_request.json"
    if native:
        import ast
        terminal = read(ROOT / cfg["parent_terminal_preservation"])
        module = Path(__file__).resolve()
        with tarfile.open(terminal["archive"], "r:gz") as archive:
            original_source = archive.extractfile("project/"+str(module.relative_to(ROOT))).read().decode()
        methods = {"generate", "logical", "score", "joint", "native_draft_feedback",
                   "final_program_revision", "program_mode", "native_draft_mode"}
        def native_contract(text):
            return {(c.name,n.name):ast.dump(n,include_attributes=False)
                    for c in ast.parse(text).body if isinstance(c,ast.ClassDef)
                    for n in c.body if isinstance(n,ast.FunctionDef) and n.name in methods}
        assert native_contract(original_source) == native_contract(module.read_text())
        writer = ROOT / cfg["resume_failed_final_request_intent"]
        intent = read(writer)
        assert intent["actually_sent_or_reserved"] is False
        assert intent["original_failed_module_sha256"] == old_frozen[str(module)]
        assert intent["original_pending_semantic_body_sha256"] == sha(pending)
        assert intent["output_schema"] == read(refs["pending_final_schema_reference"])["output_schema"]
        refs["executed_native_draft_training"] = source / f"draft_native_training/b{batch}.json"
        assert read(pending)["actual_unpublished_draft_native_training_feedback"] == read(
            refs["executed_native_draft_training"])["teacher_feedback"]
    body, system = read(pending), read(writer)["system_prompt"]
    assert body["current_parent_library"] == bank
    encoded = encode_teacher_body(body)
    chars = len(render_structured_codex_prompt(system,
        json.dumps(encoded, ensure_ascii=False, separators=(",", ":"))))
    assert chars <= CODEX_TURN_INPUT_CHARACTER_LIMIT, "Complete pending revision, never clip"
    summaries = [source / f"batch_summaries/b{b}_before.json" for b in range(1,batch+1)]
    required = [old_config,old_config.with_suffix(".frozen.json"),source/"failure.json",
                source/"progress.json",parent_path,*refs.values(),*summaries,*answers,
                *physical,*teacher_responses,*fits]
    required += [Path(read(p)["input_payload"]) for p in physical]
    for p in required:
        assert preserved_files[str(p.relative_to(ROOT))] == sha(p), "Only sealed original artifacts"
    if not native:
        assert preserved_files[str(writer.relative_to(ROOT))] == sha(writer)
    refs["pending_final_system_request"] = writer
    result = {"source_run_directory": str(source.relative_to(ROOT)),
        "resume_batch": batch, "inherited_actual_native_teacher_CPUfits": inherited,
        "logical_answer_paths": [str(p.relative_to(ROOT)) for p in answers],
        "batch_summary_paths": [str(p.relative_to(ROOT)) for p in summaries],
        **{k:str(p.relative_to(ROOT)) for k,p in refs.items()},
        "complete_pending_revision_rendered_characters": chars,
        "original_episode_label_exposures_already_seen":batch*8,
        "pending_unpublished_label_batch_finalization":8,
        "first_new_original_label_exposures_after_resume":(3-batch)*8,
        "no_repeated_native_teacher_or_draft_execution":True}
    return result, required+[writer]


def prepare_online(config):
    config = Path(config).resolve()
    cfg = read(config)
    assert cfg["method"] in ("ranked_joint_online24_forward8", "canonical_joint_online_continuation", *PROCEDURE_METHODS, *PROGRAM_METHODS)
    program, draft = cfg["method"] in PROGRAM_METHODS, cfg["method"] in DRAFT_METHODS
    native_draft = cfg["method"] in NATIVE_FEEDBACK_METHODS
    linked = cfg["method"] == LINKED_METHOD
    procedure = cfg["method"] in PROCEDURE_METHODS
    edit_feedback = cfg["method"] == EDIT_FEEDBACK_METHOD
    if edit_feedback:
        assert cfg["public_reason_words"] == 64 and cfg["generation"]["max_tokens"] == 8192
    resume = bool(cfg.get("resume_failed_revision_run"))
    assert not resume or (draft and cfg.get("start_batch",1) == 1)
    start = cfg.get("start_batch", 1)
    assert start in (1, 2)
    if start == 2:
        assert cfg["method"] == "canonical_joint_online_continuation" and not cfg["show_complete_member_order"]
    if program or procedure:
        assert start == 1 and not cfg["show_complete_member_order"]
    assert not config.with_suffix(".frozen.json").exists() and not (ROOT / "runs" / cfg["run_id"]).exists()
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    original = {r["id"]: r for r in author["documents"]}
    manifest = read(ROOT / cfg["ordinary_manifest"])
    past = manifest["seen_original_source_ids"]
    assert len(past) == len(set(past)) == cfg.get("past_source_count", 42)
    assert sha(manifest["path"]) == manifest["pickle_sha256"]
    reference = read(ROOT / cfg["development_reference_config"])
    exclude = set(past + reference["development_ids"] + read(ROOT / cfg["excluded_parent_config"])["training_ids"])
    if program:
        exclude.update(read(ROOT / cfg["additional_excluded_episode_config"])["episode_ids"])
    if draft or procedure:
        exclude.update(read(ROOT / cfg["inherited_program_config"])["episode_ids"])
    if native_draft or procedure:
        ancestor = read(ROOT / cfg["inherited_program_config"])
        ancestor_packet = read(ROOT / ancestor["input_packet"])
        exclude.update(ancestor_packet["source_only_selection"]["excluded_original_and_source_component_ids"])
    components = source_components(author["documents"])
    excluded = set().union(*(set(g) for g in components if set(g) & exclude))
    eligible = sorted(d for d in original if d not in excluded)
    ids = np.random.default_rng(cfg["source_only_seed"]).choice(eligible, size=32, replace=False).tolist()
    assert ids == cfg["episode_ids"] and not any(len(set(g) & set(ids)) > 1 for g in components)
    if draft or procedure:
        selection = read(ROOT / cfg["source_only_preselection"])
        assert sha(ROOT / cfg["source_only_preselection"]) == cfg["source_only_preselection_sha256"]
        assert selection["episode_ids"] == ids and selection["eligible_ids"] == eligible
        assert selection["excluded_original_and_source_component_ids"] == sorted(excluded)
    terminal = read(ROOT / cfg["parent_terminal_preservation"])
    assert terminal["state"] == "terminal_results_preserved" and terminal["all_members_verified"]
    assert sha(terminal["archive"]) == sha(terminal["rootdisk_copy"]) == terminal["archive_sha256"]
    with tarfile.open(terminal["archive"], "r:gz") as preserved:
        preserved_files = json.load(preserved.extractfile("terminal_recovery_manifest.json"))["files"]
    assert preserved_files[str(Path(cfg["parent_publication"]))] == sha(ROOT / cfg["parent_publication"])
    bank = read(ROOT / cfg["parent_publication"])["publication"]
    inherited_bank_sha256 = csha(bank)
    if procedure:
        if edit_feedback:
            assert cfg["initial_guidance_migration"] == "inherit_actual_procedures_exactly"
            assert inherited_bank_sha256 == csha(bank)
        else:
            assert cfg["initial_guidance_migration"] == "procedures_only_remove_source_read_layer"
            validate_member_programs(bank, author["labels"], allow_procedures=True)
            bank = [{**copy.deepcopy(s), "guidance": {"procedure": s["guidance"]["procedure"]}}
                    for s in bank if s["guidance"]["procedure"] is not None]
        validate_procedures(bank, author["labels"])
        assert read(ROOT / cfg["parent_publication"])["original_seen_source_ids"] == past
    elif draft:
        if linked and cfg.get("initial_guidance_migration") == "add_null_procedure":
            validate_member_programs(bank, author["labels"])
            bank = [{**copy.deepcopy(s), "guidance": {
                "python_source": s["guidance"]["python_source"], "procedure": None}} for s in bank]
        validate_member_programs(bank, author["labels"], allow_procedures=linked)
        if not resume:
            assert read(ROOT / cfg["parent_publication"])["original_seen_source_ids"] == past
    else:
        for channel in ("relation_criterion", "evidence_criterion"):
            channel_criteria(bank, author["labels"], channel)
    public = lambda d: {k: original[d][k] for k in ("id", "text", "spans")}
    resumed, resume_files = sealed_interrupted_revision(cfg,bank,preserved_files) if resume else (None,[])
    if resumed:
        assert read(ROOT / cfg["parent_publication"])["original_seen_source_ids"] == past+ids[:(resumed["resume_batch"]-1)*8]
    RunStore.immutable_json(ROOT / cfg["input_packet"], {
        "public_hypotheses": author["labels"], "documents": [public(d) for d in ids],
        "past_documents": [public(d) for d in past], "past_seen_ids": past,
        "converted_actual_parent": bank if draft or procedure or not program else [],
        "previous_text_method_library_for_initial_induction_only": bank if program and not draft else None,
        "parent_already_two_channel_no_conversion_or_selection": not program and not procedure,
        "new_source_program_representation_not_selected_old_bank": program and not draft,
        "inherits_actual_latest_program_without_score_selection": draft or procedure,
        "explicit_guidance_migration": cfg.get("initial_guidance_migration"),
        "initial_guidance_migration_receipt": {
            "original_actual_parent_sha256": inherited_bank_sha256,
            "initial_runtime_parent_sha256": csha(bank),
            "mechanical_null_field_only_not_new_learning": linked,
            "removes_source_read_layer_by_method_not_case_or_skill_score": cfg.get("initial_guidance_migration") == "procedures_only_remove_source_read_layer",
            "inherits_actual_procedures_byte_semantics_without_selection": edit_feedback,
            "retained_procedure_text_scope_identity_unchanged": procedure,
            "no_score_selection": True,
            "no_score_selection_or_code_change": linked} if linked or procedure else None,
        "source_only_selection": {"seed": cfg["source_only_seed"], "eligible_ids": eligible,
            "excluded_original_and_source_component_ids": sorted(excluded),
            "no_selection_using_labels_or_outcomes": True},
        "episode_has_three_learning_batches_then_forward8": True,
        "this_run_inherits_first_episode_batch": start == 2 or resume,
        "sealed_interrupted_final_revision":resumed})
    RunStore.immutable_json(ROOT / cfg["grading_only"], {
        "original_TRAIN_annotations": {str(d): original[d]["annotation_sets"][0]["annotations"] for d in past+ids},
        "teacher_gets_only_revealed_past_and_episode_prefix": True,
        "all_current_batch_answers_precede_current_batch_grading": True})
    ledger = read(ROOT / cfg["teacher"]["ledger"])
    inherited = resumed["inherited_actual_native_teacher_CPUfits"] if resumed else [0,0,0]
    teachers = (4-start)*(2 if draft else 1)+int(program and not draft)-inherited[1]
    expected_calls = (88 if edit_feedback else (160 if native_draft else 136) if start == 1 else 120)-inherited[0]
    expected_fits = 4-start-inherited[2]
    assert max(r["sequence"] for r in ledger["reservations"]) + teachers <= ledger["max_invocations"]
    assert cfg["planned_new_native_calls"] == expected_calls and cfg["planned_new_teacher_calls"] == teachers
    files = list((ROOT / "legal_skill_guard").rglob("*.py"))
    files += resume_files
    files += [Path(__file__).resolve(), config, ROOT / "tests/test_learning_contract.py", Path(manifest["path"])]
    files += [ROOT / cfg[k] for k in ("source_archive", "input_packet", "grading_only", "ordinary_manifest",
        "parent_publication", "parent_terminal_preservation", "development_reference_config",
        "excluded_parent_config", "inference_environment", "method_protocol")]
    if start == 2 or (resumed and resumed["resume_batch"] > 1):
        prefix_path = ROOT / cfg["initial_ordinary_prefix_manifest"]
        prefix = read(prefix_path)
        prior = (resumed["resume_batch"]-1)*8 if resumed else 8
        assert prefix["source_ids"] == past+ids[:prior] and sha(prefix["path"]) == prefix["sha256"]
        publication = read(ROOT / cfg["parent_publication"])
        assert publication["original_seen_source_ids"] == prefix["source_ids"]
        files += [prefix_path, Path(prefix["path"])]
    if draft or procedure:
        files += [ROOT / cfg["inherited_program_config"], ROOT / cfg["source_only_preselection"]]
    elif program:
        source_gold = {str(d): original[d]["annotation_sets"][0]["annotations"] for d in past}
        paths = sorted((ROOT / cfg["initial_teacher_own_reference_run"] /
                        f"logical_answers/{cfg['initial_teacher_own_reference_stage']}").glob("*/skills.json"))
        own = [read(p) for p in paths]
        assert own and len({u["document_id"] for u in own}) == len(own)
        assert all(u["document_id"] in past and u["bank_sha256"] == csha(bank) for u in own)
        assert all(preserved_files[str(p.relative_to(ROOT))] == sha(p) for p in paths)
        initial_teacher = {
            "public_hypotheses": author["labels"], "current_parent_library": [],
            "complete_original_past_sources_and_Gold": annotated_sources([public(d) for d in past],
                author["labels"], source_gold),
            "actual_previous_text_method_public_answers_not_program_rollouts": table(own),
            "previous_text_method_library_for_reference_not_runtime": bank,
            "same_data_ordinary_model": manifest, "pure_program_API": program_api(),
            "no_new_episode_source_or_Gold_or_official_DEV_TEST": True}
        chars = len(render_structured_codex_prompt(PROGRAM_WRITER,
            json.dumps(initial_teacher, ensure_ascii=False, separators=(",", ":"))))
        assert chars <= CODEX_TURN_INPUT_CHARACTER_LIMIT, "Complete teacher transport capacity; never truncate"
        RunStore.immutable_json(ROOT / cfg["initial_teacher_body"], initial_teacher)
        files += paths + [ROOT / cfg["initial_teacher_body"], ROOT / cfg["additional_excluded_episode_config"]]
    if edit_feedback and cfg.get("initial_parent_update_history"):
        history_path = ROOT / cfg["initial_parent_update_history"]
        history = read(history_path)
        assert history["published_bank_sha256"] == csha(bank)
        assert history["all8_source_ids"] == past[-8:]
        for name, digest in history["original_logical_artifact_sha256"].items():
            assert preserved_files[name] == sha(ROOT / name) == digest
            files.append(ROOT / name)
        files.append(history_path)
    RunStore.immutable_json(config.with_suffix(".frozen.json"), {
        "config_sha256": sha(config), "files": {str(p.resolve()): sha(p) for p in files}})
    print(json.dumps({"prepared": cfg["run_id"], "new_episode_ids": ids,
        "inherited_published_episode_labels":(resumed["resume_batch"]-1)*8 if resumed else (start-1)*8,
        "first_new_original_label_exposures":(3-resumed["resume_batch"])*8 if resumed else (4-start)*8,
        "pending_unpublished_label_finalization":8 if resume else 0,
        "forward_readout": 8, "planned_native_teacher_CPUfits": [expected_calls, teachers, expected_fits]}), flush=True)


class RankedOnline(DecisionEvidenceTransfer):
    def __init__(self, config):
        super().__init__(config)
        self.bank = copy.deepcopy(self.parent)
        packet = read(ROOT / self.cfg["input_packet"])
        self.past, self.prefix_model = packet["past_documents"], self.model
        self.own_current, self.batch_summaries, self.fit_records = {}, [], []
        self.program_cost = {}
        self.resumed = packet.get("sealed_interrupted_final_revision")
        self.prefix_ids = list(packet["past_seen_ids"])
        if self.cfg.get("start_batch", 1) == 2 or (self.resumed and self.resumed["resume_batch"] > 1):
            prefix = read(ROOT / self.cfg["initial_ordinary_prefix_manifest"])
            assert sha(prefix["path"]) == prefix["sha256"]
            with Path(prefix["path"]).open("rb") as stream:
                self.prefix_model = pickle.load(stream)
            self.prefix_ids = prefix["source_ids"]
            assert not self.prefix_model.programs
            prior = (self.resumed["resume_batch"]-1)*8 if self.resumed else 8
            assert self.prefix_ids == [r["id"] for r in self.past+self.documents[:prior]]

    def program_mode(self):
        return self.cfg.get("method") in PROGRAM_METHODS

    def draft_mode(self):
        return self.cfg.get("method") in DRAFT_METHODS

    def native_draft_mode(self):
        return self.cfg.get("method") in NATIVE_FEEDBACK_METHODS

    def linked_mode(self):
        return self.cfg.get("method") == LINKED_METHOD

    def procedure_mode(self):
        return self.cfg.get("method") in PROCEDURE_METHODS

    def publication_feedback_mode(self):
        return self.cfg.get("method") == EDIT_FEEDBACK_METHOD

    def common_tool_mode(self):
        return self.cfg.get("method") in COMMON_TOOL_METHODS

    def active_model(self):
        return self.prefix_model if self.common_tool_mode() else self.model

    def program_writer(self):
        return LINKED_WRITER if self.linked_mode() else PROGRAM_WRITER

    def runtime_guidance_schema(self):
        if self.procedure_mode():
            return PROCEDURE_GUIDANCE_SCHEMA
        if self.linked_mode():
            return LINKED_PROGRAM_GUIDANCE_SCHEMA
        return MEMBER_PROGRAM_GUIDANCE_SCHEMA if self.program_mode() else GUIDANCE_SCHEMA

    def validate_runtime_bank(self):
        if self.procedure_mode():
            validate_procedures(self.bank, self.labels)
        elif self.program_mode():
            validate_member_programs(self.bank, self.labels, allow_procedures=self.linked_mode())
        else:
            for channel in ("relation_criterion", "evidence_criterion"):
                channel_criteria(self.bank, self.labels, channel)

    def draft_execution_update(self, name, body, schema, parent, rows, gold, parent_replays):
        """One unpublished draft, one real seen-source replay, one final revision.

        No candidate ranking, performance threshold, extra attempts or publication
        of a draft. The original parent stays published until the final delta is
        returned and structurally applied, regardless of its measured utility.
        """
        draft_stage = (
            " The host will also run this candidate with the ACTUAL frozen lawyer "
            "once on ALL8 newly revealed training contracts, with unchanged ordinary "
            "tool, complete source, native schema and generation settings. The final "
            "teacher receives every actual answer and original classification/member "
            "feedback, including failures. This is a fixed training rollout, not "
            "validation, success selection, a publication gate or a second solver."
            if self.native_draft_mode() else
            " No native lawyer answer for this draft exists. Do not invent one.")
        draft = self.teacher_call(name+"_draft", self.program_writer() + (
            " This is the FIRST, UNPUBLISHED DRAFT stage of a fixed two-invocation "
            "training step. Return a delta against current_parent_library. The "
            "host will execute this draft once on ALL already-seen sources and "
            "give the actual CPU member feedback to the same teacher for ONE "
            "final revision." + draft_stage +
            " Do not self-report execution or use tools."), encode_teacher_body(body), schema)
        seen_ids = [r["id"] for r in rows]
        candidate = apply_differential_publication(parent, draft, self.labels, seen_ids,
            guidance_schema=self.runtime_guidance_schema())
        validate_member_programs(candidate, self.labels, allow_procedures=self.linked_mode())
        tokens = self.meter.token_count(text=json.dumps(candidate, ensure_ascii=False, separators=(",", ":")))
        assert tokens <= self.cfg["library_token_hard_cap"], "Invalid draft stops; no repair or substitute"
        self.record(f"drafts/b{self.current_batch}.json", {"at": now(), "parent": parent,
            "draft_delta": draft, "unpublished_draft": candidate, "serialized_tokens": tokens,
            "all_actual_seen_source_ids": seen_ids, "not_published_or_score_selected": True})
        self.progress("fixed_draft_CPU_training_replay", current_batch=self.current_batch)
        replay = []
        for row in rows:
            self.check()
            proposed, receipts = execute_member_programs(candidate, row, self.labels,
                allow_procedures=self.linked_mode())
            self.record_program_cost(receipts, "one_unpublished_draft_training_replay_not_native")
            replay.append({"document_id": row["id"],
                "by_hypothesis": member_replay_cases(proposed, gold[str(row["id"])], self.labels),
                "actual_CPU_execution_receipts": receipts,
                "unpublished_draft_CPU_training_not_native_answers": True})
        self.record(f"program_replays/b{self.current_batch}_draft.json", {
            "at": now(), "draft_library_sha256": csha(candidate),
            "complete_actual_CPU_replays": replay, "one_fixed_training_probe_no_efficacy_admission": True})
        revision = copy.deepcopy(body)
        revision["actual_unpublished_draft_delta_against_original_parent"] = draft
        revision["actual_unpublished_draft_library_sha256"] = csha(candidate)
        revision["actual_unpublished_draft_CPU_feedback"] = draft_member_feedback(parent_replays, replay, self.labels)
        if self.native_draft_mode():
            revision["actual_unpublished_draft_native_training_feedback"] = self.native_draft_feedback(candidate)
        revision["fixed_final_stage_not_an_admission_test"] = (
            "Exactly one final revision follows this actual draft feedback. " +
            ("All8 actual draft-native training outcomes are supplied without selection. "
             if self.native_draft_mode() else "No native answer for the draft was generated. ") +
            "Return a final delta against the "
            "ORIGINAL current_parent_library, not the unpublished draft. All valid "
            "final edits publish even if worse; no retry, score gate or bank selection.")
        self.record(f"learning_inputs/{name}_revision.json", revision)
        final = self.final_program_revision(name, revision, schema)
        assert self.bank == parent, "No intermediate draft publication"
        return final

    def native_draft_feedback(self, candidate):
        """One real native training pass on every newly revealed source.

        This neither publishes the candidate nor overwrites current-parent own
        observations. All successes, wrong answers and invalid outputs survive.
        Gold is used only after the entire native training batch completes.
        """
        rows = self.documents[(self.current_batch-1)*8:self.current_batch*8]
        assert len(rows) == 8
        parent = copy.deepcopy(self.bank)
        own_before = copy.deepcopy(self.own_current)
        phase = self.phase
        draft_units = []
        self.phase = f"b{self.current_batch}_unpublished_draft_training"
        for row in rows:
            messages, schema, trace = member_program_payload(row, self.labels,
                evidence_proposals(self.active_model(), row, self.labels),
                self.cfg["bundled_solver_system"], candidate, allow_procedures=self.linked_mode())
            self.record(f"source_executions/{self.phase}/{row['id']}/draft_skills.json", trace)
            self.record_program_cost(trace["actual_member_program_executions"],
                                     "unpublished_native_training_source_execution")
            response = self.generate(row, "draft_skills", messages, schema)
            unit = {"document_id": row["id"], "condition": "unpublished_draft",
                "response": response, "stage": self.phase, "bank_sha256": csha(candidate),
                "unpublished_training_not_current_parent_or_forward_inference": True}
            if self.linked_mode():
                unit["ordinary_tool_source_ids"] = list(self.prefix_ids)
                unit["ordinary_tool_source_ids_sha256"] = csha(self.prefix_ids)
            self.record(f"logical_answers/{self.phase}/{row['id']}/draft_skills.json", unit)
            self.answers.append(unit)
            draft_units.append(unit)
        self.phase = phase
        assert self.bank == parent and self.own_current == own_before
        parent_units = self.score([self.own_current[r["id"]] for r in rows])
        scored = self.score(draft_units)
        self.units.extend(scored)
        observations = []
        for unit in scored:
            observations.append({"document_id": unit["document_id"],
                "raw_id": unit["response"]["raw_id"],
                "finish_reason": unit["response"]["finish_reason"],
                "actual_original_public_answer": keyed(unit["parsed"]) if unit["public_valid"] else None,
                "actual_invalid_raw_content_not_repaired": None if unit["public_valid"] else unit["response"]["content"],
                "public_valid": unit["public_valid"],
                "original_feedback_by_hypothesis": keyed({
                    q["hypothesis_id"]: {k:q[k] for k in
                        ("label_correct","evidence_tp","evidence_fp","evidence_fn","joint_exact")}
                    for q in unit["queries"]})})
        feedback = {"all8_actual_native_draft_observations": table(observations),
            "same8_original_metric_counts": {"current_parent": points(parent_units), "unpublished_draft": points(scored)},
            "parent_public_answers_are_already_in_same_teacher_input": True,
            "fixed_training_pass_no_source_or_outcome_filter_or_efficacy_admission": True,
            "valid_public_answer_fields_preserved_semantically_not_raw_JSON_whitespace": True}
        self.record(f"draft_native_training/b{self.current_batch}.json",
            {"at":now(), "parent_library_sha256":csha(parent), "draft_library_sha256":csha(candidate),
             "all_actual_unpublished_training_units":scored, "teacher_feedback":feedback,
             "same_generation_full_sources_ordinary_model_and_native_task":True})
        return feedback

    def final_program_revision(self, name, revision, schema):
        return self.teacher_call(name+"_revision", self.program_writer() + (
            " This is the SECOND and FINAL invocation of the fixed training step. "
            "Inspect the actual unpublished draft CPU feedback and original Gold, "
            "together with actual CURRENT-PARENT native errors. Revise once, retain "
            "or explicitly NOOP as warranted. Output the final delta against the "
            "ORIGINAL current_parent_library: draft-created IDs are not parent "
            "targets. Never claim draft proposal counts are native legal accuracy. "
            "Every valid final edit publishes without a performance threshold; "
            "no additional candidate, rerun, best-bank rollback or tools." + (
            " Also inspect every supplied actual unpublished-draft native training "
            "answer and the exact paired original label/member feedback. Candidate "
            "hit counts can improve while final citations or relations worsen. "
            "Learn from successes AND harms without selecting cases, rewriting "
            "answers or claiming a successful repair that did not occur."
            if self.native_draft_mode() else "")), encode_teacher_body(revision), schema)

    def record_program_cost(self, receipts, role):
        cost = self.program_cost.setdefault(role, {"CPU_subprocesses": 0, "CPU_wall_seconds": 0.0})
        cost["CPU_subprocesses"] += len(receipts)
        cost["CPU_wall_seconds"] += sum(r["actual_CPU_wall_seconds"] for r in receipts)

    def induct_initial_programs(self):
        assert not self.bank
        body = read(ROOT / self.cfg["initial_teacher_body"])
        seen = [r["id"] for r in self.past]
        schema = differential_schema(self.labels, [], seen, guidance_schema=self.runtime_guidance_schema())
        value = self.teacher_call("initial_source_program_induction", PROGRAM_WRITER, body, schema)
        self.bank = apply_differential_publication([], value, self.labels, seen,
                                                  guidance_schema=self.runtime_guidance_schema())
        self.validate_runtime_bank()
        tokens = self.meter.token_count(text=json.dumps(self.bank, ensure_ascii=False, separators=(",", ":")))
        assert tokens <= self.cfg["library_token_hard_cap"], "No trimming, efficacy admission or selected bank"
        self.record("publications/induction.json", {"at": now(), "parent": [], "delta": value,
            "publication": self.bank, "statistics": publication_statistics([], value, self.bank, tokens),
            "original_seen_source_ids": seen, "new_episode_labels_taught": 0,
            "new_representation_learning_not_best_bank_rollback": True,
            "all_valid_edits_publish_without_efficacy_admission": True})

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

    def update_linked_online(self, seen):
        """Chronological literal replay plus complete compact executed feedback.

        The bounded window is fixed by batch order, not correctness. All seen
        programs still run, and no actual native observation is fabricated for
        older contracts under the current ordinary tool.
        """
        parent = copy.deepcopy(self.bank)
        assert all(self.own_current[r["id"]]["bank_sha256"] == csha(parent) for r in seen)
        gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        before = self.score([self.own_current[r["id"]] for r in seen])
        window = seen[-16:]
        window_ids = {r["id"] for r in window}
        raw_replays, compact_replays = [], []
        for row in self.past+seen:
            proposed, receipts = execute_member_programs(parent, row, self.labels, allow_procedures=True)
            self.record_program_cost(receipts, "teaching_component_replay_not_native")
            cases = member_replay_cases(proposed, gold[str(row["id"])], self.labels)
            raw_replays.append({"document_id": row["id"], "by_hypothesis": cases,
                "actual_CPU_execution_receipts": receipts,
                "factual_current_parent_replay_not_new_native_answers": True})
            compact_replays.append({"document_id": row["id"], "by_hypothesis": keyed(cases)})
        self.record(f"program_replays/b{self.current_batch}.json", {
            "at": now(), "complete_actual_CPU_replays": raw_replays,
            "all_original_member_feedback_is_in_teacher_readable_view": True,
            "CPU_times_code_source_hashes_audit_metadata_not_repeated_in_teacher_input": True})
        body = {
            "public_hypotheses": self.labels, "current_parent_library": parent,
            "complete_new_and_previous_batch_original_sources_and_Gold": annotated_sources(window, self.labels, gold),
            "literal_replay_window": {
                "all_new_source_ids": [r["id"] for r in seen[-8:]],
                "all_immediately_previous_episode_batch_ids": [r["id"] for r in window[:-8]],
                "selected_only_by_chronology_not_outcomes": True,
                "older_complete_sources_archived_but_NOT_present_as_literal_teacher_text": True},
            "actual_current_parent_episode_public_answers": table([
                self.own_current[r["id"]] for r in window]),
            "actual_original_component_feedback": [{"document_id": u["document_id"],
                "by_hypothesis": {q["hypothesis_id"]: {k: q[k] for k in (
                    "label_correct", "evidence_tp", "evidence_fp", "evidence_fn", "joint_exact")}
                    for q in u["queries"]}, "public_valid": u["public_valid"]}
                for u in before if u["document_id"] in window_ids],
            "actual_current_parent_source_program_component_replays": table(compact_replays),
            "actual_common_tool_current_window_candidates": table([
                {"document_id": r["id"], "by_hypothesis": {
                    h: {"candidate_original_span_indices": [v["original_span_index"] for v in p["candidates"]]}
                    for h,p in evidence_proposals(self.active_model(), r, self.labels)["by_hypothesis"].items()}}
                for r in window]),
            "current_common_ordinary_tool_source_ids": list(self.prefix_ids),
            "initial_ordinary_tool_manifest": self.manifest,
            "historical_own_observations_keep_actual_ordinary_tool_source_ids": True,
            "ordinary_tool_grows_identically_for_skills_and_strong_empty_not_a_skill_gain": True,
            "pure_program_API": program_api(),
            "future_joint_system": member_program_payload(window[0], self.labels,
                evidence_proposals(self.active_model(), window[0], self.labels),
                self.cfg["bundled_solver_system"], [], allow_procedures=True)[0][0]["content"],
            "complete_membership_rank_order_visible_in_single_joint_action": False,
            "procedure_semantics_are_tested_only_by_actual_native_feedback_NOT_CPU_member_counts": True,
            "no_future_episode_sources_answers_annotations_or_official_DEV_TEST": True}
        name = f"online_b{self.current_batch}"
        self.record(f"learning_inputs/{name}.json", body)
        schema = differential_schema(self.labels, parent, [r["id"] for r in self.past+seen],
                                     guidance_schema=self.runtime_guidance_schema())
        value = self.draft_execution_update(name, body, schema, parent, self.past+seen, gold, raw_replays)
        return self.publish_and_reanswer(parent, value, seen, before)

    def update_online(self, seen):
        if self.procedure_mode():
            return self.update_procedure_online(seen)
        if self.linked_mode():
            return self.update_linked_online(seen)
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
            "complete_original_past_and_revealed_episode_sources_and_Gold": (
                annotated_sources(seen[-8:], self.labels, gold) if self.program_mode()
                else teacher_sources(self.past+seen, gold)),
            "actual_current_parent_episode_public_answers": table(own),
            "actual_original_component_feedback": [{"document_id": u["document_id"],
                "by_hypothesis": {q["hypothesis_id"]: {k: q[k] for k in (
                    "label_correct", "evidence_tp", "evidence_fp", "evidence_fn", "joint_exact")}
                    for q in u["queries"]}, "public_valid": u["public_valid"]} for u in before],
            "actual_fixed_tool_visible_candidate_information": table(ranked_observations),
            "numeric_candidate_scores_archived_in_actual_inputs_not_resupplied_as_threshold_targets": True,
            "main_fixed_ordinary_tool_manifest": self.manifest,
            "future_joint_system": joint_payload(seen[0], self.labels,
                evidence_proposals(self.model, seen[0], self.labels),
                self.cfg["bundled_solver_system"], [] if self.program_mode() else parent,
                complete_order=complete_order)[0][0]["content"],
            "complete_membership_rank_order_visible_in_single_joint_action": complete_order,
            "no_future_episode_sources_answers_annotations_or_official_DEV_TEST": True}
        if self.program_mode():
            body["complete_newly_revealed_original_sources_and_Gold"] = body.pop(
                "complete_original_past_and_revealed_episode_sources_and_Gold")
            body["pure_program_API"] = program_api()
            body["future_joint_system"] = member_program_payload(seen[0], self.labels,
                evidence_proposals(self.model, seen[0], self.labels),
                self.cfg["bundled_solver_system"], [])[0][0]["content"]
            replays, raw_replays, witnesses = [], [], []
            before_by_id = {u["document_id"]:u for u in before}
            new_ids = {r["id"] for r in seen[-8:]}
            for row in self.past+seen:
                proposed, receipts = execute_member_programs(parent, row, self.labels)
                self.record_program_cost(receipts, "teaching_component_replay_not_native")
                cases = member_replay_cases(proposed, gold[str(row["id"])], self.labels)
                raw_replays.append({"document_id": row["id"], "by_hypothesis": cases,
                    "actual_CPU_execution_receipts": receipts,
                    "factual_current_parent_replay_not_new_native_answers": True})
                replays.append({"document_id":row["id"],"by_hypothesis":keyed(cases)})
                if row["id"] not in new_ids:
                    observed = before_by_id.get(row["id"])
                    cited = []
                    if observed is not None and observed["public_valid"]:
                        cited = [i for a in observed["parsed"].values() for i in a["spans"]]
                    witnesses.append(original_witness_replay(row,self.labels,gold[str(row["id"])],
                        [i for values in proposed.values() for i in values],cited))
            self.record(f"program_replays/b{self.current_batch}.json", {
                "at":now(),"complete_actual_CPU_replays":raw_replays,
                "all_original_member_feedback_is_in_teacher_readable_view":True,
                "CPU_times_code_source_hashes_audit_metadata_not_repeated_in_teacher_input":True})
            body["actual_current_parent_source_program_component_replays"] = table(replays)
            body["all_earlier_original_source_witness_replay_NOT_full_contracts"] = table(witnesses)
        name = f"online_b{self.current_batch}"
        self.record(f"learning_inputs/{name}.json", body)
        seen_ids = [r["id"] for r in self.past+seen]
        schema = differential_schema(self.labels, parent, seen_ids, guidance_schema=self.runtime_guidance_schema())
        writer = PROGRAM_WRITER if self.program_mode() else online_writer(complete_order).replace("42", str(len(self.past)))
        value = (self.draft_execution_update(name, body, schema, parent, self.past+seen, gold, raw_replays)
                 if self.draft_mode() else self.teacher_call(name, writer, body, schema))
        return self.publish_and_reanswer(parent, value, seen, before)

    def update_procedure_online(self, seen):
        """One direct edit, followed by execution of THAT published bank.

        Its real native outcomes, not another unexecuted final rewrite, become
        the next teacher's current-parent experience. No efficacy acceptance.
        """
        parent = copy.deepcopy(self.bank)
        window = seen[-16:]
        checked_rows = window if self.publication_feedback_mode() else seen
        assert all(self.own_current[r["id"]]["bank_sha256"] == csha(parent) for r in checked_rows)
        gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        before = self.score([self.own_current[r["id"]] for r in checked_rows])
        window_ids = {r["id"] for r in window}
        units = [u for u in before if u["document_id"] in window_ids]
        profiles = {}
        for h in self.labels:
            queries = [q for u in units for q in u["queries"] if q["hypothesis_id"] == h]
            nn = [q for q in queries if q["gold_non_neutral"] and q["label_correct"]]
            profiles[h] = {"questions": len(queries), "wrong_relation": sum(not q["label_correct"] for q in queries),
                "correct_relation_member_misses": sum(q["evidence_fn"] for q in nn),
                "correct_relation_extra_members": sum(q["evidence_fp"] for q in nn),
                "joint_exact": sum(q["joint_exact"] for q in queries)}
        body = {"public_hypotheses": self.labels, "current_parent_library": parent,
            "hypothesis_error_profiles_same_original_feedback_not_a_judge": profiles,
            "complete_new_and_previous_batch_original_sources_and_Gold": annotated_sources(window, self.labels, gold),
            "actual_current_parent_episode_public_answers": table([self.own_current[r["id"]] for r in window]),
            "actual_original_component_feedback": [{"document_id": u["document_id"],
                "by_hypothesis": {q["hypothesis_id"]: {k: q[k] for k in (
                    "label_correct", "evidence_tp", "evidence_fp", "evidence_fn", "joint_exact")}
                    for q in u["queries"]}, "public_valid": u["public_valid"]} for u in units],
            "literal_replay_window": {"all_new_source_ids": [r["id"] for r in seen[-8:]],
                "all_immediately_previous_episode_batch_ids": [r["id"] for r in window[:-8]],
                "selected_only_by_chronology_not_outcomes": True,
                "older_full_sources_and_observations_archived_not_in_current_teacher_prompt": True},
            "current_common_ordinary_tool_source_ids": list(self.prefix_ids),
            "initial_ordinary_tool_manifest": self.manifest,
            "historical_observations_preserve_actual_ordinary_tool_source_ids": True,
            "ordinary_tool_grows_identically_for_skills_and_strong_empty_not_a_skill_gain": True,
            "future_joint_system": procedure_payload(window[0], self.labels,
                evidence_proposals(self.active_model(), window[0], self.labels),
                self.cfg["bundled_solver_system"], [],
                **({"public_reason_words": self.cfg["public_reason_words"]}
                   if self.cfg.get("method") == EDIT_FEEDBACK_METHOD else {}))[0][0]["content"],
            "complete_membership_rank_order_visible_in_single_joint_action": False,
            "one_direct_publication_then_actual_native_training_not_an_unexecuted_final_rewrite": True,
            "no_future_episode_sources_answers_annotations_or_official_DEV_TEST": True}
        if self.publication_feedback_mode():
            transition = getattr(self, "last_published_update", None)
            assert (transition is None) == (self.current_batch == 1)
            if transition:
                assert transition["published_bank_sha256"] == csha(parent)
                assert transition["all8_source_ids"] == [r["id"] for r in window[:-8]]
            body.update(
                previous_actual_matched_published_update_all_gains_and_harms=transition,
                original_native_joint_answer_and_sparse_original_SPAN_lists=True,
                native_action_output_tokens={"joint":8192},
                no_reanswers_or_retention_claim_for_sources_outside_current_window=True)
            if self.current_batch == 1 and self.cfg.get("initial_parent_update_history"):
                history = read(ROOT / self.cfg["initial_parent_update_history"])
                assert history["published_bank_sha256"] == csha(parent)
                assert history["all8_source_ids"] == [r["id"] for r in self.past[-8:]]
                body["initial_actual_parent_published_update_from_completed_run"] = history
                body["literal_replay_window"]["initial_parent_previous_episode_full_source_ids"] = history["all8_source_ids"]
                body["literal_replay_window"]["older_full_sources_and_observations_archived_not_in_current_teacher_prompt"] = False
                body["literal_replay_window"]["only_explicit_parent_last8_history_not_all_past_sources_is_added"] = True
        name = f"online_b{self.current_batch}"
        self.record(f"learning_inputs/{name}.json", body)
        schema = differential_schema(self.labels, parent, [r["id"] for r in self.past+seen],
                                     guidance_schema=PROCEDURE_GUIDANCE_SCHEMA)
        writer = EDIT_FEEDBACK_WRITER if self.publication_feedback_mode() else PROCEDURE_WRITER
        value = self.teacher_call(name, writer,
                                  encode_teacher_body(body), schema)
        return self.publish_and_reanswer(parent, value, seen, before)

    def publish_and_reanswer(self, parent, value, seen, before):
        """The same unconditional publication/real-retention step for continuation."""
        seen_ids = [r["id"] for r in self.past+seen]
        self.bank = apply_differential_publication(parent, value, self.labels, seen_ids,
                                                  guidance_schema=self.runtime_guidance_schema())
        self.validate_runtime_bank()
        tokens = self.meter.token_count(text=json.dumps(self.bank, ensure_ascii=False, separators=(",", ":")))
        assert tokens <= self.cfg["library_token_hard_cap"], "No repair, trimming, selected bank or retry"
        stats = publication_statistics(parent, value, self.bank, tokens)
        self.record(f"publications/b{self.current_batch}.json", {"at": now(), "parent": parent,
            "delta": value, "publication": self.bank, "statistics": stats,
            "original_seen_source_ids": seen_ids,
            "actual_current_parent_own_episode_answers": len(before),
            "fixed_unpublished_draft_execution_then_one_revision": self.draft_mode(),
            "all_valid_edits_publish_without_efficacy_admission": True})
        self.phase = f"b{self.current_batch}_after_seen"
        start = len(self.answers)
        reanswer_rows = seen[-8:] if self.publication_feedback_mode() else seen
        for row in reanswer_rows:
            self.joint(row, "skills", evidence_proposals(self.active_model(), row, self.labels))
        after = self.score(self.answers[start:])
        self.units.extend(after)
        paired_before, paired_after = before, after
        if self.common_tool_mode():
            current_ids = {r["id"] for r in seen[-8:]}
            paired_before = [u for u in before if u["document_id"] in current_ids]
            paired_after = [u for u in after if u["document_id"] in current_ids]
            assert all(u["ordinary_tool_source_ids"] == self.prefix_ids for u in paired_before+paired_after)
        effect = paired_effect(paired_before, paired_after, seed=2026101810+self.current_batch, replicates=5000)
        self.record(f"update_effects/b{self.current_batch}.json", {"at": now(), "statistics": stats,
            "effect": effect, "parent_own_answers_selected_by_latest_bank_not_outcome": True,
            "fixed_tool_and_rank_interface_unchanged_across_paired_update": True,
            "paired_source_ids": [u["document_id"] for u in paired_before],
            "paired_scope": "current8_same_common_tool_training_only" if self.common_tool_mode() else "all_seen_fixed_tool",
            "reanswered_source_ids": [r["id"] for r in reanswer_rows],
            "all_seen_system_retention_not_pure_skill_effect": {
                "before": points(before), "after": points(after)} if self.common_tool_mode() and not self.publication_feedback_mode() else None})
        if self.publication_feedback_mode():
            self.last_published_update = {"learning_batch": self.current_batch,
                "parent_library": parent, "actual_published_delta": value,
                "published_bank_sha256": csha(self.bank),
                "all8_source_ids": [u["document_id"] for u in paired_before],
                "actual_common_ordinary_tool_source_ids_before_and_after": list(self.prefix_ids),
                "before_all8_actual_native_answers_and_original_feedback": table(paired_before),
                "after_all8_actual_native_answers_and_original_feedback": table(paired_after),
                "paired_original_effect": effect,
                "no_outcome_selection_no_extra_rollout_no_publication_gate": True}
            self.record(f"published_update_experience/b{self.current_batch}.json", self.last_published_update)
        return stats, effect

    def resume_interrupted_final_revision(self, resume):
        """Finish the sealed unsent final request, preserving all actual work."""
        parent = copy.deepcopy(self.bank)
        imported = [read(ROOT / path) for path in resume["logical_answer_paths"]]
        order = {d["id"]: i for i,d in enumerate(self.documents)}

        def chronology(item):
            stage, index = item["stage"], order[item["document_id"]]
            batch = int(stage.split("_")[0][1:])
            if stage.endswith("_unpublished_draft_training"):
                return batch*3+1, index, 0
            if stage.endswith("_after_seen"):
                return batch*3+2, index, 0
            assert stage.endswith("_prequential") or stage.endswith("_fixed_tool_control")
            arms = ("joint_empty", "skills") if index % 2 == 0 else ("skills", "joint_empty")
            rank = 2 if item["condition"] == "fixed_tool_empty" else arms.index(item["condition"])
            return batch*3, index, rank

        imported.sort(key=chronology)
        expected = resume["inherited_actual_native_teacher_CPUfits"][0]+8
        assert len(imported) == expected and not self.answers and not self.native and not self.teachers
        for item in imported:
            self.answers.append(item)
            if item["condition"] == "skills" and item["bank_sha256"] == csha(parent):
                self.own_current[item["document_id"]] = item
        self.current_batch = resume["resume_batch"]
        seen = self.documents[:self.current_batch*8]
        assert set(self.own_current) == {r["id"] for r in seen}
        self.units.extend(self.score(imported))
        self.batch_summaries = [read(ROOT / p) for p in resume["batch_summary_paths"]]
        for summary in self.batch_summaries:
            self.record(f"batch_summaries/b{summary['batch']}_before.json", summary)
        self.record("inherited_episode_artifacts.json", {"at": now(), **resume,
            "imported_logical_answer_uses": len(imported), "not_new_native_teacher_calls": True})
        body = read(ROOT / resume["pending_final_revision_body"])
        assert body["current_parent_library"] == parent
        draft = read(ROOT / resume["executed_draft"])
        assert body["actual_unpublished_draft_library_sha256"] == csha(draft["unpublished_draft"])
        before = self.score([self.own_current[r["id"]] for r in seen])
        name = f"online_b{self.current_batch}_revision"
        self.record(f"learning_inputs/{name}.json", body)
        schema = differential_schema(self.labels, parent, [r["id"] for r in self.past+seen],
                                     guidance_schema=self.runtime_guidance_schema())
        request = read(ROOT / resume["pending_final_system_request"])
        assert schema == read(ROOT / resume["pending_final_schema_reference"])["output_schema"]
        value = self.teacher_call(name, request["system_prompt"], encode_teacher_body(body), schema)
        stats, effect = self.publish_and_reanswer(parent, value, seen, before)
        self.record(f"batch_summaries/b{self.current_batch}_complete.json", {**self.batch_summaries[-1],
            "publication_statistics": stats, "paired_seen_update_effect": effect,
            "prequential_answers_and_draft_are_inherited_real_artifacts_not_new_calls": True})
        self.fit_prefix(seen)

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
            "not_a_skill_gain_or_main_tool_replacement": not self.common_tool_mode(),
            "replaces_common_tool_identically_for_skills_and_strong_empty": self.common_tool_mode()}
        self.record(f"ordinary_controls/after_b{self.current_batch}.json", manifest)
        self.bindings[str(path)] = sha(path)
        self.fit_records.append(manifest)
        self.prefix_model, self.prefix_ids = model, manifest["source_ids"]

    def joint(self, row, arm, proposals):
        bank = self.bank if arm == "skills" else []
        if self.procedure_mode():
            messages, schema = procedure_payload(row, self.labels, proposals, self.cfg["bundled_solver_system"], bank,
                public_reason_words=self.cfg.get("public_reason_words", 15))
            self.record(f"guidance_delivery/{self.phase}/{row['id']}/{arm}.json", {
                "visible_procedures": [{"hypothesis_ids": s["hypothesis_ids"],
                    "procedure": s["guidance"]["procedure"]} for s in bank],
                "visibility_not_internal_use_or_causal_proof": True, "no_source_program_layer": True})
        elif self.program_mode():
            messages, schema, trace = member_program_payload(row, self.labels, proposals,
                self.cfg["bundled_solver_system"], bank, allow_procedures=self.linked_mode())
            self.record(f"source_executions/{self.phase}/{row['id']}/{arm}.json", trace)
            self.record_program_cost(trace["actual_member_program_executions"], "native_input_source_execution")
        else:
            messages, schema = joint_payload(row, self.labels, proposals, self.cfg["bundled_solver_system"], bank,
                complete_order=self.cfg.get("show_complete_member_order", True))
        self.logical(row, arm, self.generate(row, arm, messages, schema))

    def execute(self):
        self.check()
        start_batch = self.cfg.get("start_batch", 1)
        resumed = getattr(self, "resumed", None)
        resumed_batch = resumed["resume_batch"] if resumed else None
        inherited_labels = (resumed_batch-1)*8 if resumed else (start_batch-1)*8
        new_labels = (3-resumed_batch)*8 if resumed else (4-start_batch)*8
        self.record("declaration.json", {"at": now(), "config": self.cfg,
            "exact_actual_terminal_parent": self.bank if not self.common_tool_mode() else None,
            "mechanically_migrated_actual_latest_parent": self.bank if self.common_tool_mode() else None,
            "frozen_bindings": self.bindings.copy(),
            "explicit_guidance_migration": self.cfg.get("initial_guidance_migration"),
            "ordinary_tool_shared_and_growing_for_main_comparison": self.common_tool_mode(),
            "no_best_bank_rollback_or_future_case_tuning": True,
            "start_batch": start_batch, "inherited_published_episode_labels": inherited_labels,
            "new_original_label_exposures": new_labels,
            "pending_unpublished_label_batch_finalization":8 if resumed else 0,
            "inherited_actual_native_teacher_CPUfits":resumed["inherited_actual_native_teacher_CPUfits"] if resumed else [0,0,0],
            "native_actions_per_logical_answer": 1,
            "post_publication_reanswers_current8_only_no_all_seen_retention_claim": self.publication_feedback_mode(),
            "forward_readout_not_taught": 8})
        self.record("publications/initial.json", {"at": now(), "publication": self.bank,
            "actual_inherited_teacher_sources": self.prefix_ids, "not_independent_learning_repeat": True,
            "explicit_guidance_migration": self.cfg.get("initial_guidance_migration"),
            "starts_with_empty_new_program_representation": self.program_mode() and not self.draft_mode(),
            "inherits_actual_latest_program_without_score_selection": self.draft_mode() or self.procedure_mode()})
        if self.program_mode() and not self.draft_mode():
            self.induct_initial_programs()
        if resumed:
            self.resume_interrupted_final_revision(resumed)
        elif start_batch > 1:
            self.phase = "initial_parent_canonical_retention"
            first = len(self.answers)
            for row in self.documents[:(start_batch-1)*8]:
                self.joint(row, "skills", evidence_proposals(self.model, row, self.labels))
            initial = self.score(self.answers[first:])
            self.units.extend(initial)
            self.record("initial_retention.json", {"at": now(), "metrics": points(initial),
                "not_unseen_evaluation_or_teacher_update_gain": True,
                "refresh_all_inherited_episode_own_answers_in_actual_new_interface": True})
        for batch in range(resumed_batch+1 if resumed else start_batch, 5):
            self.current_batch = batch
            rows, seen = self.documents[(batch-1)*8:batch*8], self.documents[:batch*8]
            start = len(self.answers)
            main_phase = f"b{batch}_prequential"
            for index, row in enumerate(rows):
                self.phase = main_phase
                fixed = None if self.publication_feedback_mode() else evidence_proposals(self.model, row, self.labels)
                prefix = (evidence_proposals(self.prefix_model, row, self.labels) if self.publication_feedback_mode()
                          else fixed if batch == 1 else evidence_proposals(self.prefix_model, row, self.labels))
                self.record(f"common_candidates/b{batch}/{row['id']}.json", {"fixed42": fixed,
                    "ordinary_revealed_prefix": prefix, "ordinary_prefix_source_ids": self.prefix_ids})
                order = ("joint_empty", "skills")
                if index % 2:
                    order = tuple(reversed(order))
                for arm in order:
                    self.joint(row, arm, fixed if arm == "skills" and not self.common_tool_mode() else prefix)
                if self.publication_feedback_mode():
                    continue
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
            conditions = ("joint_empty", "skills") if self.publication_feedback_mode() else (
                "joint_empty", "fixed_tool_empty", "skills")
            groups = {a: [u for u in units if u["condition"] == a] for a in conditions}
            summary = {"at": now(), "batch": batch, "new_source_ids": [r["id"] for r in rows],
                "current_bank_sha256": csha(self.bank), "current_skill_count": len(self.bank),
                "ordinary_prefix_source_ids": self.prefix_ids,
                "skills_and_strong_empty_share_current_ordinary_tool": self.common_tool_mode(),
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
        default_calls = (88 if self.publication_feedback_mode()
                         else (160 if self.native_draft_mode() else 136) if start_batch == 1 else 120)
        assert len(self.native) == self.cfg.get("planned_new_native_calls", default_calls)
        assert len(self.fit_records) == self.cfg.get("planned_new_CPU_fits",4-start_batch)
        assert len(self.teachers) == self.cfg.get("planned_new_teacher_calls",
            (4-start_batch)*(2 if self.draft_mode() else 1)+int(self.program_mode() and not self.draft_mode()))
        prequential = [u for u in self.units if u["stage"].endswith("_prequential") or u["stage"].endswith("_fixed_tool_control")]
        conditions = ("joint_empty", "skills") if self.publication_feedback_mode() else (
            "joint_empty", "fixed_tool_empty", "skills")
        groups = {a: [u for u in prequential if u["condition"] == a] for a in conditions}
        assert all(len(v) == (5-start_batch)*8 for v in groups.values())
        result = {"at": now(), "run_id": self.run_id, "batch_summaries": self.batch_summaries,
            "aggregate_prequential_metrics": {a: points(u) for a,u in groups.items()},
            "actual_new_native_teacher_CPUfits": [len(self.native), len(self.teachers), len(self.fit_records)],
            "inherited_actual_native_teacher_CPUfits":resumed["inherited_actual_native_teacher_CPUfits"] if resumed else [0,0,0],
            "total_same_episode_actual_native_teacher_CPUfits":[
                n+old for n,old in zip([len(self.native),len(self.teachers),len(self.fit_records)],
                    resumed["inherited_actual_native_teacher_CPUfits"] if resumed else [0,0,0],strict=True)],
            "final_bank": self.bank, "units": self.units, "ordinary_prefix_fits": self.fit_records,
            "actual_source_program_CPU_costs": self.program_cost if self.program_mode() else None,
            "native_actions_per_logical_answer": 1,
            "post_publication_reanswers_current8_only_no_all_seen_retention_claim": self.publication_feedback_mode(),
            "fixed_unpublished_draft_probe_then_one_revision_each_teaching_batch": self.draft_mode(),
            "fixed_all8_native_draft_training_feedback_each_teaching_batch": self.native_draft_mode(),
            "inherited_published_episode_labels": inherited_labels,
            "inherited_episode_labels":inherited_labels,
            "new_taught_labels":new_labels,
            "inherited_original_episode_label_exposures":resumed_batch*8 if resumed else (start_batch-1)*8,
            "new_original_episode_label_exposures":new_labels,
            "pending_unpublished_label_batch_finalization":8 if resumed else 0,
            "original_past_source_count": len(self.past),
            "total_original_sources_taught_at_terminal": len(self.past)+24,
            "episode24_taught_forward8_not_taught": True,
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
    online = read(args.config)["method"] in ("ranked_joint_online24_forward8", "canonical_joint_online_continuation", *PROCEDURE_METHODS, *PROGRAM_METHODS)
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
