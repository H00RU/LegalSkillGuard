"""Regression fixtures are source-grounded software tests, not model evidence."""
import json
from copy import deepcopy
from pathlib import Path

from legal_skill_guard.rr.source_attachment_learning import meaning, problem, fit, choose, project, native_answers

ROOT=Path(__file__).resolve().parents[1]


def reading(kind,head,action,*,obj,negation='none',negquote='',target=None):
    return {'head_kind':kind,'head_quote':head,'action_quote':action,'negation_scope':negation,
            'modal':'none','negation_quote':negquote,'actor_quote':'Recipient','object_quote':obj,
            'exception_target':target,'conditions':['solely for archival purpose'] if kind=='permission' else [],'references':[]}


def source111_fixture():
    seal=json.loads((ROOT/'artifacts/rr_method_redesign_20261109/contract_attachment_update_v1_20261110/training_seal.json').read_text())
    m=deepcopy(next(m for m in seal['documents'] if m['key']=='p111'))
    m['graph']['rules']=[r for r in m['graph']['rules'] if r['id'] in ['rule-5','rule-6']]
    m['graph']['scopes']=[s for s in m['graph']['scopes'] if s['id'] in {r['scope_id'] for r in m['graph']['rules']}]
    canonical="such Discloser’s Confidential Information"
    assert canonical in m['document']
    ret=reading('obligation','Recipient shall','return',obj=canonical)
    good=reading('permission','may retain','retain',obj=canonical,target='rule-5')
    bad={**good,'object_quote':'this Agreement'}
    forest={'rules':[{'rule_id':'rule-5','readings':[ret]}, {'rule_id':'rule-6','readings':[bad,good]}]}
    feedback=[{'kind':'joint_exception_binding','rule_id':'rule-6','target_rule_id':'rule-5','qualification_contains':'archival'}]
    return m,forest,feedback


def test_joint_source_constraint_distinguishes_equal_native_answers_and_updates_probability():
    m,f,feedback=source111_fixture()
    assert native_answers(project(m,f,[0,0]))==native_answers(project(m,f,[0,1]))
    p=problem(m,f,feedback)
    assert p['compatible'].tolist()==[False,True]
    assert choose(None,p)['choice']==[0,0]
    model=fit([p]);assert model['accepted']
    assert model['final_objective']<model['initial_objective']
    weights=dict(zip(model['feature_names'],model['weights']))
    delta=sum(weights.get(k,0.)*(p['feature_dicts'][1].get(k,0.)-p['feature_dicts'][0].get(k,0.)) for k in weights)
    assert delta>0  # One soft constraint need not overcome a fixed prior/L2.
    assert all('p111' not in k and 'rule-' not in k for k in model['feature_names'])


def test_negated_norm_and_consequence_do_not_turn_into_permission_or_absence():
    m,f,_=source111_fixture()
    ordinary=f['rules'][1]['readings'][1]
    no_breach={**ordinary,'head_kind':'breach','negation_scope':'head'}
    not_precluded={**ordinary,'head_kind':'restriction','negation_scope':'head'}
    assert meaning(no_breach)['effect'] is None
    assert meaning(not_precluded)['effect'] is None
    assert meaning(not_precluded)['formula']==['not',['prohibition','action']]
    # Only the construction's semantics is reused here, not its ungrounded
    # quote; project never manufactures a positive norm from this residual.
    f['rules'][1]['readings']=[not_precluded]
    state=project(m,f,[0,0])
    assert state['residuals'] and native_answers(state)['nda-20'] is None
    assert native_answers(state)['nda-16']=='Entailment'


def test_no_compatible_interpretation_is_retained_as_acquisition_failure():
    m,f,feedback=source111_fixture()
    f['rules'][1]['readings']=f['rules'][1]['readings'][:1]
    failed=fit([problem(m,f,feedback)])
    assert not failed['accepted'] and failed['uncovered']==['p111']
