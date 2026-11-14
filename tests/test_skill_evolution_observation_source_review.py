from legal_skill_guard.skill_evolution.observation_source_review import review


def grounded(facts):
    return {'bindings': [{'inputs': {'facts': facts, 'negative_givens': []}}]}


def test_stated_payment_is_not_rejected_as_unstated_labor_or_kinship():
    # Real1ff7 source: "Alice was paid$33200". Its payer/day are unstated;
    # that does not license a blanket ban on observing the payment itself.
    row = grounded([{'predicate': 'payment_', 'arguments': ['source_payment']}])
    assert review('SARA_v2_Binary:1ff7d9', row)['failures'] == 0
    row = grounded([{'predicate': 'joint_return_', 'arguments': ['invented_joint']}])
    assert review('SARA_v2_Binary:1ff7d9', row)['failures'] == 1


def test_actual_native_correct_target_given_is_rejected_by_source_not_answer():
    row = grounded([{'predicate': 's151_b', 'arguments': ['Alice', 2017, 0]}])
    value = review('SARA_v2_Binary:1ff7d9', row)
    assert value['failures'] == 1 and value['native_answer_used'] is False
    assert review('some_other_original_TRAIN', row)['reviewed'] is False
