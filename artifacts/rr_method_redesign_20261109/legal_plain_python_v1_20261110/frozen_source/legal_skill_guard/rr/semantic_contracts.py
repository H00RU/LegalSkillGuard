"""Small symbolic kernel for the redesign pilot, not a source-truth oracle.

Names, types, source quotes and scope are explicit. Proofs compare supplied
programs over supplied domains; they never certify natural-language fidelity.
No generated Python is executed.
"""
import ast
from itertools import combinations
import z3


class ContractError(ValueError):
    pass


def variables(signature):
    if not signature or any(not k.isidentifier() for k in signature):
        raise ContractError('An explicit nonempty input signature is required')
    if any(t not in {'integer', 'boolean'} for t in signature.values()):
        raise ContractError('Only explicit integer and Boolean inputs are supported')
    return {k: (z3.Int(k) if t == 'integer' else z3.Bool(k)) for k, t in signature.items()}


def expression(text, symbols):
    def positive(x):
        proof = z3.Solver(); proof.set(timeout=1000); proof.add(x <= 0)
        return proof.check() == z3.unsat

    def integer(x):
        if not z3.is_int(x):
            raise ContractError('Integer operand required')
        return x

    def boolean(x):
        if not z3.is_bool(x):
            raise ContractError('Boolean operand required')
        return x

    def go(node):
        if isinstance(node, ast.Constant):
            if type(node.value) is bool:
                return z3.BoolVal(node.value)
            if type(node.value) is int:
                return z3.IntVal(node.value)
        if isinstance(node, ast.Name) and node.id in symbols:
            return symbols[node.id]
        if isinstance(node, ast.UnaryOp):
            arg = go(node.operand)
            if isinstance(node.op, ast.Not):
                return z3.Not(boolean(arg))
            if isinstance(node.op, ast.USub):
                return -integer(arg)
        if isinstance(node, ast.BinOp):
            a, b = integer(go(node.left)), integer(go(node.right))
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            # Positive denominators make Python // and SMT integer division
            # identical even when the numerator is negative.
            if isinstance(node.op, ast.FloorDiv) and positive(b):
                return a / b
        if isinstance(node, ast.IfExp):
            cond, yes, no = boolean(go(node.test)), go(node.body), go(node.orelse)
            if yes.sort() != no.sort():
                raise ContractError('Conditional branches have different types')
            return z3.If(cond, yes, no)
        if isinstance(node, ast.BoolOp):
            args = [boolean(go(n)) for n in node.values]
            return z3.And(*args) if isinstance(node.op, ast.And) else z3.Or(*args)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            a, b = go(node.left), go(node.comparators[0])
            if a.sort() != b.sort():
                raise ContractError('Comparison types differ')
            op = node.ops[0]
            if isinstance(op, ast.Eq):
                return a == b
            if isinstance(op, ast.NotEq):
                return a != b
            integer(a); integer(b)
            if isinstance(op, ast.Lt):
                return a < b
            if isinstance(op, ast.LtE):
                return a <= b
            if isinstance(op, ast.Gt):
                return a > b
            if isinstance(op, ast.GtE):
                return a >= b
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            args = [integer(go(n)) for n in node.args]
            if node.func.id in {'min', 'max'} and len(args) >= 2:
                out = args[0]
                for other in args[1:]:
                    out = z3.If(out <= other if node.func.id == 'min' else out >= other, out, other)
                return out
            if node.func.id == 'ceildiv' and len(args) == 2 and positive(args[1]):
                return -((-args[0]) / args[1])
        raise ContractError('Unsupported expression node: ' + ast.dump(node, include_attributes=False))

    try:
        return z3.simplify(go(ast.parse(text, mode='eval').body))
    except (SyntaxError, z3.Z3Exception) as exc:
        raise ContractError(str(exc)) from exc


def validate_module(module, signature, rule_text):
    if set(module) != {'expression', 'rule_quotes', 'scope_notes', 'unresolved_requirements'}:
        raise ContractError('Module fields differ from the pilot schema')
    if not module['rule_quotes'] or any(not q or q not in rule_text for q in module['rule_quotes']):
        raise ContractError('All rule quotes must occur verbatim in the supplied policy')
    # Quote membership is provenance only, never an automatic semantic grade.
    return expression(module['expression'], variables(signature))


def compare_modules(left, right, signature, domain):
    syms = variables(signature)
    a, b = expression(left, syms), expression(right, syms)
    if a.sort() != b.sort():
        raise ContractError('Output types differ')
    guard = expression(domain, syms)
    if not z3.is_bool(guard):
        raise ContractError('A Boolean domain is required')
    solver = z3.Solver(); solver.set(timeout=3000)
    solver.add(guard)
    if solver.check() != z3.sat:
        raise ContractError('Empty or undecidable comparison domain is not evidence of equivalence')
    solver.add(a != b)
    status = solver.check()
    out = {'status': str(status), 'agreement_guard': z3.simplify(z3.And(guard, a == b)).sexpr(),
           'equivalent_over_supplied_domain': status == z3.unsat,
           'natural_language_faithfulness_proved': False}
    if status == z3.sat:
        model = solver.model()
        def value(x):
            return z3.is_true(x) if z3.is_bool(x) else x.as_long()
        out['witness'] = {k: value(model.eval(v, model_completion=True)) for k, v in syms.items()}
        out['left_value'] = value(model.eval(a, model_completion=True))
        out['right_value'] = value(model.eval(b, model_completion=True))
    elif status == z3.unknown:
        out['reason_unknown'] = solver.reason_unknown()
    return out


def evaluate(text, signature, binding):
    if set(binding) != set(signature):
        raise ContractError('No omitted or invented binding is permitted')
    syms = variables(signature)
    pairs = []
    for k, kind in signature.items():
        expected = int if kind == 'integer' else bool
        if type(binding[k]) is not expected:
            raise ContractError('Concrete binding type differs: ' + k)
        pairs.append((syms[k], z3.IntVal(binding[k]) if expected is int else z3.BoolVal(binding[k])))
    result = z3.simplify(z3.substitute(expression(text, syms), *pairs))
    if z3.is_int_value(result):
        return result.as_long()
    if z3.is_true(result) or z3.is_false(result):
        return z3.is_true(result)
    raise ContractError('Binding did not yield one concrete output')


def minimum_separating_batch(worlds, answers, batches):
    """Exact small-pilot weighted separation, a standard set-cover control.

    Worlds must be supplied by actual candidate binding/contract construction.
    This routine cannot invent correct worlds or judge model observations.
    Each batch has fields, positive cost and ID. It must distinguish every
    remaining pair with different answers; empty-world unanimity is rejected.
    """
    if not worlds or len(worlds) != len(answers):
        raise ContractError('Nonempty aligned worlds and answers required')
    pairs = [(a, b) for a, b in combinations(range(len(worlds)), 2) if answers[a] != answers[b]]
    choices = []
    for n in range(len(batches) + 1):
        for ids in combinations(range(len(batches)), n):
            if any(type(batches[i]['cost']) not in (int, float) or batches[i]['cost'] <= 0 for i in ids):
                raise ContractError('Positive measured/declared costs required')
            fields = set().union(*(set(batches[i]['fields']) for i in ids)) if ids else set()
            if all(any(worlds[a][f] != worlds[b][f] for f in fields) for a, b in pairs):
                choices.append((sum(batches[i]['cost'] for i in ids), len(ids), tuple(batches[i]['id'] for i in ids)))
    if not choices:
        return {'status': 'unseparable', 'selected': [], 'cost': None, 'different_answer_pairs': len(pairs)}
    cost, _, selected = min(choices)
    return {'status': 'already_unanimous' if not pairs else 'separating', 'selected': list(selected),
            'cost': cost, 'different_answer_pairs': len(pairs), 'new_method_advantage_proved': False}
