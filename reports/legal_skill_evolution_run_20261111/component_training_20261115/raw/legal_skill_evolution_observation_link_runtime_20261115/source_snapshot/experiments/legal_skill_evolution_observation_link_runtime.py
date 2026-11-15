"""Execute the actual link proposals after exact envelope/closure lowering."""
import argparse
import ast
import builtins
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import re
import symtable

from experiments import legal_skill_evolution_observation_link_update as generation
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema,grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.case_observation_contract import validate_adapter
from legal_skill_guard.skill_evolution.relational_observation_contract import validate,schema

ROOT=generation.ROOT
RUN='legal_skill_evolution_observation_link_runtime_20261115'
OUT=ROOT/'artifacts'/RUN


def lower_actual_closures(program):
    tree=ast.parse(program);main=next(n for n in tree.body if n.name=='apply')
    nested=[n for n in main.body if isinstance(n,ast.FunctionDef)]
    if not nested:return program,[]
    assert len(tree.body)==1 and {n.name for n in nested}<={'unique','rows','clauses'}
    symbols=symtable.symtable(program,'<actual-reader>','exec').get_children()[0]
    captures={s.get_name():sorted(x.get_name()for x in s.get_symbols()if x.is_free())
        for s in symbols.get_children()if s.get_type()=='function'}
    captures={n.name:captures[n.name]for n in nested}
    assert all(set(names)<={'facts','prior'}for names in captures.values())
    for helper in nested:
        assert not helper.decorator_list and not helper.args.defaults and not helper.args.vararg and not helper.args.kwarg
        helper.name='acquired_'+helper.name
        helper.args.args=[ast.arg(arg=n)for n in captures[helper.name.removeprefix('acquired_')]]+helper.args.args
    main.body=[n for n in main.body if n not in nested]
    tree.body=nested+[main]
    class Calls(ast.NodeTransformer):
        def visit_Call(self,node):
            self.generic_visit(node)
            if isinstance(node.func,ast.Name)and node.func.id in captures:
                name=node.func.id;node.func.id='acquired_'+name
                node.args=[ast.Name(id=n,ctx=ast.Load())for n in captures[name]]+node.args
            return node
    value=ast.unparse(ast.fix_missing_locations(Calls().visit(tree)))
    validate_adapter(value)
    return value,[{'function':name,'explicit_captures':values}for name,values in captures.items()]


def program_equivalence(original,lowered,probes):
    names=('min','max','sum','len','abs','round','sorted','all','any','int','float','bool','str','repr',
        'list','dict','set','tuple','range','enumerate','zip','isinstance','ValueError','KeyError','TypeError','Exception','type')
    outputs=[]
    for program in (original,lowered):
        scope={'__builtins__':{n:getattr(builtins,n)for n in names},'re':re}
        exec(compile(program,'<reviewed-pure-reader>','exec'),scope)
        outputs.append([scope['apply'](deepcopy(p),{})for p in probes])
    assert outputs[0]==outputs[1]
    return outputs[0]


def prepare():
    old=generation.stage.read(generation.OUT/'protocol.json')
    for f,sha in old['source_sha256'].items():
        assert hashlib.sha256((generation.OUT/'source_snapshot'/f).read_bytes()).hexdigest()==sha,f
    public,kernels=generation.stage.acquired.runtime.previous.data();candidates={};receipts=[]
    for arm in ('Method','FreeTeacher'):
        base=generation.stage.read(generation.OUT/arm/'initial_library.json');candidates[arm+'/Before']=base
        value=generation.stage.read(generation.OUT/arm/'teacher.json')['value'];updated=deepcopy(base)
        edits=value['component_updates'];assert len(edits)==2 and {e['id']for e in edits}==generation.TARGETS
        for e in edits:
            parsed=json.loads(e['contract_json']);original=deepcopy(parsed)
            wrapped='relation_contract'in parsed
            if wrapped:
                assert parsed['id']==e['id']and parsed['complete_native_families']==[]and parsed['facts_only']is True
                parsed=deepcopy(parsed['relation_contract'])
            program=parsed.get('read_constraint_program')
            closure_receipt=[];probes=[];outputs=[]
            if program:
                lowered,closure_receipt=lower_actual_closures(program)
                validate_adapter(lowered,excluded_source_ids=old['sources'])
                for sid in old['acquisition_sources']:
                    previous=next(generation.stage.read(f)for f in(generation.PARENT/'native_residual'/
                        ('MethodProjected'if arm=='Method'else 'FreeTeacher')).glob('*.json')
                        if generation.stage.read(f)['source']==sid)
                    prior=deepcopy(previous['observation'].get(e['id'],{'views':[{}]})['views'][0])
                    prior['observed_related_source_events']=[{'component':cid,'facts':r['converted']['facts']}
                        for cid,rs in previous['execution']['component_conversions'].items()if cid!=e['id']
                        for r in rs if r['trusted_complete_observation']]
                    for group in parsed['relations']:
                        probes.append({'facts':public[sid]['views'][0]['public']['facts'],
                            'requested_relation':group['name'],'record_fields':group['fields'],
                            'actual_prior_source_records':prior})
                outputs=program_equivalence(program,lowered,probes)
                parsed['read_constraint_program']=lowered
            validate(parsed,kernels[old['acquisition_sources'][0]])
            c=next(c for c in updated['components']if c['id']==e['id']);c['relation_contract']=parsed
            shape=schema(parsed);shape['required']=[]
            c['schema_json']=json.dumps(record_schema({'views':{'type':'array','minItems':1,'items':shape}}))
            receipts.append({'arm':arm,'component':e['id'],'original_contract_json':e['contract_json'],
                'original_parsed':original,'unwrapped_component_envelope':wrapped,'closure_lowering':closure_receipt,
                'original_program':program,'lowered_program':parsed.get('read_constraint_program'),
                'actual_input_probes':probes,'identical_original_and_lowered_outputs':outputs,
                'semantic_literals_added':False,'new_model_calls':0})
        candidates[arm+'/Updated']=updated
    for name,lib in candidates.items():immutable_json(OUT/'libraries'/(name+'.json'),lib)
    immutable_json(OUT/'offline_lowering_evidence.json',receipts)
    immutable_json(OUT/'TRAIN_grading.json',generation.stage.read(generation.OUT/'TRAIN_grading.json'))
    p={k:deepcopy(v)for k,v in old.items()if k!='source_sha256'}
    p.update(run_id=RUN,teacher_run=generation.RUN,shared_pure_ABI_additions=['float.is_integer','Exception'],
        rejected_initial_proposals_preserved=True,no_teacher_retry=True)
    for channel in ('relation_reads','component_reads'):
        for f in(generation.OUT/channel).glob('*.json'):immutable_json(OUT/channel/f.name,generation.stage.read(f))
    files=[Path(__file__),Path(generation.stage.actor.__file__),OUT/'offline_lowering_evidence.json',OUT/'TRAIN_grading.json']
    files+=sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))+sorted((OUT/'libraries').glob('*/*.json'))
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    print(json.dumps({'prepared':RUN,'libraries':list(candidates),'new_model_calls':0}),flush=True)


def protocol():
    p=generation.stage.read(OUT/'protocol.json')
    for f,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==sha,f
    return p


def execute():
    p=protocol();public,kernels=generation.stage.acquired.runtime.previous.data()
    libs={str(f.relative_to(OUT/'libraries')).removesuffix('.json'):generation.stage.read(f)
        for f in(OUT/'libraries').glob('*/*.json')}
    client=FrozenExecutor(EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN,sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p)),OUT,p['executor_profile'])
    rows=[]
    for name,lib in sorted(libs.items()):
        for sid in p['acquisition_sources']:
            row=generation.stage.actor.execute_one(client,p,name,lib,sid,kernels[sid],public[sid],'acquisition',purpose='skill_actor')
            rows.append(graded(row,sid,name,'acquisition',public))
    selected={a:min([a+'/Before',a+'/Updated'],key=lambda name:(
        -sum(r['core_correct']for r in rows if r['condition']==name),name.endswith('/Updated')))
        for a in ('Method','FreeTeacher')}
    immutable_json(OUT/'selected_before_reuse.json',{'selected':selected,'acquisition_only':True})
    for arm,name in selected.items():
        if name.endswith('/Before'):continue  # No unchanged-library validation masquerades as learning.
        for sid in p['fixed_reuse_sources']:
            row=generation.stage.actor.execute_one(client,p,name,libs[name],sid,kernels[sid],public[sid],'reuse',purpose='skill_actor')
            rows.append(graded(row,sid,name,'reuse',public))
    name=selected['Method']
    if name.endswith('/Updated'):
        ordinary=deepcopy(p);ordinary['native_read_policy']='direct_inputs_first'
        for sid in p['fixed_reuse_sources']:
            row=generation.stage.actor.execute_one(client,ordinary,name,libs[name],sid,kernels[sid],public[sid],'ordinary_reuse',purpose='skill_actor')
            rows.append(graded(row,sid,name,'ordinary_reuse',public))
    immutable_json(OUT/'result.json',{'rows':rows,'selected':selected,'goal_complete':False})


def graded(row,sid,name,phase,public):
    grading=generation.stage.read(OUT/'TRAIN_grading.json');result=row['execution']
    score=grade_view(public[sid]['dataset'],public[sid]['views'][0],grading[sid][public[sid]['views'][0]['id']],result['answer'])
    failures=sum(w['source_review']['failures']for w in result.get('binding_executions',[]))
    v={'source':sid,'condition':name,'phase':phase,'score':score,'source_failures':failures,
        'core_correct':result['handled']and score['correct']and not failures,'reads':len(row['reads'])}
    immutable_json(OUT/'graded'/phase/name/(digest(sid)+'.json'),v);print(json.dumps(v),flush=True)
    return v


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','execute']);args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        prepare()if args.phase=='prepare'else execute()
