"""Instantiate explicit learned-pattern calls on current-source role bindings."""
from __future__ import annotations

from copy import deepcopy
import re

from .coverage import digest
from .interfaces import Connector, InterfaceError


def graph_roles(graph):
    slots, columns = set(), set()
    def visit(node):
        if 'slot' in node:
            slots.add(node['slot'])
            return
        for key, value in node.get('params', {}).items():
            if key.endswith('_slot'):
                slots.add(value)
            elif key in {'keys', 'from', 'to'}:
                columns.update(x for x in value if re.fullmatch(r'column[0-9]+', x))
        for child in node['inputs']:
            visit(child)
    visit(graph)
    return slots, columns


def expand_graph(graph, library, available_slots):
    """Only explicit calls count as reuse; structural similarity is insufficient.

    No role, entity witness, column or graph alternative is guessed. The normal
    typed executor checks the expanded graph against the actual current inputs.
    """
    patterns = {item['pattern_hash']: item for item in (library or {}).get('patterns', [])}
    uses = []
    def expand(node, path):
        if 'pattern' not in node:
            result = deepcopy(node)
            if 'inputs' in node:
                result['inputs'] = [expand(child, path + '.inputs[' + str(i) + ']')
                                    for i, child in enumerate(node['inputs'])]
            return result
        if set(node) != {'pattern', 'variant', 'slots', 'columns'}:
            raise InterfaceError('Learned call requires pattern, variant and complete role/column bindings')
        key, variant = node['pattern'], node['variant']
        if key not in patterns:
            raise InterfaceError('Requested learned pattern is unavailable under the current library policy')
        item = patterns[key]
        if digest(item['pattern']) != key:
            raise InterfaceError('Learned pattern hash differs from its immutable definition')
        graphs = item['pattern']['graphs']
        if type(variant) is not int or not 0 <= variant < len(graphs):
            raise InterfaceError('Learned graph variant must be explicitly selected')
        template = graphs[variant]
        roles, columns = graph_roles(template)
        if set(node['slots']) != roles or set(node['columns']) != columns:
            raise InterfaceError('Learned call has missing or extra semantic role bindings')
        if not all(isinstance(v, str) and v in available_slots for v in node['slots'].values()):
            raise InterfaceError('Learned call cannot invent a missing current-source primitive')
        if not all(isinstance(v, str) and v for v in node['columns'].values()):
            raise InterfaceError('Learned call requires explicit current relation columns')
        def instantiate(part):
            if 'slot' in part:
                return {'slot': node['slots'][part['slot']]}
            result = {'op': part['op'], 'inputs': [instantiate(c) for c in part['inputs']]}
            params = {}
            for name, value in part.get('params', {}).items():
                params[name] = node['slots'][value] if name.endswith('_slot') else \
                    [node['columns'].get(c, c) for c in value] if name in {'keys', 'from', 'to'} else value
            if params:
                result['params'] = params
            return result
        expanded = instantiate(template)
        Connector(expanded).validate()
        uses.append({'pattern_hash': key, 'variant': variant, 'path': path,
                     'role_bindings': deepcopy(node['slots']), 'column_bindings': deepcopy(node['columns']),
                     'supporting_training_sources': list(item['evidence_sources']),
                     'expanded_graph_hash': digest(expanded), 'status': 'expanded_not_yet_executed'})
        return expanded
    return expand(graph, '$'), uses
