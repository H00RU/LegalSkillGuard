"""Source-only normalization of graph display names and evidence pointers.

No concept, kind, edge, value, status, inventory or scope is inferred or fixed.
Literal identity conflicts remain errors. A nonliteral display gloss may be
replaced by its already supplied verbatim quote only when it does not conflict
with another literal component in the offered source. All old names survive
in the receipt. This does not certify source meaning or native answers.
"""
from copy import deepcopy
import re

import jsonschema

from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.skill_evolution.objects import digest


def semantic_payload(graph):
    return {**graph,
            'nodes': [{k: v for k, v in n.items() if k not in ('name', 'unit_id')}
                      for n in graph['nodes']],
            'relations': [{k: v for k, v in e.items() if k != 'unit_id'}
                          for e in graph['relations']]}


def normalize_graph_evidence(graph, units):
    jsonschema.validate(graph, gi.schema())
    names = [n['id'] for n in graph['nodes']]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate node identities cannot be repaired by evidence normalization')
    offered = {u['id']: u for u in units}
    if len(offered) != len(units):
        raise ValueError('Offered source unit identities are not unique')
    result, pointers, displays = deepcopy(graph), [], []
    source_text = '\n'.join(u['text'] for u in units)
    for group in ('nodes', 'relations'):
        for i, cell in enumerate(result[group]):
            identity, quote = cell['unit_id'], cell['quote']
            if not quote:
                raise ValueError('Empty evidence is not a source anchor')
            if identity not in offered or quote not in offered[identity]['text']:
                matches = [(u['id'], m.start(), m.end()) for u in units
                           for m in re.finditer(re.escape(quote), u['text'])]
                if len(matches) != 1:
                    raise ValueError('Evidence has no unique verbatim occurrence in the offered source')
                actual, start, end = matches[0]
                pointers.append({'path': [group, i, 'unit_id'], 'original': identity,
                                 'bound': actual, 'source_local_span': [start, end], 'quote': quote})
                cell['unit_id'] = actual
            if group == 'nodes' and (not cell['name'] or cell['name'] not in quote):
                name = cell['name']
                # A name that points to another literal entity/attribute is an
                # observed conflict, not a harmless label. Never select the
                # quoted identity over that name by consulting reference roles.
                tokens = re.findall(r'[^\W_]+', name, re.UNICODE)
                literal_components = [t for t in tokens if len(t) >= 3
                    and re.search(r'(?<!\w)' + re.escape(t) + r'(?!\w)', source_text, re.IGNORECASE)]
                if any(not re.search(r'(?<!\w)' + re.escape(t) + r'(?!\w)', quote, re.IGNORECASE)
                       for t in literal_components):
                    raise ValueError('Display name conflicts with another literal source component')
                displays.append({'node': cell['id'], 'original_display_name': name,
                                 'literal_display_name': quote,
                                 'discarded_gloss_is_not_certified_source_meaning': True})
                cell['name'] = quote
    before, after = semantic_payload(graph), semantic_payload(result)
    if before != after:
        raise AssertionError('Evidence normalization changed a semantic payload')
    checks = gi.validate(result, units)
    return result, {'evidence_pointer_bindings': pointers, 'display_name_projections': displays,
        'semantic_payload_sha256_before': digest(before), 'semantic_payload_sha256_after': digest(after),
        'values_statuses_kinds_concepts_edges_inventory_and_scope_unchanged': True,
        'quotes_unchanged': True, 'literal_identity_conflicts_not_repaired': True,
        'schema_and_anchor_checks': checks, 'source_semantic_truth_verified': False,
        'new_model_requests': 0, 'public_decoder_not_a_learned_method': True}
