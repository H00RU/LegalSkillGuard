"""Independent completed-phase author, wire, teacher and lineage audit.

Run-local analysis only. Never grade a partial native phase or alter an answer.
"""

# ruff: noqa: E402 -- Bind the actual project/run before importing its modules.
from __future__ import annotations

import argparse
import json
import pickle
import runpy
import sys
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.acquisition import (
    CONTRAST_TEACHER_NOTE,
    GUIDANCE_SCHEMA,
    TEACHER,
    execute_library,
    native_member_feedback,
    source_messages,
)
from legal_skill_guard.learning.evidence_programs import evidence_proposals
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.learning.packing import expand
from legal_skill_guard.learning.publication import apply_differential_publication
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

CFG_PATH = ROOT / "configs/contractnli_published_acquisition_continuation.json"
UTIL_PATH = ROOT / "runs/legal_contractnli_executable_acquisition_online_20261017_run01/monitoring/audit_batch.py"
CI_PATH = ROOT / "runs/legal_contractnli_acquisition_fact_boundary_20261017_run01/monitoring/audit_complete.py"
UTIL = runpy.run_path(str(UTIL_PATH))
counts, contrast = UTIL["counts"], UTIL["contrast"]
resample = runpy.run_path(str(CI_PATH))["source_resampling"]
warnings.filterwarnings("ignore", message="X does not have valid feature names, but LGBMClassifier was fitted with feature names")


class Audit:
    def __init__(self):
        self.cfg = read(CFG_PATH)
        frozen = read(CFG_PATH.with_suffix(".frozen.json"))
        assert sha(CFG_PATH) == frozen["config_sha256"]
        assert all(sha(p) == d for p, d in frozen["files"].items())
        self.bindings = {**frozen["files"], **{str(p): sha(p) for p in (
            CFG_PATH.with_suffix(".frozen.json"), Path(__file__).resolve(), UTIL_PATH, CI_PATH)}}
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        self.sources = {r["id"]: r for r in author["documents"]}
        self.labels = author["labels"]
        self.manifest = self.saved(ROOT / self.cfg["ordinary_manifest"])
        assert sha(self.manifest["path"]) == self.manifest["pickle_sha256"]
        with Path(self.manifest["path"]).open("rb") as stream:
            self.model = pickle.load(stream)
        assert not self.model.queries and not self.model.programs
        self.r1 = self.saved(ROOT / self.cfg["historical_publications"][0])
        self.r2 = self.saved(ROOT / self.cfg["initial_bank_publication"])
        assert self.r2["parent"] == self.r1["publication"]
        self.proposals = {}

    def saved(self, path):
        p = Path(path).resolve()
        self.bindings[str(p)] = sha(p)
        return read(p)

    def bank(self, u):
        if u["condition"] in ("ordinary", "strong_empty"):
            return []
        stage = u["stage"]
        if stage == "held_K2_interface":
            return self.r1["parent"]
        if stage in ("prefix_after_repair", "b3_before", "held_R1_record_score"):
            return self.r1["publication"]
        if stage in ("published_R2_prefix", "b4_before"):
            return self.r2["publication"]
        assert stage == "b4_after_all_seen"
        return self.saved(OUT / "publications/b4.json")["publication"]

    def units(self, units, *, grade=True):
        rows, ids, usage = [], set(), {k: 0 for k in ("prompt_tokens", "completion_tokens")}
        for u in units:
            p, raw = self.saved(u["payload"]), self.saved(u["raw_artifact"])
            assert not u["exact_same_run_cold_alias"]
            assert raw["transport_error"] is None and len(raw["calls"]) == 1
            wire, server = (raw["calls"][0][k] for k in ("request", "response"))
            r = raw["response"]
            assert u["response"] == r
            assert p["arm"] == raw["arm"] == u["condition"]
            assert raw["document_id"] == p["document_id"] == u["document_id"]
            assert wire["messages"] == p["messages"]
            assert wire["response_format"]["json_schema"]["schema"] == p["schema"]
            assert all(wire[k] == self.cfg["generation"][k] for k in ("model", "seed", "temperature", "top_p", "top_k", "max_tokens"))
            assert r["raw_id"] == server["id"] and server["id"] not in ids
            ids.add(server["id"])
            assert server["model"] == self.cfg["generation"]["model"]
            assert r["content"] == server["choices"][0]["message"]["content"]
            assert r["finish_reason"] == server["choices"][0]["finish_reason"] == "stop"
            assert server["choices"][0]["message"]["reasoning_content"]
            assert raw["prompt_tokens_server"] == p["prompt_tokens"] == server["usage"]["prompt_tokens"]
            assert p["prompt_tokens"] + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"]
            for k in usage:
                assert r[k] == server["usage"][k]
                usage[k] += r[k]
            values = json.loads(r["content"])
            validate(values, p["schema"])
            original = self.sources[u["document_id"]]
            source = {k: original[k] for k in ("id", "text", "spans")}
            if source["id"] not in self.proposals:
                self.proposals[source["id"]] = evidence_proposals(self.model, source, self.labels)
            proposals = None if u["condition"] == "strong_empty" else self.proposals[source["id"]]
            bank = self.bank(u)
            assert p["bank"] == bank and p["bank_sha256"] == raw["bank_sha256"] == u["bank_sha256"] == csha(bank)
            assert p["fixed_ordinary_model_state"] == (None if proposals is None else self.manifest["state_sha256"])
            encoding = p.get("incremental_read_encoding", "scored_records" if u["condition"] == "scored_records" else "indices")
            messages, schema, trace = source_messages(source, self.labels, self.cfg["bundled_solver_system"], bank, proposals, incremental_encoding=encoding)
            assert (messages, schema, trace) == (p["messages"], p["schema"], p["actual_factual_trace"])
            body = json.loads(messages[1]["content"])
            assert body["full_contract_with_original_span_markers"] == marked_text(source)
            assert "SOURCE_LEADS" not in messages[1]["content"]
            assert all(s["id"] not in json.dumps([messages, schema]) for s in bank)
            assert set(values) == set(self.labels)
            for h in self.labels:
                question = body["hypotheses"][h]
                assert question["original_hypothesis"] == self.labels[h]["hypothesis"]
                for branch in schema["properties"][h]["anyOf"]:
                    assert branch["properties"]["spans"]["items"]["enum"] == list(range(len(source["spans"])))
                assert {c for branch in schema["properties"][h]["anyOf"] for c in branch["properties"]["choice"]["enum"]} == {"Entailment", "Contradiction", "NotMentioned"}
                if not grade:
                    continue
                g, v = original["annotation_sets"][0]["annotations"][h], values[h]
                gold, pred = set(g["spans"]), set(v["spans"])
                nn = g["choice"] != "NotMentioned"
                rows.append({"document_id": source["id"], "hypothesis_id": h, "condition": u["condition"],
                    "Gold_choice": g["choice"], "Gold_spans": g["spans"], **v,
                    "ordinary": [c["original_span_index"] for c in question["fallible_evidence_candidates"]],
                    "program": trace["per_hypothesis_returned_original_indices"][h],
                    "label_correct": v["choice"] == g["choice"], "joint_exact": v["choice"] == g["choice"] and gold == pred,
                    "tp": len(gold & pred) if nn else 0, "fp": len(pred - gold) if nn else 0, "fn": len(gold - pred) if nn else 0})
        return rows, ids, usage

    def inherited(self):
        parent = ROOT / self.cfg["published_prefix_run"]
        early = ROOT / self.saved(parent / "declaration.json")["config"]["prefix_feedback_run"]
        old = [u for u in self.saved(early / "complete32_native_and_original_scores.json")["units"] if u["condition"] == "skills"]
        old += self.saved(parent / "prefix_repair_all_seen_retention.json")["new_units"]
        old += [u for u in self.saved(parent / "b3_before_complete.json")["units"] if u["condition"] == "skills"]
        selected = [u for u in self.saved(ROOT / self.cfg["prefix_actor_reference_run"] / "complete_native_and_original_scores.json")["units"] if u["condition"] == "scored_records"]
        assert len(old) == 40 and len(selected) == 24
        assert [u["document_id"] for u in selected] == self.cfg["training_ids"][:24]
        return old + selected, selected

    def teacher(self):
        pub = self.saved(OUT / "publications/b4.json")
        folder = OUT / "teacher/update_b4"
        wire, response = self.saved(folder / "wire_request.json"), self.saved(folder / "response.json")
        encoded = self.saved(OUT / "learning_inputs/update_b4.json")
        assert wire["system_prompt"] == TEACHER + CONTRAST_TEACHER_NOTE
        assert json.loads(wire["user_prompt"]) == encoded
        assert encoded["encoding"] == "readable-lossless-acquisition-tables-v1"
        body = expand(encoded["body"])
        assert csha(wire) == response["request_sha256"] and response["value"] == pub["delta"]
        assert wire["model"] == response["model"] == self.cfg["teacher"]["model"]
        assert wire["reasoning_effort"] == self.cfg["teacher"]["reasoning_effort"]
        assert not response["cache_hit"] and not response["invocation"]["tool_events_detected"]
        assert response["invocation"]["attempt"] == 1 and response["invocation"]["returncode"] == 0
        own, _ = self.inherited()
        own += self.saved(OUT / "published_prefix_actual_retention.json")["new_units"]
        own += [u for u in self.saved(OUT / "b4_before_complete.json")["units"] if u["condition"] == "skills"]
        assert len(own) == len(body["actual_own_public_observations"]) == 96
        self.units(own)
        assert body["public_hypotheses"] == self.labels and body["current_parent_library"] == pub["parent"] == self.r2["publication"]
        seen = body["complete_cumulative_original_TRAIN_sources_and_Gold"]
        assert [r["id"] for r in seen] == self.cfg["training_ids"]
        for r in seen:
            original = self.sources[r["id"]]
            assert all(r[k] == original[k] for k in ("id", "text", "spans"))
            assert r["original_annotations"] == original["annotation_sets"][0]["annotations"]
        expected_index = {h: {c: [r["id"] for r in seen if r["original_annotations"][h]["choice"] == c]
            for c in ("Entailment", "Contradiction", "NotMentioned")} for h in self.labels}
        assert encoded["cross_source_relation_index"] == expected_index
        actual = {u["response"]["raw_id"]: u for u in own}
        assert len(actual) == 96
        latest = {}
        for o in body["actual_own_public_observations"]:
            u = actual[o["actual_native_raw_id"]]
            p = self.saved(u["payload"])
            assert o["document_id"] == u["document_id"] and o["actual_stage"] == u["stage"]
            assert o["actual_public_answer"] == json.loads(u["response"]["content"])
            assert o["actual_bank_sha256"] == u["bank_sha256"] == csha(p["bank"])
            assert o["actual_native_artifact_sha256"] == sha(u["raw_artifact"])
            assert o["actual_input_payload_sha256"] == sha(u["payload"])
            expected_encoding = p.get("incremental_read_encoding", p["arm"] if p["arm"] == "scored_records" else "indices")
            assert o["actual_incremental_read_encoding"] == expected_encoding
            assert body["observed_libraries"][o["actual_bank_sha256"]] == p["bank"]
            assert body["actual_source_execution_catalogue"][o["actual_source_execution_ref"]] == p["actual_factual_trace"]["actual_source_executions"]
            if o["actual_bank_sha256"] == csha(pub["parent"]):
                latest[o["document_id"]] = (o, p)
        assert set(latest) == set(self.cfg["training_ids"])
        for d, (o, p) in latest.items():
            source = {k: self.sources[d][k] for k in ("id", "text", "spans")}
            executions = execute_library(source, pub["parent"])
            assert body["actual_source_execution_catalogue"][body["current_parent_source_replay_refs_not_new_native_responses"][str(d)]] == executions
            assert body["current_parent_actual_native_raw_ids"][str(d)] == o["actual_native_raw_id"]
            actor = json.loads(p["messages"][1]["content"])
            for h, annotation in self.sources[d]["annotation_sets"][0]["annotations"].items():
                q = actor["hypotheses"][h]
                assert body["actual_visible_incremental_reads_by_source"][str(d)][h] == q["additional_source_read_indices"]
                assert body["actual_visible_ordinary_candidates_by_source"][str(d)][h] == q["fallible_evidence_candidates"]
                roles = {role: {i for s in pub["parent"] if h in s["hypothesis_ids"] for e in executions[s["id"]] for i in e[role]} for role in ("matched", "neighbour", "preamble")}
                ordinary = [c["original_span_index"] for c in q["fallible_evidence_candidates"]]
                assert body["current_parent_native_member_feedback"][str(d)][h] == native_member_feedback(annotation, o["actual_public_answer"][h], ordinary, roles)
        history = body["published_edit_history_not_individual_edit_effects"]
        assert len(history) == len(self.cfg["historical_publications"]) == 2
        for item, path in zip(history, self.cfg["historical_publications"], strict=True):
            event = self.saved(ROOT / path)
            assert item["actual_publication_sha256"] == sha(ROOT / path)
            assert item["actual_delta"] == event["delta"]
            assert item["parent_bank_sha256"] == csha(event["parent"])
            assert item["published_bank_sha256"] == csha(event["publication"])
        replay = apply_differential_publication(pub["parent"], response["value"], self.labels, self.cfg["training_ids"], guidance_schema=GUIDANCE_SCHEMA)
        assert replay == pub["publication"] and max(pub["capacity"].values()) <= 4096
        return {"all32_original_sources_and_Gold": True, "actual_cumulative_own_observations": 96,
            "all32_have_real_current_parent_feedback_scores_and_relation_index": True,
            "actual_teacher_invocation": response["invocation"], "statistics": pub["statistics"],
            "published_bank_sha256": csha(replay), "capacity": pub["capacity"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prefix", "before", "teacher", "retention"))
    args = parser.parse_args()
    audit = Audit()
    ids = audit.cfg["training_ids"]
    if args.phase == "teacher":
        report = audit.teacher()
    elif args.phase == "before":
        units = audit.saved(OUT / "b4_before_complete.json")["units"]
        assert len(units) == 24 and {u["document_id"] for u in units} == set(ids[24:])
        rows, raw_ids, usage = audit.units(units)
        groups = {a: [r for r in rows if r["condition"] == a] for a in ("strong_empty", "ordinary", "skills")}
        report = {"actual_new_source_contracts": 8, "actual_unique_native_calls": len(raw_ids),
            "results": {a: counts(v) for a, v in groups.items()},
            "skill_minus_ordinary": contrast(groups["ordinary"], groups["skills"]),
            "conditional_source_intervals": resample(groups["ordinary"], groups["skills"], ids[24:]),
            "actual_new_native_usage": usage, "rows": rows}
    else:
        if args.phase == "prefix":
            data = audit.saved(OUT / "published_prefix_actual_retention.json")
            units, reference = data["new_units"], data["matched_R1_same_encoding_reference_units"]
            assert len(units) == len(reference) == 24
            assert [u["document_id"] for u in units] == [u["document_id"] for u in reference] == ids[:24]
        else:
            units = audit.saved(OUT / "b4_all_seen_retention.json")["units"]
            reference = audit.saved(OUT / "published_prefix_actual_retention.json")["new_units"]
            reference += [u for u in audit.saved(OUT / "b4_before_complete.json")["units"] if u["condition"] == "skills"]
            assert len(units) == len(reference) == 32
            assert [u["document_id"] for u in units] == [u["document_id"] for u in reference] == ids
        rows, raw_ids, usage = audit.units(units)
        old, old_ids, old_usage = audit.units(reference)
        assert raw_ids.isdisjoint(old_ids)
        report = {"actual_unique_native_calls": len(raw_ids), "historical_reference_calls_not_new": len(old_ids),
            "before": counts(old), "after": counts(rows), "paired_changes": contrast(old, rows),
            "conditional_source_intervals": resample(old, rows, ids[:len(units)]),
            "by_original_source_group": {str(b + 1): {"before": counts([r for r in old if r["document_id"] in ids[8*b:8*(b+1)]]),
                "after": counts([r for r in rows if r["document_id"] in ids[8*b:8*(b+1)]])} for b in range(len(units) // 8)},
            "actual_new_native_usage": usage, "historical_reference_usage_not_new_spend": old_usage,
            "rows": rows, "reference_rows": old, "seen_retention_not_new_case_transfer": True}
    report.update(at=now(), phase=args.phase, all_phase_original_author_and_actual_wires_checked=True,
        not_independent_learning_or_official_TEST=True, bindings=audit.bindings)
    target = OUT / f"monitoring/{args.phase}_complete_original_author_wire_and_teacher_audit.json"
    RunStore.immutable_json(target, report)
    print(json.dumps({"audit": str(target), "phase": args.phase, "bindings": len(audit.bindings)}))


if __name__ == "__main__":
    main()
