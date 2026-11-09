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
RUN='legal_annual_scope_v2_20261110'
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
        c.execute('CREATE TABLE payments(payment_id TEXT PRIMARY KEY,payer TEXT,payee TEXT,payment_year INTEGER,service_id TEXT,amount INTEGER)')
        c.execute('CREATE TABLE qualifications(payment_id TEXT,witness_id TEXT)')
        c.executemany('INSERT INTO payments VALUES(?,?,?,?,?,?)',payments)
        c.executemany('INSERT INTO qualifications VALUES(?,?)',qualifications)
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
    if set(plan)!={'cap_scope_keys','annual_limit','eligibility_use'}:raise ValueError('Plan fields differ')
    keys=plan['cap_scope_keys']
    if len(set(keys))!=len(keys) or any(k not in FIELDS for k in keys):raise ValueError('Unknown/duplicate scope key')
    if type(plan['annual_limit']) is not int or plan['annual_limit']<0:raise ValueError('A nonnegative integer limit required')
    limit=str(plan['annual_limit'])
    mode=plan['eligibility_use']
    if mode=='exists':base='SELECT p.* FROM payments p WHERE EXISTS (SELECT 1 FROM qualifications q WHERE q.payment_id=p.payment_id)'
    elif mode=='join':base='SELECT p.* FROM payments p JOIN qualifications q ON q.payment_id=p.payment_id'
    elif mode=='ignore':base='SELECT p.* FROM payments p'
    else:raise ValueError('Unknown eligibility operator')
    # The scope of the cap is represented exactly once. A per-payment cap is
    # expressible by payment_id; a global cap uses an empty key set. No second
    # field can silently bypass the declared scope.
    if not keys:return f'WITH eligible AS ({base}) SELECT MIN({limit},COALESCE(SUM(amount),0)) FROM eligible'
    return f'WITH eligible AS ({base}), grouped AS (SELECT MIN({limit},SUM(amount)) AS value FROM eligible GROUP BY '+','.join(keys)+') SELECT COALESCE(SUM(value),0) FROM grouped'



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
    valid={'cap_scope_keys':['payer','payee','payment_year'],'annual_limit':7000,
           'eligibility_use':'exists'}
    assert check(plan_sql(valid))['all_passed']
    bad_key=valid|{'cap_scope_keys':['payment_id']};assert not check(plan_sql(bad_key))['all_passed']
    bad_join=valid|{'eligibility_use':'join'};assert not check(plan_sql(bad_join))['all_passed']
    assert check(plan_sql(bad_key))['rows'][1]['actual']==13725
    assert check(plan_sql(valid))['rows'][1]['actual']==7000
    old_shape=valid|{'cap_application':'each_payment','source_quote':'part3306(b)(1)'}
    try:plan_sql(old_shape)
    except ValueError:pass
    else:raise AssertionError('Old contradictory shape must not be silently adapted')
    return {'passed':6,'source_annual_scope_countermodel_verified':True,
            'independent_failures_key_scope_and_witness_multiplicity':True,
            'ordinary_SQL_EXISTS_GROUP_BY_is_strong_control':True,'model_calls':0}


def prepare():
    old=read(OLD);source=old['sources']['train'][87]
    case=next(r for r in read(ROOT/'data/packets/rr_v2/public_train.json')['sources'] if r['key']==source)
    policy=case['public']['rules'];a=policy.index('(b) Wages');b=policy.index('(2)',a)
    excerpt=policy[a:b]
    assert '$7,000' in excerpt and 'calendar year' in excerpt
    common={'source_clause':excerpt,
        'local_scope':'Compute the total remuneration included by the annual-limit part3306(b)(1) for the supplied relation. Other statutory exclusions are outside this local component; qualifications supplies candidate admission. Do not claim a complete3306 predictor.',
        'input_relations':{
          'payments':{'columns':['payment_id TEXT PRIMARY KEY','payer TEXT','payee TEXT','payment_year INTEGER','service_id TEXT','amount INTEGER'],
                      'meaning':'Each row is one physical payment of nonnegative gross remuneration, directly paid by this payer/employer to this payee/individual in the stated payment calendar year. Different payment IDs are different physical payments even when all other values coincide.'},
          'qualifications':{'columns':['payment_id TEXT','witness_id TEXT'],
                            'meaning':'Each row is a proof witness that the referenced payment is admitted as a candidate for this local component. Several independent proof witnesses may refer to the same physical payment; a missing witness supplies no admission. This is not an additional payment relation.'}},
        'requested_output':'One integer: total remuneration included by the quoted local annual-limit provision across all supplied payments. An empty input must give0. No case facts, native queries, labels, audit examples, reference query or programme are supplied.'}
    schema=obj({'cap_scope_keys':{'type':'array','items':{'type':'string','enum':FIELDS},'minItems':0,'maxItems':5},
        'annual_limit':{'type':'integer'},'eligibility_use':{'type':'string','enum':['exists','join','ignore']}})
    instructions={
      'sql':'Compile the supplied local source provision into one ordinary SQLite SELECT/WITH query over the supplied tables. Return only complete SQL, no JSON, fences, explanation, DDL, DML or imports. You may use standard SELECT, GROUP BY, EXISTS, JOIN, SUM, MIN, MAX, CASE and COALESCE. Preserve source roles and temporal scope. No hardcoded people, events or case answers.',
      'plan':'Compile the supplied local source provision into the supplied aggregation scope plan. Select its scope keys, numeric limit and eligibility operation yourself from the source and relation meanings. For every distinct tuple of scope keys, sum the admitted amounts, include at most the limit and sum the results. A per-payment cap is represented by payment_id in the keys; an empty key list is one global cap. No additional cap-order field exists. exists admits each payment if it has any witness; join retains joined witness multiplicity; ignore includes every payment. Source provenance is attached by the compiler, not generated as a new rule or inferred from a case. Return only the schema; no hardcoded people, events or case answers.'}
    sql_before=read(PREVIOUS/'sql.json');plan_before=read(PREVIOUS/'plan.json')
    common['same_shared_feedback_for_both_arms']={
       'previous_source_generated_SQL':sql_before['sql'],
       'previous_source_generated_plan':json.loads(plan_before['physical_response']['content']),
       'source_counterexamples':[{'name':p['name'],'payments':p['payments'],'qualifications':p['qualifications'],'source_required_total':p['expected']} for p in probes()],
       'repair_context':'The source limits the amount within its legal scope, not all-or-nothing exclusion of a whole payment. A consistent scope plan has one scope binding; numerical semantics of per-payment and global caps are expressible by their own scope key sets. These are source-contract examples, not native task labels.'}
    protocol=ROOT/'reports/method_redesign_20261109/legal_annual_scope_protocol.md'
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
      'experiments/rr_v2_legal_annual_scope.py','legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py')}
    off=offline()
    s={'run_id':RUN,'config':old['config'],'sources':old['sources'],'source':source,'source_excerpt':excerpt,
       'messages':{k:[{'role':'system','content':v},{'role':'user','content':json.dumps(common,ensure_ascii=False)}] for k,v in instructions.items()},
       'plan_schema':schema,'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
       'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'offline':off,
       'common_source_and_relation_contract_identical':True,'source_compilation_sees_no_cases_or_labels':True,
       'scope_key_and_identity_operator_choices_not_fixed_to_correct_values':True,
       'source_provenance_attached_deterministically':{'source_sha256':hashlib.sha256(policy.encode()).hexdigest(),'span':[a,b]},
       'same_two_original_model_outputs_and_feedback_shared_with_both_arms':True,'goal_complete':False}
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
