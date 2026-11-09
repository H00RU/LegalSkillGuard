"""Actual preserved module, caller-scope and unknown-input regressions."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from experiments.rr_v2_legal_scope_replay import adapted_module,c7_clauses
from legal_skill_guard.rr.legal_source_projection import (
    assess_view,calendar_year_condition,substitution_view)
from legal_skill_guard.rr.semantic_contracts import ContractError
from legal_skill_guard.rr.source_obligations import compile_module,verify,bind_and_assess

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'artifacts/rr_method_redesign_20261109/redesign_source_roles_v1_20261109'


def real():
    raw=json.loads((OLD/'teacher_sara63_basic_deduction.json').read_text())['module']
    seal=json.loads((OLD/'seal.json').read_text())
    source=next(t['rules'] for t in seal['targets'] if t['id']=='sara63_basic_deduction')
    module=compile_module(adapted_module(raw),source)
    governing,clauses=c7_clauses(source)
    view=substitution_view(module,clauses['63(c)(7)(ii)'],governing,'63(c)(7)(ii)')
    return raw,module,view


def test_actual_domain_recovery_changes_only_unambiguous_prose_not_the_generated_law():
    raw,module,view=real()
    assert raw['domain'].startswith('earned_income is an integer')
    assert module.raw['domain']!=raw['domain']
    assert all(module.raw[k]==raw[k] for k in raw if k!='domain')
    assert verify(module)['all_supplied_obligations_verified']
    changed=deepcopy(raw);changed['domain']+=' Extra unspecified restriction.'
    with pytest.raises(ContractError,match='only to the captured'):adapted_module(changed)


def test_actual_2019_query_executes_the_original_subexpression_with_its_local_authority():
    raw,module,view=real()
    flag=calendar_year_condition(view['condition_quote'],2019)
    result=assess_view(view,{view['condition_name']:flag},3000,query_authority='63(c)(7)(ii)')
    assert result['value']==12000 and result['answer']=='Contradiction'
    assert view['expression'] in raw['expression']
    assert view['existing_AST_occurrences']>1


def test_inapplicable_and_unknown_conditions_do_not_supply_an_ordinary_amount():
    _,_,view=real();name=view['condition_name']
    missing=assess_view(view,{name:None},3000,query_authority=view['authority'])
    assert missing['answer'] is None and missing['value'] is None
    inactive=assess_view(view,{name:False},3000,query_authority=view['authority'])
    assert inactive['answer']=='Contradiction' and inactive['value'] is None
    with pytest.raises(ContractError,match='different legal output scope'):
        assess_view(view,{name:True},12000,query_authority='63(c)(2)')


def test_temporal_boundaries_are_taken_from_the_original_role_quote():
    _,_,view=real();q=view['condition_quote']
    assert [calendar_year_condition(q,y) for y in (2017,2018,2025,2026)]==[False,True,True,False]
    assert calendar_year_condition(q,None) is None
    with pytest.raises(ContractError):calendar_year_condition('some year',2019)


def test_unmapped_or_nonunique_source_substitution_is_not_repaired():
    _,module,view=real()
    with pytest.raises(ContractError,match='No unique'):
        substitution_view(module,'by substituting "$13,000" for "$3,000"',view['condition_quote'],'63(c)(7)(ii)')
    with pytest.raises(ContractError,match='One explicit'):
        substitution_view(module,'by substituting "$12,000" for "$3,000"; by substituting "$18,000" for "$4,400"',view['condition_quote'],'63(c)(7)(ii)')


def test_projection_cannot_erase_a_real_constraint_on_the_selected_input():
    _,module,view=real()
    limited=deepcopy(module.raw);limited['domain']+=' and not '+view['condition_name']
    source=next(t['rules'] for t in json.loads((OLD/'seal.json').read_text())['targets'] if t['id']=='sara63_basic_deduction')
    limited_module=compile_module(limited,source)
    with pytest.raises(ContractError,match='domain restrictions'):
        substitution_view(limited_module,view['source_substitution_clause'],view['condition_quote'],view['authority'])


def test_existing_program_already_propagates_the_replaced_basis_to_joint_returns():
    _,module,view=real()
    binding={k:None for k in module.signature}
    binding.update(is_2018_through_2025_taxable_year=True,is_joint_return=True,is_c5_dependent=False,
        is_married_filing_separately_with_either_spouse_itemizing=False,is_nonresident_alien_individual=False,
        is_estate_trust_common_trust_fund_or_partnership=False)
    assert bind_and_assess(module,binding,24000)['answer']=='Entailment'
    binding['is_nonresident_alien_individual']=True
    assert bind_and_assess(module,binding,0)['answer']=='Entailment'
    assert assess_view(view,{view['condition_name']:True},12000,query_authority=view['authority'])['value']==12000
