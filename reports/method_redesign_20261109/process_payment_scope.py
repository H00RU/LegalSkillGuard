"""Unambiguous null-sentinel rendering, independent TRAIN review and execution.

The raw generation/validation and frozen generation files remain unchanged.
"""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.payment_scope import EVENT_SCHEMA,decode_payments,scope_sum
from legal_skill_guard.rr.source_discrimination import execute_paths
from experiments.rr_v2_payment_scope_pilot import ROOT,STAGE,RUN,REVIEW_SCHEMA,prepare,clients,read


def render_null_sentinels(value,text):
    output=copy.deepcopy(value);conversions=[]
    for i,event in enumerate(output['events']):
        for field,schema in EVENT_SCHEMA['properties'].items():
            nullable=any(s.get('type')=='null' for s in schema.get('anyOf',[]))
            if nullable and event[field]=='null' and 'null' not in text:
                event[field]=None;conversions.append({'path':['events',i,field],
                    'from':'literal string null','to':'JSON null',
                    'basis':'Schema permits unknown; original facts contain no competing literal null span'})
    return output,conversions


def process(s):
    raw=read(STAGE/'executor.json');value=json.loads(raw['physical_response']['content'])
    normalized,conversions=render_null_sentinels(value,s['case']['facts'])
    decoded=decode_payments(normalized,s['case']['facts'])
    record={'captured_utc':datetime.now(timezone.utc).isoformat(),
            'original_executor_sha256':hashlib.sha256((STAGE/'executor.json').read_bytes()).hexdigest(),
            'generation_seal_sha256':hashlib.sha256((STAGE/'seal.json').read_bytes()).hexdigest(),
            'processor_sha256':hashlib.sha256(open(__file__,'rb').read()).hexdigest(),
            'conversions':conversions,'normalized_value':normalized,'decoded':decoded,
            'original_response_unchanged':True,'semantic_facts_added':False,'new_calls':0}
    immutable_json(STAGE/'processed_executor.json',record)
    print(json.dumps({'events':len(decoded['events']),'conversions':conversions,'new_calls':0}))


def review(s):
    processed=read(STAGE/'processed_executor.json');path=STAGE/'teacher_processed.json'
    if path.exists():print(json.dumps({'existing':str(path)}));return
    _,teacher=clients(s)
    wire=teacher.summarize(RUN+':review_processed:TRAIN88',source_ids=[s['source']],
        system_prompt='Independently list every explicitly stated payment event from these TRAIN facts, then review the executor rows for payer/payee, amount, shared work scope, payment material and service period. Use exact short substrings and full supporting sentence. Do not solve the legal question or use final labels. Distinguish service dates from payment dates; flag missing temporal information rather than inventing it. Check all coordinated recipients and the reverse payment.',
        user_prompt=json.dumps({'facts':s['case']['facts'],'executor_proposal':processed['normalized_value']},ensure_ascii=False),
        output_schema=REVIEW_SCHEMA)
    immutable_json(path,{'physical_response':wire,'captured_utc':datetime.now(timezone.utc).isoformat(),
                        'evidence_type':'TRAIN teacher local relation judgment; not automatically true'})
    print(json.dumps(wire['value'],ensure_ascii=False))


def execute(s):
    processed=read(STAGE/'processed_executor.json');review=read(STAGE/'teacher_processed.json')['physical_response']['value']
    teacher_decoded=decode_payments({'events':review['independent_events']},s['case']['facts'])
    def classify(v):return execute_paths(s['learned_paths'],[{'values':v}])[0]
    control=scope_sum(processed['decoded'],payer='Alice',kind='wages',work_classify=classify,
                      threshold=s['threshold_span'][1:].replace(',',''))
    control['source_review']={'type':'Independent TRAIN teacher relation/completeness judgment, inspected against source',
        'all_executor_rows_supported':all(r['all_role_relations_supported'] for r in review['executor_event_reviews']),
        'teacher_completeness_supported':review['executor_event_completeness_supported'],
        'teacher_event_count':len(teacher_decoded['events']),
        'payment_year_explicit':review['payment_year_is_explicit_for_every_event'],'period_review':review['period_review']}
    control.update({'evidence_type':'Real model event IR plus learned local source classes and ordinary arithmetic control',
                    'new_core_method_success_claimed':False,'model_rule_program_generated':False,
                    'original_response_was_not_rewritten':True,'goal_complete':False})
    immutable_json(STAGE/'processed_execution.json',control);print(json.dumps(control,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['process','review','execute']);a=p.parse_args();globals()[a.action](prepare())
