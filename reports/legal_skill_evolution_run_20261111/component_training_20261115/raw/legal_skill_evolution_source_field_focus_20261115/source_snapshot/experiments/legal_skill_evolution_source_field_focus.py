"""Diagnose two actual source-reading failures with one explicit clause per read.

This common input-interface repair is not a learned C mechanism or native score.
The two original TRAIN clauses were already queried by the acquired planner.
No new source, teacher, configuration, label input or whole-contract rerun.
"""
import argparse
import fcntl
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_source_field_probe as previous
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages

ROOT=previous.ROOT
RUN='legal_skill_evolution_source_field_focus_20261115'
OUT=ROOT/'artifacts'/RUN
SYSTEM=previous.SYSTEM.replace(
    'Extract literal rule-text fields from the supplied CURRENT source.',
    'Extract literal rule-text fields ONLY for the supplied focus_unit_id. '
    'The other units are context for that focus, not additional output frames.')+'''
Return exactly ONE frame using the supplied output_schema, not a frames array.
Do not shift the focus to a different clause. Use the context only for actual
governing clauses and definitions needed by this focus. A person who performs
return/destruction or retention is not thereby a disclosure recipient; keep
recipient_members empty when the focus specifies no disclosure/access recipient.
'''


def prepare():
    p=previous.read(previous.OUT/'protocol.json')
    bank=previous.read(previous.OUT/'source_only_inputs.json')
    focuses={s:(10 if ':e671' in s else 51)for s in p['probe_sources']}
    rows=[]
    for sid,focus in focuses.items():
        source=ROOT/'artifacts/legal_skill_evolution_C_program_retained_20261115/C/raw_observations'/(digest(sid)+'.json')
        raw=previous.read(source)
        matching=[q for q in raw['visible_inputs']['queries']if q['id'].endswith('|unit|'+str(focus))]
        assert matching and all(focus in q['unit_ids']for q in matching)
        item=deepcopy(bank[sid]);item['focus_unit_id']=focus
        schema=deepcopy(previous.schema(item['units'])['properties']['frames']['items'])
        schema['properties']['clause_unit_id']['enum']=[focus]
        rows.append({'source':sid,'input':item,'schema':schema,
            'prior_actual_queries':matching,'prior_observation_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
    immutable_json(OUT/'inputs.json',rows)
    p.update(run_id=RUN,prior_run=previous.RUN,focuses=focuses,
        actual_change='One explicit pre-existing query focus and one frame; source text and field semantics preserved',
        common_interface_probe_not_C_success=True,teacher_requests=0,
        ledger_before=previous.current.previous.base.lineage.ledger_snapshot())
    files=[Path(__file__),Path(previous.__file__),OUT/'inputs.json']+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    print(json.dumps({'prepared':RUN,'focused_actual_queries':focuses,'model_calls':0}),flush=True)


def execute():
    p=previous.read(OUT/'protocol.json')
    for path,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,OUT,p['executor_profile']);rows=[]
    for task in previous.read(OUT/'inputs.json'):
        sid=task['source'];target=OUT/'results'/(digest(sid)+'.json')
        if target.exists():rows.append(previous.read(target));continue
        host=task['schema'];wire,checks=decoder_schema(host)
        prompt=render_messages(SYSTEM,task['input'],host)
        assert json.loads(prompt[1]['content'])['output_schema']==host
        tokens=client.tokenize(prompt,thinking=False)['count']
        assert tokens+p['executor_profile']['max_tokens']<=p['executor_profile']['context_tokens']
        response=client.generate(RUN+':fields:'+digest(sid),source=sid,purpose='skill_replay',messages=prompt,thinking=False,schema=wire)
        row={'source':sid,'focus_unit_id':task['input']['focus_unit_id'],'response':response,
            'decoder_host_checks':checks,'input_tokens':tokens,'typed_complete':False,
            'source_semantics_verified':False,'native_score':None,'not_method_contribution_evidence':True}
        if response['finish_reason']=='stop':
            try:
                value=json.loads(response['content']);jsonschema.validate(value,host);row.update(typed_complete=True,value=value)
            except(ValueError,jsonschema.ValidationError)as error:row['error']=str(error)
        else:row['error']='Incomplete response; no implicit retry'
        immutable_json(target,row);rows.append(row)
        print(json.dumps({'source':sid,'typed_complete':row['typed_complete'],'finish_reason':response['finish_reason'],
            'elapsed_seconds':response['elapsed_seconds']}),flush=True)
    immutable_json(OUT/'result.json',{'rows':rows,'common_interface_diagnostic_only':True,'goal_complete':False,'new_DEV_TEST':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','execute'));args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'execute':execute}[args.phase]()
