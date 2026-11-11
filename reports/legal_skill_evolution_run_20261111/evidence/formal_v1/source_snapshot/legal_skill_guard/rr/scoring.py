"""Task scoring is separate from certificate and system status."""
from __future__ import annotations

from collections import defaultdict, Counter
from statistics import mean
from typing import Any

from .coverage import digest
from .ledger import DATASETS

LABELS = {"SARA_v2_Binary": {"Entailment", "Contradiction"},
          "ProofWriter_OWA_depth5": {"True", "False", "Unknown"},
          "ContractNLI": {"Entailment", "Contradiction", "NotMentioned"}}


def task_score(dataset: str, answer: Any, target: Any, *, family: str | None = None) -> dict:
    if dataset not in DATASETS:
        raise ValueError("Unknown benchmark")
    if dataset in LABELS:
        valid = isinstance(answer, str) and answer in LABELS[dataset]
        if target not in LABELS[dataset]:
            raise ValueError("Invalid grading label")
        return {"valid": valid, "correct": valid and answer == target, "metric": "accuracy"}
    if dataset == "RuleArena_Airline":
        valid = type(answer) is int and answer >= 0
        if type(target) is not int or target < 0:
            raise ValueError("Expected original Airline total cost")
        return {"valid": valid, "correct": valid and answer == target, "metric": "exact_match"}
    import jsonschema
    from fractions import Fraction
    from legal_skill_guard.openexempt import answer_schema
    if family not in {'EC', 'EV'}:
        raise ValueError('OE scoring requires its native view')
    def valid(value):
        try:
            jsonschema.validate(value, answer_schema(family))
            return True
        except jsonschema.ValidationError:
            return False
    if not valid(target):
        raise ValueError('Invalid native OE grading mapping')
    ok = valid(answer)
    def mapping(value):
        return {asset: Counter(claims if family == 'EC' else
                [(c['citation'], Fraction(str(c['claim_value']))) for c in claims])
                for asset, claims in value.items()}
    return {'valid': ok, 'correct': ok and mapping(answer) == mapping(target),
            'metric': 'complete_mapping_exact_match'}


def official_openexempt_metrics(family: str, answer: dict, target: dict) -> dict:
    import jsonschema

    from legal_skill_guard.openexempt import answer_schema, evaluate
    if family not in {"EC", "EV"}:
        raise ValueError("OE view must be EC or EV")
    try:
        jsonschema.validate(answer, answer_schema(family))
    except jsonschema.ValidationError:
        return {"status": "native_format_rejection", "metrics": None}
    try:
        result = evaluate({"family": family, "case_id": "rr_score_only"}, answer, target)
    except ValueError as exc:
        # Native all-negative cases may have undefined F1. Preserve that state,
        # rather than inventing 0/1 or dropping the sample from main accuracy.
        if "Nonfinite official score" in str(exc):
            return {"status": "native_metric_undefined", "metrics": None}
        raise
    return {"status": "scored", "metrics": result}


def aggregate(records: list[dict], *, expected_outputs: set[tuple[str, str, str]]) -> dict:
    """Average views within sources, then sources within benchmark, then 5-way macro.

    Every manifest output is required, including failures and fallbacks.
    """
    grouped = defaultdict(list)
    seen = set()
    stable_count = stable_wrong = answered = 0
    for record in records:
        if record["dataset"] not in DATASETS:
            raise ValueError("Unknown benchmark")
        key = record["dataset"], record["source"], record["view"]
        if key in seen:
            raise ValueError("Duplicate answer record")
        seen.add(key)
        correct = record["correct"]
        if type(correct) is not bool:
            raise ValueError("Task correctness must include failures as False")
        grouped[key[:2]].append(int(correct))
        answered += bool(record["answered"])
        if record["certificate_status"] == "completion_stable":
            stable_count += 1
            stable_wrong += not correct
    if seen != expected_outputs:
        raise ValueError("Records differ from the prediction manifest; failures cannot be dropped")
    by_dataset = defaultdict(list)
    for (dataset, _), values in grouped.items():
        by_dataset[dataset].append(mean(values))
    scores = {d: mean(v) for d, v in by_dataset.items()}
    return {"by_dataset": scores, "five_benchmark_macro": mean(scores.values())
            if set(scores) == set(DATASETS) else None,
            "source_counts": {d: len(v) for d, v in by_dataset.items()},
            "outputs": len(records), "answered": answered,
            "answer_coverage": answered / len(records) if records else 0,
            "stable_outputs": stable_count,
            "stable_coverage": stable_count / len(records) if records else 0,
            "stable_but_wrong_rate": stable_wrong / stable_count if stable_count else None}
