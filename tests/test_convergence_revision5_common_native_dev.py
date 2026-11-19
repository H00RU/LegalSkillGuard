import pytest

from experiments.convergence_revision5_common_native_dev import apply_compiled, compare


def test_common_rule_uses_the_original_prediction_and_copies_its_bound_output():
    source = {'dataset': 'ContractNLI', 'views': [
        {'id': view, 'answer_schema': {'enum': ['Entailment', 'NotMentioned']},
         'public': {'sentence_spans': [[0, 5], [6, 12]]}}
        for view in ('bound', 'uncovered')
    ]}
    native = {'bound': {'answer': 'Entailment', 'evidence_sentence_ids': [0]},
              'uncovered': {'answer': 'NotMentioned', 'evidence_sentence_ids': []}}
    result = apply_compiled(source, native, {'bound': lambda out: {'evidence_sentence_ids': out['evidence_sentence_ids'] + [1]}})
    assert result['bound']['original']['evidence_sentence_ids'] == [0]
    assert result['bound']['common']['evidence_sentence_ids'] == [0, 1]
    assert result['uncovered']['original'] == result['uncovered']['common']
    assert native['bound']['evidence_sentence_ids'] == [0]


def test_metrics_preserve_source_pairing_and_balance_classes():
    rows = [{'source': str(i), 'view': 'native', 'grade': 1.0, 'stratum': 'yes' if i else 'no'} for i in range(3)]
    revised = [{**row, 'grade': 0.0 if i == 0 else 1.0} for i, row in enumerate(rows)]
    key = 'balanced'
    assert compare({key: rows}, {key: revised})[key]['after'] == 0.5
    with pytest.raises(AssertionError):
        compare({key: rows}, {key: revised[::-1]})
