"""Finite design check: consumer-preserving relational interface synthesis.

No LLM, natural-language claims, training results, or new-theory claim.
The feature grammar is fixed before enumerating candidates. Decoder tables are
synthesized from the declared finite semantic domain, not supplied per example.
"""
from dataclasses import dataclass
from itertools import combinations, product
import json


@dataclass(frozen=True)
class Event:
    key: str
    start: int
    end: int
    pay: int


@dataclass(frozen=True)
class Feature:
    op: str
    # Human-declared illustrative interface complexity, NOT measured token cost.
    cost: int

    def read(self, event):
        if self.op == 'start_date':
            return event.start
        if self.op == 'end_date':
            return event.end
        if self.op == 'payment_date':
            return event.pay
        if self.op == 'payment_end_order':
            return (event.pay > event.end) - (event.pay < event.end)
        if self.op == 'service_duration':
            return event.end - event.start
        if self.op == 'duration_ge_2':
            return event.end - event.start >= 2
        raise ValueError(self.op)


GRAMMAR = (
    Feature('start_date', 3), Feature('end_date', 3),
    Feature('payment_date', 3), Feature('payment_end_order', 1),
    Feature('service_duration', 2), Feature('duration_ge_2', 1),
)


def encode(world, features, anchored=True):
    records = tuple((event.key, tuple(feature.read(event) for feature in features))
                    for event in world)
    if anchored:
        return records
    # Deliberately unsafe grammar option: erase event identity and sort values.
    return tuple(sorted(record[1] for record in records))


def legal_output(world, *, require_duration=False):
    # Multiple query results; no target label is included in the reading grammar.
    return tuple((e.key, e.pay > e.end, e.pay == e.end,
                  *((e.end-e.start >= 2,) if require_duration else ()))
                 for e in world)


def compile_decoder(worlds, features, *, require_duration=False, anchored=True):
    table, witness = {}, {}
    for w in worlds:
        encoded = encode(w, features, anchored)
        output = legal_output(w, require_duration=require_duration)
        if encoded in table and table[encoded] != output:
            return None, {'world_1': witness[encoded], 'world_2': w,
                          'output_1': table[encoded], 'output_2': output}
        table[encoded] = output
        witness[encoded] = w
    return table, None


def enumerate_interfaces(worlds, require_duration=False):
    accepted, rejected = [], 0
    for width in range(1, len(GRAMMAR)+1):
        for features in combinations(GRAMMAR, width):
            table, counterexample = compile_decoder(
                worlds, features, require_duration=require_duration)
            if counterexample is None:
                accepted.append((sum(f.cost for f in features),
                                 tuple(f.op for f in features), table))
            else:
                rejected += 1
    accepted.sort(key=lambda row: (row[0], len(row[1]), row[1]))
    return accepted, rejected


def answer_set(worlds, features, decoder):
    # Exact relational image of the SAME admissible world set. Do not take the
    # Cartesian product of uncertain coordinates and claim it is exact.
    return {decoder[encode(w, features)] for w in worlds}


def run_checks():
    # Forty local finite states: end >= start, while payment can be before or after.
    states = [(s, e, p) for s, e, p in product(range(4), repeat=3) if s <= e]
    worlds = [tuple(Event(key, *state) for key, state in zip(('A', 'B'), pair))
              for pair in product(states, repeat=2)]
    after, reject_after = enumerate_interfaces(worlds)
    duration, reject_duration = enumerate_interfaces(worlds, require_duration=True)
    order = (next(f for f in GRAMMAR if f.op == 'payment_end_order'),)
    assert after[0][1] == ('payment_end_order',)
    assert set(duration[0][1]) == {'payment_end_order', 'duration_ge_2'}
    table, witness = compile_decoder(worlds, order)
    assert witness is None
    bad, duration_witness = compile_decoder(worlds, order, require_duration=True)
    assert bad is None and duration_witness is not None
    bad, binding_witness = compile_decoder(worlds, order, anchored=False)
    assert bad is None and binding_witness is not None

    # Exact dates remain unknown at compile time. Each state is enumerated;
    # therefore ordinary constant substitution cannot remove both date inputs.
    w1 = (Event('A', 0, 0, 1), Event('B', 0, 0, 0))
    w2 = (Event('A', 0, 2, 3), Event('B', 0, 0, 0))
    assert w1 != w2 and encode(w1, order) == encode(w2, order)
    assert legal_output(w1) == legal_output(w2)
    # Same encoding maps to different original dates: no inverse to original ABI.
    assert w1[0].end != w2[0].end and w1[0].pay != w2[0].pay
    completions = [w1, w2]
    exact = answer_set(completions, order, table)
    native = {legal_output(w) for w in completions}
    assert exact == native and len(exact) == 1
    independent = [
        (Event('A', 0, end, pay), w1[1])
        for end, pay in product({0, 2}, {1, 3})
    ]
    cartesian = answer_set(independent, order, table)
    assert len(cartesian) > len(exact)

    return {
        'status': 'finite_semantic_core_checked_not_empirical_validation',
        'local_event_states': len(states), 'two_event_worlds': len(worlds),
        'candidate_feature_subsets': 2**len(GRAMMAR)-1,
        'after_valid_candidates': len(after), 'after_rejected_candidates': reject_after,
        'duration_valid_candidates': len(duration), 'duration_rejected_candidates': reject_duration,
        'after_min_illustrative_cost_interface': list(after[0][1]),
        'duration_min_illustrative_cost_interface': list(duration[0][1]),
        'cost_is_measured_reader_cost': False,
        'order_encoding_is_noninvertible': True,
        'order_only_rejected_when_duration_needed': True,
        'event_identity_erasure_rejected': True,
        'partial_world_relational_lifting_preserves_answer_set': True,
        'independent_cartesian_lifting_introduces_spurious_answers': True,
        'actual_reader_performance_tested': False,
        'model_calls': 0,
    }


if __name__ == '__main__':
    print(json.dumps(run_checks(), ensure_ascii=False, indent=2))
