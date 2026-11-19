from experiments.convergence_revision5_oe_oregon_eligibility import (
    CLAUSES, HOUSEHOLD, PICTURES, VEHICLE, bound_clauses, repair, usage_edit,
)
from experiments.convergence_revision5_oe_category_scope import PERSONAL_USE
from experiments.convergence_revision5_oe_wildcard_replay import EV_SCOPE


def view(family, fact, *, jurisdiction="Oregon"):
    statutes = "\n\n".join(c + "\n" + text for c, text in CLAUSES.items())
    return {
        "id": family,
        "public": {"original_input": (
            f"{PERSONAL_USE} {EV_SCOPE}\nStatutes:\n{statutes}"
            f"\nSolved Reasoning Steps:\nThe Debtor may claim property exemptions under {jurisdiction} statutes."
            "\nFacts:\nAva Martin (hereinafter the Debtor) filed for bankruptcy on 1/2/2024.\n"
            f"{fact}\nOutput contract:\n"
        )},
    }


def test_explicit_oregon_instrument_replaces_vehicle_citation_and_binds_cap():
    task = view("EV", "Ava owns a flute worth $925.00.")
    assert bound_clauses(task) == set(CLAUSES)
    assert repair(task, {"flute": [{"citation": VEHICLE, "claim_value": 925}]}) == {
        "flute": [{"citation": PICTURES, "claim_value": 600}]
    }


def test_possession_supports_vehicle_exclusion_without_inventing_title():
    task = view("EC", "Records show that Ava possesses a flute with a value of $20.00.")
    assert repair(task, {"flute": [VEHICLE]}) == {"flute": []}


def test_unbound_law_and_unresolved_household_category_leave_existing_claims():
    fact = "Ava owns a framed canvas print worth $750.00."
    answer = {"framed canvas print": [HOUSEHOLD]}
    assert repair(view("EC", fact), answer) == answer
    assert repair(view("EC", fact, jurisdiction="Pennsylvania"), answer) == answer


def test_usage_edit_preserves_membership_uncertainty_and_binds_zero_on_resale():
    asset = "framed canvas print"
    fact = f"Ava owns a {asset} worth $750.00."
    witness = usage_edit("paired", {f: view(f, fact) for f in ("EC", "EV")}, asset)
    assert witness["counts"] == {"shared": 2, "independent_completions": 4}
    assert witness["shared_signatures"] == [[False, 0, False, 0], [True, 750.0, False, 0]]
    assert witness["direct_matches_shared_on_all_states"] == 81
