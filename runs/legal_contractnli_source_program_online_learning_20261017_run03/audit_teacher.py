"""Replay a real teacher edit/full own-feedback packet; no model generation."""

# ruff: noqa: E402 -- Run-local reproducible audit.
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
from legal_skill_guard.learning.literal_evidence import literal_feedback_view
from legal_skill_guard.learning.publication import apply_differential_publication, differential_schema
from legal_skill_guard.learning.source_programs import (
    PROGRAM_FIELDS,
    PROGRAM_GUIDANCE_SCHEMA,
    PROGRAM_TEACHER,
    one_copy_memory,
    program_member_feedback,
    pack_program_feedback,
    unpack_program_feedback,
)
from legal_skill_guard.learning.task_local import bounded_teacher_packet
from legal_skill_guard.task import render_library
from legal_skill_guard.utils.hashing import canonical_json_sha256


def audit(batch):
    cfg_path = ROOT / "configs/contractnli_source_programs_completion.json"
    cfg, frozen = read(cfg_path), read(cfg_path.with_suffix(".frozen.json"))
    assert all(sha(p) == h for p, h in frozen["files"].items())
    packet = read(ROOT / cfg["input_packet"])
    labels, training = packet["public_hypotheses"], packet["training"]
    parent = read(OUT / f"update_transactions/b{batch - 1}.json")["publication"] if batch > 1 else []
    tx_path = OUT / f"update_transactions/b{batch}.json"
    tx = read(tx_path)
    assert tx["actual_parent"] == parent
    rows = [r for r in training if r["batch"] in (batch - 1, batch)]
    before, after, paths = {}, {}, [tx_path]
    for row in rows:
        stage = f"batch{batch}_before" if row["batch"] == batch else f"batch{batch - 1}_after"
        candidates = [OUT / stage / "skill_memory" / f"{row['id']}.{suffix}.json" for suffix in ("public", "reference")]
        found = [p for p in candidates if p.exists()]
        assert len(found) == 1
        p = found[0]
        unit = read(p)
        assert unit["published_library"] == parent
        (before if row["batch"] == batch else after)[row["id"]] = unit
        paths.extend((p, Path(unit["raw_artifact"])))
    state = next(iter(before.values()))["actual_factual_trace"]["ordinary_model_state"]
    meter = WireClient(cfg["generation"])
    master = meter.token_count(text=render_library(parent))
    scoped = meter.token_count(text=json.dumps(one_copy_memory(parent, labels), ensure_ascii=False, separators=(",", ":")))
    body = bounded_teacher_packet(training, batch, labels, parent, state, before, after,
        master_tokens=master, cap=cfg["library_token_hard_cap"], semantic_fields=PROGRAM_FIELDS)
    body = literal_feedback_view(body, rows)
    body["serialized_parent_scoped_delivery_tokens"] = scoped
    body["canonical_projection_is_resolved_named_library_not_literal_wire_repetition"] = True
    body["actual_runtime_source_lead_tags_by_case"] = {str(row["id"]):
        (before if row["batch"] == batch else after)[row["id"]]["actual_factual_trace"]["task_local_delivery"]["source_lead_tags_by_original_span"]
        for row in rows}
    body["actual_parent_source_program_member_feedback"] = [program_member_feedback(
        (before if row["batch"] == batch else after)[row["id"]], row, labels) for row in rows]
    directory = OUT / f"teacher/task_local_b{batch}"
    wire, response, events = (read(directory / name) for name in ("wire_request.json", "response.json", "event_log.json"))
    assert wire["system_prompt"] == PROGRAM_TEACHER
    inherited = (directory / "explicit_historical_reference.json").exists()
    expected = body if inherited else pack_program_feedback(body)
    assert wire["user_prompt"] == json.dumps(expected, ensure_ascii=False, separators=(",", ":"))
    if not inherited:
        assert json.dumps(unpack_program_feedback(json.loads(wire["user_prompt"])), ensure_ascii=False, separators=(",", ":")) == json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    assert wire["output_schema"] == differential_schema(labels, parent, [r["id"] for r in rows], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
    assert canonical_json_sha256(wire) == response["request_sha256"]
    assert response["value"] == tx["actual_teacher_value"]
    assert canonical_json_sha256(response["value"]) == response["response_sha256"]
    assert response["model"] == cfg["teacher"]["model"] and not response["cache_hit"]
    invocation = response["invocation"]
    assert invocation["attempt"] == 1 and invocation["returncode"] == 0 and not invocation["tool_events_detected"]
    assert canonical_json_sha256({"event_log": events["event_log"]}) == invocation["event_log_sha256"]
    messages = []
    for line in events["event_log"].splitlines():
        event = json.loads(line)
        if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "agent_message":
            messages.append(json.loads(event["item"]["text"]))
    assert messages == [response["value"]]
    published = apply_differential_publication(parent, response["value"], labels, [r["id"] for r in rows], guidance_schema=PROGRAM_GUIDANCE_SCHEMA)
    assert published == tx["publication"]
    paths.extend(directory / name for name in ("wire_request.json", "response.json", "event_log.json"))
    result = {"at": now(), "run_id": OUT.name, "batch": batch,
        "full_actual_same_parent_feedback_rebuilt_byte_identically": True,
        "actual_single_teacher_event_value_and_atomic_publication_replayed": True,
        "teacher_call_new_in_this_run_not_inherited": not inherited,
        "one_copy_actual_receipts_and_full_original_byte_roundtrip_checked": not inherited,
        "source_ids": [r["id"] for r in rows], "published_skill_count": len(published),
        "published_query_count": sum(len(s["guidance"]["source_queries"]) for s in published),
        "actual_management": tx["management"], "teacher_invocation": invocation,
        "not_independent_semantic_correctness_or_native_utility_proof": True,
        "audited_file_sha256": {**frozen["files"], str(Path(__file__)): sha(__file__), **{str(p): sha(p) for p in paths}}}
    RunStore.immutable_json(OUT / f"monitoring/M{batch}_full_actual_teacher_packet_and_publication_audit.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "audited_file_sha256"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    audit(int(sys.argv[1]))
