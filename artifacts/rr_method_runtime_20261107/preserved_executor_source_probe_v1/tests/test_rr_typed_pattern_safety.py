"""Interface-field evidence alone cannot verify an executable reusable graph."""
from copy import deepcopy

from legal_skill_guard.rr import typed_learning
from legal_skill_guard.rr.interfaces import Refinement
from legal_skill_guard.rr.source_learning import candidate_views
from test_rr_method_gaps import allowance_case


class RecordedTestOracle:
    def __init__(self, views=()):
        self.views = list(views)

    def cached_views(self):
        return deepcopy(self.views)

    def query(self, view):
        return 200


def identified(_):
    return Refinement('identified_on_observed_collisions', [], [('order_observable',)])


def test_empty_executable_H_never_enters_library(monkeypatch):
    source, proposal, grade = allowance_case()
    # Even a positive field-refinement result cannot rescue graphs that fail
    # the original source target. No benchmark model or oracle is invoked.
    monkeypatch.setattr(typed_learning, 'refine', identified)
    grade['answer'] = 999
    result = typed_learning.learn_typed_source(source, grade, RecordedTestOracle(), proposal=proposal)
    assert result['connector_candidates_retained'] == 0
    assert result['connector_synthesis_status'] == 'NO_VALID_CONNECTOR'
    assert result['learned_pattern'] is None


def test_unbound_recorded_view_cannot_verify_a_retained_graph(monkeypatch):
    source, proposal, grade = allowance_case()
    original = typed_learning.bind_variant
    def base_only(s, variant, bindings):
        if variant['public'] != source['public']:
            raise ValueError('No verified primitive extraction for the edited input')
        return original(s, variant, bindings)
    monkeypatch.setattr(typed_learning, 'bind_variant', base_only)
    monkeypatch.setattr(typed_learning, 'refine', identified)
    views = candidate_views(source, grade)
    result = typed_learning.learn_typed_source(source, grade, RecordedTestOracle(views[:1]), proposal=proposal)
    assert result['connector_candidates_retained'] > 0
    assert result['connector_synthesis_status'] == 'view_rebinding_unavailable'
    assert result['learned_pattern'] is None
