"""Frozen original-TRAIN transfer: learned refinement and read-policy controls.

The hospital source is fixed by original TRAIN order and a non-wage service
query, before its current outputs. It is outside this repair's teacher task;
historical B8 exposure remains disclosed. No new teacher or TEST is used.
"""
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_observation_copy_probe as previous
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

ROOT=previous.ROOT
RUN='legal_skill_evolution_observation_contract_transfer_compact_20261115'
OUT=ROOT/'artifacts'/RUN
runtime=previous.runtime
read=previous.generation.read


def run():
    public,kernels=runtime.previous.data()
    sid=next(s for s in public if ':982d5316'in s)
    assert public[sid]['split']=='train'
    generation=read(previous.generation.OUT/'protocol.json')
    assert sid not in generation['acquisition_sources']+generation['fixed_reuse_sources']
    p={k:deepcopy(generation[k])for k in ('sources','teacher_profile','executor_profile','shared_native_event_encoding')}
    p.update(run_id=RUN,compile_finite_copy_obligations=True,stop_without_supported_demand=True,
        include_observed_event_context=True,compile_literal_copy_and_shared_keys=True,
        original_TRAIN_sources=[sid],new_teacher_requests=0,goal_complete=False,DEV_TEST=False,
        historical_B8_exposure_disclosed=True,not_new_blind_data=True,
        prior_stopped_transfer='legal_skill_evolution_observation_contract_transfer_20261115',
        substantive_changes=['Compact source-token grammar; unchanged full-copy host check',
            'Public query event types prevent foreign-domain property reads before source binding'])
    grading={}
    paths=sorted(runtime.previous.train.OUT.glob('B*/teacher_task.json'))
    paths.append(ROOT/'artifacts/legal_skill_evolution_mixed_component_training_source_review_20261115/B1/teacher_task.json')
    for path in paths:
        for c in read(path)['acquisition_cases']:
            if c['source']==sid:
                value=c['original_TRAIN_supervision']
                if sid in grading:assert grading[sid]==value
                grading[sid]=value
    if sid not in grading:
        # This source needed no B8 teacher feedback. Its native supervision
        # still comes from the same original TRAIN manifest, never DEV/TEST.
        grading[sid]=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')[sid]
    immutable_json(OUT/'TRAIN_grading.json',grading)
    names=('Method/0','Method/1','FreeTeacher/0')
    libraries={n:read(previous.PARENT/'candidate_libraries'/(n+'.json'))for n in names}
    files=[Path(__file__),Path(runtime.__file__)]+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    files += [previous.PARENT/'candidate_libraries'/(n+'.json')for n in names]
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for file in files:
        target=OUT/'source_snapshot'/file.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(file.read_bytes())
    origins=[]
    for name in ('legal_skill_evolution_mixed_component_training_compact_refs_20261115',
                 'legal_skill_evolution_mixed_component_training_validated_updates_20261115',
                 'legal_skill_evolution_relation_contract_learning_20261115'):
        for file in (ROOT/'artifacts'/name/'component_reads').glob('*.json'):
            v=read(file)
            if v.get('source')!=sid or v.get('error')or not v.get('receipt'):continue
            target=OUT/'component_reads'/file.name
            if not target.exists():immutable_json(target,v);origins.append(str(file.relative_to(ROOT)))
    immutable_json(OUT/'paid_cache_origins.json',origins)
    client=FrozenExecutor(EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN,sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p)),OUT,p['executor_profile'])
    rows=[runtime.run_case(client,p,n,libraries[n],sid,public[sid]['views'][0]['public'],kernels[sid])for n in names]
    ordinary=runtime.run_case(client,p,'Method/1',libraries['Method/1'],sid,
        public[sid]['views'][0]['public'],kernels[sid],policy='ordinary')
    immutable_json(OUT/'result.json',{'source':sid,'rows':rows,'same_contract_ordinary':ordinary,
        'no_teacher_or_extra_sources':True,'not_a_two_contribution_or_goal_completion':True,
        'goal_complete':False})


if __name__=='__main__':
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
