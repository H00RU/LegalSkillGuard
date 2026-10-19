"""Checks the compact source-bound execution language and ASCII wire contract."""
import json

import pytest

from legal_skill_guard.learning.claim_execution import (
    InvalidClaimProgram,
    answer_schema,
    execute_claims,
    execute_limit,
    source_registry,
)

FACTS = "A and B (hereinafter the Debtors) own a watch valued at $600.00."
LAW = "Statutes:\nExample Code\nExample § 1\nA ceiling of $2,000 per debtor."


def refs():
    registry = source_registry(LAW)
    return next(iter(registry["laws"])), next(iter(registry["amounts"]))


def plan(ref=None):
    lid, money = refs()
    return [{"asset_name": "watch", "value_quote": "watch valued at $600.00",
             "claims": [{"law_id": lid, "operator_id": ref,
                         "limit_expression": money if ref is None else None}]}]


def test_inline_and_learned_operators_have_identical_capability():
    a, receipt = execute_claims(plan(), FACTS, LAW, [])
    _, money = refs()
    bank = [{"id": "s", "guidance": {"operators": [{"id": "cap", "citation": "Example § 1",
             "limit_expression": money}]}}]
    b, learned = execute_claims(plan("s/cap"), FACTS, LAW, bank)
    assert a == b == {"watch": [{"citation": "Example § 1", "claim_value": 600.0}]}
    assert learned["actually_executed_operator_ids"] == ["s/cap"]
    assert receipt["actually_executed_operator_ids"] == []


def test_no_invented_quote_or_source_amount():
    p = plan()
    p[0]["value_quote"] = "watch valued at $700.00"
    with pytest.raises(InvalidClaimProgram):
        execute_claims(p, FACTS, LAW, [])
    with pytest.raises(InvalidClaimProgram):
        execute_limit("2000", FACTS, LAW)
    with pytest.raises(InvalidClaimProgram):
        execute_limit("M_NOT_IN_SOURCE", FACTS, LAW)


def test_explicit_joint_conditional_and_unlimited_operations():
    _, money = refs()
    assert execute_limit(money + "*N", FACTS, LAW)[0] == 4000
    assert execute_limit(f"{money}*2 if N==2 else {money}", FACTS, LAW)[0] == 4000
    assert execute_limit("unlimited", FACTS, LAW) == (None, [])


def test_no_arbitrary_python_or_failure_fallback():
    with pytest.raises(InvalidClaimProgram):
        execute_limit("__import__('os')", FACTS, LAW)
    with pytest.raises(InvalidClaimProgram):
        execute_claims(plan("not/published"), FACTS, LAW, [])


def test_every_wire_enum_is_ascii_not_unicode_citation():
    schema = answer_schema(LAW, [])

    def visit(value):
        if isinstance(value, dict):
            for v in value.get("enum", []):
                assert not isinstance(v, str) or v.isascii()
            for v in value.values():
                visit(v)
        elif isinstance(value, list):
            for v in value:
                visit(v)

    visit(schema)
    assert "Example" not in json.dumps(schema)
