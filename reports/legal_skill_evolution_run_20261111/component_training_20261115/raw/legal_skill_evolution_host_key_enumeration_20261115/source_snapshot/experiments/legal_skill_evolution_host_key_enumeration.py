"""One actual schema preflight for the real duplicate-key TRAIN failure."""
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_field_projection_integration as stage
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.observation_component_library import component_value
from legal_skill_guard.skill_evolution.observation_relation_reader import read_relation
from legal_skill_guard.skill_evolution.objects import digest

ROOT=stage.ROOT
RUN='legal_skill_evolution_host_key_enumeration_20261115'
OUT=ROOT/'artifacts'/RUN


def run():
    public,kernels=stage.acquired.runtime.previous.data();sid=next(s for s in public if ':6939feda'in s)
    old=stage.read(ROOT/'artifacts/legal_skill_evolution_field_projection_scopes_20261115/protocol.json')
    p={k:old[k]for k in ('sources','executor_profile','teacher_profile')}
    library=stage.read(ROOT/'artifacts/legal_skill_evolution_field_projection_scopes_20261115/libraries/MethodProjected.json')
    c=next(c for c in library['components']if c['id']=='service_events');relation=c['relation_contract']['enumerator']
    p.update(run_id=RUN,source=sid,host_enumerator_keys=True,compile_literal_copy_and_shared_keys=True,
        no_teacher=True,no_DEV_TEST=True,question='Can the real first read enumerate distinct source rows without generating keys?',
        not_whole_case_or_method_evidence=True,goal_complete=False)
    files=[Path(__file__),ROOT/'tests/test_skill_evolution_observation_host_keys.py']
    files+=sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p);immutable_json(OUT/'library.json',library)
    for file in files:
        target=OUT/'source_snapshot'/file.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(file.read_bytes())
    client=FrozenExecutor(EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN,sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p)),OUT,p['executor_profile'])
    value,receipt=read_relation(client,p,sid,c,relation,public[sid]['views'][0]['public'],{})
    part=component_value(library,c,kernels[sid],public[sid]['views'][0]['public'],value)
    rows=value[relation].get('records')or[]
    immutable_json(OUT/'result.json',{'source':sid,'relation':relation,'observation':value,'converted':part,
        'receipt':receipt,'distinct_nominal_keys':len({r['source_key']for r in rows})==len(rows),
        'source_worker_multiset_correct':sorted(r['worker']for r in rows)==['Alice','Bob'],
        'not_a_whole_case_or_learning_gain':True,'goal_complete':False})
    print(json.dumps({'source':sid,'distinct_keys':len({r['source_key']for r in rows}),
        'rows':len(rows),'conversion_complete':part['complete'],'whole_case_not_claimed':True}),flush=True)


if __name__=='__main__':
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);run()
