"""One actual member-criterion update and a complete four-arm development study.

Reuse existing frozen-model/teacher/editor primitives. Preparation and execution
are separate commands; no implicit re-preparation, inference retry or answer fix.
"""

# ruff: noqa: E402 -- Bind the authoritative project before importing its modules.
from __future__ import annotations

import argparse
import copy
import fcntl
import json
import shutil
import sys
import traceback
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FOLDER))

from evidence_contract import (
    EVIDENCE_GUIDANCE_SCHEMA,
    NEW_NOTICE_SENTENCE,
    OLD_NOTICE_SENTENCE,
    WRITER_SYSTEM,
    criterion_projection,
    member_contrasts,
    render_discriminative,
)
from jsonschema import ValidationError, validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.acquisition import (
    CONTRAST_TEACHER_NOTE,
    NOTICE,
    AcquisitionStudy,
    compact,
    execute_library,
)
from legal_skill_guard.learning.audit import original_score
from legal_skill_guard.learning.evidence_programs import evidence_proposals
from legal_skill_guard.learning.experiment import now, points, read, sha
from legal_skill_guard.learning.packing import expand
from legal_skill_guard.learning.publication import (
    apply_differential_publication,
    differential_schema,
    paired,
    publication_statistics,
    skill_record_schema,
)
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

PARENT = ROOT / "runs/legal_contractnli_published_acquisition_continuation_20261017_run01"
CONFIG = FOLDER / "config.json"
RUN_ID = "legal_contractnli_discriminative_evidence_skill_20261017_run01"
IDS = [501, 339, 164, 253, 421, 295, 132, 427]
ARMS = ["skills", "acquisition", "ordinary", "strong_empty"]


def prepare():
    """Freeze original completed evidence before any new teacher/generation."""
    assert not CONFIG.exists() and not (ROOT / "runs" / RUN_ID).exists()
    assert read(PARENT / "completion.json")["actual_new_native_teacher_calls"] == [80, 1]
    parent_path = ROOT / "configs/contractnli_published_acquisition_continuation.json"
    parent, frozen = read(parent_path), read(parent_path.with_suffix(".frozen.json"))
    assert sha(parent_path) == frozen["config_sha256"]
    assert all(sha(p) == h for p, h in frozen["files"].items())
    assert IDS == [d for i, d in enumerate(parent["training_ids"]) if i % 8 < 2]
    for phase in ("teacher", "retention"):
        assert read(PARENT / f"monitoring/{phase}_complete_original_author_wire_and_teacher_audit.json")[
            "all_phase_original_author_and_actual_wires_checked"]
    complete12 = ROOT / "runs/legal_contractnli_explicit_member_execution_20261017_run02"
    assert read(complete12 / "completion.json")["completed_native_calls"] == 12
    assert read(complete12 / "monitoring/complete12_original_author_native_bit_and_control_audit.json")[
        "all12_actual_wires_and_original_author_members_checked"]
    keep = ("generation", "teacher", "inference_environment", "ordinary_manifest", "input_packet", "grading_only",
        "training_ids", "solver_system_reference", "library_token_hard_cap", "prelaunch_backup_receipt",
        "source_archive", "source_archive_sha256", "teacher_evidence_view")
    cfg = {k: copy.deepcopy(parent[k]) for k in keep}
    cfg.update(method="discriminative_evidence_skill", run_id=RUN_ID,
        planned_new_native_calls=32, planned_new_teacher_calls=1, diagnostic_source_ids=IDS,
        diagnostic_arms=ARMS, incremental_source_encoding="scored_records",
        fixed_parent_publication=str(PARENT / "publications/b4.json"),
        fixed_parent_publication_sha256=sha(PARENT / "publications/b4.json"),
        current_parent_own_answers=str(PARENT / "b4_all_seen_retention.json"),
        historical_publications=parent["historical_publications"] + [str(PARENT / "publications/b4.json")],
        method_protocol="docs/DISCRIMINATIVE_EVIDENCE_SKILL_PROTOCOL_20261017.md",
        all_seen_TRAIN_fit_development_not_transfer_independent_learning_or_official_TEST=True,
        response_window="ALL32_current_parent_canonical_own_answers_not_earlier96_or_mask",
        publication_step=5)
    paths = [parent_path, parent_path.with_suffix(".frozen.json"), Path(__file__), FOLDER / "evidence_contract.py",
        ROOT / cfg["method_protocol"], PARENT / "completion.json", Path(cfg["fixed_parent_publication"]),
        Path(cfg["current_parent_own_answers"]),
        PARENT / "monitoring/R3_complete32_source_access_and_all11_edit_content_audit_not_native_gain.json",
        complete12 / "completion.json", complete12 / "monitoring/complete12_original_author_native_bit_and_control_audit.json",
        FOLDER / "complete12_preservation_before_new_learner.json"]
    own = read(cfg["current_parent_own_answers"])["units"]
    assert [u["document_id"] for u in own] == cfg["training_ids"]
    assert len(own) == len({u["response"]["raw_id"] for u in own}) == 32
    assert {u["condition"] for u in own} == {"skills"}
    paths.extend(Path(u[k]) for u in own for k in ("payload", "raw_artifact"))
    paths.extend(ROOT / p for p in cfg["historical_publications"])
    RunStore.immutable_json(CONFIG, cfg)
    files = frozen["files"] | {str(p.resolve()): sha(p) for p in paths + [CONFIG]}
    RunStore.immutable_json(CONFIG.with_suffix(".frozen.json"), {"config_sha256": sha(CONFIG), "files": files})
    print(compact({"prepared": str(CONFIG), "bound_files": len(files), "native_teacher_calls": [0, 0]}))


class DiscriminativeEvidenceStudy(AcquisitionStudy):
    def __init__(self, config):
        super().__init__(config)
        assert self.cfg["diagnostic_source_ids"] == IDS and self.cfg["diagnostic_arms"] == ARMS
        assert sha(self.cfg["fixed_parent_publication"]) == self.cfg["fixed_parent_publication_sha256"]
        self.bank = read(self.cfg["fixed_parent_publication"])["publication"]
        self.banks = {csha(self.bank): copy.deepcopy(self.bank)}
        self.own = read(self.cfg["current_parent_own_answers"])["units"]
        assert [u["document_id"] for u in self.own] == self.cfg["training_ids"]
        assert {u["bank_sha256"] for u in self.own} == {csha(self.bank)}
        self.current_batch = self.cfg["publication_step"]
        self.proposals = {r["id"]: evidence_proposals(self.model, r, self.labels) for r in self.training}

    def capacity(self, bank):
        assert len({s["id"] for s in bank}) == len(bank)
        for s in bank:
            validate(s, skill_record_schema(self.labels, guidance_schema=EVIDENCE_GUIDANCE_SCHEMA))
            assert len(s["hypothesis_ids"]) == len(set(s["hypothesis_ids"]))
        execute_library({"id": -1, "text": "", "spans": []}, bank)
        value = {"master": self.meter.token_count(text=compact(bank)),
            "with_public_scope_map": self.meter.token_count(text=compact({"library": bank, "scope": {
                h: [s["id"] for s in bank if h in s["hypothesis_ids"]] for h in self.labels}})),
            "actual_criterion_projection": self.meter.token_count(text=compact(criterion_projection(bank, self.labels)))}
        assert max(value.values()) <= self.cfg["library_token_hard_cap"], "Oversize retained; no pruning or retry"
        return value

    def payload(self, row, arm, bank):
        assert arm in ARMS
        p = super().payload(row, "skills" if arm == "acquisition" else arm, bank)
        p["arm"] = arm
        p["messages"] = render_discriminative(p["messages"], p["bank"], self.labels,
            p["actual_factual_trace"], include_criterion=arm == "skills")
        trace = p["actual_factual_trace"]
        del trace["no_program_code_or_semantic_inspection_delivered"]
        trace.update(no_program_code_delivered=True,
            learned_criteria_delivered=arm == "skills" and any(criterion_projection(p["bank"], self.labels).values()),
            access_roles_are_literal_facts_not_semantic_labels=True)
        p["criterion_text_withheld_ablation"] = arm == "acquisition"
        p["prompt_tokens"] = self.meter.token_count(messages=p["messages"])
        assert p["prompt_tokens"] + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"]
        return p

    def teacher_body(self, seen):
        result = super().teacher_body(seen)
        body = result["body"]
        del body["all_cumulative_own_successes_failures_retention_included_no_other_arm_answers"]
        body["all_current_parent_own_successes_failures_included_no_other_arm_answers"] = True
        body["learning_response_window"] = self.cfg["response_window"]
        annotations = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        answers = {u["document_id"]: json.loads(u["response"]["content"]) for u in self.own}
        executions = {u["document_id"]: read(u["payload"])["actual_factual_trace"]["actual_source_executions"] for u in self.own}
        body["member_contrasts_by_hypothesis"] = member_contrasts(seen, self.labels,
            annotations, answers, self.bank, executions, self.proposals)
        body["future_actor_input_contract"] = {
            "unchanged_native_solver_system": self.system,
            "common_notice_all_four_arms": NOTICE.replace(OLD_NOTICE_SENTENCE, NEW_NOTICE_SENTENCE),
            "additional_source_read_indices": "Same original index and unchanged membership_score, plus literal_match, explicit_neighbour, possible_list_preamble booleans.",
            "evidence_selection_criteria": "Optional published concise text under its original hypothesis; absent in the declared withholding arm.",
            "factual_roles_not_member_predictions_or_semantic_dependencies": True,
            "unchanged_final_fields": ["choice", "spans", "reason"],
            "all_source_text_original_coordinates_and_any_outside_citation_remain_available": True}
        body["confirmed_parent_portability_observations_not_manual_edits"] = read(
            PARENT / "monitoring/R3_complete32_source_access_and_all11_edit_content_audit_not_native_gain.json")[
                "confirmed_named_party_runtime_queries"]
        return result

    def preserve_phase(self, stage):
        super().preserve_phase(stage)
        receipt = read(self.out / f"phase_backups/{stage}.json")
        source = Path(receipt["archive"])
        dest = Path("/home/yndx/hhy/legal-skill-rootdisk-backups") / source.name
        assert not dest.exists() and source.stat().st_dev != dest.parent.stat().st_dev
        shutil.copy2(source, dest)
        assert sha(dest) == receipt["archive_sha256"]
        path = self.out / f"phase_backups/{stage}.rootdisk.json"
        RunStore.immutable_json(path, {"at": now(), "source_archive": str(source), "rootdisk_copy": str(dest),
            "sha256": sha(dest), "different_filesystems_verified": True,
            "all_members_verified_in_source_receipt": str(self.out / f"phase_backups/{stage}.json"),
            "same_host_not_offsite_weights_or_auth": True})
        self.bindings[str(path)] = sha(path)

    def update(self, seen):
        body = self.teacher_body(seen)
        name = f"update_b{self.current_batch}"
        path = self.out / f"learning_inputs/{name}.json"
        RunStore.immutable_json(path, body)
        self.bindings[str(path)] = sha(path)
        self.preserve_phase("before_teacher")
        schema = differential_schema(self.labels, self.bank, [r["id"] for r in seen], guidance_schema=EVIDENCE_GUIDANCE_SCHEMA)
        value = self.teacher_call(name, WRITER_SYSTEM + CONTRAST_TEACHER_NOTE, body, schema)
        for p in (self.out / "teacher" / name).glob("*.json"):
            self.bindings[str(p)] = sha(p)
        published = apply_differential_publication(self.bank, value, self.labels, [r["id"] for r in seen],
            guidance_schema=EVIDENCE_GUIDANCE_SCHEMA)
        capacity = self.capacity(published)
        stats = publication_statistics(self.bank, value, published, capacity["master"])
        path = self.out / f"publications/b{self.current_batch}.json"
        RunStore.immutable_json(path, {"at": now(), "parent": self.bank, "delta": value,
            "publication": published, "capacity": capacity, "statistics": stats,
            "complete_teaching_source_ids": [r["id"] for r in seen],
            "actual_same_parent_own_native_responses": len(self.own), "no_other_arm_or_mask_answers": True,
            "fixed_ordinary_model_state": self.manifest["state_sha256"],
            "no_fitting_effect_admission_rollback_or_native_answer_repair": True})
        self.bindings[str(path)] = sha(path)
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
            "native_schema_valid": valid, "native_schema_failure": error,
            "native_content_never_repaired": True}
        path = self.out / f"ungraded_answers/{entry['arm']}/{entry['document_id']}.json"
        RunStore.immutable_json(path, unit)
        self.bindings.update({str(dest): sha(dest), str(path): sha(path)})
        return unit

    def execute(self):
        self.check()
        RunStore.immutable_json(self.out / "declaration.json", {"at": now(), "run_id": self.run_id,
            "config": self.cfg, "frozen_bindings": self.bindings,
            "inherited_own_observations_not_new_calls": 32,
            "not_online_cold_start_transfer_independent_learning_or_official_TEST": True})
        stats = self.update(self.training)
        rows = [r for r in self.training if r["id"] in IDS]
        assert [r["id"] for r in rows] == IDS
        entries = self.freeze_phase("criterion_probe", rows, ARMS)
        units = [self.answer(entry) for entry in entries]
        assert len(units) == len(self.native) == 32 and len(self.teachers) == 1
        gold = read(ROOT / self.cfg["grading_only"])["original_TRAIN_annotations"]
        sources = {r["id"]: r for r in rows}
        for u in units:
            p, raw = read(u["payload"]), read(u["raw_artifact"])
            assert len(raw["calls"]) == 1 and raw["transport_error"] is None and raw["response"] == u["response"]
            request = raw["calls"][0]["request"]
            assert request["messages"] == p["messages"]
            assert request["response_format"]["json_schema"]["schema"] == p["schema"]
            scoring_response = u["response"] if u["native_schema_valid"] else {"content": "", "finish_reason": None}
            u.update(original_score(scoring_response, sources[u["document_id"]], gold[str(u["document_id"])], list(self.labels)))
        results = {a: points([u for u in units if u["condition"] == a]) for a in ARMS}
        RunStore.immutable_json(self.out / "complete32_native_and_original_scores.json", {"units": units})
        complete = {"at": now(), "run_id": self.run_id, "completed_native_calls": len(self.native),
            "completed_teacher_calls": len(self.teachers), "actual_development_contracts": len(rows),
            "planned_arms": ARMS, "publication": stats, "results": results,
            "paired_skills_vs_controls": {a: paired([u for u in units if u["condition"] == a],
                [u for u in units if u["condition"] == "skills"]) for a in ARMS if a != "skills"},
            "invalid_native_answers_included_in_original_denominators": sum(not u["native_schema_valid"] for u in units),
            "actual_native_usage": {k: sum(u["response"][k] for u in units) for k in ("prompt_tokens", "completion_tokens")},
            "actual_teacher_invocations": self.teachers,
            "not_new_case_transfer_or_independent_learning_or_official_TEST": True}
        self.check()
        RunStore.immutable_json(self.out / "completion.json", complete)
        RunStore.atomic_json(self.out / "progress.json", {"state": "completed", **complete})
        print(compact({"completed": self.run_id, "new_native_teacher_calls": [32, 1], "results": results}))


def audit_completed():
    """Read actual wires and author TRAIN; manually count, not the producer scorer."""
    out = ROOT / "runs" / RUN_ID
    cfg, frozen = read(CONFIG), read(CONFIG.with_suffix(".frozen.json"))
    assert sha(CONFIG) == frozen["config_sha256"]
    assert all(sha(p) == h for p, h in frozen["files"].items())
    complete = read(out / "completion.json")
    assert complete["completed_native_calls"] == 32 and complete["completed_teacher_calls"] == 1
    units = read(out / "complete32_native_and_original_scores.json")["units"]
    assert len(units) == len({u["response"]["raw_id"] for u in units}) == 32
    assert {(u["condition"], u["document_id"]) for u in units} == {(a, d) for a in ARMS for d in IDS}
    archive_path = ROOT / cfg["source_archive"]
    assert sha(archive_path) == cfg["source_archive_sha256"]
    with zipfile.ZipFile(archive_path) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    sources = {r["id"]: r for r in author["documents"]}
    labels = author["labels"]
    teaching = read(out / "learning_inputs/update_b5.json")
    body = expand(teaching)["body"]
    teacher_request = read(out / "teacher/update_b5/wire_request.json")
    teacher_response = read(out / "teacher/update_b5/response.json")
    assert teacher_request["system_prompt"] == WRITER_SYSTEM + CONTRAST_TEACHER_NOTE
    assert teacher_request["user_prompt"] == compact(teaching)
    assert teacher_request["model"] == cfg["teacher"]["model"]
    assert not teacher_response["cache_hit"] and not teacher_response["invocation"].get("tool_events_detected")
    assert [r["id"] for r in body["complete_cumulative_original_TRAIN_sources_and_Gold"]] == cfg["training_ids"]
    own = read(cfg["current_parent_own_answers"])["units"]
    assert len(body["actual_own_public_observations"]) == len(own) == 32
    positive_members = 0
    parent_bank = read(cfg["fixed_parent_publication"])["publication"]
    parent_payloads = {}
    for old, taught, observed in zip(own, body["complete_cumulative_original_TRAIN_sources_and_Gold"],
            body["actual_own_public_observations"], strict=True):
        d = old["document_id"]
        row, gold = sources[d], sources[d]["annotation_sets"][0]["annotations"]
        assert taught == {k: row[k] for k in ("id", "text", "spans")} | {"original_annotations": gold}
        assert observed["actual_public_answer"] == json.loads(old["response"]["content"])
        assert observed["actual_native_raw_id"] == old["response"]["raw_id"]
        assert observed["actual_bank_sha256"] == csha(parent_bank)
        parent_payloads[d] = read(old["payload"])
        old_raw = read(old["raw_artifact"])
        assert old_raw["response"] == old["response"] and len(old_raw["calls"]) == 1
        assert old_raw["calls"][0]["request"]["messages"] == parent_payloads[d]["messages"]
        actual = observed["actual_public_answer"]
        for h in labels:
            contrast = next(c for c in body["member_contrasts_by_hypothesis"][h] if c["source_case_id"] == d)
            assert contrast["original_choice"] == gold[h]["choice"] and contrast["actual_choice"] == actual[h]["choice"]
            gm, pm = set(gold[h]["spans"]), set(actual[h]["spans"])
            assert [m["original_span_index"] for m in contrast["members"]] == sorted(gm | pm)
            for m in contrast["members"]:
                i = m["original_span_index"]
                assert m["original_text"] == row["text"][slice(*row["spans"][i])]
                assert m["original_member"] == (i in gm if gold[h]["choice"] != "NotMentioned" else None)
                assert m["actually_cited"] == (i in pm)
                positive_members += m["original_member"] is True
    assert positive_members == 604
    publication = read(out / "publications/b5.json")
    assert publication["parent"] == parent_bank and publication["delta"] == teacher_response["value"]
    assert apply_differential_publication(parent_bank, teacher_response["value"], labels, cfg["training_ids"],
        guidance_schema=EVIDENCE_GUIDANCE_SCHEMA) == publication["publication"]
    bank = publication["publication"]
    manual = {a: {"hypotheses": 0, "label_correct": 0, "evidence_tp": 0, "evidence_fp": 0,
        "evidence_fn": 0, "joint_exact_correct": 0} for a in ARMS}
    payloads, invalids, reasoning = {}, 0, 0
    for u in units:
        d, a = u["document_id"], u["condition"]
        row, p, raw = sources[d], read(u["payload"]), read(u["raw_artifact"])
        gold = row["annotation_sets"][0]["annotations"]
        assert len(raw["calls"]) == 1 and raw["transport_error"] is None and raw["response"] == u["response"]
        request, response = raw["calls"][0]["request"], raw["calls"][0]["response"]
        assert request["messages"] == p["messages"]
        assert request["response_format"]["json_schema"]["schema"] == p["schema"]
        assert request["model"] == response["model"] == cfg["generation"]["model"]
        for name in ("temperature", "top_p", "top_k", "seed", "max_tokens"):
            assert request[name] == cfg["generation"][name]
        assert response["id"] == u["response"]["raw_id"]
        assert response["usage"]["prompt_tokens"] == p["prompt_tokens"]
        assert (response["choices"][0]["message"].get("content") or "").strip() == u["response"]["content"]
        reasoning += bool(response["choices"][0]["message"].get("reasoning_content"))
        payloads[a, d] = p
        served = json.loads(p["messages"][1]["content"])
        assert served["full_contract_with_original_span_markers"] == marked_text({k: row[k] for k in ("id", "text", "spans")})
        for h in labels:
            assert served["hypotheses"][h]["original_hypothesis"] == labels[h]["hypothesis"]
        actual, independently_valid = None, True
        try:
            assert u["response"]["finish_reason"] == "stop"
            actual = json.loads(u["response"]["content"])
            validate(actual, p["schema"])
        except (AssertionError, ValueError, TypeError, ValidationError):
            actual = None
            independently_valid = False
            invalids += 1
        assert independently_valid == u["native_schema_valid"]
        m = manual[a]
        for h in labels:
            g, predicted = gold[h], actual[h] if actual is not None else None
            gs, ps = set(g["spans"]), set(predicted["spans"]) if predicted else set()
            correct = predicted is not None and predicted["choice"] == g["choice"]
            m["hypotheses"] += 1
            m["label_correct"] += correct
            m["joint_exact_correct"] += correct and ps == gs
            if g["choice"] != "NotMentioned":
                m["evidence_tp"] += len(gs & ps)
                m["evidence_fp"] += len(ps - gs)
                m["evidence_fn"] += len(gs - ps)
    for d in IDS:
        a, b = (copy.deepcopy(json.loads(payloads[arm, d]["messages"][1]["content"])) for arm in ("skills", "acquisition"))
        for h in labels:
            criteria = a["hypotheses"][h].pop("evidence_selection_criteria", [])
            assert criteria == criterion_projection(bank, labels)[h]
        assert a == b and payloads["skills", d]["bank"] == payloads["acquisition", d]["bank"] == bank
        assert len({payloads[arm, d]["messages"][0]["content"] for arm in ARMS}) == 1
        assert all(payloads[arm, d]["schema"] == payloads["skills", d]["schema"] for arm in ARMS)
        parent_body = json.loads(parent_payloads[d]["messages"][1]["content"])
        for arm in ARMS:
            served = json.loads(payloads[arm, d]["messages"][1]["content"])
            actual_bank = bank if arm in ("skills", "acquisition") else []
            assert payloads[arm, d]["bank"] == actual_bank
            assert payloads[arm, d]["bank_sha256"] == csha(actual_bank)
            assert NEW_NOTICE_SENTENCE in payloads[arm, d]["messages"][0]["content"]
            assert OLD_NOTICE_SENTENCE not in payloads[arm, d]["messages"][0]["content"]
            executions = execute_library({k: sources[d][k] for k in ("id", "text", "spans")}, actual_bank)
            assert executions == payloads[arm, d]["actual_factual_trace"]["actual_source_executions"]
            for h in labels:
                candidates = served["hypotheses"][h]["fallible_evidence_candidates"]
                assert candidates == ([] if arm == "strong_empty" else parent_body["hypotheses"][h]["fallible_evidence_candidates"])
                ordinary = {c["original_span_index"] for c in candidates}
                roles = {role: {i for s in actual_bank if h in s["hypothesis_ids"]
                    for event in executions[s["id"]] for i in event[role]}
                    for role in ("matched", "neighbour", "preamble")}
                additional = served["hypotheses"][h]["additional_source_read_indices"]
                assert [x["original_span_index"] for x in additional] == sorted(set.union(*roles.values()) - ordinary)
                for record in additional:
                    i = record["original_span_index"]
                    assert record["literal_match"] == (i in roles["matched"])
                    assert record["explicit_neighbour"] == (i in roles["neighbour"])
                    assert record["possible_list_preamble"] == (i in roles["preamble"])
                    assert served["candidate_original_text"][str(i)] == sources[d]["text"][slice(*sources[d]["spans"][i])]
    for arm, m in manual.items():
        assert m["hypotheses"] == len(IDS) * len(labels) == 136
        m["label_accuracy"] = m["label_correct"] / m["hypotheses"]
        m["joint_exact_accuracy"] = m["joint_exact_correct"] / m["hypotheses"]
        m["evidence_micro_f1_gold_non_neutral"] = 2 * m["evidence_tp"] / (2 * m["evidence_tp"] + m["evidence_fp"] + m["evidence_fn"])
        assert all(abs(complete["results"][arm][k] - v) < 1e-12 for k, v in m.items())
    assert invalids == complete["invalid_native_answers_included_in_original_denominators"]
    path = out / "monitoring/complete32_actual_wires_teacher_original_member_and_ablation_audit.json"
    RunStore.immutable_json(path, {"at": now(), "all32_actual_wires_and_original_author_members_checked": True,
        "original_contracts": 8, "actual_new_native_teacher_calls": [32, 1],
        "all32_current_parent_canonical_answers_and604_Gold_members_in_actual_teacher": True,
        "criterion_withholding_changes_only_criterion_text_in_actor_body": True,
        "same_current_model_decoding_full_source_original_hypotheses_and_native_schema_all_arms": True,
        "manual_original_set_metrics": manual, "invalid_native_answers_included": invalids,
        "actual_native_nonempty_reasoning_count_not_private_content": reasoning,
        "all_seen_TRAIN_development_not_independent_transfer_or_official_TEST": True,
        "no_new_model_or_teacher_calls_for_audit": True})
    print(compact({"audited": str(path), "actual_native_teacher_calls": [32, 1]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run", "audit"])
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
        return
    if args.command == "audit":
        audit_completed()
        return
    with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        study = DiscriminativeEvidenceStudy(CONFIG)
        try:
            study.execute()
            audit_completed()
        except BaseException as exc:
            failure = {"at": now(), "error": repr(exc), "traceback": traceback.format_exc(),
                "completed_native_calls": len(study.native), "completed_teacher_calls": len(study.teachers),
                "teacher_attempts": study.teacher_attempts, "no_retry_or_partial_effect_grading": True}
            RunStore.immutable_json(study.out / "failure.json", failure)
            RunStore.atomic_json(study.out / "progress.json", {"state": "failed", **failure})
            raise


if __name__ == "__main__":
    main()
