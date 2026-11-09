from copy import deepcopy
import pytest
from experiments.rr_v2_legal_feedback_acquisition import (BASE,hypotheses,offline,pool,read,rows,score,select,validate_tests)


def feedback():
    s=read(BASE/'legal_feedback_acquisition_v1_20261110/seal.json')
    # Explicit source-reference software fixture, never presented as model output.
    amounts=[14000,13542,14000,7000]
    return s,[{'payments':deepcopy(p),'expected':v,'source_quote':s['source_excerpt']} for p,v in zip(s['fixed_queries'],amounts)]


def test_correct_feedback_identifies_scope_and_wrong_feedback_is_not_repaired():
    s,t=feedback();good=score(t,s['source_excerpt'],s['fixed_queries'])
    assert good['all_feedback_semantically_correct'] and good['unique_reference_plan']
    t[-1]['expected']=13725;bad=score(t,s['source_excerpt'],s['fixed_queries'])
    assert not bad['all_feedback_semantically_correct'] and not bad['unique_reference_plan']
    assert t[-1]['expected']==13725


def test_selector_is_invariant_to_hypothesis_order():
    h=hypotheses();a=select(pool(),h)
    assert a==select(pool(),list(reversed(h)))
    assert a['indices']==[2,3,4,5]
    assert offline()['canonical_classes_fitting_original_local_amount']==28


def test_changed_fixed_inputs_are_rejected():
    s,t=feedback();t[0]['payments'][0]['amount']=6999
    with pytest.raises(ValueError,match='fixed query'):validate_tests(t,s['source_excerpt'],s['fixed_queries'])


def test_duplicate_physical_ids_and_invented_quotes_rejected():
    s,t=feedback();t[0]['payments'][1]['payment_id']=t[0]['payments'][0]['payment_id']
    with pytest.raises(ValueError,match='unique'):validate_tests(t,s['source_excerpt'])
    s,t=feedback();t[0]['source_quote']='NOT A QUOTE'
    with pytest.raises(ValueError,match='quote'):validate_tests(t,s['source_excerpt'])
