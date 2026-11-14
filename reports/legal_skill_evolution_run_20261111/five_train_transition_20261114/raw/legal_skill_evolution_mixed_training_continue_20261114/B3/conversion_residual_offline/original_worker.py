"""Host-only executed conversion-guard diagnostics; generated code is unchanged.

Observe actual STORE_FAST/CALL instructions so same-line conditional assignments
are not guessed from line numbers. Keep original JSON objects and exact type()
semantics. The trace supplies read hints, never facts or a legal answer.
"""
import ast
import builtins
import dis
import inspect
import json
from pathlib import Path
import resource
import runpy
import sys


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    request = json.load(sys.stdin)
    tree = ast.parse(request['program'])
    parent = {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    original_objects = {}
    def index(value, path):
        if isinstance(value, (dict, list)):
            original_objects[id(value)] = path
            for key, child in (value.items() if isinstance(value, dict) else enumerate(value)):
                index(child, path + [key])
    index(request['inputs'], [])
    derived_fields, derived_objects, frames, bytecode = {}, {}, {}, {}
    nodes_by_line = {}
    for node in ast.walk(tree):
        if hasattr(node, 'lineno'):
            nodes_by_line.setdefault(node.lineno, []).append(node)
    mutations, assignments = [], []
    filename = '<learned-conversion-residual>'

    def union(*items):
        result = []
        for values in items:
            for value in values:
                if value not in result:
                    result.append(value)
        return result

    def object_value(node, frame):
        if isinstance(node, ast.Name):
            return frame.f_locals.get(node.id)
        if isinstance(node, ast.Constant):
            return node.value
        return None  # Never evaluate a generated expression a second time.

    def paths(node, frame, state):
        if node is None:
            return []
        if isinstance(node, ast.Name):
            value = frame.f_locals.get(node.id)
            return state['variables'].get(node.id, [original_objects[id(value)]] if id(value) in original_objects else [])
        base = key = None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'get' and node.args:
            base, key = node.func.value, object_value(node.args[0], frame)
        elif isinstance(node, ast.Subscript) and not isinstance(node.slice, ast.Slice):
            base, key = node.value, object_value(node.slice, frame)
        if base is not None and isinstance(base, ast.Name) and type(key) in (str, int):
            obj = frame.f_locals.get(base.id)
            if id(obj) in original_objects:
                return [original_objects[id(obj)] + [key]]
            if (id(obj), key) in derived_fields:
                return derived_fields[id(obj), key]
        return union(*(paths(child, frame, state) for child in ast.iter_child_nodes(node)))

    def controls(node):
        result = []
        ancestor = parent.get(id(node))
        while ancestor is not None and not isinstance(ancestor, ast.FunctionDef):
            if isinstance(ancestor, ast.If):
                result.append(ancestor.test)
            ancestor = parent.get(id(ancestor))
        return result

    def node_at(instruction, kind):
        pos = instruction.positions
        if pos.lineno is None:
            return None
        candidates = []
        for node in nodes_by_line.get(pos.lineno, []):
            if not isinstance(node, kind) or getattr(node, 'lineno', -1) != pos.lineno:
                continue
            if node.col_offset <= (pos.col_offset or 0) < getattr(node, 'end_col_offset', 10**9):
                candidates.append(node)
        return min(candidates, key=lambda n: getattr(n, 'end_col_offset', 0) - n.col_offset) if candidates else None

    def flush(frame, state):
        pending = state.pop('store', None)
        if pending:
            name, node, dependencies = pending
            state['variables'][name] = dependencies
            value = frame.f_locals.get(name)
            if isinstance(value, dict) and isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                derived_objects[id(value)] = value
                for key, child in zip(node.value.keys, node.value.values):
                    if isinstance(key, ast.Constant):
                        derived_fields[id(value), key.value] = paths(child, frame, state)
            if value is False and dependencies:
                assignments.append({'function': frame.f_code.co_name, 'variable': name,
                    'line': node.lineno if node is not None else frame.f_lineno,
                    'cause_paths': dependencies})
        pending = state.pop('mutation', None)
        if pending:
            obj, before, node, cause = pending
            after = {x for x in obj if isinstance(x, str)} if isinstance(obj, (list, set)) else set()
            added = sorted(after - before)
            if added:
                mutations.append({'function': frame.f_code.co_name, 'line': node.lineno,
                    'expression': ast.unparse(node), 'added_strings': added, 'cause_paths': cause})

    def trace(frame, event, arg):
        if frame.f_code.co_filename != filename:
            return trace
        key = id(frame)
        if event == 'call':
            frame.f_trace_opcodes = True
            variables = {}
            for name, value in frame.f_locals.items():
                if id(value) in original_objects:
                    variables[name] = [original_objects[id(value)]]
            caller = frame.f_back
            if caller is not None and id(caller) in frames:
                caller_state = frames[id(caller)]
                instruction = bytecode.get(caller.f_code, {}).get(caller.f_lasti)
                call = node_at(instruction, ast.Call) if instruction is not None else None
                if call is not None:
                    parameters = list(inspect.getargvalues(frame).args)
                    for name, expression in zip(parameters, call.args):
                        variables[name] = paths(expression, caller, caller_state)
            frames[key] = {'variables': variables}
            if frame.f_code not in bytecode:
                bytecode[frame.f_code] = {i.offset: i for i in dis.get_instructions(frame.f_code)}
            return trace
        state = frames[key]
        flush(frame, state)
        if len(assignments) + len(mutations) > 8192:
            raise ValueError('Conversion diagnostic exceeds its trace bound')
        if event == 'opcode':
            instruction = bytecode[frame.f_code].get(frame.f_lasti)
            if instruction is None:
                return trace
            if instruction.opname == 'STORE_FAST':
                node = node_at(instruction, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.For))
                if node is not None:
                    expr = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else node
                    dependencies = union(paths(expr, frame, state), *(paths(c, frame, state) for c in controls(node)))
                    state['store'] = (instruction.argval, node, dependencies)
            elif instruction.opname == 'CALL':
                node = node_at(instruction, ast.Call)
                if (node is not None and isinstance(node.func, ast.Attribute)
                        and node.func.attr in ('add', 'append', 'extend', 'update')
                        and isinstance(node.func.value, ast.Name)):
                    obj = frame.f_locals.get(node.func.value.id)
                    if isinstance(obj, (list, set)):
                        before = {x for x in obj if isinstance(x, str)}
                        cause = union(*(paths(c, frame, state) for c in controls(node)))
                        state['mutation'] = (obj, before, node, cause)
        elif event == 'return':
            instruction = bytecode[frame.f_code].get(frame.f_lasti)
            node = node_at(instruction, ast.Return) if instruction is not None else None
            if isinstance(arg, dict) and node is not None and isinstance(node.value, ast.Dict):
                derived_objects[id(arg)] = arg
                for field, expression in zip(node.value.keys, node.value.values):
                    if isinstance(field, ast.Constant):
                        derived_fields[id(arg), field.value] = paths(expression, frame, state)
            frames.pop(key, None)
        return trace

    shared = runpy.run_path(str(Path(__file__).with_name('span_compiler_worker.py')))
    names = ('min', 'max', 'sum', 'len', 'abs', 'round', 'sorted', 'all', 'any', 'int', 'float', 'bool',
        'str', 'list', 'dict', 'set', 'tuple', 'range', 'enumerate', 'zip', 'isinstance', 'ValueError', 'KeyError', 'TypeError', 'type')
    scope = {'__builtins__': {name: getattr(builtins, name) for name in names}}
    for name in ('re', 'bind_scope', 'calendar_year', 'year_days', 'inclusive_year_overlap_days', 'elapsed_year_overlap_days'):
        scope[name] = shared[name]
    exec(compile(tree, filename, 'exec'), scope)
    sys.settrace(trace)
    try:
        result = scope['apply'](request['inputs'], {})
    finally:
        sys.settrace(None)
    reasons = set(result.get('unresolved', []))
    blocking = [m for m in mutations if reasons.intersection(m['added_strings'])]
    body = json.dumps({'result': result, 'blocking_writes': blocking,
        'executed_false_assignments': assignments, 'program_bytes_unchanged': True}, ensure_ascii=False)
    if len(body) > 1024 * 1024:
        raise ValueError('Oversized conversion diagnostic')
    sys.stdout.write(body)


if __name__ == '__main__':
    main()
