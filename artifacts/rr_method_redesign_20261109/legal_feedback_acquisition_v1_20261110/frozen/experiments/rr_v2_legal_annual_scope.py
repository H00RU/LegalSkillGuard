"""Finite source3306(b)(1) aggregation-scope pilot with an ordinary SQL control.

This is local annual-cap semantics over already admitted remuneration candidates,
not a complete3306(a)(2)(A) predictor. The paid dates in the diagnostic runtime
come from the explicitly charged TRAIN annotation, not a repaired model reader.
"""
import argparse
from copy import deepcopy
import hashlib,json,re,sqlite3
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import obj

ROOT=Path(__file__).resolve().parents[1]
RUN='legal_annual_scope_v3_20261110'
PREVIOUS=ROOT/'artifacts/rr_method_redesign_20261109/legal_annual_scope_v1_20261110'
STAGE=ROOT/'artifacts/rr_method_redesign_20261109'/RUN
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
OLD=BASE/'redesign_source_roles_v1_20261109/seal.json'
FIELDS=['payment_id','payer','payee','payment_year','service_id']


def read(p):return json.loads(p.read_text())


def reference(payments,qualifications):
    admitted={r[0] for r in qualifications};groups={}
    for payment_id,payer,payee,year,service_id,amount in payments:
        if payment_id in admitted:groups[payer,payee,year]=groups.get((payer,payee,year),0)+amount
    return sum(min(7000,amount) for amount in groups.values())


def sql_value(sql,payments,qualifications):
    # Standard SQL engine shared by the source-generated query and plan compiler.
    # The model has no filesystem/database connection and no generated Python runs.
    c=sqlite3.connect(':memory:')
    try:
        # Admission/physical identity is a common deterministic input adapter,
        # not a learned legal mechanism. Both generated representations see it.
        c.execute('CREATE TABLE admitted_payments(payment_id TEXT PRIMARY KEY,payer TEXT,payee TEXT,payment_year INTEGER,service_id TEXT,amount INTEGER)')
        ids={r[0] for r in qualifications}
        c.executemany('INSERT INTO admitted_payments VALUES(?,?,?,?,?,?)',[p for p in payments if p[0] in ids])
        def auth(op,a,b,db,trigger):
            if op in {sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ}:return sqlite3.SQLITE_OK
            if op==sqlite3.SQLITE_FUNCTION and str(b).lower() in {'sum','min','max','coalesce','count'}:return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        c.set_authorizer(auth)
        steps=[0]
        def progress():
            steps[0]+=1;return int(steps[0]>10000)
        c.set_progress_handler(progress,100)
        rows=c.execute(sql).fetchall()
        if len(rows)!=1 or len(rows[0])!=1 or type(rows[0][0]) is not int:raise ValueError('Return exactly one nonnull integer total')
        return rows[0][0]
    finally:c.close()


def plan_sql(plan):
    if set(plan)!={'scope_keys','threshold','adjustment'}:raise ValueError('Plan fields differ')
    keys=plan['scope_keys']
    if len(set(keys))!=len(keys) or any(k not in FIELDS for k in keys):raise ValueError('Unknown/duplicate scope key')
    if type(plan['threshold']) is not int or plan['threshold']<0:raise ValueError('A nonnegative integer threshold required')
    threshold=str(plan['threshold']);op=plan['adjustment']
    total='SUM(amount)'
    if op=='cap':value=f'MIN({threshold},{total})'
    elif op=='exclude_scope_at_least':value=f'CASE WHEN {total} >= {threshold} THEN 0 ELSE {total} END'
    elif op=='exclude_scope_above':value=f'CASE WHEN {total} > {threshold} THEN 0 ELSE {total} END'
    elif op=='include_all':value=total
    else:raise ValueError('Unknown local amount adjustment')
    if not keys:return f'SELECT COALESCE({value},0) FROM admitted_payments'
    return f'WITH grouped AS (SELECT {value} AS value FROM admitted_payments GROUP BY '+','.join(keys)+') SELECT COALESCE(SUM(value),0) FROM grouped'



def probes():
    def row(i,amount,payer='P',payee='Q',year=2017,service='S'):return [i,payer,payee,year,service,amount]
    rows=[('empty',[],[]),
      ('annual_same_person_two_payments',[row('a',6771),row('b',6954)],[['a','w1'],['b','w2']]),
      ('different_payers',[row('a',7000),row('b',7000,payer='R')],[['a','w1'],['b','w2']]),
      ('different_payees',[row('a',6771),row('b',6771,payee='R')],[['a','w1'],['b','w2']]),
      ('different_payment_years',[row('a',7000),row('b',7000,year=2018)],[['a','w1'],['b','w2']]),
      ('same_annual_key_different_services',[row('a',6771),row('b',6954,service='T')],[['a','w1'],['b','w2']]),
      ('same_payment_multiple_witnesses',[row('a',1000)],[['a','w1'],['a','w2'],['a','w3']]),
      ('unqualified_payment_not_counted',[row('a',1000),row('b',5000)],[['a','w1']])]
    return [{'name':n,'payments':p,'qualifications':q,'expected':reference(p,q)} for n,p,q in rows]


def check(sql):
    out=[]
    for p in probes():
        try:value=sql_value(sql,p['payments'],p['qualifications']);passed=value==p['expected'];error=None
        except Exception as exc:value=None;passed=False;error=type(exc).__name__+': '+str(exc)
        out.append({'name':p['name'],'expected':p['expected'],'actual':value,'passed':passed,'error':error})
    return {'rows':out,'all_passed':all(r['passed'] for r in out),'source_contract_probes_not_new_native_examples':True,
            'finite_probe_pass_not_full_NL_fidelity_certificate':True}


def offline():
    valid={'scope_keys':['payer','payee','payment_year'],'threshold':7000,'adjustment':'cap'}
    assert check(plan_sql(valid))['all_passed']
    assert not check(plan_sql(valid|{'scope_keys':['payment_id']}))['all_passed']
    assert not check(plan_sql(valid|{'adjustment':'exclude_scope_at_least'}))['all_passed']
    assert check(plan_sql(valid|{'scope_keys':['payment_id']}))['rows'][1]['actual']==13725
    assert check(plan_sql(valid))['rows'][1]['actual']==7000
    for old_shape in [valid|{'cap_application':'each_payment'}, {'cap_scope_keys':[],'annual_limit':7000,'eligibility_use':'exists'}]:
        try:plan_sql(old_shape)
        except ValueError:pass
        else:raise AssertionError('Old/contradictory shapes must not be silently adapted')
    return {'passed':7,'source_annual_scope_countermodel_verified':True,
            'cap_and_whole_scope_exclusion_both_expressible':True,
            'payment_admission_identity_preprocessing_shared_not_new_contribution':True,
            'no_rejected_code_anchoring_in_new_prompts':True,'model_calls':0}



def prepare():
    old=read(OLD);source=old['sources']['train'][87]
    case=next(r for r in read(ROOT/'data/packets/rr_v2/public_train.json')['sources'] if r['key']==source)
    policy=case['public']['rules'];a=policy.index('(b) Wages');b=policy.index('(2)',a)
    excerpt=policy[a:b]
    assert '$7,000' in excerpt and 'calendar year' in excerpt
    operations={
        'cap':'Group by the chosen scope keys, sum amount inside each group, include min(threshold,group sum), then sum included amounts.',
        'exclude_scope_at_least':'Group by the chosen scope keys; include0 for a group whose sum>=threshold, otherwise include its whole sum; sum the included values.',
        'exclude_scope_above':'Same whole-group exclusion with > instead of >=.',
        'include_all':'Include each group total without applying the threshold.'}
    common={'source_clause':excerpt,
        'local_scope':'Compute the local amount inclusion specified by3306(b)(1). Other statutory exclusions are outside this component. No complete3306 predictor is requested.',
        'input_relation':{'admitted_payments':{
          'columns':['payment_id TEXT PRIMARY KEY','payer TEXT','payee TEXT','payment_year INTEGER','service_id TEXT','amount INTEGER'],
          'meaning':'Each row is one physical direct payment of nonnegative gross remuneration by the payer/employer to the payee/individual in payment_year. An ordinary input adapter admits it when any supplied candidate-admission witness exists and emits it once. Different payment IDs remain different payments even when amounts coincide. This shared adapter is given to both controls, not learned from the law.'}},
        'scope_and_operation_language_identical_for_SQL_and_plan':operations,
        'scope_semantics':'Each distinct tuple of selected keys is one scope. payment_id in the keys permits per-payment scopes; an empty key list is one global scope. Choose the legal keys and operation from the source, not from a fixed expected answer.',
        'source_contract_counterexamples':[{'name':p['name'],'admitted_payments':[r for r in p['payments'] if r[0] in {q[0] for q in p['qualifications']}],'source_required_total':p['expected']} for p in probes()],
        'repair_context':'Previous candidates were rejected. Do NOT copy a previous programme or treat rejected examples as authoritative. The rejected code is intentionally not included here. Re-derive the operation and scope from the source and the shared source-contract examples.',
        'requested_output':'One integer total; empty input gives0. No original native case facts/query/label, annotated runtime records or reference SQL are supplied. Source-contract examples are explicit shared training feedback, not a native evaluation set.'}
    schema=obj({'scope_keys':{'type':'array','items':{'type':'string','enum':FIELDS},'minItems':0,'maxItems':5},
        'threshold':{'type':'integer'},'adjustment':{'type':'string','enum':list(operations)}})
    instructions={
      'sql':'Repair the previously rejected local-source implementation from scratch. The source and shared source-contract examples are authoritative; an earlier programme is not. Return one ordinary SQLite SELECT/WITH query over admitted_payments, producing one nonnull integer total, no JSON or explanation. Use GROUP BY/EXISTS/SUM/MIN/MAX/CASE/COALESCE as needed. The shared operation and scope definitions are identical to those given to the plan control; infer the correct legal operation, threshold and keys yourself. Do not exclude a whole payment merely by copying an old implementation. No hardcoded people, event IDs or case answers.',
      'plan':'Repair the previously rejected local-source implementation from scratch. Infer the correct operation, threshold and scope keys from the source and shared source-contract examples. Return only the schema. All operation meanings and the input adapter are identical to those given to ordinary SQL. No raw source quote, duplicate cap-order field, hardcoded people, event IDs or native answers.'}
    protocol=ROOT/'reports/method_redesign_20261109/legal_annual_scope_protocol.md'
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
      'experiments/rr_v2_legal_annual_scope.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py')}
    off=offline()
    s={'run_id':RUN,'config':old['config'],'sources':old['sources'],'source':source,'source_excerpt':excerpt,
       'messages':{k:[{'role':'system','content':v},{'role':'user','content':json.dumps(common,ensure_ascii=False)}] for k,v in instructions.items()},
       'plan_schema':schema,'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
       'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'offline':off,
       'common_source_and_relation_contract_identical':True,'source_compilation_sees_no_original_native_cases_or_native_labels':True,'shared_source_contract_examples_in_prompt':True,
       'scope_key_and_identity_operator_choices_not_fixed_to_correct_values':True,
       'source_provenance_attached_deterministically':{'source_sha256':hashlib.sha256(policy.encode()).hexdigest(),'span':[a,b]},
       'same_source_contract_feedback_shared_with_both_arms':True,'rejected_model_code_not_in_prompts':True,'goal_complete':False}
    immutable_json(STAGE/'seal.json',s);return s


def main(action):
    s=prepare()
    if action=='prepare':print(json.dumps({'prepared':True,'offline':s['offline'],'model_calls':0}));return
    path=STAGE/(action+'.json')
    if path.exists():print(json.dumps({'existing':str(path)}));return
    l=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],
      question='Can a source-generated aggregation plan correctly infer annual legal amount scope and physical-payment identity, beyond an ordinary SQL source compiler with the same information? A finite local source-only test, not a full new build or claimed two contributions.')
    e=MethodExecutor(l,STAGE,s['config']['executor']);e.readiness()
    w=e.generate(RUN+':'+action,source=s['source'],purpose='method_train_synthesis',messages=s['messages'][action],thinking=False,schema=s['plan_schema'] if action=='plan' else None)
    result={'physical_response':w,'goal_complete':False}
    try:
      if action=='plan':
        plan=json.loads(w['content']);sql=plan_sql(plan);result['plan']=plan
        result['source_provenance']=s['source_provenance_attached_deterministically']
      else:
        sql=w['content'].strip()
        if sql.startswith('```'):
          lines=sql.splitlines()
          if lines[0] not in ['```','```sql'] or lines[-1]!='```':raise ValueError('Incomplete/extra fence')
          sql='\n'.join(lines[1:-1])
      result.update(sql=sql,source_checks=check(sql),status='source_checked_local_module')
    except Exception as exc:result.update(status='rejected',error_type=type(exc).__name__,error=str(exc))
    immutable_json(path,result)
    print(json.dumps({k:v for k,v in result.items() if k!='physical_response'},ensure_ascii=False,indent=2))


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','sql','plan']);main(p.parse_args().action)
