"""Replay the preserved real observer proposals after the str.zfill repair.

The first failed validation remains immutable. No proposal is changed, no
teacher/student is called, and the fixed reuse cases do not select a version.
"""
import ast
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from experiments import legal_skill_evolution_compiled_observer_learning as acquisition
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import validate_adapter
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_component_library import component_value


ROOT=acquisition.ROOT
OUT=ROOT/'artifacts/legal_skill_evolution_compiled_observer_validation_zfill_20261115'


def run():
    read=acquisition.train.read
    protocol=read(acquisition.OUT/'protocol.json')
    # Exact sources under which the calls and original rejection occurred remain
    # reproducible; the new shared runtime is bound separately below.
    for name,sha in protocol['source_sha256'].items():
        assert hashlib.sha256((acquisition.OUT/'source_snapshot'/name).read_bytes()).hexdigest()==sha,name
    before=acquisition.lineage.ledger_snapshot()
    paths=[Path(__file__),ROOT/'legal_skill_guard/skill_evolution/span_compiler.py',
        ROOT/'legal_skill_guard/skill_evolution/compiled_observation.py',
        ROOT/'experiments/legal_skill_evolution_observation_component_execute.py',
        acquisition.OUT/'CoverageRecombine/teacher.json',acquisition.OUT/'FreeGlobalUpdate/teacher.json']
    immutable_json(OUT/'protocol.json',{'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'teacher_proposals_changed':False,'repair':'Expose pure str.zfill, preserving Python behavior',
        'new_model_calls':0,'ledger_before':before,'DEV_TEST_loaded':False,'goal_complete':False})
    for path in paths:
        target=OUT/'source_snapshot'/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert target.read_bytes()==path.read_bytes()
        else:target.write_bytes(path.read_bytes())
    bank=acquisition.train.actor.acquisition.previous.parent.OUT
    public={s['key']:s for s in read(bank/'SARA_corrected_TRAIN_views.json')}
    kernels={r['source']:acquisition.train.actor.acquisition.current_case_interface(r['kernel'])
        for r in read(bank/'SARA_native_kernel_bank.json')}
    checkpoint=read(acquisition.train.OUT/'B8/checkpoint.json')
    client=SimpleNamespace(artifacts=OUT,ledger=SimpleNamespace(run_id=OUT.name))
    task=read(acquisition.OUT/'teacher_task.json');candidates={};selected={}
    for arm in acquisition.train.ARMS:
        library=read(ROOT/checkpoint['libraries'][arm]['path']);scored=[]
        for index,proposal in enumerate(read(acquisition.OUT/arm/'teacher.json')['value']['candidates']):
            name=arm+'/'+str(index);program=proposal['observation_program']
            entry={'candidate':name,'program_sha256':digest(program),'cases':[]}
            try:
                validate_adapter(program,excluded_source_ids=protocol['sources'])
                for n in ast.walk(ast.parse(program)):
                    if isinstance(n,ast.Constant):
                        assert n.value not in ('Alice','Bob','Charlie','Dan','Johns Hopkins University'), 'Training entity constant in observer'
                        if type(n.value)is int:assert n.value not in (2015,2017,2018,2019), 'Training year constant in observer'
                component={**deepcopy(task['existing_component']),'observation_program':program}
                for sid in protocol['acquisition_sources']:
                    pub=public[sid]['views'][0]['public']
                    observation,receipt=acquisition.train.actor.read_component(client,protocol,sid,component,kernels[sid],pub,purpose='skill_actor')
                    converted=[component_value(library,component,kernels[sid],pub,v) for v in observation[acquisition.COMPONENT]['views']]
                    checks=[acquisition.source_checks(sid,v) for v in converted]
                    entry['cases'].append({'source':sid,'observation':observation,'receipt':receipt,
                        'converted':converted,'source_checks':checks})
                entry['source_errors']=sum(len(v['source_errors']) for r in entry['cases'] for v in r['source_checks'])
                entry['usable_cases']=sum(all(v['usable'] for v in r['source_checks']) for r in entry['cases'])
                scored.append((entry['source_errors'],-entry['usable_cases'],len(program),name,component))
            except Exception as error:
                entry['error']=type(error).__name__+': '+str(error)
            immutable_json(OUT/'candidate_results'/(name+'.json'),entry);candidates[name]=entry
        if scored:
            chosen=min(scored,key=lambda r:r[:-1]);selected[arm]={'candidate':chosen[3],
                'component':chosen[4],'source_errors':chosen[0],'usable_acquisition_cases':-chosen[1]}
    immutable_json(OUT/'selected_before_reuse.json',{'selected':selected,
        'selection_uses_only_acquisition_sources':True,'native_labels_used_for_selection':False,'goal_complete':False})
    reuse=[]
    for arm,choice in selected.items():
        library=read(ROOT/checkpoint['libraries'][arm]['path'])
        for sid in protocol['fixed_reuse_sources']:
            pub=public[sid]['views'][0]['public'];component=choice['component']
            observation,receipt=acquisition.train.actor.read_component(client,protocol,sid,component,kernels[sid],pub,purpose='skill_actor')
            converted=[component_value(library,component,kernels[sid],pub,v) for v in observation[acquisition.COMPONENT]['views']]
            reuse.append({'arm':arm,'source':sid,'candidate':choice['candidate'],'observation':observation,
                'receipt':receipt,'converted':converted,'source_checks':[acquisition.source_checks(sid,v) for v in converted]})
    after=acquisition.lineage.ledger_snapshot();assert before==after
    immutable_json(OUT/'result.json',{'candidates':candidates,'selected':selected,'fixed_reuse':reuse,
        'new_teacher_calls':0,'new_executor_calls':0,'parent_acquisition_teacher_calls':2,
        'ledger_before':before,'ledger_after':after,'DEV_TEST_loaded':False,
        'runtime_observer_saw_only_current_facts':True,'original_schema_and_converter_unchanged':True,
        'not_a_whole_case_native_or_independent_contribution_result':True,'goal_complete':False})
    print(json.dumps({'selected':{a:{k:v for k,v in c.items()if k!='component'}for a,c in selected.items()},
        'reuse_usable':[all(v['usable']for v in r['source_checks'])for r in reuse]}),flush=True)


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
