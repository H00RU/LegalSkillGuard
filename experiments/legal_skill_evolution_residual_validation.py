"""Materialize the two actual TRAIN updates and run the fixed TRAIN holdout.

No teacher is called here. Linking copies inherited pure helpers verbatim;
the acquired legal code and choices are not repaired by the host.
"""
import argparse
import ast
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import re

from experiments.legal_skill_evolution_residual_calibration import ROOT, RUN, source_record
from experiments.legal_skill_evolution_residual_update import canonical_functions
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.residual_reader import execute, residual_answers
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.semantic_operations import validate_operations, NATIVE_LABELS
from legal_skill_guard.skill_evolution.source_python import (
    CALLS, merge_functions, validate, plan, finish, probe_program)
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units

OUT=ROOT/'artifacts'/RUN
ARMS=('Residual','FreeReflection')
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def linked_monitor(functions, inherited):
    """Resolve only named calls to functions already in the actual shared bank."""
    if not functions:return None,[]
    parts={ast.parse(s).body[0].name:s for s in functions}
    if len(parts)!=len(functions) or 'apply' not in parts:
        raise ValueError('One acquired residual apply and distinct helpers required')
    bank={n.name:ast.get_source_segment(inherited,n) for n in ast.parse(inherited).body}
    linked=[]
    while True:
        tree=ast.parse('\n\n'.join(parts.values()))
        local={n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}
        calls={n.func.id for n in ast.walk(tree)
               if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        missing=sorted(calls-CALLS-local)
        if not missing:break
        for name in missing:
            if name=='apply' or name not in bank:
                raise ValueError('No inherited helper for '+name)
            parts[name]=bank[name]
            linked.append({'function':name,'exact_inherited_code_sha256':digest(bank[name])})
    result='\n\n'.join(parts.values())+'\n'
    validate(result)
    return result,linked


def materialize_one(seed,value,texts):
    b=deepcopy(seed)
    changes,adapted=canonical_functions(value['source_functions'])
    b['program']=merge_functions(seed['program'],changes)
    ops={o['name']:o for o in seed['operations']}
    delta=value['operations_delta']
    if len({o['name'] for o in delta})!=len(delta):raise ValueError('Repeated operation update')
    for o in delta:ops[o['name']]=o
    b['operations']=list(ops.values());validate_operations(b['operations'],texts)
    monitors,monitor_adapt=canonical_functions(value['monitor_functions'])
    monitor,linked=linked_monitor(monitors,b['program'])
    for code in [b['program']]+([monitor] if monitor else []):
        for n in ast.walk(ast.parse(code)):
            if isinstance(n,ast.Constant) and isinstance(n.value,str):
                if n.value in NATIVE_LABELS or n.value.startswith('ContractNLI:'):
                    raise ValueError('Source code may not contain answers or source identities')
                if re.fullmatch(r'sr_\d+_(?:role|actor|trigger|action|timing|qualification|retention_info|disposal_info)',n.value):
                    raise ValueError('Absolute TRAIN query position is not applicability')
    actual={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(b['program']).body}
    exact=all(actual[ast.parse(s).body[0].name]==ast.dump(ast.parse(s).body[0],include_attributes=False)
              for s in changes)
    assert exact
    return {'bundle':b,'monitor':monitor,'scope':value['scope'],'lookup':value['lookup_name'],
        'representation_adaptation':adapted+monitor_adapt,'linked_inherited_helpers':linked,
        'acquired_source_function_AST_unchanged':exact,
        'acquired_monitor_function_AST_unchanged':all(
            ast.dump(ast.parse(s).body[0],include_attributes=False)==next(
                ast.dump(n,include_attributes=False) for n in ast.parse(monitor).body
                if n.name==ast.parse(s).body[0].name) for s in monitors),
        'old_materializer_error':'No nested functions',
        'pure_python_change':'Local helpers, recursive pure traversal and dict.setdefault; same restricted subprocess/resource limits and scientific checks.'}


def materialize():
    common=read(OUT/'revision/common_input.json')
    texts={s['source']:s['source_text'] for s in common['original_TRAIN']}
    for arm in ARMS:
        raw=read(OUT/'revision'/arm/'teacher.json')
        result=materialize_one(common['seed'],raw['value'],texts)
        result['raw_teacher_sha256']=sha(OUT/'revision'/arm/'teacher.json')
        immutable_json(OUT/'materialized'/arm/'compiled.json',result)
        print(json.dumps({'arm':arm,'compiled':True,'linked':result['linked_inherited_helpers']}),flush=True)


def offline():
    common=read(OUT/'revision/common_input.json')
    public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    rows=[]
    for arm in ARMS:
        compiled=read(OUT/'materialized'/arm/'compiled.json');b=compiled['bundle']
        for source in common['original_TRAIN']:
            queries=plan(b['program'],b['operations'],source['source_text'],source['source_units'])
            answers={a['id']:a for a in source['actual_semantic_answers']}
            # Component replay only. Changed questions/windows mean these are
            # NOT new neural observations or end-to-end updated-reader results.
            corrected,changes=residual_answers(compiled['monitor'],b['operations'],queries,
                source['source_text'],source['source_units'],answers)
            raw=finish(b['program'],source['source_text'],source['source_units'],list(corrected.values()))
            record=source_record(b,public[source['source']],{'source_output':raw})
            if compiled['lookup']:
                probe=probe_program(b['program'],compiled['lookup'])
                demand=finish(probe,source['source_text'],source['source_units'],[])
            else:demand=None
            row={'arm':arm,'source':source['source'],'queries':queries,'corrections':changes,
                'record':record,'initial_demand':demand,'component_replay_only':True,
                'old_observations_not_new_question_measurements':True}
            immutable_json(OUT/'materialized'/arm/(source['source'].replace(':','_')+'.json'),row)
            rows.append({'arm':arm,'source':source['source'],'corrections':len(changes),
                'typed_roots':len(record['interpretation']['roots']),
                'native_correct':sum(bool(v['score'] and v['score']['correct']) for v in record['views'])})
    result={'rows':rows,'execution_types_and_evidence_passed':True,'new_model_calls':0,
        'not_end_to_end_or_generalization_evidence':True,'goal_complete':False}
    immutable_json(OUT/'materialized/offline.json',result);print(json.dumps(result),flush=True)


def freeze():
    p=read(OUT/'protocol.json');offline_result=read(OUT/'materialized/offline.json')
    assert offline_result['execution_types_and_evidence_passed']
    paths=[Path(__file__).resolve()]+[ROOT/'legal_skill_guard/skill_evolution'/n for n in
        ('residual_reader.py','source_python.py','source_evidence_codec.py','semantic_operations.py',
         'span_compiler_worker.py')]
    current={'run_id':RUN+':fixed_validation','train_sources':p['train_sources'],
        'validation_sources':p['validation_sources'],'executor_profile':p['executor_profile'],
        'arms':['Residual','FreeReflection','NoResidual','Seed'],
        'compiled_sha256':{a:sha(OUT/'materialized'/a/'compiled.json') for a in ARMS},
        'seed_sha256':sha(OUT/'seed.json'),'offline_sha256':sha(OUT/'materialized/offline.json'),
        'source_sha256':{str(q.relative_to(ROOT)):sha(q) for q in paths},
        'no_validation_adaptation':True,'same_initial_acquisition_not_independent_initial_learning':True,
        'NoResidual':'Same Residual G/operations, acquired monitor removed; exact-wire response reuse only.',
        'Seed':'Unchanged common seed. Exact source-error cache only applies identical original TRAIN context, never inferred labels.',
        'fallback_reported_not_executed':True,'new_full_training_DEV_TEST':False,'goal_complete':False}
    dest=OUT/'fixed_validation/protocol.json'
    immutable_json(dest,current)
    for q in paths:
        target=OUT/'fixed_validation/source_snapshot'/q.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert target.read_bytes()==q.read_bytes()
        else:target.write_bytes(q.read_bytes())
    for name,h in current['source_sha256'].items():assert sha(ROOT/name)==h
    return current


def validation():
    p=freeze();folder=OUT/'fixed_validation'
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=p['run_id'],
        sources={'train':p['train_sources']+p['validation_sources'],'dev':[],'test':[]},binding=digest(p))
    public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    specs={a:read(OUT/'materialized'/a/'compiled.json') for a in ARMS}
    specs['NoResidual']={**specs['Residual'],'monitor':None}
    specs['Seed']={'bundle':read(OUT/'seed.json'),'monitor':None,'lookup':'_sr_get','scope':'focus_last'}
    for arm in p['arms']:
        c=specs[arm];client=FrozenExecutor(ledger,folder,p['executor_profile'])
        client.exact_replay_roots=(folder,OUT)
        client.readiness()
        for key in p['validation_sources']:
            path=folder/arm/(key.replace(':','_')+'.json')
            if path.exists():continue
            source=public[key];pub=source['views'][0]['public']
            units,_=execution_source_units(pub['source_text'],source_spans(material_public(pub)))
            def save(event):
                identity=event.get('call_id',digest(event))
                immutable_json(folder/arm/'events'/(digest(identity)+'.json'),event)
            result=execute(client,p['run_id']+':'+arm+':'+key,key,c['bundle'],pub['source_text'],units,
                scope=c['scope'],lookup=c['lookup'],monitor=c['monitor'],save_event=save)
            row=source_record(c['bundle'],source,result);immutable_json(path,row)
            print(json.dumps({'arm':arm,'source':key,'read':result['answered_queries'],
                'corrections':result['learned_corrections'],'roots':len(row['interpretation']['roots']),
                'core':sum(v['core_executed'] for v in row['views']),
                'correct':sum(bool(v['score'] and v['score']['correct']) for v in row['views']),
                'physical':sum(not e['result'].get('cache_hit',False) for e in result['events'] if e['kind']=='neural')}),flush=True)
    immutable_json(folder/'completed.json',{'arms':p['arms'],'sources':p['validation_sources'],
        'source_semantic_review_pending':True,'goal_complete':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['materialize','offline','validate']);a=parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_residual_reader_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'materialize':materialize,'offline':offline,'validate':validation}[a.stage]()
