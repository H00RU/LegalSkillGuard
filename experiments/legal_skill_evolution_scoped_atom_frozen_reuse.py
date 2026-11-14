"""Two preselected original-TRAIN mothers, frozen paid libraries, native score last."""
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
from datetime import datetime,timezone
from experiments import legal_skill_evolution_scoped_atom_acquisition as e
from experiments.legal_skill_evolution_scoped_atom_execution import annotate
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.rr.checkpoint import immutable_json

RUN='legal_skill_evolution_scoped_atom_frozen_reuse_20261114'
OUT=e.OUT/'frozen_reuse'


def setup():
    original=e.read(e.PARENT/'protocol.json');parent=e.read(e.OUT/'protocol.json')
    keys=[k for k in original['acquisition_sources'] if k not in parent['sources']][:2]
    assert len(keys)==2
    if not (OUT/'protocol.json').exists():
        before=e.prior.rows();assert not any(r[6]=='reserved' for r in before)
        immutable_json(OUT/'ledger_before_row_hashes.json',{r[0]:digest(r) for r in before})
        for arm in e.ARMS:
            src=e.OUT/'execution/ConstraintAcquire/learned.json' if arm=='ConstraintAcquire' else e.OUT/arm/'compiled.json'
            immutable_json(OUT/'libraries'/arm/'library.json',e.read(src))
            for key in keys:
                immutable_json(OUT/'history'/arm/e.name_for(key),e.read(e.PARENT/'history'/arm/e.name_for(key)))
        source_files=[Path(__file__),e.ROOT/'experiments/legal_skill_evolution_scoped_atom_execution.py',
            Path(e.__file__),*sorted((e.ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))]
        data=[e.prior.prior.PUBLIC,OUT/'ledger_before_row_hashes.json',*sorted((OUT/'libraries').glob('*/*.json')),
            *sorted((OUT/'history').glob('*/*.json')),e.PARENT/'base.json',e.PARENT/'grammar.json',e.PARENT/'shared/initial_library.json',
            *[e.PARENT/'upstream'/e.name_for(k) for k in keys],*[e.PARENT/'shared_source_outputs'/e.name_for(k) for k in keys]]
        p={'run_id':RUN,'same_goal':True,'goal_complete':False,'selected_utc':datetime.now(timezone.utc).isoformat(),
          'reuse_sources':keys,'selection':'first2 remaining mothers in previously fixed original12 TRAIN order; selected without opening their grading',
          'no_prior4_reuse_replay':True,'no_new_source_or_blind_test_claim':True,'prior_full_TRAIN_and_library_example_exposure_disclosed':True,
          'acquisition_sources':parent['sources'],'library_versions_frozen':True,'executor_profile':parent['executor_profile'],
          'all4_executions_saved_before_first_native_scoring':True,'no_fit_repair_or_teacher_in_this_run':True,
          'source_sha256':{str(f.relative_to(e.ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in source_files},
          'data_sha256':{str(f.relative_to(e.ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
        for src in source_files:
            dst=OUT/'source_snapshot'/src.relative_to(e.ROOT);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes())
        immutable_json(OUT/'protocol.json',p)
    p=e.read(OUT/'protocol.json')
    for name,value in {**p['source_sha256'],**p['data_sha256']}.items():assert hashlib.sha256((e.ROOT/name).read_bytes()).hexdigest()==value,name
    ledger=EvolutionLedger(e.prior.prior.LEDGER,run_id=RUN,sources={'train':p['reuse_sources'],'dev':[],'test':[]},binding=digest(p))
    public={s['key']:s for s in e.read(e.prior.prior.PUBLIC)}
    return p,ledger,public


def generate():
    p,ledger,public=setup()
    for arm in e.ARMS:
        lib=e.read(OUT/'libraries'/arm/'library.json');client=FrozenExecutor(ledger,OUT,p['executor_profile'])
        client.exact_replay_roots=(e.PARENT,e.prior.FIELD_PARENT,e.prior.PARENT,e.prior.prior.READING_PARENT)
        for key in p['reuse_sources']:
            path=OUT/'unscored'/arm/e.name_for(key)
            if path.exists():continue
            pub,units,up=e.prior.prior.source_material(e.PARENT,public,key)
            history=[e.read(OUT/'history'/a/e.name_for(key))['observation'] for a in e.ARMS]
            raw=observe(client,RUN+':'+arm+':'+key,key,lib,source_text=pub['source_text'],units=units,source_output=up,
                previous_observations=history,save_event=lambda event:immutable_json(OUT/'events'/arm/(digest(event['call_id'])+'.json'),event))
            observation=annotate(raw,arm)
            actual=e.prior.prior.evaluate_source(lib,observation,public[key],None)
            immutable_json(path,{'source':key,'observation':observation,'unscored_execution':actual})
            print(json.dumps({'arm':arm,'source':key,'new_physical':observation['execution']['new_physical_requests'],
                'backend':observation['execution']['disposal_backend']['mode'],'not_yet_scored':True}),flush=True)
    paths=[OUT/'unscored'/a/e.name_for(k) for a in e.ARMS for k in p['reuse_sources']]
    immutable_json(OUT/'execution_before_scoring.json',{'captured_utc':datetime.now(timezone.utc).isoformat(),
        'all4_unscored_executions_saved':True,'files':{str(f.relative_to(OUT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths},
        'no_frozen_library_change':True,'no_grading_loaded_in_generate':True})


def score():
    p,_,public=setup();assert (OUT/'execution_before_scoring.json').exists()
    grading=e.read(e.prior.prior.GRADING)
    for arm in e.ARMS:
        lib=e.read(OUT/'libraries'/arm/'library.json')
        for key in p['reuse_sources']:
            dst=OUT/'scores'/arm/e.name_for(key)
            if dst.exists():continue
            row=e.read(OUT/'unscored'/arm/e.name_for(key));r=e.prior.prior.evaluate_source(lib,row['observation'],public[key],grading[key])
            assert r['execution']==row['unscored_execution']['execution']
            immutable_json(dst,{'source':key,**r})
            print(json.dumps({'arm':arm,'source':key,'correct':sum(bool(v['score'] and v['score']['correct']) for v in r['feedback']['views'])}),flush=True)


if __name__=='__main__':
    import sys
    with (e.ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if sys.argv[1]=='preflight':setup()
        elif sys.argv[1]=='generate':generate()
        elif sys.argv[1]=='score':score()
        else:raise ValueError('Explicit preflight/generate/score phase required')
