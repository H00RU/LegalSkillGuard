"""Finite, evidence-bearing responsibility contexts; never a legal oracle.

Code probes intervene on one Boolean dependency under explicit reference
bindings. A source relation is known only for a literal, uniquely bound
exception reference. Unsupported source syntax and unavailable bindings stay
unknown and contribute no matching evidence.
"""
from copy import deepcopy
from functools import lru_cache
import ast
import json
import re

from .objects import Skill, digest
from .runtime import execute_helper


def invocations(trace, producer, field, consumer):
    """Actual USE followed by its consumer APPLY, not a guessed graph edge."""
    for view in trace.get('views', []):
        events = view.get('execution', {}).get('events', [])
        for index, event in enumerate(events):
            if (event.get('kind') != 'USE' or event.get('producer') != producer
                    or event.get('field') != field or event.get('consumer') != consumer):continue
            apply = next((e for e in events[index + 1:] if e.get('kind') == 'APPLY'
                and e.get('skill_id') == consumer
                and e.get('source') == trace['source'] and e.get('view') == view['view']
                and e.get('invocation_arguments', {}) == event.get('consumer_arguments', {})), None)
            if apply is not None:
                yield {'source': trace['source'], 'view': view['view'],
                    'inputs': apply['inputs'], 'premises': apply['premises'],
                    'input_port': event['input'], 'USE': event,
                    'score': view['score'], 'core_executed': view['execution'].get('core_executed', False)}


def improved_invocations(table, selected_mask, producer, field, consumer):
    """The approved parent's improved core view supplies context, not a new score."""
    for source in table.trigger:
        before = table.traces.get((0, source), {})
        scores = {v['view']: v['score']['grade'] for v in before.get('views', [])}
        after = table.traces.get((selected_mask, source), {})
        if before.get('source') != source or after.get('source') != source:continue
        for unit in invocations(after, producer, field, consumer):
            old, new = scores.get(unit['view']), unit['score']['grade']
            if unit['core_executed'] and old is not None and new is not None and new > old:
                yield unit


def _checks(skill):
    # This describes code/acquisition structure, not truth of a legal condition.
    used_inputs = {n.slice.value for n in ast.walk(ast.parse(skill.procedure))
        if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == 'inputs'
        and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str)}
    used_inputs.update(b['port'] for p in skill.inputs.values() if p['mode'] == 'skill'
                       for b in p.get('arguments', {}).values() if b['namespace'] == 'inputs')
    return [{'namespace': namespace, 'port': n, 'type': p['type'], 'acquisition': p['mode']}
            for namespace, ports in (('inputs', skill.inputs), ('premises', skill.premises))
            for n, p in sorted(ports.items()) if namespace == 'premises' or n in used_inputs]


def _code_sites(skill):
    return {'skill_id': skill.id, 'skill_hash': skill.hash,
        'literal_port_accesses': [{'namespace': n.value.id, 'port': n.slice.value,
            'line': n.lineno, 'column': n.col_offset}
            for n in ast.walk(ast.parse(skill.procedure)) if isinstance(n, ast.Subscript)
            and isinstance(n.value, ast.Name) and n.value.id in ('inputs', 'premises')
            and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str)],
        'dependency_binding_sites': [{'input': name, 'parameter': parameter, **binding}
            for name, p in skill.inputs.items() if p['mode'] == 'skill'
            for parameter, binding in p.get('arguments', {}).items()]}


def read_cost(table, mask):
    """Deduplicate traced READ origins; untraced failures are not zero cost."""
    seen, total, complete = set(), 0, True
    def leaves(event):
        if event.get('subreads'):
            for sub in event['subreads']:yield from leaves(sub)
        else:yield event
    for (assignment, _), trace in table.traces.items():
        if assignment != mask:continue
        for view in trace.get('views', []):
            execution = view.get('execution', {})
            if execution.get('error') or any(not f.get('error', '').startswith('Static')
                                            for f in execution.get('failed_candidates', [])):
                complete = False
            for event in execution.get('events', []):
                if event.get('kind') != 'READ_LOCAL':continue
                for leaf in leaves(event):
                    identity = leaf.get('physical_call_id') or leaf.get('call_id')
                    tokens = (leaf.get('usage') or {}).get('total_tokens')
                    if identity is None or type(tokens) is not int:
                        complete = False;continue
                    if identity not in seen:seen.add(identity);total += tokens
    return {'traced_tokens': total, 'unique_read_origins': len(seen), 'complete': complete,
        'kind': 'unique referenced READ consumption footprint, not incremental physical billing'}


@lru_cache(maxsize=2048)
def _probe_serialized(skill_json, input_port, inputs_json, premises_json, dependency_value):
    skill = Skill.from_dict(json.loads(skill_json))
    inputs, premises = json.loads(inputs_json), json.loads(premises_json)
    inputs[input_port] = dependency_value
    try:
        output = execute_helper(skill, inputs, premises,
            unresolved_inputs=set(skill.inputs) - set(inputs),
            unresolved_premises=set(skill.premises) - set(premises))
        return {'status': 'known', 'output': output}
    except Exception as error:
        return {'status': 'unknown', 'reason': type(error).__name__ + ': ' + str(error)}


def _effects(skill, input_port, inputs, reference_premises):
    from dataclasses import asdict
    arguments = {n: deepcopy(inputs[n]) for n in skill.inputs if n in inputs and n != input_port}
    premises = {n: deepcopy(p['value']) if p['mode'] == 'constant' else deepcopy(reference_premises[n])
                for n, p in skill.premises.items() if p['mode'] == 'constant' or n in reference_premises}
    data = [json.dumps(x, ensure_ascii=False, sort_keys=True) for x in (asdict(skill), arguments, premises)]
    return {str(value).lower(): deepcopy(_probe_serialized(data[0], input_port, data[1], data[2], value))
            for value in (False, True)}


def _source_text(source, view_id):
    if not source:return None
    values = [v.get('public', {}).get('source_text') for v in source.get('views', [])
              if view_id is None or v.get('id') == view_id]
    if not values or not all(isinstance(t, str) for t in values):return None
    texts = set(values)
    return next(iter(texts)) if len(texts) == 1 else None


def _unique_quote_anchor(skill, port, text):
    if text is None:return None
    anchors = set()
    for obligation in skill.source_obligations:
        if obligation.get('port') != port:continue
        origin = obligation.get('origin', {})
        quote = origin.get('quote', '')
        if not isinstance(quote, str) or not quote or text.count(quote) != 1:continue
        anchors.add((text.index(quote), text.index(quote) + len(quote), quote))
    return next(iter(anchors)) if len(anchors) == 1 else None


def source_relation(producer, consumer, field, source, *, view_id=None):
    """Bind an explicit exception cross-reference; no inferred missing rule."""
    text = _source_text(source, view_id)
    p = _unique_quote_anchor(producer, field, text)
    c = _unique_quote_anchor(consumer, 'answer', text)
    unknown = {'status': 'unknown', 'reason': 'No unique literal exception-reference binding'}
    if p is None or c is None:return unknown
    headers = list(re.finditer(r'(?m)^[ \t]*(\d+)\.[ \t]+', text))
    scopes = [(m.group(1), m.start(), headers[i + 1].start() if i + 1 < len(headers) else len(text))
              for i, m in enumerate(headers)]
    producer_scopes = [n for n, a, b in scopes if a <= p[0] and p[1] <= b]
    refs = list(re.finditer(r'\bexcept\s+as\s+expressly\s+permitted\s+under\s+(?:Paragraph|Section)\s+(\d+)\b', c[2], re.I))
    if len(producer_scopes) != 1 or len(refs) != 1:return unknown
    target = refs[0].group(1)
    if target != producer_scopes[0] or sum(n == target for n, _, _ in scopes) != 1:return unknown
    consumer_scopes = [n for n, a, b in scopes if a <= c[0] and c[1] <= b]
    if len(consumer_scopes) != 1:return unknown
    return {'status': 'known', 'kind': 'literal_express_exception_reference',
        'direction': 'consumer_reference_to_producer_scope',
        'source_id': source['key'], 'producer_scope': target, 'consumer_scope': consumer_scopes[0],
        'view_id': view_id,
        'binding_policy': 'Exact unique quote in current material; learning-origin source IDs are not applicability IDs.',
        'producer_anchor': {'start': p[0], 'end': p[1], 'quote': p[2]},
        'consumer_anchor': {'start': c[0], 'end': c[1], 'quote': c[2]},
        'reference': {'start': c[0] + refs[0].start(), 'end': c[0] + refs[0].end(), 'text': refs[0].group(0)},
        'legal_truth_or_universal_implication_inferred': False}


def context(producer, consumer, after_producer, after_consumer, field, unit, source=None):
    """Verified code facts plus supported source fields; declarations stay separate."""
    port = unit['input_port']
    binding = consumer.inputs.get(port, {})
    if (producer.outputs[field]['type'] != 'boolean' or binding.get('mode') != 'skill'
            or binding.get('skill_id') != producer.id or binding.get('field') != field or binding.get('type') != 'boolean'
            or type(unit['inputs'].get(port)) is not bool):
        return {'fields': {}, 'unknown': ['unsupported_dependency_type'], 'evidence': {}}
    reference = {n: deepcopy(p['value']) if p['mode'] == 'constant' else deepcopy(unit['premises'][n])
                 for n, p in consumer.premises.items() if p['mode'] == 'constant' or n in unit['premises']}
    before = _effects(consumer, port, unit['inputs'], reference)
    after = _effects(after_consumer, port, unit['inputs'], reference)
    fields = {'producer_port_type': 'boolean', 'consumer_uses_actual_producer_output': True,
        'producer_before_checks': _checks(producer), 'producer_after_checks': _checks(after_producer),
        'dependency_arguments': deepcopy(consumer.inputs[port].get('arguments', {}))}
    unknown = []
    for version, outcomes in (('before', before), ('after', after)):
        for value, result in outcomes.items():
            name = 'consumer_' + version + '_' + value + '_output'
            if result['status'] == 'known':fields[name] = result['output']
            else:unknown.append(name)
    relation = source_relation(producer, consumer, field, source, view_id=unit['view'])
    if relation['status'] == 'known':
        fields['source_relation_kind'] = relation['kind']
        fields['source_relation_direction'] = relation['direction']
    else:unknown.append('source_relation')
    return {'fields': fields, 'unknown': unknown, 'evidence': {
        'source': unit['source'], 'view': unit['view'], 'actual_USE': deepcopy(unit['USE']),
        'consumer_before_effects': before, 'consumer_after_effects': after,
        'reference_premises': reference,
        'probe_scope': 'Boolean dependency interventions under fixed pre-edit reference bindings; not fresh READ values or new legal labels.',
        'producer_checks_scope': 'Declared actual-use inventory and acquisition modes; not independent legal condition gold.',
        'code_bindings': {'producer_before': _code_sites(producer), 'producer_after': _code_sites(after_producer),
                          'consumer_before': _code_sites(consumer), 'consumer_after': _code_sites(after_consumer)},
        'source_relation': relation, 'declared_roles_are_not_matching_evidence': True}}
