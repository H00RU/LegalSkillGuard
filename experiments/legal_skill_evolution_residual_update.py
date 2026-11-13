"""Independent residual vs unrestricted reader updates from identical TRAIN."""
import argparse
import ast
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments.legal_skill_evolution_residual_calibration import ROOT,RUN,source_record
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema,source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.semantic_operations import OPERATION,validate_operations,prepare_queries,finish,NATIVE_LABELS
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units,validate_procedure
from legal_skill_guard.skill_evolution.teacher_transport import pack,unpack,INSTRUCTION

OUT=ROOT/'artifacts'/RUN
ARMS=('Residual','FreeReflection')
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
PROPOSAL=record_schema({'rationale':{'type':'string'},
    'monitor_functions':{'type':'array','items':{'type':'string'}},
    'source_functions':{'type':'array','items':{'type':'string'}},
    'operations_delta':{'type':'array','items':OPERATION},
    'lookup_name':{'type':['string','null']},
    'scope':{'type':'string','enum':['focus_last','window']}})

COMMON='''Acquire a reusable legal source-reader UPDATE from only the supplied
original TRAIN. Both arms independently update the SAME actual seed and receive
byte-identical original text, native supervision, source-semantic supervision,
current execution results, source feedback, code, examples and public tools.
This is independent UPDATING of a common initial acquisition, not independent
initial learning. No validation source or answer is provided. Frozen Qwen3-8B
thinking is OFF and sampling unchanged. No model weights are trained.

Native16/16 does not certify the source interpretation. The current source442
misses a principal passive return duty, confuses survival with retention rights,
and confuses alternative performances with independent duties. Fix actual source
semantics, not answer tables. Acquired example labels are positive-only, NOT an
exhaustive exclusive gold set. A different role name may denote the same actor;
unknown equivalence is not a negative. An inactive field mismatch is not itself
an outcome error. Old354 errors already fixed are history, not new targets.

Keep no source IDs, company/contract names or absolute TRAIN query positions as
applicability keys. Explicit legal content and names copied as values are allowed.
Do not encode native answer labels in source code or operations. Do not invent
missing rules, treat uncertainty as no-exception, or use default answers. Both
arms can use the full raw source, all acquired functions and the same public
source-evidence tool. Unsupported details may remain unresolved; timing/priority
limitations are not a new full-contract/all-details gate.

PUBLIC TOOLS AND OUTPUT
- The source program is pure functions with apply(inputs,premises), phase plan
  -> {queries:[{id,operation,unit_ids}]} and phase finish -> {complete,statements:
  [{term,support_ids}],unresolved}. It may use ordinary pure parsing instead of
  neural queries. The common59 constructors and consumer stay fixed to isolate
  reader updating. Complete acquired constructor definitions are supplied.
- An optional residual program is also pure functions with apply(inputs,premises).
  Inputs are source_text, source_spans, operations, queries, semantic_answers.
  Return {corrections:[{id,choice,evidence:[{unit_id,quote}]}]}. Correct ONLY observed
  query IDs, using a declared choice and exact current-source evidence inside
  that query window. Build quotes from the actual source_spans text rather than
  typing remembered text. It can abstain with an empty list. No host correction
  law exists. Corrections and prior neural values are both recorded.
- A residual executes after each neural observation batch and on restored exact
  observations. Correcting a role can activate other real queries through G.
- Neural replies select supporting current unit IDs; the host attaches literal
  source text. This common codec changes no legal meaning or correctness check.
- lookup_name may name the actual opaque semantic lookup with first four args
  (answers,qid,operation,unresolved), optional fifth required flag. Declare null
  if not using this tracer; then all planned queries are available. A pure-code
  reader can plan zero queries. Both focus_last/window scopes are public; keep
  acquired question meanings consistent with the declared scope.
- source_functions are compact replacements/additions to the seed functions;
  operations_delta replaces/appends operations by name. Omit unchanged functions
  and operations. No need to repeat the whole seed. monitor_functions, if used,
  contains the complete residual apply plus helpers. Each string is one complete
  function. Prebound re and supported ordinary Python methods are available;
  do not import, inspect, network, access files, globals, or model endpoints.

Keep actual known valid source behavior, including both return/prohibited-
retention and return/archival-retention cases. A correction to unknown alone is
abstention, not restored core semantics. Ordinary program edits or runtime
wrappers are not automatically research contributions. We compare source-
supported effects, actual later use, and complete acquisition/update costs.
'''
INSTRUCTIONS={
 'Residual':'''Learn a reusable source-conditioned residual interpretation program
from the actual current source contradictions. Its useful object is a small
corrector for fallible semantic observations, rather than a list of source IDs
or a duplicate whole reader. Necessary G/operation changes for source fidelity
are allowed, especially linked contexts/alternative performances. Do not add
an unnecessary layer when an ordinary source-function change suffices; explain
which part of the final update is the learned residual and which is common
source compilation. Return the runnable compact update, not a design report.''',
 'FreeReflection':'''Independently choose the best unrestricted reflective reader
update from exactly the same source, supervision and trace. You may change any
source function or operation, use pure code, add the SAME residual corrector,
or combine them. Do not adopt a larger architecture merely to differ. You are
allowed the candidate's entire hypothesis space and compact deltas. Minimize
all source errors and total cost. Return the runnable compact update.'''}


def prepare():
    p=read(OUT/'protocol.json');seed=read(OUT/'seed.json');folder=OUT/'revision'
    assert (OUT/'calibration/completed.json').exists()
    if (folder/'protocol.json').exists():
        protocol=read(folder/'protocol.json');common=read(folder/'common_input.json')
    else:
        public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
        grading=read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
        training=[]
        for key in p['train_sources']:
            source=public[key];pub=source['views'][0]['public']
            units,_=execution_source_units(pub['source_text'],source_spans(material_public(pub)))
            if key==p['train_sources'][0]:old=read(ROOT/p['current_known_train_result'])
            else:old=read(OUT/'calibration'/(key.replace(':','_')+'.json'))
            training.append({'source':key,'source_text':pub['source_text'],'source_units':units,
                'native_tasks':[{'view':v['id'],'question':v['public']['question'],
                    'annotation':grading[key][v['id']]} for v in source['views']],
                'current_queries':old['runtime']['query_plan'],'actual_semantic_answers':old['runtime']['semantic_answers'],
                'actual_source_output':old['runtime']['source_output']})
        common={'seed':seed,'original_TRAIN':training,'current_source_feedback':read(folder/'source_feedback.json'),
            'shared_acquired_scope_supervision':read(ROOT/'artifacts/legal_skill_evolution_scope_learning_20261113/execution/validated.json')['value'],
            'historical_feedback_semantic_review':read(ROOT/'artifacts/legal_skill_evolution_scope_learning_20261113/execution/training_feedback_semantic_review.json')}
        assert {s['source'] for s in common['original_TRAIN']}==set(p['train_sources'])
        paths=[Path(__file__).resolve(),ROOT/'legal_skill_guard/skill_evolution/residual_reader.py',
            ROOT/'legal_skill_guard/skill_evolution/source_evidence_codec.py']
        with __import__('sqlite3').connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
            rows=[list(r) for r in db.execute('select * from calls order by id')]
        assert not any(r[6]=='reserved' for r in rows)
        protocol={'same_goal':True,'goal_complete':False,'run_id':RUN+':updates','arms':list(ARMS),
            'train_sources':p['train_sources'],'validation_sources':p['validation_sources'],
            'seed_sha256':digest(seed),'common_input_sha256':digest(common),
            'systems':{a:COMMON+'\n'+INSTRUCTIONS[a]+'\n'+INSTRUCTION for a in ARMS},
            'source_sha256':{str(q.relative_to(ROOT)):sha(q) for q in paths},
            'executor_profile':p['executor_profile'],'teacher_profile':p['teacher_profile'],
            'same_information_and_resource_profile':True,'free_arm_can_use_residual_architecture':True,
            'independent_initial_acquisition':False,'compact_deltas_both_arms':True,
            'validation_frozen_before_current_TRAIN_update':True,'no_validation_adaptation':True,
            'no_new_mechanical_call_cap':True}
        immutable_json(folder/'protocol.json',protocol);immutable_json(folder/'common_input.json',common)
        immutable_json(folder/'ledger_before.json',{'rows':rows})
        for q in paths:
            dst=folder/'source_snapshot'/q.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(q.read_bytes())
    for name,h in protocol['source_sha256'].items():assert sha(ROOT/name)==h
    assert digest(common)==protocol['common_input_sha256']
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=protocol['run_id'],
        sources={'train':p['train_sources']+p['validation_sources'],'dev':[],'test':[]},binding=digest(protocol))
    return folder,protocol,ledger,common


def canonical_functions(changes):
    result=[];adapted=[]
    for code in changes:
        tree=ast.parse(code)
        if any(not isinstance(n,ast.FunctionDef) for n in tree.body):raise ValueError('Only supplied pure functions allowed')
        if len(tree.body)>1:adapted.append({'raw_sha256':digest(code),'functions':[n.name for n in tree.body]})
        for n in tree.body:result.append(ast.get_source_segment(code,n))
    return result,adapted


def compile_update(seed,value,texts):
    updated=deepcopy(seed)
    changes,source_adapt=canonical_functions(value['source_functions'])
    updated['program']=function_update(seed['program'],changes)
    operations={o['name']:o for o in seed['operations']}
    for op in value['operations_delta']:operations[op['name']]=op
    if len({o['name'] for o in value['operations_delta']})!=len(value['operations_delta']):
        raise ValueError('Duplicate operation update')
    updated['operations']=list(operations.values());validate_operations(updated['operations'],texts)
    monitors,monitor_adapt=canonical_functions(value['monitor_functions'])
    monitor=function_update('def apply(inputs,premises):\n    return {"corrections":[]}\n',monitors) if monitors else None
    for code in [updated['program']]+([monitor] if monitor else []):
        for n in ast.walk(ast.parse(code)):
            if isinstance(n,ast.Constant) and isinstance(n.value,str):
                if n.value in NATIVE_LABELS or n.value.startswith('ContractNLI:'):
                    raise ValueError('Native answer/source identity cannot be a source rule')
                if __import__('re').fullmatch(r'sr_\d+_(?:role|actor|trigger|action|timing|qualification|retention_info|disposal_info)',n.value):
                    raise ValueError('A TRAIN query position is not a semantic applicability condition')
    return {'bundle':updated,'monitor':monitor,'scope':value['scope'],'lookup':value['lookup_name'],
        'representation_adaptation':source_adapt+monitor_adapt,'raw_legal_meanings_not_changed_by_adapter':True}


def acquire(arm):
    folder,p,ledger,common=prepare();envelope=pack(common);assert unpack(envelope)==common
    teacher=FrozenTeacher(ledger,OUT,p['teacher_profile'])
    r=teacher.propose(p['run_id']+':teacher:'+arm+':'+digest(p['systems'][arm]),
        source_ids=p['train_sources'],system_prompt=p['systems'][arm],
        user_prompt=json.dumps(envelope,ensure_ascii=False),output_schema=PROPOSAL)
    immutable_json(folder/arm/'teacher.json',r)
    texts={s['source']:s['source_text'] for s in common['original_TRAIN']}
    result=compile_update(common['seed'],r['value'],texts)
    for s in common['original_TRAIN']:
        prepare_queries(result['bundle']['program'],result['bundle']['operations'],s['source_text'],s['source_units'])
        finish(result['bundle']['program'],s['source_text'],s['source_units'],[])
    immutable_json(folder/arm/'compiled.json',result)
    print(json.dumps({'arm':arm,'monitor':result['monitor'] is not None,
        'changed_source_functions':len(r['value']['source_functions']),
        'changed_operations':len(r['value']['operations_delta']),
        'elapsed_seconds':r['elapsed_seconds'],'goal_complete':False}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('arm',choices=['prepare',*ARMS]);args=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_residual_reader_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.arm=='prepare':print(prepare()[0])
        else:acquire(args.arm)
