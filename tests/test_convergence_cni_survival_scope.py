from experiments.convergence_revision5_cni_survival_scope import (
    ScopeProof,
    bound_proofs,
    terminal_exception,
)


def test_agreement_termination_is_separate_from_execution_and_employment():
    sources = [
        "The obligations shall survive the execution and delivery of this Agreement.",
        "Confidentiality obligations shall survive termination of each employee's employment.",
        "The obligations shall survive the termination of this Confidentiality Agreement.",
    ]
    assert bound_proofs(sources) == [ScopeProof((2,), "same_agreement_trigger")]


def test_continuation_after_the_event_keeps_different_scope_from_until_and_purported():
    sources = [
        "The duty shall remain effective until the termination of this Agreement.",
        "The duty shall remain effective after the termination of this Agreement.",
        "The Agreement shall remain in force notwithstanding an earlier purported termination.",
        "No duty shall survive the termination of this Agreement.",
    ]
    assert bound_proofs(sources) == [ScopeProof((1,), "same_agreement_trigger")]


def test_such_termination_requires_the_governing_duration_in_the_previous_span():
    condition = "The provisions of clauses 1 and 2 shall survive any such termination."
    assert bound_proofs(["The transaction is discussed here.", condition]) == []
    term = "This Agreement shall become effective from the date hereof and continue in force for a period of one year."
    assert bound_proofs([term, condition]) == [ScopeProof((0, 1), "same_term_reference")]


def test_explicit_exception_has_a_positive_interval_only_with_matching_start_and_section():
    term = (
        "14. Except as otherwise provided in paragraph 8 above, this Agreement and all obligations "
        "of the parties hereunder, notwithstanding anything to the contrary that may be contained herein, "
        "shall terminate one (1) year from the date of this Agreement."
    )
    duty = "8. The recipient agrees that, for a period of eighteen (18) months from the date of this Agreement,"
    clauses = [duty, "(a) acquire securities without written consent.", term]
    assert terminal_exception(clauses) == [
        {
            "evidence": (0, 1, 2),
            "exception_months": 18,
            "agreement_months": 12,
            "replacement": "eighteen (18)",
        }
    ]
    assert bound_proofs(clauses) == [ScopeProof((0, 1, 2), "longer_explicit_exception")]
    assert bound_proofs([duty.replace("eighteen (18)", "twelve (12)"), *clauses[1:]]) == []
    assert (
        terminal_exception(
            [duty.replace("date of this Agreement", "receipt of notice"), *clauses[1:]]
        )
        == []
    )
    assert terminal_exception([duty.replace("8.", "9."), *clauses[1:]]) == []
