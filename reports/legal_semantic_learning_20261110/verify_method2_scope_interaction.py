"""Exact verification of the proposed scope-interaction training targets.

This checks the finite construction and algebra, not learned-model performance.
"""
from fractions import Fraction
from itertools import product
import json
from pathlib import Path


def evaluate(atoms, first_swap, second_swap):
    u, v, w, z = atoms
    if first_swap:
        u, w = w, u
    if second_swap:
        v, z = z, v
    return int(((u and v) or w) and z)


def difference(values):
    return values[3] - values[2] - values[1] + values[0]


def center(values):
    values = list(map(Fraction, values))
    rows = [(values[0] + values[1]) / 2, (values[2] + values[3]) / 2]
    cols = [(values[0] + values[2]) / 2, (values[1] + values[3]) / 2]
    grand = sum(values) / 4
    return [values[2*a+b] - rows[a] - cols[b] + grand
            for a, b in product(range(2), repeat=2)]


def main():
    squares, identities, nonzero = 0, 0, 0
    for atoms in product((False, True), repeat=4):
        outputs = [evaluate(atoms, a, b) for a, b in product(range(2), repeat=2)]
        interaction = difference(outputs)
        squares += 1
        nonzero += int(interaction != 0)
        for gold_index in range(4):
            y = outputs[gold_index]
            losses = [abs(value - y) for value in outputs]
            directed = difference(losses)
            assert directed == (1 - 2*y) * interaction
            target = center([-value for value in losses])
            delta = -Fraction(directed, 4)
            assert target == [delta, -delta, -delta, delta]
            assert target[0] + target[1] == target[2] + target[3] == 0
            assert target[0] + target[2] == target[1] + target[3] == 0
            identities += 1
    example = (True, False, False, True)
    outputs = [evaluate(example, a, b) for a, b in product(range(2), repeat=2)]
    assert outputs == [0, 0, 1, 0]
    losses = [abs(value - outputs[2]) for value in outputs]
    result = {
        "status": "deterministic_algebra_and_scope_example_only",
        "fact_assignments": squares,
        "gold_conditioned_identities_checked": identities,
        "assignments_with_nonzero_interaction": nonzero,
        "example_outputs_00_01_10_11": outputs,
        "example_gold_index": "10",
        "example_losses": losses,
        "example_directed_interaction": difference(losses),
        "example_centered_negative_loss": list(map(str, center([-v for v in losses]))),
        "all_assertions_passed": True,
    }
    Path(__file__).with_name("method2_scope_interaction_result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
