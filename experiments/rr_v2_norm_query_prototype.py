"""Offline semantic probes for definition binding and potential permissions.

The primitive joins, SAT checks and consistency selection are ordinary controls.
This module has no language model, native labels, dataset writer or dispatch path.
It establishes distinctions a future learned compiler would have to preserve;
it is not itself evidence of two novel contributions.
"""
import z3


def recipient_members(term,definitions,expand):
    return set(definitions[term]) if expand and term in definitions else {term}


def classify_permission(rules,definitions,recipient,*,action,expand=True,mode='possible',facts=None):
    if mode not in ['possible','operative']:raise ValueError('Unknown query interpretation')
    if not isinstance(action,str) or not action:raise ValueError('Query action is required')
    positive=[];negative=[]
    for r in rules:
        if r['effect'] not in ['permission','prohibition']:raise ValueError('Unknown normative effect')
        if not isinstance(r['action'],str) or not r['action']:raise ValueError('Rule action is required')
        if r['action']!=action:continue
        if recipient not in recipient_members(r['recipient'],definitions,expand):continue
        (positive if r['effect']=='permission' else negative).append(r['guard'])
    p=z3.Or(*positive);n=z3.Or(*negative);s=z3.Solver()
    for name,value in (facts or {}).items():s.add(z3.Bool(name)==value)
    def sat(f):
        s.push();s.add(f);status=s.check();w={str(d):str(s.model()[d]) for d in s.model().decls()} if status==z3.sat else None;s.pop();return status,w
    if sat(z3.BoolVal(True))[0]!=z3.sat:raise ValueError('Inconsistent explicit context')
    pstatus,witness=sat(z3.And(p,z3.Not(n)));nstatus,_=sat(z3.And(n,z3.Not(p)))
    if mode=='possible':
        # Existential permissions concern feasible authorized circumstances,
        # not a factual claim that a disclosure has already happened.
        answer='Entailment' if pstatus==z3.sat else 'Contradiction' if sat(z3.Not(z3.And(n,z3.Not(p))))[0]==z3.unsat else None
    else:
        yes=sat(z3.Not(z3.And(p,z3.Not(n))))[0]==z3.unsat
        no=sat(z3.Not(z3.And(n,z3.Not(p))))[0]==z3.unsat
        answer='Entailment' if yes and not no else 'Contradiction' if no and not yes else None
    return {'answer':answer,'mode':mode,'action':action,'definition_expansion':expand,'witness':witness,
        'positive_consistent_context':str(pstatus),'negative_consistent_context':str(nstatus),
        'missing_permission_is_not_a_prohibition':True,
        'toy_IR_semantics_only_not_native_NLI_semantics_certificate':True}


def consistent_modes(rows):
    return [mode for mode in ['possible','operative'] if all(classify_permission(
        r['rules'],r['definitions'],r['recipient'],action=r['action'],mode=mode,facts=r.get('facts'))['answer']==r['label'] for r in rows)]


def offline_probes():
    always=z3.BoolVal(True);need=z3.Bool('need_to_know')
    definitions={'Representatives':['employee','external_adviser']}
    defined=[{'effect':'permission','action':'disclose','recipient':'Representatives','guard':always}]
    conditional=[{'effect':'permission','action':'disclose','recipient':'external_adviser','guard':need}]
    binding={str(expand):classify_permission(defined,definitions,'external_adviser',action='disclose',expand=expand) for expand in [False,True]}
    modality={mode:classify_permission(conditional,{},'external_adviser',action='disclose',mode=mode) for mode in ['operative','possible']}
    assert binding['False']['answer'] is None and binding['True']['answer']=='Entailment'
    assert modality['operative']['answer'] is None and modality['possible']['answer']=='Entailment'
    assert classify_permission([],{},'external_adviser',action='disclose')['answer'] is None
    return {'definition_binding_ablation':binding,'query_mode_ablation':modality,
        'ordinary_consistency_selection_on_software_label':consistent_modes([
            {'rules':conditional,'definitions':{},'recipient':'external_adviser','action':'disclose','label':'Entailment'}]),
        'same_grammar_consistency_learner_is_a_required_control_not_a_new_algorithm':True,
        'all_probes_authored_software_fixtures_not_native_examples_or_real_learning':True,
        'new_model_calls':0,'new_native_labels':0,'two_contributions_established':False}
