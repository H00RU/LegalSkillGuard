"""Deterministic audit of partial semantic fragment induction.

No LLM, native held-out label, external solver, or remote mutation is used.
The strong comparator is an independently evaluated finite CSP relation projected
onto a fragment and followed by canonical semantic compression. It is NOT Stitch.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from itertools import product, combinations
from pathlib import Path
import hashlib
import json
import time
from typing import Any


Expr = tuple


def Var(name): return ("var", name)
def Const(value): return ("const", bool(value))
def Not(expr): return ("not", expr)
def And(a, b): return ("and", a, b)
def Or(a, b): return ("or", a, b)
def Ite(c, a, b): return ("ite", c, a, b)
def Call(name, *args): return ("call", name, tuple(args))
def Unknown(name, *args): return ("unknown", name, tuple(args))


def digest(obj):
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def domain(roles):
    return tuple(product((False, True), repeat=len(roles)))


@dataclass(frozen=True)
class Clause:
    name: str
    roles: tuple[str, ...]
    body: Expr


@dataclass(frozen=True)
class Program:
    clauses: tuple[Clause, ...]
    # Reader-map belongs only to natural-language training execution. Exported
    # public clause ports always use their declared legal names, not this map.
    reader_map: tuple[int, ...] = ()

    def lookup(self, name):
        return next(c for c in self.clauses if c.name == name)


@dataclass(frozen=True)
class Observation:
    fragment: str
    values: tuple[bool, ...]
    label: bool
    through_reader: bool = False


@dataclass(frozen=True)
class Hypothesis:
    program: Program
    # Every uninterpreted function receives one total truth table, shared across
    # all its invocations. Repeated equal arguments cannot get independent values.
    unknown_tables: tuple[tuple[str, tuple[bool, ...]], ...]

    def world(self):
        return dict(self.unknown_tables)


@dataclass(frozen=True)
class Source:
    name: str
    grammar: tuple[Program, ...]
    unknown_signatures: tuple[tuple[str, int], ...] = ()
    observations: tuple[Observation, ...] = ()
    # Supplied finite source boundary; no claim of automatic text completeness.
    closed_fragments: tuple[str, ...] = ()
    role_anchors: tuple[tuple[int, int], ...] = ()
    revision: int = 1

    @property
    def fingerprint(self):
        return digest(asdict(self))


@dataclass(frozen=True)
class Certificate:
    source: str
    fingerprint: str
    fragment: str
    roles: tuple[str, ...]
    truth: tuple[bool, ...]
    candidate_count: int


def scalar_expr(expr, env, program, world, stack=()):
    op = expr[0]
    if op == "var": return env[expr[1]]
    if op == "const": return expr[1]
    if op == "not": return not scalar_expr(expr[1], env, program, world, stack)
    if op == "and":
        return scalar_expr(expr[1], env, program, world, stack) and scalar_expr(expr[2], env, program, world, stack)
    if op == "or":
        return scalar_expr(expr[1], env, program, world, stack) or scalar_expr(expr[2], env, program, world, stack)
    if op == "ite":
        condition = scalar_expr(expr[1], env, program, world, stack)
        return scalar_expr(expr[2 if condition else 3], env, program, world, stack)
    if op == "call":
        name, arguments = expr[1:]
        if name in stack: raise ValueError("Recursive calls are outside the finite DAG DSL")
        clause = program.lookup(name)
        values = tuple(scalar_expr(a, env, program, world, stack) for a in arguments)
        if len(values) != len(clause.roles): raise ValueError("Call arity mismatch")
        return scalar_expr(clause.body, dict(zip(clause.roles, values)), program, world, stack + (name,))
    if op == "unknown":
        name, arguments = expr[1:]
        values = tuple(scalar_expr(a, env, program, world, stack) for a in arguments)
        index = sum(int(value) << (len(values) - 1 - i) for i, value in enumerate(values))
        return world[name][index]
    raise ValueError(op)


def scalar_eval(h, fragment, values, through_reader=False):
    clause = h.program.lookup(fragment)
    if through_reader and h.program.reader_map:
        values = tuple(values[i] for i in h.program.reader_map)
    return scalar_expr(clause.body, dict(zip(clause.roles, values)), h.program, h.world(), (fragment,))


def expand_version_space(source):
    """Exact finite grammar product and constraint filtering, never top-k."""
    worlds_per_name = [(name, tuple(product((False, True), repeat=2 ** arity)))
                       for name, arity in source.unknown_signatures]
    completions = tuple(product(*(tables for _, tables in worlds_per_name)))
    if not worlds_per_name: completions = ((),)
    answers = []
    for program in source.grammar:
        if any(not program.reader_map or program.reader_map[r] != c for r, c in source.role_anchors):
            continue
        for tables in completions:
            h = Hypothesis(program, tuple((worlds_per_name[i][0], table) for i, table in enumerate(tables)))
            if all(scalar_eval(h, o.fragment, o.values, o.through_reader) == o.label
                   for o in source.observations):
                answers.append(h)
    return tuple(answers)


def common_fragment_pool(source):
    """All named source boundaries with identical public role contracts."""
    if not source.grammar: return ()
    first = source.grammar[0]
    result = []
    for clause in first.clauses:
        if clause.name not in source.closed_fragments: continue
        if all(any(c.name == clause.name and c.roles == clause.roles for c in p.clauses)
               for p in source.grammar):
            result.append((clause.name, clause.roles))
    return tuple(result)


def proposed_induce(source):
    """Method 2: representative + exhaustive counterexample search."""
    version_space = expand_version_space(source)
    accepted, rejected = {}, {}
    if not version_space:
        return accepted, {"__source__": {"reason": "inconsistent_or_empty_grammar"}}
    for fragment, roles in common_fragment_pool(source):
        truth = tuple(scalar_eval(version_space[0], fragment, x) for x in domain(roles))
        witness = None
        for i, h in enumerate(version_space[1:], 1):
            for x, ref in zip(domain(roles), truth):
                actual = scalar_eval(h, fragment, x)
                if actual != ref:
                    witness = {"hypothesis": i, "input": x, "reference": ref, "actual": actual}
                    break
            if witness is not None: break
        if witness is None:
            accepted[fragment] = Certificate(source.name, source.fingerprint, fragment, roles, truth, len(version_space))
        else:
            rejected[fragment] = witness
    return accepted, rejected


def vector_expr(expr, env, program, world, mask, stack=()):
    """Independent bit-vector evaluator for the projected-CSP comparator."""
    op = expr[0]
    if op == "var": return env[expr[1]]
    if op == "const": return mask if expr[1] else 0
    if op == "not": return mask ^ vector_expr(expr[1], env, program, world, mask, stack)
    if op == "and": return vector_expr(expr[1], env, program, world, mask, stack) & vector_expr(expr[2], env, program, world, mask, stack)
    if op == "or": return vector_expr(expr[1], env, program, world, mask, stack) | vector_expr(expr[2], env, program, world, mask, stack)
    if op == "ite":
        c = vector_expr(expr[1], env, program, world, mask, stack)
        a = vector_expr(expr[2], env, program, world, mask, stack)
        b = vector_expr(expr[3], env, program, world, mask, stack)
        return (c & a) | ((mask ^ c) & b)
    if op == "call":
        name, arguments = expr[1:]
        if name in stack: raise ValueError("Recursive call")
        child = program.lookup(name)
        values = [vector_expr(a, env, program, world, mask, stack) for a in arguments]
        return vector_expr(child.body, dict(zip(child.roles, values)), program, world, mask, stack + (name,))
    if op == "unknown":
        name, arguments = expr[1:]
        bit_arguments = [vector_expr(a, env, program, world, mask, stack) for a in arguments]
        result = 0
        for value_tuple, output in zip(domain(arguments), world[name]):
            if not output: continue
            matching_rows = mask
            for bits, value in zip(bit_arguments, value_tuple):
                matching_rows &= bits if value else mask ^ bits
            result |= matching_rows
        return result
    raise ValueError(op)


def vector_truth(h, fragment):
    clause = h.program.lookup(fragment)
    rows = domain(clause.roles)
    env = {r: sum(int(row[i]) << j for j, row in enumerate(rows)) for i, r in enumerate(clause.roles)}
    bits = vector_expr(clause.body, env, h.program, h.world(), (1 << len(rows)) - 1, (fragment,))
    return tuple(bool(bits & (1 << j)) for j in range(len(rows)))


def strong_projected_csp(source):
    """Finite relation projection -> singleton test, independent of method 2.

    The relation is the exact finite CSP solution set, represented explicitly here.
    This comparator is not branded as a reimplementation of SmartLabel or Stitch.
    """
    solution_relation = expand_version_space(source)
    if not solution_relation:
        return {}, {"__source__": {"reason": "inconsistent_or_empty_grammar"}}
    accepted, rejected = {}, {}
    for fragment, roles in common_fragment_pool(source):
        projection = {vector_truth(row, fragment) for row in solution_relation}
        if len(projection) == 1:
            truth = next(iter(projection))
            accepted[fragment] = Certificate(source.name, source.fingerprint, fragment, roles, truth, len(solution_relation))
        else:
            rejected[fragment] = {"distinct_projection_rows": len(projection)}
    return accepted, rejected


def pick_first(source):
    vs = expand_version_space(source)
    if not vs: return {}
    return {fragment: Certificate(source.name, source.fingerprint, fragment, roles,
                                 tuple(scalar_eval(vs[0], fragment, x) for x in domain(roles)), len(vs))
            for fragment, roles in common_fragment_pool(source)}


def wait_unique(source):
    """Strong wait baseline: full semantic uniqueness, not AST identity."""
    vs = expand_version_space(source)
    if not vs: return {}
    pool = common_fragment_pool(source)
    whole_semantics = {tuple((fragment, vector_truth(h, fragment)) for fragment, _ in pool) for h in vs}
    return pick_first(source) if len(whole_semantics) == 1 else {}


def canonical_body(roles, truth):
    """Canonical ordered Shannon decomposition; deterministic, not Stitch/MDL."""
    if all(v == truth[0] for v in truth): return Const(truth[0])
    half = len(truth) // 2
    low = canonical_body(roles[1:], truth[:half])
    high = canonical_body(roles[1:], truth[half:])
    if low == high: return low
    return Ite(Var(roles[0]), high, low)


def compress(certificates):
    library = {}
    for certificate in certificates:
        # Distinct named legal roles or domains are never merged by blind renaming.
        key = digest((certificate.roles, domain(certificate.roles), certificate.truth))
        item = library.setdefault(key, {"roles": certificate.roles,
                                       "truth": certificate.truth,
                                       "canonical_body": canonical_body(certificate.roles, certificate.truth),
                                       "members": []})
        item["members"].append((certificate.source, certificate.fragment))
    for item in library.values(): item["members"].sort()
    return library


def certificate_current(cert, source):
    return cert.source == source.name and cert.fingerprint == source.fingerprint


def transfer_allowed(cert, target, target_fragment):
    accepted, _ = strong_projected_csp(target)
    current = accepted.get(target_fragment)
    return current is not None and current.roles == cert.roles and current.truth == cert.truth


def make_scenarios():
    a, b, c = Var("eligible"), Var("exception"), Var("resident")
    roles = ("eligible", "exception", "resident")
    common = And(a, Not(b))
    programs = tuple(Program((Clause("exemption", roles, common), Clause("filing", roles, body)))
                     for body in (And(a, c), Or(a, c)))
    partial = Source("whole_ambiguous_local_unique", programs, closed_fragments=("exemption", "filing"))
    # Both complete grammars agree on all visible observations, but differ off them.
    sample = Source("sample_equal_domain_different",
                    tuple(Program((Clause("rule", ("p", "q"), body),))
                          for body in (And(Var("p"), Var("q")), Or(Var("p"), Var("q")))),
                    observations=(Observation("rule", (False, False), False), Observation("rule", (True, True), True)),
                    closed_fragments=("rule",))
    role_programs = (Program((Clause("rule", ("TAXP", "SPOUSE"), Var("TAXP")),), (0, 1)),
                     Program((Clause("rule", ("TAXP", "SPOUSE"), Var("SPOUSE")),), (1, 0)))
    role_observations = tuple(Observation("rule", x, x[0], True) for x in domain(("TAXP", "SPOUSE")))
    role = Source("same_type_role_compensation", role_programs, observations=role_observations, closed_fragments=("rule",))
    role_fixed = Source("same_type_role_with_anchor", role_programs, observations=role_observations,
                        closed_fragments=("rule",), role_anchors=((0, 0),))
    unknown = Source("unknown_call_affects_output",
                     (Program((Clause("rule", ("p",), And(Var("p"), Unknown("u", Var("p")))),)),),
                     (("u", 1),), closed_fragments=("rule",))
    unknown_masked = Source("unknown_call_proven_irrelevant",
                            (Program((Clause("rule", ("p",), Or(Var("p"), And(Const(False), Unknown("u", Var("p"))))),)),),
                            (("u", 1),), closed_fragments=("rule",))
    calls = Source("known_call_scope",
                   (Program((Clause("helper", ("x", "y"), And(Var("x"), Not(Var("y")))),
                             Clause("rule", ("eligible", "exception"), Call("helper", Var("eligible"), Var("exception"))))),),
                   closed_fragments=("rule", "helper"))
    equivalent = Source("syntactic_difference_same_function",
                        tuple(Program((Clause("rule", ("p", "q"), e),)) for e in
                              (And(Var("p"), Var("q")), And(Var("q"), Var("p")), Not(Or(Not(Var("p")), Not(Var("q")))))),
                        closed_fragments=("rule",))
    target_1 = Source("transfer_new_source",
                      (Program((Clause("tax_fragment", roles, Not(Or(Not(a), b))),)),),
                      closed_fragments=("tax_fragment",))
    target_bad = Source("transfer_wrong_named_role",
                        (Program((Clause("tax_fragment", roles, And(c, Not(b))),)),),
                        closed_fragments=("tax_fragment",))
    missing_boundary = Source("unclosed_source_boundary", programs, closed_fragments=())
    return (partial, sample, role, role_fixed, unknown, unknown_masked, calls, equivalent,
            target_1, target_bad, missing_boundary)


def scenario_results(sources):
    rows, proposed_all, strong_all = [], [], []
    expected = {
        "whole_ambiguous_local_unique": {"exemption"},
        "sample_equal_domain_different": set(),
        "same_type_role_compensation": set(),
        "same_type_role_with_anchor": {"rule"},
        "unknown_call_affects_output": set(),
        "unknown_call_proven_irrelevant": {"rule"},
        "known_call_scope": {"rule", "helper"},
        "syntactic_difference_same_function": {"rule"},
        "transfer_new_source": {"tax_fragment"},
        "transfer_wrong_named_role": {"tax_fragment"},
        "unclosed_source_boundary": set(),
    }
    for source in sources:
        start = time.perf_counter()
        ours, witnesses = proposed_induce(source)
        ours_time = time.perf_counter() - start
        start = time.perf_counter()
        strong, _ = strong_projected_csp(source)
        strong_time = time.perf_counter() - start
        assert ours == strong
        assert set(ours) == expected[source.name], (source.name, ours)
        pick, wait = pick_first(source), wait_unique(source)
        unsafe_pick = sorted(set(pick) - set(strong))
        wrong_for_some_allowed_world = [f for f in unsafe_pick if any(
            vector_truth(h, f) != pick[f].truth for h in expand_version_space(source))]
        rows.append({"source": source.name, "grammar_programs": len(source.grammar),
                     "complete_candidate_worlds": len(expand_version_space(source)),
                     "fragments": [x[0] for x in common_fragment_pool(source)],
                     "method2": sorted(ours), "strong_projection": sorted(strong),
                     "pick_first": sorted(pick), "wait_whole_semantic_unique": sorted(wait),
                     "pick_first_uncertified": unsafe_pick,
                     "pick_first_wrong_for_some_allowed_world": wrong_for_some_allowed_world,
                     "method2_witnesses": witnesses,
                     "method2_seconds": ours_time, "strong_seconds": strong_time})
        proposed_all.extend(ours.values())
        strong_all.extend(strong.values())
    lp, lb = compress(proposed_all), compress(strong_all)
    assert lp == lb
    return rows, lp


def all_boolean_functions():
    """The complete 2-input Boolean function grammar, represented as ITEs."""
    roles = ("p", "q")
    return tuple(Program((Clause("rule", roles, canonical_body(roles, table)),))
                 for table in product((False, True), repeat=4))


def exhaustive_audit():
    grammar = all_boolean_functions()
    checks = 0
    # 65,535 non-empty finite version spaces; implementations must agree even
    # when none, some or all of the functions fit a visible data sample.
    all_truths = tuple(vector_truth(Hypothesis(p, ()), "rule") for p in grammar)
    assert len(set(all_truths)) == 16
    for mask in range(1, 1 << 16):
        indices = tuple(i for i in range(16) if mask & (1 << i))
        reference = all_truths[indices[0]]
        # Exactly the independent two algorithmic predicates, exhaustively.
        representative_no_counterexample = all(all_truths[i] == reference for i in indices)
        relation_projection_singleton = len({all_truths[i] for i in indices}) == 1
        assert representative_no_counterexample == relation_projection_singleton
        checks += 1
    # Execute complete code paths for all subsets of size at most 3 and for each
    # of 81 possible partial IO observation sets on the complete 16-rule grammar.
    codepath_checks = 0
    for size in (1, 2, 3):
        for subset in combinations(grammar, size):
            source = Source("all_small_subsets", tuple(subset), closed_fragments=("rule",))
            assert proposed_induce(source)[0] == strong_projected_csp(source)[0]
            codepath_checks += 1
    for labels in product((None, False, True), repeat=4):
        observations = tuple(Observation("rule", x, y) for x, y in zip(domain(("p", "q")), labels) if y is not None)
        source = Source("all_partial_supervision", grammar, observations=observations, closed_fragments=("rule",))
        assert proposed_induce(source)[0] == strong_projected_csp(source)[0]
        codepath_checks += 1
    # Two Boolean public inputs and all 16 total unknown binary functions;
    # repeated calls must share one interpretation rather than vary independently.
    calls = Source("unknown_repeat_correlation", (Program((Clause("rule", ("p", "q"),
        Or(Unknown("u", Var("p"), Var("q")), Not(Unknown("u", Var("p"), Var("q"))))),)),),
        (("u", 2),), closed_fragments=("rule",))
    for h in expand_version_space(calls):
        scalar = tuple(scalar_eval(h, "rule", x) for x in domain(("p", "q")))
        assert scalar == vector_truth(h, "rule") == (True, True, True, True)
        codepath_checks += 1
    assert set(proposed_induce(calls)[0]) == {"rule"}
    for truth in product((False, True), repeat=4):
        canonical = Program((Clause("rule", ("p", "q"), canonical_body(("p", "q"), truth)),))
        assert vector_truth(Hypothesis(canonical, ()), "rule") == truth
        codepath_checks += 1
    return {"all_nonempty_two_input_semantic_version_spaces": checks,
            "full_codepath_checks": codepath_checks,
            "complete_boolean_functions": 16,
            "failures": 0}


def lifecycle_audit(sources):
    original = Source("grammar_lifecycle", (Program((Clause("rule", ("p", "q"), And(Var("p"), Var("q"))),)),),
                      closed_fragments=("rule",))
    cert = proposed_induce(original)[0]["rule"]
    expanded = Source(original.name, original.grammar +
                      (Program((Clause("rule", ("p", "q"), Or(Var("p"), Var("q"))),)),),
                      closed_fragments=("rule",), revision=2)
    assert certificate_current(cert, original)
    assert not certificate_current(cert, expanded)
    assert proposed_induce(expanded)[0] == strong_projected_csp(expanded)[0] == {}
    resolved = Source(expanded.name, expanded.grammar,
                      observations=(Observation("rule", (False, True), False),),
                      closed_fragments=("rule",), revision=3)
    assert set(proposed_induce(resolved)[0]) == {"rule"}
    stable = proposed_induce(sources[0])[0]["exemption"]
    assert transfer_allowed(stable, sources[8], "tax_fragment")
    assert not transfer_allowed(stable, sources[9], "tax_fragment")
    return {"old_certificate_invalidated_by_grammar_expansion": True,
            "expanded_grammar_blocks_old_fragment": True,
            "new_observation_recovers_fragment": True,
            "equivalent_new_source_transfer_accepted": True,
            "wrong_role_new_source_transfer_rejected": True}


def main():
    start = time.perf_counter()
    sources = make_scenarios()
    rows, library = scenario_results(sources)
    audit = exhaustive_audit()
    lifecycle = lifecycle_audit(sources)
    for source in sources:
        reversed_source = Source(source.name, tuple(reversed(source.grammar)),
                                 source.unknown_signatures, source.observations,
                                 source.closed_fragments, source.role_anchors, source.revision)
        original_library = compress(proposed_induce(source)[0].values())
        reversed_library = compress(proposed_induce(reversed_source)[0].values())
        assert original_library == reversed_library
    results = {"status": "METHOD2_EQUALS_PROJECTION_PLUS_CANONICAL_COMPRESSION",
               "scope": "Deterministic finite DSL only; no native accuracy or LLM calls",
               "strong_baseline": "Independent finite CSP relation projection + canonical Shannon semantic compression; NOT Stitch",
               "scenarios": rows, "semantic_library": library,
               "exhaustive": audit, "lifecycle": lifecycle,
               "total_seconds": time.perf_counter() - start,
               "general_equivalence": "For identical nonempty V, interfaces, domains, fragment pool, and compression operator, representative universal agreement iff projected semantic set is singleton. Therefore libraries are identical on every instance, not just these tests."}
    destination = Path(__file__).with_name("results.json")
    destination.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    fixture_path = Path(__file__).with_name("fixtures.json")
    fixture_path.write_text(json.dumps([asdict(s) for s in sources], ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"artifact_kind": "finite deterministic validation, no native dataset results",
                "files_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (Path(__file__), destination, fixture_path)}}
    Path(__file__).with_name("manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"status": results["status"], "scenarios": len(rows),
                      "library_functions": len(library), "exhaustive": audit,
                      "lifecycle": lifecycle, "seconds": results["total_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
