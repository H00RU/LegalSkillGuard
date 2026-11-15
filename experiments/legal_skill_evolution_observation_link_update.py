"""Learn a source-faithful payment/service update from actual TRAIN failures.

The same native execution, host-key transport, source checks and budget rules
are public to both arms. This is a finite incremental update, not a new study.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_field_projection_integration as stage
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema,grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_observation_contract import schema,validate
from legal_skill_guard.skill_evolution.case_observation_contract import validate_adapter
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs,INSTRUCTION,PROGRAM_INSTRUCTION
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues

ROOT=stage.ROOT
RUN='legal_skill_evolution_observation_link_update_20261115'
OUT=ROOT/'artifacts'/RUN
PARENT=ROOT/'artifacts/legal_skill_evolution_field_projection_scopes_20261115'
TARGETS={'service_events','source_payment_relations'}
ENTRY=record_schema({'id':{'type':'string'},'contract_json':{'type':'string'}})
SCHEMA=record_schema({'rationale':{'type':'string'},'component_updates':{'type':'array','items':ENTRY}})
SYSTEM='''Update the runnable learned observation contracts using the supplied actual
TRAIN failures. No tools or new data. Return JSON only. Both arms have the same
source facts, original TRAIN supervision, failures, public ABI, code and budget.
Each receives its OWN independently acquired library, not the other arm's learned
program. All retained components stay available. Only service_events and
source_payment_relations can be replaced. Return both complete contracts.

The current bad native success is a semantic error: a payment expressly FOR labor
was read with service_event_id=null and purpose_ closed empty. It happened to get
the gold label; this is rejected by source correctness. Do not patch answers.
The independent teacher's prior program also forces means=null on 'in hay'.
Hay is stated noncash medium; lack of the word cash does not mean no medium.
The second source has two oppositely directed work/payments. The host now names
enumerated rows; do not merge events or copy payment periods into work or kinship.

Learn source-reading fields, their meanings, read constraints and factual
transductions. You may jointly change the two schemas, reading prompts and
read_constraint_programs. Rules emit factual native inputs only. The supplied
contract module is the full API. Existing nominal binding, literal copying,
partial closure and native legal execution are shared and unmodified.
read_constraint_program has pure apply(inputs,premises), returns exactly
{status: constrained/unread, domains:[{field,values}], witnesses:[{field: facts,quote}]}.
It can inspect facts, requested_relation, record_fields and actual_prior_source_records,
including observed_related_source_events with the actual observed native IDs.
It may restrict only declared non-key fields, with actual source witnesses.
Don't invent expected persons, names, dates, statutes, source IDs or answer labels.
Use generic source operations, not hardcoded case values or target-query lookup.
No model query is supplied to the reader. Do not infer cash from dollar amounts,
payment dates from work periods, or home from domestic work. Source-unstated or
ambiguous time remains unread. Positive source connections must not become null
just because their key is a host nominal ID rather than a literal source phrase.
Preserve event scope, optional factual attributes and unrelated acquired skills.

Method update uses actual residual-to-field dependency information and the current
field refinement. Treat a false closure as a counterexample to the read contract:
change the observation or source-domain program that caused it, and preserve
the factual transduction whenever it is correct. The host will evaluate the
proposed update against retaining the old contracts on whole acquisition cases.

FreeTeacher is an unrestricted strong ordinary updater under the SAME interface.
You may use all traces and the identical decomposition, programs and architecture;
choose the strongest contracts directly. Do not leave a weak representation merely
to distinguish the arms. The same whole-case selection applies.

One proposal per arm; no scan or new supervision. The original TRAIN labels are
lawful learning signals but cannot be encoded as outputs or supplied to the 8B.
Reuse begins only after selection; no DEV/TEST evidence is supplied.
'''


def prepare():
    public,kernels=stage.acquired.runtime.previous.data();old=stage.read(PARENT/'protocol.json')
    acquisition=[next(s for s in public if ':'+pre in s)for pre in ('d5e113','6939feda')]
    reuse=[next(s for s in public if ':'+pre in s)for pre in ('3e22604a','ed3f34d3')]
    assert all(public[s]['split']=='train'for s in acquisition+reuse)
    p={k:deepcopy(old[k])for k in ('sources','executor_profile','teacher_profile','shared_native_event_encoding')}
    p.update(run_id=RUN,acquisition_sources=acquisition,fixed_reuse_sources=reuse,
        native_proof_routing=True,host_enumerator_keys=True,compile_finite_copy_obligations=True,
        compile_literal_copy_and_shared_keys=True,old_B8_exposure_disclosed=True,
        no_new_sources_DEV_TEST=True,one_update_per_arm=True,goal_complete=False)
    grading=stage.read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    immutable_json(OUT/'TRAIN_grading.json',{s:grading[s]for s in acquisition+reuse})
    review=stage.read(PARENT/'unbound_reviewed_results.json')
    for arm,name in [('Method','MethodProjected'),('FreeTeacher','FreeTeacher')]:
        library=stage.read(PARENT/'libraries'/(name+'.json'));immutable_json(OUT/arm/'initial_library.json',library)
        feedback=[r for r in review['rows']if r['source']in acquisition and r['condition']==name and r['policy']=='native_residual']
        task={'current_target_components':[c for c in library['components']if c['id']in TARGETS],
            'actual_failure_feedback':feedback,'actual_raw_observations':[
                stage.read(ROOT/r['retained_original_artifact'])for r in feedback],
            'host_key_preflight':stage.read(ROOT/'artifacts/legal_skill_evolution_host_key_enumeration_20261115/result.json'),
            'acquisition_sources':[{'source':s,'public':public[s]['views'][0]['public'],
                'original_TRAIN_supervision':grading[s],'factual_vocabulary':kernels[s]['fact_arities']}for s in acquisition],
            'public_code':{n:(ROOT/'legal_skill_guard/skill_evolution'/n).read_text()for n in
                ('relational_observation_contract.py','observation_relation_reader.py','observation_copy_grammar.py',
                 'native_observation_execution.py','source_event_binding.py')},
            'native_author_code':{n:(ROOT/kernels[acquisition[0]]['statute_directory']/n).read_text()
                for n in ('events.pl','section3306.pl','utils.pl')},
            'retained_other_components':[{'id':c['id'],'meaning':c['meaning'],'coverage':c['complete_native_families']}
                for c in library['components']if c['id']not in TARGETS],
            'reuse_sources_not_provided_to_update':True}
        immutable_json(OUT/arm/'teacher_task.json',task)
    files=[Path(__file__),Path(stage.actor.__file__)]
    files+=sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    files+=sorted((ROOT/'tests').glob('test_skill_evolution_observation_host_keys.py'))
    files+=sorted(OUT.glob('*/initial_library.json'))+sorted(OUT.glob('*/teacher_task.json'))+[OUT/'TRAIN_grading.json']
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    assert not strict_output_schema_issues(SCHEMA)
    immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    # Exact semantic/raw-content caches remain paid evidence, not new requests.
    for origin in (PARENT,ROOT/'artifacts/legal_skill_evolution_host_key_enumeration_20261115'):
        for channel in ('component_reads','relation_reads'):
            for f in(origin/channel).glob('*.json'):
                if not (OUT/channel/f.name).exists():immutable_json(OUT/channel/f.name,stage.read(f))
    print(json.dumps({'prepared':RUN,'acquisition':acquisition,'reuse':reuse}),flush=True)


def protocol():
    p=stage.read(OUT/'protocol.json')
    for f,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==sha,f
    return p


def ledger(p):
    return EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p),teacher_concurrency=2)


def acquire():
    p=protocol()
    def one(arm):
        target=OUT/arm/'teacher.json'
        if target.exists():return
        task=json.dumps(pack_programs(stage.read(OUT/arm/'teacher_task.json')),ensure_ascii=False,separators=(',',':'))
        value=FrozenTeacher(ledger(p),OUT,p['teacher_profile']).propose(RUN+':'+arm+':update',
            source_ids=p['acquisition_sources'],system_prompt=SYSTEM+'\nYour arm: '+arm+'\n'+INSTRUCTION+'\n'+PROGRAM_INSTRUCTION,
            user_prompt=task,output_schema=SCHEMA)
        immutable_json(target,value);print(json.dumps({'teacher_saved':arm}),flush=True)
    with ThreadPoolExecutor(max_workers=2)as pool:
        for future in [pool.submit(one,a)for a in ('Method','FreeTeacher')]:future.result()


def libraries():
    p=protocol();_,kernels=stage.acquired.runtime.previous.data();result={}
    for arm in ('Method','FreeTeacher'):
        base=stage.read(OUT/arm/'initial_library.json');result[arm+'/Before']=base
        edits=stage.read(OUT/arm/'teacher.json')['value']['component_updates']
        assert len(edits)==len(TARGETS)and {c['id']for c in edits}==TARGETS
        updated=deepcopy(base)
        for edit in edits:
            c=next(c for c in updated['components']if c['id']==edit['id'])
            contract=json.loads(edit['contract_json']);validate(contract,kernels[p['acquisition_sources'][0]])
            if contract.get('read_constraint_program'):validate_adapter(contract['read_constraint_program'],excluded_source_ids=p['sources'])
            c['relation_contract']=contract;shape=schema(contract);shape['required']=[]
            c['schema_json']=json.dumps(record_schema({'views':{'type':'array','minItems':1,'items':shape}}))
        result[arm+'/Updated']=updated
    return result


def execute():
    p=protocol();public,kernels=stage.acquired.runtime.previous.data();libs=libraries();rows=[]
    for name,lib in libs.items():immutable_json(OUT/'libraries'/(name+'.json'),lib)
    client=FrozenExecutor(ledger(p),OUT,p['executor_profile'])
    for name,lib in libs.items():
        for sid in p['acquisition_sources']:
            row=stage.actor.execute_one(client,p,name,lib,sid,kernels[sid],public[sid],'acquisition',purpose='skill_actor')
            rows.append(graded(row,p,sid,name,'acquisition',public))
    selected={}
    for arm in ('Method','FreeTeacher'):
        # The actual whole-case and source checks, not the teacher's claim,
        # choose retaining versus adopting the update. Ties retain the old.
        selected[arm]=min([arm+'/Before',arm+'/Updated'],key=lambda n:(
            -sum(r['core_correct']for r in rows if r['condition']==n),n.endswith('/Updated')))
    immutable_json(OUT/'selected_before_reuse.json',{'selected':selected,'acquisition_only':True})
    for arm,name in selected.items():
        for sid in p['fixed_reuse_sources']:
            row=stage.actor.execute_one(client,p,name,libs[name],sid,kernels[sid],public[sid],'reuse',purpose='skill_actor')
            rows.append(graded(row,p,sid,name,'reuse',public))
    name=selected['Method'];ordinary=deepcopy(p);ordinary['native_read_policy']='direct_inputs_first'
    for sid in p['fixed_reuse_sources']:
        row=stage.actor.execute_one(client,ordinary,name,libs[name],sid,kernels[sid],public[sid],'ordinary_reuse',purpose='skill_actor')
        rows.append(graded(row,p,sid,name,'ordinary_reuse',public))
    immutable_json(OUT/'result.json',{'rows':rows,'selected':selected,'goal_complete':False})


def graded(row,p,sid,name,phase,public):
    grading=stage.read(OUT/'TRAIN_grading.json');result=row['execution']
    score=grade_view(public[sid]['dataset'],public[sid]['views'][0],grading[sid][public[sid]['views'][0]['id']],result['answer'])
    failures=sum(w['source_review']['failures']for w in result.get('binding_executions',[]))
    value={'source':sid,'condition':name,'phase':phase,'score':score,'source_failures':failures,
        'core_correct':result['handled']and score['correct']and not failures,'reads':len(row['reads'])}
    immutable_json(OUT/'graded'/phase/name/(digest(sid)+'.json'),value);print(json.dumps(value),flush=True)
    return value


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','acquire','validate','execute']);args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.phase=='prepare':prepare()
        elif args.phase=='acquire':acquire()
        elif args.phase=='validate':
            libs=libraries();immutable_json(OUT/'offline_proposal_validation.json',{'libraries':list(libs),'new_model_calls':0})
            print(json.dumps({'validated':list(libs)}),flush=True)
        else:execute()
