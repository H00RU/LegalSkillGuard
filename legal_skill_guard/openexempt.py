"""Pinned OpenExempt TRAIN generation and unchanged official EC/EV scoring.

Upstream: servantez/OpenExempt, ec6fa2547431096588ce2d3ef107b8adc33cd4fe,
CC BY 4.0. The original generator and evaluator remain unmodified in data/cache.
Only original Task.prompt() is an inference input. Symbolic cases and the
upstream solver are data-construction/grading capabilities, never agent tools.
"""

from __future__ import annotations

import copy
import importlib
import json
import logging
import math
import random
import sys
from pathlib import Path

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "ec6fa2547431096588ce2d3ef107b8adc33cd4fe"
UPSTREAM = ROOT / "data/cache/openexempt/servantez-OpenExempt-ec6fa25"
FAMILIES = {"EC": 2, "EV": 3}
PROMPT_FIELDS = (
    "instruction", "meta_instruction", "response_format", "facts", "solved_steps",
    "statutes", "format_reminder",
)


def upstream(name):
    if not UPSTREAM.is_dir():
        raise FileNotFoundError("Download the pinned official OpenExempt archive first")
    location = str(UPSTREAM)
    if location not in sys.path:
        sys.path.insert(0, location)
    module = importlib.import_module(name)
    if not Path(module.__file__).resolve().is_relative_to(UPSTREAM):
        raise ValueError("Unexpected upstream module origin")
    return module


def public_case_key(case):
    """Group EC/EV by public underlying facts, not task ID or expert annotations."""
    value = copy.deepcopy(case.serialize())
    value.pop("state_jurisdiction")  # Generated AE answer, not a raw factual attribute.
    for asset in value["assets"]:
        del asset["applicable_exemptions"]
        del asset["category_hints"]
    return csha(value)


def public_task(task, case_id, source_key, family):
    components = {key: getattr(task, key) for key in PROMPT_FIELDS}
    prompt = "\n\n".join(filter(None, components.values()))
    if prompt != task.prompt():
        raise ValueError("Original Task.prompt() did not reconstruct exactly")
    return {"case_id": case_id, "source_key": source_key, "family": family,
            "components": components, "prompt": prompt}


def prepare(config):
    """Generate fixed independent TRAIN cases, never resample by model outcome."""
    from legal_skill_guard.learning.experiment import sha

    packet_path = ROOT / config["input_packet"]
    if packet_path.exists():
        raise FileExistsError("Prepared input exists; use it, never overwrite/resample")
    Config = upstream("source.config").Config
    CaseGenerator = upstream("source.case_generator").CaseGenerator
    TaskGenerator = upstream("source.task_generator").TaskGenerator
    settings = json.loads((UPSTREAM / "config.json").read_text())
    settings.update(config["dataset_generation"])
    for name in ("data_directory", "asset_directory", "statute_directory", "template_directory"):
        settings[name] = str(UPSTREAM / settings[name])
    settings["output_directory"] = str(packet_path.parent / "unused_upstream_output")
    settings["start_task_id"] = 2
    selected_ids = config.get("preselected_source_case_ids", [])
    count = config["source_cases"] - len(selected_ids)
    if count < 1 or len(selected_ids) != len(set(selected_ids)):
        raise ValueError("A positive additional-source count and distinct preselected IDs are required")
    settings["dataset_size"] = count
    random.seed(config["dataset_seed"])
    configs = {f: Config({**settings, "terminal_task_id": i}, "train_" + f, False)
               for f, i in FAMILIES.items()}
    cases = CaseGenerator(configs["EC"])
    generators = {f: TaskGenerator(c) for f, c in configs.items()}
    public_rows, groups, excluded_keys = [], [], set()
    if selected_ids:
        parent_rows = json.loads((ROOT / config["preselected_source_packet"]).read_text())["rows"]
        excluded_keys = {r["source_key"] for r in parent_rows}
        for position, case_id in enumerate(selected_ids):
            pair = [r for r in parent_rows if r["case_id"] == case_id]
            if len(pair) != 2 or {r["family"] for r in pair} != set(FAMILIES):
                raise ValueError("Every preselected source needs its original EC/EV pair")
            groups.append(pair[0]["source_key"])
            public_rows.extend({**copy.deepcopy(r), "batch": position // config["batch_source_cases"] + 1}
                               for r in pair)
            old_grade = ROOT / config["preselected_grading_directory"] / f"{case_id}.json"
            old_case = old_grade.parent.parent / "construction_only" / f"{case_id}.json"
            for destination, original in (
                    (ROOT / config["grading_directory"] / f"{case_id}.json", old_grade),
                    (packet_path.parent / "construction_only" / f"{case_id}.json", old_case)):
                RunStore.immutable_json(destination, json.loads(original.read_text()))
    for name in config.get("additional_exclusion_packets", []):
        excluded_keys.update(r["source_key"] for r in json.loads((ROOT / name).read_text())["rows"])
    for index in range(count):
        case = cases.generate_case()
        source_key = public_case_key(case)
        if source_key in groups or source_key in excluded_keys:
            raise ValueError("Duplicate generated case; do not silently reroll")
        groups.append(source_key)
        case_id = config.get("new_case_id_start", 1) + index
        if case_id in selected_ids:
            raise ValueError("Additional case identity collides with a preselected source")
        gold = {}
        for family, generator in generators.items():
            task = generator.generate_task(case)
            if family == "EV" and not task.solution:
                raise ValueError(f"Original EV target is empty for fixed case {case_id}; "
                                 "native F1 is undefined, retain selection and review without reroll")
            public_rows.append({**public_task(task, case_id, source_key, family),
                "batch": (len(selected_ids) + index) // config["batch_source_cases"] + 1})
            gold[family] = task.solution
        RunStore.immutable_json(ROOT / config["grading_directory"] / f"{case_id}.json",
                                {"case_id": case_id, "source_key": source_key,
                                 "targets": gold})
        RunStore.immutable_json(packet_path.parent / "construction_only" / f"{case_id}.json",
                                {"never_to_actor_or_teacher": True, "case": case.serialize()})
    packet = {"rows": public_rows, "generation_seed": config["dataset_seed"],
              "source_cases": len(groups), "additional_generated_source_cases": count,
              "preselected_source_case_ids": selected_ids, "upstream_commit": COMMIT,
              "official_test_opened": False, "start_task_id": 2}
    RunStore.immutable_json(packet_path, packet)
    receipt = {"upstream_commit": COMMIT,
               "archive_sha256": sha(ROOT / config["upstream_archive"]),
               "generation_settings": settings, "seed": config["dataset_seed"],
               "source_keys": groups, "source_cases": len(groups), "tasks": len(public_rows),
               "additional_generated_source_cases": count, "preselected_source_case_ids": selected_ids,
               "actual_terminal_task_ids_by_family": FAMILIES,
               "input_packet_sha256": sha(packet_path),
               "original_generator_unmodified": True, "official_test_opened": False,
               "inference_inputs_are_exact_original_Task_prompt": True}
    RunStore.immutable_json(packet_path.parent / "preselection.json", receipt)
    return receipt


def answer_schema(family):
    """Both arms use the same task adapter and legal result types.

    Original assets/citations are NOT inferred from hidden targets to constrain
    output. No extra rationale or skill self-report precedes the task answer.
    """
    if family == "EC":
        entry = {"type": "string"}
    elif family == "EV":
        entry = {"type": "object", "additionalProperties": False,
                 "required": ["citation", "claim_value"], "properties": {
                     "citation": {"type": "string"}, "claim_value": {"type": "number"}}}
    else:
        raise ValueError("Only the predeclared EC/EV tasks are supported")
    return {"type": "object", "additionalProperties": {"type": "array", "items": entry}}


def evaluate(row, answer, target):
    """Invoke the pinned native evaluator; no new semantic judge or target edits."""
    Evaluator = upstream("evaluator").Evaluator
    TaskID = upstream("source.task_id").TaskID
    logger = logging.getLogger("openexempt_official_scoring")
    logger.disabled = True
    evaluator = Evaluator([])  # EC/EV scoring does not require private case/solver data.
    uid = f"{row['case_id']}_{row['family']}"
    result = evaluator.evaluate(
        TaskID(FAMILIES[row["family"]]),
        [{"uid": uid, "prediction": json.dumps(answer, ensure_ascii=False)}],
        [{"uid": uid, "target": target}], [None], logger)
    if not all(math.isfinite(result[key]) for key in ("precision", "recall", "f1")):
        raise ValueError("Nonfinite official score; never replace it with a fabricated value")
    # The unchanged official macro scorer visits target asset keys only. Expose
    # all predicted claims outside that traversal; never silently call them safe.
    ignored, full_output = {}, {}
    if isinstance(answer, dict) and not result["invalid_format"]:
        normalized = {k.strip().lower(): v for k, v in answer.items()}
        matched = {evaluator._find_matching_asset_description(k.strip().lower(), list(normalized))
                   for k in target}
        ignored = {k: len(v) for k, v in normalized.items() if k not in matched and v}
        if row["family"] == "EV":
            Claim = upstream("source.pydantic_response").Claim
            used, tp, fp, fn = set(), 0, 0, 0
            for key, claims in target.items():
                match = evaluator._find_matching_asset_description(key.strip().lower(), list(normalized))
                predicted = normalized[match] if match is not None and match not in used else []
                if match is not None:
                    used.add(match)
                _, recall, _, _ = evaluator._compute_precision_recall_f1_mare_scores(
                    [Claim(**v) for v in predicted], [Claim(**v) for v in claims])
                correct = round(recall * len(claims))
                tp += correct
                fp += len(predicted) - correct
                fn += len(claims) - correct
            fp += sum(len(v) for k, v in normalized.items() if k not in used)
            precision, recall, f1 = evaluator._precision_recall_f1_from_outcomes(tp, fp, fn)
            full_output = {"full_output_f1": f1, "full_output_precision": precision,
                           "full_output_recall": recall, "full_output_claim_tp": tp,
                           "full_output_claim_fp": fp, "full_output_claim_fn": fn,
                           "secondary_all_claim_micro_within_case_not_original_macro_F1": True}
    if row["family"] == "EV" and not full_output:
        full_output = {"full_output_f1": 0.0}
    return {**result, "exact_target": answer == target,
            **full_output,
            "officially_unscored_predicted_claims": sum(ignored.values()),
            "officially_unscored_predicted_assets": ignored,
            "official_evaluator_commit": COMMIT}


def metrics(records):
    """Mean native per-case F1, separately per legal task; not ContractNLI F1."""
    result = {}
    for family in FAMILIES:
        rows = [r for r in records if r["family"] == family]
        if not rows:
            continue
        result[family] = {k: sum(r["score"][k] for r in rows) / len(rows)
                          for k in ("precision", "recall", "f1", "exact_target")}
        result[family]["tasks"] = len(rows)
        result[family]["invalid_format"] = sum(r["score"]["invalid_format"] for r in rows)
        result[family]["officially_unscored_predicted_claims"] = sum(
            r["score"].get("officially_unscored_predicted_claims", 0) for r in rows)
        if family == "EV":
            result[family]["full_output_f1"] = sum(
                r["score"].get("full_output_f1", r["score"]["f1"]) for r in rows) / len(rows)
    result["mean_family_f1"] = sum(v["f1"] for v in result.values()) / len(result) if result else 0
    return result
