"""Offline acceptance of source responsibility, Ω and joint separation."""
import time
from dataclasses import replace
from itertools import combinations, product

import pytest

from legal_skill_guard.rr.coverage import (
    FiniteTheory,
    Residual,
    SourceLedger,
    certificate,
    complete,
    digest,
    evaluate,
    plan_batch,
)


def var(name):
    return {"var": name}


def op(name, *args):
    return {"op": name, "args": list(args)}


def theory(query=None):
    ledger = SourceLedger.from_text("General rule\nInternational exception\nGift deduction")
    ledger.clauses[0] = replace(ledger.clauses[0], state="compiled")
    return FiniteTheory(ledger, {"international": True}, {"exception": (False, True),
                        "gift": (0, 10)}, query if query is not None else
                        op("if", op("and", var("international"), var("exception")), 0, 80),
                        [Residual("s1", ("exception",), "public_structure", False),
                         Residual("s2", ("gift",), "public_structure", False)],
                        containment_assumptions=("accepted translation of general rule",))


def test_full_source_registration_including_unknown_fragments():
    text = "Title\n  \n未知 fragment  § 9\nR1 except R2\n"
    ledger = SourceLedger.from_text(text)
    assert len(ledger.clauses) == 3
    ledger.clauses.pop(1)
    with pytest.raises(ValueError, match="Unregistered"):
        ledger.validate()


def test_relevant_untranslated_exception_blocks_stability():
    result = complete(theory())
    assert result.status == "translation_unresolved"
    assert {w.answer for w in result.worlds} == {0, 80}


def test_verified_irrelevant_residuals_allow_stop():
    t = theory()
    t.facts["international"] = False
    r = complete(t)
    assert r.status == "completion_stable" and r.answer == 80
    proof = certificate(t, r)
    assert proof["completion_count"] == 4
    assert proof["natural_language_faithfulness_proven"] is False


def test_llm_scope_guess_cannot_discard_unknown_effects():
    t = theory(80)
    t.residuals[0] = Residual("s1", ("exception",))
    assert complete(t).status == "translation_unresolved"
    with pytest.raises(ValueError, match="TOP"):
        t.narrow("exception", (False,), evidence="unverified_llm")


@pytest.mark.parametrize("mode,expected", [("empty", "conflict"), ("outside", "unsupported_no_certificate"),
                                          ("timeout", "budget_exhausted"), ("conflict", "conflict")])
def test_noncertifiable_states_are_distinct(mode, expected):
    t = theory()
    kwargs = {}
    if mode == "empty":
        t.constraints = [False]
    if mode == "outside":
        t.residuals[0] = replace(t.residuals[0], supported=False)
    if mode == "timeout":
        kwargs["deadline"] = time.monotonic() - 1
    if mode == "conflict":
        t.query = "__CONFLICT__"
    r = complete(t, **kwargs)
    assert r.status == expected
    with pytest.raises(ValueError):
        certificate(t, r)


def test_prefix_with_one_observed_answer_is_never_certified():
    t = theory()
    r = complete(t, max_worlds=1)
    assert len(r.worlds) == 1 and r.status == "budget_exhausted"


def test_task_unknown_is_a_stable_answer_not_a_solver_failure():
    r = complete(theory("Unknown"))
    assert r.answer == "Unknown" and r.status == "completion_stable"


def test_revocation_invalidates_old_certificate():
    t = theory()
    t.narrow("exception", (True,), evidence="accepted_translation")
    r = complete(t)
    assert certificate(t, r)["answer"] == 0
    t.revoke("exception", (False, True), reason="cross-reference disproves the accepted contract")
    assert complete(t).status == "translation_unresolved"
    with pytest.raises(ValueError, match="current"):
        certificate(t, r)
    assert t.events[-1]["event"] == "revoke_contract_and_dependent_certificates"


def test_xor_requires_joint_batch_and_shared_context_is_counted_once():
    t = theory(op("xor", var("exception"), var("gift")))
    t.domains["gift"] = (False, True)
    t.ledger.clauses[1] = replace(t.ledger.clauses[1], context=("s0",))
    t.ledger.clauses[2] = replace(t.ledger.clauses[2], context=("s0",))
    def cost(closure):
        return 10 + len(closure)
    result = plan_batch(t, cost, 13)
    assert result.status == "separation_complete"
    assert result.selected == ("s1", "s2") and result.context == ("s0", "s1", "s2")
    assert result.cost == 13
    assert plan_batch(t, cost, 12).status == "batch_budget_insufficient"
    assert plan_batch(t, cost, 12).lower_bound == 13


def test_h_agreement_does_not_shrink_omega():
    finite_candidate_answers = [80, 80]
    assert len(set(finite_candidate_answers)) == 1
    assert complete(theory()).status == "translation_unresolved"


@pytest.mark.parametrize("truth_table", list(product((False, True), repeat=4)))
def test_batch_against_independent_exhaustive_oracle(truth_table):
    # All 16 binary Boolean functions: independent truth-table dependency check.
    t = theory(op("if", var("exception"),
                  op("if", var("gift"), truth_table[3], truth_table[2]),
                  op("if", var("gift"), truth_table[1], truth_table[0])))
    t.domains["gift"] = (False, True)
    def cost(s):
        return 10 + sum({"s1": 2, "s2": 3}.get(k, 0) for k in s)
    options = []
    worlds = list(product((False, True), repeat=2))
    for n in range(3):
        for chosen in combinations((0, 1), n):
            if all(truth_table[i] == truth_table[j] or
                   any(worlds[i][k] != worlds[j][k] for k in chosen)
                   for i in range(4) for j in range(4)):
                subset = {("s1", "s2")[k] for k in chosen}
                options.append(cost(subset) if subset else 0)
    r = plan_batch(t, cost, 100)
    if len(set(truth_table)) == 1:
        assert r.status == "completion_stable"
    else:
        assert r.status == "separation_complete" and r.cost == min(options)


def test_limits_and_invalid_ir_do_not_turn_into_proofs():
    t = theory(op("mul", var("gift"), var("gift")))
    assert complete(t).status == "unsupported_no_certificate"
    assert plan_batch(theory(), lambda x: len(x), 100, max_calls=0).status == "budget_exhausted"
    assert plan_batch(theory(), lambda x: len(x), 100, seconds=0).status == "budget_exhausted"
    with pytest.raises(ValueError):
        evaluate(op("and", 1, True), {})
    assert digest(False) != digest(0)


def test_missing_source_obligation_is_a_hard_error():
    t = theory()
    t.residuals.pop()
    with pytest.raises(ValueError, match="obligation"):
        complete(t)
