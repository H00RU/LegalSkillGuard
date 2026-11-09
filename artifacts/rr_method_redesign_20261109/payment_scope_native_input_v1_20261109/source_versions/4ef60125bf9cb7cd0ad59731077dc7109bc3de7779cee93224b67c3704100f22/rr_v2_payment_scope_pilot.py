"""Single existing-TRAIN source gap, same clients/ledger, no new dataset."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor,MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.payment_scope import PAYMENT_SCHEMA,decode_payments,scope_sum
from legal_skill_guard.rr.semantic_frames import obj
from legal_skill_guard.rr.source_discrimination import execute_paths

ROOT=Path(__file__).resolve().parents[1]
RUN='payment_scope_native_input_v1_20261109'
STAGE=ROOT/'artifacts/rr_method_redesign_20261109'/RUN
REPORT=ROOT/'reports/method_redesign_20261109'
REVIEW_SCHEMA=obj({'independent_events':PAYMENT_SCHEMA['properties']['events'],
    'executor_event_reviews':{'type':'array','items':obj({'event_index':{'type':'integer'},
        'all_role_relations_supported':{'type':'boolean'},'review':{'type':'string'}})},
    'executor_event_completeness_supported':{'type':'boolean'},
    'payment_year_is_explicit_for_every_event':{'type':'boolean'},
    'period_review':{'type':'string'},'unresolved':{'type':'array','items':{'type':'string'}}})


def read(p):return json.loads(p.read_text())


def prepare():
    base=read(ROOT/'artifacts/rr_method_redesign_20261109/semantic_disambiguation_acquisition_v1_20261109/seal.json')
    case=next(c for c in base['cases'] if c['case_id']=='TRAIN88:original')
    public={s['key']:s for s in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    rules=public[case['source']]['public']['rules']
    a=rules.index('(2) Agricultural labor');b=rules.index('(3) Domestic service',a)
    excerpt=rules[a:b];thresholds=__import__('re').findall(r'\$[0-9,]+',excerpt);assert thresholds==['$20,000']
    paths=['experiments/rr_v2_payment_scope_pilot.py','legal_skill_guard/rr/payment_scope.py',
        'legal_skill_guard/rr/source_discrimination.py','legal_skill_guard/rr/semantic_frames.py',
        'legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/client.py','legal_skill_guard/rr/method_ledger.py']
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    protocol=ROOT/'reports/method_redesign_20261109/payment_scope_protocol.md'
    seal={'run_id':RUN,'case':case,'source':case['source'],'config':base['config'],'sources':base['sources'],
          'files':files,'binding':{'code_hash':digest(files),'config_hash':digest(base['config'])},
          'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
          'source_policy_excerpt':excerpt,'threshold_span':thresholds[0],
          'threshold_control':'Read exact 20000 from this supplied clause; >= is the human-implemented ordinary reference control, not a learned mechanism',
          'learned_paths':read(REPORT/'M1_learned_dependency_results.json')['learned_skill']['learned_evidence_paths'],
          'native_answer_not_claimed':True,'TEST_authorized':False,'goal_complete':False}
    immutable_json(STAGE/'seal.json',seal);return seal


def clients(s):
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],
        question='Can a compact full payment-event IR recover the original TRAIN88 multi-recipient/reverse-direction source input, without adding legal assumptions or equating local scope execution with method contribution?')
    return MethodExecutor(ledger,STAGE,s['config']['executor']),MethodTeacher(ledger,STAGE,s['config']['teacher'])


def extract(s):
    p=STAGE/'executor.json'
    if p.exists():print(json.dumps({'existing':str(p)}));return
    e,_=clients(s);e.readiness()
    messages=[{'role':'system','content':'Extract all explicitly stated payment relationships. Return one row per payer/payee/payment, including coordinated recipients and reverse-direction events. Use exact short source substrings for role fields and the full exact supporting sentence for event_evidence. Null means unstated. Distinguish the service period from the time of payment; do not infer a payment year. The remuneration_kind is the stated noun such as wages, not a legal conclusion. No final legal answer, code, classification or arithmetic. Return only the schema object.'},
              {'role':'user','content':json.dumps({'facts':s['case']['facts']},ensure_ascii=False)}]
    wire=e.generate(RUN+':extract:TRAIN88',source=s['source'],purpose='method_train_synthesis',
                    messages=messages,schema=PAYMENT_SCHEMA,thinking=False)
    try:validation={'status':'decoded','value':decode_payments(json.loads(wire['content']),s['case']['facts'])}
    except Exception as exc:validation={'status':'rejected','error_type':type(exc).__name__,'error':str(exc)}
    immutable_json(p,{'physical_response':wire,'validation':validation,'captured_utc':datetime.now(timezone.utc).isoformat()})
    print(json.dumps({'validation':validation},ensure_ascii=False))


def review(s):
    p=STAGE/'teacher.json'
    if p.exists():print(json.dumps({'existing':str(p)}));return
    output=read(STAGE/'executor.json');assert output['validation']['status']=='decoded'
    _,t=clients(s)
    wire=t.summarize(RUN+':review:TRAIN88',source_ids=[s['source']],
        system_prompt='Independently list every explicitly stated payment event from these TRAIN facts, then review the executor rows for payer/payee, amount, shared work scope, payment material and service period. Use exact short substrings and full supporting sentence. Do not solve the legal question or use final labels. Distinguish service dates from payment dates; flag missing temporal information rather than inventing it. Check all coordinated recipients and the reverse payment.',
        user_prompt=json.dumps({'facts':s['case']['facts'],'executor_proposal':json.loads(output['physical_response']['content'])},ensure_ascii=False),output_schema=REVIEW_SCHEMA)
    immutable_json(p,{'physical_response':wire,'captured_utc':datetime.now(timezone.utc).isoformat(),
                     'evidence_type':'TRAIN teacher source-relation judgment, not automatically true'})
    print(json.dumps(wire['value'],ensure_ascii=False))


def execute(s):
    d=read(STAGE/'executor.json');assert d['validation']['status']=='decoded'
    def classify(v):return execute_paths(s['learned_paths'],[{'values':v}])[0]
    result=scope_sum(d['validation']['value'],payer='Alice',kind='wages',work_classify=classify,
                     threshold=s['threshold_span'][1:].replace(',',''))
    result.update({'evidence_type':'Actual model event IR with learned local classes and an ordinary source-threshold control; conditional scope execution only',
                   'model_rule_program_generated':False,'new_core_method_success_claimed':False,'goal_complete':False})
    immutable_json(STAGE/'execution.json',result);print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','extract','review','execute']);args=p.parse_args();s=prepare()
    if args.action!='prepare':globals()[args.action](s)
    else:print(json.dumps({'prepared':True,'new_calls':0}))
