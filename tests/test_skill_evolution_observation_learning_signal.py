import pytest

from legal_skill_guard.skill_evolution.observation_learning_signal import signal, metrics, rank


def row(handled=True,correct=True,failures=0,**extra):
    value={'execution':{'handled':handled,'answer':'Entailment' if handled else None},'reads':[],**extra}
    value['learning_signal']=signal(value,{'correct':correct},{'failures':failures})
    return value


def test_known_source_error_and_public_arithmetic_are_not_learned_success():
    invalid=row(failures=1)
    assert invalid['learning_signal']['raw_native_correct']
    assert not invalid['learning_signal']['native_correct_after_supplied_source_checks']
    public=row(shared_public_calculation={'certificate':True})
    assert public['learning_signal']['native_correct_after_supplied_source_checks']
    assert not public['learning_signal']['learned_path_correct']
    assert not row(handled=False,correct=True)['learning_signal']['raw_native_correct']


def test_equal_success_count_cannot_reward_more_confident_errors():
    unknown=[row(),row(handled=False,correct=False)]
    wrong=[row(),row(handled=True,correct=False)]
    assert metrics(unknown)['native_correct']==metrics(wrong)['native_correct']
    assert rank(metrics(unknown))<rank(metrics(wrong))


def test_compiled_read_cost_is_not_confused_with_a_cached_neural_read():
    compiled=row(reads=[{'read_backend':'learned_source_program','new_physical_requests':0}])
    cached=row(reads=[{'cache_hit':True}])
    assert rank(metrics([compiled]))<rank(metrics([cached]))


def test_missing_paid_evidence_is_neither_a_prediction_nor_an_optimization_loss():
    missing=row(handled=False,correct=False,error='ValueError: MissingPaidRead: no cache')
    assert missing['learning_signal']['state']=='missing_offline_evidence'
    with pytest.raises(ValueError,match='offline evidence'):
        metrics([missing])
