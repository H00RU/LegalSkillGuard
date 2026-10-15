"""Read completed atomic-memory cohorts; no model calls or effect gating."""

import copy
import json
import zipfile
from collections import Counter
from pathlib import Path

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.audit import close, original_score
from legal_skill_guard.learning.experiment import now, points, read, sha
from legal_skill_guard.learning.procedures import (
    ARMS,
    BOUNDARY_GUIDANCE_SCHEMA,
    ProcedureStudy,
    procedure_messages,
)
from legal_skill_guard.learning.publication import (
    apply_differential_publication,
    paired,
    publication_statistics,
)
from legal_skill_guard.task import marked_text
from legal_skill_guard.utils.hashing import canonical_json_sha256

RUN = Path(__file__).resolve().parents[1]
ROOT = RUN.parents[1]
CFG = read(ROOT / "configs/contractnli_atomic_boundaries.json")
PACKET = read(ROOT / CFG["input_packet"])
LABELS = PACKET["public_hypotheses"]
ROWS = {r["id"]: r for r in PACKET["training"]}


def check_source():
    bindings = read(RUN / "declaration.json")["frozen_bindings"]
    assert all(sha(p) == h for p, h in bindings.items())


def first_encounter(batch):
    dest = RUN / "monitoring" / f"B{batch}_complete_first_encounter_audit.json"
    if dest.exists():
        return
    rows = [r for r in ROWS.values() if r["batch"] == batch]
    arms = ("strong_empty", "ordinary_memory", "trace_procedures")
    paths = {
        a: [RUN / f"batch{batch}_before/{a}/{r['id']}.public.json" for r in rows] for a in arms
    }
    if not all(p.is_file() for pp in paths.values() for p in pp):
        return
    check_source()
    by = {a: [read(p) for p in pp] for a, pp in paths.items()}
    with zipfile.ZipFile(ROOT / CFG["source_archive"]) as z:
        author = json.loads(z.read("contract-nli/train.json"))
    assert author["labels"] == LABELS
    originals = {r["id"]: r for r in author["documents"]}
    expected_bank = read(RUN / f"update_transactions/trace_b{batch - 1}.json")["publication"]
    state = read(RUN / f"evidence_models/ordinary_M{batch - 1}.manifest.json")["state_sha256"]
    ids, controls = [], []
    for index, row in enumerate(rows):
        source = originals[row["id"]]
        assert row["text"] == source["text"] and row["spans"] == source["spans"]
        assert (
            row["annotation_sets"][0]["annotations"] == source["annotation_sets"][0]["annotations"]
        )
        normalized = []
        decode = None
        for arm in arms:
            u = by[arm][index]
            bank = expected_bank if arm == "trace_procedures" else []
            assert u["published_library"] == bank
            assert u["actual_factual_trace"]["ordinary_model_state"] == (
                None if arm == "strong_empty" else state
            )
            proposal = u["actual_factual_trace"]["proposals"]
            messages, schema = procedure_messages(
                row, LABELS, CFG["bundled_solver_system"], bank, proposal
            )
            raw = read(u["raw_artifact"])
            assert len(raw["calls"]) == 1 and raw["response"] == u["response"]
            request = raw["calls"][0]["request"]
            assert request["messages"] == messages
            assert request["response_format"]["json_schema"]["schema"] == schema
            meta = {k: v for k, v in request.items() if k not in ("messages", "response_format")}
            if decode is None:
                decode = meta
            assert meta == decode
            close(
                original_score(
                    u["response"], row, source["annotation_sets"][0]["annotations"], list(LABELS)
                ),
                u,
            )
            ids.append(u["response"]["raw_id"])
            if arm != "strong_empty":
                normalized.append(
                    (copy.deepcopy(json.loads(messages[1]["content"])), copy.deepcopy(schema))
                )
        ordinary, main = (by[a][index] for a in ("ordinary_memory", "trace_procedures"))
        assert ordinary["actual_factual_trace"] == main["actual_factual_trace"]
        for body, schema in normalized:
            for hypothesis in body["hypotheses"].values():
                del hypothesis["applicable_published_skill_ids"]
            del body["output_contract"]["common_schema_for_each_hypothesis"]["properties"][
                "used_skill_ids"
            ]
            for variants in schema["properties"].values():
                for variant in variants["anyOf"]:
                    del variant["properties"]["used_skill_ids"]
        assert normalized[0] == normalized[1]
        controls.append(row["id"])
    assert len(ids) == len(set(ids)) == 18
    metrics = {a: points(uu) for a, uu in by.items()}
    result = {
        "at": now(),
        "batch": batch,
        "results": metrics,
        "trace_minus_control": {
            a: {
                k: metrics["trace_procedures"][k] - metrics[a][k]
                for k in (
                    "label_accuracy",
                    "evidence_micro_f1_gold_non_neutral",
                    "joint_exact_accuracy",
                )
            }
            for a in arms
            if a != "trace_procedures"
        },
        "paired_trace_minus_control": {
            a: paired(by[a], by["trace_procedures"]) for a in arms if a != "trace_procedures"
        },
        "all6_actual_tool_control_source_pairs_verified": controls,
        "same_original_source_hypotheses_candidates_floats_decode_and_NLI_constraints": True,
        "intended_differences_are_library_declared_binding_and_skill_report_universe": True,
        "not_literal_full_prompt_identity_or_independent_learning_repeat": True,
        "new_native_calls": 0,
        "new_teacher_calls": 0,
        "endpoint_gold_read": False,
    }
    RunStore.immutable_json(dest, result)
    print(
        json.dumps(
            {k: v for k, v in result.items() if not k.startswith("paired_")},
            ensure_ascii=False,
            indent=2,
        )
    )


def teacher_window(batch):
    dest = RUN / "monitoring" / f"actual_B{batch}_same_parent_teacher_audit.json"
    transaction = RUN / f"update_transactions/trace_b{batch}.json"
    if dest.exists() or not transaction.is_file():
        return
    check_source()
    t = read(transaction)
    wire = read(RUN / f"teacher/trace_b{batch}/wire_request.json")
    body = json.loads(wire["user_prompt"])
    study = object.__new__(ProcedureStudy)
    study.training, study.bank = PACKET["training"], t["actual_parent"]
    study.state = (
        None
        if batch == 1
        else read(RUN / f"evidence_models/ordinary_M{batch - 1}.manifest.json")["state_sha256"]
    )
    study.before = {
        r["id"]: read(
            RUN
            / f"batch{batch}_before/trace_procedures/{r['id']}.{'shared' if batch == 1 else 'public'}.json"
        )
        for r in study.training
        if r["batch"] == batch
    }
    study.after = {
        r["id"]: read(RUN / f"batch{batch - 1}_after/trace_procedures/{r['id']}.public.json")
        for r in study.training
        if r["batch"] == batch - 1
    }
    expected = study.teacher_cases(batch, include_trace=True)
    assert body["same_parent_library_and_tool_original_train_cases"] == expected
    assert body["complete_actual_parent_library"] == study.bank
    with zipfile.ZipFile(ROOT / CFG["source_archive"]) as z:
        original = json.loads(z.read("contract-nli/train.json"))
    originals = {r["id"]: r for r in original["documents"]}
    for case in expected:
        row = originals[case["document_id"]]
        assert case["full_original_contract_with_spans"] == marked_text(row)
        assert case["original_annotations"] == row["annotation_sets"][0]["annotations"]
    assert (
        apply_differential_publication(
            study.bank,
            t["actual_teacher_value"],
            LABELS,
            t["source_case_ids"],
            guidance_schema=BOUNDARY_GUIDANCE_SCHEMA,
        )
        == t["publication"]
    )
    result = {
        "at": now(),
        "batch": batch,
        "all_original_source_gold_and_actual_same_parent_observations": len(expected),
        "current_before_cases": [
            c["document_id"]
            for c in expected
            if c["observation_kind"] == "current_batch_first_encounter"
        ],
        "previous_after_cases": [
            c["document_id"]
            for c in expected
            if c["observation_kind"] == "previous_batch_post_update"
        ],
        "actual_teacher_input_characters": len(wire["system_prompt"]) + len(wire["user_prompt"]),
        "actual_local_8b_trace_characters": sum(
            len(
                c["actual_own_same_parent_observation"]["local_executor_trace"][
                    "reasoning_content_verbatim"
                ]
            )
            for c in expected
        ),
        "management": t["management"],
        "no_outcome_filter_or_stale_different_parent_observations": True,
        "new_native_calls": 0,
        "new_teacher_calls": 0,
        "endpoint_gold_read": False,
    }
    RunStore.immutable_json(dest, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def library_lifecycle(batch):
    """Inspect actual edits and scope; text identity is not semantic utility."""
    dest = RUN / "monitoring" / f"M{batch}_library_lifecycle_audit.json"
    transaction = RUN / f"update_transactions/trace_b{batch}.json"
    if dest.exists() or not transaction.is_file():
        return
    check_source()
    t = read(transaction)
    old, bank = t["actual_parent"], t["publication"]
    if batch > 1:
        assert old == read(RUN / f"update_transactions/trace_b{batch - 1}.json")["publication"]
    tokens = t["management"]["serialized_library_tokens"]
    assert publication_statistics(old, t["actual_teacher_value"], bank, tokens) == t["management"]
    assert tokens <= CFG["library_token_hard_cap"]
    wire = read(RUN / f"teacher/trace_b{batch}/wire_request.json")
    assert all(
        word in wire["system_prompt"] for word in ("CREATE", "UPDATE", "MERGE", "DELETE", "noop")
    )
    identities = {}
    for s in bank:
        key = json.dumps(
            {"hypothesis_ids": sorted(s["hypothesis_ids"]), "guidance": s["guidance"]},
            ensure_ascii=False,
            sort_keys=True,
        )
        identities.setdefault(key, []).append(s["id"])
    coverage = {h: [s["id"] for s in bank if h in s["hypothesis_ids"]] for h in LABELS}
    result = {
        "at": now(),
        "version": batch,
        "actual_parent_and_logged_edit_statistics_verified": True,
        "actual_teacher_instructions_offer_create_update_merge_delete_and_noop": True,
        "management": t["management"],
        "serialized_library_token_cap": CFG["library_token_hard_cap"],
        "remaining_library_token_capacity": CFG["library_token_hard_cap"] - tokens,
        "same_guidance_and_scope_exact_duplicate_groups": [
            ids for ids in identities.values() if len(ids) > 1
        ],
        "public_hypothesis_to_declared_skill_ids": coverage,
        "public_hypotheses_without_declared_skill": [h for h, ids in coverage.items() if not ids],
        "conditional_relation_counts": dict(
            Counter(str(s["guidance"]["relation_if_established"]) for s in bank)
        ),
        "retained_unmentioned_rules_are_not_deleted_for_feedback_window_absence": True,
        "growth_or_token_use_is_not_efficacy": True,
        "exact_text_identity_does_not_detect_semantic_redundancy_or_conflicts": True,
        "no_forced_count_merge_delete_quota_or_effect_gate": True,
        "actual_transfer_evidence": (
            str(RUN / "monitoring" / f"B{batch + 1}_complete_first_encounter_audit.json")
            if batch < 4
            else "fixed-last-bank endpoint and B1 retention, only when fully completed"
        ),
        "new_native_calls": 0,
        "new_teacher_calls": 0,
        "endpoint_gold_read": False,
    }
    RunStore.immutable_json(dest, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def after_components(batch):
    dest = RUN / "monitoring" / f"B{batch}_complete_component_audit.json"
    summary = RUN / f"batch{batch}_summary.json"
    if dest.exists() or not summary.is_file():
        return
    check_source()
    units = [
        read(RUN / f"batch{batch}_after/trace_procedures/{r['id']}.public.json")
        for r in ROWS.values()
        if r["batch"] == batch
    ]
    assert len(units) == 6
    counts = Counter()
    exact_wrong = {"nonneutral_with_nonempty_gold": [], "NM_with_empty_gold": []}
    for unit in units:
        row = ROWS[unit["document_id"]]
        expected = original_score(
            unit["response"], row, row["annotation_sets"][0]["annotations"], list(LABELS)
        )
        close(expected, unit)
        proposals = unit["actual_factual_trace"]["proposals"]["by_hypothesis"]
        for q in expected["queries"]:
            candidates = {
                v["original_span_index"] for v in proposals[q["hypothesis_id"]]["candidates"]
            }
            gold = set(q["gold"]["spans"])
            predicted = set((q["prediction"] or {}).get("spans", []))
            if not q["label_correct"] and gold == candidates:
                category = (
                    "nonneutral_with_nonempty_gold"
                    if q["gold_non_neutral"]
                    else "NM_with_empty_gold"
                )
                exact_wrong[category].append([unit["document_id"], q["hypothesis_id"]])
            if not q["gold_non_neutral"]:
                continue
            counts.update(
                {
                    "tool_tp": len(gold & candidates),
                    "tool_fp": len(candidates - gold),
                    "tool_fn": len(gold - candidates),
                    "native_fn_inside_candidates": len((gold - predicted) & candidates),
                    "native_fn_outside_candidates": len((gold - predicted) - candidates),
                }
            )
    metrics = points(units)
    close(metrics, read(summary)["after"]["trace_procedures"])
    tp, fp, fn = (counts[k] for k in ("tool_tp", "tool_fp", "tool_fn"))
    result = {
        "at": now(),
        "batch": batch,
        "after_seen_fit_original_metrics": metrics,
        "ordinary_tool_membership_micro_f1": 2 * tp / (2 * tp + fp + fn),
        "membership_counts": dict(counts),
        "wrong_relations_with_exact_gold_candidate_sets": exact_wrong,
        "NM_empty_candidates_are_not_correct_positive_evidence": True,
        "after_also_includes_new_supervised_tool_labels_not_pure_skill_effect": True,
        "new_native_calls": 0,
        "new_teacher_calls": 0,
        "endpoint_gold_read": False,
    }
    RunStore.immutable_json(dest, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def completed_primary():
    """Read back all native wires, then independently score original TRAIN Gold."""
    dest = RUN / "monitoring/independent_complete_primary_audit.json"
    if dest.exists() or read(RUN / "progress.json")["state"] != "completed":
        return
    check_source()
    paths = (
        list(RUN.glob("batch*/*/*.public.json"))
        + list((RUN / "retention_b4").glob("*/*.public.json"))
        + list((RUN / "later").glob("*/*.public.json"))
    )
    shares = [read(p) for p in RUN.glob("batch1_before/*/*.shared.json")]
    units = [read(p) for p in paths]
    assert len(units) == len({u["response"]["raw_id"] for u in units}) == 130
    assert len(shares) == 12
    later = [u for u in units if u["stage"] == "later"]
    assert len(later) == 40 and {u["arm"] for u in later} == set(ARMS)
    final = read(RUN / "memory_frozen_before_later.json")
    banks = {
        "strong_empty": [],
        "ordinary_memory": [],
        "trace_procedures": final["main_library"],
        "static_procedures": final["static_library"],
        "public_only_final_update": final["public_only_final_update_library"],
    }
    manifests = {
        b: read(RUN / f"evidence_models/ordinary_M{b}.manifest.json") for b in (1, 2, 3, 4)
    }
    versions = {
        0: [],
        **{
            b: read(RUN / f"update_transactions/trace_b{b}.json")["publication"]
            for b in (1, 2, 3, 4)
        },
    }
    for unit in units + shares:
        if unit["stage"] == "later":
            b, bank = 4, banks[unit["arm"]]
        elif unit["stage"] == "retention_b4":
            b, bank = 4, versions[4]
        else:
            phase = unit["stage"].split("_")
            b = int(phase[0].removeprefix("batch")) - (phase[1] == "before")
            bank = versions[b] if unit["arm"] == "trace_procedures" else []
        assert unit["published_library"] == bank
        assert unit["published_library_sha256"] == canonical_json_sha256(bank)
        state = None if b == 0 or unit["arm"] == "strong_empty" else manifests[b]["state_sha256"]
        assert unit["actual_factual_trace"]["ordinary_model_state"] == state
    # Reuse native replay, not the online result aggregation. This checks raw
    # source, model-derived candidates, public schema and local-trace identity.
    study = object.__new__(ProcedureStudy)
    study.training, study.future, study.labels, study.cfg, study.out = (
        PACKET["training"],
        PACKET["later_inputs_no_annotation_sets"],
        LABELS,
        CFG,
        RUN,
    )
    study.state_versions = {m["state_sha256"]: m for m in manifests.values()}
    study.audit_native(units + shares, "all142_logical_observations_readback")
    # Endpoint grading is read only after the complete40 response/wire gate.
    gold = read(ROOT / CFG["grading_only"])["annotations"]
    with zipfile.ZipFile(ROOT / CFG["source_archive"]) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    assert author["labels"] == LABELS
    originals = {r["id"]: r for r in author["documents"]}
    rows = {r["id"]: r for r in PACKET["training"] + PACKET["later_inputs_no_annotation_sets"]}
    for row in rows.values():
        source = originals[row["id"]]
        assert row["text"] == source["text"] and row["spans"] == source["spans"]
        if row["id"] in ROWS:
            assert (
                row["annotation_sets"][0]["annotations"]
                == source["annotation_sets"][0]["annotations"]
            )
        else:
            assert (
                "annotation_sets" not in row
                and gold[str(row["id"])] == source["annotation_sets"][0]["annotations"]
            )
    by = {a: [] for a in ARMS}
    for unit in units + shares:
        row = rows[unit["document_id"]]
        expected = original_score(
            unit["response"],
            row,
            originals[row["id"]]["annotation_sets"][0]["annotations"],
            list(LABELS),
        )
        if unit["stage"] == "later":
            scored = read(RUN / "later_scored" / unit["arm"] / f"{row['id']}.json")
            assert scored["response"] == unit["response"]
            close(expected, scored)
            by[unit["arm"]].append({**unit, **expected})
        else:
            close(expected, unit)
    done = read(RUN / "completion.json")
    metrics = {
        a: points(sorted(v, key=lambda u: CFG["expected_later_ids"].index(u["document_id"])))
        for a, v in by.items()
    }
    close(metrics, done["development"])
    native = [read(p) for p in RUN.rglob("*.final.native.json")]
    assert len(native) == 130 and {n["response"]["raw_id"] for n in native} == {
        u["response"]["raw_id"] for u in units
    }
    for n in native:
        assert len(n["calls"]) == 1
        wire = n["calls"][0]["response"]
        assert wire["id"] == n["response"]["raw_id"]
        for k in ("prompt_tokens", "completion_tokens"):
            assert wire["usage"][k] == n["response"][k]
    usage = {
        k: sum(n["response"][k] for n in native) for k in ("prompt_tokens", "completion_tokens")
    }
    close(usage, done["native_usage"])
    teachers = [read(p) for p in (RUN / "teacher").glob("*/response.json")]
    assert len(teachers) == 6 and done["new_teacher_calls"] == 6
    teacher_usage = {
        k: sum(t["invocation"]["usage"][k] for t in teachers)
        for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")
    }
    close(teacher_usage, done["teacher_usage"])
    assert all(
        not t["cache_hit"] and not t["invocation"].get("tool_events_detected") for t in teachers
    )
    result = {
        "at": now(),
        "physical_native_answers": 130,
        "explicit_shared_observations": 12,
        "teacher_responses": 6,
        "all40_native_endpoint_answers_saved_and_replayed_before_this_auditor_grading_read": True,
        "all_original_TRAIN_sources_labels_and_2414_logical_hypotheses_independently_scored": True,
        "wire_source_model_library_schema_replay_uses_existing_replayer_not_a_separate_semantic_judge": True,
        "results": metrics,
        "native_usage": usage,
        "teacher_usage": teacher_usage,
        "reasoning_output_tokens_are_a_subset_not_added_again": True,
        "not_official_test_or_independent_learning_repetitions": True,
        "new_native_calls": 0,
        "new_teacher_calls": 0,
    }
    RunStore.immutable_json(dest, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    for batch in (1, 2, 3, 4):
        library_lifecycle(batch)
        after_components(batch)
    for batch in (2, 3, 4):
        first_encounter(batch)
        teacher_window(batch)
    completed_primary()
