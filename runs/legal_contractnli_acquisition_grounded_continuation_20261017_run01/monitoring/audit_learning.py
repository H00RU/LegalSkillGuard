"""Complete-phase author/wire/lineage audit; never score partial generations.

Run-local evidence analysis, not an inference component or a semantic judge.
"""

# ruff: noqa: E402 -- Explicit authoritative run identity before project imports.
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
    GUIDANCE_SCHEMA,
    TEACHER,
    execute_library,
    native_member_feedback,
    source_messages,
)
from legal_skill_guard.learning.evidence_programs import evidence_proposals
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.learning.publication import apply_differential_publication
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

UTIL_PATH = ROOT / "runs/legal_contractnli_executable_acquisition_online_20261017_run01/monitoring/audit_batch.py"
# Reuse ONLY the old verifier's pure member arithmetic, not its old-tag compiler.
UTIL = runpy.run_path(str(UTIL_PATH))
counts, contrast = UTIL["counts"], UTIL["contrast"]
CFG_PATH = ROOT / "configs/contractnli_acquisition_grounded_continuation.json"
warnings.filterwarnings("ignore", message="X does not have valid feature names, but LGBMClassifier was fitted with feature names")


class Audit:
    def __init__(self):
        self.cfg = read(CFG_PATH)
        frozen = read(CFG_PATH.with_suffix(".frozen.json"))
        assert all(sha(p) == d for p, d in frozen["files"].items())
        assert sha(ROOT / self.cfg["source_archive"]) == self.cfg["source_archive_sha256"]
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            self.author = json.loads(archive.read("contract-nli/train.json"))
        self.sources = {r["id"]: r for r in self.author["documents"]}
        self.labels = self.author["labels"]
        self.manifest = read(ROOT / self.cfg["ordinary_manifest"])
        assert sha(self.manifest["path"]) == self.manifest["pickle_sha256"]
        with Path(self.manifest["path"]).open("rb") as stream:
            self.model = pickle.load(stream)
        assert not self.model.queries and not self.model.programs
        self.proposals = {}
        self.bindings = {**frozen["files"], str(CFG_PATH.with_suffix(".frozen.json")): sha(CFG_PATH.with_suffix(".frozen.json"))}
        self.bindings.update({str(p): sha(p) for p in (UTIL_PATH, Path(__file__).resolve())})

    def saved(self, path):
        path = Path(path)
        self.bindings[str(path)] = sha(path)
        return read(path)

    def expected_bank(self, unit):
        if unit["condition"] != "skills":
            return []
        stage = unit["stage"]
        if stage == "held_K2_interface":
            path = ROOT / self.cfg["initial_bank_publication"]
        else:
            assert stage == "prefix_after_repair" or stage in {
                f"b{b}_{phase}" for b in (3, 4) for phase in ("before", "after_all_seen")}
            b = 2 if stage == "prefix_after_repair" else int(stage[1]) - int(stage.endswith("before"))
            path = OUT / f"publications/b{b}.json"
        return self.saved(path)["publication"]

    def units(self, units):
        rows, raw_ids = [], set()
        usage = {k: 0 for k in ("prompt_tokens", "completion_tokens")}
        for u in units:
            p, raw = self.saved(u["payload"]), self.saved(u["raw_artifact"])
            assert raw["transport_error"] is None and len(raw["calls"]) == 1
            wire, server = (raw["calls"][0][k] for k in ("request", "response"))
            response = raw["response"]
            assert u["response"] == response
            assert wire["messages"] == p["messages"]
            assert wire["response_format"]["json_schema"]["schema"] == p["schema"]
            assert all(wire[k] == self.cfg["generation"][k] for k in (
                "model", "seed", "temperature", "top_p", "top_k", "max_tokens"))
            assert response["raw_id"] == server["id"] and server["id"] not in raw_ids
            assert server["model"] == self.cfg["generation"]["model"]
            assert response["content"] == server["choices"][0]["message"]["content"]
            assert response["finish_reason"] == server["choices"][0]["finish_reason"] == "stop"
            assert server["choices"][0]["message"]["reasoning_content"]
            raw_ids.add(server["id"])
            for k in usage:
                assert response[k] == server["usage"][k]
                usage[k] += server["usage"][k]
            values = json.loads(response["content"])
            validate(values, p["schema"])
            original = self.sources[u["document_id"]]
            source = {k: original[k] for k in ("id", "text", "spans")}
            if source["id"] not in self.proposals:
                self.proposals[source["id"]] = evidence_proposals(self.model, source, self.labels)
            proposals = None if u["condition"] == "strong_empty" else self.proposals[source["id"]]
            bank = self.expected_bank(u)
            assert p["bank"] == bank and p["bank_sha256"] == u["bank_sha256"] == csha(bank)
            assert p["fixed_ordinary_model_state"] == (None if proposals is None else self.manifest["state_sha256"])
            messages, schema, trace = source_messages(source, self.labels,
                self.cfg["bundled_solver_system"], bank, proposals)
            assert (messages, schema, trace) == (p["messages"], p["schema"], p["actual_factual_trace"])
            body = json.loads(messages[1]["content"])
            assert body["full_contract_with_original_span_markers"] == marked_text(source)
            assert "SOURCE_LEADS" not in messages[1]["content"]
            assert all(s["id"] not in json.dumps([messages, schema]) for s in bank)
            assert set(values) == set(self.labels)
            for h, g in original["annotation_sets"][0]["annotations"].items():
                value, question = values[h], body["hypotheses"][h]
                assert set(value) == {"choice", "spans", "reason"}
                assert question["original_hypothesis"] == self.labels[h]["hypothesis"]
                for branch in schema["properties"][h]["anyOf"]:
                    assert branch["properties"]["spans"]["items"]["enum"] == list(range(len(source["spans"])))
                assert {c for branch in schema["properties"][h]["anyOf"] for c in branch["properties"]["choice"]["enum"]} == {"Entailment", "Contradiction", "NotMentioned"}
                ordinary = [v["original_span_index"] for v in question["fallible_evidence_candidates"]]
                returned = trace["per_hypothesis_returned_original_indices"][h]
                assert question["additional_source_read_indices"] == sorted(set(returned) - set(ordinary))
                gold, pred = set(g["spans"]), set(value["spans"])
                nn = g["choice"] != "NotMentioned"
                rows.append({"document_id": source["id"], "hypothesis_id": h,
                    "condition": u["condition"], "Gold_choice": g["choice"], "Gold_spans": g["spans"],
                    **value, "ordinary": ordinary, "program": returned,
                    "label_correct": value["choice"] == g["choice"],
                    "joint_exact": value["choice"] == g["choice"] and pred == gold,
                    "tp": len(gold & pred) if nn else 0, "fp": len(pred - gold) if nn else 0,
                    "fn": len(gold - pred) if nn else 0})
        return rows, raw_ids, usage

    def teacher(self, batch):
        pub = self.saved(OUT / f"publications/b{batch}.json")
        folder = OUT / f"teacher/update_b{batch}"
        wire, response = self.saved(folder / "wire_request.json"), self.saved(folder / "response.json")
        body = self.saved(OUT / f"learning_inputs/update_b{batch}.json")
        assert wire["system_prompt"] == TEACHER and json.loads(wire["user_prompt"]) == body
        assert csha(wire) == response["request_sha256"]
        assert response["model"] == wire["model"] == self.cfg["teacher"]["model"]
        assert wire["reasoning_effort"] == self.cfg["teacher"]["reasoning_effort"]
        assert not response["cache_hit"] and not response["invocation"]["tool_events_detected"]
        assert response["invocation"]["attempt"] == 1 and response["invocation"]["returncode"] == 0
        assert response["value"] == pub["delta"]
        parent = ROOT / self.cfg["prefix_feedback_run"]
        own = [u for u in self.saved(parent / "complete32_native_and_original_scores.json")["units"] if u["condition"] == "skills"]
        if batch >= 3:
            own += self.saved(OUT / "prefix_repair_all_seen_retention.json")["new_units"]
        for b in range(3, batch + 1):
            own += [u for u in self.saved(OUT / f"b{b}_before_complete.json")["units"] if u["condition"] == "skills"]
            if b < batch:
                own += self.saved(OUT / f"b{b}_all_seen_retention.json")["units"]
        assert len(own) == len(body["actual_own_public_observations"]) == 4 * batch * (batch + 1) - 8
        expected = self.cfg["training_ids"][:8 * batch]
        assert [r["id"] for r in body["complete_cumulative_original_TRAIN_sources_and_Gold"]] == expected
        assert body["public_hypotheses"] == self.labels and body["current_parent_library"] == pub["parent"]
        for r in body["complete_cumulative_original_TRAIN_sources_and_Gold"]:
            original = self.sources[r["id"]]
            assert all(r[k] == original[k] for k in ("id", "text", "spans"))
            assert r["original_annotations"] == original["annotation_sets"][0]["annotations"]
        by_id = {u["response"]["raw_id"]: u for u in own}
        assert len(by_id) == len(own)
        latest = {}
        for o in body["actual_own_public_observations"]:
            u = by_id[o["actual_native_raw_id"]]
            payload = self.saved(u["payload"])
            assert o["actual_public_answer"] == json.loads(u["response"]["content"])
            assert o["actual_native_artifact_sha256"] == sha(u["raw_artifact"])
            assert o["actual_bank_sha256"] == u["bank_sha256"] == csha(payload["bank"])
            assert body["observed_libraries"][o["actual_bank_sha256"]] == payload["bank"]
            assert body["actual_source_execution_catalogue"][o["actual_source_execution_ref"]] == payload["actual_factual_trace"]["actual_source_executions"]
            if o["actual_bank_sha256"] == csha(pub["parent"]):
                latest[o["document_id"]] = o
        assert set(latest) == set(expected)
        diagnostics = {}
        for d in expected:
            original = self.sources[d]
            source = {k: original[k] for k in ("id", "text", "spans")}
            executions = execute_library(source, pub["parent"])
            ref = body["current_parent_source_replay_refs_not_new_native_responses"][str(d)]
            assert body["actual_source_execution_catalogue"][ref] == executions
            assert body["current_parent_actual_native_raw_ids"][str(d)] == latest[d]["actual_native_raw_id"]
            for h, annotation in original["annotation_sets"][0]["annotations"].items():
                roles = {role: {i for s in pub["parent"] if h in s["hypothesis_ids"] for e in executions[s["id"]] for i in e[role]} for role in ("matched", "neighbour", "preamble")}
                ordinary = [v["original_span_index"] for v in body["actual_visible_ordinary_candidates_by_source"][str(d)][h]]
                feedback = native_member_feedback(annotation, latest[d]["actual_public_answer"][h], ordinary, roles)
                assert body["current_parent_native_member_feedback"][str(d)][h] == feedback
                diagnostics.setdefault(str(d), {})[h] = feedback
        replay = apply_differential_publication(pub["parent"], response["value"], self.labels, expected, guidance_schema=GUIDANCE_SCHEMA)
        assert replay == pub["publication"] and max(pub["capacity"].values()) <= 4096
        return {"phase": "teacher", "batch": batch, "all_sources": expected,
            "actual_cumulative_own_observations": len(own),
            "all_sources_have_latest_actual_same_parent_feedback_and_exact_member_diagnostics": True,
            "actual_invocation": response["invocation"], "statistics": pub["statistics"],
            "capacity": pub["capacity"], "published_bank_sha256": csha(replay)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prefix", "before", "retention", "teacher"))
    parser.add_argument("batch", type=int, choices=(2, 3, 4))
    args = parser.parse_args()
    assert args.phase == "teacher" or (args.phase == "prefix") == (args.batch == 2)
    complete_path = OUT / ("prefix_repair_all_seen_retention.json" if args.phase == "prefix" else
        f"publications/b{args.batch}.json" if args.phase == "teacher" else
        f"b{args.batch}_before_complete.json" if args.phase == "before" else f"b{args.batch}_all_seen_retention.json")
    assert complete_path.is_file(), "Whole phase must finish; no partial quality scoring"
    destination = OUT / f"monitoring/{args.phase}_b{args.batch}_complete_original_author_wire_and_parent_audit.json"
    assert not destination.exists(), "Read the existing immutable audit, do not overwrite"
    audit = Audit()
    data = audit.saved(complete_path)
    if args.phase == "teacher":
        report = audit.teacher(args.batch)
    else:
        units = data["new_units"] if args.phase == "prefix" else data["units"]
        expected = 16 if args.phase == "prefix" else 24 if args.phase == "before" else 8 * args.batch
        assert len(units) == expected
        rows, ids, usage = audit.units(units)
        assert len(ids) == expected
        arms = sorted({r["condition"] for r in rows})
        report = {"phase": args.phase, "batch": args.batch, "actual_new_native_responses": len(ids),
            "metrics": {a: counts([r for r in rows if r["condition"] == a]) for a in arms},
            "actual_new_native_usage": usage, "all_original_query_records": rows}
        if args.phase == "before":
            report["paired"] = {a: contrast([r for r in rows if r["condition"] == a], [r for r in rows if r["condition"] == "skills"]) for a in ("ordinary", "strong_empty")}
        else:
            if args.phase == "prefix":
                reference = data["inherited_actual_own_reference"]
            else:
                previous = audit.saved(OUT / ("prefix_repair_all_seen_retention.json" if args.batch == 3 else "b3_all_seen_retention.json"))
                reference = previous["new_units" if args.batch == 3 else "units"]
                reference += [u for u in audit.saved(OUT / f"b{args.batch}_before_complete.json")["units"] if u["condition"] == "skills"]
            parent_hash = csha(audit.saved(OUT / f"publications/b{args.batch}.json")["parent"])
            assert all(u["bank_sha256"] == parent_hash for u in reference)
            before, _, _ = audit.units(reference)
            report["same_parent_actual_reference_metrics"] = counts(before)
            report["paired_update_effect"] = contrast(before, rows)
            report["by_original_source_group"] = {str(b): {
                "before": counts([r for r in before if r["document_id"] in audit.cfg["training_ids"][(b - 1) * 8:b * 8]]),
                "after": counts([r for r in rows if r["document_id"] in audit.cfg["training_ids"][(b - 1) * 8:b * 8]])}
                for b in range(1, args.batch + 1)}
            if args.phase == "prefix":
                parent = ROOT / audit.cfg["prefix_feedback_run"]
                controls = [u for u in audit.saved(parent / "complete32_native_and_original_scores.json")["units"] if u["condition"] == "ordinary"]
                ordinary, _, _ = audit.units(controls)
                report["same_ABI_saved_ordinary_not_new_calls"] = counts(ordinary)
                report["versus_saved_ordinary"] = contrast(ordinary, rows)
    report.update(at=now(), run_id=OUT.name, bindings=audit.bindings,
        original_author_and_actual_wire_audit_not_a_semantic_judge=True,
        not_proof_of_independent_learning_significance_or_official_TEST=True)
    RunStore.immutable_json(destination, report)
    print(json.dumps({k: v for k, v in report.items() if k not in (
        "bindings", "all_original_query_records", "by_original_source_group")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
