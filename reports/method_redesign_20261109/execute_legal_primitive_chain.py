"""Freeze the actual primitive-fact/source-program chain before TRAIN grading."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,re,sqlite3
from pathlib import Path

from experiments.rr_v2_legal_primitive_chain import HEAD,PRIMITIVES,query_year,ledger
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_case_grounding import compile_question
from legal_skill_guard.rr.legal_predicate_skills import validate,validate_case,run
from legal_skill_guard.rr.source_obligations import compile_module,bind_and_assess

ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'artifacts/rr_method_redesign_20261109/legal_primitive_chain_v2_20261110'


def read(p):return json.loads(p.read_text())


def literal_support(source):
    """Independent finite source checks; never fills a model's omitted facts."""
    text=source['facts'];year=query_year(source['query'])
    if not re.search(r'\bIn '+year+r', ',text):raise ValueError('No unique literal narrative-year anchor')
    support={}
    for quote in re.split(r'(?<=\.)\s+',text.strip()):
        m=re.fullmatch(r'([A-Z][a-z]+) and ([A-Z][a-z]+) have been married since .*, (\d{4})\.',quote)
        if m and m[3]==year:
            support[quote]={('married',(m[1],m[2],year),True),('married',(m[2],m[1],year),True)}
        m=re.fullmatch(r'([A-Z][a-z]+) and ([A-Z][a-z]+) file separate returns\.',quote)
        if m:support[quote]={('separate_return',(m[1],year),True),('separate_return',(m[2],year),True)}
        m=re.fullmatch(r'([A-Z][a-z]+) is allowed an itemized deduction of \$([0-9,]+)\.',quote)
        if m:support[quote]={('itemized_deduction',(m[1],year),True)}
    return support


def accept_facts(value,source):
    supported=literal_support(source);out=[];seen=set();audit=[]
    for i,row in enumerate(value['facts']):
        a=row['atom'];key=(a['predicate'],tuple(a['arguments']),a['positive'])
        if key not in supported.get(row['quote'],set()):raise ValueError('Unsupported actual premise at row '+str(i))
        if key not in seen:out.append(deepcopy(row));seen.add(key)
        audit.append({'row_index':i,'participant_year_and_polarity_supported_by_literal_sentence':True})
        if a['predicate']=='married':
            p,q,y=a['arguments'];reverse=('married',(q,p,y),a['positive'])
            if reverse not in seen:
                out.append({'atom':{**a,'arguments':[q,p,y]},'quote':row['quote']});seen.add(reverse)
    return out,{'all_actual_model_rows_supported':True,'rows_checked':audit,
                'only_adaptations':'equality duplicate removal and declared undirected-marriage symmetry',
                'no_missing_model_premises_filled':True,'no_target_legal_conclusion_in_fact_inputs':True}


def ordinary_guard(case):
    facts={(r['atom']['predicate'],tuple(r['atom']['arguments'])) for r in case['facts'] if r['atom']['positive']}
    person,year=case['query']['arguments']
    yes=any(p=='married' and args[0]==person and args[2]==year and
        ('separate_return',(person,year)) in facts and
        (('itemized_deduction',(person,year)) in facts or ('itemized_deduction',(args[1],year)) in facts)
        for p,args in facts)
    return 'Entailment' if yes else None


def execute():
    s=read(STAGE/'seal.json');source=read(STAGE/'source.json');raw=read(STAGE/'facts.json')
    assert source['validation']['c6']['status']=='validated_source_program'
    assert source['validation']['f68']['status']=='validated_source_module'
    for name,want in s['files'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==want,name
    immutable_json(STAGE/'execution_seal.json',{'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_response_sha256':hashlib.sha256((STAGE/'source.json').read_bytes()).hexdigest(),
        'fact_response_sha256':hashlib.sha256((STAGE/'facts.json').read_bytes()).hexdigest(),
        'input_programs_frozen_before_grade':True,'labels_opened':False})
    program=source['value']['c6_program'];public=s['cases']['8']['public']
    facts,fact_check=accept_facts(raw['value'],public)
    case={'ordinal':8,'facts':facts,'query':compile_question(public['query'],program),'unresolved':raw['value']['unresolved']}
    info=validate(program,[public['rules']]);validate_case(case,public['facts'],info['predicates'])
    basic=read(ROOT/'artifacts/rr_method_redesign_20261109/legal_scope_replay_v1_20261110/frozen_source_cache.json')['module']
    cache={'c6_program':program,'f68_module':source['value']['f68_module'],'basic63_module':basic}
    immutable_json(STAGE/'frozen_library.json',cache);restored=read(STAGE/'frozen_library.json')
    c6=run(restored['c6_program'],case);control=ordinary_guard(case)
    assert c6['answer']==control
    scalar=compile_module(restored['basic63_module'],public['rules'])
    role=next(r for r in basic['inputs'] if r['name']=='is_married_filing_separately_with_either_spouse_itemizing')
    assert any(r['guard_quote']==role['quote'] for r in program['rules'])
    binding={k:None for k in scalar.signature}
    if c6['answer']=='Entailment':binding[role['name']]=True
    effect=bind_and_assess(scalar,binding,0)
    f68=compile_module(restored['f68_module'],s['cases']['76']['public']['rules'])
    year=int(query_year(s['cases']['76']['public']['query']))
    temporal=bind_and_assess(f68,{'year':year},True,comparison='applies')
    assert c6==run(cache['c6_program'],case)
    assert temporal==bind_and_assess(compile_module(cache['f68_module'],s['cases']['76']['public']['rules']),{'year':year},True,comparison='applies')
    out={'closed_utc':datetime.now(timezone.utc).isoformat(),'original_TRAIN_ordinals':[8,76],
        'c6_native':{'source':s['cases']['8']['key'],'query':public['query'],'case':case,'proof':c6,
            'ordinary_correct_join_control':control,'actual_fact_semantic_check':fact_check,'fallback_used':False,
            'whole_applicability_was_not_a_fact_input':True},
        'actual_composition_into_old_basic_deduction_module':{'matched_source_guard_quote':role['quote'],
            'binding':binding,'assessment_of_zero':effect,'not_an_extra_native_case':True},
        'f68_native':{'source':s['cases']['76']['key'],'query':s['cases']['76']['public']['query'],
            'year':year,'assessment':temporal,'source_scope':'local_exception_activation_not_whole68_applicability',
            'other_case_facts_not_used_to_generate_program':True,'fallback_used':False},
        'library_restoration_reproduces_actual_predictions':True,'labels_opened_by_execution':False,
        'source_and_fact_messages_separated':True,'two_method_contributions_established':False,'goal_complete':False}
    immutable_json(STAGE/'execution_closed_before_grading.json',out)
    print(json.dumps({'c6_answer':c6['answer'],'ordinary_control':control,'composed_zero':effect['answer'],
                      'f68_answer':temporal['answer'],'model_facts_supported':fact_check['all_actual_model_rows_supported']},ensure_ascii=False))


def grade():
    s=read(STAGE/'seal.json');pred=read(STAGE/'execution_closed_before_grading.json')
    if (STAGE/'TRAIN_grades.json').exists():print('Existing frozen TRAIN grades');return
    # Compatible legacy original views use this exact source-learning base view.
    view={'kind':'SARA_v2_Binary','edit':None};vh=digest(view);l=ledger(s);rows=[]
    for ordinal,p in [('8',pred['c6_native']['proof']),('76',pred['f68_native']['assessment'])]:
        key=s['cases'][ordinal]['key']
        with l.transaction() as db:prior=db.execute('select 1 from oracle_views where source=? and view_hash=?',(key,vh)).fetchone()
        if not prior:l.reserve_oracle(key,vh)
        gold=read(ROOT/'data/packets/rr_v2/grading_only/train.json')['sources'][key]['answer']
        rows.append({'original_TRAIN_ordinal':int(ordinal),'source':key,'view_hash':vh,'view':view,
                     'prediction':p['answer'],'gold':gold,'correct':p['answer']==gold,
                     'compatible_prior_view_reused':bool(prior),'prediction_frozen_before_grade':True})
    immutable_json(STAGE/'TRAIN_grades.json',{'rows':rows,'new_model_calls':0,'TEST_started':False,'goal_complete':False})
    print(json.dumps(rows,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['execute','grade']);a=p.parse_args().action
    execute() if a=='execute' else grade()
