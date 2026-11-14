"""Frozen semantic parsing into acquired, typed constructor expressions.

The model supplies semantic operators; deterministic lowering handles the
consumer representation. Raw source text is not a root interpretation.
"""
import ast
import json
import jsonschema

from .native import record_schema, source_spans
from .scoped_grammar import constructors, term_sort, RESULT, material_public
from .span_compiler import execute_json
from .span_compiler import occurrences


def read_schema(spec, spans):
    return record_schema({'statements': {'type': 'array', 'maxItems': 24,
        'items': record_schema({'expression': {'type': 'string'},
            'support_ids': {'type': 'array', 'minItems': 1, 'maxItems': len(spans), 'uniqueItems': True,
                'items': {'type': 'integer', 'minimum': 0, 'maximum': len(spans) - 1}}})}})


def expression_text(term):
    if isinstance(term, dict):
        return 'ARG' + str(term['$'])
    if isinstance(term, str):
        return json.dumps(term, ensure_ascii=False)
    return term[0] + '(' + ','.join(expression_text(t) for t in term[1:]) + ')'


def decode_expression(expression, schema, evidence, text_audit=None):
    tree = ast.parse(expression.strip(), mode='eval')
    if not isinstance(tree.body, ast.Call):
        raise ValueError('A root must use acquired semantic constructors, not raw text')
    def decode(node, path, depth):
        if depth > 64:
            raise ValueError('Constructor expression exceeds bounded execution depth')
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if text_audit is not None:
                text_audit.append({'path': path, 'value': node.value,
                    'verbatim_in_cited_source': bool(occurrences(evidence, node.value)),
                    'semantic_support_verified': False})
            return node.value
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.keywords:
            raise ValueError(path + ': only acquired positional constructor calls and source strings are allowed')
        if node.func.id not in schema:
            raise ValueError(path + ': unacquired constructor ' + node.func.id)
        term = [node.func.id, *(decode(n, path + '.arg' + str(i), depth + 1) for i,n in enumerate(node.args))]
        expected = schema[node.func.id]['arguments']
        actual = [term_sort(t, schema) for t in term[1:]]
        if actual != expected:
            raise ValueError(path + ': expected sorts ' + str(expected) + ', actual ' + str(actual))
        return term
    return decode(tree.body, 'expression', 0)


def bind(spec, public, value):
    spans = source_spans(material_public(public))
    jsonschema.validate(value, read_schema(spec, spans))
    schema = constructors(spec)
    nodes = []
    for i, raw in enumerate(value['statements']):
        evidence = ' '.join(spans[s]['text'] for s in raw['support_ids'])
        text_audit = []
        try:
            term = decode_expression(raw['expression'], schema, evidence, text_audit)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(f'statements[{i}].expression: {exc}') from exc
        sort = term_sort(term, schema)
        nodes.append({'id': i, 'sort': sort, 'term': term, 'support_ids': raw['support_ids'],
                      'child_ids': [], 'ambiguous': False, 'text_argument_audit': text_audit,
                      'source_semantics_verified': False})
    return {'nodes': nodes, 'roots': [n['id'] for n in nodes]}


def grammar_view(grammar):
    return [{'source_pattern': ' '.join(str(p) if isinstance(p, str)
                else '{ARG' + str(p) + ':' + r['child_sorts'][p] + '}' for p in r['parts']),
             'argument_sorts': r['child_sorts'],
             'expression_template': expression_text(r['target']), 'result_sort': r['sort']}
            for r in grammar['rules'] if r['id'] not in grammar['disabled_rules']]


def read_current(reads, source, spec, grammar):
    public = source['views'][0]['public']
    if any(v['public'].get('source_text') != public['source_text'] for v in source['views']):
        raise ValueError('Current material must be parsed separately for distinct view texts')
    spans = source_spans(material_public(public))
    value, event = reads.generate(source, source['views'][0],
        system='Translate the complete CURRENT legal source into a FEW executable semantic constructor expressions. '
               'Output operative disclosure permissions/prohibitions and any definitions needed to interpret them. '
               'Do not reproduce the source as text records. Expressions use the acquired constructor names as '
               'functions with positional arguments; nest calls directly. A zero-argument constructor is NAME(). '
               'Text arguments use ordinary ASCII quote delimiters and describe only source-supported names or '
               'qualifications. Prefer short exact source wording; canonical descriptions must preserve its exact '
               'meaning. Never import an old example participant, purpose or condition. Each statement cites all current '
               'span IDs supporting that coherent interpretation. A definition may be a separate statement used by '
               'a referring norm. No native answer labels, raw-text roots, Python variables, assignments or imports. '
               'There is no literal operator and no model-written node numbering. If no supported interpretation '
               'is available, return statements:[]; unknown must not become a negative fact. Distinguish '
               'information descriptions, permissions, restrictions, the acting party, recipient ownership, definition '
               'references and exception scope. Preserve nested ownership and locally bound references in the tree. '
               'Do not infer a permission from a role mention or copy every operator into the output. '
               'Use only supported operators; leave unresolved interpretations absent rather than inventing facts. '
               'The examples/productions describe a learned translation language: {ARG0:Type} in a source_pattern '
               'and ARG0,ARG1 in templates denote typed grammar slots. In your final expressions replace them with actual '
               'constructor expressions or current-source strings. Old example facts are not current facts.',
        content={'constructors': spec['constructors'], 'learned_productions': grammar_view(grammar),
                 'current_source_spans': [{k: v for k, v in s.items() if k != 'public_sentence_id'} for s in spans]},
        schema=read_schema(spec, spans), purpose='skill_replay')
    return bind(spec, public, value), {**event, 'kind': 'READ_ACQUIRED_SCOPED_TERMS', 'returned': value}


def match_template(template, term, sorts, schema, bindings=None):
    bindings = {} if bindings is None else bindings
    if isinstance(template, dict):
        i = template['$']
        if term_sort(term, schema) != sorts[i]:
            return False
        if i in bindings:
            return bindings[i] == term
        bindings[i] = term
        return True
    if isinstance(template, list):
        return (isinstance(term, list) and len(template) == len(term) and template[0] == term[0]
                and all(match_template(a, b, sorts, schema, bindings) for a, b in zip(template[1:], term[1:])))
    return template == term


def apply_current(spec, grammar, interpretation, view):
    result = execute_json(spec['decision_program'], {'task_id': view['id'], 'question': view['public']['question']},
                          interpretation, allow_helpers=True)
    jsonschema.validate(result, RESULT)
    if any(i not in interpretation['roots'] for i in result['used_nodes']):
        raise ValueError('Consumer proof references a non-root or absent source interpretation')
    if result['handled'] and (result['answer'] is None or not result['used_nodes']):
        raise ValueError('Handled result needs an actual typed source interpretation')
    schema = constructors(spec)
    used = []
    for i in result['used_nodes']:
        term = interpretation['nodes'][i]['term']
        patterns = [r['id'] for r in grammar['rules'] if r['induced']
                    and r['id'] not in grammar['disabled_rules']
                    and match_template(r['target'], term, r['child_sorts'], schema)]
        used.append({'root': i, 'induced_target_patterns_matched': patterns,
                     'term_not_in_acquired_pairs': not any(p['term'] == term for p in grammar['acquired_pairs'])})
    return {'value': result, 'root_uses': used,
            'pattern_match_is_not_causal_ablation_or_source_truth': True}
