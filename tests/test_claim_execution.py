"""Boundary tests for actual public-source calculator operations."""

import pytest

from legal_skill_guard.learning.claim_execution import (
    InvalidClaimProgram,
    execute_claims,
    execute_limit,
    validate_program,
)

FACTS = "A and B (hereinafter the Debtors) own a watch valued at $600.00."
LAW = "Statutes:\nExample Code\nExample § 1\nA ceiling of $2,000 per debtor."


def instruction(op, **kwargs):
    return {"op": op, "citation": None, "literal": None, "number": None, **kwargs}


def plan(ref=None):
    return [{"asset_name": "watch", "value_quote": "watch valued at $600.00",
             "claims": [{"citation": "Example § 1", "operator_id": ref,
                         "limit_program": [instruction("LAW", citation="Example § 1",
                                                        literal="$2,000")] if ref is None else None}]}]


def test_inline_and_learned_operators_have_identical_capability():
    a, receipt = execute_claims(plan(), FACTS, LAW, [])
    bank = [{"id": "s", "guidance": {"operators": [{"id": "cap", "citation": "Example § 1",
             "limit_program": [instruction("LAW", citation="Example § 1", literal="$2,000")]}]}}]
    b, learned = execute_claims(plan("s/cap"), FACTS, LAW, bank)
    assert a == b == {"watch": [{"citation": "Example § 1", "claim_value": 600.0}]}
    assert learned["actually_executed_operator_ids"] == ["s/cap"]
    assert receipt["actually_executed_operator_ids"] == []


def test_no_invented_amount_quote_or_post_generation_repair():
    p = plan()
    p[0]["value_quote"] = "watch valued at $700.00"
    with pytest.raises(InvalidClaimProgram):
        execute_claims(p, FACTS, LAW, [])
    p = plan()
    p[0]["claims"][0]["limit_program"][0]["literal"] = "$200"
    with pytest.raises(InvalidClaimProgram):
        execute_claims(p, FACTS, LAW, [])  # $200 is not the $2,000 source token.


def test_explicit_joint_and_unlimited_operations():
    program = [instruction("LAW", citation="Example § 1", literal="$2,000"),
               instruction("DEBTORS"), instruction("MUL")]
    assert execute_limit(program, FACTS, LAW)[0] == 4000
    assert execute_limit([], FACTS, LAW) == (None, [])


def test_invalid_stack_is_failure_not_fallback():
    with pytest.raises(InvalidClaimProgram):
        validate_program([instruction("ADD")])
    p = plan("not/published")
    with pytest.raises(InvalidClaimProgram):
        execute_claims(p, FACTS, LAW, [])
