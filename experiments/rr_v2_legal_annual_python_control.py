"""Ordinary PAL-style source Python control after local SQL/plan failures."""
import argparse,hashlib,json,multiprocessing
from pathlib import Path

from experiments.rr_v2_legal_annual_scope import ROOT, probes, read, reference
from experiments.rr_v2_legal_independent_cache import check_code,_worker
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger

RUN='legal_annual_python_control_v1_20261110'
STAGE=ROOT/'artifacts/rr_method_redesign_20261109'/RUN
MATCH=ROOT/'artifacts/rr_method_redesign_20261109/legal_annual_scope_v3_20261110'
NAMES=['payment_id','payer','payee','payment_year','service_id','amount']


def admitted(payments,qualifications):
    ids={r[0] for r in qualifications}
    return [dict(zip(NAMES,r)) for r in payments if r[0] in ids]


def execute_scalar(code,facts):
    # Reuse the generic resource-limited worker and AST checker. The older
    # execute_code wrapper enforces a legal answer dict, which this integer
    # component does not return; no generated function or value is rewritten.
    check_code(code)
    context=multiprocessing.get_context('fork');parent,child=context.Pipe(duplex=False)
    process=context.Process(target=_worker,args=(child,code,facts,{'component':'3306_b_1','return':'included_total'},[]))
    process.start();child.close()
    try:
        if not parent.poll(8):raise ValueError('Scalar Python control exceeded execution bound')
        result=json.loads(parent.recv_bytes())
    finally:
        if process.is_alive():process.terminate()
        process.join();parent.close()
    if 'error' in result:raise ValueError(result['error_type']+': '+result['error'])
    return result['value']


def checks(code):
    check_code(code);rows=[]
    for p in probes():
        try:
            actual=execute_scalar(code,admitted(p['payments'],p['qualifications']))
            passed=type(actual) is int and actual==p['expected'];error=None
        except Exception as exc:actual=None;passed=False;error=type(exc).__name__+': '+str(exc)
        rows.append({'name':p['name'],'actual':actual,'expected':p['expected'],'passed':passed,'error':error})
    return {'rows':rows,'all_passed':all(r['passed'] for r in rows),'source_probes_not_native_dataset_examples':True}


def prepare():
    old=read(MATCH/'seal.json');common=json.loads(old['messages']['sql'][1]['content'])
    code="def law_cache(facts, query):\n    totals = {}\n    for p in facts:\n        k = (p['payer'], p['payee'], p['payment_year'])\n        totals[k] = totals.get(k, 0) + p['amount']\n    return sum(min(7000, x) for x in totals.values())\n"
    assert checks(code)['all_passed']
    system=('Implement the supplied local source amount rule as one ordinary Python policy-cache function law_cache(facts, query). '
      'facts is the admitted_payments relation represented as a list of dicts with the six supplied column names. query identifies component3306_b_1 and requests the integer included total; do not hardcode a case answer. '
      'Use the same source and source-contract feedback as the SQL/plan controls. Infer the legal operation, threshold and grouping keys from the source. '
      'All candidate-admission and physical-payment uniqueness preprocessing is identical across controls; do not implement other3306 provisions. '
      'Use ordinary dict/list/tuple/set operations, for loops, if/else, integer arithmetic and allowed builtins set,frozenset,list,dict,tuple,str,int,bool,len,sorted,enumerate,zip,any,all,min,max,sum,isinstance. '
      'No imports, nested functions, classes, annotations, defaults, exceptions, files, network, solve/helper calls or dynamic calls. Return one int, including0 for empty input. '
      'Previous rejected code is not included and must not be copied. Return only the complete undecorated function, no JSON or explanation.')
    protocol=ROOT/'reports/method_redesign_20261109/legal_annual_python_protocol.md'
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
       'experiments/rr_v2_legal_annual_python_control.py','experiments/rr_v2_legal_annual_scope.py','experiments/rr_v2_legal_independent_cache.py',
       'legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py')}
    s={'run_id':RUN,'config':old['config'],'sources':old['sources'],'source':old['source'],
       'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(common,ensure_ascii=False)}],
       'same_source_and_feedback_as_v3_SQL_and_plan':True,'no_native_CASE_or_label_in_prompt':True,
       'ordinary_generic_cache_API_reused_no_new_compatibility_wrapper':True,
       'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
       'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
       'offline':{'source_contract_controls_passed':8,'no_generated_reference_code_sent':True},'goal_complete':False}
    immutable_json(STAGE/'seal.json',s);return s


def main(action):
    s=prepare()
    if action=='prepare':print(json.dumps({'prepared':True,'offline':s['offline'],'new_calls':0}));return
    path=STAGE/'source.json'
    if path.exists():print(json.dumps({'existing':str(path)}));return
    l=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],
      question='Does ordinary Python/PAL implement the local source annual amount scope with the exact same source and feedback, where raw SQL and richer plans failed? One finite strong control, no new native task or labels.')
    e=MethodExecutor(l,STAGE,s['config']['executor']);e.readiness()
    w=e.generate(RUN+':source',source=s['source'],purpose='method_train_synthesis',messages=s['messages'],thinking=False,schema=None)
    result={'physical_response':w,'goal_complete':False}
    try:
        code=w['content'].strip()
        if code.startswith('```'):
            lines=code.splitlines()
            if lines[0] not in ['```','```python'] or lines[-1]!='```':raise ValueError('Incomplete outer fence')
            code='\n'.join(lines[1:-1])
        result.update(code=code,source_checks=checks(code),status='source_checked_ordinary_python')
    except Exception as exc:result.update(status='rejected',error_type=type(exc).__name__,error=str(exc))
    immutable_json(path,result)
    print(json.dumps({k:v for k,v in result.items() if k!='physical_response'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','source']);main(p.parse_args().action)
