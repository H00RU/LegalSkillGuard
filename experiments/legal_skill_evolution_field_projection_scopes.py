"""Source-preserving scope repair, paid-output replay, then fixed TRAIN queue."""
from copy import deepcopy
import fcntl
import json
from pathlib import Path

from experiments import legal_skill_evolution_field_projection_integration as stage
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.native_observation_execution import evaluate
from legal_skill_guard.skill_evolution.objects import digest

ROOT=stage.ROOT
PREVIOUS=stage.OUT
RUN='legal_skill_evolution_field_projection_scopes_20261115'
OUT=ROOT/'artifacts'/RUN


def run():
    stage.RUN=RUN;stage.OUT=OUT
    public,kernels=stage.acquired.runtime.previous.data();grading=stage.read(PREVIOUS/'TRAIN_grading.json')
    replay=[]
    for path in sorted(PREVIOUS.glob('*/*/*.json')):
        if path.parts[-3]not in ('native_residual','direct_inputs_first'):continue
        row=stage.read(path);sid=row['source'];name=row['candidate']
        lib=stage.read(PREVIOUS/'libraries'/(name+'.json'))
        result=evaluate(lib,kernels[sid],public[sid]['views'][0]['public'],row['observation'],sid)
        score=grade_view(public[sid]['dataset'],public[sid]['views'][0],
            grading[sid][public[sid]['views'][0]['id']],result['answer'])
        replay.append({'original':str(path.relative_to(ROOT)),'source':sid,'candidate':name,
            'same_actual_observation_sha256':digest(row['observation']),
            'before_execution':row['execution'],'after_execution':result,'native_score':score,
            'no_new_facts_or_source_values':True,'new_model_calls':0})
    immutable_json(OUT/'offline_replay.json',{'rows':replay,'shared_scope_repair':True,'new_model_calls':0})
    for channel in ('relation_reads','component_reads'):
        for path in(PREVIOUS/channel).glob('*.json'):
            immutable_json(OUT/channel/path.name,stage.read(path))
    stage.prepare()
    # Current implementation and tests are fixed before the remaining sources.
    stage.execute([0,1,2,3])


if __name__=='__main__':
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);run()
