"""An absorbing outcome for observed production-decoder abstentions.

Keep source-specific error text in immutable raw evidence, outside the outcome
identity. Alignment/work-limit unknowns are not production abstentions. This
adds no success outcome and does not set unmodeled semantic error mass to zero.
"""
from dataclasses import replace

from legal_skill_guard.paired_interfaces.empirical_channel import (
    IndexedJointEdit, learn_dictionary as semantic_dictionary)
from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph, observations
from legal_skill_guard.skill_evolution.objects import digest

OPERATOR = 'observed_production_abstention_v1'
MARKER = 'observed-production-abstention:v1'


def abstention_graph(reference):
    if MARKER in dict(reference.nodes):
        raise ValueError('The reference domain already contains the reserved abstention marker')
    return Graph(tuple(sorted((*reference.nodes, (MARKER, 'unresolved_read')))),
                 frozenset({Fact('read_failure', (), 'unread')}), reference.schema, reference.context)


class ObservedAbstention(IndexedJointEdit):
    @property
    def identity(self):
        return digest({'operator': OPERATOR})

    def images(self, graph):
        return frozenset({abstention_graph(graph)})


def canonical_pair(pair, production_decode):
    """Call only with the original, verified production decode receipt."""
    if ('graph' not in production_decode or not isinstance(production_decode.get('errors'), list)
            or any(not isinstance(error, str) or not error for error in production_decode['errors'])):
        raise ValueError('A complete production decode receipt is required')
    if production_decode.get('graph') is not None:
        if not isinstance(production_decode['graph'], dict) or production_decode['errors']:
            raise ValueError('A valid graph cannot simultaneously be a production rejection')
        return pair, {'production_abstention': False,
                      'analysis_unknown_or_successful_alignment_not_changed': True}
    if not production_decode['errors']:
        raise ValueError('An absent production graph needs explicit rejection evidence')
    return replace(pair, observed=abstention_graph(pair.reference)), {
        'production_abstention': True, 'operator': OPERATOR,
        'original_production_errors': production_decode['errors'],
        'native_abstention_loss_is_one_when_reference_is_defined': True,
        'source_fields_or_native_answers_reconstructed': False}


def learn_dictionary(development_pairs):
    # Abstention is a declared decoder result, not a teacher-invented semantic
    # rewrite. Its frequency is estimated in each original version/context;
    # no failures or calibration sources are pooled across versions.
    result = semantic_dictionary(development_pairs)
    edits = (*result['edits'], ObservedAbstention((), (), ()))
    unmatched = sorted({pair.source_id for pair in development_pairs
                        if any(not any(world in edit.images(pair.reference) for edit in edits)
                               for world in observations(pair))})
    return {**result, 'edits': edits, 'unmatched_development_sources': unmatched,
            'declared_absorbing_outcome': OPERATOR,
            'unmodeled_semantic_error_component_retained': True}


def edit_record(edit):
    if isinstance(edit, ObservedAbstention):
        return {'operator': OPERATOR, 'identity': edit.identity}
    return {'identity': edit.identity, 'variables': edit.variables,
            'before': [vars(fact) for fact in edit.before],
            'after': [vars(fact) for fact in edit.after], 'all_matches': edit.all_matches}


def restore_edit(item):
    if item.get('operator') == OPERATOR:
        edit = ObservedAbstention((), (), ())
    elif 'operator' not in item:
        facts = lambda name: tuple(Fact(f['predicate'], tuple(f['arguments']), f['status']) for f in item[name])
        edit = IndexedJointEdit(tuple(tuple(v) for v in item['variables']),
                                facts('before'), facts('after'), item['all_matches'])
    else:
        raise ValueError('Unknown saved channel operator')
    if edit.identity != item['identity']:
        raise ValueError('A fitted edit identity changed')
    return edit
