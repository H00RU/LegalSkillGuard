from itertools import product

from experiments.convergence_revision5_oe_category_scope import (
    FEDERAL,
    FEDERAL_TEXT,
    OREGON,
    OREGON_TEXT,
    PERSONAL_USE,
    category,
    direct_supported,
    repair,
    signatures,
    view_facts,
)
from experiments.convergence_revision5_oe_wildcard_replay import EV_SCOPE
from legal_skill_guard.paired_interfaces.shared_semantics import matches_assertions


def task(family="EC", title="Ava owns a framed canvas print worth $300.00.", *, policy=OREGON_TEXT):
    return {
        "id": family,
        "public": {
            "original_input": (
                f"{PERSONAL_USE}\n{EV_SCOPE}\nStatutes:\n{OREGON}\n{policy}\n\n"
                f"{FEDERAL}\n{FEDERAL_TEXT}\n\nSolved Reasoning Steps:\n"
                "The Debtor may claim property exemptions under Federal and Oregon statutes.\n\nFacts:\n"
                "Ava Doe (hereinafter the Debtor) filed for bankruptcy on 3.6.2024. "
                f"{title}\n\nOutput contract: the original claim plan"
            )
        },
    }


def test_shared_title_couples_two_applicable_citations():
    allowed = {OREGON: True, FEDERAL: True}
    fields, values = signatures(task(), "root", "shawl", {"title": None, "allowed": allowed})
    assert len(values["shared"]) == 2
    assert len(values["independent_completions"]) == 4
    assert [True, False] in values["independent_completions"]
    assert [True, False] not in values["shared"]
    for observed in product((True, False, None), repeat=2):
        assert any(matches_assertions(list(observed), v) for v in values["shared"]) == direct_supported(
            allowed, None, dict(zip(fields, observed, strict=True))
        )


def test_oregon_exclusion_leaves_indeterminate_federal_art_scope_open():
    source = task("EV")
    assert category("framed canvas print in a green frame") == "art"
    facts = view_facts(source)
    assert facts["framed canvas print"]["allowed"] == {OREGON: False}
    marked = {
        "framed canvas print": [
            {"citation": OREGON, "claim_value": 300},
            {"citation": FEDERAL, "claim_value": 300},
        ]
    }
    assert repair(marked, "EV", facts) == {
        "framed canvas print": [{"citation": FEDERAL, "claim_value": 300}],
    }


def test_apparel_supports_both_citations_with_title_but_no_addition_under_unresolved_title():
    for title, should_bind in (
        ("Ava owns a shawl worth $24.00.", True),
        ("Records show that Ava possesses a shawl with a value of $24.00.", False),
    ):
        facts = view_facts(task("EC", title))
        assert facts["shawl"]["allowed"] == {OREGON: True, FEDERAL: True}
        answer = repair({}, "EC", facts)
        assert set(answer.get("shawl", [])) == ({OREGON, FEDERAL} if should_bind else set())


def test_instrument_supported_federally_and_oregon_claim_is_removed():
    facts = view_facts(task("EV", "Ava owns a flute worth $925.00."))
    prior = {"flute": [{"citation": OREGON, "claim_value": 925}]}
    assert repair(prior, "EV", facts) == {"flute": [{"citation": FEDERAL, "claim_value": 700}]}


def test_development_rule_verifies_the_supplied_citation_text():
    assert view_facts(task("EV", policy="Instruments up to $1,800.")) == {}
