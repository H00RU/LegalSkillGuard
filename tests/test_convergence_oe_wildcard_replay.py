from experiments.convergence_revision5_oe_wildcard_replay import (
    CITATION,
    EV_SCOPE,
    HOMESTEAD,
    JOINT_APPLY,
    JOINT_CLAUSE,
    JOINT_FACTS,
    certificate,
    claimed_at_fresh_state,
    complete_wildcard,
    direct_claim,
    native_bounds,
)


def view(facts, *, jurisdictions="Federal", task="EV", framing=EV_SCOPE, joint_rule=JOINT_CLAUSE):
    return {
        "id": task,
        "public": {
            "original_input": (
                f"{framing}\n{JOINT_FACTS}\nStatutes:\n"
                f"{CITATION}\nThe debtor's aggregate interest in any property, not to exceed in value "
                "$1,475 plus up to $13,950 of any unused amount of the exemption provided under paragraph (1) of this subsection.\n\n"
                f"{HOMESTEAD}\nThe debtor's aggregate interest, not to exceed $27,900 in value, in a residence.\n\n"
                f"{JOINT_APPLY}\n{joint_rule}\n\n"
                "Or. Rev. Stat. § 18.345(1)(p)\nThe debtor's interest in personal property.\n"
                f"Solved Reasoning Steps:\nThe Debtor may claim property exemptions under {jurisdictions} statutes.\n"
                f"Facts:\n{facts}\n\nOutput contract: the claim plan"
            )
        },
    }


def test_independent_fresh_allowance_uses_no_balance_from_other_assets():
    sample = view(
        "Ava Doe (hereinafter the Debtor) filed for bankruptcy on 3.6.2024. "
        "Ava currently owns a carved desk valued at $18,000.00, as well as a guitar worth $400.00."
    )
    proof = native_bounds(sample)
    assert proof is not None
    values = certificate("train", sample, proof)
    assert values == {"carved desk": 1_542_500, "guitar": 40_000}
    assert sum(values.values()) > 1_542_500


def test_active_law_task_scope_and_direct_ownership_are_required():
    filing = "Ava Doe (hereinafter the Debtor) filed for bankruptcy on 3.6.2024. "
    known = filing + "Ava owns a desk worth $300.00."
    possible = filing + "Records show that Ava possesses a desk with a value of $300.00."
    assert native_bounds(view(known, jurisdictions="Oregon")) is None
    assert native_bounds(view(known, framing="Optimize total exemptions.")) is None
    partial = native_bounds(view(possible))
    assert partial is not None and partial["assets"] == {}


def test_joint_case_requires_separate_application_clause():
    facts = (
        "Ava Doe and Ben Doe (hereinafter the Debtors) filed for bankruptcy on 3.6.2024. "
        "The Debtors own a carved desk worth $44,444.00."
    )
    sample = view(facts)
    proof = native_bounds(sample)
    assert proof is not None
    assert certificate("train", sample, proof) == {"carved desk": 3_085_000}
    assert native_bounds(view(facts, joint_rule="This section applies in a joint case.")) is None


def test_direct_and_fresh_credit_agree_at_the_boundaries():
    limits = {"base": 40_000, "fallback": 30_000, "residence": 20_000}
    for value in (0, 39_999, 40_000, 40_001, 59_999, 60_000, 60_001, 200_000):
        assert claimed_at_fresh_state(value, limits) == direct_claim(value, limits)


def test_replay_changes_only_the_wildcard_claim_and_keeps_other_assets():
    before = {
        "desk": [
            {"citation": CITATION, "claim_value": 7},
            {"citation": "state", "claim_value": 10},
        ],
        "tool": [],
    }
    after = complete_wildcard(before, "EV", {"desk": 50_000, "guitar": 4_000})
    assert after == {
        "desk": [
            {"citation": "state", "claim_value": 10},
            {"citation": CITATION, "claim_value": 500},
        ],
        "guitar": [{"citation": CITATION, "claim_value": 40}],
        "tool": [],
    }
    assert before["desk"][0]["claim_value"] == 7
    assert complete_wildcard({}, "EC", {"desk": 50_000}) == {"desk": [CITATION]}
    assert complete_wildcard(None, "EV", {"desk": 50_000}) is None
