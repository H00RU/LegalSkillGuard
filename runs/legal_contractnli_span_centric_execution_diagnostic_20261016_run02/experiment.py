"""Fixed-M2, complete B3 execution diagnostic; not a new online learner.

Native span-first assignments are a lossless original-set representation. No
label, candidate, skill or Gold adds/removes a model-selected membership. All
18 calls finish before new scores are computed. Never substitute a reply.
"""

from __future__ import annotations

import copy
import fcntl
import json
import os
import signal
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator, validate

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.audit import original_score
from legal_skill_guard.learning.experiment import Comparison, now, read, sha
from legal_skill_guard.task import marked_text

ARMS = ("strong_empty", "ordinary_memory", "skill_memory")
SOURCE = ROOT / "runs/legal_contractnli_literal_evidence_online_learning_20261016_run02"
CONFIG = ROOT / "configs/contractnli_literal_fixed_static.json"


def transform(original):
    """Change serialization/execution unit only; all source/skills/tools stay."""
    req = copy.deepcopy(original)
    old_schema = req["response_format"]["json_schema"]["schema"]
    keys = list(old_schema["properties"])
    decisions, coordinate_lists = {}, []
    for h, wrapped in old_schema["properties"].items():
        one = copy.deepcopy(wrapped["anyOf"][0])
        coordinate_lists.append(one["properties"].pop("spans")["items"]["enum"])
        one["required"].remove("spans")
        one["properties"]["choice"]["enum"] = ["Entailment", "Contradiction", "NotMentioned"]
        decisions[h] = one
    coordinates = coordinate_lists[0]
    assert coordinates == list(range(len(coordinates))) and all(x == coordinates for x in coordinate_lists)
    assignment = {str(i): {"type": "array", "maxItems": len(keys), "items": {"type": "string", "enum": keys}} for i in coordinates}
    props = {
        "span_membership": {"type": "object", "additionalProperties": False, "required": list(assignment), "properties": assignment},
        "decisions": {"type": "object", "additionalProperties": False, "required": keys, "properties": decisions},
    }
    schema = {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}
    Draft202012Validator.check_schema(schema)
    req["response_format"]["json_schema"]["schema"] = schema
    replacements = {
        "For supported/opposed hypotheses cite all original evidence span indices for that decision, including independently operative redundant support and necessary governing language.":
        "Inspect every original SPAN in order and assign it to all hypotheses whose complete evidence set includes that SPAN, including independently operative redundant support and necessary governing language.",
        "For NotMentioned return an empty evidence list.":
        "For NotMentioned do not assign that hypothesis to any SPAN.",
        "Return exactly the supplied JSON schema with all 17 original hypothesis keys. For each emit choice, spans, reason, used_skill_ids in that order.":
        "Return span_membership first: an explicit list of applicable original hypothesis IDs for EVERY original SPAN key, including [] when irrelevant. Then return decisions for all 17 original hypotheses, each with choice, reason, used_skill_ids. Membership means full original evidence, not mere topical overlap or a minimal proof. A SPAN may belong to several hypotheses. Do not restrict the scan to proposed candidates. Labels and assignments must agree, but no host will correct them for you.",
    }
    system = req["messages"][0]["content"]
    for old, new in replacements.items():
        assert system.count(old) == 1
        system = system.replace(old, new)
    req["messages"][0]["content"] = system
    body = json.loads(req["messages"][1]["content"])
    old_body = copy.deepcopy(body)
    body["output_contract"] = {
        "native_format": "complete_span_centric_membership_v1",
        "span_membership_keys_in_order": list(assignment),
        "all_original_hypothesis_keys": keys,
        "empty_assignment_for_irrelevant_span": True,
        "original_choices": ["Entailment", "Contradiction", "NotMentioned"],
        "NotMentioned_requires_no_assigned_spans": True,
        "other_original_choices_require_assigned_evidence": True,
        "reason_at_most15_words_per_hypothesis": True,
        "used_skill_ids_must_be_from_this_question_and_may_be_empty": True,
        "no_automatic_union_label_change_completion_or_repair": True,
    }
    assert {k: v for k, v in body.items() if k != "output_contract"} == {k: v for k, v in old_body.items() if k != "output_contract"}
    req["messages"][1]["content"] = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return req, schema


def decode(value, schema):
    """Only transpose explicit memberships; no inference or label-based erasure."""
    validate(value, schema)
    return {h: {**decision, "spans": [int(i) for i, hs in value["span_membership"].items() if h in hs]}
            for h, decision in value["decisions"].items()}


def aggregate(queries):
    nn = [q for q in queries if q["Gold_choice"] != "NotMentioned"]
    tp, fp, fn = (sum(q[k] for q in nn) for k in ("tp", "fp", "fn"))
    return {"hypotheses": len(queries), "label_correct": sum(q["label_correct"] for q in queries),
            "label_accuracy": sum(q["label_correct"] for q in queries) / len(queries),
            "evidence_tp": tp, "evidence_fp": fp, "evidence_fn": fn,
            "evidence_micro_f1_gold_non_neutral": 2 * tp / (2 * tp + fp + fn),
            "joint_exact_correct": sum(q["joint_exact"] for q in queries),
            "joint_exact_accuracy": sum(q["joint_exact"] for q in queries) / len(queries),
            "NN_joint": sum(q["joint_exact"] for q in nn),
            "NM_joint": sum(q["joint_exact"] for q in queries if q["Gold_choice"] == "NotMentioned"),
            "true_members_outside_original_candidates": sum(len(set(q["Gold_spans"]) & set((q["prediction"] or {}).get("spans", [])) - set(q["visible_candidates"])) for q in nn),
            "choice_evidence_inconsistencies_not_repaired": sum(q["prediction"] is not None and ((q["prediction"]["choice"] == "NotMentioned") != (not q["prediction"]["spans"])) for q in queries)}


def paired(before, after):
    assert [(q["document_id"], q["hypothesis_id"]) for q in before] == [(q["document_id"], q["hypothesis_id"]) for q in after]
    pairs = list(zip(before, after, strict=True))
    result = {}
    for name in ("label_correct", "joint_exact"):
        result[name + "_fixes"] = sum(not a[name] and b[name] for a, b in pairs)
        result[name + "_damage"] = sum(a[name] and not b[name] for a, b in pairs)
    return result


class Probe(Comparison):
    def __init__(self):
        registration = read(OUT / "registration.json")
        self.cfg = read(CONFIG)
        self.cfg = {**self.cfg, "planned_new_native_calls": 18, "planned_new_teacher_calls": 0}
        self.bindings = registration["files"]
        self.run_id, self.out = OUT.name, OUT
        self.native, self.teachers, self.teacher_attempts, self.current_batch, self.stop = [], [], 0, 3, False
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: setattr(self, "stop", True))

    def execute(self):
        registration = read(OUT / "registration.json")
        terminal = read(SOURCE / "progress.json")
        launch = read(SOURCE / "launch.json")
        assert not (Path("/proc") / str(launch["pid"])).exists()
        assert terminal["state"] == "failed"
        assert (terminal["completed_native_calls"], terminal["completed_teacher_calls"], terminal["teacher_attempts"]) == (96, 4, 4)
        audit = read(SOURCE / "monitoring/complete_B3_independent_original_author_and_matched_error_audit.json")
        assert audit["complete_original_training_source_ids"] == registration["source_ids"]
        assert audit["distinct_native_raw_ids"] == 30
        assert all(sha(p) == h for p, h in audit["audited_file_sha256"].items())
        RunStore.immutable_json(OUT / "terminal_source_provenance.json", {
            "actual_source_terminal_state": terminal,
            "complete_B3_independent_original_author_and_actual_wire_audit_checked": True,
            "source_M4_rejected_proposal_not_used": True,
            "unrelated_B4_failure_not_replaced_repaired_or_called_complete": True,
        })
        with (ROOT / "artifacts/gpu_generation.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            for index, d in enumerate(registration["source_ids"]):
                order = ARMS[index % 3:] + ARMS[:index % 3]
                for arm in order:
                    original = read(SOURCE / f"batch3_before/{arm}/{d}.final.native.json")["calls"][0]["request"]
                    req, schema = transform(original)
                    response = self.call(OUT / arm / f"{d}.native.json", req["messages"], schema, req["max_tokens"], {"stage": "complete_B3_fixed_M2_diagnostic", "arm": arm, "document_id": d, "call_role": "final"})
                    assert self.native[-1]["calls"][0]["request"] == req
                    parsed, error = None, None
                    try:
                        if response["finish_reason"] != "stop":
                            raise ValueError("Incomplete native answer")
                        parsed = decode(json.loads(response["content"]), schema)
                    except Exception as exc:
                        error = repr(exc)
                    RunStore.immutable_json(OUT / arm / f"{d}.observation.json", {
                        "actual_native": response, "lossless_original_coordinate_view": parsed,
                        "public_format_error_no_retry_or_repair": error,
                        "not_a_new_native_response_or_label_corrected_answer": True,
                    })
            self.finish_probe()

    def finish_probe(self):
        assert len(self.native) == len({r["response"]["raw_id"] for r in self.native}) == 18
        ids = read(OUT / "registration.json")["source_ids"]
        # Only these six already-observed TRAIN contracts; no endpoint/DEV/TEST.
        with zipfile.ZipFile(ROOT / self.cfg["source_archive"]) as archive:
            author = json.loads(archive.read("contract-nli/train.json"))
        rows = {r["id"]: r for r in author["documents"] if r["id"] in ids}
        groups = {}
        for arm in ARMS:
            old_queries, new_queries = [], []
            for d in ids:
                row = rows[d]
                old = read(SOURCE / f"batch3_before/{arm}/{d}.final.native.json")
                old_body = json.loads(old["calls"][0]["request"]["messages"][1]["content"])
                assert old_body["full_contract_with_original_span_markers"] == marked_text(row)
                observed = read(OUT / arm / f"{d}.observation.json")
                decoded = observed["lossless_original_coordinate_view"]
                original = original_score(old["response"], row, row["annotation_sets"][0]["annotations"], list(author["labels"]))
                for q in original["queries"]:
                    h, gold = q["hypothesis_id"], q["gold"]
                    before = q["prediction"]
                    after = None if decoded is None else decoded[h]
                    for output, prediction in ((old_queries, before), (new_queries, after)):
                        gs, ps = set(gold["spans"]), set() if prediction is None else set(prediction["spans"])
                        correct = prediction is not None and prediction["choice"] == gold["choice"]
                        output.append({"document_id": d, "hypothesis_id": h, "Gold_choice": gold["choice"],
                            "Gold_spans": gold["spans"], "prediction": prediction, "label_correct": correct,
                            "visible_candidates": [c["original_span_index"] for c in old_body["hypotheses"][h]["fallible_evidence_candidates"] or []],
                            "joint_exact": correct and gs == ps, "tp": len(gs & ps), "fp": len(ps - gs), "fn": len(gs - ps)})
            groups[arm] = {"old_sparse_interface": old_queries, "new_span_centric_interface": new_queries}
        result = {"at": now(), "run_id": OUT.name, "source_ids": ids, "new_native_calls": 18, "new_teacher_calls": 0,
            "fixed_M2_delivery_diagnostic_not_new_learning_or_paper_test": True,
            "all18_completed_before_new_scores": True, "all_frozen_files_unchanged": True,
            "native_originals_and_lossless_views_kept_separate_no_answer_repair": True,
            "new_schema_does_not_hard_constrain_cross_object_label_evidence_coherence": True,
            "old_new_difference_is_execution_output_contract_policy_not_only_field_order": True,
            "metrics": {arm: {k: aggregate(qs) for k, qs in variants.items()} for arm, variants in groups.items()},
            "paired_new_vs_old_execution": {arm: paired(qs["old_sparse_interface"], qs["new_span_centric_interface"]) for arm, qs in groups.items()},
            "paired_new_skill_vs_new_controls": {arm: paired(groups[arm]["new_span_centric_interface"], groups["skill_memory"]["new_span_centric_interface"]) for arm in ARMS if arm != "skill_memory"},
            "all_query_records": groups,
            "native_usage": {k: sum(n["response"][k] for n in self.native) for k in ("prompt_tokens", "completion_tokens")},
            "no_automatic_method_bank_selection_or_formal_training_launch": True}
        self.check()
        RunStore.immutable_json(OUT / "completion.json", result)
        RunStore.atomic_json(OUT / "progress.json", {"at": now(), "state": "completed", "run_id": OUT.name, "completed_native_calls": 18, "completed_teacher_calls": 0})


def prepare():
    assert not (OUT / "registration.json").exists()
    cfg, frozen = read(CONFIG), read(CONFIG.with_suffix(".frozen.json"))
    assert frozen["config_sha256"] == sha(CONFIG) and all(sha(p) == h for p, h in frozen["files"].items())
    ids = cfg["training_ids"][12:18]
    assert len(ids) == 6
    pid = read(SOURCE / "launch.json")["pid"]
    proc = Path("/proc") / str(pid)
    assert not proc.exists(), "Source worker must really be terminal"
    terminal = read(SOURCE / "progress.json")
    assert terminal["state"] == "failed" and terminal["completed_native_calls"] == 96
    files = {**frozen["files"], str(CONFIG.with_suffix(".frozen.json")): sha(CONFIG.with_suffix(".frozen.json")),
             str(Path(__file__)): sha(__file__), str(OUT / "PROTOCOL.md"): sha(OUT / "PROTOCOL.md")}
    for p in (SOURCE / "failure.json", SOURCE / "progress.json", SOURCE / "launch.json",
              SOURCE / "monitoring/complete_B3_independent_original_author_and_matched_error_audit.json"):
        files[str(p)] = sha(p)
    for d in ids:
        for arm in ARMS:
            path = SOURCE / f"batch3_before/{arm}/{d}.final.native.json"
            raw = read(path)
            req, schema = transform(raw["calls"][0]["request"])
            original = json.loads(raw["response"]["content"])
            transposed = {"span_membership": {i: [h for h, p in original.items() if int(i) in p["spans"]] for i in schema["properties"]["span_membership"]["properties"]},
                          "decisions": {h: {k: v for k, v in p.items() if k != "spans"} for h, p in original.items()}}
            restored = decode(transposed, schema)
            assert all(set(restored[h]["spans"]) == set(p["spans"]) and {k: v for k, v in restored[h].items() if k != "spans"} == {k: v for k, v in p.items() if k != "spans"} for h, p in original.items())
            files[str(path)] = sha(path)
    RunStore.immutable_json(OUT / "registration.json", {"at": now(), "source_ids": ids, "arms": list(ARMS), "planned_new_native_calls": 18,
        "files": files, "source_worker_pid_confirmed_exited": pid, "source_terminal_state": terminal,
        "all18_archived_answer_sets_losslessly_roundtripped_without_Gold": True,
        "local_schema_codec_checks_not_model_qualification_or_efficacy": True, "new_model_teacher_calls_so_far": [0, 0]})


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "prepare":
        prepare()
    elif command == "launch":
        assert (OUT / "registration.json").exists() and not (OUT / "launch.json").exists()
        argv = [str(ROOT / ".venv/bin/python"), str(Path(__file__).resolve()), "worker"]
        with (OUT / "worker.log").open("xb") as log:
            child = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        RunStore.immutable_json(OUT / "launch.json", {"at": now(), "pid": child.pid, "actual_argv": argv, "background_independent_of_conversation": True})
        print(json.dumps({"run_id": OUT.name, "pid": child.pid, "complete_B3_and_terminal96_source_verified": True}))
    elif command == "worker":
        probe = Probe()
        try:
            probe.execute()
        except BaseException as exc:
            value = {"at": now(), "run_id": OUT.name, "error": repr(exc), "completed_native_calls": len(probe.native), "completed_teacher_calls": 0, "no_retry_fallback_or_output_repair": True}
            RunStore.immutable_json(OUT / "failure.json", value)
            RunStore.atomic_json(OUT / "progress.json", {"state": "failed", **value})
            raise
    else:
        raise ValueError("Explicit prepare, launch or worker command required")
