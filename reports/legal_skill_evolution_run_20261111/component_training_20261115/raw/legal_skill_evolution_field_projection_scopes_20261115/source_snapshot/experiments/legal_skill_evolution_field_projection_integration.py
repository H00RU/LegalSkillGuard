"""Current-entry integration and fixed original-TRAIN recovery comparison.

No new teacher or data. Shared compiler/runtime fixes apply to both arms.
This stage tests whole-case recovery and attribution, not a new full matrix.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from experiments import legal_skill_evolution_payment_contract_refinement as acquired
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_field_projection import compile_library
from legal_skill_guard.skill_evolution.observation_component_library import validate

ROOT=acquired.ROOT
RUN='legal_skill_evolution_field_projection_integration_20261115'
OUT=ROOT/'artifacts'/RUN
PARENT=ROOT/'artifacts/legal_skill_evolution_payment_contract_routing_20261115'
actor=acquired.runtime.previous.train.actor
read=acquired.read
PREFIXES=('250fc5','d5e113','6939fed','982d5316')


def prepare():
    public,kernels=acquired.runtime.previous.data()
    sources=[next(s for s in public if ':'+prefix in s)for prefix in PREFIXES]
    assert all(public[s]['split']=='train'for s in sources)
    old=read(PARENT/'protocol.json')
    p={k:deepcopy(old[k])for k in ('sources','executor_profile','teacher_profile','shared_native_event_encoding')}
    p.update(run_id=RUN,original_TRAIN_sources=sources,native_proof_routing=True,
        compile_finite_copy_obligations=True,compile_literal_copy_and_shared_keys=True,
        no_new_teacher=True,no_DEV_TEST=True,goal_complete=False,
        original_acquisition_sources=old['acquisition_sources'],
        old_B8_exposure_disclosed_not_blind=True,
        questions=['Does field-level reading and binding reach whole-case execution?',
            'Does recovery survive the independent ordinary teacher and same-contract ordinary-read control?'],
        changes=['Shared source-only nominal binding demands','Partial source checks distinguish unread from wrong',
            'Positive witnesses do not assert exhaustive scans','Relation path uses current native execution entry'])
    grading=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    immutable_json(OUT/'TRAIN_grading.json',{s:grading[s]for s in sources})
    method=read(PARENT/'candidate_libraries/Method/1.json')
    free=read(PARENT/'candidate_libraries/FreeTeacher/0.json')
    projected,receipt=compile_library(method);free_projected,free_receipt=compile_library(free)
    libs={'MethodProjected':projected,'MethodCoupled':method,'FreeTeacher':free_projected}
    for name,lib in libs.items():
        for sid in sources:validate(lib,kernels[sid])
        immutable_json(OUT/'libraries'/(name+'.json'),lib)
    immutable_json(OUT/'compiler_receipts.json',{'Method':receipt,'FreeTeacher':free_receipt,
        'shared_public_compiler_not_learning':True})
    # Original-schema programs and raw responses are not rewritten. Exact paid
    # component cache identity is still checked by the existing actor.
    origins=[]
    names=('legal_skill_evolution_payment_contract_routing_20261115',
        'legal_skill_evolution_observation_contract_transfer_compact_saved_20261115',
        'legal_skill_evolution_projected_observation_execute_20261115',
        'legal_skill_evolution_mixed_component_training_compact_refs_20261115')
    for name in names:
        for file in (ROOT/'artifacts'/name/'component_reads').glob('*.json'):
            value=read(file)
            if value.get('source')not in sources or value.get('error')or not value.get('receipt'):continue
            target=OUT/'component_reads'/file.name
            if not target.exists():immutable_json(target,value);origins.append(str(file.relative_to(ROOT)))
    immutable_json(OUT/'paid_cache_origins.json',origins)
    files=[Path(__file__),Path(actor.__file__),OUT/'TRAIN_grading.json']
    files+=sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    files+=sorted((OUT/'libraries').glob('*.json'))
    files+=list((ROOT/'tests').glob('test_skill_evolution_field_projection_integration.py'))
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for file in files:
        target=OUT/'source_snapshot'/file.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(file.read_bytes())
    print(json.dumps({'prepared':RUN,'sources':sources,'new_model_calls':0}),flush=True)


def protocol():
    p=read(OUT/'protocol.json')
    for f,sha in p['source_sha256'].items():
        assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==sha,f
    return p


def execute(indices):
    p=protocol();public,kernels=acquired.runtime.previous.data();grading=read(OUT/'TRAIN_grading.json')
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN,sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,OUT,p['executor_profile'])
    rows=[]
    for i in indices:
        sid=p['original_TRAIN_sources'][i]
        for name,policy in [('MethodProjected','native_residual'),('MethodCoupled','native_residual'),
                            ('FreeTeacher','native_residual'),('MethodProjected','direct_inputs_first')]:
            lib=read(OUT/'libraries'/(name+'.json'));variant=deepcopy(p);variant['native_read_policy']=policy
            row=actor.execute_one(client,variant,name,lib,sid,kernels[sid],public[sid],policy,purpose='skill_actor')
            result=row['execution'];score=grade_view(public[sid]['dataset'],public[sid]['views'][0],
                grading[sid][public[sid]['views'][0]['id']],result['answer'])
            failures=sum(w['source_review']['failures']for w in result.get('binding_executions',[]))
            graded={'source':sid,'condition':name,'policy':policy,'native_score':score,'source_failures':failures,
                'core_correct':result['handled']and score['correct']and not failures,
                'reads':len(row['reads']),'artifact':str((OUT/policy/name/(digest(sid)+'.json')).relative_to(ROOT))}
            immutable_json(OUT/'graded'/(name+'_'+policy+'_'+digest(sid)+'.json'),graded)
            rows.append(graded);print(json.dumps(graded),flush=True)
    summary={'rows':[read(f)for f in sorted((OUT/'graded').glob('*.json'))],
        'fixed_original_TRAIN_only':True,'new_teacher_calls':0,'goal_complete':False}
    # An evolving status snapshot is deliberately not part of the frozen manifest.
    (OUT/'unbound_summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','execute'])
    parser.add_argument('--indices',nargs='+',type=int,default=list(range(len(PREFIXES))))
    args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        prepare()if args.action=='prepare'else execute(args.indices)
