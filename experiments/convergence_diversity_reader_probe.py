"""Two production reads on one locked pilot TRAIN mother, with exact replay.

This validates real reading of a common coordinate control and the generated
joint interface. It is an engineering/mechanism trace, not an effect estimate
or the complete20-source pilot. No teacher, DEV or TEST access occurs here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from experiments.convergence_replay_diversity_references import reference_reading
from legal_skill_guard.paired_interfaces import diversity_relational
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.native_adapters import LIBRARY
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/legal_skill_convergence_20261117'


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def prepare(*,all_candidates=False):
    data_pointer=read(BASE/'handoff/normalized_inputs_current.json');data=ROOT/data_pointer['artifact_root']
    audit_pointer=read(BASE/'handoff/source_audit_current.json')
    pilot=read(ROOT/audit_pointer['artifact_root']/'pilot20.json')
    rows={s['key']:s for s in read(data/'train/public.json')}
    candidates=[rows[r['source']] for r in pilot if r['dataset']=='LegalBench_Diversity']
    source=sorted(candidates,key=lambda s:(s['native_config'],digest(s)),reverse=True)[0]
    views=diversity_relational.views(source);plans=views[0]['plans']
    selected=plans if all_candidates else [plans[0],plans[-1]]
    executor=read(BASE/'handoff/executor_readiness.json')['executor_config']
    files=['experiments/convergence_diversity_reader_probe.py','experiments/convergence_replay_diversity_references.py',
        'legal_skill_guard/paired_interfaces/diversity_relational.py','legal_skill_guard/paired_interfaces/relational_program.py',
        'legal_skill_guard/paired_interfaces/diversity.py','legal_skill_guard/paired_interfaces/residual.py',
        'legal_skill_guard/paired_interfaces/production_decode.py','legal_skill_guard/paired_interfaces/formal_actors.py',
        'legal_skill_guard/skill_evolution/clients.py','legal_skill_guard/skill_evolution/ledger.py',
        'legal_skill_guard/rr/client.py','legal_skill_guard/skill_evolution/native.py']
    binding={'name':('convergence_Diversity_all_candidate_calibration_01' if all_candidates else 'convergence_Diversity_production_reader_probe_01'),'plan_commit':'37a76ffdf9490d7d213f5a9e67553a174416d84c',
        'normalized_input_root':data_pointer['artifact_root'],'pilot20_sha256':digest(pilot),
        'selected_source':source['key'],'source_public_sha256':digest(source),'executor':executor,
        'source_sha256':{p:sha(ROOT/p) for p in files},'selected_plan_versions':[p['version'] for p in selected],
        'comparisons':(['all_consumer_generated_profiles_for_paired_reader_selection'] if all_candidates else ['correct_fixed_coordinate_control','automatically_generated_joint_relations']),
        'same_source_information_and_one_call_per_candidate':True,
        'common_external_library_sha256':sha(LIBRARY),'common_external_library_path':str(LIBRARY.relative_to(ROOT)),
        'no_applicable_historical_Diversity_skill_preloaded':True,'not_full_pilot_or_learning_success':True}
    out=BASE/'diversity_reader_probe_01'/digest(binding)
    immutable_json(out/'binding.json',binding);immutable_json(out/'public_TRAIN_source.json',source)
    immutable_json(out/'selected_candidates.json',[{'name':p['name'],'version':p['version'],'choices':p['choices']} for p in selected])
    (BASE/'handoff/diversity_reader_probe_current.json').write_text(json.dumps({'artifact_root':str(out.relative_to(ROOT)),
        'status':'prepared_not_started','candidate_requests':len(selected),
        'prior_exact_wire_reads_must_be_reused':True,'source':source['key']},indent=2)+'\n')
    print(json.dumps({'prepared':str(out.relative_to(ROOT)),'TRAIN_source':source['key'],
        'native_config':source['native_config'],'candidates':len(selected),'calls_dispatched':0}),flush=True)


def run():
    pointer=read(BASE/'handoff/diversity_reader_probe_current.json');out=ROOT/pointer['artifact_root'];binding=read(out/'binding.json')
    for p,h in binding['source_sha256'].items():
        if sha(ROOT/p)!=h:raise ValueError('Bound production source changed: '+p)
    source=read(out/'public_TRAIN_source.json')
    if digest(source)!=binding['source_public_sha256']:raise ValueError('Frozen TRAIN source changed')
    identities=read(ROOT/binding['normalized_input_root']/'identity_metadata.json')
    sources={p:[r['source'] for r in identities if r['project_split']==p] for p in ('train','dev','test')}
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id='convergence-Diversity-reader-'+digest(binding)[:16],sources=sources,binding=binding)
    executor=FrozenExecutor(ledger,out,binding['executor'])
    # Valid exact-wire responses from any prior convergence probe are reusable;
    # decoder/source changes never grant permission to redispatch an old wire.
    executor.exact_replay_roots=tuple(p.parent for p in (BASE/'diversity_reader_probe_01').glob('*/binding.json') if p.parent!=out)
    ready=executor.readiness();immutable_json(out/'executor_preflight.json',ready)
    provider=diversity_relational.Provider();actor=InterfaceActor(executor,out,plan_assets={},source_inputs=None,
        pipeline_binding=binding['source_sha256'],relational_provider=provider)
    view=actor.views(source)[0];plans={p['version']:p for p in view['plans']}
    status={'artifact_root':str(out.relative_to(ROOT)),'status':'running','pid':os.getpid(),
        'started_at':time.time(),'source':source['key'],'requests':len(binding['selected_plan_versions'])}
    pointer_path=BASE/'handoff/diversity_reader_probe_current.json'
    pointer_path.write_text(json.dumps(status,indent=2)+'\n');completed=[]
    try:
        for version in binding['selected_plan_versions']:
            plan=plans[version]
            messages=[{'role':'system','content':plan['system']},
                {'role':'user','content':json.dumps(view['read_input'],ensure_ascii=False,sort_keys=True)}]
            count=executor.tokenize(messages,thinking=False)['count']
            immutable_json(out/'input_token_counts'/(version+'.json'),{'tokens':count,'generation_requests':0})
            if count+executor.config['max_tokens']>executor.config['context_tokens']:
                raise ValueError('Complete source/prompt exceeds frozen context; no generation or truncation')
            actual=actor.measure(source,view,plan,'skill_actor')
            # Predictions are already persisted and physically verified before
            # the independent source parser or native labels are consulted.
            expected,_=reference_reading(source,plan)
            local=(actual.get('decoder_receipt') or {}).get('local_receipts',{})
            comparisons=[]
            for name,reading in expected.items():
                observed=local.get(name,{}).get('source_read',{}).get('values')
                comparisons.append({'unit':name,'source_fidelity_verified':observed==reading['observation']['relations'],
                    'observed_values':observed,'reference_values':reading['observation']['relations']})
            train_pointer=read(BASE/'handoff/diversity_train_current.json')
            gold=read(ROOT/train_pointer['artifact_root']/'grading.json')[source['key']]['native']
            row={'source':source['key'],'plan':plan['name'],'choices':plan['choices'],
                'physical_call_id':actual['physical_call_id'],'reused_paid_response':actual['reused_paid_response'],
                'usage':actual['usage'],'finish_reason':actual['response_finish_reason'],
                'production_errors':actual['production_errors'],'native':actual['native'],
                'native_correct':actual['native']['native']['answer']==gold['answer'],
                'source_fidelity':comparisons,'all_local_relations_source_faithful':all(r['source_fidelity_verified'] for r in comparisons),
                'native_target_in_original_reader_input':False,'not_independent_efficacy_estimate':True}
            immutable_json(out/'comparison_rows'/(version+'.json'),row);completed.append(row)
        immutable_json(out/'terminal.json',{'status':'completed','completed':completed,'full_pilot_completed':False})
        status.update({'status':'completed','ended_at':time.time(),'completed':[{
            k:r[k] for k in ('choices','physical_call_id','usage','finish_reason','production_errors','native_correct','all_local_relations_source_faithful')} for r in completed]})
    except Exception as error:
        status.update({'status':'failed','error':type(error).__name__+': '+str(error),'ended_at':time.time()})
        (out/'terminal_failure.json').write_text(json.dumps(status,indent=2)+'\n');raise
    finally:pointer_path.write_text(json.dumps(status,indent=2)+'\n')
    print(json.dumps(status,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);p.add_argument('--all-candidates',action='store_true');a=p.parse_args()
    prepare(all_candidates=a.all_candidates) if a.action=='prepare' else run()
