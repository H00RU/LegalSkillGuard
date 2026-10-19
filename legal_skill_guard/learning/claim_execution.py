"""Public-source claim execution with ASCII references and small expressions.

Both arms may write the same inline expression; a learned operator merely
reuses it. No Gold, expert categories, solver, I/O, arbitrary Python execution
or post-answer repair is available. Reusable constants bind to ORIGINAL law
money lexemes. The model supplies asset names/values and chooses eligibility;
it does not have to learn an exact-quotation or hashed-money-reference task.
"""
from __future__ import annotations

import ast
import re
from decimal import Decimal

from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

MONEY = re.compile(r"\$(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?(?![\d,])")


class InvalidClaimProgram(ValueError):
    """Invalid actions are failed attempts, not fallback answers."""


def law_blocks(statutes):
    result = {}
    for paragraph in statutes.split("\n\n"):
        lines = paragraph.splitlines()
        headers = [i for i, line in enumerate(lines) if "§" in line and len(line) < 120]
        if headers:
            i = headers[0]
            header = lines[i].strip()
            if header in result:
                raise InvalidClaimProgram("Duplicate original law header")
            result[header] = "\n".join(lines[i + 1:])
    return result


def source_money(literal):
    if not isinstance(literal, str) or MONEY.fullmatch(literal) is None:
        raise InvalidClaimProgram("One exact original money lexeme is required")
    return Decimal(literal[1:].replace(",", ""))


def source_registry(statutes):
    laws = {}
    for citation in law_blocks(statutes):
        lid = "L" + csha(citation)[:8].upper()
        if lid in laws:
            raise InvalidClaimProgram("Law-reference collision")
        laws[lid] = {"citation": citation}
    return {"laws": laws}


def debtor_count(facts):
    match = re.search(r"\(hereinafter the (Debtors|Debtor)\)", facts)
    if match is None:
        raise InvalidClaimProgram("Public debtor-count marker absent")
    return Decimal(2 if match.group(1) == "Debtors" else 1)


def execute_limit(expression, facts, statutes, *, asset_value=Decimal(0), reusable=False):
    if not isinstance(expression, str) or len(expression) > 512:
        raise InvalidClaimProgram("A short limit expression is required")
    if expression == "unlimited":
        return None, []
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise InvalidClaimProgram("Invalid arithmetic expression") from exc
    if len(list(ast.walk(tree))) > 64:
        raise InvalidClaimProgram("Expression operation budget exceeded")
    constants, used = {}, []
    for citation, body in law_blocks(statutes).items():
        for literal in dict.fromkeys(MONEY.findall(body)):
            constants.setdefault(source_money(literal), []).append(
                {"citation": citation, "literal": literal})
    if not reusable:
        for literal in dict.fromkeys(MONEY.findall(facts)):
            constants.setdefault(source_money(literal), []).append(
                {"source": "current_public_facts", "literal": literal})

    def constant(node):
        if type(node.value) not in (int, float):
            raise InvalidClaimProgram("Only finite numeric constants are available")
        value = Decimal(str(node.value))
        if not value.is_finite() or (value not in (0, 1, 2) and value not in constants):
            raise InvalidClaimProgram("Numeric constant absent from permitted public source")
        if value in constants:
            used.append({"value": str(value), "public_source_matches": constants[value]})
        return value

    # Check both branches, not merely the branch selected on the current case.
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            constant(node)

    def evaluate(node):
        if isinstance(node, ast.Name):
            if node.id == "N":
                return debtor_count(facts)
            if node.id == "V":
                return asset_value
            raise InvalidClaimProgram("Only V and N are available variables")
        if isinstance(node, ast.Constant):
            return Decimal(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if right == 0:
                raise InvalidClaimProgram("Division by zero")
            return left / right
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("min", "max"):
            if node.keywords or not 1 <= len(node.args) <= 8:
                raise InvalidClaimProgram("Only bounded positional min/max calls are available")
            values = [evaluate(n) for n in node.args]
            return (min if node.func.id == "min" else max)(values)
        if isinstance(node, ast.IfExp):
            test = node.test
            if (not isinstance(test, ast.Compare) or len(test.ops) != 1
                    or not isinstance(test.ops[0], ast.Eq) or len(test.comparators) != 1
                    or not isinstance(test.left, ast.Name) or test.left.id != "N"
                    or not isinstance(test.comparators[0], ast.Constant)
                    or type(test.comparators[0].value) is not int
                    or test.comparators[0].value not in (1, 2)):
                raise InvalidClaimProgram("Only the public N==1/2 conditional is supported")
            branch = node.body if debtor_count(facts) == test.comparators[0].value else node.orelse
            return evaluate(branch)
        raise InvalidClaimProgram("Unsupported arithmetic syntax or unsourced numeric constant")

    value = evaluate(tree.body)
    if not value.is_finite() or value < 0:
        raise InvalidClaimProgram("A finite nonnegative ceiling is required")
    return value, used


def operator_schema():
    return {"type": "object", "additionalProperties": False,
            "required": ["id", "citation", "limit_expression"], "properties": {
                "id": {"type": "string", "minLength": 1},
                "citation": {"type": "string", "minLength": 1},
                "limit_expression": {"type": "string", "minLength": 1}}}


def operator_catalog(bank):
    result = {}
    for skill in bank:
        if not skill["id"].isascii():
            raise InvalidClaimProgram("Native wire skill identities must be ASCII")
        for operator in skill["guidance"]["operators"]:
            key = skill["id"] + "/" + operator["id"]
            if key in result or not key.isascii():
                raise InvalidClaimProgram("Operator identities must be distinct ASCII names")
            result[key] = {**operator, "skill_id": skill["id"]}
    return result


def answer_schema(statutes, bank):
    operators = list(operator_catalog(bank))
    reference = {"type": "null"} if not operators else {
        "anyOf": [{"type": "string", "enum": operators}, {"type": "null"}]}
    claim = {"type": "object", "additionalProperties": False,
             "required": ["law_id", "operator_id", "limit_expression"], "properties": {
                 "law_id": {"type": "string", "enum": list(source_registry(statutes)["laws"])},
                 "operator_id": reference, "limit_expression": {"type": ["string", "null"]}}}
    asset = {"type": "object", "additionalProperties": False,
             "required": ["asset_name", "asset_value", "claims"], "properties": {
                 "asset_name": {"type": "string"}, "asset_value": {"type": "number", "minimum": 0},
                 "claims": {"type": "array", "items": claim}}}
    used = {"type": "array", "items": {"type": "string"}}
    if bank:
        used["items"]["enum"] = [s["id"] for s in bank]
    else:
        used["maxItems"] = 0
    return {"type": "object", "additionalProperties": False,
            "required": ["public_checks", "assets", "applied_skill_ids"], "properties": {
                "public_checks": {"type": "string"},
                "assets": {"type": "array", "items": asset}, "applied_skill_ids": used}}


def execute_claims(assets, facts, statutes, bank):
    operators, registry = operator_catalog(bank), source_registry(statutes)
    answer, receipts, used, seen = {}, [], [], set()
    fact_values = {source_money(literal) for literal in MONEY.findall(facts)}
    source_text = " ".join(facts.casefold().split())
    for asset in assets:
        name = asset["asset_name"]
        if not name or name.casefold() in seen:
            raise InvalidClaimProgram("Empty or repeated asset name")
        seen.add(name.casefold())
        if " ".join(name.casefold().split()) not in source_text:
            raise InvalidClaimProgram("Asset name absent from current public facts")
        value = Decimal(str(asset["asset_value"]))
        if not value.is_finite() or value < 0 or value not in fact_values:
            raise InvalidClaimProgram("Asset value absent from current public facts")
        claims = []
        for claim in asset["claims"]:
            lid, ref, expression = claim["law_id"], claim["operator_id"], claim["limit_expression"]
            if lid not in registry["laws"]:
                raise InvalidClaimProgram("Unknown public law reference")
            citation = registry["laws"][lid]["citation"]
            if (ref is None) == (expression is None):
                raise InvalidClaimProgram("Select exactly one inline expression or learned operator")
            if ref is not None:
                if ref not in operators or operators[ref]["citation"] != citation:
                    raise InvalidClaimProgram("Learned operation must address the selected law")
                expression = operators[ref]["limit_expression"]
                used.append(ref)
            limit, trace = execute_limit(expression, facts, statutes,
                                         asset_value=value, reusable=ref is not None)
            amount = value if limit is None else min(value, limit)
            claims.append({"citation": citation, "claim_value": float(amount)})
            receipts.append({"asset_name": name, "asset_value": str(value),
                "citation": citation, "operator_id": ref, "limit_expression": expression,
                "source_constants": trace, "limit": None if limit is None else str(limit),
                "claim_value": str(amount)})
        if claims:
            answer[name] = claims
    return answer, {"actual_claim_operations": receipts, "actually_executed_operator_ids": used,
        "program_sha256": csha(assets), "source_facts_sha256": csha(facts),
        "public_statutes_sha256": csha(statutes), "no_Gold_solver_model_or_post_answer_repair": True}
