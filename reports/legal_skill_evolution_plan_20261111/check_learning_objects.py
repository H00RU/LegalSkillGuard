"""Finite algorithm checks. Fixtures are exact, not model or native task results."""
import itertools
import json
from pathlib import Path


def candidate_blocks(records, anchor, max_units=3):
    """Use local semantic records, never merge by the final return node."""
    blocks = {frozenset([anchor])}
    for record in records:
        if anchor in record and len(record) <= max_units:
            blocks.add(frozenset(record))
    return sorted(blocks, key=lambda x: (len(x), sorted(x)))


def lift_bindings(old_values, block, observed_record, use_sites):
    values = dict(old_values)
    for unit in block:
        if unit not in observed_record:
            raise ValueError("unknown premise; no invented completion")
        values[unit] = observed_record[unit]
    return {site: values[unit] for unit, sites in use_sites.items() for site in sites}


def minimal_bundles(scores, historical, baseline):
    """Scores are equal-weight means within the same fixed source cohort."""
    accepted = []
    for mask in scores:
        preserves = all(a >= b for a, b in zip(historical[mask], historical[baseline]))
        improves = sum(scores[mask]) > sum(scores[baseline])
        if preserves and improves:
            accepted.append(frozenset(i for i, bit in enumerate(mask) if bit))
    return [b for b in accepted if not any(a < b for a in accepted)]


class RevisionMemory:
    def __init__(self):
        self.entries = {}

    def observe(self, signature, label, source_id):
        if label not in {"joint_needed", "single_sufficient", "harmful_or_unresolved"}:
            raise ValueError(label)
        # Repeated execution views must not inflate independent support.
        self.entries.setdefault(signature, {})[source_id] = label

    def priority(self, signature):
        if signature not in self.entries:
            return None
        labels = list(self.entries[signature].values())
        return (labels.count("joint_needed") + 1) / (len(labels) + 3)


def main():
    checks = []
    records = [{"cap", "scope"}, {"clock", "duration"}]
    blocks = candidate_blocks(records, "cap")
    assert blocks == [frozenset({"cap"}), frozenset({"cap", "scope"})]
    checks.append("coupled candidates exclude unrelated final-output dependencies")
    bound = lift_bindings({"cap": 100, "scope": "basic"}, {"cap", "scope"},
                          {"cap": 60, "scope": "total"},
                          {"cap": ["a.limit", "audit.limit"], "scope": ["a.basis"]})
    assert bound == {"a.limit": 60, "audit.limit": 60, "a.basis": "total"}
    checks.append("one lifted premise binds every declared use consistently")
    try:
        lift_bindings({"cap": 100}, {"cap"}, {}, {"cap": ["x"]})
    except ValueError:
        checks.append("missing premise remains unresolved")
    else:
        raise AssertionError("invented missing field")
    facts = list(itertools.product([False, True], repeat=3))
    scores = {}
    for p, q in itertools.product([0, 1], repeat=2):
        rows = []
        for a, s, c in facts:
            mid = a if p else a and not s
            answer = (mid and (not s or c)) if q else (mid or (s and c))
            rows.append(int(answer == (a and (not s or c))))
        scores[(p, q)] = rows
    historical = {mask: [1] for mask in scores}
    assert minimal_bundles(scores, historical, (0, 0)) == [frozenset({0, 1})]
    checks.append("joint block found despite no strictly improving singleton")
    singleton_scores = {(0, 0): [0], (1, 0): [1], (0, 1): [0], (1, 1): [1]}
    assert minimal_bundles(singleton_scores, historical, (0, 0)) == [frozenset({0})]
    checks.append("single sufficient edit is not relabeled necessary joint repair")
    memory = RevisionMemory()
    sig = ("preliminary_qualification", "consumer_bypass", "exception_requires_base")
    memory.observe(sig, "joint_needed", "source_a")
    before = memory.priority(sig)
    memory.observe(sig, "joint_needed", "source_a")
    assert memory.priority(sig) == before
    checks.append("repeated views do not inflate cross-source support")
    memory.observe(sig, "single_sufficient", "source_b")
    assert memory.priority(sig) < before
    checks.append("contradictory transfer evidence lowers joint-pattern priority")
    assert memory.priority(("different_subject", "consumer_bypass", "unknown")) is None
    checks.append("unobserved legal context does not inherit a hard dependency")
    result = {"kind": "finite algorithm fixture checks", "model_calls": 0,
              "server_changes": False, "native_performance_claim": False,
              "passed": len(checks), "checks": checks}
    Path(__file__).with_name("LEARNING_OBJECTS_CHECK.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
