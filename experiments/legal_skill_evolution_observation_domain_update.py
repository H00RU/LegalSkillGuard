"""Learn source-dependent read constraints from the actual kinship misread.

This finite continuation updates an observation contract, not a law or a label.
Both teachers can learn the same source-domain program. Actual acquisition and
selection use frozen-8B executions; cross-case reuse stays original TRAIN.
"""
from copy import deepcopy
import argparse
import ast
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

import jsonschema

from experiments import legal_skill_evolution_relation_contract_learning as parent
from experiments import legal_skill_evolution_source_selection_lineage as lineage
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_observation_contract import validate,split,schema,constrained_read_schema,forward
from legal_skill_guard.skill_evolution.case_observation_contract import validate_adapter
from legal_skill_guard.skill_evolution.observation_component_library import retained_family_context,component_value
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs

ROOT=parent.ROOT
RUN='legal_skill_evolution_observation_domain_context_20261115'
OUT=ROOT/'artifacts'/RUN
GENERATION=ROOT/'artifacts/legal_skill_evolution_observation_domain_update_20261115'
PREVIOUS=ROOT/'artifacts/legal_skill_evolution_observation_domain_scoped_20261115'
COMPONENT='family_relationship_residence'
def read(path):return json.loads(path.read_text())


def prepare():
    old=read(PREVIOUS/'protocol.json');public,kernels=parent.previous.data()
    acquisition=old['acquisition_sources']
    # Chosen by existing original TRAIN order and native kinship dependence,
    # before proposals. Both cases have appeared in the old B8 history.
    reuse=[s for s in public if any(':'+prefix in s for prefix in ('5c29a3a2','a51930fd'))]
    assert len(reuse)==2 and not set(reuse)&set(acquisition)
    task=read(GENERATION/'teacher_task.json')
    immutable_json(OUT/'teacher_task.json',task)
    for arm in ('Method','FreeTeacher'):
        immutable_json(OUT/arm/'teacher.json',read(GENERATION/arm/'teacher.json'))
    grading={}
    train_tasks=sorted(parent.previous.train.OUT.glob('B*/teacher_task.json'))
    train_tasks.append(ROOT/'artifacts/legal_skill_evolution_mixed_component_training_source_review_20261115/B1/teacher_task.json')
    for file in train_tasks:
        for case in read(file)['acquisition_cases']:
            if case['source']in acquisition+reuse:
                value=case['original_TRAIN_supervision']
                if case['source']in grading:assert grading[case['source']]==value
                grading[case['source']]=value
    assert set(grading)==set(acquisition+reuse)
    immutable_json(OUT/'TRAIN_grading.json',grading)
    context=retained_family_context(read(parent.BASE))
    immutable_json(OUT/'retained_context_component.json',context)
    views={};origins=[]
    original=read(ROOT/'artifacts/legal_skill_evolution_residence_scope_recovery_20261115/FreeGlobalUpdate/result.json')
    views[original['source']]=original['adapted_observation'][COMPONENT]['views'][0]
    origins.append({'source':original['source'],'artifact':'artifacts/legal_skill_evolution_residence_scope_recovery_20261115/FreeGlobalUpdate/result.json'})
    raw_file=ROOT/'artifacts/legal_skill_evolution_mixed_component_training_validated_updates_20261115/component_reads/ffa1c146c0169272ff7e8f812e00e3d01f856182c1099cced8f0db5e6089dcb4.json'
    raw=read(raw_file);assert ':a51930fd'in raw['source']and raw.get('receipt')and not raw.get('error')
    views[raw['source']]=raw['value'][COMPONENT]['views'][0]
    origins.append({'source':raw['source'],'artifact':str(raw_file.relative_to(ROOT))})
    projected={};vschema=json.loads(context['schema_json'])['properties']['views']['items']
    for sid,value in views.items():
        assert sid in reuse and public[sid]['split']=='train'
        view={k:deepcopy(value[k])for k in ('extraction_status','residences','births','witnesses')}
        for channel in ('residences','births'):
            fields=set(vschema['properties'][channel]['items']['properties'])
            view[channel]=[{k:v for k,v in row.items()if k in fields}for row in view[channel]]
        jsonschema.validate({'views':[view]},json.loads(context['schema_json']))
        part=component_value(read(parent.BASE),context,kernels[sid],public[sid]['views'][0]['public'],view)
        assert part['complete']and not part['reasons']
        projected[sid]={context['id']:{'views':[view]}}
    immutable_json(OUT/'retained_context_observations.json',{'observations':projected,'origins':origins,
        'common_to_all_candidates':True,'no_new_factual_values':True,'not_a_new_learning_success':True})
    old_family=next(c for c in read(parent.BASE)['components']if c['id']==COMPONENT)
    full_schema=json.loads(old_family['schema_json'])['properties']['views']['items']
    full={}
    for sid,value in views.items():
        view={k:deepcopy(value[k])for k in full_schema['properties']}
        for channel in ('relationships','residences','births'):
            fields=set(full_schema['properties'][channel]['items']['properties'])
            view[channel]=[{k:v for k,v in row.items()if k in fields}for row in view[channel]]
        jsonschema.validate({'views':[view]},json.loads(old_family['schema_json']))
        full[sid]={COMPONENT:{'views':[view]}}
    immutable_json(OUT/'original_family_cache_control.json',{'observations':full,'origins':origins,
        'strong_existing_paid_source_cache_not_new_generalization':True})
    p={k:deepcopy(old[k])for k in ('sources','teacher_profile','executor_profile','shared_native_event_encoding')}
    p.update(run_id=RUN,acquisition_sources=acquisition,fixed_reuse_sources=reuse,
        compile_finite_copy_obligations=True,stop_without_supported_demand=True,
        original_TRAIN_only=True,no_new_full_training_DEV_TEST=True,goal_complete=False,
        finite_source_domain_update=True,ledger_before=lineage.ledger_snapshot())
    p['teacher_generation_run']=GENERATION.name
    p['compilation_change']='Literal character folding and regex delimiter escaping; raw proposals unchanged'
    p['routing_change']='Typed event-key pullback and observed native aliases; both controls share current unresolved-component identification'
    p['prior_execution_run']=PREVIOUS.name
    p['context_restore']='Retain acquired residence/birth loops and paid source observations; all candidates share them'
    files=[Path(__file__),Path(parent.__file__),OUT/'teacher_task.json',OUT/'TRAIN_grading.json',
           OUT/'retained_context_component.json',OUT/'retained_context_observations.json']
    files.append(OUT/'original_family_cache_control.json')
    files += [parent.OUT/'candidate_libraries'/(a+'/1.json')for a in ('Method','FreeTeacher')]
    files += sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for file in files:
        target=OUT/'source_snapshot'/file.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
    # Exact old source reads are reusable if messages/schema/prior also match.
    for folder in ('component_reads','relation_reads'):
        for file in (PREVIOUS/folder).glob('*.json'):
            target=OUT/folder/file.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
    # One-time import of the actual raw JSON text. immutable_json sorts object
    # keys, which must not change a resumed dependent reader's prompt bytes.
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True)as db:
        paid={}
        for identity,source,record in db.execute("select id,source,result from calls where id like '%:relation:%' and status='completed'"):
            paid.setdefault((identity.rsplit(':',1)[-1],source),[]).append((identity,json.loads(record)))
    imported=[]
    for file in (OUT/'relation_reads').glob('*.json'):
        saved=read(file)
        if saved.get('error')or 'raw_content'in saved:continue
        matches=[(identity,r)for identity,r in paid.get((file.stem,saved['source']),[])
            if r['elapsed_seconds']==saved['receipt']['elapsed_seconds']and json.loads(r['content'])==saved['value']]
        assert len(matches)==1,(file,len(matches))
        identity,r=matches[0];saved['raw_content']=r['content']
        file.write_text(json.dumps(saved,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
        imported.append({'cache':file.name,'original_physical_request':identity,'parsed_value_unchanged':True})
    immutable_json(OUT/'raw_response_cache_import.json',{'rows':imported,'new_model_calls':0,
        'original_archives_unchanged':True,'source':PREVIOUS.name})
    print(json.dumps({'acquisition':acquisition,'fixed_reuse':reuse,'task_chars':len(json.dumps(pack_programs(task)))}),flush=True)


def protocol():
    p=read(OUT/'protocol.json')
    for name,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    return p


def ledger(p):
    return EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p),teacher_concurrency=2)


def literal_characters(program):
    # The actual FreeTeacher response has a single-quoted regex character
    # class containing its delimiter. Escaping that literal character keeps
    # the regex value identical and adds no semantic rule.
    program=program.replace("[’']", "[’\\']")
    tree=ast.parse(program)
    if any(isinstance(n,ast.Name)and n.id=='chr'and isinstance(n.ctx,ast.Store)
           or isinstance(n,(ast.FunctionDef,ast.arg))and getattr(n,'name',getattr(n,'arg',None))=='chr'
           for n in ast.walk(tree)):
        raise ValueError('A shadowed character function is not a constant expression')
    class Fold(ast.NodeTransformer):
        def visit_Call(self,node):
            self.generic_visit(node)
            if isinstance(node.func,ast.Name)and node.func.id=='chr'and len(node.args)==1 and not node.keywords:
                n=node.args[0]
                if isinstance(n,ast.Constant)and type(n.value)is int and 0<=n.value<=0x10ffff:
                    return ast.copy_location(ast.Constant(value=chr(n.value)),node)
            return node
    return ast.unparse(ast.fix_missing_locations(Fold().visit(tree)))


def candidates():
    p=protocol();public,kernels=parent.previous.data();result={}
    for arm in ('Method','FreeTeacher'):
        proposal=read(OUT/arm/'teacher.json')['value'];base=json.loads(proposal['base_contract_json'])
        contracts=[base,split(base,base['relations'][0]['name'],json.loads(proposal['partitions_json']))]if arm=='Method'else[base,json.loads(proposal['alternative_contract_json'])]
        for index,contract in enumerate(contracts):
            original_program=contract.get('read_constraint_program')
            if original_program:
                contract['read_constraint_program']=literal_characters(original_program)
            validate(contract,kernels[p['acquisition_sources'][0]])
            program=contract.get('read_constraint_program')
            assert program,'This update requires an actual learned source-domain program'
            validate_adapter(program,excluded_source_ids=p['sources'])
            for node in ast.walk(ast.parse(program)):
                if isinstance(node,ast.Constant):assert node.value not in ('Alice','Bob','Charlie','Entailment','Contradiction','NotMentioned')
            lib=read(parent.OUT/'candidate_libraries'/(arm+'/1.json'));c=next(c for c in lib['components']if c['id']==COMPONENT)
            c['relation_contract']=contract;s=schema(contract);s['required']=[]
            c['schema_json']=json.dumps(record_schema({'views':{'type':'array','minItems':1,'items':s}}))
            lib['components'].append(read(OUT/'retained_context_component.json'))
            result[arm+'/'+str(index)]=lib
    return result


def validate_proposals():
    p=protocol();public,kernels=parent.previous.data();libs=candidates();rows=[]
    for name,lib in libs.items():
        contract=next(c for c in lib['components']if c['id']==COMPONENT)['relation_contract']
        for sid in p['acquisition_sources']:
            for relation in contract['relations']:
                s,receipt=constrained_read_schema(contract,relation['name'],public[sid]['views'][0]['public'],{})
                jsonschema.Draft202012Validator.check_schema(s)
                rows.append({'candidate':name,'source':sid,'relation':relation['name'],'receipt':receipt,'schema_sha256':digest(s)})
    immutable_json(OUT/'offline_proposal_validation.json',{'rows':rows,'new_model_calls':0,'validated_candidates':list(libs)})
    print(json.dumps({'validated_candidates':list(libs)}),flush=True)


def execute():
    p=protocol();public,kernels=parent.previous.data();libs=candidates();client=FrozenExecutor(ledger(p),OUT,p['executor_profile'])
    client.exact_replay_roots=[PREVIOUS,parent.OUT];acquired=[];selected={}
    initial=read(OUT/'retained_context_observations.json')['observations']
    assert(OUT/'offline_proposal_validation.json').exists()
    for name,lib in libs.items():
        immutable_json(OUT/'candidate_libraries'/(name+'.json'),lib)
        rows=[parent.run_case(client,p,name,lib,s,public[s]['views'][0]['public'],kernels[s],initial_observation=initial.get(s))for s in p['acquisition_sources']]
        acquired.append({'candidate':name,'rows':rows})
    for arm in ('Method','FreeTeacher'):
        best=min((v for v in acquired if v['candidate'].startswith(arm+'/')),key=lambda v:(-sum(r['core_correct']for r in v['rows']),
            sum(r['source_failures']for r in v['rows']),sum(x.get('elapsed_seconds')or 0 for r in v['rows']for x in r['reads']),v['candidate']))
        selected[arm]=best['candidate']
    immutable_json(OUT/'selected_before_reuse.json',{'selected':selected,'acquisition_only':True})
    reuse=[]
    for arm,name in selected.items():
        for sid in p['fixed_reuse_sources']:
            reuse.append(parent.run_case(client,p,name,libs[name],sid,public[sid]['views'][0]['public'],kernels[sid],initial_observation=initial.get(sid)))
    immutable_json(OUT/'result.json',{'acquisition':acquired,'selected':selected,'fixed_reuse':reuse,
        'goal_complete':False,'no_DEV_TEST':True,'source_domain_learning_not_itself_a_novelty_certificate':True})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','validate','execute'));args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'validate':validate_proposals,'execute':execute}[args.phase]()
