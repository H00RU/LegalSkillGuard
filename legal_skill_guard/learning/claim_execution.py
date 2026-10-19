"""Source-grounded claim operations for a frozen legal task executor.

The model emits a program, not an answer later clipped or repaired. Both empty
and learned-library conditions have the same arithmetic instruction set. A
learned operator is a reusable source-bound limit program; an empty-library
model may write the identical program inline. No Gold, expert asset categories,
benchmark solver, model call, filesystem or Python execution is available here.
"""

from __future__ import annotations

import re
from decimal import Decimal

from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

MONEY = re.compile(r"\$(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?(?![\d,])")
OPCODES = ("LAW", "CONST", "DEBTORS", "ADD", "SUB", "MUL", "DIV", "MIN", "MAX", "IF_TWO")


class InvalidClaimProgram(ValueError):
    """An invalid model action is a failed attempt, never an alternative answer."""


def instruction_schema():
    return {"type": "object", "additionalProperties": False,
            "required": ["op", "citation", "literal", "number"], "properties": {
                "op": {"type": "string", "enum": list(OPCODES)},
                "citation": {"type": ["string", "null"]},
                "literal": {"type": ["string", "null"]},
                "number": {"anyOf": [{"type": "integer", "enum": [0, 1, 2]},
                                       {"type": "null"}]}}}


def operator_schema():
    return {"type": "object", "additionalProperties": False,
            "required": ["id", "citation", "limit_program"], "properties": {
                "id": {"type": "string", "minLength": 1},
                "citation": {"type": "string", "minLength": 1},
                "limit_program": {"type": "array", "maxItems": 32,
                                  "items": instruction_schema()}}}


def answer_schema(statutes, bank):
    """Same inline arithmetic expressivity with or without learned operators."""
    operators = list(operator_catalog(bank))
    reference = {"type": "null"} if not operators else {
        "anyOf": [{"type": "string", "enum": operators}, {"type": "null"}]}
    claim = {"type": "object", "additionalProperties": False,
             "required": ["citation", "operator_id", "limit_program"], "properties": {
                 "citation": {"type": "string", "enum": list(law_blocks(statutes))},
                 "operator_id": reference,
                 "limit_program": {"anyOf": [
                     {"type": "array", "maxItems": 32, "items": instruction_schema()},
                     {"type": "null"}]}}}
    asset = {"type": "object", "additionalProperties": False,
             "required": ["asset_name", "value_quote", "claims"], "properties": {
                 "asset_name": {"type": "string"}, "value_quote": {"type": "string"},
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


def law_blocks(statutes):
    """Split original displayed statute headers mechanically, not by legal merit."""
    result = {}
    for paragraph in statutes.split("\n\n"):
        lines = paragraph.splitlines()
        headers = [i for i, line in enumerate(lines) if "§" in line and len(line) < 120]
        if not headers:
            continue
        i = headers[0]
        header = lines[i].strip()
        body = "\n".join(lines[i + 1:])
        if header in result:
            raise InvalidClaimProgram("Duplicate public statute header")
        result[header] = body
    return result


def source_money(literal):
    if not isinstance(literal, str) or MONEY.fullmatch(literal) is None:
        raise InvalidClaimProgram("Money must be one exact currency lexeme")
    return Decimal(literal[1:].replace(",", ""))


def debtor_count(facts):
    match = re.search(r"\(hereinafter the (Debtors|Debtor)\)", facts)
    if match is None:
        raise InvalidClaimProgram("Declared public debtor-count marker is absent")
    return Decimal(2 if match.group(1) == "Debtors" else 1)


def validate_program(program):
    if not isinstance(program, list) or len(program) > 32:
        raise InvalidClaimProgram("A limit program must be an instruction array")
    depth = 0
    for step in program:
        if not isinstance(step, dict) or set(step) != {"op", "citation", "literal", "number"}:
            raise InvalidClaimProgram("Exact instruction fields required")
        op = step["op"]
        if op not in OPCODES:
            raise InvalidClaimProgram("Unknown arithmetic instruction")
        if op == "LAW":
            if (not isinstance(step["citation"], str) or not step["citation"]
                    or step["number"] is not None):
                raise InvalidClaimProgram("LAW requires a citation and exact money lexeme only")
            source_money(step["literal"])
        elif op == "CONST":
            if (type(step["number"]) is not int or step["number"] not in (0, 1, 2)
                    or step["citation"] is not None or step["literal"] is not None):
                raise InvalidClaimProgram("Only generic constants0/1/2 are available")
        elif any(step[k] is not None for k in ("citation", "literal", "number")):
            raise InvalidClaimProgram("This instruction takes no literal payload")
        if op in ("LAW", "CONST", "DEBTORS"):
            depth += 1
        else:
            if depth < 2:
                raise InvalidClaimProgram("Arithmetic stack underflow")
            depth -= 1
    if program and depth != 1:
        raise InvalidClaimProgram("Exactly one final limit is required")
    # An explicitly empty program denotes no dollar ceiling, not a failure path.


def execute_limit(program, facts, statutes):
    validate_program(program)
    if not program:
        return None, []
    catalog = law_blocks(statutes)
    stack, trace = [], []
    for step in program:
        op = step["op"]
        if op == "LAW":
            if (step["citation"] not in catalog
                    or step["literal"] not in MONEY.findall(catalog[step["citation"]])):
                raise InvalidClaimProgram("A law amount must occur in that ORIGINAL public clause")
            value = source_money(step["literal"])
        elif op == "CONST":
            value = Decimal(step["number"])
        elif op == "DEBTORS":
            value = debtor_count(facts)
        else:
            left, right = stack[-2:]
            del stack[-2:]
            if op == "ADD":
                value = left + right
            elif op == "SUB":
                value = left - right
            elif op == "MUL":
                value = left * right
            elif op == "DIV":
                if right == 0:
                    raise InvalidClaimProgram("Division by zero")
                value = left / right
            elif op == "MIN":
                value = min(left, right)
            elif op == "MAX":
                value = max(left, right)
            else:  # IF_TWO: stack order is single-debtor, two-debtor ceiling.
                value = right if debtor_count(facts) == 2 else left
        if not value.is_finite():
            raise InvalidClaimProgram("Nonfinite arithmetic result")
        stack.append(value)
        trace.append({"instruction": step, "result": str(value)})
    if stack[0] < 0:
        raise InvalidClaimProgram("A monetary ceiling cannot be negative")
    return stack[0], trace


def operator_catalog(bank):
    result = {}
    for skill in bank:
        for operator in skill["guidance"]["operators"]:
            key = skill["id"] + "/" + operator["id"]
            if key in result:
                raise InvalidClaimProgram("Duplicate executable operator identity")
            validate_program(operator["limit_program"])
            result[key] = {**operator, "skill_id": skill["id"]}
    return result


def execute_claims(assets, facts, statutes, bank):
    """Execute the explicit action plan; there is no provisional answer to repair."""
    operators, catalog = operator_catalog(bank), law_blocks(statutes)
    answer, receipts, used = {}, [], []
    seen = set()
    for asset in assets:
        name, quote = asset["asset_name"], asset["value_quote"]
        if not name or name.casefold() in seen:
            raise InvalidClaimProgram("Empty or repeated asset name")
        seen.add(name.casefold())
        if not quote or quote not in facts or name.casefold() not in quote.casefold():
            raise InvalidClaimProgram("Asset and value must share an exact original fact quotation")
        values = MONEY.findall(quote)
        if len(values) != 1:
            raise InvalidClaimProgram("Quote must isolate exactly one factual monetary value")
        value = source_money(values[0])
        claims = []
        for claim in asset["claims"]:
            citation, ref, program = claim["citation"], claim["operator_id"], claim["limit_program"]
            if citation not in catalog:
                raise InvalidClaimProgram("A claimed citation must be an original public statute header")
            if (ref is None) == (program is None):
                raise InvalidClaimProgram("Select exactly one inline or learned operator action")
            if ref is not None:
                if ref not in operators or operators[ref]["citation"] != citation:
                    raise InvalidClaimProgram("The learned operator must address this exact citation")
                program = operators[ref]["limit_program"]
                used.append(ref)
            limit, trace = execute_limit(program, facts, statutes)
            amount = value if limit is None else min(value, limit)
            claims.append({"citation": citation, "claim_value": float(amount)})
            receipts.append({"asset_name": name, "value_quote": quote,
                "asset_value": str(value), "citation": citation, "operator_id": ref,
                "limit_program": program, "arithmetic_trace": trace,
                "limit": None if limit is None else str(limit), "claim_value": str(amount)})
        if claims:
            answer[name] = claims
    return answer, {"actual_claim_operations": receipts, "actually_executed_operator_ids": used,
                    "program_sha256": csha(assets), "source_facts_sha256": csha(facts),
                    "public_statutes_sha256": csha(statutes),
                    "no_Gold_solver_model_or_post_answer_repair": True}
