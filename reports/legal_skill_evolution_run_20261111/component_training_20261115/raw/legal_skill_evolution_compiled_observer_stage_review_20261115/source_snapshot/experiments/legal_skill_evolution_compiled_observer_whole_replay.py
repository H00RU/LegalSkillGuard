"""Integrate the real learned observers into fixed TRAIN whole-case paths.

Only original paid component responses are reused; a missing response is not
generated or called an incorrect prediction. Native labels score only completed
executions and never enter the learned observer or candidate selection.
"""
from copy import deepcopy
import fcntl
import json
from types import SimpleNamespace

from experiments import legal_skill_evolution_compiled_observer_learning as acquired
from experiments import legal_skill_evolution_observation_TRAIN_replay as cache_index
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native_case_encoding import FACTUAL_ENCODING
from legal_skill_guard.skill_evolution.objects import digest


ROOT=acquired.ROOT
OUT=ROOT/'artifacts/legal_skill_evolution_compiled_observer_whole_replay_20261115'
SELECTED=ROOT/'artifacts/legal_skill_evolution_compiled_observer_validation_component_abi_20261115'


class MissingPaidRead(RuntimeError):pass


class OnlyPaid:
    artifacts=OUT
    ledger=SimpleNamespace(run_id=OUT.name)

    def tokenize(self,*args,**kwargs):
        raise MissingPaidRead('No original exact paid read, no model request dispatched')

    def generate(self,*args,**kwargs):
        raise AssertionError('This integration entry cannot call a model')


def run():
    read=acquired.train.read;before=acquired.lineage.ledger_snapshot()
    protocol=read(acquired.OUT/'protocol.json')
    selected=read(SELECTED/'selected_before_reuse.json')['selected']
    keys=protocol['acquisition_sources']+protocol['fixed_reuse_sources']
    checkpoint=read(acquired.train.OUT/'B8/checkpoint.json')
    bank=acquired.train.actor.acquisition.previous.parent.OUT
    public={s['key']:s for s in read(bank/'SARA_corrected_TRAIN_views.json')}
    kernels={r['source']:acquired.train.actor.acquisition.current_case_interface(r['kernel'])
        for r in read(bank/'SARA_native_kernel_bank.json')}
    grading=read(acquired.train.actor.acquisition.previous.parent.PREPARED/'grading.json')
    cache,origins,conflicts={},{},set()
    for name in cache_index.CACHE_NAMES:
        for path in sorted((ROOT/'artifacts'/name/'component_reads').glob('*.json')):
            row=read(path)
            if row['source'] not in keys:continue
            key=row['wire_input_sha256'];payload={k:row[k]for k in ('source','component_id','value','error')}
            if key in cache and payload!=cache[key][0]:conflicts.add(key)
            cache.setdefault(key,(payload,row));origins.setdefault(key,[]).append(str(path.relative_to(ROOT)))
    for key,(_,row)in cache.items():
        if key not in conflicts:immutable_json(OUT/'component_reads'/(key+'.json'),row)
    immutable_json(OUT/'paid_read_provenance.json',{'origins':origins,'conflicts_not_replayed':sorted(conflicts)})
    actor_protocol={'executor_profile':protocol['executor_profile'],'shared_public_pure_calculation':True,
        'shared_native_event_encoding':FACTUAL_ENCODING}
    rows=[]
    for arm,choice in selected.items():
        library=deepcopy(read(ROOT/checkpoint['libraries'][arm]['path']))
        for component in library['components']:
            if component['id']==acquired.COMPONENT:
                component['observation_program']=choice['component']['observation_program']
        immutable_json(OUT/'libraries'/(arm+'.json'),library)
        for sid in keys:
            row=acquired.train.actor.execute_one(OnlyPaid(),actor_protocol,arm,library,sid,kernels[sid],
                public[sid],'whole_fixed_TRAIN',purpose='skill_actor')
            assessable='MissingPaidRead:'not in row.get('error','')
            row={**row,'all_original_paid_read_evidence_available':assessable}
            if assessable:row=acquired.train.scored(row,public,grading)
            rows.append(row)
    after=acquired.lineage.ledger_snapshot();assert before==after
    summary={}
    for arm in selected:
        subset=[r for r in rows if r['candidate']==arm];assessed=[r for r in subset if r['all_original_paid_read_evidence_available']]
        summary[arm]={'mothers':len(subset),'assessable_from_paid_evidence':len(assessed),
            'missing_paid_read_evidence':len(subset)-len(assessed),
            'core_handled':sum(r['execution']['handled']for r in assessed),
            'core_native_correct':sum(r['execution']['handled']and r['native_score']['correct']for r in assessed),
            'partial_source_failures':sum(r['partial_source_review']['failures']for r in assessed)}
    immutable_json(OUT/'result.json',{'summary':summary,'rows':rows,'new_model_calls':0,
        'ledger_before':before,'ledger_after':after,'DEV_TEST_loaded':False,
        'native_correctness_not_full_source_semantics':True,'goal_complete':False})
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
