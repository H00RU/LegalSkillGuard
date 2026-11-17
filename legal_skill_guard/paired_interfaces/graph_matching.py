"""Typed graph-pattern joins with an explicit unsupported-work boundary.

Index facts before joining variables. This avoids enumerating all permutations
of every node kind when applying a small learned error to a large source graph.
Crossing a limit raises, so a partial set of favorable matches is never used.
"""
from collections import defaultdict


class GraphMatchLimit(ValueError):
    pass


def typed_bindings(graph, variables, before, *, max_work=1_000_000, max_bindings=20_000):
    kinds, typed = dict(graph.nodes), dict(variables)
    by_kind, by_signature = defaultdict(list), defaultdict(list)
    for node, kind in graph.nodes:
        by_kind[kind].append(node)
    for fact in sorted(graph.facts):
        by_signature[fact.predicate, fact.status, len(fact.arguments)].append(fact)
    if any(len(by_kind[kind]) < sum(t == kind for v, t in variables) for kind in set(typed.values())):
        return
    patterns = sorted(before, key=lambda f: (len(by_signature[f.predicate, f.status, len(f.arguments)]),
                                              f.predicate, f.arguments, f.status))
    work, emitted = 0, 0

    def charge():
        nonlocal work
        work += 1
        if work > max_work:
            raise GraphMatchLimit('Typed graph match work exhausted; complete binding support unavailable')

    def complete(binding, used, remaining):
        nonlocal emitted
        if not remaining:
            emitted += 1
            if emitted > max_bindings:
                raise GraphMatchLimit('Too many compatible typed bindings; partial support is not a channel estimate')
            yield dict(binding)
            return
        variable = remaining[0]
        for node in sorted(by_kind[typed[variable]]):
            charge()
            if node in used:
                continue
            yield from complete({**binding, variable: node}, used | {node}, remaining[1:])

    def join(i, binding, used):
        if i == len(patterns):
            yield from complete(binding, used, [v for v, kind in variables if v not in binding])
            return
        pattern = patterns[i]
        for fact in by_signature[pattern.predicate, pattern.status, len(pattern.arguments)]:
            charge()
            proposal, reserved = dict(binding), set(used)
            for variable, node in zip(pattern.arguments, fact.arguments):
                if variable not in typed:
                    if variable != node:
                        break
                elif variable in proposal:
                    if proposal[variable] != node:
                        break
                elif node in reserved or kinds.get(node) != typed[variable]:
                    break
                else:
                    proposal[variable] = node
                    reserved.add(node)
            else:
                yield from join(i + 1, proposal, reserved)
    yield from join(0, {}, set())
