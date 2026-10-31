"""Audit the stopped66-call study without inventing its missing endpoint."""

# ruff: noqa: E402 -- Run-local analysis resolves the project root.
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.learning.literal_evidence import LITERAL_TEACHER_NOTICE, literal_feedback_view
from legal_skill_guard.learning.skill_tables import COLUMNS, scoped_budget_view
from legal_skill_guard.learning.task_local import LOCAL_TEACHER_SYSTEM, bounded_teacher_packet, task_skill_projection
from legal_skill_guard.learning.witness_grounding import WITNESS_NOTICE, publish_with_training_witnesses, witness_publication_schema
from legal_skill_guard.task import render_library
from legal_skill_guard.utils.hashing import canonical_json_sha256


def audit():
    cfg_path = ROOT / "configs/contractnli_witness_table.json"
    cfg, frozen = read(cfg_path), read(cfg_path.with_suffix(".frozen.json"))
    assert frozen["config_sha256"] == sha(cfg_path)
    assert all(sha(p) == digest for p, digest in frozen["files"].items())
    terminal, launch = read(OUT / "progress.json"), read(OUT / "launch.json")
    assert not (Path("/proc") / str(launch["pid"])).exists()
    assert terminal["state"] == "stopped"
    assert (terminal["completed_native_calls"], terminal["completed_teacher_calls"], terminal["teacher_attempts"]) == (66, 3, 3)
    assert not (OUT / "batch3_summary.json").exists() and not (OUT / "completion.json").exists()
    assert not list(OUT.glob("later/*/*.public.json"))
    receipts = [OUT / "monitoring" / name for name in (
        "complete_B1_independent_original_author_and_matched_error_audit.json",
        "complete_B2_independent_original_author_and_matched_error_audit.json",
        "complete_B3_before_original_candidate_coverage_audit.json",
    )]
    files = {**frozen["files"], str(cfg_path): sha(cfg_path), str(Path(__file__)): sha(__file__)}
    for p in receipts:
        receipt = read(p)
        assert all(sha(q) == digest for q, digest in receipt["audited_file_sha256"].items())
        files[str(p)] = sha(p)
    packet = read(ROOT / cfg["input_packet"])
    labels, training = packet["public_hypotheses"], packet["training"]
    tx_path = OUT / "update_transactions/b3.json"
    tx, parent = read(tx_path), read(OUT / "update_transactions/b2.json")["publication"]
    assert tx["actual_parent"] == parent
    rows = [r for r in training if r["batch"] in (2, 3)]
    before, after = {}, {}
    for row in rows:
        stage = "batch3_before" if row["batch"] == 3 else "batch2_after"
        path = OUT / stage / "skill_memory" / f"{row['id']}.public.json"
        unit = read(path)
        (before if row["batch"] == 3 else after)[row["id"]] = unit
        files.update({str(path): sha(path), unit["raw_artifact"]: sha(unit["raw_artifact"])})
    state = next(iter(before.values()))["actual_factual_trace"]["ordinary_model_state"]
    meter = WireClient(cfg["generation"])
    master = meter.token_count(text=render_library(parent))
    scoped = meter.token_count(text=json.dumps(scoped_budget_view(task_skill_projection(parent, labels)), ensure_ascii=False, separators=(",", ":")))
    body = literal_feedback_view(bounded_teacher_packet(training, 3, labels, parent, state, before, after, master_tokens=master, cap=cfg["library_token_hard_cap"]), rows)
    body["serialized_parent_scoped_delivery_tokens"] = scoped
    body["lawyer_skill_delivery_encoding"] = {
        "format": "scoped_lossless_table_v1", "columns": list(COLUMNS),
        "same_public_scope_and_words_no_semantic_filter_or_verdict": True,
        "semantic_projection_in_observations_is_losslessly_decoded_not_wire_object_spelling": True,
        "training_witness_metadata_never_enters_runtime_table_or_its_token_budget": True,
    }
    teacher_dir = OUT / "teacher/task_local_b3"
    wire, response, events = (read(teacher_dir / name) for name in ("wire_request.json", "response.json", "event_log.json"))
    assert wire["system_prompt"] == LOCAL_TEACHER_SYSTEM + LITERAL_TEACHER_NOTICE + WITNESS_NOTICE
    assert wire["user_prompt"] == json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    assert wire["output_schema"] == witness_publication_schema(labels, parent, rows)
    assert canonical_json_sha256(wire) == response["request_sha256"]
    assert response["value"] == tx["actual_teacher_value"]
    assert canonical_json_sha256(response["value"]) == response["response_sha256"]
    inv = response["invocation"]
    assert not response["cache_hit"] and response["model"] == cfg["teacher"]["model"]
    assert inv["attempt"] == 1 and inv["returncode"] == 0 and not inv["tool_events_detected"]
    assert canonical_json_sha256({"event_log": events["event_log"]}) == inv["event_log_sha256"]
    messages = []
    for line in events["event_log"].splitlines():
        event = json.loads(line)
        item = event.get("item", {})
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            messages.append(json.loads(item["text"]))
    assert messages == [response["value"]]
    published, projected, claims = publish_with_training_witnesses(parent, response["value"], labels, rows)
    assert published == tx["publication"] == parent
    assert projected == tx["publication_input_without_training_only_witness_metadata"]
    assert claims == tx["teacher_witness_claim_audit_not_admission"]
    assert response["value"]["operations"] == [] and response["value"]["noop_reason"]
    natives = [read(p) for p in OUT.glob("batch*_*/*/*.final.native.json")]
    assert len(natives) == len({v["response"]["raw_id"] for v in natives}) == 66
    teachers = [read(OUT / f"teacher/task_local_b{b}/response.json") for b in (1, 2, 3)]
    files.update({str(p): sha(p) for p in (tx_path, OUT / "failure.json", OUT / "operator_stop_request.json")})
    files.update({str(p): sha(p) for p in teacher_dir.glob("*.json")})
    result = {
        "at": now(), "run_id": OUT.name, "actual_terminal_state": terminal,
        "all68_frozen_inputs_unchanged": True,
        "complete_B1_B2_and_complete_B3_before_receipts_revalidated": True,
        "M3_full_same_parent12_source_feedback_rebuilt_byte_identically": True,
        "M3_real_teacher_event_value_schema_and_atomic_publication_replayed": True,
        "M3_NOOP_reason": response["value"]["noop_reason"],
        "M3_accounts_not_proof_of_runtime_evidence_acquisition": claims["original_Gold_members_explicitly_accounted_once_not_proven_retrieved"],
        "actual_new_native_calls": 66, "actual_new_main_teacher_responses_and_attempts": [3, 3],
        "historical_fixed_public_static_teacher_artifacts": 1,
        "native_usage": {k: sum(n["response"][k] for n in natives) for k in ("prompt_tokens", "completion_tokens")},
        "new_main_teacher_usage": {k: sum(t["invocation"]["usage"][k] for t in teachers) for k in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")},
        "missing_B3_after_B4_retention_and_endpoint_not_imputed_or_scored": True,
        "whole_trial_stop_not_skill_admission_rollback_or_goal_pause": True,
        "audited_file_sha256": files,
    }
    RunStore.immutable_json(OUT / "monitoring/terminal66_M3_full_feedback_and_cost_audit.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "audited_file_sha256"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    audit()
