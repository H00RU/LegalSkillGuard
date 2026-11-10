"""First source-fact reader for the already paid TRAIN3 ordinary cache.

No labels/native annotations in the model payload; source code is unchanged.
This is a baseline probe, not new rule generation or method confirmation.
"""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import complete,digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.pal_frontend import lower_pal
from legal_skill_guard.rr.semantic_frames import obj
from legal_skill_guard.rr.source_program import compile_source,source_theory

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
RUN='train3_cached_fact_reader_v1_20261110';STAGE=BASE/RUN
FULL='reference_pal_teacher_sara3_full_v3_20261108:compile'
KEYS=('b_after_employment_termination','b_termination_death','b_retirement_for_disability')


def read(p):return json.loads(p.read_text())


def cached_source():
    parent=read(BASE/'redesign_source_roles_v1_20261109/seal.json')
    key=parent['sources']['train'][2]
    source=next(s for s in read(ROOT/'data/packets/rr_v2/public_train.json')['sources'] if s['key']==key)
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as c:
        row=c.execute('select result from calls where id=? and status=?',(FULL,'completed')).fetchone()
    code=json.loads(row[0])['value']['code'];programme,adaptation=lower_pal(source,code)
    compiled=compile_source(source,programme)
    assert set(compiled['query'].completion_dependencies())==set(KEYS)
    return parent,source,code,compiled,adaptation


def accept(value,source):
    assert type(value) is dict and set(value)==set(KEYS)
    for name,row in value.items():
        assert set(row)=={'value','quote'}
        if row['value'] is not None:
            assert type(row['value']) is bool and row['quote'] and row['quote'] in source['public']['facts'],name
        else:assert type(row['quote']) is str and (not row['quote'] or row['quote'] in source['public']['facts'])
    return {k:v['value'] for k,v in value.items()}


def prepare():
    parent,source,code,c,adaptation=cached_source()
    audit=read(ROOT/'reports/method_redesign_20261109/train3_cached_condition_results.json')
    assert audit['software_partial_condition_cases']==27
    materials=[]
    for name in KEYS:
        o=c['observations'][name];u=next(x for x in c['structure'].ledger.clauses if x.id==o['predicate_source'])
        materials.append({**o,'source_rule_sentence':c['structure'].ledger.text[u.start:u.end]})
    field=obj({'value':{'anyOf':[{'type':'boolean'},{'type':'null'}]},'quote':{'type':'string'}})
    schema=obj({k:field for k in KEYS});assert strict_output_schema_issues(schema)==[]
    system=('Read the supplied PUBLIC case facts and evaluate only the supplied source-derived factual predicates for their declared entities. '
        'Return each value as true, false, or null with an exact supporting case-text quote. '
        'Do not answer a legal question or infer a final legal qualification. '
        'Keep employer, employee, payment, termination, retirement and death events distinct and preserve any causal and temporal relationships stated in the case. '
        'Do not add dates or events. Do not treat an unmentioned event as false; use null when its presence/absence or the required relationship is not established by the case. '
        'Each non-null value needs an exact nonempty substring of the supplied PUBLIC facts; matching text alone is not a license to alter its meaning. '
        'Return only the structured values; no rule code or final answer.')
    user=json.dumps({'public_case_facts':source['public']['facts'],'actual_cached_predicate_tasks':materials},ensure_ascii=False)
    protocol=ROOT/'reports/method_redesign_20261109/train3_cached_fact_reader_protocol.md'
    files=['experiments/rr_v2_train3_cached_fact_reader.py','legal_skill_guard/rr/source_program.py',
        'legal_skill_guard/rr/pal_frontend.py','legal_skill_guard/rr/clause_scope.py','legal_skill_guard/rr/scoped_program.py',
        'legal_skill_guard/rr/coverage.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
    config=read(BASE/'contract_norm_binding_v1_20261110/seal.json')['config']
    seal={'run_id':RUN,'config':config,'sources':parent['sources'],'source':source,'old_paid_code':code,
        'old_paid_code_sha256':hashlib.sha256(code.encode()).hexdigest(),'programme':c['program'],'format_adaptation':adaptation,
        'messages':[{'role':'system','content':system},{'role':'user','content':user}],'schema':schema,
        'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'files':hashes,
        'binding':{'code_hash':digest(hashes),'config_hash':digest(config)},'goal_complete':False,
        'given_predicates_not_newly_learned_here':True,'cached_teacher_saw_case_and_question':True,
        'native_labels_and_annotation_dates_in_model_payload':False,'thinking':False}
    immutable_json(STAGE/'seal.json',seal)
    for p,h in hashes.items():
        raw=(ROOT/p).read_bytes();assert hashlib.sha256(raw).hexdigest()==h
        dest=STAGE/'frozen'/p;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert dest.read_bytes()==raw
        else:dest.write_bytes(raw)
    return seal


def main(generate):
    out=STAGE/'execution_before_cached_grading.json'
    if generate and out.exists():print(json.dumps({'saved_result':str(out),'no_redispatch':True}));return
    seal=prepare()
    if not generate:print(json.dumps({'prepared':True,'new_model_calls':0,'predicate_tasks':list(KEYS)}));return
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        binding=seal['binding'],sources=seal['sources'],authorization_hash=seal['protocol_sha256'],
        question='Does an ordinary fact-only Qwen OFF reader supply the actual already-paid TRAIN3 cache predicates from original public facts, without question, label, native annotation or rule regeneration? A baseline gap check, not either contribution.')
    client=MethodExecutor(ledger,STAGE,seal['config']['executor']);client.readiness()
    wire=client.generate(RUN+':facts',source=seal['source']['key'],purpose='method_primitive_observation',
        messages=seal['messages'],thinking=False,schema=seal['schema'])
    result={'physical_response':wire,'native_labels_opened_by_driver':False,'new_counterfactual_oracle_views':0,
        'source_rule_code_unchanged':True,'given_predicate_contract_not_new_source_learning':True,'goal_complete':False}
    try:
        value=json.loads(wire['content']);result['raw_generated_values']=value
        observed=accept(value,seal['source'])
        compiled=compile_source(seal['source'],seal['programme']);theory=source_theory(compiled,observed);completion=complete(theory)
        result.update(observed=observed,status=completion.status,answer=completion.answer,
            reason=completion.reason,projection=completion.projection,
            semantic_fidelity_still_requires_review=True,fallback_used=False)
    except Exception as e:result.update(status='rejected',error_type=type(e).__name__,error=str(e))
    immutable_json(out,result)
    print(json.dumps({k:result.get(k) for k in ['status','answer','observed','error']},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--generate',action='store_true');a=p.parse_args();main(a.generate)
