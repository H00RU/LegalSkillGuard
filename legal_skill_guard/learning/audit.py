"""Independent original-membership audit recovered from the Oct13 auditor."""

import json
import math

from jsonschema import validate

CLASSES = ["Entailment", "Contradiction", "NotMentioned"]


def close(expected, actual):
    if type(expected) is bool or expected is None or isinstance(expected, str):
        assert expected == actual, (expected, actual)
    elif isinstance(expected, (int, float)):
        assert isinstance(actual, (int, float)) and math.isclose(
            expected, actual, rel_tol=1e-12, abs_tol=1e-12
        ), (expected, actual)
    elif isinstance(expected, dict):
        for k, v in expected.items():
            assert k in actual, k
            close(v, actual[k])
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(expected) == len(actual)
        for a, b in zip(expected, actual):
            close(a, b)
    else:
        assert expected == actual


def original_score(response, row, annotations, keys):
    parsed, valid = None, False
    one = {
        "type": "object",
        "additionalProperties": True,
        "required": ["choice", "spans"],
        "properties": {
            "choice": {"type": "string", "enum": CLASSES},
            "spans": {
                "type": "array",
                "items": {"type": "integer", "enum": list(range(len(row["spans"])))},
            },
        },
    }
    try:
        if response["finish_reason"] != "stop":
            raise ValueError("Incomplete original public answer")
        parsed = json.loads(response["content"])
        validate(
            parsed,
            {
                "type": "object",
                "additionalProperties": False,
                "required": keys,
                "properties": {k: one for k in keys},
            },
        )
        valid = True
    except Exception:
        pass
    qq = []
    for k in keys:
        g, p = annotations[k], parsed[k] if valid else None
        gs, ps = set(g["spans"]), set(p["spans"]) if valid else set()
        nn = g["choice"] != "NotMentioned"
        assert g["choice"] in CLASSES and bool(gs) == nn
        assert all(type(s) is int and 0 <= s < len(row["spans"]) for s in gs)
        tp, fp, fn = len(gs & ps), len(ps - gs), len(gs - ps)
        f1 = 2 * tp / (2 * tp + fp + fn) if nn else None
        correct = bool(valid and p["choice"] == g["choice"])
        qq.append(
            {
                "hypothesis_id": k,
                "gold": g,
                "prediction": p,
                "label_correct": correct,
                "gold_non_neutral": nn,
                "evidence_tp": tp,
                "evidence_fp": fp,
                "evidence_fn": fn,
                "evidence_f1_gold_non_neutral": f1,
                "joint_exact": bool(correct and ps == gs),
                "joint_soft": float(correct) * f1 if nn else float(correct and not ps),
            }
        )
    return {"parsed": parsed, "public_valid": valid, "queries": qq}
