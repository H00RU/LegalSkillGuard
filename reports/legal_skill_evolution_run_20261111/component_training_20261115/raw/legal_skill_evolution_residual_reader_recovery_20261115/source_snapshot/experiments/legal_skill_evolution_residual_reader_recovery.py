"""Recover actual paid observations through explicit source/query transport.

No observer program, factual role, location, date or legal rule is synthesized.
Original failures remain immutable. One independently shared family read may
close a genuinely missing proof input; its effect is separated from rereading.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from experiments import legal_skill_evolution_residual_reader_matched as previous
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.decoder_constraints import decoding_schema
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.literal_statutory_givens import constrain
from legal_skill_guard.skill_evolution.native_observation_execution import evaluate
from legal_skill_guard.skill_evolution.observation_component_library import component_value,observation_schema,_program
from legal_skill_guard.skill_evolution.observation_scope_normalization import normalize
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import render_messages
from legal_skill_guard.skill_evolution.source_event_binding import bind
from legal_skill_guard.skill_evolution.span_compiler import execute_json

ROOT=previous.ROOT
RUN='legal_skill_evolution_residual_reader_recovery_20261115'
OUT=ROOT/'artifacts'/RUN
train=previous.parent.train


def setup():
    path=OUT/'protocol.json';original=train.read(previous.OUT/'protocol.json')
    if not path.exists():
        files=[Path(__file__),Path(previous.__file__),Path(train.actor.__file__),
            previous.OUT/'protocol.json',previous.OUT/'result.json',previous.OUT/'offline_before.json',
            ROOT/original['library_path']]
        files+=sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
        files+=[ROOT/'tests'/name for name in ('test_skill_evolution_source_event_binding.py',
            'test_skill_evolution_partial_native_proof.py','test_skill_evolution_facts_only_component.py',
            'test_skill_evolution_observation_scope_normalization.py')]
        p={k:v for k,v in original.items()if k not in ('run_id','source_sha256','ledger_before')}
        p.update(run_id=RUN,original_paired_run=str(previous.OUT.relative_to(ROOT)),
            recovery='Exact calendar canonicalization and shared typed identity linking after unchanged source-only encoding.',
            no_missing_semantics_filled=True,new_teacher_calls=0,
            shared_family_source=next(s for s in original['fixed_sources']if ':3e22604a'in s),
            common_family_read_is_not_residual_or_observer_learning_credit=True,
            source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files},
            ledger_before=previous.parent.acquired.lineage.ledger_snapshot())
        immutable_json(path,p)
        for f in files:
            target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    p=train.read(path)
    for name,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    return p,train.read(ROOT/p['library_path']),*previous.parent.acquired.data()


def assessed(library,kernel,source,observation,grading):
    normalized,receipts=normalize(library,kernel,source['views'][0]['public'],observation)
    execution=evaluate(library,kernel,source['views'][0]['public'],normalized,source['key'])
    scored=train.scored({'source':source['key'],'execution':execution,'reads':[],
        'grounded':{},'fallback':False}, {source['key']:source},grading)
    return {'observation':normalized,'normalization_receipts':receipts,
        'execution':execution,'native_score':scored['native_score'],
        'partial_source_review':scored['partial_source_review'],
        'source_checked_core_correct':execution['handled']and scored['native_score']['correct']and
            not scored['partial_source_review']['failures']}


def recover():
    p,library,public,kernels=setup()
    grading=train.read(train.actor.acquisition.previous.parent.PREPARED/'grading.json')
    pairs=train.read(previous.OUT/'result.json')['pairs'];result=[]
    component=next(c for c in library['components']if c['id']=='service_events')
    for pair in pairs:
        sid=pair['source'];kernel=kernels[sid];source=public[sid];row={'source':sid,'policies':{}}
        for label,old in pair['policies'].items():
            current=assessed(library,kernel,source,old['observation_after'],grading)
            encoding_kernel={**deepcopy(kernel),'native_query':[],'query_clause':''}
            transports=[]
            for view in current['observation']['service_events']['views']:
                encoded=execute_json(_program(library['shared_helpers'],component['conversion_program']),
                    {'component_id':component['id'],'view':view,'kernel':encoding_kernel,
                        'public_case':{'facts':source['views'][0]['public']['facts']}},{},allow_helpers=True)
                linked,receipt=bind(kernel,encoded)
                assert linked==component_value(library,component,kernel,source['views'][0]['public'],view)
                assert linked['witnesses']==encoded['witnesses']
                transports.append({'source_encoding':encoded,'linked_encoding':linked,'receipt':receipt})
            row['policies'][label]={'before':{k:old[k]for k in ('execution','source_checked_core_success')},
                'recovered':current,'identity_transport':transports}
        result.append(row)
    # Replay previously validated compiled program outputs, not a new learning
    # run: every old complete conversion must remain exactly the same facts.
    old_audit=train.read(ROOT/'artifacts/legal_skill_evolution_service_observer_TRAIN_audit_20261115/result.json')
    parity=[]
    for old in old_audit['rows']:
        base=train.read(previous.parent.acquired.BASE/'libraries'/(old['arm']+'.json'))
        proposal=train.read(previous.parent.acquired.OUT/old['arm']/'teacher.json')['value']['candidates'][old['candidate']]
        component={**next(c for c in base['components']if c['id']=='service_events'),
            **{k:v for k,v in proposal.items()if k!='rationale'},'facts_only':True}
        sid=old['source'];current=[component_value(base,component,kernels[sid],public[sid]['views'][0]['public'],view)
            for view in old['observation']['service_events']['views']]
        if all(v['complete']for v in old['converted']):assert current==old['converted'],(old['arm'],old['candidate'],sid)
        parity.append({'source':sid,'arm':old['arm'],'candidate':old['candidate'],
            'previous_complete':all(v['complete']for v in old['converted']),
            'exact_conversion_equal':current==old['converted']})
    immutable_json(OUT/'result.json',{'pairs':result,'new_model_calls':0,'new_teacher_calls':0,
        'previous_compiled_observation_conversion_parity':parity,
        'original_raw_observations_and_libraries_unchanged':True,
        'source_home_omission_not_repaired':True,'DEV_TEST_loaded':False,'goal_complete':False})
    print(json.dumps([{'source':r['source'].split(':')[1][:8],
        'policies':{k:{'handled':v['recovered']['execution']['handled'],
            'source_checked_core_correct':v['recovered']['source_checked_core_correct'],
            'source_failures':v['recovered']['partial_source_review']['failures']}
            for k,v in r['policies'].items()}}for r in result]),flush=True)


def family():
    p,library,public,kernels=setup();sid=p['shared_family_source'];kernel=kernels[sid];source=public[sid]
    component=next(c for c in library['components']if c['id']=='family_relationship_residence')
    schema=constrain(observation_schema({'components':[component]},[component['id']]),source['views'][0]['public'],kernel)
    pub=source['views'][0]['public'];task={'current_case':{k:pub[k]for k in ('facts','question')},
        'current_legal_query':{k:kernel[k]for k in ('native_query','query_clause')},
        'component_meanings':{component['id']:component['meaning']}}
    messages=render_messages(component['prompt']+'\nShared native event meanings: '+p['shared_native_event_encoding'],task,schema)
    key=digest({'source':sid,'messages':messages,'wire_schema':decoding_schema(schema)[0]})
    matches=[]
    for path in (ROOT/'artifacts').glob('legal_skill_evolution*/component_reads/'+key+'.json'):
        value=train.read(path)
        if 'OfflineReadUnavailable:'in str(value.get('error'))or 'MissingPaidRead:'in str(value.get('error')):continue
        matches.append((path,value))
    if matches:
        assert len({digest({k:v[k]for k in ('source','component_id','value','error')})for _,v in matches})==1
        immutable_json(OUT/'component_reads'/(key+'.json'),matches[0][1])
    immutable_json(OUT/'common_family_cache_probe.json',{'wire_input_sha256':key,
        'actual_prior_record_paths':[str(path.relative_to(ROOT))for path,_ in matches],
        'offline_missing_markers_not_a_response':True})
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,OUT,p['executor_profile']);client.exact_replay_roots=[OUT]
    observation,receipt=train.actor.read_component(client,p,sid,component,kernel,pub,purpose='skill_actor')
    initial=next(r for r in train.read(previous.OUT/'offline_before.json')['rows']if r['source']==sid)['initial']['observation']
    grading=train.read(train.actor.acquisition.previous.parent.PREPARED/'grading.json')
    common_before=deepcopy(initial);common_before.update(observation)
    values={'source':sid,'shared_family_observation':observation,'receipt':receipt,
        'common_before_service_reread':assessed(library,kernel,source,common_before,grading),'policies':{}}
    original_pair=next(r for r in train.read(previous.OUT/'result.json')['pairs']if r['source']==sid)
    for label,row in original_pair['policies'].items():
        current=deepcopy(row['observation_after']);current.update(observation)
        values['policies'][label]=assessed(library,kernel,source,current,grading)
    immutable_json(OUT/'common_family_result.json',values)
    print(json.dumps({'before_service_reread':values['common_before_service_reread']['source_checked_core_correct'],
        'after':{k:v['source_checked_core_correct']for k,v in values['policies'].items()},
        'family_source_failures':{k:v['partial_source_review']['failures']for k,v in values['policies'].items()}}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('recover','family'));args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'recover':recover,'family':family}[args.phase]()
