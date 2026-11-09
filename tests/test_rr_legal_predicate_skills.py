from copy import deepcopy
import pytest
from legal_skill_guard.rr.legal_predicate_skills import validate,run,learned_guards,match_guard

Q='In the case of an individual with respect to whom a deduction under this section is allowable to another taxpayer, the exemption amount shall be zero.'

def atom(p,*a,positive=True):return {'predicate':p,'arguments':list(a),'positive':positive}

def program():
 def pred(n,r,functional=False):return {'name':n,'roles':r,'functional':functional,'meaning':n}
 def rule(i,h,b,different=None):return {'id':i,'authority':'151','head':h,'body':b,'different':different or [],'guard_quote':Q.split(',')[0],'quote':Q}
 return {'predicates':[pred('case_subject_year',['person','year']),pred('deduction',['claimant','subject','year']),pred('applies',['person','year']),pred('amount',['person','year','dollars'],True)],
 'rules':[rule('role',atom('applies','?subject','?year'),[atom('deduction','?claimant','?subject','?year')],[{'left':'?claimant','right':'?subject'}]),
 rule('base',atom('amount','?person','?year','2000'),[atom('case_subject_year','?person','?year')]),
 rule('zero',atom('amount','?person','?year','0'),[atom('applies','?person','?year')])],
 'priorities':[{'higher':'zero','lower':'base','quote':Q}],'unresolved':[]}

def case(facts,query):return {'facts':[{'atom':a,'quote':'evidence'} for a in facts],'query':query,'unresolved':[]}

def test_directed_witness_and_unseen_claimant_not_false():
 p=program();validate(p,['§151 '+Q]);c=case([atom('deduction','Alice','Bob','2015')],atom('applies','Bob','2015'))
 o=run(p,c);assert o['answer']=='Entailment';assert o['rule_witnesses'][0]['bindings']['?subject']=='Bob'
 assert run(p,case(c['facts'] and [atom('deduction','Alice','Bob','2015',positive=False)],c['query']))['answer'] is None
 assert run(p,case([atom('deduction','Bob','Alice','2015')],c['query']))['answer'] is None


def test_priority_preserves_key_and_removes_conflicting_general_amount():
 p=program();c=case([atom('case_subject_year','Bob','2015'),atom('case_subject_year','Alice','2015'),atom('deduction','Alice','Bob','2015')],atom('amount','Bob','2015','2000'))
 o=run(p,c);assert o['answer']=='Contradiction';assert len(o['suppressed'])==1
 assert o['suppressed'][0]['loser']['bindings']['?person']=='Bob'
 flat=run(p,c,use_priorities=False);assert flat['answer'] is None and flat['query_supported'] and flat['query_refuted']
 assert ['amount',['Alice','2015','2000'],True] in o['known_atoms']


def test_calendar_key_and_same_person_do_not_create_exception():
 p=program()
 for a in [atom('deduction','Alice','Bob','2014'),atom('deduction','Bob','Bob','2015')]:
  assert run(p,case([a],atom('applies','Bob','2015')))['answer'] is None


def test_template_resolves_only_explicit_own_section_reference():
 p=program();lib=learned_guards(p,['§151 '+Q]);target=Q.replace('this section','section 151')
 assert match_guard(lib,target,63)
 assert not match_guard(lib,Q.replace('this section','section 152'),63)


def test_invalid_scope_and_priority_cycles_are_rejected():
 p=program();p['rules'][0]['head']['arguments'][0]='?unbound'
 with pytest.raises(ValueError,match='Unsafe'):validate(p,['§151 '+Q])
 p=program();p['priorities'].append({'higher':'base','lower':'zero','quote':Q})
 with pytest.raises(ValueError,match='Cyclic'):validate(p,['§151 '+Q])


def test_native_projection_does_not_invent_unasked_claimant():
 p=program();c=case([atom('deduction','Alice','Bob','2015')],atom('applies','Bob','2015'))
 p['predicates'].append({'name':'relation_applies','roles':['claimant','subject','year'],'functional':False,'meaning':'role preserving applicability'})
 p['rules'][0]['head']=atom('relation_applies','?claimant','?subject','?year')
 c['query']=atom('relation_applies',None,'Bob','2015')
 o=run(p,c);assert o['answer']=='Entailment';assert o['query_witnesses']==[['relation_applies',['Alice','Bob','2015'],True]]
 c['facts']=[{'atom':atom('deduction','Alice','Bob','2015',positive=False),'quote':'evidence'}]
 assert run(p,c)['answer'] is None


def test_conflicting_body_evidence_cannot_propagate_a_legal_conclusion():
 p=program();c=case([atom('deduction','Alice','Bob','2015'),atom('deduction','Alice','Bob','2015',positive=False)],atom('applies','Bob','2015'))
 o=run(p,c);assert o['answer'] is None;assert not o['rule_witnesses']


def test_unfounded_rule_cycle_is_not_legal_evidence():
 p=program();p['rules']=[{**p['rules'][0],'head':atom('applies','?person','?year'),'body':[atom('applies','?person','?year')],'different':[]}];p['priorities']=[]
 o=run(p,case([],atom('applies','Bob','2015')));assert o['answer'] is None;assert o['known_atoms']==[]
