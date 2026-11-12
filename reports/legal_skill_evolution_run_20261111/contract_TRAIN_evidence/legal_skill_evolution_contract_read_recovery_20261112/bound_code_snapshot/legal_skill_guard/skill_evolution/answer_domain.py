"""Conservatively prove a helper cannot satisfy the existing native enum."""
import ast
from functools import lru_cache


def constants(expression):
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return frozenset((expression.value,))
    if isinstance(expression, ast.IfExp):
        left, right = constants(expression.body), constants(expression.orelse)
        return left | right if left is not None and right is not None else None
    return None


@lru_cache(maxsize=256)
def literal_answers(procedure):
    try:tree = ast.parse(procedure)
    except (SyntaxError, RecursionError):return None
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(functions) != 1 or functions[0].name != 'apply':return None
    function = functions[0]
    if tree.body != [function] or function.decorator_list:return None
    args = function.args
    if args.posonlyargs or args.vararg or args.kwarg or args.kwonlyargs or args.defaults:return None
    nodes = list(ast.walk(functions[0]))
    if any(isinstance(n, (ast.Match, ast.Try, ast.TryStar, ast.With, ast.AsyncWith,
                          ast.ClassDef, ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)) for n in nodes):return None
    if [a.arg for a in functions[0].args.args] != ['inputs', 'premises']:return None
    parents = {id(child): parent for parent in nodes for child in ast.iter_child_nodes(parent)}
    returns, possible = [n for n in nodes if isinstance(n, ast.Return)], frozenset()
    if not returns:return None
    for node in returns:
        record = node.value
        if not isinstance(record, ast.Dict) or any(not isinstance(k, ast.Constant) or not isinstance(k.value, str) for k in record.keys):return None
        keys = [k.value for k in record.keys]
        if len(set(keys)) != len(keys) or 'answer' not in keys:return None
        expression = record.values[keys.index('answer')]
        values = constants(expression)
        if isinstance(expression, ast.Name) and expression.id not in ('inputs', 'premises'):
            stores = [n for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id == expression.id]
            if not stores:return None
            values = frozenset()
            for store in stores:
                assignment = parents[id(store)]
                if not isinstance(assignment, ast.Assign) or len(assignment.targets) != 1 or assignment.targets[0] is not store:return None
                assigned = constants(assignment.value)
                if assigned is None:return None
                values |= assigned
        if values is None:return None
        possible |= values
    return possible


def incompatible_native_enum(procedure, schema):
    allowed = schema.get('enum')
    if schema.get('type') != 'string' or not allowed or not all(isinstance(v, str) for v in allowed):return None
    possible = literal_answers(procedure)
    if possible is None or possible & set(allowed):return None
    return {'criterion': 'Every possible successful answer is a literal string outside the existing native enum.',
            'possible_answers': sorted(possible), 'native_allowed_answers': allowed}
