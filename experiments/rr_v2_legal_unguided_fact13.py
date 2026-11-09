"""One matched no-schema transport control, not a prompt/model scan."""
import argparse
import hashlib
import json
from pathlib import Path

from experiments.rr_v2_legal_temporal13 import ROOT, frame_errors, grounding_regressions, read
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger

RUN='legal_temporal13_unguided_v1_20261110'
STAGE=ROOT/'artifacts/rr_method_redesign_20261109'/RUN
MATCH=ROOT/'artifacts/rr_method_redesign_20261109/legal_temporal13_v2_20261110'


def value_shape(value,schema):
    if schema['type']=='object':
        assert type(value) is dict and set(value)==set(schema['required'])
        for k,v in value.items():value_shape(v,schema['properties'][k])
    elif schema['type']=='array':
        assert type(value) is list
        for v in value:value_shape(v,schema['items'])
    else:
        assert type(value) is {'string':str,'integer':int,'boolean':bool}[schema['type']]
        if 'enum' in schema:assert value in schema['enum']


def prepare():
    original=read(MATCH/'seal.json')
    bad=read(MATCH/'facts.json')['value'];value_shape(bad,original['reader_schema'])
    assert len(frame_errors(bad,original['case']['public']['facts']))==2
    regressions=grounding_regressions();assert regressions['passed']==5
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
        'experiments/rr_v2_legal_unguided_fact13.py','experiments/rr_v2_legal_temporal13.py',
        'legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py')}
    protocol=ROOT/'reports/method_redesign_20261109/legal_unguided_fact13_protocol.md'
    s={'run_id':RUN,'config':original['config'],'sources':original['sources'],'case':original['case'],
       'messages':original['reader_messages'],'messages_byte_content_unchanged_from_guided_feedback':True,
       'reader_schema_not_sent':original['reader_schema'],'response_schema':None,
       'binding':{'code_hash':digest(files),'config_hash':digest(original['config'])},'files':files,
       'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'offline':regressions,
       'only_generation_interface_change':'Remove response_format guided JSON; messages, thinking, model and sampling unchanged',
       'goal_complete':False}
    immutable_json(STAGE/'seal.json',s);return s


def main(action):
    s=prepare()
    if action=='prepare':print(json.dumps({'prepared':True,'offline':s['offline'],'new_calls':0}));return
    out=STAGE/'facts.json'
    if out.exists():print(json.dumps({'existing':str(out)}));return
    l=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],
        question='Does removing guided JSON alone fix the actual TRAIN13 feedback reader errors? Exactly the same already-failed feedback messages, fixed OFF/model/sampling and source; no repeated identical dispatch.')
    e=MethodExecutor(l,STAGE,s['config']['executor']);e.readiness()
    w=e.generate(RUN+':facts',source=s['case']['key'],purpose='method_primitive_observation',messages=s['messages'],thinking=False,schema=None)
    result={'physical_response':w,'goal_complete':False}
    try:
        text=w['content'].strip()
        if text.startswith('```'):
            lines=text.splitlines()
            if lines[0] not in ['```','```json'] or lines[-1]!='```':raise ValueError('Incomplete/extra fence')
            text='\n'.join(lines[1:-1])
        value=json.loads(text);value_shape(value,s['reader_schema_not_sent'])
        errors=frame_errors(value,s['case']['public']['facts'])
        result.update(value=value,schema_valid=True,semantic_errors=errors,status='grounding_rejected' if errors else 'source_grounded')
    except Exception as exc:result.update(status='parse_or_shape_rejected',error_type=type(exc).__name__,error=str(exc))
    immutable_json(out,result)
    print(json.dumps({k:v for k,v in result.items() if k!='physical_response'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','facts']);main(p.parse_args().action)
