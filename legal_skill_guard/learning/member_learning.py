"""Fresh, four-batch online source-only criterion skill learning.

Reuses the audited native client, acquisition executor and atomic editor. The
complete original source is shared with its empty-memory control. Every answer is
a new native call. No retrieval model, inherited bank, retries or answer repair.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import json
import shutil
import signal
import traceback
import zipfile
from pathlib import Path

import numpy as np
from jsonschema import ValidationError, validate

from legal_skill_guard.experiment.storage import RunStore, safe_component
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

from .acquisition import (
    AcquisitionStudy,
    compact,
    source_messages,
)
from .audit import original_score
from .experiment import ROOT, now, points, read, sha
from .member_contract import (
    EDIT_GUIDANCE,
    MEMBER_NOTICE,
    STORED_GUIDANCE,
    WRITER,
    actor_messages,
    expand_member_contrasts,
    hypothesis_error_profiles,
    member_contrasts,
    one_copy_criteria,
    project_criteria,
    teacher_sources,
)
from .packing import keyed, table
from .publication import (
    apply_differential_publication,
    differential_schema,
    paired,
    publication_statistics,
    skill_record_schema,
)

ARMS = ["strong_empty", "skills"]
ENDPOINTS = ["label_accuracy", "evidence_micro_f1_gold_non_neutral", "joint_exact_accuracy"]


def paired_effect(before, after, *, seed, replicates):
    """Descriptive paired-source uncertainty, not independent learning repeats."""
    a, b = ({u["document_id"]: u for u in units} for units in (before, after))
    assert len(a) == len(before) and len(b) == len(after) and a.keys() == b.keys() and a
    ids = sorted(a)

    def matrix(units):
        rows = []
        for d in ids:
            q = units[d]["queries"]
            nn = [v for v in q if v["gold_non_neutral"]]
            rows.append([len(q), sum(v["label_correct"] for v in q),
                sum(v["evidence_tp"] for v in nn), sum(v["evidence_fp"] for v in nn),
                sum(v["evidence_fn"] for v in nn), sum(v["joint_exact"] for v in q)])
        return np.asarray(rows, dtype=float)

    def metrics(m):
        n, correct, tp, fp, fn, joint = np.moveaxis(m, -1, 0)
        denominator = 2 * tp + fp + fn
        f1 = np.divide(2 * tp, denominator, out=np.zeros_like(tp), where=denominator != 0)
        return np.stack((correct / n, f1, joint / n), axis=-1)

    ma, mb = matrix(a), matrix(b)
    actual = metrics(mb.sum(axis=0)) - metrics(ma.sum(axis=0))
    pa, pb = points(before), points(after)
    assert np.allclose(actual, [pb[k] - pa[k] for k in ENDPOINTS], rtol=0, atol=1e-12)
    indices = np.random.default_rng(seed).integers(0, len(ids), size=(replicates, len(ids)))
    draws = metrics(mb[indices].sum(axis=1)) - metrics(ma[indices].sum(axis=1))
    bounds = np.percentile(draws, [2.5, 97.5], axis=0)
    per_source = metrics(mb) - metrics(ma)
    return {"before": pa, "after": pb, "paired_questions": paired(before, after),
        "source_contracts": len(ids), "difference_after_minus_before": dict(zip(ENDPOINTS, actual.tolist(), strict=True)),
        "source_win_tie_loss": {k: {"win": int((per_source[:, i] > 0).sum()),
            "tie": int((per_source[:, i] == 0).sum()), "loss": int((per_source[:, i] < 0).sum())}
            for i, k in enumerate(ENDPOINTS)},
        "descriptive_source_percentile_95_intervals": {k: bounds[:, i].tolist() for i, k in enumerate(ENDPOINTS)},
        "bootstrap_replicates": replicates, "bootstrap_seed": seed,
        "conditional_on_one_adaptive_episode_not_algorithmic_stability_or_confirmatory_significance": True}


def prepare(config):
    """Bind original TRAIN, current code and the live model without generation."""
    path = Path(config).resolve()
    cfg = read(path)
    assert cfg["method"] == "online_source_criterion_learning"
    assert cfg["generation"]["disable_thinking"] is True
    assert cfg["criterion_delivery"] == "one_copy_public_hypothesis_records"
    assert cfg["planned_new_native_calls"] == 144
    assert cfg["planned_new_teacher_calls"] == 4
    assert not path.with_suffix(".frozen.json").exists() and not (ROOT / "runs" / cfg["run_id"]).exists()
    packet, selection = read(ROOT / cfg["input_packet"]), read(ROOT / cfg["source_selection_record"])
    rows, ids = packet["documents"], cfg["training_ids"]
    assert ids == selection["selected_source_ids_in_fixed_order"] == [r["id"] for r in rows]
    assert len(ids) == len(set(ids)) == 32 and not set(ids) & set(selection["excluded_ids"])
    assert sha(ROOT / cfg["source_archive"]) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(ROOT / cfg["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    originals = {r["id"]: r for r in author["documents"]}
    assert len(originals) == 423 and packet["public_hypotheses"] == author["labels"]
    for row in rows:
        assert set(row) == {"id", "text", "spans"} and row == {k: originals[row["id"]][k] for k in row}
    gold = {str(d): originals[d]["annotation_sets"][0]["annotations"] for d in ids}
    # This is a TRAIN-only scoring/teacher store, not a lawyer input. Selection
    # was already source-only; preparing it parses annotations, not TEST content.
    gold_path = ROOT / cfg["grading_only"]
    RunStore.immutable_json(gold_path, {"original_TRAIN_annotations": gold,
        "lawyer_payloads_never_read_this_store": True, "teacher_only_supplied_seen_prefix": True})
    teacher_sources(rows, gold)  # Exact inverse text/offset checks; no LLM call.
    assert not any(k in cfg for k in ("ordinary_manifest", "own_ordinary_retrieval", "solver_system_reference"))
    assert isinstance(cfg["bundled_solver_system"], str) and cfg["bundled_solver_system"].strip()
    environment = read(ROOT / cfg["inference_environment"])
    proc = Path("/proc") / str(environment["pid"])
    assert [s.decode() for s in (proc / "cmdline").read_bytes().split(b"\0") if s] == environment["actual_argv"]
    assert (proc / "stat").read_text().rsplit(")", 1)[1].split()[19] == environment["process_start_ticks"]
    ledger = read(ROOT / cfg["teacher"]["ledger"])
    reserved = max(r["sequence"] for r in ledger["reservations"])
    assert reserved + cfg["planned_new_teacher_calls"] <= cfg["teacher"]["total_invocation_budget"] == ledger["max_invocations"]
    receipt = ROOT / cfg["preparation_receipt"]
    RunStore.immutable_json(receipt, {"at": now(), "original32_source_text_offsets_and_labels_equal": True,
        "official_DEV_TEST_unopened": True, "source_only_selection_precedes_annotation_preparation": True,
        "current_lawyer_pid_identity_unchanged": True, "actual_new_native_teacher_calls": [0, 0],
        "current_teacher_reserved_sequence": reserved, "planned_teacher_calls": 4,
        "not_an_effect_result_or_full_model_qualification": True})
    files = [p for p in (ROOT / "legal_skill_guard").rglob("*.py") if p.is_file()]
    files += [path, gold_path, receipt, ROOT / "pyproject.toml"]
    files += [ROOT / cfg[k] for k in ("input_packet", "source_selection_record", "source_archive",
        "inference_environment", "method_protocol")]
    files += [ROOT / p for p in cfg["completed_supporting_evidence"]]
    RunStore.immutable_json(path.with_suffix(".frozen.json"), {
        "config_sha256": sha(path), "files": {str(p.resolve()): sha(p) for p in files}})
    print(compact({"prepared": str(path), "source_contracts": 32,
        "planned_new_native_teacher_calls": [cfg["planned_new_native_calls"], 4],
        "planned_inherited_native_answers": 0,
        "frozen_files": len(set(files)), "actual_new_native_teacher_calls": [0, 0]}))


class MemberLearning(AcquisitionStudy):
    def __init__(self, config):
        # Reuse native/phase-preservation primitives, not the legacy constructor
        # which loads an ordinary evidence classifier and its proposal cache.
        self.cfg, self.config_path = read(config), Path(config).resolve()
        frozen = read(self.config_path.with_suffix(".frozen.json"))
        assert frozen["config_sha256"] == sha(self.config_path)
        self.bindings = frozen["files"].copy()
        self.run_id = safe_component(self.cfg["run_id"])
        self.out = ROOT / "runs" / self.run_id
        assert not self.out.exists(), "Never restart or overwrite a Run ID"
        packet = read(ROOT / self.cfg["input_packet"])
        self.labels, self.training = packet["public_hypotheses"], packet["documents"]
        assert [r["id"] for r in self.training] == self.cfg["training_ids"]
        assert all(set(r) == {"id", "text", "spans"} for r in self.training)
        self.system = self.cfg["bundled_solver_system"]
        self.native, self.teachers, self.own, self.first, self.units = [], [], [], [], []
        self.teacher_attempts, self.current_batch, self.stop = 0, 0, False
        self.inherited_count = 0
        self.bank, self.banks = [], {csha([]): []}
        self.meter, self.summaries = WireClient(self.cfg["generation"]), []
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))
        assert self.cfg["method"] == "online_source_criterion_learning"
        assert self.cfg["criterion_delivery"] == "one_copy_public_hypothesis_records"
        assert self.cfg["generation"]["disable_thinking"] is True
        assert self.cfg["teacher_evidence_view"] == "source_only_original_member_tables"
        assert self.cfg["historical_publications"] == []
        assert self.cfg["planned_new_native_calls"] == 144
        assert self.cfg["planned_new_teacher_calls"] == 4
        assert len(self.training) == len(set(self.cfg["training_ids"])) == 32
        assert not self.bank and self.inherited_count == 0
        self.own_history = []

    def record(self, name, value):
        path = self.out / name
        RunStore.immutable_json(path, value)
        self.bindings[str(path)] = sha(path)
        return path

    def progress(self, stage, **extra):
        super().progress(stage, inherited_cold_native_answers=self.inherited_count,
            completed_logical_native_answers=len(self.native) + self.inherited_count, **extra)

    def capacity(self, bank):
        assert len({s["id"] for s in bank}) == len(bank)
        for s in bank:
            validate(s, skill_record_schema(self.labels, guidance_schema=STORED_GUIDANCE))
            assert len(s["hypothesis_ids"]) == len(set(s["hypothesis_ids"]))
        capacity = {"master": self.meter.token_count(text=compact(bank)),
            "with_public_scope_map": self.meter.token_count(text=compact({"library": bank, "scope": {
                h: [s["id"] for s in bank if h in s["hypothesis_ids"]] for h in self.labels}})),
            "actual_one_copy_criteria": self.meter.token_count(text=compact(one_copy_criteria(bank)))}
        assert max(capacity.values()) <= self.cfg["library_token_hard_cap"], "No pruning, truncation or retry"
        return capacity

    def payload(self, row, arm, bank, *, hypothesis_ids=None):
        assert arm in ARMS
        labels = self.labels
        if hypothesis_ids is not None:
            if (not hypothesis_ids or len(set(hypothesis_ids)) != len(hypothesis_ids)
                    or not set(hypothesis_ids) <= self.labels.keys()):
                raise ValueError("Distinct original public hypothesis keys required")
            labels = {h: self.labels[h] for h in hypothesis_ids}
            bank = project_criteria(bank, hypothesis_ids)
        actual = bank if arm == "skills" else []
        messages, schema, trace = source_messages(row, labels, self.system, [],
            None, incremental_encoding="records")
        messages = actor_messages(messages, actual, labels)
        assert not trace["actual_source_executions"]
        tokens = self.meter.token_count(messages=messages)
        assert tokens + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"]
        return {"document_id": row["id"], "arm": arm, "messages": messages, "schema": schema,
            "prompt_tokens": tokens, "bank": copy.deepcopy(actual), "bank_sha256": csha(actual),
            "served_criteria": one_copy_criteria(actual),
            "full_original_source_only": True,
            "no_candidate_model_queries_windows_or_host_answer_decision": True}

    def select_current_own(self, seen):
        """Latest actual same-parent answer per source, never the best answer."""
        latest = {u["document_id"]: u for u in self.own_history if u["bank_sha256"] == csha(self.bank)}
        assert {r["id"] for r in seen} <= latest.keys()
        self.own = [latest[r["id"]] for r in seen]
        assert len({u["response"]["raw_id"] for u in self.own}) == len(seen)
        assert all(u["native_schema_valid"] and u["condition"] == "skills" for u in self.own)

    def teacher_body(self, seen):
        self.select_current_own(seen)
        gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        encoded = teacher_sources(seen, gold)
        answers = {u["document_id"]: json.loads(u["response"]["content"]) for u in self.own}
        observations = []
        for unit in self.own:
            p = read(unit["payload"])
            assert p["bank"] == self.bank and p["full_original_source_only"] is True
            actual = json.loads(p["messages"][1]["content"])
            assert "candidate_original_text" not in actual
            assert all(set(q) == {"original_hypothesis", "original_public_short_description"}
                for q in actual["hypotheses"].values())
            assert actual.get("evidence_selection_criteria", []) == one_copy_criteria(self.bank)
            observations.append({"document_id": unit["document_id"], "actual_stage": unit["stage"],
                "actual_bank_sha256": unit["bank_sha256"], "actual_native_raw_id": unit["response"]["raw_id"],
                "actual_public_answer": keyed(answers[unit["document_id"]]),
                "actual_input_payload_sha256": sha(unit["payload"]), "actual_native_artifact_sha256": sha(unit["raw_artifact"])})
        contrasts = member_contrasts(seen, self.labels, gold, answers)
        decoded = expand_member_contrasts(contrasts, encoded)
        for h, cases in decoded.items():
            for source, case in zip(seen, cases, strict=True):
                d = source["id"]
                assert case["source_case_id"] == d
                assert {m["original_span_index"] for m in case["members"]} == set(gold[str(d)][h]["spans"]) | set(answers[d][h]["spans"])
        body = {"public_hypotheses": self.labels,
            "complete_cumulative_original_TRAIN_sources_and_Gold": encoded,
            "current_parent_library": table(self.bank),
            "actual_own_public_observations": table(observations),
            "cross_source_relation_index": {h: {choice: [r["id"] for r in seen if gold[str(r["id"])][h]["choice"] == choice]
                for choice in ("Entailment", "Contradiction", "NotMentioned")} for h in self.labels},
            "member_contrasts_by_hypothesis": contrasts,
            "hypothesis_error_profiles": hypothesis_error_profiles(decoded),
            "all_current_parent_own_successes_failures_included_no_other_arm_answers": True,
            "serving_notice": MEMBER_NOTICE, "source_only_actor_without_retrieval": True}
        body["learning_response_window"] = {
            "selection": "Latest actual current-parent own answer per supplied seen source, by chronology not outcome.",
            "supplied_seen_source_ids": [r["id"] for r in seen],
            "actual_selected_own_answers": len(self.own), "archived_own_answers": len(self.own_history),
            "older_raw_answers_archived_and_previously_taught_not_resupplied_as_current_parent": True}
        body["future_actor_input_contract"] = {
            "unchanged_native_solver_system": self.system, "common_notice_all_arms": body["serving_notice"],
            "evidence_selection_criteria": "Top-level one-copy records with public hypothesis_ids and verbatim criterion. No opaque skill IDs, repeated per-hypothesis prose or queries required. All17 hypotheses remain visible together.",
            "full_source_without_candidates_or_membership_scores": True,
            "no_learned_queries_windows_filtering_or_host_citation_union": True,
            "unchanged_final_fields": ["choice", "spans", "reason"],
            "full_original_text_any_original_citation_no_host_answer_decision": True}
        return {"encoding": "source-only-indexed-original-members-teacher-v3", "body": body, "legend": (
            "Record/keyed tables expand by their ordered columns/keys. Complete original sources "
            "are printed once with original <SPAN i> markers; removing markers reconstructs "
            "every source character and original offset. Member rows zip with member_columns "
            "and resolve text by source_case_id/index there. Every seen source, Gold, current-parent "
            "answer and citation remains. cross_source_relation_index indexes only "
            "these original TRAIN annotations. Original NM has undefined evidence membership."
        )}

    def preserve_phase(self, stage):
        super().preserve_phase(stage)
        receipt = self.out / f"phase_backups/{stage}.json"
        source = Path(read(receipt)["archive"])
        destination = Path(self.cfg["rootdisk_backup_directory"]) / source.name
        assert not destination.exists() and source.stat().st_dev != destination.parent.stat().st_dev
        shutil.copy2(source, destination)
        assert sha(destination) == sha(source)
        self.bindings[str(receipt)] = sha(receipt)
        self.record(f"phase_backups/{stage}.rootdisk.json", {"at": now(),
            "source_archive": str(source), "rootdisk_copy": str(destination), "sha256": sha(destination),
            "different_filesystems_verified": True, "all_members_verified_in_source_receipt": str(receipt),
            "same_host_not_offsite_weights_or_auth": True})

    def update(self, seen):
        body = self.teacher_body(seen)
        name = f"update_b{self.current_batch}"
        self.record(f"learning_inputs/{name}.json", body)
        self.preserve_phase(f"b{self.current_batch}_before_teacher")
        schema = differential_schema(self.labels, self.bank, [r["id"] for r in seen], guidance_schema=EDIT_GUIDANCE)
        value = self.teacher_call(name, WRITER, body, schema)
        for p in (self.out / "teacher" / name).glob("*.json"):
            self.bindings[str(p)] = sha(p)
        published = apply_differential_publication(self.bank, value, self.labels,
            [r["id"] for r in seen], guidance_schema=EDIT_GUIDANCE)
        capacity = self.capacity(published)
        stats = publication_statistics(self.bank, value, published, capacity["master"])
        stats["non_null_criteria"] = sum(s["guidance"].get("evidence_criterion") is not None for s in published)
        self.record(f"publications/b{self.current_batch}.json", {"at": now(), "parent": self.bank,
            "delta": value, "publication": published, "capacity": capacity, "statistics": stats,
            "complete_teaching_source_ids": [r["id"] for r in seen],
            "actual_current_parent_own_native_responses": len(self.own),
            "source_only_actor_without_retrieval": True,
            "all_valid_edits_and_NOOP_publish_without_efficacy_admission": True})
        self.bank = published
        self.banks[csha(published)] = copy.deepcopy(published)
        return stats

    def answer(self, entry):
        p = read(entry["path"])
        dest = self.out / f"native/{entry['stage']}/{entry['arm']}/{entry['document_id']}.final.native.json"
        response = self.call(dest, p["messages"], p["schema"], self.cfg["generation"]["max_tokens"], {
            **entry, "call_role": "final", "bank_sha256": p["bank_sha256"]})
        valid, error = True, None
        try:
            assert response["finish_reason"] == "stop", "Incomplete native response"
            validate(json.loads(response["content"]), p["schema"])
        except (AssertionError, ValueError, TypeError, ValidationError) as exc:
            valid, error = False, str(exc)
        unit = {"stage": entry["stage"], "condition": entry["arm"], "document_id": entry["document_id"],
            "raw_artifact": str(dest), "payload": entry["path"], "response": response,
            "bank_sha256": p["bank_sha256"], "exact_same_run_cold_alias": False,
            "native_schema_valid": valid, "native_schema_failure": error, "native_content_never_repaired": True}
        self.bindings[str(dest)] = sha(dest)
        self.record(f"ungraded_answers/{entry['stage']}/{entry['arm']}/{entry['document_id']}.json", unit)
        return unit

    def audit_and_grade(self, units):
        sources = {r["id"]: r for r in self.training}
        for u in units:
            p, raw = read(u["payload"]), read(u["raw_artifact"])
            assert len(raw["calls"]) == 1 and raw["transport_error"] is None and raw["response"] == u["response"]
            request = raw["calls"][0]["request"]
            assert request["messages"] == p["messages"]
            assert request["response_format"]["json_schema"]["schema"] == p["schema"]
            assert all(request[k] == self.cfg["generation"][k] for k in ("model", "seed", "temperature", "top_p", "top_k", "max_tokens"))
            expected_template = {"enable_thinking": False} if self.cfg["generation"].get("disable_thinking", False) else None
            assert request.get("chat_template_kwargs") == expected_template
            assert csha(p["bank"]) == u["bank_sha256"] == p["bank_sha256"]
            assert json.loads(p["messages"][1]["content"])["full_contract_with_original_span_markers"] == marked_text(sources[u["document_id"]])
        gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        result = []
        for u in units:
            response = u["response"] if u["native_schema_valid"] else {"content": "", "finish_reason": None}
            result.append({**u, **original_score(response, sources[u["document_id"]], gold[str(u["document_id"])], list(self.labels))})
        self.units.extend(result)
        self.record(f"scored_phases/{units[0]['stage']}.json", {"at": now(), "units": result,
            "invalid_answers_retained_in_original_denominators": sum(not u["native_schema_valid"] for u in result)})
        if any(not u["native_schema_valid"] for u in result):
            raise ValueError("Complete phase scored including invalids; no invented own answer, repair or teacher retry")
        return result

    def effect(self, before, after):
        return paired_effect(before, after, seed=self.cfg["analysis"]["seed"], replicates=self.cfg["analysis"]["bootstrap_replicates"])


    def execute(self):
        self.check()
        self.record("declaration.json", {"at": now(), "config": self.cfg, "frozen_bindings": self.bindings.copy(),
            "initial_bank": [], "all_native_answers_new_no_inherited_cold_responses": True,
            "no_inherited_bank_or_teacher_edits_or_initial_bank_selection": True,
            "untouched_official_DEV_TEST": True, "not_independent_repetition_of_an_already_completed_learning_run": True})
        for batch in range(1, 5):
            self.current_batch = batch
            rows, seen = self.training[8 * (batch - 1):8 * batch], self.training[:8 * batch]
            entries = self.freeze_phase(f"b{batch}_before", rows, ARMS)
            answers = [self.answer(e) for e in entries]
            before = self.audit_and_grade(answers)
            self.first.extend(before)
            self.own_history.extend(u for u in before if u["condition"] == "skills")
            self.select_current_own(seen)
            parent = self.own.copy()
            self.record(f"b{batch}_before_complete.json", {"at": now(), "units": before,
                "metrics": {a: points([u for u in before if u["condition"] == a]) for a in ARMS},
                "all16_actual_answers_before_current_batch_teacher_feedback": True})
            stats = self.update(seen)
            entries = self.freeze_phase(f"b{batch}_after_all_seen", seen, ["skills"])
            after = self.audit_and_grade([self.answer(e) for e in entries])
            self.own_history.extend(after)
            ids = {r["id"] for r in rows}
            current_after = [u for u in after if u["document_id"] in ids]
            old_parent = [u for u in parent if u["document_id"] not in ids]
            summary = {"at": now(), "batch": batch, "source_ids": [r["id"] for r in rows],
                "before": {a: points([u for u in before if u["condition"] == a]) for a in ARMS},
                "after": {"skills": points(current_after)}, "retention_all_seen": points(after),
                "prequential_skill_vs_strong_empty": self.effect([u for u in before if u["condition"] == "strong_empty"], [u for u in before if u["condition"] == "skills"]),
                "current_batch_parent_to_published": self.effect([u for u in parent if u["document_id"] in ids], current_after),
                "all_seen_parent_to_published": self.effect(parent, after),
                "old_sources_parent_to_published": self.effect(old_parent, [u for u in after if u["document_id"] not in ids]) if old_parent else None,
                "library_management": stats, "source_only_actor_without_retrieval": True,
                "after_is_seen_fit_and_retention_not_new_case_transfer": True}
            self.record(f"b{batch}_all_seen_retention.json", {"at": now(), "units": after,
                "by_original_batch": {str(b): points([u for u in after if u["document_id"] in {
                    r["id"] for r in self.training[8 * (b - 1):8 * b]}]) for b in range(1, batch + 1)}})
            self.record(f"batch{batch}_summary.json", summary)
            self.summaries.append(summary)
            self.preserve_phase(f"b{batch}_complete")
            self.progress("batch_complete", finished_batch=batch)
        assert len(self.native) == self.cfg["planned_new_native_calls"]
        assert len(self.units) == len({u["response"]["raw_id"] for u in self.units}) == 144
        assert self.inherited_count == 0
        assert len(self.teachers) == 4 and len(self.own_history) == 112
        complete = {"at": now(), "run_id": self.run_id,
            "actual_new_native_teacher_calls": [len(self.native), 4],
            "inherited_exact_cold_native_answers": self.inherited_count,
            "logical_native_answers": len(self.units), "initial_bank_empty": True,
            "prequential_results": {a: points([u for u in self.first if u["condition"] == a]) for a in ARMS},
            "prequential_skill_vs_controls": {a: self.effect([u for u in self.first if u["condition"] == a], [u for u in self.first if u["condition"] == "skills"]) for a in ARMS if a != "skills"},
            "final_seen_retention": self.summaries[-1]["retention_all_seen"],
            "final_seen_vs_first_empty": self.effect([u for u in self.first if u["condition"] == "strong_empty"], after),
            "final_library": self.bank, "actual_teacher_invocations": [t["invocation"] for t in self.teachers],
            "actual_native_usage": {k: sum(r["response"][k] for r in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "source_only_actor_without_retrieval": True,
            "new_online_episode_not_mature_baseline_win_independent_repeats_or_official_TEST": True}
        self.check()
        self.record("completion.json", complete)
        self.preserve_phase("complete_terminal")
        RunStore.atomic_json(self.out / "progress.json", {"state": "completed", **complete})
        print(compact({"completed": self.run_id, "actual_new_native_teacher_calls": [len(self.native), 4],
            "prequential_results": complete["prequential_results"], "final_seen_retention": complete["final_seen_retention"]}))


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
        study = MemberLearning(args.config)
        try:
            study.execute()
        except BaseException as exc:
            failure = {"at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
                "actual_native_teacher_calls": [len(study.native), len(study.teachers)],
                "teacher_attempts": study.teacher_attempts,
                "all_raw_invalid_partial_phases_and_costs_retained_no_retry_or_repair": True,
                "completion_record_exists": (study.out / "completion.json").exists()}
            RunStore.immutable_json(study.out / "failure.json", failure)
            RunStore.atomic_json(study.out / "progress.json", {"state": "failed", **failure})
            raise


if __name__ == "__main__":
    main()
