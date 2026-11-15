"""One finite correction of actual TRAIN copy violations, with matched controls.

No new teacher or proposal selection. Preserve the parent experiment's selected
contracts; apply the common source-copy grammar to Method, NoSplit and Free.
The existing fixed reuse sources and all negative outcomes remain unchanged.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shutil

import jsonschema

from experiments import legal_skill_evolution_relation_contract_learning as parent
from experiments import legal_skill_evolution_source_selection_lineage as lineage
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_observation_contract import source_copy_schema, schema

ROOT=parent.ROOT
RUN='legal_skill_evolution_relation_reader_refinement_20261115'
OUT=ROOT/'artifacts'/RUN


def prepare():
    p=parent.read(parent.OUT/'protocol.json')
    assert parent.read(parent.OUT/'result.json')['selected']=={'Method':'Method/1','FreeTeacher':'FreeTeacher/1'}
    p.update(run_id=RUN,parent_protocol_sha256=hashlib.sha256((parent.OUT/'protocol.json').read_bytes()).hexdigest(),
        original_selected_contracts_unchanged=True,new_teacher_calls=0,
        compile_finite_copy_obligations=True,stop_without_supported_demand=True,
        comparison_candidates=['Method/0','Method/1','FreeTeacher/1'],
        same_fixed_sources_no_new_validation_rescan=True,
        previous_reuse_already_observed=True,ledger_before=lineage.ledger_snapshot())
    files=[Path(__file__),Path(parent.__file__)]+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    files += [parent.OUT/'candidate_libraries'/(name+'.json') for name in p['comparison_candidates']]
    files += [parent.OUT/'TRAIN_grading.json']
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    immutable_json(OUT/'TRAIN_grading.json',parent.read(parent.OUT/'TRAIN_grading.json'))
    for f in files:
        dest=OUT/'source_snapshot'/f.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest)
    # Existing raw failures are the regression. A source-present finite cue
    # stays allowed; a hallucinated reciprocal cue becomes unrepresentable.
    public,kernels=parent.previous.data();regressions=[]
    for file in sorted((parent.OUT/'cases').glob('*/*/*.json')):
        row=parent.read(file)
        lib=parent.read(parent.OUT/'candidate_libraries'/(row['candidate']+'.json'))
        for comp in lib['components']:
            if 'relation_contract'not in comp:continue
            observed=row['observation'].get(comp['id'],{}).get('views',[{}])[0]
            for name,value in observed.items():
                old=schema(comp['relation_contract'],[name]);new=source_copy_schema(comp['relation_contract'],[name],public[row['source']]['views'][0]['public']['facts'])
                jsonschema.validate({name:value},old)
                try:
                    jsonschema.validate({name:value},new);accepted=True
                except jsonschema.ValidationError:accepted=False
                regressions.append({'source':row['source'],'candidate':row['candidate'],'relation':name,
                    'raw_response_unchanged':True,'old_schema_accepts':True,'copy_grammar_accepts':accepted,
                    'schema_changed':old!=new})
    assert any(not r['copy_grammar_accepts']for r in regressions)
    immutable_json(OUT/'offline_real_failure_regression.json',{'rows':regressions,
        'no_facts_or_semantic_rules_added':True,'new_model_calls':0})
    # Paid exact reads with unchanged prompts/schema are shared; their actual
    # generation cost remains recorded, rather than charged a second time.
    for folder in ('component_reads','relation_reads'):
        for file in (parent.OUT/folder).glob('*.json'):
            dest=OUT/folder/file.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)


def execute():
    p=parent.read(OUT/'protocol.json')
    for name,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p),teacher_concurrency=2)
    client=FrozenExecutor(ledger,OUT,p['executor_profile']);client.exact_replay_roots=[parent.OUT]
    public,kernels=parent.previous.data();rows=[]
    for name in p['comparison_candidates']:
        library=parent.read(parent.OUT/'candidate_libraries'/(name+'.json'))
        for sid in p['acquisition_sources']+p['fixed_reuse_sources']:
            rows.append(parent.run_case(client,p,name,library,sid,public[sid]['views'][0]['public'],kernels[sid]))
    same_contract=[]
    library=parent.read(parent.OUT/'candidate_libraries/Method/1.json')
    for sid in p['fixed_reuse_sources']:
        same_contract.append(parent.run_case(client,p,'Method/1',library,sid,public[sid]['views'][0]['public'],kernels[sid],policy='ordinary'))
    immutable_json(OUT/'result.json',{'rows':rows,'same_contract_ordinary':same_contract,
        'generic_original_unchanged':str(parent.OUT/'fixed_generic'),
        'new_teacher_calls':0,'new_sources':0,'goal_complete':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','execute'));args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'execute':execute}[args.phase]()
