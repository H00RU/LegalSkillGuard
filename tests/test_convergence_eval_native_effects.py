import pytest

from experiments.convergence_eval_native_effects import _evidence_effect


def test_evidence_effect_preserves_annotated_unit_mean_when_document_sizes_differ():
    units = [('first', 'a'), ('first', 'b'), ('second', 'a'), ('second', 'b')]
    before = [{'source': source, 'view': view, 'native_metrics': {}} for source, view in units]
    after = [{**row, 'native_metrics': {'evidence_f1': float(index == 0)}} for index, row in enumerate(before)]
    eligible = {units[0], units[2], units[3]}
    summary = [{'evidence_f1': {'native_units': 3, 'mean': mean}} for mean in (0.0, 1 / 3)]

    result = _evidence_effect(before, after, summary, eligible)

    assert result['before'] == 0.0
    assert result['after'] == pytest.approx(1 / 3)
    assert result['mean_change'] == pytest.approx(1 / 3)
    assert result['mothers'] == 2
    assert result['native_units'] == 3
    assert result['paired_source_bootstrap_95'] == [0.0, 1.0]
    with pytest.raises(ValueError, match='original annotation scope'):
        _evidence_effect(before, after, summary, {units[0], units[2], ('unrelated', 'a')})


def test_no_eligible_evidence_units_leave_the_metric_undefined():
    scores = [{'source': 'first', 'view': 'a', 'native_metrics': {}}]
    summary = [{'evidence_f1': {'native_units': 0, 'mean': None}}] * 2
    result = _evidence_effect(scores, scores, summary, set())

    assert result['native_units'] == 0
    assert result['mean_change'] is None
    assert result['paired_source_bootstrap_95'] is None
