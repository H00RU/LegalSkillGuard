import pytest

from experiments.convergence_revision5_oe_assertion_coverage import compare_conflicts, normalized_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory


def joint_view(quote, surname="Santos"):
    return {"id": "EC", "public": {"original_input": (
        f"CASES\nFacts:\nAva and Lee {surname} (hereinafter the Debtors) "
        f"filed for bankruptcy on 1/2/2024.\n{quote}\nOutput contract:\n"
    )}}


@pytest.mark.parametrize("surname", ["Santos", "Marx", "Diaz", "Birch", "Marsh"])
def test_exact_renderer_alias_binds_joint_title(surname):
    view = joint_view(f"The {surname}es own a desk worth $20.00.", surname)
    scoped, edits = normalized_scope(view)
    assert edits == 1 and f"{surname}es" in view["public"]["original_input"]
    count, inventory, _ = title_inventory(scoped["public"]["original_input"])
    assert count == 2
    assert [(row["description"], row["amount_quote"], row["filing_interest_established"])
            for row in inventory.values()] == [("desk", "$20.00", True)]


def test_other_family_name_remains_unresolved():
    view = joint_view("The Mendozes own a desk worth $20.00.")
    assert normalized_scope(view) == (view, 0)
    with pytest.raises(ValueError, match="outside the resolved filing group"):
        title_inventory(view["public"]["original_input"])


@pytest.mark.parametrize("name_was_answered, excluded, expected_rejection", [
    (False, False, False), (True, False, True), (False, True, True)
])
def test_completing_wildcard_does_not_assert_ineligibility_for_other_claims(
    name_was_answered, excluded, expected_rejection
):
    original = {"EC": {"desk": []} if name_was_answered else {}, "EV": {}}
    controlled = {"EC": {"desk": ["wildcard"]}, "EV": {"desk": [{"citation": "category", "claim_value": 20}]}}
    facts = {"desk": {"allowed": {"category": False}}} if excluded else {}
    coarse, explicit, unresolved = compare_conflicts(original, controlled, {"desk": (True, True)}, facts)
    assert coarse == {("desk", "category")}
    assert bool(explicit) == expected_rejection
    assert bool(unresolved) != expected_rejection
