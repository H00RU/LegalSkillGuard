"""Regression fixtures are source-grounded software tests, not model evidence."""
import json
from copy import deepcopy
from pathlib import Path

from legal_skill_guard.rr.source_attachment_learning import meaning, problem, fit, choose, project, native_answers

ROOT=Path(__file__).resolve().parents[1]


def reading(program,head,action,*,obj,negquote='',target=None):
    return {'program':program,'head_quote':head,'action_quote':action,
            'negation_quote':negquote,'actor_quote':'Recipient','object_quote':obj,
            'exception_target':target,'conditions':['solely for archival purpose'] if program=='P(A)' else [],'references':[],
            'context_quotes':[],'prior_logit':0.,'information_anchor':obj}


def source111_fixture():
    seal=json.loads((ROOT/'artifacts/rr_method_redesign_20261109/contract_attachment_update_v1_20261110/training_seal.json').read_text())
    m=deepcopy(next(m for m in seal['documents'] if m['key']=='p111'))
    m['graph']['rules']=[r for r in m['graph']['rules'] if r['id'] in ['rule-5','rule-6']]
    m['graph']['scopes']=[s for s in m['graph']['scopes'] if s['id'] in {r['scope_id'] for r in m['graph']['rules']}]
    canonical="such Discloser’s Confidential Information"
    assert canonical in m['document']
    ret=reading('O(A)','Recipient shall','return',obj=canonical)
    good=reading('P(A)','may retain','retain',obj=canonical,target='rule-5')
    good['prior_logit']=-1.
    bad={**good,'object_quote':'this Agreement','information_anchor':'','prior_logit':0.}
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
    no_breach={**ordinary,'program':'NOT(BREACH(A))'}
    not_precluded={**ordinary,'program':'NOT(F(A))'}
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


def test_actual_first_response_is_rejected_by_required_keys_and_anchor_schema():
    import jsonschema
    from experiments.rr_v2_source_attachment_learning import source_schema
    p=ROOT/'artifacts/rr_method_redesign_20261109/source_attachment_learning_v1_20261110/p15_forest.json'
    raw=json.loads(p.read_text());value=json.loads(raw['wire']['content'])
    schema,anchors=source_schema(raw['material'])
    # Structural conversion does not add any omitted reading or fix its values.
    keyed={r['rule_id']:r['readings'] for r in value['rules']}
    errors=list(jsonschema.Draft202012Validator(schema).iter_errors(keyed))
    assert sum(e.validator=='required' and not list(e.path) for e in errors)==3
    assert any('action_quote' in list(e.path) for e in errors)
    assert any('exception_target' in list(e.path) for e in errors)
    assert 'share' not in anchors['rule-1']


def test_actual_expanded_operand_is_bound_without_changing_outer_operators():
    from legal_skill_guard.rr.source_attachment_forests import compile_forest
    p=ROOT/'artifacts/rr_method_redesign_20261109/source_attachment_learning_v3_20261110/p15_forest.json'
    raw=json.loads(p.read_text());m=raw['material'];value=json.loads(raw['wire']['content'])
    compiled=compile_forest(m,value)
    programs={r['program'] for r in compiled['forest']['rules'][0]['readings']}
    assert programs=={'F(A)','NOT(P(A))','P(A)'}
    assert compiled['separate_preserved_seed_proposals'][0]['program']=='P(A)'
    assert compiled['literal_or_operand_adaptations']
    feedback=[{'kind':'source_head','rule_id':'rule-4','forbidden_derived_effects':['permission'],'equals':{},
               'contains':{'head_quote':'prohibited','action_quote':'disclos'},'list_contains':{'references':'Except as provided herein'}}]
    p=problem(m,compiled['forest'],feedback)
    assert p['compatible'].any()
    assert not choose(None,p)['training_compatible']
    # This is hypothesis expansion/partial-supervision input, not a claim
    # that NOT(P(A)) was a correct model answer or that missing rules recovered.
    assert not compiled['missing_source_claims_supplied'] and not compiled['new_semantics_invented']


def test_actual_111_recovery_reuses_paid_heads_and_resolves_information_not_copy_identity():
    from legal_skill_guard.rr.source_attachment_forests import compile_forest
    p=ROOT/'artifacts/rr_method_redesign_20261109/source_attachment_learning_v4_20261110/p111_forest.json'
    raw=json.loads(p.read_text());m=raw['material'];value=json.loads(raw['wire']['content'])
    compiled=compile_forest(m,value)
    assert any(r['program']=='P(A)' for r in compiled['forest']['rules'][1]['readings'])
    assert compiled['rejected_readings']  # destroy/copy are not renamed retain/return-or-destroy.
    assert all(x['copy_quantities_not_equated'] for x in compiled['unique_information_reference_bindings'])
    feedback=[{'kind':'joint_exception_binding','rule_id':'rule-6','target_rule_id':'rule-5','qualification_contains':'archival'}]
    p=problem(m,compiled['forest'],feedback)
    assert p['compatible'].any()


def test_nested_operator_preferences_can_depend_on_source_head_words():
    import numpy as np
    from legal_skill_guard.rr.source_attachment_forests import compile_forest
    from legal_skill_guard.rr.source_attachment_learning import features
    p=ROOT/'artifacts/rr_method_redesign_20261109/source_attachment_learning_v4_20261110/p20_forest.json'
    raw=json.loads(p.read_text());m=raw['material'];compiled=compile_forest(m,json.loads(raw['wire']['content']))['forest']
    a=deepcopy(next(r for r in compiled['rules'][0]['readings'] if r['program']=='NOT(BREACH(A))'))
    b=deepcopy(next(r for r in compiled['rules'][0]['readings'] if r['program']=='NOT(O(A))'))
    differences=[]
    for word,direction in [('breached',1),('obligation',-1)]:
        a['head_quote']=word;b['head_quote']=word
        f={'rules':[{'rule_id':'rule-2','readings':[deepcopy(a),deepcopy(b)]}]}
        x=features(m,f,[0]);y=features(m,f,[1])
        differences.append({k:direction*(x.get(k,0)-y.get(k,0)) for k in x.keys()|y.keys()})
    names=sorted({k for d in differences for k in d})
    assert np.linalg.matrix_rank([[d.get(k,0) for k in names] for d in differences])==2
    # These are two actual quoted words used for representation-capacity
    # regression, not two new legal cases or native supervision labels.
