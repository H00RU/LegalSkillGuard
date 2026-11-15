"""Actual owner-scope failure and preservation of unrelated learned functions."""
import ast
from copy import deepcopy

from experiments import legal_skill_evolution_C_owner_scope_repair as study
from legal_skill_guard.skill_evolution.span_compiler import execute_json


def test_exact_TRAIN_scope_review_passes_without_changing_the_correct_neural_read():
    p = study.current.read(study.OUT / 'result.json')
    assert p['hard_source_failures'] == []
    assert p['new_model_calls'] == 0
    before = study.current.read(study.alignment.OUT / 'C/aligned_candidate.json')
    after = study.current.read(study.OUT / 'candidate.json')
    restored = deepcopy(after)
    restored['source_concept_program'] = before['source_concept_program']
    assert restored == before
    old = {f.name: ast.dump(f) for f in ast.parse(before['source_concept_program']).body}
    new = {f.name: ast.dump(f) for f in ast.parse(after['source_concept_program']).body}
    assert old.keys() == new.keys()
    assert all(old[k] == new[k] for k in old if k != 'legal_roles')


def test_own_and_affiliate_mentions_remain_separate_when_the_same_word_repeats():
    result = study.current.read(study.OUT / 'owner_scope_regressions.json')
    assert len(result['rows']) == 3
    both = next(r for r in result['rows'] if r['case'] == 'both')['actual']['roles'][0]
    assert both == ['participant_union', ['employees_of', ['receiving_party']],
                    ['employees_of', ['controlled_entities_of', ['receiving_party']]]]
