"""Actual-source controls for the new generative logic frontend, no model calls."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.model_horn import (LogicTranslationError,parse_model_horn,
                                            assess_model_horn,model_horn_prompt)
from legal_skill_guard.rr.source_structure import inspect_source

ROOT=Path(__file__).resolve().parents[1]


def actual_source():
    rows=json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']
    return next(s for s in rows if s['key']=='ProofWriter_OWA_depth5:43ec41194db931b0e509a68dddf476b80e9edb3c5b98cdc6ce889b19314ba096')


CONTROL='''-chases(cat,squirrel). % s0
blue(cat). % s1
chases(cow,cat). % s2
chases(cow,squirrel). % s3
kind(cow). % s4
-young(cow). % s5
chases(mouse,cat). % s6
needs(mouse,cat). % s7
sees(mouse,cat). % s8
sees(mouse,squirrel). % s9
chases(squirrel,cow). % s10
-chases(squirrel,cat). % s11
-round(squirrel). % s12
young(squirrel). % s13
kind(X) :- chases(X,cat). % s14
sees(X,cow) :- kind(X). % s15
-round(X) :- young(X), needs(X,cow). % s16
sees(mouse,cow) :- needs(X,cow), chases(X,mouse). % s17
kind(X) :- needs(X,cow). % s18
needs(cat,cow) :- sees(X,cow), chases(X,cat). % s19
needs(X,mouse) :- sees(X,cow). % s20
chases(cat,mouse) :- needs(cat,cow). % s21
?- -round(cat). % s22'''


def test_actual_complete_control_uses_its_own_formulas_and_has_no_fallback(monkeypatch):
    import legal_skill_guard.rr.public_horn as public
    def forbidden(*args,**kwargs):raise AssertionError('The public parser cannot generate this prediction')
    monkeypatch.setattr(public,'parse_public',forbidden)
    source=actual_source();before=digest(source);p=parse_model_horn(source,CONTROL)
    assert not p.export()['missing_units'] and len(p.facts)==14 and len(p.rules)==8
    result=assess_model_horn(p)
    assert result['answer']=='Unknown' and result['certificate_status']=='completion_stable'
    assert result['certificate'] and not result['fallback_used']
    assert digest(source)==before and not result['A_residual_followup_proved']


def test_omitted_source_is_not_filled_by_the_independent_grammar_checker():
    text=CONTROL.replace('blue(cat). % s1\n','')
    p=parse_model_horn(actual_source(),text);result=assess_model_horn(p)
    assert 's1' in result['missing_source_units'] and result['certificate'] is None
    assert result['certificate_status']!='completion_stable' and result['answer'] is None


def test_alpha_renaming_and_reordered_conjuncts_preserve_the_exact_rule_semantics():
    code=CONTROL.replace('-round(X) :- young(X), needs(X,cow).',
                         '-round(Person) :- needs(Person,cow), young(Person).')
    assert assess_model_horn(parse_model_horn(actual_source(),code))['answer']=='Unknown'


@pytest.mark.parametrize('old,new',[
    ('young(X), needs(X,cow)','young(X)'),
    ('needs(cat,cow) :- sees(X,cow), chases(X,cat)',
     'needs(cat,cow) :- sees(X,cow), chases(Y,cat)'),
    ('-young(cow). % s5','young(cow). % s5'),
    ('?- -round(cat). % s22','?- round(cat). % s22'),
    ('% s0','% s9999'),
    ('blue(cat). % s1','blue(mouse). % s1'),
    ('kind(X) :- chases(X,cat)','kind(Y) :- chases(X,cat)'),
])
def test_actual_semantic_errors_are_rejected_before_execution(old,new):
    with pytest.raises(LogicTranslationError):parse_model_horn(actual_source(),CONTROL.replace(old,new))


@pytest.mark.parametrize('suffix',['\nTrue','\nquery = "Unknown"','\nblue(cat).','\nblue(cat). % s1'])
def test_native_answers_unattributed_lines_and_duplicate_ownership_do_not_supply_IR(suffix):
    with pytest.raises(LogicTranslationError):parse_model_horn(actual_source(),CONTROL+suffix)


def test_truncation_is_rejected_and_exact_complete_fence_is_losslessly_removed():
    with pytest.raises(LogicTranslationError):parse_model_horn(actual_source(),CONTROL[:-10])
    assert parse_model_horn(actual_source(),'```prolog\n'+CONTROL+'\n```').export()['represented_units']==parse_model_horn(actual_source(),CONTROL).export()['represented_units']


def test_prompt_contains_every_original_unit_and_no_reference_program_or_target_label():
    source=actual_source();user=json.loads(model_horn_prompt(source)[1]['content'])
    structure=inspect_source(source)
    assert user['units']==[{'id':c.id,'role':structure.roles[c.id]['role'],
        'text':structure.ledger.text[c.start:c.end]} for c in structure.ledger.clauses]
    assert set(user)=={'units','source_only_feedback'}


def test_actual_later_source_runs_the_preserved_join_graph_on_generated_formulas():
    from legal_skill_guard.rr.public_horn import parse_atom,parse_rule
    from legal_skill_guard.rr.learning import SkillLibrary
    rows=json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']
    source=next(s for s in rows if s['key']=='ProofWriter_OWA_depth5:e95366c5947484c083f10b4fea4f936a17ec6bb58ed903aa3f1d376b7105c2dc')
    structure=inspect_source(source)
    def term(t):return t[1:].upper() if t.startswith('?') else repr(t)
    def atom(a):return ('' if a.positive else '-')+a.predicate+'('+','.join(term(t) for t in a.arguments)+')'
    # This deterministic conversion is an offline positive control only;
    # actual model requests never receive its program or a parser answer.
    lines=[]
    for c in structure.ledger.clauses:
        text=structure.ledger.text[c.start:c.end];role=structure.roles[c.id]['role']
        if role=='rule':
            r=parse_rule(text,c.id);value=atom(r.head)+' :- '+','.join(atom(a) for a in r.body)
        else:value=('?- ' if role=='query' else '')+atom(parse_atom(text))
        lines.append(value+'. % '+c.id)
    origin=actual_source()['key']
    record=json.loads((ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_ast_v1_20261107/build/sources'/(digest(origin)+'.json')).read_text())
    library=SkillLibrary();library.add(record['learning']['learned_pattern'],source=origin)
    program=parse_model_horn(source,'\n'.join(lines));result=assess_model_horn(program,library.export(),interface='collision_refined')
    assert result['certificate_status']=='completion_stable' and result['B_main_path_executed']
    assert result['execution']['pattern_uses'] and not result['fallback_used']
    assert all(p['source_units'] for p in result['execution']['pattern_uses'])
    missing=assess_model_horn(program,{'patterns':[]},interface='collision_refined')
    assert missing['answer'] is None and missing['certificate'] is None
    assert missing['certificate_status']!='completion_stable' and not missing['fallback_used']
