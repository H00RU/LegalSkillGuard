"""Bounded production matching for the frozen joint-edit channel algorithm.

The running reader manifest binds structural_channel.py. This module preserves
that implementation and its exact edit semantics, while replacing factorial
node permutations with indexed fact joins. Work exhaustion propagates as an
unsupported computation; it never returns a convenient partial image set.
"""
from legal_skill_guard.paired_interfaces.graph_matching import typed_bindings
from legal_skill_guard.paired_interfaces.structural_channel import (
    Graph, Fact, JointEdit, generalized_edit, observations)


class IndexedJointEdit(JointEdit):
    def images(self, graph, *, max_work=1_000_000, max_bindings=20_000):
        if not self.variables and not self.before and not self.after:
            return frozenset({graph})
        outputs, changes = set(), []
        for binding in typed_bindings(graph, self.variables, self.before,
                                      max_work=max_work, max_bindings=max_bindings):
            def instantiate(fact):
                return Fact(fact.predicate, tuple(binding.get(a, a) for a in fact.arguments), fact.status)
            before = {instantiate(f) for f in self.before}
            after = {instantiate(f) for f in self.after}
            changes.append((before, after))
            outputs.add(Graph(graph.nodes, frozenset((graph.facts - before) | after),
                              graph.schema, graph.context))
        if self.all_matches and changes:
            for i, (left, result) in enumerate(changes):
                for right, other in changes[i + 1:]:
                    if left & right and (result - left) != (other - right):
                        return frozenset(outputs)
            removed = set().union(*(before for before, after in changes))
            added = set().union(*(after for before, after in changes))
            return frozenset({Graph(graph.nodes, frozenset((graph.facts - removed) | added),
                                    graph.schema, graph.context)})
        return frozenset(outputs or {graph})


def indexed(edit):
    return IndexedJointEdit(edit.variables, edit.before, edit.after, edit.all_matches)


def learn_dictionary(development_pairs):
    """The original anti-unification rule, using complete indexed image sets.

    This entry point is separate because the currently running phase binds the
    original source. There are no additional operator families or label-based
    choices in this implementation.
    """
    identity = IndexedJointEdit((), (), ())
    edits, sources, unmatched = {identity.identity: identity}, set(), []
    for pair in development_pairs:
        if pair.role != 'development':
            raise ValueError('Only disjoint dictionary-development sources may define edits')
        sources.add(pair.source_id)
        for observed in observations(pair):
            if pair.reference.nodes != observed.nodes:
                unmatched.append(pair.source_id)
                continue
            removed = sorted(pair.reference.facts - observed.facts)
            added = sorted(observed.facts - pair.reference.facts)
            edit = indexed(generalized_edit(pair.reference, removed, added))
            edits[edit.identity] = edit
            kinds = dict(pair.reference.nodes)
            anchor_kinds = {'event', 'service_event', 'effect', 'obligation', 'exception', 'bag', 'asset'}
            anchors = {f.arguments[0] for f in removed + added if f.arguments
                       and kinds.get(f.arguments[0]) in anchor_kinds}
            for anchor in sorted(anchors):
                before = [f for f in removed if f.arguments and f.arguments[0] == anchor]
                after = [f for f in added if f.arguments and f.arguments[0] == anchor]
                if before and after:
                    systematic = indexed(generalized_edit(pair.reference, before, after, all_matches=True))
                    if systematic.images(pair.reference) == frozenset({observed}):
                        edits[systematic.identity] = systematic
    return {'edits': tuple(edits.values()), 'development_sources': frozenset(sources),
            'unmatched_development_sources': unmatched}


def graph_record(graph):
    return {'nodes': list(graph.nodes), 'facts': [
        {'predicate': f.predicate, 'arguments': list(f.arguments), 'status': f.status}
        for f in sorted(graph.facts)], 'schema': graph.schema, 'context': graph.context}


def restore_graph(record):
    return Graph(tuple(tuple(n) for n in record['nodes']), frozenset(
        Fact(f['predicate'], tuple(f['arguments']), f['status']) for f in record['facts']),
        record['schema'], record['context'])
