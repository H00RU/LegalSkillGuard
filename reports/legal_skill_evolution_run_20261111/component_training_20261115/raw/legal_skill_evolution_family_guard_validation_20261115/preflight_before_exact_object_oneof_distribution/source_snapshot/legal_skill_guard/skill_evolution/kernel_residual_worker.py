"""Host-only dependency instrumentation; never exposed to generated programs."""
import ast
import builtins
import inspect
import json
from pathlib import Path
import resource
import runpy
import sys


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    request = json.load(sys.stdin)
    tree = ast.parse(request['program'])
    events, versions, guards = [], {}, {}
    objects = {}
    def index(value, path):
        if isinstance(value, (dict, list)):
            objects[id(value)] = path
            iterator = value.items() if isinstance(value, dict) else enumerate(value)
            for key, child in iterator:
                index(child, path + [key])
    index(request['inputs'], [])

    def mark(kind, identity, value, targets, dependencies, accesses, controls):
        if len(events) >= 8192:
            raise ValueError('Residual trace exceeds its diagnostic bound')
        local = inspect.currentframe().f_back.f_locals
        data_parents = {versions[n] for n in dependencies if n in versions}
        parents = data_parents | {guards[n] for n in controls if n in guards}
        paths = []
        for name, key in accesses:
            obj = local.get(name)
            if id(obj) in objects:
                path = objects[id(obj)] + [key]
                if path not in paths:
                    paths.append(path)
        entry = {'id': len(events), 'kind': kind, 'source_id': identity,
            'parents': sorted(parents), 'data_parents': sorted(data_parents),
            'controls': [guards[n] for n in controls if n in guards],
            'targets': targets, 'input_paths': paths}
        events.append(entry)
        if kind == 'guard':
            entry['truth'] = bool(value)
            guards[identity] = entry['id']
            return entry['truth']
        if kind == 'definition':
            for name in targets:
                versions[name] = entry['id']
        if kind == 'return':
            entry['value'] = value
        return value

    class Instrument(ast.NodeTransformer):
        def __init__(self):
            self.controls = []
            self.sources = {}
            self.counter = 0

        def identity(self, node):
            identity = str(self.counter)
            self.counter += 1
            self.sources[identity] = {'line': node.lineno, 'expression': ast.unparse(node)}
            return identity

        def call(self, kind, identity, value, targets, expr, controls):
            names = sorted({n.id for n in ast.walk(expr) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)})
            accesses = []
            for n in ast.walk(expr):
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'get'
                        and isinstance(n.func.value, ast.Name) and n.args and isinstance(n.args[0], ast.Constant)):
                    accesses.append([n.func.value.id, n.args[0].value])
                if (isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Load)
                        and isinstance(n.value, ast.Name) and isinstance(n.slice, ast.Constant)):
                    accesses.append([n.value.id, n.slice.value])
            return ast.Call(func=ast.Name(id='__host_residual_mark__', ctx=ast.Load()),
                args=[ast.Constant(kind), ast.Constant(identity), value,
                    ast.parse(repr(targets), mode='eval').body, ast.parse(repr(names), mode='eval').body,
                    ast.parse(repr(accesses), mode='eval').body, ast.parse(repr(controls), mode='eval').body], keywords=[])

        def block(self, statements):
            result = []
            for statement in statements:
                replacement = self.visit(statement)
                result.extend(replacement if isinstance(replacement, list) else [replacement])
            return result

        def visit_If(self, node):
            identity = self.identity(node.test)
            node.test = self.call('guard', identity, node.test, [], node.test, self.controls)
            self.controls.append(identity)
            node.body = self.block(node.body)
            node.orelse = self.block(node.orelse)
            self.controls.pop()
            return node

        def visit_For(self, node):
            identity = self.identity(node)
            targets = [n.id for n in ast.walk(node.target) if isinstance(n, ast.Name)]
            marker = ast.Expr(self.call('definition', identity, ast.Constant(None), targets, node.iter, self.controls))
            node.body = [marker, *self.block(node.body)]
            node.orelse = self.block(node.orelse)
            return node

        def visit_Assign(self, node):
            targets = [n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
            identity = self.identity(node)
            return [node, ast.Expr(self.call('definition', identity, ast.Constant(None), targets, node.value, self.controls))]

        def visit_AugAssign(self, node):
            targets = [node.target.id] if isinstance(node.target, ast.Name) else []
            identity = self.identity(node)
            return [node, ast.Expr(self.call('definition', identity, ast.Constant(None), targets, node, self.controls))]

        def visit_Expr(self, node):
            call = node.value
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr in ('append', 'extend', 'add', 'update', 'pop') and isinstance(call.func.value, ast.Name)):
                identity = self.identity(node)
                return [node, ast.Expr(self.call('definition', identity, ast.Constant(None), [call.func.value.id], call, self.controls))]
            return node

        def visit_Return(self, node):
            identity = self.identity(node)
            node.value = self.call('return', identity, node.value, [], node.value, self.controls)
            return node

    instrument = Instrument()
    tree = ast.fix_missing_locations(instrument.visit(tree))
    shared = runpy.run_path(str(Path(__file__).with_name('span_compiler_worker.py')))
    names = ('min', 'max', 'sum', 'len', 'abs', 'round', 'sorted', 'all', 'any', 'int', 'float', 'bool',
        'str', 'list', 'dict', 'set', 'tuple', 'range', 'enumerate', 'zip', 'isinstance', 'ValueError', 'KeyError', 'TypeError', 'type')
    scope = {'__builtins__': {n: getattr(builtins, n) for n in names}, '__host_residual_mark__': mark}
    for name in ('re', 'bind_scope', 'calendar_year', 'year_days', 'inclusive_year_overlap_days', 'elapsed_year_overlap_days'):
        scope[name] = shared[name]
    exec(compile(tree, '<instrumented-legal-kernel>', 'exec'), scope)
    result = scope['apply'](request['inputs'], request.get('premises', {}))
    body = json.dumps({'result': result, 'events': events, 'source_nodes': instrument.sources}, ensure_ascii=False)
    if len(body) > 1024 * 1024:
        raise ValueError('Oversized residual diagnostic')
    sys.stdout.write(body)


if __name__ == '__main__':
    main()
