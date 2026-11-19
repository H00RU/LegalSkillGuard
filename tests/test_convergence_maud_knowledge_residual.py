from experiments.convergence_revision5_maud_knowledge_residual import (
    ACTUAL,
    EFFECT,
    TARGET,
    definitions,
    facts,
    independent_direct,
    parent_anchor,
    specialized,
)


def test_join_aliases_and_keep_initials_inside_the_definition():
    text = (
        "“to the Company’s knowledge” or “to the knowledge of the Company” means "
        "the actual knowledge of A. Doe and B. Roe after reasonable due inquiry. "
        "The notice provision follows."
    )
    (anchor,) = definitions(text)
    assert anchor["closed"] and anchor["text"].endswith("after reasonable due inquiry.")
    known = facts(anchor)
    assert known == {ACTUAL: True, TARGET: "target_definition", EFFECT: "required"}
    assert (
        specialized(known)["direct_answer"] == independent_direct(known) == "Constructive knowledge"
    )


def test_parent_completion_preserves_a_distinct_excerpt_scope():
    excerpt = "“Knowledge” means (i) the actual knowledge of those persons in Section 8.10(a), and"
    (visible,) = definitions(excerpt)
    assert not visible["closed"]
    assert facts(visible) == {ACTUAL: True}
    assert specialized(facts(visible))["direct_answer"] is None
    parent = (
        "Section 8.10. "
        + excerpt
        + " (ii) the actual knowledge of the Parent, in each case after reasonable inquiry."
    )
    completed = parent_anchor(visible, parent)
    assert completed is not None
    assert specialized(facts(completed))["direct_answer"] == "Constructive knowledge"
    assert parent_anchor(visible, parent + " " + parent) is None


def test_omission_cannot_establish_absence_and_requires_ordered_parent_alignment():
    prefix = "“Knowledge” means the actual knowledge of the Company, "
    suffix = "of the officers identified on Schedule 1.1."
    (visible,) = definitions(prefix + "<omitted> " + suffix)
    assert facts(visible) == {ACTUAL: True}
    assert parent_anchor(visible, prefix + "and the actual knowledge " + suffix) is not None
    assert parent_anchor(visible, prefix + "limited to named employees.") is None


def test_restricted_domain_has_an_exact_smaller_read_or_a_constant_answer():
    partial = specialized({ACTUAL: True})
    assert partial == {
        "states": 16,
        "direct_answer": None,
        "fully_determined": False,
        "fixed_fields": 2,
        "synthesized_fields": 1,
    }
    (complete,) = definitions("“Knowledge” means actual knowledge of the parties.")
    known = facts(complete)
    assert known == {ACTUAL: True, EFFECT: "absent", TARGET: "absent"}
    assert specialized(known)["fixed_fields"] == specialized(known)["synthesized_fields"] == 0
    assert specialized(known)["direct_answer"] == independent_direct(known) == "Actual knowledge"


def test_unrelated_or_disclaimed_inquiry_does_not_prove_an_operative_condition():
    (disclaimed,) = definitions(
        "“Knowledge” means actual knowledge, without any duty to determine the facts after reasonable inquiry."
    )
    assert facts(disclaimed) == {ACTUAL: True}
    (separate,) = definitions(
        "“Knowledge” means actual knowledge of the Chief Executive Officer. "
        "“Reasonable efforts” means a step taken after reasonable inquiry."
    )
    assert facts(separate)[EFFECT] == "absent"
