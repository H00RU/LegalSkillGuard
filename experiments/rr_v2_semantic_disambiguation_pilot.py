"""Finite TRAIN acquisition using the existing ledger and clients."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor,MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import FRAME_SCHEMA,READER_SCHEMA,obj,decode_frame,decode_reader,exact_edit

ROOT=Path(__file__).resolve().parents[1]
RUN='semantic_disambiguation_acquisition_v1_20261109'
STAGE=ROOT/'artifacts/rr_method_redesign_20261109'/RUN
OLD=ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109'
STRING={'type':'string'}
TEACHER_SCHEMA=obj({'cases':{'type':'array','items':obj({'case_id':STRING,'frame':FRAME_SCHEMA,
    'local_relation_review':STRING,'edit_valid_for_local_roles':{'type':'boolean'},'edit_review':STRING})},
    'discrimination_questions':{'type':'array','items':STRING},'unresolved':{'type':'array','items':STRING}})


def prepare():
    old=json.loads((OLD/'seal.json').read_text())
    public={s['key']:s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']}
    groups={'OpenExempt':[1,6,11,16],'RuleArena_Airline':[2,7,12,17],'ProofWriter_OWA_depth5':[4,9,14,19],
            'ContractNLI':[5,10,15,20],'SARA_v2_Binary':[71,79,83,88]}
    pool=[]
    for dataset,ordinals in groups.items():
        for i,ordinal in enumerate(ordinals):
            key=old['sources']['train'][ordinal-1];assert public[key]['dataset']==dataset
            pool.append(dict(source=key,ordinal=ordinal,dataset=dataset,fold='induction' if i<2 else 'excluded'))
    edits={71:('agricultural labor','domestic service'),79:('wages of $3200','wages of $3200 in hay'),
           83:('paid $3200','paid $3200 in hay'),88:('wages of $6771 to Bob','wages of $6771 in hay to Bob')}
    cases=[]
    for row in pool:
        if row['dataset']!='SARA_v2_Binary':continue
        s=public[row['source']];text=s['public']['facts']
        common={**row,'original_query':s['public']['query'],'focus':{'payer':'Alice','payee':'Bob'},'family':'work_activity_payment_medium'}
        cases.append({**common,'case_id':f'TRAIN{row["ordinal"]}:original','facts':text,'variant':'original','edit':None})
        changed,receipt=exact_edit(text,*edits[row['ordinal']])
        cases.append({**common,'case_id':f'TRAIN{row["ordinal"]}:controlled','facts':changed,'variant':'controlled','edit':receipt})
    paths=['experiments/rr_v2_semantic_disambiguation_pilot.py','legal_skill_guard/rr/semantic_frames.py',
        'legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/client.py','legal_skill_guard/rr/method_ledger.py',
        'legal_skill_guard/rr/ledger.py','legal_skill_guard/rr/coverage.py','legal_skill_guard/rr/checkpoint.py',
        'legal_skill_guard/inference/codex_cli_client.py']
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    protocol=ROOT/'reports/method_redesign_20261109/M1_M2_pilot_protocol.md'
    seal=dict(run_id=RUN,files=files,binding=dict(code_hash=digest(files),config_hash=digest(old['config'])),
        config=old['config'],sources=old['sources'],source_pool=pool,cases=cases,
        public_TRAIN_packet_sha256=hashlib.sha256((ROOT/'data/packets/rr_v2/public_train.json').read_bytes()).hexdigest(),
        protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest(),
        fixed_external_design_main_commit='5368150eceece401ee475370cc6b8170ca6584bf',
        TEST_authorized=False,goal_complete=False)
    immutable_json(STAGE/'seal.json',seal)
    return seal


def messages(case,mode,materials=None):
    if mode=='direct':
        system=('Extract a light source-grounded event frame for the specified payer/payee. '
            'Use exact short substrings of facts for the four text fields; null if not stated or not identifiable. '
            'Classify the paid work and payment material separately as agricultural/nonagricultural only when supported; null means unknown. '
            'A money amount alone does not identify the payment material. Do not infer false from absence. '
            'No final legal answer or code. Return the schema object.')
    else:
        system=('Answer two local source questions for the specified payer/payee: '
            '(1) Is the remuneration for agricultural labor? '
            '(2) Is the payment made using agricultural products? '
            'Return true/false only when supported, otherwise null. Give exact fact substrings as evidence, or null. '
            'Do not answer the full legal task. Return the schema object.')
    content={'facts':case['facts'],'focus':case['focus']}
    if materials is not None:
        content['training_error_and_verified_relation_materials']=materials
    return [{'role':'system','content':system},{'role':'user','content':json.dumps(content,ensure_ascii=False)}]


def clients(seal):
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        binding=seal['binding'],sources=seal['sources'],authorization_hash=seal['protocol_sha256'],
        question='Can learned discrimination programs and structural reader-error channels outperform direct roles, correct policy cache, same-material repair retrieval and equal-information error models on excluded TRAIN mothers? Controlled variants remain grouped.')
    return MethodExecutor(ledger,STAGE,seal['config']['executor']),MethodTeacher(ledger,STAGE,seal['config']['teacher'])


def run_case(seal,case,mode):
    if case['fold']=='excluded':
        assert (STAGE/'frozen_learning.json').exists(),'Freeze M1/M2 and strong controls before excluded-source calls'
        assert (STAGE/'blind_predictions.json').exists(),'Save conditional joint forecasts before any excluded reader answers'
    executor,_=clients(seal);path=STAGE/'responses'/mode/(digest(case['case_id'])+'.json')
    if path.exists():print(json.dumps({'existing':str(path)}));return
    materials=None
    if mode=='retrieval':
        materials=json.loads((STAGE/'frozen_learning.json').read_text())['retrieval_materials']
    schema=FRAME_SCHEMA if mode=='direct' else READER_SCHEMA
    executor.readiness()
    wire=executor.generate(RUN+':'+mode+':'+case['case_id'],source=case['source'],purpose='method_train_synthesis',
        messages=messages(case,mode,materials),schema=schema,thinking=False)
    try:
        value=json.loads(wire['content']);decoded=(decode_frame if mode=='direct' else decode_reader)(value,case['facts'])
        validation={'status':'decoded','decoded':decoded}
    except Exception as exc:validation={'status':'rejected','error_type':type(exc).__name__,'error':str(exc)}
    immutable_json(path,dict(case_id=case['case_id'],source=case['source'],fold=case['fold'],mode=mode,
        physical_response=wire,validation=validation,captured_utc=datetime.now(timezone.utc).isoformat(),
        semantic_truth_not_inferred_from_span_membership=True))
    print(json.dumps({'case':case['case_id'],'mode':mode,'validation':validation},ensure_ascii=False),flush=True)


def teacher_mother(seal,source):
    cases=[c for c in seal['cases'] if c['source']==source]
    assert cases
    if cases[0]['fold']=='excluded':
        assert (STAGE/'execution_closed_before_grading.json').exists(),'No excluded-source teacher information before predictions and arm outputs close'
    path=STAGE/'teacher'/(digest(source)+'.json')
    if path.exists():print(json.dumps({'existing':str(path)}));return
    _,teacher=clients(seal)
    payload={'cases':cases,'task':'Review only the local payer/payee, paid activity and payment material. Do not solve the native legal question.'}
    if cases[0]['fold']=='induction':
        payload['actual_training_reader_outputs']=[]
        for c in cases:
            for mode in ('direct','reader'):
                p=STAGE/'responses'/mode/(digest(c['case_id'])+'.json');assert p.exists()
                d=json.loads(p.read_text());payload['actual_training_reader_outputs'].append(dict(case_id=c['case_id'],mode=mode,content=d['physical_response']['content']))
    system=('Independently verify the local source relations and any controlled one-span edit. '
        'Return exact short source substrings for payer, payee, work_activity and payment_medium; null when not stated. '
        'Classifications are Boolean or unknown, not inferred from another role or a final legal label. '
        'A dollar amount alone is not evidence of cash or a particular payment material. '
        'Explain any error/ambiguity and whether each edit is valid for local relation evaluation; its full statutory/native label is not being evaluated. '
        'Propose at most two concise source questions that distinguish the actual conflicting work/material interpretations. '
        'Use {payer}/{payee} placeholders, never memorize Alice, Bob, money or the final answer. Return only the schema object.')
    wire=teacher.summarize(RUN+':teacher:'+str(cases[0]['ordinal']),source_ids=[source],system_prompt=system,
        user_prompt=json.dumps(payload,ensure_ascii=False),output_schema=TEACHER_SCHEMA)
    value=wire['value'];assert {r['case_id'] for r in value['cases']}=={c['case_id'] for c in cases}
    validation=[]
    for row in value['cases']:
        case=next(c for c in cases if c['case_id']==row['case_id'])
        try:decoded=decode_frame(row['frame'],case['facts']);validation.append({'case_id':row['case_id'],'status':'decoded','decoded':decoded})
        except Exception as exc:validation.append({'case_id':row['case_id'],'status':'rejected','error':str(exc)})
    immutable_json(path,dict(source=source,fold=cases[0]['fold'],value=value,validation=validation,
        physical_response=wire,captured_utc=datetime.now(timezone.utc).isoformat(),
        evidence_type='TRAIN teacher local relation judgment; not automatic semantic truth'))
    print(json.dumps({'teacher_source':source,'validation':validation},ensure_ascii=False),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','direct','reader','retrieval','teacher'])
    p.add_argument('--case');p.add_argument('--ordinal',type=int);args=p.parse_args();seal=prepare()
    if args.action=='prepare':
        print(json.dumps({'pool_mothers':len(seal['source_pool']),'current_phase_mothers':4,'cases':len(seal['cases']),'new_calls':0}));return
    if args.action=='teacher':
        if args.ordinal is None:p.error('--ordinal required for a teacher mother')
        key=seal['sources']['train'][args.ordinal-1];teacher_mother(seal,key)
    else:
        if not args.case:p.error('--case required; inspect each physical result before the next dispatch')
        case=next(c for c in seal['cases'] if c['case_id']==args.case);run_case(seal,case,args.action)


if __name__=='__main__':main()
