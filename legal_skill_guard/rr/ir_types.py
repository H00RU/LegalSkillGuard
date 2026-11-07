"""Static expression checks, including inactive branches; no coercion or repair."""
from __future__ import annotations

from fractions import Fraction

FIXED_ARITIES = {"if": 3, "not": 1, "xor": 2, "eq": 2, "ne": 2, "lt": 2,
                 "le": 2, "sub": 2, "scale": 2, "divide_constant": 2,
                 "ceil_divide_constant": 2, "number_at": 2, "pair": 2}
NONEMPTY_OPERATORS = frozenset({"min", "max"})


class IRTypeError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__(str(diagnostics))


def check_expression(body, slots, *, slot_types=None):
    errors = []

    def issue(path, expected, actual):
        errors.append({"path": path, "expected": expected, "actual": actual})

    def literal_type(value):
        if type(value) is bool:
            return "boolean"
        if type(value) in (int, Fraction):
            return "number"
        if isinstance(value, str):
            return "string"
        if value is None:
            return "null"
        if isinstance(value,list) and value and all(type(v) in (int,Fraction) for v in value):
            return 'numbers'
        return "array" if isinstance(value, list) else "object" if isinstance(value, dict) else type(value).__name__

    def infer(node, path):
        if not isinstance(node, dict):
            return {literal_type(node)}
        if set(node) == {"var"}:
            if slot_types is not None and node['var'] in slot_types:
                return set(slot_types[node['var']])
            if node["var"] not in slots:
                issue(path + ".var", "bound variable name", repr(node["var"]))
                return {"invalid"}
            return {literal_type(slots[node["var"]])}
        if set(node) != {"op", "args"} or not isinstance(node["args"], list):
            issue(path, "object with op and args array", repr(node))
            return {"invalid"}
        op, args = node["op"], node["args"]
        if op in FIXED_ARITIES and len(args) != FIXED_ARITIES[op] or op in NONEMPTY_OPERATORS and not args:
            issue(path + ".args", f"arity {FIXED_ARITIES.get(op, 'at least 1')}", len(args))
            return {"invalid"}
        types = [infer(arg, f"{path}.args[{i}]") for i, arg in enumerate(args)]

        def require(i, wanted):
            allowed = {"array", "pair", "numbers"} if wanted == "array" else {wanted}
            if not types[i] <= allowed:
                issue(f"{path}.args[{i}]", wanted, sorted(types[i]))

        if op == "if":
            require(0, "boolean")
            return types[1] | types[2]
        if op in {"and", "or", "xor", "not"}:
            for i in range(len(args)):
                require(i, "boolean")
            return {"boolean"}
        if op in {"eq", "ne"}:
            return {"boolean"}  # evaluator explicitly defines cross-type inequality
        if op in {"add", "sub", "min", "max", "lt", "le", "scale", "divide_constant", "ceil_divide_constant"}:
            for i in range(len(args)):
                require(i, "number")
            if op == "scale" and type(args[0]) not in (int, Fraction):
                issue(path + ".args[0]", "literal numeric scale constant", args[0])
            if op == "divide_constant" and (type(args[1]) not in (int, Fraction) or args[1] == 0):
                issue(path + ".args[1]", "nonzero literal numeric denominator", args[1])
            if op == 'ceil_divide_constant' and (type(args[1]) not in (int,Fraction) or args[1] <= 0):
                issue(path+'.args[1]','positive literal numeric denominator',args[1])
            return {"boolean" if op in {"lt", "le"} else "number"}
        if op == 'number_at':
            require(0,'numbers');require(1,'number')
            if type(args[1]) is not int or args[1] < 0:
                issue(path+'.args[1]','nonnegative literal integer index',args[1])
            return {'number'}
        if op == "array":
            return {'numbers'} if types and all(t<={'number'} for t in types) else {"array"}
        if op == "pair":
            require(0, "string")
            return {"pair"}
        if op == "object":
            for i in range(len(args)):
                require(i, "pair")
            return {"object"}
        if op == "concat":
            for i in range(len(args)):
                require(i, "array")
            return {'numbers'} if types and all(t<={'numbers'} for t in types) else {"array"}
        issue(path + ".op", "supported expression operator", op)
        return {"invalid"}

    result_types = infer(body["query"], "program.body.query")
    nodes = {"query"} | {"binding:" + name for name in slots}
    for source, values in body.get("source_links", {}).items():
        for i, value in enumerate(values):
            if value not in nodes:
                issue(f"program.body.source_links.{source}[{i}]", "existing semantic node (query or binding:NAME)", value)
    if errors:
        raise IRTypeError(errors)
    return {"pass": True, "all_branches_checked": True, 'result_types': sorted(result_types)}
