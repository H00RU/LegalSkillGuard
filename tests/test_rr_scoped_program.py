"""Offline soundness checks. Invented cases are not core learning evidence."""
from fractions import Fraction

import pytest

from legal_skill_guard.rr.coverage import (
    FiniteTheory,Residual,SourceLedger,Unsupported,certificate,complete,plan_batch)
from legal_skill_guard.rr.interfaces import AllowanceBank,Amount,Relation,InterfaceError
from legal_skill_guard.rr.ir_types import IRTypeError
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.scoped_program import compile_query


def var(name):return {'var':name}
def op(name,*args):return {'op':name,'args':list(args)}
def node(name,body):return {'name':name,'kind':'expression','body':body}


def test_transitive_dependencies_and_exact_arithmetic():
    q=compile_query([node('third',op('divide_constant',var('n'),3)),
                     node('unused',var('other'))],var('third'),{},domains={'n':(1,2),'other':(0,1)})
    assert q.completion_dependencies()=={'n'}
    result=q.execute({'n':1,'other':0})
    assert result['answer']==Fraction(1,3)
    assert result['executed_nodes']==['third']


def test_inactive_union_branch_still_type_checks():
    with pytest.raises(IRTypeError):
        compile_query([node('mixed',op('if',var('b'),2,'wrong')),
                       node('sum',op('add',var('mixed'),1))],var('sum'),{},domains={'b':(False,True)})


@pytest.mark.parametrize('nodes',[
    [node('x',var('later')),node('later',1)],
    [node('x',1),node('x',2)],
    [node('input',2)],
])
def test_no_forward_references_or_shadowing(nodes):
    with pytest.raises((IRTypeError,Unsupported)):
        compile_query(nodes,var('x'),{'input':0})


def learned_query():
    library=SkillLibrary()
    key=library.add({'fields':['entity_equality'],'basis':'observed_source_collisions',
        'universal_semantic_equivalence_claim':False,'graphs':[{'op':'join_on',
        'inputs':[{'slot':'slot0'},{'slot':'slot1'}],'params':{'keys':['column0']}}]},source='offline:fixture')
    call={'pattern':key,'variant':0,'slots':{'slot0':'left','slot1':'right'},'columns':{'column0':'person'}}
    nodes=[{'name':'connected','kind':'connector','body':{'graph':{'op':'project_exists','inputs':[call]},'project':'identity'}},
           node('label',op('if',var('b'),var('connected'),False))]
    inputs={'left':Relation(('person',),(('Alice',),)), 'right':Relation(('person',),(('Alice',),)), 'b':False}
    return compile_query(nodes,var('label'),inputs,library=library.export()),inputs


def test_only_actually_executed_learned_calls_count_as_reuse():
    q,inputs=learned_query()
    result=q.execute(inputs)
    assert result['answer'] is False and result['pattern_uses']==[]
    assert result['executed_nodes']==['label']
    result=q.execute({**inputs,'b':True})
    assert result['answer'] is True
    assert len(result['pattern_uses'])==1
    assert result['executed_nodes']==['connected','label']


def test_wrapper_dependencies_remain_lazy_and_are_not_prefix_guesses():
    q=compile_query([node('n_result_extra',op('add',var('extra'),1)),
        {'name':'wrapped','kind':'connector','body':{'graph':{'slot':'count'},'project':'identity',
            'query':op('if',False,var('n_result_extra'),var('n_result'))}}],var('wrapped'),{'count':2,'extra':4})
    assert q.completion_dependencies()=={'count','extra'}
    assert q.execute({'count':2,'extra':4})['executed_nodes']==['wrapped']


def test_mutable_bank_has_one_owner_and_inputs_are_preserved():
    bank=AllowanceBank();key=('rule','owner','period')
    bank.create(key,100,policy='input_order',order_observable=True)
    inputs={'bank':bank,'key':key,'amounts':[Amount(80,'USD','owner','period',frozenset({'a'}),'element')]}
    body={'graph':{'op':'thread_allowance','inputs':[{'slot':'amounts'}],
                  'params':{'bank_slot':'bank','key_slot':'key'}},'project':'amount_values'}
    first={'name':'first','kind':'connector','body':body}
    with pytest.raises(Unsupported,match='one owning'):
        compile_query([first,{**first,'name':'second'}],var('first'),inputs)
    q=compile_query([first],var('first'),inputs)
    assert q.evaluate(inputs)==q.evaluate(inputs)==[0]
    assert bank.__rr_state__()['events']==[]


def theory_with_dead_choices(count=20):
    domains={'b'+str(i):(False,True) for i in range(count)}
    ledger=SourceLedger.from_text('\n'.join(domains))
    q=compile_query([node('identity',var('b0'))],op('if',var('identity'),1,0),{},domains=domains)
    return FiniteTheory(ledger,{},domains,q,
        [Residual(c.id,(name,),'accepted_translation',False) for c,name in zip(ledger.clauses,domains)])


def test_dead_domains_are_proved_irrelevant_not_sampled_or_resolved():
    theory=theory_with_dead_choices()
    result=complete(theory,max_worlds=2)
    assert result.status=='translation_unresolved' and len(result.worlds)==2
    assert result.projection['inactive_domain_multiplicity']==2**19
    assert result.projection['inactive_values_resolved'] is False
    assert all(len(w.choices)==20 for w in result.worlds)
    batch=plan_batch(theory,lambda units:len(units),1)
    assert batch.status=='separation_complete' and batch.selected==('s0',)
    theory.facts['b0']=True;del theory.domains['b0']
    theory.residuals[0]=Residual('s0',(),'accepted_translation',False)
    result=complete(theory,max_worlds=1)
    proof=certificate(theory,result)
    assert proof['answer']==1 and proof['completion_count']==2**19
    assert proof['enumerated_query_worlds']==1


def test_constraints_prevent_incorrect_domain_elimination():
    theory=theory_with_dead_choices(3)
    theory.constraints=[op('eq',var('b1'),var('b0'))]
    result=complete(theory,max_worlds=4)
    assert result.projection['active_slots']==['b0','b1']
    assert sorted(w.answer for w in result.worlds)==[0,1]
    theory.constraints.append(op('and',var('b2'),op('not',var('b2'))))
    assert complete(theory).status=='conflict'


def test_unknown_whole_clause_scope_still_blocks_projection():
    theory=theory_with_dead_choices(3)
    theory.residuals[2]=Residual('s2',('b2',),'accepted_translation',True)
    result=complete(theory)
    assert result.status=='translation_unresolved' and result.worlds==[]


def test_empty_inactive_domain_is_empty_omega_not_stable():
    theory=theory_with_dead_choices(3);theory.domains['b2']=()
    assert complete(theory).status=='conflict'


def test_enumeration_limit_never_certifies_a_prefix():
    theory=theory_with_dead_choices(3)
    result=complete(theory,max_worlds=1)
    assert result.status=='budget_exhausted'
    with pytest.raises(ValueError):certificate(theory,result)
