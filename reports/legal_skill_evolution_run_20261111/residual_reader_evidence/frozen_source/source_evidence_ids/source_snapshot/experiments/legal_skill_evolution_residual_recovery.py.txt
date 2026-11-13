"""Resume the terminal quote-copy failure with source-ID evidence encoding."""
import base64
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments.legal_skill_evolution_residual_calibration import ROOT,RUN,source_record
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.residual_reader import execute
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.semantic_execution import answer_schema,focused_messages,strict_json
from legal_skill_guard.skill_evolution.semantic_operations import ground_answers,prepare_queries
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units

OUT=ROOT/'artifacts'/RUN
PHASE='source_evidence_ids'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def recovered_observations(ledger,p,public,bundle):
    key=p['calibration_sources'][1];source=public[key];pub=source['views'][0]['public']
    units,_=execution_source_units(pub['source_text'],source_spans(material_public(pub)))
    planned={q['id']:q for q in prepare_queries(bundle['program'],bundle['operations'],pub['source_text'],units)}
    with ledger.transaction() as db:
        rows=db.execute("select id,result,request_hash from calls where source=? and id like ? order by reserved_at",
                        (key,RUN+':calibration:%')).fetchall()
    assert len(rows)==1,'Recover the actual single failed batch, not a chosen response'
    identity,raw_result,h=rows[0];result=json.loads(raw_result)
    request=read(OUT/'calls'/digest(identity)/'request.json');assert request['request_hash']==h
    assert result['request_hash']==h and result['finish_reason']=='stop'
    wire=read(OUT/'calls'/digest(identity)/'wire_request.json');body=base64.b64decode(wire['body_b64'])
    assert hashlib.sha256(body).hexdigest()==wire['body_sha256']
    payload=json.loads(body);assert payload==request['payload']
    content=json.loads(payload['messages'][1]['content']);batch=[]
    for q in content['current_queries']:
        canonical={k:q[k] for k in ['id','operation','unit_ids']};assert canonical==planned[q['id']];batch.append(canonical)
    assert focused_messages(bundle['operations'],batch,units,scope='focus_last')==payload['messages']
    value=strict_json(result['content']);jsonschema.validate(value,answer_schema(bundle['operations'],batch))
    accepted=[];rejected=[]
    for q in batch:
        raw={'id':q['id'],**value['answers'][q['id']]}
        try:accepted.extend(ground_answers(bundle['operations'],[q],units,{'answers':[raw]}))
        except ValueError as e:rejected.append({'id':q['id'],'raw':raw,'error':str(e)})
    assert len(accepted)==6 and len(rejected)==1 and rejected[0]['id']=='sr_1_role'
    immutable_json(OUT/PHASE/'observation_recovery.json',{'source':key,'physical_call_id':identity,
        'request_hash':h,'wire_sha256':wire['body_sha256'],'accepted':accepted,'rejected':rejected,
        'original_bad_quote_not_rewritten':True,'no_semantic_score_filtering':True,
        'all_valid_siblings_including_semantic_mistakes_preserved':True,'new_physical_requests':0})
    return key,accepted


def setup():
    p=read(OUT/'protocol.json');bundle=read(OUT/'seed.json')
    public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    paths=[Path(__file__).resolve(),ROOT/'legal_skill_guard/skill_evolution/residual_reader.py',
        ROOT/'legal_skill_guard/skill_evolution/source_evidence_codec.py',
        ROOT/'tests/test_skill_evolution_residual_reader.py',ROOT/'tests/test_skill_evolution_source_evidence_codec.py']
    protocol={'parent_protocol_sha256':sha(OUT/'protocol.json'),'same_goal':True,'goal_complete':False,
        'source_sha256':{str(q.relative_to(ROOT)):sha(q) for q in paths},'run_id':RUN+':'+PHASE,
        'executor_profile':p['executor_profile'],'train_sources':p['train_sources'],
        'validation_sources':p['validation_sources'],'source_and_operation_meanings_unchanged':True,
        'wire_change':'Required query keys; declared semantic choices; nonunknown needs at least one current support unit ID. Host attaches literal source text. Duplicate/support/window/type checks retained.',
        'no_bad_quote_recovery':'The rejected copied quote is not normalized/promoted; only its query gets a changed-wire real retry. Six independently valid sibling interpretations remain original observations.',
        'no_new_mechanical_call_cap':True}
    immutable_json(OUT/PHASE/'protocol.json',protocol)
    for q in paths:
        dst=OUT/PHASE/'source_snapshot'/q.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert dst.read_bytes()==q.read_bytes()
        else:dst.write_bytes(q.read_bytes())
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=protocol['run_id'],
        sources={'train':p['train_sources']+p['validation_sources'],'dev':[],'test':[]},binding=digest(protocol))
    return p,bundle,public,protocol,ledger


def resume():
    p,bundle,public,protocol,ledger=setup();key,restored=recovered_observations(ledger,p,public,bundle)
    client=FrozenExecutor(ledger,OUT,p['executor_profile']);client.exact_replay_roots=(OUT,)
    for source_key in p['calibration_sources']:
        dst=OUT/'calibration'/(source_key.replace(':','_')+'.json')
        if dst.exists():continue
        source=public[source_key];pub=source['views'][0]['public'];spans=source_spans(material_public(pub))
        units,_=execution_source_units(pub['source_text'],spans)
        def save(event):immutable_json(OUT/PHASE/'events'/(digest(event['call_id'])+'.json'),event)
        r=execute(client,protocol['run_id']+':calibration:'+source_key,source_key,bundle,pub['source_text'],units,
            scope='focus_last',lookup='_sr_get',initial_observations=restored if source_key==key else (),save_event=save)
        row=source_record(bundle,source,r);row['evidence_transport_phase']=PHASE;immutable_json(dst,row)
        print(json.dumps({'source':source_key,'read':r['answered_queries'],'restored':r['restored_observation_count'],
            'core':sum(v['core_executed'] for v in row['views']),
            'correct':sum(bool(v['score'] and v['score']['correct']) for v in row['views']),
            'new_physical':sum(not e['result'].get('cache_hit',False) for e in r['events'] if e['kind']=='neural')}),flush=True)
    immutable_json(OUT/'calibration/completed.json',{'sources':p['calibration_sources'],
        'previous_result_reused':p['train_sources'][0],'current_error_review_pending':True,
        'evidence_protocol':digest(protocol),'goal_complete':False})

if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_residual_reader_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);resume()
