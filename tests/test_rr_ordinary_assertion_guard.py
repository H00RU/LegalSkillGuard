from copy import deepcopy
from experiments.rr_v2_ordinary_assertion_guard import guarded_case,citations

P={'rules':[{'head':{'predicate':p}} for p in ['dependent','section_151c_applies','deduction_under_151_allowable_to']]}


def case(predicate,quote):
    return {'facts':[{'atom':{'predicate':predicate,'arguments':['Bob','Alice','2015'],'positive':True},'quote':quote}],
        'query':{'predicate':predicate,'arguments':['Bob','Alice','2015'],'positive':True},'unresolved':[]}


def test_subcondition_does_not_match_parent_or_other_applicability_citation():
    c=case('section_151c_applies','Bob satisfies section 152(c)(1).')
    out,receipt=guarded_case(P,c)
    assert not out['facts'] and receipt['quarantined']
    assert citations('section 152(c)(1)')==[('152','c','1')]


def test_literal_given_status_is_retained():
    c=case('dependent',"Bob counts as Alice's dependent under section 152(c)(1) for 2015.")
    out,r=guarded_case(P,c);assert out==c and not r['quarantined']


def test_condition_only_status_is_quarantined_without_invented_negative():
    c=case('dependent','Bob satisfies section 152(c)(1) for 2015.');before=deepcopy(c)
    out,r=guarded_case(P,c)
    assert not out['facts'] and c==before and r['quarantine_is_not_negation_or_label_repair']
    assert out['query']==c['query'] and not any(not x['atom']['positive'] for x in out['facts'])


def test_actual_named_applicability_and_allowance_section_are_retained():
    for name,quote in [('section_151c_applies','Section 151(c) applies to these persons.'),
        ('deduction_under_151_allowable_to','Alice is entitled to an exemption under section 151(d) for Bob.')]:
        c=case(name,quote);assert guarded_case(P,c)[0]==c


def test_unhandled_opaque_head_not_claimed_certified():
    p={'rules':[{'head':{'predicate':'opaque_status'}}]};c=case('opaque_status','Other words.')
    out,r=guarded_case(p,c);assert out==c and r['unhandled_head_predicates']==['opaque_status']


def test_synonym_can_be_quarantined_and_is_not_falsified():
    c=case('dependent','Bob has the stipulated support status for Alice.')
    out,r=guarded_case(P,c);assert not out['facts'] and r['not_a_complete_semantic_validator']
