"""A declarative Python-syntax frontend for the existing source IR.

This module parses syntax, never executes Python or supplies missing semantics.
Its output still needs the existing source schema, grounding, type, scope,
resource and completion checks. It does not accept legacy response envelopes.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import re

from .coverage import Unsupported
from .source_program import OPERATORS


PRIMITIVES = frozenset({'integer', 'rational', 'scalar', 'relation', 'amount',
                        'amounts', 'allowance_bank', 'resource_key', 'slot_list'})
GRAPHS = {'bind_rename': 1, 'join_on': 2, 'project_exists': 1, 'group_by': 1,
          'map': 1, 'fold_reduce': 1, 'thread_allowance': 1}
PROJECTIONS = frozenset({'identity', 'amount_value', 'amount_values', 'entailment_label'})
FUNCTIONS = {op: op for op in OPERATORS if op not in {'if', 'and', 'or', 'not'}}
FUNCTIONS.update(all_of='and', any_of='or')
FIELDS = ('bindings', 'observations', 'rule_residuals', 'nodes', 'scopes', 'clauses', 'query')


def compiler_response_schema(source, library=None):
    """Constrain declaration metadata while keeping local expressions compact.

    Reuse the actual SourceIR binding, provenance and native-query contracts.
    Expression strings still pass the restricted parser and every IR check.
    """
    from .source_program import program_schema
    from .strict_contract import obj, array
    schema = program_schema(source, library)
    fields = schema['properties']
    symbol = fields['scopes']['items']['properties']['name']
    rule = fields['scopes']['items']['properties']['source']
    code = {'type': 'string', 'minLength': 1}
    fields['scopes']['items'] = obj({'name': symbol, 'source': rule, 'condition_code': code})
    fields['clauses']['items'] = obj({'name': symbol, 'sources': array(rule),
        'value_code': code, 'otherwise_code': code})
    fields['nodes'] = array(obj({'name': symbol,
        'kind': {'type': 'string', 'enum': ['expression', 'connector']}, 'code': code}))
    # Generate executable rules before optional witness tables. The order is
    # part of dispatch identity, not a change to dependency or coverage rules.
    order = ('scopes', 'clauses', 'rule_residuals', 'observations', 'bindings', 'nodes', 'query')
    schema['properties'] = {key: fields[key] for key in order}
    schema['required'] = list(order)
    return schema


def decode_compiler_response(response, source, library=None):
    from .wire_validation import validate_wire
    validate_wire(response, compiler_response_schema(source, library))
    parser = _Parser(ast.Module(body=[], type_ignores=[]))
    parser.reserved.update(row['name'] for field in FIELDS[:-1] for row in response[field])
    # Lifted graph temporaries must not capture an undeclared name referenced
    # by the native query or a later expression/slot-parameter string.
    parser.reserved.update(re.findall(r'\b_inline_[0-9]+\b', repr(response)))
    for field in ('bindings', 'observations', 'rule_residuals'):
        parser.program[field] = deepcopy(response[field])

    def fragment(code, path, connector_name=None):
        try:
            try:
                tree = ast.parse(code, mode='eval')
            except (SyntaxError, ValueError, RecursionError) as exc:
                raise SourceCodeError('Invalid expression: ' + str(exc), [{
                    'path': path, 'line': getattr(exc, 'lineno', None),
                    'column': getattr(exc, 'offset', None),
                    'expected': 'one syntactically valid restricted expression',
                    'actual': getattr(exc, 'msg', str(exc))}]) from exc
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    parser.reserved.add(node.id)
                if _call_name(node) in PRIMITIVES | {'observation', 'residual', 'scope', 'clause'}:
                    _fail(node, 'Declare typed inputs, observations, residuals, scopes and clauses in their schema fields')
            if connector_name is not None:
                return parser.connector(connector_name, tree.body)
            return parser.expression(tree.body)
        except SourceCodeError as exc:
            for diagnostic in exc.diagnostics:
                diagnostic['path'] = path
            raise SourceCodeError(path + ': ' + str(exc), exc.diagnostics) from exc

    for index, row in enumerate(response['nodes']):
        path = f'nodes[{index}].code'
        if row['kind'] == 'connector':
            fragment(row['code'], path, row['name'])
        else:
            body = fragment(row['code'], path)
            parser.program['nodes'].append({'name': row['name'], 'kind': 'expression', 'body': body})
    for field, code_fields in (('scopes', ('condition',)), ('clauses', ('value', 'otherwise'))):
        for index, row in enumerate(response[field]):
            lowered = {key: deepcopy(value) for key, value in row.items() if not key.endswith('_code')}
            for key in code_fields:
                lowered[key] = fragment(row[key + '_code'], f'{field}[{index}].{key}_code')
            parser.program[field].append(lowered)
    parser.program['query'] = deepcopy(response['query'])
    return parser.program


def encode_compiler_program(program):
    """Render accepted declarations without changing their IR meaning."""
    if set(program) != set(FIELDS):
        raise SourceCodeError('Expected the seven internal source IR fields')
    result = {field: deepcopy(program[field]) for field in ('bindings', 'observations', 'rule_residuals')}
    result['nodes'] = [{'name': row['name'], 'kind': row['kind'], 'code': _node_code(row)}
                       for row in program['nodes']]
    for field, code_fields in (('scopes', ('condition',)), ('clauses', ('value', 'otherwise'))):
        result[field] = []
        for row in program[field]:
            rendered = {key: deepcopy(value) for key, value in row.items() if key not in code_fields}
            rendered.update({key + '_code': _render_expression(row[key]) for key in code_fields})
            result[field].append(rendered)
    result['query'] = deepcopy(program['query'])
    return {field: result[field] for field in
            ('scopes', 'clauses', 'rule_residuals', 'observations', 'bindings', 'nodes', 'query')}


class SourceCodeError(Unsupported):
    """An unsupported or ambiguous source-code construct, with its location."""

    def __init__(self, message, diagnostics=None):
        super().__init__(message)
        self.diagnostics = diagnostics or []


def _fail(node, message):
    raise SourceCodeError(f'code:{getattr(node, "lineno", 0)}:'
                          f'{getattr(node, "col_offset", 0) + 1}: {message}',
        [{'path':'code', 'line':getattr(node, 'lineno', 0),
          'column':getattr(node, 'col_offset', 0) + 1,
          'expected':message, 'actual':type(node).__name__}])


def _literal(node):
    if isinstance(node, ast.Constant) and type(node.value) in (str, int, bool, type(None)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _literal(node.operand)
        if type(value) is int:
            return -value
    if isinstance(node, ast.List):
        return [_literal(item) for item in node.elts]
    if isinstance(node, ast.Dict):
        result = {}
        for key, value in zip(node.keys, node.values):
            if key is None:
                _fail(node, 'Dictionary unpacking is not supported')
            key = _literal(key)
            if type(key) is not str or key in result:
                _fail(node, 'Literal dictionary keys must be unique strings')
            result[key] = _literal(value)
        return result
    _fail(node, 'Expected a literal string, integer, Boolean, null, list or dictionary')


def _arguments(node, names, required=None):
    if len(node.args) > len(names) or any(isinstance(a, ast.Starred) for a in node.args):
        _fail(node, 'Invalid positional arguments')
    values = dict(zip(names, node.args))
    for kw in node.keywords:
        if kw.arg not in names or kw.arg in values:
            _fail(node, 'Unknown, unpacked or duplicate argument: ' + str(kw.arg))
        values[kw.arg] = kw.value
    missing = set(names if required is None else required) - values.keys()
    if missing:
        _fail(node, 'Missing arguments: ' + ', '.join(sorted(missing)))
    return values


def _operation(op, *args):
    return {'op': op, 'args': list(args)}


def _call_name(node):
    return node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else None


class _Parser:
    def __init__(self, tree):
        self.program = {field: [] for field in FIELDS[:-1]}
        self.reserved = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.counter = 0

    def fresh(self):
        while True:
            name = '_inline_' + str(self.counter)
            self.counter += 1
            if name not in self.reserved:
                self.reserved.add(name)
                return name

    def binding(self, name, node):
        args = _arguments(node, ('value', 'sources'))
        self.program['bindings'].append({'name': name, 'type': _call_name(node),
            'value': _literal(args['value']), 'sources': _literal(args['sources'])})

    def connector(self, name, node):
        projection = _call_name(node)
        if projection in PROJECTIONS:
            args = _arguments(node, ('value',))
            graph = self.graph(args['value'])
        else:
            projection, graph = 'identity', self.graph(node)
        self.program['nodes'].append({'name': name, 'kind': 'connector',
            'body': {'graph': graph, 'project': projection}})

    def graph(self, node):
        if isinstance(node, ast.Name):
            return {'slot': node.id}
        function = _call_name(node)
        if function in PRIMITIVES:
            name = self.fresh()
            self.binding(name, node)
            return {'slot': name}
        if function == 'learned':
            args = _arguments(node, ('pattern', 'variant', 'slots', 'columns'))
            return {key: _literal(value) for key, value in args.items()}
        if function in GRAPHS:
            arity = GRAPHS[function]
            if len(node.args) != arity or any(isinstance(a, ast.Starred) for a in node.args):
                _fail(node, f'{function} requires {arity} graph inputs')
            params = {}
            for kw in node.keywords:
                if kw.arg != 'params' or params:
                    _fail(node, 'Graph parameters must be supplied once as params={...}')
                params = {'params': _literal(kw.value)}
            return {'op': function, 'inputs': [self.graph(item) for item in node.args], **params}
        _fail(node, 'Expected a connector input, one of the seven operators, or learned(...)')

    def expression(self, node):
        if isinstance(node, ast.Constant):
            return _literal(node)
        if isinstance(node, ast.Name):
            return {'var': node.id}
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return _operation('not', self.expression(node.operand))
            return _literal(node)
        if isinstance(node, ast.BoolOp):
            return _operation('and' if isinstance(node.op, ast.And) else 'or',
                              *(self.expression(v) for v in node.values))
        if isinstance(node, ast.IfExp):
            return _operation('if', self.expression(node.test), self.expression(node.body),
                              self.expression(node.orelse))
        if isinstance(node, ast.Compare):
            names = {ast.Eq: 'eq', ast.NotEq: 'ne', ast.Lt: 'lt', ast.LtE: 'le'}
            if len(node.ops) != 1 or type(node.ops[0]) not in names:
                _fail(node, 'Use a single ==, !=, < or <= comparison')
            return _operation(names[type(node.ops[0])], self.expression(node.left),
                              self.expression(node.comparators[0]))
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, (ast.Add, ast.Sub)):
                return _operation('add' if isinstance(node.op, ast.Add) else 'sub',
                                  self.expression(node.left), self.expression(node.right))
            if isinstance(node.op, ast.Mult):
                scale = _literal(node.left)
                if type(scale) is not int:
                    _fail(node.left, 'Scale requires a literal integer multiplier')
                return _operation('scale', scale, self.expression(node.right))
            if isinstance(node.op, ast.Div):
                denominator = _literal(node.right)
                if type(denominator) is not int or denominator == 0:
                    _fail(node.right, 'Division requires a nonzero literal integer denominator')
                return _operation('divide_constant', self.expression(node.left), denominator)
        if isinstance(node, ast.Subscript):
            index = _literal(node.slice)
            if type(index) is not int or index < 0:
                _fail(node.slice, 'Numeric vector index must be a nonnegative literal integer')
            return _operation('number_at', self.expression(node.value), index)
        if isinstance(node, ast.List):
            return _operation('array', *(self.expression(item) for item in node.elts))
        if isinstance(node, ast.Dict):
            pairs, seen = [], set()
            for key, value in zip(node.keys, node.values):
                if key is None:
                    _fail(node, 'Dictionary unpacking is not supported')
                key_value = _literal(key)
                if type(key_value) is not str or key_value in seen:
                    _fail(node, 'Expression dictionary keys must be unique literal strings')
                seen.add(key_value)
                pairs.append(_operation('pair', key_value, self.expression(value)))
            return _operation('object', *pairs)
        function = _call_name(node)
        if function in {'observation', 'residual', 'scope', 'clause'}:
            _fail(node, 'Declaration constructors require their own named assignment; query must read the guarded clause result')
        if function in PRIMITIVES:
            name = self.fresh()
            self.binding(name, node)
            return {'var': name}
        if function in GRAPHS or function in PROJECTIONS or function == 'learned':
            name = self.fresh()
            self.connector(name, node)
            return {'var': name}
        if function in FUNCTIONS:
            if node.keywords or any(isinstance(item, ast.Starred) for item in node.args):
                _fail(node, 'Expression operations take explicit positional arguments')
            return _operation(FUNCTIONS[function], *(self.expression(a) for a in node.args))
        _fail(node, 'Unsupported expression; attributes, tools and arbitrary Python are unavailable')

    def declaration(self, name, node):
        function = _call_name(node)
        if function in PRIMITIVES:
            self.binding(name, node)
        elif function in GRAPHS or function in PROJECTIONS or function == 'learned':
            self.connector(name, node)
        elif function in {'observation', 'residual', 'scope', 'clause'}:
            names = {'observation': ('entity', 'entity_source', 'predicate', 'predicate_source'),
                     'residual': ('source', 'quote'), 'scope': ('source', 'condition'),
                     'clause': ('sources', 'value', 'otherwise')}[function]
            args = _arguments(node, names)
            exprs = {'condition'} if function == 'scope' else {'value', 'otherwise'} if function == 'clause' else set()
            row = {'name': name, **{key: self.expression(value) if key in exprs else _literal(value)
                                   for key, value in args.items()}}
            field = {'observation': 'observations', 'residual': 'rule_residuals',
                     'scope': 'scopes', 'clause': 'clauses'}[function]
            self.program[field].append(row)
        else:
            self.program['nodes'].append({'name': name, 'kind': 'expression', 'body': self.expression(node)})


def parse_source_code(code):
    """Return the internal source IR without executing or accepting its semantics."""
    if type(code) is not str:
        raise SourceCodeError('code must be a string')
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise SourceCodeError('Invalid declarative source code: ' + str(exc),
            [{'path':'code', 'line':getattr(exc, 'lineno', None), 'column':getattr(exc, 'offset', None),
              'expected':'syntactically valid declarative assignments', 'actual':getattr(exc, 'msg', str(exc))}]) from exc
    parser, seen = _Parser(tree), set()
    for index, statement in enumerate(tree.body):
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
            _fail(statement, 'Only single-name assignments are supported')
        name = statement.targets[0].id
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', name) is None or name in seen:
            _fail(statement, 'Names must be unique ASCII identifiers of at most64 characters')
        seen.add(name)
        if name == 'query':
            if index != len(tree.body) - 1:
                _fail(statement, 'query must be the final assignment')
            parser.program['query'] = parser.expression(statement.value)
        else:
            parser.declaration(name, statement.value)
    if 'query' not in parser.program:
        raise SourceCodeError('A final query assignment is required')
    return parser.program


def _render_expression(value):
    if not isinstance(value, dict):
        if type(value) not in (int, bool, str, type(None)):
            raise SourceCodeError('Cannot render a non-IR expression literal')
        return repr(value)
    if set(value) == {'var'}:
        return value['var']
    op, args = value['op'], value['args']
    rendered = [_render_expression(a) for a in args]
    if op == 'if' and len(args) == 3:
        return '(' + rendered[1] + ' if ' + rendered[0] + ' else ' + rendered[2] + ')'
    if op == 'not' and len(args) == 1:
        return '(not ' + rendered[0] + ')'
    if op in {'and', 'or'} and len(args) >= 2:
        return '(' + (' ' + op + ' ').join(rendered) + ')'
    if op == 'array':
        return '[' + ', '.join(rendered) + ']'
    function = {'and': 'all_of', 'or': 'any_of'}.get(op, op)
    if function not in FUNCTIONS:
        raise SourceCodeError('Cannot render an unsupported or malformed expression')
    return function + '(' + ', '.join(rendered) + ')'


def _render_graph(graph):
    if set(graph) == {'slot'}:
        return graph['slot']
    if 'pattern' in graph:
        return 'learned(' + ', '.join(key + '=' + repr(graph[key])
                    for key in ('pattern', 'variant', 'slots', 'columns')) + ')'
    arguments = [_render_graph(item) for item in graph['inputs']]
    if 'params' in graph:
        arguments.append('params=' + repr(graph['params']))
    return graph['op'] + '(' + ', '.join(arguments) + ')'


def _node_code(row):
    if row['kind'] == 'expression':
        return _render_expression(row['body'])
    if row['kind'] != 'connector':
        raise SourceCodeError('Unknown internal node kind')
    body = row['body']
    value = _render_graph(body['graph'])
    if body['project'] != 'identity' or 'slot' in body['graph']:
        value = body['project'] + '(' + value + ')'
    return value


def render_source_code(program):
    """Render accepted internal IR for deterministic, semantics-free round trips."""
    if set(program) != set(FIELDS):
        raise SourceCodeError('Expected the seven internal source IR fields')
    lines = []
    for row in program['bindings']:
        lines.append(row['name'] + ' = ' + row['type'] + '(' + repr(row['value']) + ', sources=' + repr(row['sources']) + ')')
    for field, function, keys in (
        ('observations', 'observation', ('entity', 'entity_source', 'predicate', 'predicate_source')),
        ('rule_residuals', 'residual', ('source', 'quote')),
    ):
        for row in program[field]:
            lines.append(row['name'] + ' = ' + function + '(' + ', '.join(key + '=' + repr(row[key]) for key in keys) + ')')
    for row in program['nodes']:
        lines.append(row['name'] + ' = ' + _node_code(row))
    for row in program['scopes']:
        lines.append(row['name'] + ' = scope(source=' + repr(row['source']) + ', condition=' + _render_expression(row['condition']) + ')')
    for row in program['clauses']:
        lines.append(row['name'] + ' = clause(sources=' + repr(row['sources']) + ', value=' + _render_expression(row['value']) + ', otherwise=' + _render_expression(row['otherwise']) + ')')
    lines.append('query = ' + _render_expression(program['query']))
    return '\n'.join(lines) + '\n'
