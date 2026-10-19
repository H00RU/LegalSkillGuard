"""Public-source claim execution with original citations and small expressions.

Both arms may write the same inline expression; a learned operator merely
reuses it. No Gold, expert categories, solver, I/O, arbitrary Python execution
or post-answer repair is available. This is an arithmetic executor, NOT a
legal-semantic or English-number validator. The model supplies asset names/values and chooses eligibility;
it does not have to learn an exact-quotation or hashed-money-reference task.
"""
from __future__ import annotations

import ast
import re
from decimal import Decimal

from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

LAW_HEADER = re.compile(
    r"^(?:[\dA-Za-z. ]+ § [\dA-Za-z.-]+(?:\([A-Za-z0-9]+\))*"
    r"|[0-9]+ [A-Za-z. ]+ Stat\. [0-9]+/[\d-]+(?:\([A-Za-z0-9]+\))*)$")


class InvalidClaimProgram(ValueError):
    """Invalid actions are failed attempts, not fallback answers."""


def law_blocks(statutes):
    result, current = {}, None
    for raw in statutes.splitlines():
        line = raw.strip()
        if len(line) < 120 and LAW_HEADER.fullmatch(line):
            current = line
            # One public citation can repeat with additional text, and adjacent
            # citations need not have a blank line between them.
            result.setdefault(current, [])
        elif current is not None:
            result[current].append(raw)
    return {citation: "\n".join(lines) for citation, lines in result.items()}


def debtor_count(facts):
    match = re.search(r"\(hereinafter the (Debtors|Debtor)\)", facts)
    if match is None:
        raise InvalidClaimProgram("Public debtor-count marker absent")
    return Decimal(2 if match.group(1) == "Debtors" else 1)


def execute_limit(expression, facts, *, asset_value=Decimal(0)):
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
    used = []

    def constant(node):
        if type(node.value) not in (int, float):
            raise InvalidClaimProgram("Only finite numeric constants are available")
        value = Decimal(str(node.value))
        if not value.is_finite():
            raise InvalidClaimProgram("Only finite numeric constants are available")
        used.append({"value": str(value)})
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
        raise InvalidClaimProgram("Unsupported arithmetic syntax")

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
    result, identities = {}, set()
    for skill in bank:
        if not skill["id"].isascii():
            raise InvalidClaimProgram("Native wire skill identities must be ASCII")
        for operator in skill["guidance"]["operators"]:
            key = skill["id"] + "/" + operator["id"]
            if key in identities or not key.isascii():
                raise InvalidClaimProgram("Operator identities must be distinct ASCII names")
            identities.add(key)
            citation = operator["citation"]
            if citation in result:
                raise InvalidClaimProgram("Only one active routine per citation; merge variants or use inline arithmetic")
            result[citation] = {**operator, "skill_id": skill["id"], "qualified_id": key}
    return result


def answer_schema(bank):
    operators = operator_catalog(bank)
    claim = {"type": "object", "additionalProperties": False,
             "required": ["citation", "limit_expression"], "properties": {
                 "citation": {"type": "string"},
                 "limit_expression": {"type": ["string", "null"] if operators else "string"}}}
    asset = {"type": "object", "additionalProperties": False,
             "required": ["asset_name", "asset_value", "claims"], "properties": {
                 "asset_name": {"type": "string"}, "asset_value": {"type": "number", "minimum": 0},
                 "claims": {"type": "array", "items": claim}}}
    return {"type": "object", "additionalProperties": False,
            "required": ["assets"], "properties": {
                "assets": {"type": "array", "items": asset}}}


def execute_claims(assets, facts, statutes, bank):
    operators = operator_catalog(bank)
    answer, receipts, used, seen = {}, [], [], set()
    for asset in assets:
        name = asset["asset_name"]
        if not name or name.casefold() in seen:
            raise InvalidClaimProgram("Empty or repeated asset name")
        seen.add(name.casefold())
        value = Decimal(str(asset["asset_value"]))
        if not value.is_finite() or value < 0:
            raise InvalidClaimProgram("Asset value must be finite and nonnegative")
        claims = []
        for claim in asset["claims"]:
            citation, expression = claim["citation"], claim["limit_expression"]
            ref = None
            if expression is None:
                if citation not in operators:
                    raise InvalidClaimProgram("No published routine for the explicitly requested citation")
                ref = operators[citation]["qualified_id"]
                expression = operators[citation]["limit_expression"]
                used.append(ref)
            limit, trace = execute_limit(expression, facts, asset_value=value)
            amount = value if limit is None else min(value, limit)
            claims.append({"citation": citation, "claim_value": float(amount)})
            receipts.append({"asset_name": name, "asset_value": str(value),
                "citation": citation, "operator_id": ref, "limit_expression": expression,
                "numeric_literals": trace, "limit": None if limit is None else str(limit),
                "claim_value": str(amount)})
        if claims:
            answer[name] = claims
    return answer, {"actual_claim_operations": receipts, "actually_executed_operator_ids": used,
        "program_sha256": csha(assets), "source_facts_sha256": csha(facts),
        "public_statutes_sha256": csha(statutes), "no_Gold_solver_model_or_post_answer_repair": True,
        "runtime_does_not_judge_legal_truth_or_rewrite_names_values_citations": True}
