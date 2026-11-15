"""Acquire and execute a facts-only observer for the actual education misread.

This bounded TRAIN continuation retains the existing learned observation schema
and conversion. Independent ordinary teaching receives the identical capability
and evidence. No DEV/TEST, new original source, full training or implicit retry.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from experiments import legal_skill_evolution_mixed_component_training as train
from experiments import legal_skill_evolution_source_selection_lineage as lineage
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import validate_adapter
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_component_library import component_value
from legal_skill_guard.skill_evolution.sara_statute_kernel import literal_date


ROOT = train.ROOT
RUN = 'legal_skill_evolution_compiled_observer_learning_20261115'
OUT = ROOT / 'artifacts' / RUN
COMPONENT = 'education_service_states'
ACQUISITION_PREFIXES = ('d9d6b2', '250fc5')
REUSE_PREFIX = 'd5e113'
SCHEMA = record_schema({'rationale': {'type': 'string'}, 'candidates': {'type': 'array',
    'minItems': 2, 'maxItems': 2, 'items': record_schema({
        'rationale': {'type': 'string'}, 'observation_program': {'type': 'string', 'minLength': 1}})}})
SYSTEM = '''Learn two reusable executable observation programs from the supplied
actual TRAIN misread and preservation source. No tools. This updates the current
observation-learning component, not the legal rules or model weights.

The prior frozen student invented school/enrollment/attendance from agricultural
wage sentences. The existing schema permits complete empty arrays; the fault was
semantic, not a demand to fabricate records. Learn a source-grounded observer
instead of returning a cached observation or hardcoding the two examples.

Each self-contained program defines apply(inputs,premises). The ONLY input key
is facts (the current original facts string); premises is empty. No source ID,
question, legal query, statute, answer, previous case, teacher annotation or
reference fact is available at runtime. Return EXACTLY the same wrapper and
schema as the existing education component, including explicit complete/unread
and original fact witnesses. The current conversion code is unchanged.

Pure Python, top-level functions; no imports, IO, nested functions, recursion,
classes, lambda or reflection. Standard re is prebound by the existing sandbox.
Programs must be self-contained; the converter helpers are NOT in their globals.
Never branch on training person/company names, source IDs, dates/years or complete
case strings. Extract actual entities and dates from CURRENT facts. Month names,
general grammatical/lexical cues and reusable role patterns are allowed. Keep
institution identity separate from its classification: a named university must
remain the SAME named institution across educational-institution, enrollment
and attendance records. Do not invent institution names, merge unrelated parties,
infer attendance from enrollment, transfer dates between unrelated events, or
use a question as a fact. A stated enrollment/attendance closed interval may be
copied verbatim; do not invent bounds for onset-only or unsupported tense.

An explicit exhaustive scan for the component's source-stated event types may
report complete empty channels on unrelated wage facts. Ambiguous or unsupported
education constructions must remain unread/null, not confidently absent. Exact
quotes alone do not prove their claimed types. Do not weaken schema, conversion,
source checks or completeness. No native answer strings in code. Return only
the requested structured proposal; do not run or score it yourself.

Both arms have identical current schema/converter, source material, error feedback,
program capability, model and acquisition budget. The ordinary-teacher control
may use any equally expressive decomposition, lexical or grammatical strategy.
Program compilation itself is not claimed as a novel contribution.
'''


def prepare():
    old = train.read(train.OUT / 'protocol.json')
    bank = train.actor.acquisition.previous.parent.OUT
    public = {s['key']: s for s in train.read(bank / 'SARA_corrected_TRAIN_views.json')}
    acquisition = [sid for sid in public if any(sid.startswith('SARA_v2_Binary:'+p) for p in ACQUISITION_PREFIXES)]
    reuse = [sid for sid in public if sid.startswith('SARA_v2_Binary:'+REUSE_PREFIX)]
    assert len(acquisition) == 2 and len(reuse) == 1 and not set(acquisition)&set(reuse)
    checkpoint = train.read(train.OUT / 'B8/checkpoint.json')
    libraries = {a: train.read(ROOT / checkpoint['libraries'][a]['path']) for a in train.ARMS}
    components = {a: next(c for c in l['components'] if c['id']==COMPONENT) for a,l in libraries.items()}
    from legal_skill_guard.skill_evolution.paired_observation_recombination import _behavior
    assert _behavior(components[train.ARMS[0]]) == _behavior(components[train.ARMS[1]])
    assert libraries[train.ARMS[0]]['shared_helpers'] == libraries[train.ARMS[1]]['shared_helpers']
    actual = train.read(ROOT/'artifacts/legal_skill_evolution_observation_semantic_audit_20261115/actual_case.json')
    task = {'existing_component': components[train.ARMS[0]],
        'unchanged_converter_helpers': libraries[train.ARMS[0]]['shared_helpers'],
        'original_TRAIN_facts': [{'source':sid,'facts':public[sid]['views'][0]['public']['facts']} for sid in acquisition],
        'actual_misread': actual['observation'][COMPONENT],
        'actual_misread_conversion': next(c for c in actual['individual_actual_component_conversions'] if c['id']==COMPONENT),
        'source_feedback': 'Agricultural wages and service periods state no educational institution, enrollment or class attendance. Preserve independently stated enrollment and attendance at their actual named institution.',
        'runtime_input_example': {'facts': '<current original facts; examples are not runtime facts>'},
        'prior_B8_exposure_disclosed': True, 'reuse_source_not_in_this_task': True}
    immutable_json(OUT/'teacher_task.json', task)
    paths = [Path(__file__), train.OUT/'protocol.json', train.OUT/'B8/checkpoint.json', OUT/'teacher_task.json']
    paths += [ROOT/v['path'] for v in checkpoint['libraries'].values()]
    paths += sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += [ROOT/'experiments/legal_skill_evolution_observation_component_execute.py',
        ROOT/'tests/test_skill_evolution_compiled_observation.py']
    protocol = {'run_id':RUN,'same_goal':True,'sources':old['sources'],'acquisition_sources':acquisition,
        'fixed_reuse_sources':reuse,'teacher_profile':old['teacher_profile'],'executor_profile':old['executor_profile'],
        'component':COMPONENT,'schema':SCHEMA,'no_executor_requests_in_this_entry':True,
        'same_program_execution_capability_both_arms':True,'DEV_TEST_loaded':False,
        'not_a_blind_split_original_B8_exposure_retained':True,
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'ledger_before':lineage.ledger_snapshot(),'goal_complete':False}
    immutable_json(OUT/'protocol.json', protocol)
    for path in paths:
        target=OUT/'source_snapshot'/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert target.read_bytes()==path.read_bytes()
        else:target.write_bytes(path.read_bytes())
    print(json.dumps({'acquisition_sources':acquisition,'fixed_reuse_sources':reuse,
        'teacher_task_characters':len(json.dumps(task)),'new_model_calls':0}),flush=True)


def checked_protocol():
    p=train.read(OUT/'protocol.json')
    for name,sha in p['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    return p


def acquire():
    protocol=checked_protocol();task=train.read(OUT/'teacher_task.json')
    assert not strict_output_schema_issues(SCHEMA)
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':protocol['sources'],'dev':[],'test':[]},binding=digest(protocol),teacher_concurrency=2)
    def one(arm):
        target=OUT/arm/'teacher.json'
        if target.exists():return
        mode=('Learn reusable observation programs from the actual semantic error, preserving supported entity/time relationships.'
            if arm==train.ARMS[0] else 'Independently acquire the strongest ordinary teacher source programs with all the same abilities. Do not weaken this control.')
        response=FrozenTeacher(ledger,OUT,protocol['teacher_profile']).propose(RUN+':'+arm+':observer',
            source_ids=protocol['acquisition_sources'],system_prompt=SYSTEM+'\n'+mode,
            user_prompt=json.dumps(task,ensure_ascii=False,separators=(',',':')),output_schema=SCHEMA)
        immutable_json(target,response);print(json.dumps({'teacher_saved':arm}),flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(one,a) for a in train.ARMS]
        for job in jobs:job.result()


def source_checks(source, value):
    if not value['complete']:
        return {'source_errors':[], 'usable':False, 'reason':'Explicit unresolved observation'}
    facts=deepcopy(value['facts'])
    for row in facts:
        if row['predicate'] in ('start_','end_'):
            row['arguments'][1]=literal_date(row['arguments'][1])
    def has(p,args):return {'predicate':p,'arguments':args} in facts
    errors=[]
    if source.startswith('SARA_v2_Binary:250fc5'):
        # Original TRAIN source annotations, not a native answer or runtime data.
        for typ,role in [('educational_institution_','agent_'),('enrollment_','patient_'),('attending_classes_','location_')]:
            ids=[f['arguments'][0] for f in facts if f['predicate']==typ]
            if not any(has(role,[e,'Johns Hopkins University']) and (typ=='educational_institution_' or
                has('agent_',[e,'Alice']) and has('start_',[e,'2015-08-29']) and has('end_',[e,'2019-05-30'])) for e in ids):
                errors.append('Missing or inconsistent source-stated '+typ)
    elif facts:
        errors.append('Unrelated wage source supplied no educational institution, enrollment or attendance')
    return {'source_errors':errors,'usable':not errors,'normalized_facts':facts}


def validate():
    protocol=checked_protocol();bank=train.actor.acquisition.previous.parent.OUT
    public={s['key']:s for s in train.read(bank/'SARA_corrected_TRAIN_views.json')}
    kernels={r['source']:train.actor.acquisition.current_case_interface(r['kernel'])
        for r in train.read(bank/'SARA_native_kernel_bank.json')}
    checkpoint=train.read(train.OUT/'B8/checkpoint.json')
    client=SimpleNamespace(artifacts=OUT,ledger=SimpleNamespace(run_id=RUN))
    task=train.read(OUT/'teacher_task.json');candidates={};selected={}
    for arm in train.ARMS:
        library=train.read(ROOT/checkpoint['libraries'][arm]['path']);scored=[]
        for index,proposal in enumerate(train.read(OUT/arm/'teacher.json')['value']['candidates']):
            name=arm+'/'+str(index);program=proposal['observation_program']
            entry={'candidate':name,'program_sha256':digest(program),'cases':[]}
            try:
                validate_adapter(program,excluded_source_ids=protocol['sources'])
                for n in ast.walk(ast.parse(program)):
                    if isinstance(n,ast.Constant):
                        assert n.value not in ('Alice','Bob','Charlie','Dan','Johns Hopkins University'), 'Training entity constant in observer'
                        if type(n.value) is int:assert n.value not in (2015,2017,2018,2019), 'Training year constant in observer'
                component={**deepcopy(task['existing_component']),'observation_program':program}
                for sid in protocol['acquisition_sources']:
                    pub=public[sid]['views'][0]['public']
                    observation,receipt=train.actor.read_component(client,protocol,sid,component,kernels[sid],pub,purpose='skill_actor')
                    converted=[component_value(library,component,kernels[sid],pub,v) for v in observation[COMPONENT]['views']]
                    checks=[source_checks(sid,v) for v in converted]
                    entry['cases'].append({'source':sid,'observation':observation,'receipt':receipt,
                        'converted':converted,'source_checks':checks})
                entry['source_errors']=sum(len(v['source_errors']) for r in entry['cases'] for v in r['source_checks'])
                entry['usable_cases']=sum(all(v['usable'] for v in r['source_checks']) for r in entry['cases'])
                scored.append((entry['source_errors'],-entry['usable_cases'],len(program),name,component))
            except Exception as error:
                entry['error']=type(error).__name__+': '+str(error)
            immutable_json(OUT/'candidate_results'/(name+'.json'),entry);candidates[name]=entry
        if scored:
            choice=min(scored,key=lambda r:r[:-1]);selected[arm]={'candidate':choice[3],
                'component':choice[4],'source_errors':choice[0],'usable_acquisition_cases':-choice[1]}
    immutable_json(OUT/'selected_before_reuse.json',{'selected':selected,
        'selection_uses_only_acquisition_sources':True,'not_native_score_selection':True,'goal_complete':False})
    reuse=[]
    for arm,choice in selected.items():
        library=train.read(ROOT/checkpoint['libraries'][arm]['path'])
        for sid in protocol['fixed_reuse_sources']:
            pub=public[sid]['views'][0]['public'];component=choice['component']
            observation,receipt=train.actor.read_component(client,protocol,sid,component,kernels[sid],pub,purpose='skill_actor')
            converted=[component_value(library,component,kernels[sid],pub,v) for v in observation[COMPONENT]['views']]
            reuse.append({'arm':arm,'source':sid,'candidate':choice['candidate'],'observation':observation,
                'receipt':receipt,'converted':converted,'source_checks':[source_checks(sid,v) for v in converted]})
    immutable_json(OUT/'result.json',{'candidates':candidates,'selected':selected,'fixed_reuse':reuse,
        'teacher_calls':2,'executor_calls':0,'DEV_TEST_loaded':False,
        'runtime_observer_saw_only_current_facts':True,'original_schema_and_converter_unchanged':True,
        'not_a_whole_case_native_or_independent_contribution_result':True,'goal_complete':False})
    print(json.dumps({'selected':{a:{k:v for k,v in c.items() if k!='component'} for a,c in selected.items()},
        'reuse_usable':[all(v['usable'] for v in r['source_checks']) for r in reuse]}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','acquire','validate'));args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'acquire':acquire,'validate':validate}[args.phase]()
