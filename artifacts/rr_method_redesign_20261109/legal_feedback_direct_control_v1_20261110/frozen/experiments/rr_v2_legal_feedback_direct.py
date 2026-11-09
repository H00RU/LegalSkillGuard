"""Same-teacher ordinary programme acquisition cost control for the feedback pilot."""
import argparse,hashlib,json
from pathlib import Path
from experiments.rr_v2_legal_feedback_acquisition import BASE,ROOT,read,rows,raw_rows,validate_tests
from experiments.rr_v2_legal_annual_scope import probes,reference
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.ordinary_python_cache import execute
from legal_skill_guard.rr.semantic_frames import obj

RUN='legal_feedback_direct_control_v1_20261110';STAGE=BASE/RUN
SCHEMA=obj({'code':{'type':'string'}})
QUERY='component3306_b_1'


def check(code):
    scores=[]
    for p in probes():
        ids={q[0] for q in p['qualifications']};facts=rows([r for r in p['payments'] if r[0] in ids])
        try:
            v=execute(code,facts,QUERY)
            good=type(v) is int and v==p['expected'];error=None
        except Exception as exc:v=None;good=False;error=type(exc).__name__+': '+str(exc)
        scores.append({'name':p['name'],'actual':v,'source_expected':p['expected'],'passed':good,'error':error})
    return {'rows':scores,'all_passed':all(r['passed'] for r in scores),'software_source_checks_not_new_native_examples':True}


def prepare():
    old=read(BASE/'legal_feedback_acquisition_v1_20261110/seal.json')
    material=json.loads(old['messages']['free']['user'])
    material.pop('output_contract')
    material['output_contract']='Return ordinary Python code defining law_cache(facts,query). facts is the list of already-admitted payment row dictionaries described above; query is exactly the registered string component3306_b_1. Return one nonnegative integer, empty facts gives0. Top-level function helpers or one entry lambda are allowed. Use ordinary collections and builtin sum,min,max,any,all,len,sorted,set,list,dict,tuple,str,int,bool,enumerate,zip. No imports, classes, defaults, annotations, decorators, exceptions, files/network, private attributes or tools. No native case/query/label, expected test amounts or correct programme are supplied.'
    system='Compile one ordinary reusable Python source-policy cache. Derive the local included amount from the statutory source and common input contract, not by copying a candidate or a test label. All source text, candidate families and unlabelled pool inputs match the source-feedback comparison. You may reason about boundary cases, but return code only inside the required JSON field. Do not browse, read files, call tools or run code.'
    fixture="def law_cache(facts, query):\n    groups = {}\n    for p in facts:\n        key = (p['payer'],p['payee'],p['payment_year'])\n        groups[key] = groups.get(key,0)+p['amount']\n    return sum(min(7000,a) for a in groups.values())"
    assert check(fixture)['all_passed']
    protocol=ROOT/'reports/method_redesign_20261109/legal_feedback_direct_protocol.md'
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['experiments/rr_v2_legal_feedback_direct.py','experiments/rr_v2_legal_feedback_acquisition.py','experiments/rr_v2_legal_annual_scope.py','legal_skill_guard/rr/ordinary_python_cache.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py']}
    s={'run_id':RUN,'config':old['config'],'sources':old['sources'],'source':old['source'],'files':files,
       'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
       'messages':{'system':system,'user':json.dumps(material,ensure_ascii=False)},'schema':SCHEMA,'offline_source_runtime_checks':8,
       'same_teacher_same_source_unlabelled_pool_candidates':True,'no_new_model_feedback_or_expected_values_in_prompt':True,'goal_complete':False}
    immutable_json(STAGE/'seal.json',s);return s


def main(action):
    s=prepare()
    if action=='prepare':print(json.dumps({'prepared':True,'source_checks':8,'new_model_calls':0}));return
    path=STAGE/'source.json'
    if path.exists():print(json.dumps({'existing':str(path),'no_redispatch':True}));return
    l=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],
        question='Does learned source-feedback plus ordinary exact consistency have any cost advantage over an actual same-teacher ordinary policy programme, with the same source, contract, candidates and unlabelled inputs? A finite strong acquisition-cost control, no new native grading.')
    w=MethodTeacher(l,STAGE,s['config']['teacher']).summarize(RUN+':source',source_ids=[s['source']],system_prompt=s['messages']['system'],user_prompt=s['messages']['user'],output_schema=s['schema'])
    result={'physical_response':w,'code':w['value']['code'],'goal_complete':False}
    result['source_checks']=check(result['code'])
    immutable_json(path,result)
    print(json.dumps({'source_checks':result['source_checks'],'elapsed_seconds':w['elapsed_seconds']},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','generate']);main(p.parse_args().action)
