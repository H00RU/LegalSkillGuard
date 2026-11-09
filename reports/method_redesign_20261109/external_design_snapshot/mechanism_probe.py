"""Offline design probe, never an LLM/benchmark efficacy experiment.

Historical checks use preserved source text. All candidate/question/reader
tables below are explicitly constructed fixtures. No model or network calls.
"""
from __future__ import annotations

import itertools
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent / "audit_final_repo"
sys.path.insert(0, str(REPO))
from legal_skill_guard.rr.grounding import binding_literal_audit
from legal_skill_guard.rr.source_bindings import decode_source_bindings


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def historical_blind_spot():
    public = load(ROOT.parent / "audit7_public_train.json")["sources"]
    src = next(s for s in public if s["key"].endswith(
        "1bb6328a07dda2ef71c58892c5c62e7cd99422123d9480d08c8e79130eb681ff"))
    from legal_skill_guard.rr.source_structure import inspect_source
    st = inspect_source(src)
    units = {c.id: st.ledger.text[c.start:c.end] for c in st.ledger.clauses}
    text = units["s320"]
    injected = {"name": "blender_value", "type": "integer", "value": 95,
                "sources": ["s320"]}
    slots, covered, checks = decode_source_bindings([injected], units)
    assert all(c["pass"] for c in checks)
    assert "115" in text and "95" in text
    run = REPO / "artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109"
    record = load(run / "dev/predictions/M11/96b6e8a08da8750d9d98fc0ae5abb5a919c5cf95e4e8a3a4da688a6821092441.json")
    p = record["prediction"]
    return {"OE_source": src["key"], "OE_fact_text": text,
            "injected_wrong_binding": injected, "old_decoder_accepted": True,
            "injection_is_not_a_historical_model_error": True,
            "SARA_historical_observation_rows": p.get("observation_rows"),
            "SARA_historical_answer": p["result"]["answer"],
            "SARA_historical_certificate_status": p["result"]["certificate_status"],
            "DEV_used_only_as_historical_failure_evidence": True}


def minimal_support(rows, fields):
    """All inclusion-minimal supports consistent with a finite labelled table.

    This is standard finite functional-dependency inference, not new theory.
    Unidentified supports are retained, never selected by a lucky ordering.
    """
    accepted = []
    for n in range(len(fields) + 1):
        for ss in itertools.combinations(fields, n):
            if any(set(old).issubset(ss) for old in accepted):
                continue
            lookup = {}
            valid = True
            for row in rows:
                key = tuple(row[f] for f in ss)
                if key in lookup and lookup[key] != row["target"]:
                    valid = False
                    break
                lookup[key] = row["target"]
            if valid:
                accepted.append(ss)
    return accepted


@dataclass(frozen=True)
class Question:
    name: str
    group: str
    cost: int
    answers: tuple


def group_distance(h1, h2, selected):
    return len({q.group for q in selected if q.answers[h1] != q.answers[h2]})


def minimum_separating_set(questions, answer_classes, error_groups):
    """Exact tiny-pool cost search under a bounded group-error model.

    Distances use groups, so repeated paraphrases are not independent votes.
    The >2b condition is ordinary coding theory; novelty is not asserted here.
    """
    relevant = [(i, j) for i in range(len(answer_classes))
                for j in range(i) if answer_classes[i] != answer_classes[j]]
    if not relevant:
        return []
    best = None
    for n in range(len(questions) + 1):
        for subset in itertools.combinations(questions, n):
            if all(group_distance(i, j, subset) > 2 * error_groups for i, j in relevant):
                rank = (sum(q.cost for q in subset), len(subset), tuple(q.name for q in subset))
                if best is None or rank < best[0]:
                    best = rank, subset
    return None if best is None else list(best[1])


def decode(questions, observed, answer_classes, error_groups):
    survivors = []
    conflicts = {}
    for h in range(len(answer_classes)):
        bad = {q.group for q in questions
               if observed.get(q.name) is not None and observed[q.name] != q.answers[h]}
        conflicts[str(h)] = sorted(bad)
        if len(bad) <= error_groups:
            survivors.append(h)
    answers = {answer_classes[h] for h in survivors}
    return {"survivors": survivors, "conflict_groups": conflicts,
            "answer": next(iter(answers)) if len(answers) == 1 else None,
            "status": "resolved_conditionally" if len(answers) == 1 else
                      "empty_version_space" if not survivors else "unresolved"}


def fixture_probe():
    # Label truth below is specified by the fixture author. It is not teacher
    # output, automatic NL understanding, or evidence of real-world transfer.
    fields = ("work_is_agricultural", "payment_is_agricultural")
    confounded = [{fields[0]: a, fields[1]: a, "target": a} for a in (False, True)]
    factorial = [{fields[0]: a, fields[1]: b, "target": a}
                 for a, b in itertools.product((False, True), repeat=2)]
    before = minimal_support(confounded, fields)
    after = minimal_support(factorial, fields)
    assert len(before) == 2 and after == [(fields[0],)]

    # Deliberately easy coding example. Two interpretations, two task answers;
    # q1..q3 are three wordings sharing ONE possible failure mechanism.
    qs = [Question("q1", "same_role_confusion", 1, (0, 1)),
          Question("q2", "same_role_confusion", 1, (0, 1)),
          Question("q3", "same_role_confusion", 1, (0, 1)),
          Question("q4", "independent_fixture_relation_B", 2, (0, 1)),
          Question("q5", "independent_fixture_relation_C", 2, (0, 1))]
    labels = ("answer_A", "answer_B")
    chosen = minimum_separating_set(qs, labels, 1)
    assert chosen is not None and len(chosen) == 3
    assert len({q.group for q in chosen}) == 3
    observed = {q.name: (1 if q.group == "same_role_confusion" else 0) for q in qs}
    decoded = decode(qs, observed, labels, 1)
    assert decoded["answer"] == "answer_A"
    majority = "answer_B" if sum(observed.values()) > len(qs)/2 else "answer_A"
    assert majority == "answer_B"
    no_independent_evidence = minimum_separating_set(qs[:3], labels, 1)
    assert no_independent_evidence is None
    abstained = decode(qs[:3], observed, labels, 1)
    assert abstained["answer"] is None

    # All legal corruptions in this fixture, under the stated error assumption.
    checks = 0
    for true_h in (0, 1):
        groups = sorted({q.group for q in qs})
        for corrupt in [None] + groups:
            active = [q for q in qs if q.group == corrupt]
            for replacement in itertools.product((0, 1), repeat=len(active)):
                obs = {q.name: q.answers[true_h] for q in qs}
                obs.update({q.name: value for q, value in zip(active, replacement)})
                got = decode(qs, obs, labels, 1)
                assert true_h in got["survivors"] and got["answer"] == labels[true_h]
                checks += 1

    # Exceed the declared fault model: there is deliberately no false guarantee.
    exceeded = {q.name: (0 if q.group == "independent_fixture_relation_C" else 1) for q in qs}
    outside = decode(qs, exceeded, labels, 1)
    assert outside["answer"] == "answer_B"
    return {"scope": "constructed finite fixtures, not dataset or model outcomes",
            "support_candidates_before_independent_variation": before,
            "support_candidates_after_independent_variation": after,
            "known_role_pointer_baseline_also_solves_this_fixture": True,
            "selected_question_names": [q.name for q in chosen],
            "group_distance": group_distance(0, 1, chosen),
            "naive_majority_fixture_answer": majority,
            "group_aware_fixture_result": decoded,
            "all_one_fault_group_fixture_cases_checked": checks,
            "only_repeated_evidence_result": abstained,
            "no_separating_set_without_distinct_evidence": no_independent_evidence is None,
            "outside_fault_assumption_can_answer_wrong": outside,
            "standard_group_noise_baseline_is_same_decoder": True}


if __name__ == "__main__":
    result = {"network_calls": 0, "model_calls": 0,
              "historical_code_commit": "6c2f2a5dce7e9e78c6aae6ccc000a3eb769f99c2",
              "historical_blind_spot": historical_blind_spot(),
              "algorithm_fixture": fixture_probe(),
              "establishes_novelty_or_real_model_improvement": False}
    (ROOT / "mechanism_probe_results.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"model_calls": 0,
        "wrong_numeric_binding_passes_old_check": result["historical_blind_spot"]["old_decoder_accepted"],
        "synthetic_algorithm_checks": result["algorithm_fixture"]["all_one_fault_group_fixture_cases_checked"],
        "novelty_or_LLM_efficacy_established": False}, ensure_ascii=False))
