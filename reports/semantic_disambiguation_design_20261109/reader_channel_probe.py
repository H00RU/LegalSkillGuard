"""Finite symbolic reader-error prototype; every observation is synthetic.

Implements operator induction, joint interpretation/channel inference, and
the non-identifiability counterexample. No NLP ability or real gains claimed.
"""
import itertools
import json
from pathlib import Path

ROLES = ("work.activity", "payment.medium")
# Each tuple says which role the reader actually uses for the requested role.
OPERATORS = {
    "identity": (0, 1),
    "work_reads_payment": (1, 1),
    "payment_reads_work": (0, 0),
    "swap_roles": (1, 0),
}


def predict(state, operator):
    return tuple(state[j] for j in OPERATORS[operator])


def induce(traces):
    scores = {}
    for name, mapping in OPERATORS.items():
        errors = sum(predict(truth, name) != tuple(observed) for truth, observed in traces)
        edits = sum(j != i for i, j in enumerate(mapping))
        scores[name] = (errors, edits)
    # Lexicographic minimization is a tiny demonstrator, not a fitted likelihood.
    best = min(scores.values())
    return [name for name, score in scores.items() if score == best], scores


def compatible_pairs(states, channels, observed, trusted_anchors=()):
    result = []
    for state in states:
        if any(state[role] != value for role, value in trusted_anchors):
            continue
        for channel in channels:
            if predict(state, channel) == tuple(observed):
                result.append((state, channel))
    return result


def answer_or_unknown(pairs):
    # Toy query asks about work.activity; never a real legal answer.
    answers = {state[0] for state, _ in pairs}
    return next(iter(answers)) if len(answers) == 1 else None


def main():
    traces = [((0, 1), (1, 1)), ((1, 0), (0, 0))]
    learned, scores = induce(traces)
    assert learned == ["work_reads_payment"]
    # New value identities show symbolic copying, not benchmark generalization.
    heldout_state = ("repairing a roof", "paying with hay")
    assert predict(heldout_state, learned[0]) == ("paying with hay", "paying with hay")

    states = list(itertools.product((0, 1), repeat=2))
    # Retain identity too: learning a tendency must not assert it occurs always.
    channels = ["identity", learned[0]]
    without_anchor = compatible_pairs(states, channels, (1, 1))
    assert ((0, 1), "work_reads_payment") in without_anchor
    assert ((1, 1), "identity") in without_anchor
    assert answer_or_unknown(without_anchor) is None
    # Trusted anchor is supplied BY THE FIXTURE AUTHOR, not magically inferred
    # from a verbatim citation or a second question to the same model.
    with_anchor = compatible_pairs(states, channels, (1, 1), [(0, 0)])
    assert answer_or_unknown(with_anchor) == 0
    # Missing correct channel must be exposed, never silently assigned identity.
    impossible = compatible_pairs([(0, 1)], channels, (1, 0))
    assert impossible == []
    result = {
        "model_calls": 0,
        "source_of_all_labels": "author-constructed finite fixtures",
        "learned_operator": learned,
        "operator_scores": scores,
        "heldout_symbolic_value_prediction": predict(heldout_state, learned[0]),
        "without_trusted_anchor": {"pairs": without_anchor, "answer": answer_or_unknown(without_anchor)},
        "with_fixture_author_trusted_anchor": {"pairs": with_anchor, "answer": answer_or_unknown(with_anchor)},
        "missing_channel_detected_as_unexplained": impossible == [],
        "new_source_semantic_accuracy_measured": False,
        "novelty_established": False,
        "necessary_next_evidence": "learn operators and discriminating anchors from real TRAIN-only traces, then evaluate on excluded original sources against equal-information error models",
    }
    Path(__file__).with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"learned": learned, "unidentifiable_without_anchor": answer_or_unknown(without_anchor) is None,
                      "model_calls": 0, "real_efficacy_claimed": False}))


if __name__ == "__main__":
    main()
