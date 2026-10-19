"""Small arithmetic and citation-bound invocation checks, no model qualification."""
import json

import pytest

from legal_skill_guard.learning.claim_execution import (
    InvalidClaimProgram,
    answer_schema,
    execute_claims,
    execute_limit,
    law_blocks,
    operator_catalog,
)

FACTS = "A and B (hereinafter the Debtors) own a watch valued at $600.00."
LAW = "Statutes:\nExample Code\nExample § 1\nA ceiling of $2,000 per debtor."


def plan(use_skill=False):
    return [{"asset_name": "watch", "asset_value": 600,
             "claims": [{"citation": "Example § 1",
                         "limit_expression": None if use_skill else "min(V,2000)"}]}]


def test_inline_and_learned_operators_have_identical_capability():
    a, receipt = execute_claims(plan(), FACTS, LAW, [])
    bank = [{"id": "s", "guidance": {"operators": [{"id": "cap", "citation": "Example § 1",
             "limit_expression": "min(V,2000)"}]}}]
    b, learned = execute_claims(plan(True), FACTS, LAW, bank)
    assert a == b == {"watch": [{"citation": "Example § 1", "claim_value": 600.0}]}
    assert learned["actually_executed_operator_ids"] == ["s/cap"]
    assert receipt["actually_executed_operator_ids"] == []
    with pytest.raises(InvalidClaimProgram):
        operator_catalog(bank + [{"id": "other", "guidance": {"operators": [
            {"id": "variant", "citation": "Example § 1", "limit_expression": "1000"}]}}])


def test_runtime_computes_submitted_values_without_legal_source_repair():
    p = plan()
    p[0]["asset_value"] = 700
    assert execute_claims(p, FACTS, LAW, [])[0]["watch"][0]["claim_value"] == 700
    assert execute_limit("700", FACTS)[0] == 700
    with pytest.raises(InvalidClaimProgram):
        execute_limit("M_NOT_IN_SOURCE", FACTS)
    assert execute_limit("min(600,2000)", FACTS)[0] == 600
    # A statute's English spelling must not invalidate a correct numeric action.
    law_words = "Example § 1\nA ceiling of two thousand dollars."
    assert execute_claims(plan(), FACTS, law_words, [])[0]["watch"][0]["claim_value"] == 600


def test_explicit_joint_conditional_and_unlimited_operations():
    assert execute_limit("2000*N", FACTS)[0] == 4000
    assert execute_limit("2000*2 if N==2 else 2000", FACTS)[0] == 4000
    assert execute_limit("unlimited", FACTS) == (None, [])


def test_no_arbitrary_python_or_failure_fallback():
    with pytest.raises(InvalidClaimProgram):
        execute_limit("__import__('os')", FACTS)
    with pytest.raises(InvalidClaimProgram):
        execute_claims(plan(True), FACTS, LAW, [])
    p = plan()
    p[0]["asset_name"] = "format example car"
    assert "format example car" in execute_claims(p, FACTS, LAW, [])[0]


def test_every_wire_enum_is_ascii_not_unicode_citation():
    schema = answer_schema([])

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
    assert "operator_id" not in json.dumps(schema)
    assert schema["properties"]["assets"]["items"]["properties"]["claims"]["items"][
        "properties"]["limit_expression"]["type"] == "string"


def test_compiled_statutes_adjacent_headers_and_repeated_citation_are_retained():
    source = ("735 Ill. Comp. Stat. 5/12-1001(c)\nA vehicle cap of $2,400.\n"
              "735 Ill. Comp. Stat. 5/12-1001(d)\nA tools cap of $1,500.\n\n"
              "735 Ill. Comp. Stat. 5/12-1001(c)\nAdditional public qualification.\n\n"
              "Example § 1\nA ceiling of $2,000 per debtor.")
    blocks = law_blocks(source)
    assert len(blocks) == 3
    assert "$2,400" in blocks["735 Ill. Comp. Stat. 5/12-1001(c)"]
    assert "Additional public qualification" in blocks["735 Ill. Comp. Stat. 5/12-1001(c)"]
    assert "$1,500" in blocks["735 Ill. Comp. Stat. 5/12-1001(d)"]
    assert execute_limit("2400", FACTS)[0] == 2400
