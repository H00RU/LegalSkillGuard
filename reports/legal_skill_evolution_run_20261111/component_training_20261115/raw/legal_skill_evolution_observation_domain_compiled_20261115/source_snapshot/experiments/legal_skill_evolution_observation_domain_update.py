"""Learn source-dependent read constraints from the actual kinship misread.

This finite continuation updates an observation contract, not a law or a label.
Both teachers can learn the same source-domain program. Actual acquisition and
selection use frozen-8B executions; cross-case reuse stays original TRAIN.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import argparse
import ast
import fcntl
import hashlib
import json
from pathlib import Path
import shutil

import jsonschema

from experiments import legal_skill_evolution_relation_contract_learning as parent
from experiments import legal_skill_evolution_source_selection_lineage as lineage
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor,FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_observation_contract import validate,split,schema,constrained_read_schema,forward
from legal_skill_guard.skill_evolution.case_observation_contract import validate_adapter
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs,INSTRUCTION,PROGRAM_INSTRUCTION

ROOT=parent.ROOT
RUN='legal_skill_evolution_observation_domain_compiled_20261115'
OUT=ROOT/'artifacts'/RUN
GENERATION=ROOT/'artifacts/legal_skill_evolution_observation_domain_update_20261115'
PREVIOUS=ROOT/'artifacts/legal_skill_evolution_relation_reader_refinement_20261115'
COMPONENT='family_relationship_residence'
OUTPUT=record_schema({'rationale':{'type':'string'},'base_contract_json':{'type':'string'},
                     'partitions_json':{'type':'string'},'alternative_contract_json':{'type':'string'}})
SYSTEM='''Continue the SAME observation-contract learning task, not a new method search.
No tools. The frozen weak reader now correctly copied the father cue but then
put WORK dates into the KINSHIP period. The ordinary contract recovered roles
but left the optional kinship dates unrepresented, so the author program could
not close that lookup. Fix this actual failure without changing the law, source
checks or labels. Work dates do not state kinship dates, and residence/marriage
periods must also remain attached to their own actual events.

Return the supplied executable relation-contract format for the FAMILY component
only. Preserve supported family meanings, use shared source keys, and represent
optional relationship dates without fabricating dates or residence. The existing
service component and unrelated library entries are retained. Do not claim to
cover a source meaning your rules cannot express. Public native factual vocabulary
and the complete runtime are supplied. Source facts only; no question, legal query,
source ID, native answer, previous case or annotation is a runtime factual input.

You may add read_constraint_program to the contract. It defines pure
apply(inputs,premises), with prebound re and no imports/IO/classes/nested functions,
recursion/reflection. inputs has ONLY facts, requested_relation, record_fields,
actual_prior_source_records. Return EXACTLY {status:constrained|unread,
domains:[{field:<existing non-key field>,values:[<allowed scalar or null>]}],
witnesses:[{field:facts,quote:<exact current source quote>}]}.
An unread program returns no domains. Each nonempty domain must conform to the
current field's type/enum and literal-copy obligations. The program cannot assert
native facts, specify a key, insert source-absent strings or declare a native
answer. Null restrictions are learned, fallible claims of source absence and need
an actual exhaustive grammatical scan; they are NOT defaults when attachment is
ambiguous. Leave unsupported constructions unread and unrestricted. Do not force
all dates to null: a source can expressly date a relationship. Do not hardcode
training people, sources, dates/years, whole sentences or native answer strings.
General lexical/syntactic cues are allowed. Use record_fields to preserve one
program's meaning across the coupled and split reading units. A complete view
still enumerates every source relationship with stable keys and source witnesses.

Method: base_contract_json is ONE initially coupled relation with its actual
fields and complete positive transduction. partitions_json is a list of field
partitions in the supplied split API, grouping by the actual error/dependencies.
The host constructs the split alternative and selects by actual weak-reader
acquisition execution, not by an assumed preference. alternative_contract_json={}
as a JSON string. The same learned domain program applies to both candidates.

FreeTeacher: independently return your TWO strongest complete contracts in
base_contract_json and alternative_contract_json. You may choose the identical
decomposed architecture and source-domain program capability; do not omit period
coverage or stay coupled just to weaken the control. partitions_json=[]. Both
arms receive the same complete acquisition facts, prior components, failures,
feedback, runtime abilities, model and proposal/selection budget. Ordinary teacher
repair may absorb the effect; correctness and actual reuse decide.
'''


def read(path):return json.loads(path.read_text())


def prepare():
    old=read(PREVIOUS/'protocol.json');public,kernels=parent.previous.data()
    acquisition=old['acquisition_sources']
    # Chosen by existing original TRAIN order and native kinship dependence,
    # before proposals. Both cases have appeared in the old B8 history.
    reuse=[s for s in public if any(':'+prefix in s for prefix in ('5c29a3a2','a51930fd'))]
    assert len(reuse)==2 and not set(reuse)&set(acquisition)
    libraries={a:read(parent.OUT/'candidate_libraries'/(a+'/1.json'))for a in ('Method','FreeTeacher')}
    failures=[]
    for file in sorted((PREVIOUS/'cases').glob('*/*/residual_*.json')):
        row=read(file)
        if row['source']in acquisition:failures.append(row)
    task={'current_components_both_arms':{a:next(c for c in lib['components']if c['id']==COMPONENT)for a,lib in libraries.items()},
        'actual_weak_read_failures':failures,
        'acquisition_sources':[{'source':s,'facts':public[s]['views'][0]['public']['facts'],
            'native_factual_vocabulary':kernels[s]['fact_arities']}for s in acquisition],
        'source_feedback':'Bob is Alice\'s father. The interval explicitly modifies work, not fatherhood or a shared residence. The other source states domestic work in her home but no kinship.',
        'relational_observation_contract.py':(ROOT/'legal_skill_guard/skill_evolution/relational_observation_contract.py').read_text(),
        'prior_B8_exposure_disclosed_not_blind':True,'reuse_cases_not_in_this_teacher_task':True}
    immutable_json(OUT/'teacher_task.json',task)
    assert task==read(GENERATION/'teacher_task.json'),'Reuse only the exact actual teacher input'
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
    p={k:deepcopy(old[k])for k in ('sources','teacher_profile','executor_profile','shared_native_event_encoding')}
    p.update(run_id=RUN,acquisition_sources=acquisition,fixed_reuse_sources=reuse,
        compile_finite_copy_obligations=True,stop_without_supported_demand=True,
        original_TRAIN_only=True,no_new_full_training_DEV_TEST=True,goal_complete=False,
        finite_source_domain_update=True,ledger_before=lineage.ledger_snapshot())
    p['teacher_generation_run']=GENERATION.name
    p['compilation_change']='Constant-fold unshadowed chr(integer literal); no new runtime capability or semantic repair'
    files=[Path(__file__),Path(parent.__file__),OUT/'teacher_task.json',OUT/'TRAIN_grading.json']
    files += [parent.OUT/'candidate_libraries'/(a+'/1.json')for a in libraries]
    files += sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for file in files:
        target=OUT/'source_snapshot'/file.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
    # Exact old source reads are reusable if messages/schema/prior also match.
    for folder in ('component_reads','relation_reads'):
        for file in (PREVIOUS/folder).glob('*.json'):
            target=OUT/folder/file.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
    print(json.dumps({'acquisition':acquisition,'fixed_reuse':reuse,'task_chars':len(json.dumps(pack_programs(task)))}),flush=True)


def protocol():
    p=read(OUT/'protocol.json')
    for name,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    return p


def ledger(p):
    return EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p),teacher_concurrency=2)


def acquire():
    p=protocol();l=ledger(p);task=read(OUT/'teacher_task.json')
    def one(arm):
        target=OUT/arm/'teacher.json'
        if target.exists():return
        value=FrozenTeacher(l,OUT,p['teacher_profile']).propose(RUN+':'+arm+':domain_update',source_ids=p['acquisition_sources'],
            system_prompt=SYSTEM+'\nYour arm: '+arm+'\n'+INSTRUCTION+'\n'+PROGRAM_INSTRUCTION,
            user_prompt=json.dumps(pack_programs(task),ensure_ascii=False,separators=(',',':')),output_schema=OUTPUT)
        immutable_json(target,value);print(json.dumps({'teacher_saved':arm}),flush=True)
    with ThreadPoolExecutor(max_workers=2)as pool:
        jobs=[pool.submit(one,a)for a in ('Method','FreeTeacher')]
        for job in jobs:job.result()


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
    assert(OUT/'offline_proposal_validation.json').exists()
    for name,lib in libs.items():
        immutable_json(OUT/'candidate_libraries'/(name+'.json'),lib)
        rows=[parent.run_case(client,p,name,lib,s,public[s]['views'][0]['public'],kernels[s])for s in p['acquisition_sources']]
        acquired.append({'candidate':name,'rows':rows})
    for arm in ('Method','FreeTeacher'):
        best=min((v for v in acquired if v['candidate'].startswith(arm+'/')),key=lambda v:(-sum(r['core_correct']for r in v['rows']),
            sum(r['source_failures']for r in v['rows']),sum(x.get('elapsed_seconds')or 0 for r in v['rows']for x in r['reads']),v['candidate']))
        selected[arm]=best['candidate']
    immutable_json(OUT/'selected_before_reuse.json',{'selected':selected,'acquisition_only':True})
    reuse=[]
    for arm,name in selected.items():
        for sid in p['fixed_reuse_sources']:
            reuse.append(parent.run_case(client,p,name,libs[name],sid,public[sid]['views'][0]['public'],kernels[sid]))
    immutable_json(OUT/'result.json',{'acquisition':acquired,'selected':selected,'fixed_reuse':reuse,
        'goal_complete':False,'no_DEV_TEST':True,'source_domain_learning_not_itself_a_novelty_certificate':True})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','validate','execute'));args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'acquire':acquire,'validate':validate_proposals,'execute':execute}[args.phase]()
