"""Independent counterexamples for witness, grouping, resource and interface loss."""
from dataclasses import replace

import pytest

from legal_skill_guard.rr.interfaces import (
    AllowanceBank,
    Amount,
    Connector,
    ConnectorPool,
    InterfaceError,
    Observation,
    OracleViews,
    Relation,
    alpha_structure,
    cap,
    choose_view,
    refine,
    sum_amounts,
)


def amount(value, id, owner="household", period="year"):
    return Amount(value, "dollar", owner, period, frozenset({id}))


def test_same_witness_join_is_not_independent_existence():
    a = Relation(("x",), (("alice",),))
    b = Relation(("x",), (("bob",),))
    assert a.exists() and b.exists()
    assert not a.join(b, ("x",)).exists()
    assert a.join(a, ("x",)).exists()


def test_boolean_projection_cannot_recover_witnesses():
    c = Connector({"op": "project_exists", "inputs": [{"slot": "A"}]})
    with pytest.raises(InterfaceError, match="Boolean"):
        c.execute({"A": True})


def test_cap_per_item_vs_complete_group():
    items = [amount(300, "i1"), amount(300, "i2")]
    assert sum_amounts([cap(a, 400, scope="element") for a in items]).value == 600
    assert cap(sum_amounts(items), 400, scope="closed_group").value == 400
    with pytest.raises(InterfaceError):
        cap(items[0], 400, scope="closed_group")


def test_duplicate_contribution_and_mixed_owner_are_rejected():
    a = amount(10, "i1")
    with pytest.raises(InterfaceError, match="Repeated"):
        sum_amounts([a, a])
    assert sum_amounts([a, a], allow_multiplicity=True).value == 20
    with pytest.raises(InterfaceError, match="owner"):
        sum_amounts([a, amount(10, "i2", owner="other")])


def test_shared_allowance_is_single_state_and_not_reinitializable():
    bank = AllowanceBank()
    key = ("rule", "household", "year")
    bank.create(key, 100, policy="input_order", order_observable=False)
    out = bank.thread(key, [amount(80, "i1"), amount(80, "i2")])
    assert [a.value for a in out] == [0, 60]
    assert bank.states[key].balance == 0
    assert sum(e["used"] for e in bank.events) == 100
    with pytest.raises(InterfaceError, match="copying"):
        bank.create(key, 100, policy="input_order", order_observable=False)
    with pytest.raises(InterfaceError, match="Stale"):
        bank.consume(key, 10, expected_version=0)


def test_conservation_does_not_decide_allocation_order():
    values = []
    for policy in ("input_order", "reverse_order"):
        bank = AllowanceBank()
        key = ("rule", "household", "year")
        bank.create(key, 100, policy=policy, order_observable=True)
        out = bank.thread(key, [amount(80, "i1"), amount(80, "i2")])
        values.append(out[0].value + 2 * out[1].value)
        assert bank.states[key].balance == 0
    assert values == [120, 60]


def test_independent_owner_allowances():
    bank = AllowanceBank()
    for owner in ("household", "other"):
        key = ("rule", owner, "year")
        bank.create(key, 100, policy="input_order", order_observable=False)
        assert bank.thread(key, [amount(80, owner, owner=owner)])[0].value == 0


def test_unknown_allocation_policy_cannot_be_cost_tiebroken():
    with pytest.raises(InterfaceError, match="Unresolved"):
        AllowanceBank().create(("r", "o", "p"), 100, policy="unknown", order_observable=True)


def test_collision_field_refinement_and_alpha_renaming():
    a = Observation([True, True], {"entity_equality": [{"entity": "alice"}, {"entity": "bob"}]}, False, "v1")
    b = Observation([True, True], {"entity_equality": [{"entity": "alice"}, {"entity": "alice"}]}, True, "v2")
    r = refine([a, b])
    assert r.minimal_field_sets == [("entity_equality",)]
    assert r.status == "identified_on_observed_collisions"
    renamed = [replace(a, metadata={"entity_equality": [{"entity": "X"}, {"entity": "Y"}]}),
               replace(b, metadata={"entity_equality": [{"entity": "X"}, {"entity": "X"}]})]
    assert refine(renamed).pattern() == r.pattern()
    assert "alice" not in str(r.pattern()) and "v1" not in str(r.pattern())


def test_ambiguous_field_minima_and_unrecoverable_information():
    a = Observation([80, 80], {"membership": [0, 0], "owner_period_keys": [0, 0]}, 60, "v1")
    b = Observation([80, 80], {"membership": [0, 1], "owner_period_keys": [0, 1]}, 0, "v2")
    assert refine([a, b]).status == "ambiguous_interface"
    assert len(refine([a, b]).minimal_field_sets) == 2
    assert refine([a, replace(a, answer=0, view_hash="v2")]).status == "unrecoverable_interface_information"


@pytest.mark.parametrize("bad", [{"case_id": 12}, {"gold": True}, {"answer_fingerprint": "abc"},
                                {"membership": "source-unique-text"}])
def test_no_id_gold_or_string_routing(bad):
    with pytest.raises(InterfaceError):
        Observation([], bad, True, "v1").normalized()


def test_normalization_preserves_cross_field_identity():
    left = {"membership": [{"entity": "A"}], "owner_period_keys": [{"entity": "A"}]}
    right = {"membership": [{"entity": "X"}], "owner_period_keys": [{"entity": "Y"}]}
    assert alpha_structure(left) != alpha_structure(right)


def join_graph():
    return Connector({"op": "project_exists", "inputs": [{"op": "join_on", "params": {"keys": ["x"]},
                       "inputs": [{"slot": "A"}, {"slot": "B"}]}]})


def test_connector_execution_filter_and_H_is_not_omega():
    c = join_graph()
    view = {"A": Relation(("x",), (("alice",),)), "B": Relation(("x",), (("bob",),))}
    pool = ConnectorPool([c])
    assert c.execute(view) is False
    result = pool.predict(view)
    assert result["answer"] is False and result["is_Omega"] is False
    assert result["certificate_status"] == "translation_unresolved"
    pool.observe(view, True)
    assert pool.predict(view)["status"] == "NO_VALID_CONNECTOR"


def test_candidate_limit_and_parameterized_graph():
    with pytest.raises(InterfaceError, match="32"):
        ConnectorPool([join_graph()] * 33)
    with pytest.raises(InterfaceError, match="parameterized"):
        Connector({"op": "map", "inputs": [{"slot": "items"}],
                   "params": {"primitive": "cap", "limit": 400}}).validate()


def test_one_combined_oracle_budget_including_discarded_and_failed_views():
    charged = []
    def oracle(view):
        if view["i"] == 0:
            raise RuntimeError("failed oracle")
        return False
    budget = OracleViews("train1", "ProofWriter_OWA_depth5", "train",
                         lambda s, v: charged.append((s, v)), oracle)
    with pytest.raises(RuntimeError):
        budget.query({"i": 0})
    for i in range(1, 4):
        budget.query({"i": i})
    with pytest.raises(InterfaceError, match="exhausted"):
        budget.query({"i": 4})
    assert len(charged) == 4
    for dataset, split in [("ContractNLI", "train"), ("ProofWriter_OWA_depth5", "test")]:
        with pytest.raises(InterfaceError):
            OracleViews("x", dataset, split, lambda s, v: None, oracle)


def test_view_selection_uses_disagreement_without_labels():
    first = Connector({"op": "project_exists", "inputs": [{"slot": "A"}]})
    pool = ConnectorPool([first, join_graph()])
    a = Relation(("x",), (("alice",),))
    agree = {"A": a, "B": a}
    disagree = {"A": a, "B": Relation(("x",), (("bob",),))}
    assert choose_view(pool, [agree, disagree]) == disagree
    assert pool.predict(disagree)["status"] == "ambiguous_connector"
