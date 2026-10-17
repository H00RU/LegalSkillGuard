"""Run-local actual-wire and original-author audit; no inference component.

The wire-only entry never calculates quality. Complete scoring requires all48
new answers and preserves the24+24 historical controls as reused observations.
"""

# ruff: noqa: E402 -- Resolve this authoritative run before project imports.
from __future__ import annotations

import argparse
import copy
import json
import math
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
from legal_skill_guard.learning.acquisition import source_messages
from legal_skill_guard.learning.evidence_programs import evidence_proposals
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

UTIL_PATH = ROOT / "runs/legal_contractnli_executable_acquisition_online_20261017_run01/monitoring/audit_batch.py"
UTIL = runpy.run_path(str(UTIL_PATH))
counts, contrast = UTIL["counts"], UTIL["contrast"]
CFG_PATH = ROOT / "configs/contractnli_read_record_score_mechanism.json"
warnings.filterwarnings("ignore", message="X does not have valid feature names, but LGBMClassifier was fitted with feature names")


class Audit:
    def __init__(self):
        self.cfg = read(CFG_PATH)
        frozen_path = CFG_PATH.with_suffix(".frozen.json")
        frozen = read(frozen_path)
        assert sha(CFG_PATH) == frozen["config_sha256"]
        assert all(sha(p) == digest for p, digest in frozen["files"].items())
        self.bindings = {**frozen["files"], str(frozen_path): sha(frozen_path),
            str(Path(__file__).resolve()): sha(__file__), str(UTIL_PATH): sha(UTIL_PATH)}
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
        self.bank = self.saved(ROOT / self.cfg["fixed_bank_publication"])["publication"]
        assert sha(ROOT / self.cfg["fixed_bank_publication"]) == self.cfg["fixed_bank_publication_sha256"]
        self.ids = self.cfg["diagnostic_source_ids"]
        assert len(self.ids) == len(set(self.ids)) == 24
        assert self.ids == self.cfg["training_ids"][:24]
        parent = ROOT / self.cfg["mechanism_reference_run"]
        old_prefix = self.saved(ROOT / self.cfg["ordinary_prefix_reference_run"] / "complete32_native_and_original_scores.json")["units"]
        old_before = self.saved(parent / "b3_before_complete.json")["units"]
        old_retention = self.saved(parent / "prefix_repair_all_seen_retention.json")["new_units"]
        self.references = {
            "ordinary": [u for u in old_prefix + old_before if u["condition"] == "ordinary"],
            "indices": old_retention + [u for u in old_before if u["condition"] == "skills"],
        }
        assert all([u["document_id"] for u in group] == self.ids for group in self.references.values())
        self.proposals, self.raw_ids, self.costs = {}, set(), {}

    def saved(self, path):
        path = Path(path).resolve()
        self.bindings[str(path)] = sha(path)
        return read(path)

    def new_units(self, ids):
        stage = self.cfg["diagnostic_stage"]
        result = {}
        for arm in self.cfg["diagnostic_arms"]:
            units = []
            for d in ids:
                raw_path = OUT / f"native/{stage}/{arm}/{d}.final.native.json"
                raw = self.saved(raw_path)
                units.append({"stage": stage, "condition": arm, "document_id": d,
                    "payload": str(OUT / f"prospective/{stage}/{arm}/{d}.json"),
                    "raw_artifact": str(raw_path), "bank_sha256": csha(self.bank),
                    "response": raw["response"], "exact_same_run_cold_alias": False})
            result[arm] = units
        return result

    def unit(self, u, condition, *, grade):
        d = u["document_id"]
        p, raw = self.saved(u["payload"]), self.saved(u["raw_artifact"])
        assert p["document_id"] == raw["document_id"] == d
        assert p["arm"] == raw["arm"] == u["condition"]
        assert raw["stage"] == u["stage"] and raw["call_role"] == "final"
        assert raw["input_payload"] == u["payload"]
        assert not u["exact_same_run_cold_alias"]
        assert raw["transport_error"] is None and len(raw["calls"]) == 1
        wire, server = (raw["calls"][0][k] for k in ("request", "response"))
        response = raw["response"]
        assert response == u["response"]
        assert wire["messages"] == p["messages"]
        assert wire["response_format"]["json_schema"]["schema"] == p["schema"]
        assert all(wire[k] == self.cfg["generation"][k] for k in (
            "model", "seed", "temperature", "top_p", "top_k", "max_tokens"))
        assert response["raw_id"] == server["id"] and server["id"] not in self.raw_ids
        self.raw_ids.add(server["id"])
        assert server["model"] == self.cfg["generation"]["model"]
        message = server["choices"][0]["message"]
        assert response["content"] == message["content"]
        assert message["reasoning_content"]
        assert response["finish_reason"] == server["choices"][0]["finish_reason"] == "stop"
        assert raw["prompt_tokens_server"] == p["prompt_tokens"] == server["usage"]["prompt_tokens"]
        assert p["prompt_tokens"] + self.cfg["generation"]["max_tokens"] <= self.cfg["generation"]["context_tokens"]
        costs = self.costs.setdefault(condition, {"prompt_tokens": 0, "completion_tokens": 0})
        for k in costs:
            assert response[k] == server["usage"][k]
            costs[k] += response[k]
        values = json.loads(response["content"])
        validate(values, p["schema"])
        original = self.sources[d]
        source = {k: original[k] for k in ("id", "text", "spans")}
        if d not in self.proposals:
            self.proposals[d] = evidence_proposals(self.model, source, self.labels)
        bank = [] if condition == "ordinary" else self.bank
        assert p["bank"] == bank
        assert p["bank_sha256"] == raw["bank_sha256"] == u["bank_sha256"] == csha(bank)
        assert p["fixed_ordinary_model_state"] == self.manifest["state_sha256"]
        encoding = condition if condition in ("records", "scored_records") else "indices"
        messages, schema, trace = source_messages(source, self.labels,
            self.cfg["bundled_solver_system"], bank, self.proposals[d], incremental_encoding=encoding)
        assert (messages, schema, trace) == (p["messages"], p["schema"], p["actual_factual_trace"])
        body = json.loads(messages[1]["content"])
        assert body["full_contract_with_original_span_markers"] == marked_text(source)
        assert "SOURCE_LEADS" not in messages[1]["content"]
        assert all(s["id"] not in json.dumps([messages, schema]) for s in bank)
        assert set(values) == set(self.labels)
        rows = []
        for h in self.labels:
            question, value = body["hypotheses"][h], values[h]
            assert set(value) == {"choice", "spans", "reason"}
            assert question["original_hypothesis"] == self.labels[h]["hypothesis"]
            for branch in schema["properties"][h]["anyOf"]:
                assert branch["properties"]["spans"]["items"]["enum"] == list(range(len(source["spans"])))
            assert {c for branch in schema["properties"][h]["anyOf"] for c in branch["properties"]["choice"]["enum"]} == {"Entailment", "Contradiction", "NotMentioned"}
            ordinary = [v["original_span_index"] for v in question["fallible_evidence_candidates"]]
            program = trace["per_hypothesis_returned_original_indices"][h]
            incremental = sorted(set(program) - set(ordinary))
            delivered = question["additional_source_read_indices"]
            if encoding == "indices":
                assert delivered == incremental
            else:
                assert [v["original_span_index"] for v in delivered] == incremental
                for v in delivered:
                    assert set(v) == ({"original_span_index", "membership_score"} if encoding == "scored_records" else {"original_span_index"})
                    if encoding == "scored_records":
                        score = float(self.proposals[d]["by_hypothesis"][h]["raw_scores"][v["original_span_index"]])
                        assert v["membership_score"] == score <= 0.5
            if not grade:
                continue
            g = original["annotation_sets"][0]["annotations"][h]
            gold, pred = set(g["spans"]), set(value["spans"])
            nn = g["choice"] != "NotMentioned"
            row = {"document_id": d, "hypothesis_id": h, "condition": condition,
                "Gold_choice": g["choice"], "Gold_spans": g["spans"], **value,
                "ordinary": ordinary, "program": program, "incremental": incremental,
                "label_correct": value["choice"] == g["choice"],
                "joint_exact": value["choice"] == g["choice"] and pred == gold,
                "tp": len(gold & pred) if nn else 0, "fp": len(pred - gold) if nn else 0,
                "fn": len(gold - pred) if nn else 0}
            if "queries" in u:
                q = next(q for q in u["queries"] if q["hypothesis_id"] == h)
                assert q["gold"] == g and q["prediction"] == value
                assert q["label_correct"] == row["label_correct"] and q["joint_exact"] == row["joint_exact"]
                assert q["evidence_tp"] == len(gold & pred)
                assert q["evidence_fp"] == len(pred - gold) and q["evidence_fn"] == len(gold - pred)
            rows.append(row)
        return p, rows

    def pair_fields(self, records, scored):
        assert records["schema"] == scored["schema"]
        assert records["actual_factual_trace"] == scored["actual_factual_trace"]
        assert records["messages"][0] == scored["messages"][0]
        a, b = (json.loads(p["messages"][1]["content"]) for p in (records, scored))
        b = copy.deepcopy(b)
        for h in self.labels:
            for entry in b["hypotheses"][h]["additional_source_read_indices"]:
                entry.pop("membership_score")
        assert a == b, "Only existing per-position scores may differ between new arms"


def summarize(rows):
    result = counts(rows)
    nn = [r for r in rows if r["Gold_choice"] != "NotMentioned"]
    result.update({
        "nonGold_incremental_final_citations_NN": sum(len((set(r["spans"]) - set(r["Gold_spans"])) & set(r["incremental"])) for r in nn),
        "exact_copies_of_nonempty_incremental_pool_NN": sum(bool(r["incremental"]) and set(r["spans"]) == set(r["incremental"]) for r in nn),
        "Gold_visible_in_ordinary_or_program_but_omitted_NN": sum(len((set(r["Gold_spans"]) & (set(r["ordinary"]) | set(r["program"]))) - set(r["spans"])) for r in nn),
    })
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wire-only", action="store_true")
    args = parser.parse_args()
    audit = Audit()
    if args.wire_only:
        units = audit.new_units([audit.ids[0]])
        payloads = {a: audit.unit(group[0], a, grade=False)[0] for a, group in units.items()}
        audit.pair_fields(payloads["records"], payloads["scored_records"])
        report = {"at": now(), "document_id": audit.ids[0], "actual_distinct_new_native_responses": 2,
            "actual_wire_matches_frozen_payload_and_same_original_source": True,
            "only_existing_membership_score_differs_between_new_arms": True,
            "same_fixed_bank_M2_schema_system_generation_and_all_read_locations": True,
            "no_quality_computed_no_teacher_or_new_generation": True,
            "actual_usage_not_additional_spend": audit.costs, "bindings": audit.bindings}
        target = OUT / "monitoring/first_actual_pair_wire_and_existing_score_audit.json"
    else:
        complete = audit.saved(OUT / "completion.json")
        assert complete["completed_native_calls"] == 48 and complete["completed_teacher_calls"] == 0
        assert complete["unique_source_contracts"] == 24
        scored_units = audit.saved(OUT / "complete_native_and_original_scores.json")["units"]
        assert len(scored_units) == 48
        new = audit.new_units(audit.ids)
        for arm, group in new.items():
            actual = [u for u in scored_units if u["condition"] == arm]
            assert [{k: u[k] for k in group[0]} for u in actual] == group
        rows, payloads = {}, {}
        for condition, group in {**audit.references, **new}.items():
            rows[condition], payloads[condition] = [], {}
            for u in group:
                p, scored = audit.unit(u, condition, grade=True)
                payloads[condition][u["document_id"]] = p
                rows[condition].extend(scored)
        assert len(audit.raw_ids) == 96
        for d in audit.ids:
            audit.pair_fields(payloads["records"][d], payloads["scored_records"][d])
        new_usage = {k: sum(audit.costs[a][k] for a in new) for k in ("prompt_tokens", "completion_tokens")}
        assert new_usage == complete["actual_native_usage"]
        groups = {"all24": audit.ids, "R1_seen16": audit.ids[:16], "previously_observed_next8": audit.ids[16:]}
        groups.update({f"original_group{b + 1}": audit.ids[b * 8:(b + 1) * 8] for b in range(3)})
        results = {}
        for name, ids in groups.items():
            selected = {a: [r for r in rr if r["document_id"] in ids] for a, rr in rows.items()}
            results[name] = {"source_ids": ids, "results": {a: summarize(rr) for a, rr in selected.items()},
                "paired_changes": {f"{a}_minus_{b}": contrast(selected[b], selected[a])
                    for a, b in (("indices", "ordinary"), ("records", "ordinary"), ("scored_records", "ordinary"),
                        ("records", "indices"), ("scored_records", "indices"), ("scored_records", "records"))}}
        for arm in new:
            independent = results["all24"]["results"][arm]
            for key in ("label_accuracy", "evidence_micro_f1_gold_non_neutral", "joint_exact_accuracy"):
                assert math.isclose(independent[key], complete["fixed_seen_interface_results"][arm][key], abs_tol=1e-12)
        report = {"at": now(), "all48_new_and48_historical_wires_and_original_author_sets_recomputed": True,
            "new_native_calls": 48, "new_teacher_calls": 0, "reused_historical_native_calls_not_new_or_independent": 48,
            "unique_source_clusters": 24, "fixed_R1_sha256": csha(audit.bank), "results": results,
            "new_native_usage": new_usage,
            "reused_historical_usage_not_new_spend": {a: audit.costs[a] for a in audit.references},
            "not_online_evolution_unseen_confirmation_official_TEST_or_mature_method_victory": True,
            "rows": rows, "bindings": audit.bindings}
        target = OUT / "monitoring/complete48_original_author_wires_and_fixed24_mechanism_audit.json"
    RunStore.immutable_json(target, report)
    print(json.dumps({"audit": str(target), "wire_only": args.wire_only,
        "distinct_native_responses_checked": len(audit.raw_ids), "bindings": len(audit.bindings)}))


if __name__ == "__main__":
    main()
