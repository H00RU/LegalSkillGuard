"""Independently count the complete12 experiment from native bits and author Gold.

Never grade an incomplete phase, use a model judge or change an answer.
"""

# ruff: noqa: E402 -- Bind the actual project and research folder before imports.
from __future__ import annotations

import hashlib
import json
import runpy
import sys
import tarfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from jsonschema import ValidationError, validate
from native_membership import compile_membership

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, sha
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

PARENT = ROOT / "runs/legal_contractnli_published_acquisition_continuation_20261017_run01"
BASE = runpy.run_path(str(PARENT / "monitoring/audit_learning.py"))
counts, contrast = BASE["counts"], BASE["contrast"]


def evidence_change(before, after):
    paired = {(r["document_id"], r["hypothesis_id"]): r for r in before}
    result = Counter()
    for r in after:
        old = paired[(r["document_id"], r["hypothesis_id"])]
        if r["Gold_choice"] == "NotMentioned":
            continue
        gold, previous, current = (set(v) for v in (r["Gold_spans"], old["spans"], r["spans"]))
        result["false_citations_added"] += len((current - gold) - previous)
        result["false_citations_removed"] += len((previous - gold) - current)
    return {**contrast(before, after), **dict(result)}


def main():
    a = BASE["Audit"]()
    cfg = a.saved(HERE / "config.json")
    frozen = a.saved(HERE / "config.frozen.json")
    assert sha(HERE / "config.json") == frozen["config_sha256"]
    assert all(sha(p) == h for p, h in frozen["files"].items())
    a.bindings.update(frozen["files"])
    a.bindings[str(Path(__file__).resolve())] = sha(Path(__file__))
    out = ROOT / "runs" / cfg["run_id"]
    done = a.saved(out / "completion.json")
    assert done["completed_native_calls"] == 12 and done["completed_teacher_calls"] == 0
    phase = a.saved(out / "phase_backups/fixed_R3.json")
    assert sha(phase["archive"]) == phase["archive_sha256"]
    archived = {}
    with tarfile.open(phase["archive"], "r|gz") as archive:
        manifest = None
        for member in archive:
            stream = archive.extractfile(member)
            if member.name == "phase_manifest.json":
                manifest = json.load(stream)
            else:
                digest = hashlib.sha256()
                while chunk := stream.read(2**20):
                    digest.update(chunk)
                archived[member.name] = digest.hexdigest()
    assert manifest is not None
    assert archived == {"project/" + p: h for p, h in manifest["files"].items()}
    assert all(str(Path(u).resolve().relative_to(ROOT)) in manifest["files"] for u in frozen["files"])
    units = a.saved(out / "complete12_native_and_original_scores.json")["units"]
    assert len(units) == 12
    assert {u["document_id"] for u in units} == set(cfg["diagnostic_source_ids"])
    assert len({(u["condition"], u["document_id"]) for u in units}) == 12
    publication = a.saved(Path(cfg["fixed_bank_publication"]))
    assert sha(cfg["fixed_bank_publication"]) == cfg["fixed_bank_publication_sha256"]
    source_rows = a.saved(ROOT / cfg["input_packet"])
    source_map = {r["id"]: r for r in source_rows["documents"]}
    system = a.saved(ROOT / cfg["solver_system_reference"])["bundled_solver_system"]
    rows, raw_ids, usage, health, field_orders = [], set(), Counter(), [], Counter()
    invalids = 0
    for u in units:
        d, arm = u["document_id"], u["condition"]
        p, raw = a.saved(Path(u["payload"])), a.saved(Path(u["raw_artifact"]))
        assert manifest["files"][str(Path(u["payload"]).resolve().relative_to(ROOT))] == sha(u["payload"])
        assert raw["transport_error"] is None and len(raw["calls"]) == 1
        wire, server = raw["calls"][0]["request"], raw["calls"][0]["response"]
        assert raw["response"] == u["response"]
        assert wire["messages"] == p["messages"]
        assert wire["response_format"]["json_schema"]["schema"] == p["schema"]
        assert server["model"] == wire["model"] == cfg["generation"]["model"]
        assert all(wire[k] == cfg["generation"][k] for k in ("seed", "temperature", "top_p", "top_k", "max_tokens"))
        assert wire.get("chat_template_kwargs", {}).get("enable_thinking", True) is True
        response, message = u["response"], server["choices"][0]["message"]
        assert response["raw_id"] == server["id"] and server["id"] not in raw_ids
        raw_ids.add(server["id"])
        assert response["content"] == message["content"].strip() and message["reasoning_content"]
        assert response["finish_reason"] == server["choices"][0]["finish_reason"]
        assert not u["exact_same_run_cold_alias"] and u["native_content_never_overwritten"]
        for k in ("prompt_tokens", "completion_tokens"):
            assert response[k] == server["usage"][k]
            usage[k] += response[k]
        assert response["prompt_tokens"] == p["prompt_tokens"] == raw["prompt_tokens_server"]
        assert p["prompt_tokens"] + cfg["generation"]["max_tokens"] <= cfg["generation"]["context_tokens"]
        original = a.sources[d]
        source = {k: original[k] for k in ("id", "text", "spans")}
        assert source == source_map[d] and source_rows["public_hypotheses"] == a.labels
        if d not in a.proposals:
            a.proposals[d] = BASE["evidence_proposals"](a.model, source, a.labels)
        bank = publication["publication"] if arm == "skills" else []
        proposals = None if arm == "strong_empty" else a.proposals[d]
        canonical, old_schema, trace = BASE["source_messages"](source, a.labels, system, bank,
            proposals, incremental_encoding="scored_records")
        assert p["canonical_actor_messages_sha256"] == csha(canonical)
        assert p["canonical_actor_schema_sha256"] == csha(old_schema)
        expected_messages, expected_schema, order = compile_membership(canonical, len(source["spans"]))
        assert (p["messages"], p["schema"], p["evidence_check_order"]) == (expected_messages, expected_schema, order)
        assert p["actual_factual_trace"] == trace and p["bank"] == bank
        assert p["bank_sha256"] == raw["bank_sha256"] == u["bank_sha256"] == csha(bank)
        assert p["fixed_ordinary_model_state"] == (None if arm == "strong_empty" else a.manifest["state_sha256"])
        body = json.loads(p["messages"][1]["content"])
        assert body["full_contract_with_original_span_markers"] == marked_text(source)
        native = None
        try:
            if response["finish_reason"] != "stop":
                raise ValueError("Incomplete native output")
            native = json.loads(message["content"])
            validate(native, p["schema"])
        except (ValueError, ValidationError):
            native = None
        valid = native is not None
        invalids += not valid
        assert u["public_valid"] == valid
        projected = {}
        queries = {q["hypothesis_id"]: q for q in u["queries"]}
        assert set(queries) == set(a.labels)
        for h in a.labels:
            hyp = body["hypotheses"][h]
            assert hyp["original_hypothesis"] == a.labels[h]["hypothesis"]
            ordinary = [c["original_span_index"] for c in hyp["fallible_evidence_candidates"]]
            program = trace["per_hypothesis_returned_original_indices"][h]
            checked = sorted(set(ordinary) | set(program))
            assert order[h] == hyp["evidence_check_order"] == checked
            permitted_outside = p["schema"]["properties"][h]["properties"]["other_spans"]
            remaining = sorted(set(range(len(source["spans"]))) - set(checked))
            assert permitted_outside["items"].get("enum", []) == remaining
            if not remaining:
                assert permitted_outside["maxItems"] == 0
            value = native[h] if valid else {"choice": None, "reason": ""}
            if valid:
                field_orders["/".join(value)] += 1
                # Independent transpose: no codec call, score, Gold or label here.
                selected = {checked[j] for j, yes in enumerate(value["evidence_flags"]) if yes}
                selected.update(value["other_spans"])
                projected[h] = {"choice": value["choice"], "spans": sorted(selected), "reason": value["reason"]}
                if (value["choice"] == "NotMentioned") != (not selected):
                    health.append({"source": d, "arm": arm, "hypothesis": h,
                        "choice": value["choice"], "spans": sorted(selected)})
            else:
                selected = set()
            annotation = original["annotation_sets"][0]["annotations"][h]
            gold = set(annotation["spans"])
            nn = annotation["choice"] != "NotMentioned"
            assert bool(gold) == nn
            correct = valid and value["choice"] == annotation["choice"]
            joint = correct and gold == selected
            q = queries[h]
            assert q["gold"] == annotation and q["label_correct"] == correct and q["joint_exact"] == joint
            assert q["evidence_tp"] == len(gold & selected)
            assert q["evidence_fp"] == len(selected - gold)
            assert q["evidence_fn"] == len(gold - selected)
            rows.append({"document_id": d, "hypothesis_id": h, "condition": arm,
                "Gold_choice": annotation["choice"], "Gold_spans": annotation["spans"],
                "choice": value["choice"], "spans": sorted(selected), "reason": value["reason"],
                "ordinary": ordinary, "program": program, "label_correct": correct, "joint_exact": joint,
                "tp": len(gold & selected) if nn else 0, "fp": len(selected - gold) if nn else 0,
                "fn": len(gold - selected) if nn else 0})
        assert u["original_coordinate_view_not_native_response"] == (projected if valid else None)
        assert u["parsed"] == (projected if valid else None)
    by_arm = {arm: [r for r in rows if r["condition"] == arm] for arm in ("strong_empty", "ordinary", "skills")}
    reference = a.saved(Path(cfg["reference_units"]))["units"]
    old, old_ids, old_usage = a.units(reference)
    assert len(old_ids) == 8 and raw_ids.isdisjoint(old_ids)
    original = {arm: [r for r in old if r["condition"] == arm] for arm in ("ordinary", "skills")}
    assert done["invalid_native_answers_included_in_original_denominators"] == invalids
    assert done["native_relation_evidence_inconsistencies_not_repaired"] == health
    for arm in by_arm:
        manual = counts(by_arm[arm])
        assert all(done["results"][arm][k] == v for k, v in manual.items()
            if k in done["results"][arm])
    assert done["actual_native_usage"] == dict(usage)
    report = {"at": now(), "all12_actual_wires_and_original_author_members_checked": True,
        "original_contracts": 4, "actual_unique_native_calls": len(raw_ids), "teacher_calls": 0,
        "original_labels_and_citations_copied_from_native_without_choice_dependent_repair": True,
        "pre_native_phase_archive_independently_verified": phase["archive_sha256"],
        "metrics": {arm: counts(v) for arm, v in by_arm.items()},
        "new_skill_minus_ordinary": evidence_change(by_arm["ordinary"], by_arm["skills"]),
        "new_skill_minus_strong_empty": evidence_change(by_arm["strong_empty"], by_arm["skills"]),
        "actual_conventional_reference_metrics_not_new_calls": {arm: counts(v) for arm, v in original.items()},
        "interface_change_by_arm": {arm: evidence_change(original[arm], by_arm[arm]) for arm in original},
        "by_original_source": {str(d): {arm: counts([r for r in v if r["document_id"] == d])
            for arm, v in by_arm.items()} for d in cfg["diagnostic_source_ids"]},
        "actual_native_usage": dict(usage), "historical_reference_usage_not_new_spend": old_usage,
        "observed_native_field_orders": dict(field_orders), "invalid_native_answers": invalids,
        "relation_evidence_inconsistencies_retained": health, "rows": rows,
        "not_independent_learning_new_case_transfer_significance_or_official_TEST": True,
        "bindings": a.bindings}
    target = out / "monitoring/complete12_original_author_native_bit_and_control_audit.json"
    RunStore.immutable_json(target, report)
    print(json.dumps({"report": str(target), "actual_wires": len(raw_ids), "historical_references": len(old_ids),
        "original_contracts": 4, "bindings": len(a.bindings)}))


if __name__ == "__main__":
    main()
