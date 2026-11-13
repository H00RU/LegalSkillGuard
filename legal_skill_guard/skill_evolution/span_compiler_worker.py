"""Isolated pure text/record execution, shared by compiler and free control."""
import json
import re
import resource
import sys
from pathlib import Path

# Trusted, law-free calendar primitives are equally available to every arm.
# Generated programs still have no import or filesystem capabilities.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from calendar_ops import (calendar_year, elapsed_year_overlap_days,
                          inclusive_year_overlap_days, year_days)
sys.path.pop(0)


def bind_scope(template, bindings):
    """Pure structural substitution; the source program supplies every value."""
    if isinstance(template, dict):
        if set(template) != {'$scope'}:
            raise ValueError('Invalid inherited scope placeholder')
        index=template['$scope']
        if type(index) is not int or not 0 <= index < len(bindings):
            raise ValueError('Unresolved inherited scope variable')
        return bindings[index]
    if isinstance(template, list):
        return [bind_scope(t,bindings) for t in template]
    return template


def trace_functions(scope, code):
    """Host-owned diagnostics; generated code receives no new capabilities."""
    import ast
    calls, active = [], []
    budget = {'bytes': 0, 'truncated': False}

    def snapshot(value):
        def clean(obj, depth=0):
            if depth > 10:
                budget['truncated'] = True
                return {'trace_truncated': True}
            if obj is None or isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, SourceValues):
                return {'known': {k: clean(v, depth + 1) for k, v in dict.items(obj)},
                        'unresolved': sorted(obj.unresolved)}
            if isinstance(obj, dict):
                if len(obj) > 128:
                    budget['truncated'] = True
                return {str(k): clean(v, depth + 1) for k, v in list(obj.items())[:128]}
            if isinstance(obj, (list, tuple, set)):
                if len(obj) > 128:
                    budget['truncated'] = True
                return [clean(v, depth + 1) for v in list(obj)[:128]]
            return {'trace_python_type': type(obj).__name__}
        body = json.dumps(clean(value), ensure_ascii=False, allow_nan=False)
        if len(body) > 32768 or budget['bytes'] + len(body) > 256 * 1024:
            budget['truncated'] = True
            return {'trace_truncated': True}
        budget['bytes'] += len(body)
        return json.loads(body)

    def wrap(name, fn):
        def invoke(*args, **kwargs):
            if len(calls) >= 2048:
                budget['truncated'] = True
                return fn(*args, **kwargs)
            entry = {'id': len(calls), 'parent': active[-1] if active else None,
                     'function': name, 'arguments': snapshot({'positional': args, 'keywords': kwargs})}
            calls.append(entry)
            active.append(entry['id'])
            try:
                value = fn(*args, **kwargs)
                entry['returned'] = snapshot(value)
                return value
            finally:
                active.pop()
        return invoke

    for node in ast.parse(code).body:
        if isinstance(node, ast.FunctionDef):
            scope[node.name] = wrap(node.name, scope[node.name])
    return calls, budget


class SourceValues(dict):
    """Unknown source fields cannot silently become defaults or absence."""
    def __init__(self, values, unresolved):
        super().__init__(values)
        self.unresolved = set(unresolved)

    def check(self, key):
        if key in self.unresolved:raise ValueError('Unresolved source field accessed: ' + key)

    def __getitem__(self, key):
        self.check(key);return super().__getitem__(key)

    def get(self, key, default=None):
        self.check(key);return super().get(key, default)

    def __contains__(self, key):
        self.check(key);return super().__contains__(key)

    def whole(self):
        if self.unresolved:raise ValueError('Whole-map observation of unresolved source values')

    def __iter__(self):
        self.whole();return super().__iter__()

    def __len__(self):
        self.whole();return super().__len__()

    def keys(self):
        self.whole();return super().keys()

    def values(self):
        self.whole();return super().values()

    def items(self):
        self.whole();return super().items()

    def __repr__(self):
        self.whole();return super().__repr__()

    __str__ = __repr__

    def pop(self, key, *default):
        self.check(key);return super().pop(key, *default)

    def __setitem__(self, key, value):
        self.check(key);return super().__setitem__(key, value)

    def update(self, values):
        for key in values:self.check(key)
        return super().update(values)


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    request = json.load(sys.stdin)
    for record in request['premises'].get('records', []):
        if record.get('unresolved_fields'):
            record['values'] = SourceValues(record['values'], record['unresolved_fields'])
    import builtins
    names = ('min', 'max', 'sum', 'len', 'abs', 'round', 'sorted', 'all', 'any',
        'int', 'float', 'bool', 'str', 'list', 'dict', 'set', 'tuple', 'range',
        'enumerate', 'zip', 'isinstance', 'ValueError', 'KeyError', 'TypeError')
    scope = {'__builtins__': {n: getattr(builtins, n) for n in names}, 're': re, 'bind_scope': bind_scope,
        'calendar_year': calendar_year, 'year_days': year_days,
        'inclusive_year_overlap_days': inclusive_year_overlap_days,
        'elapsed_year_overlap_days': elapsed_year_overlap_days}
    exec(compile(request['procedure'], '<learned-source-procedure>', 'exec'), scope)
    if request.get('trace', False):
        calls, trace_budget = trace_functions(scope, request['procedure'])
    value = scope['apply'](request['inputs'], request['premises'])
    body = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(body) > 1024 * 1024:raise ValueError('Oversized learned result')
    if request.get('trace', False):
        body = json.dumps({'result': value, 'calls': calls, 'trace_truncated': trace_budget['truncated']},
                          ensure_ascii=False, allow_nan=False)
    sys.stdout.write(body)


if __name__ == '__main__':main()
