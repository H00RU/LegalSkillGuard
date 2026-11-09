"""Recover the preserved63 module and execute its preregistered TRAIN85 view.

No new model generation. This common source-cache path is not a new contribution.
Predictions are immutable before a separate TRAIN grading action.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.legal_case_grounding import citation
from legal_skill_guard.rr.legal_source_projection import (
    assess_view, calendar_year_condition, substitution_view)
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.source_obligations import compile_module, verify, bind_and_assess
from legal_skill_guard.rr.semantic_contracts import ContractError

ROOT=Path(__file__).resolve().parents[1]
RUN='legal_scope_replay_v1_20261110'
STAGE=ROOT/'artifacts/rr_method_redesign_20261109'/RUN
OLD=ROOT/'artifacts/rr_method_redesign_20261109/redesign_source_roles_v1_20261109'
SOURCE='SARA_v2_Binary:ff37f276befe4d94c75a66194216350a28d62ca83570c13e77928d9df5a4aff0'
DOMAIN_TEXT=('earned_income is an integer number of dollars; all Boolean inputs are true or false; '
             'is_head_of_household cannot be true when either is_joint_return or is_surviving_spouse is true.')
DOMAIN='not (is_head_of_household and (is_joint_return or is_surviving_spouse))'


def read(path):return json.loads(path.read_text())


def ledger_snapshot():
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
        snap={t:db.execute('select * from '+t+' order by 1').fetchall() for t in ('calls','meta','oracle_views')}
        counts=dict(db.execute('select role,count(*) from calls group by role'))
        pending=db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    return snap,{'counts_total':counts,'pending':pending,'logical_sha256':digest(snap)}


def adapted_module(value):
    if value['domain']!=DOMAIN_TEXT:raise ContractError('This recovery applies only to the captured explicit domain')
    signature={r['name']:r['type'] for r in value['inputs']}
    if signature.get('earned_income')!='integer' or any(t!='boolean' for n,t in signature.items() if n!='earned_income'):
        raise ContractError('The prose type clauses must equal the existing declared signature')
    out=deepcopy(value);out['domain']=DOMAIN
    assert all(out[k]==value[k] for k in value if k!='domain')
    return out


def c7_clauses(text):
    start=text.index('(7) Special rules for taxable years')
    end=text.index('\n(d) Itemized deductions',start)
    block=text[start:end]
    matches=list(re.finditer(r'(?m)^\s*\((i+)\) by substituting',block))
    if [m[1] for m in matches]!=['i','ii']:raise ContractError('Unexpected source substitution structure')
    governing=block[:matches[0].start()]
    clauses={f'63(c)(7)({m[1]})':block[m.start():matches[i+1].start() if i+1<len(matches) else len(block)].strip()
             for i,m in enumerate(matches)}
    return governing,clauses


def prepare():
    original=read(OLD/'seal.json')
    assert 85 in original['preregistered_original_case_TRAIN_ordinals']
    assert original['sources']['train'][84]==SOURCE
    raw_path=OLD/'teacher_sara63_basic_deduction.json'
    raw=read(raw_path)
    target=next(t for t in original['targets'] if t['id']=='sara63_basic_deduction')
    row=next(r for r in read(ROOT/'data/packets/rr_v2/public_train.json')['sources'] if r['key']==SOURCE)
    assert row['public']['rules']==target['rules']
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
        'experiments/rr_v2_legal_scope_replay.py','legal_skill_guard/rr/legal_source_projection.py',
        'legal_skill_guard/rr/source_obligations.py','legal_skill_guard/rr/semantic_contracts.py')}
    protocol=ROOT/'reports/method_redesign_20261109/legal_scope_replay_protocol.md'
    seal={'run_id':RUN,'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(original['config'])},
          'config':original['config'],'sources':original['sources'],'source':SOURCE,'original_TRAIN_ordinal':85,
          'source_public':row['public'],'source_module_acquired_from_original_TRAIN_ordinal':8,
          'raw_module_sha256':hashlib.sha256(raw_path.read_bytes()).hexdigest(),
          'original_source_role_seal_sha256':hashlib.sha256((OLD/'seal.json').read_bytes()).hexdigest(),
          'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
          'new_model_requests':0,'new_sources_added':0,'TEST_started':False,'goal_complete':False}
    immutable_json(STAGE/'seal.json',seal)
    return seal,raw


def run(seal,raw):
    before,before_info=ledger_snapshot();assert before_info['pending']==0
    value=raw['module'];source=seal['source_public']['rules']
    try:compile_module(value,source)
    except ContractError as exc:old_error={'type':type(exc).__name__,'error':str(exc)}
    else:raise ContractError('Expected the actual captured natural-language-domain rejection')
    adapted=adapted_module(value);module=compile_module(adapted,source);checks=verify(module)
    assert checks['all_supplied_obligations_verified']
    governing,clauses=c7_clauses(source)
    views={authority:substitution_view(module,clause,governing,authority) for authority,clause in clauses.items()}
    frozen={'module':adapted,'views':views,'raw_expression_unchanged':adapted['expression']==value['expression'],
            'new_rules_or_literals_added_to_expression':False,'candidate_method_promoted':False}
    immutable_json(STAGE/'frozen_source_cache.json',frozen)
    restored=read(STAGE/'frozen_source_cache.json')
    query=seal['source_public']['query'];authority=citation(query)
    year=re.findall(r'\b(?:19|20)\d\d\b',query);assert len(set(year))==1
    claim=re.findall(r'\$([0-9,]+)',query);assert len(claim)==1
    view=restored['views'][authority];claimed=int(claim[0].replace(',',''))
    flag=calendar_year_condition(view['condition_quote'],int(year[0]))
    result=assess_view(view,{view['condition_name']:flag},claimed,query_authority=authority)
    assert result==assess_view(views[authority],{view['condition_name']:flag},claimed,query_authority=authority)
    # A simple source-literal cache is an equally strong control for this view.
    ordinary={'applicable':flag,'value':view['new_amount'] if flag else None,
              'answer':'Entailment' if flag and view['new_amount']==claimed else 'Contradiction'}
    assert all(ordinary[k]==result[k] for k in ordinary)
    # Boundary controls are not extra natural-language benchmark cases.
    full_binding={k:None for k in module.signature}
    full_binding.update(is_2018_through_2025_taxable_year=True)
    full_value_claim=bind_and_assess(module,full_binding,claimed)
    joint=deepcopy(full_binding);joint.update(is_joint_return=True,is_c5_dependent=False,
        is_married_filing_separately_with_either_spouse_itemizing=False,
        is_nonresident_alien_individual=False,is_estate_trust_common_trust_fund_or_partnership=False)
    joint_control=bind_and_assess(module,joint,2*view['new_amount'])
    assert joint_control['answer']=='Entailment'
    immutable_json(STAGE/'adaptation_and_checks.json',{'original_rejection':old_error,
        'old_prose_domain':value['domain'],'canonical_domain':adapted['domain'],
        'only_domain_field_changed':True,'typed_signature_encodes_the_prose_type_clauses':True,
        'cross_role_prohibition_translated_without_added_restrictions':True,
        'no_nonnegative_income_assumption_added':True,'old_expression_obligations_and_inputs_unchanged':True,
        'original_seven_supplied_obligations':checks,
        'view_domain_existential_projection_checked':True,
        'whole_module_with_missing_external_roles':full_value_claim,
        'joint_return_nested_substitution_software_control':joint_control,
        'software_controls_are_not_new_neural_or_native_benchmark_cases':True})
    _,after_info=ledger_snapshot();assert before_info==after_info
    out={'closed_utc':datetime.now(timezone.utc).isoformat(),'source':SOURCE,'original_TRAIN_ordinal':85,
         'native_query':query,'queried_scope':authority,'claimed_amount':claimed,'query_calendar_year':int(year[0]),
         'actual_execution':result,'ordinary_correct_source_cache_control':ordinary,
         'same_policy_subsequent_TRAIN_source_not_unseen_law':True,
         'teacher_module_is_actual_generated_program':True,'executor_new_IR_or_learning_success':False,
         'fallback_used':False,'native_labels_opened_by_this_action':False,'new_model_calls':0,
         'ledger_before':before_info,'ledger_after':after_info,'new_rules_or_case_facts_invented':False,
         'new_method_increment_established':False,'goal_complete':False}
    immutable_json(STAGE/'execution_closed_before_grading.json',out)
    print(json.dumps(out,ensure_ascii=False,indent=2))


def grade(seal):
    result=read(STAGE/'execution_closed_before_grading.json')
    path=STAGE/'TRAIN_grade.json'
    if path.exists():print(json.dumps({'existing_grade':str(path)}));return
    view_hash=digest({'source':SOURCE,'public':seal['source_public'],'kind':'original_unmodified_TRAIN_source'})
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        binding=seal['binding'],sources=seal['sources'],authorization_hash=seal['protocol_sha256'],
        question='Recover an unambiguous existing source-module domain and execute preregistered TRAIN85 at its actual clause output scope; preserve old rejection and compare an ordinary correct source cache. Zero new model requests.')
    with ledger.transaction() as db:
        prior=db.execute('select 1 from oracle_views where source=? and view_hash=?',(SOURCE,view_hash)).fetchone()
    if not prior:ledger.reserve_oracle(SOURCE,view_hash)
    answer=read(ROOT/'data/packets/rr_v2/grading_only/train.json')['sources'][SOURCE]['answer']
    immutable_json(path,{'source':SOURCE,'view_hash':view_hash,'view_is_original_unmodified_TRAIN':True,
        'prediction_closed_before_label':True,'prediction':result['actual_execution']['answer'],'gold':answer,
        'correct':result['actual_execution']['answer']==answer,'ordinary_control_correct':result['ordinary_correct_source_cache_control']['answer']==answer,
        'TRAIN_oracle_view_charged_once':True,'new_physical_model_requests':0,'goal_complete':False})
    print(json.dumps(read(path),ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run','grade'])
    action=parser.parse_args().action;seal,raw=prepare()
    if action=='prepare':print(json.dumps({'prepared':True,'new_model_requests':0}))
    elif action=='run':run(seal,raw)
    else:grade(seal)
