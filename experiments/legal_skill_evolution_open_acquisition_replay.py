"""Replay existing actual TRAIN readings through the new interface, no APIs.

This checks information retention, typed rendering and unchanged native consumer
execution. The identity composition is a public wiring control, not a learned
legal mechanism or new efficacy experiment. No teacher or executor is imported.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

import clingo

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_learning import execute_composition
from legal_skill_guard.skill_evolution.scoped_grammar import constructors,material_public,term_sort
from legal_skill_guard.skill_evolution.scoped_reader import apply_current
from legal_skill_guard.skill_evolution.semantic_operations import prepare_queries
from legal_skill_guard.skill_evolution.source_composition import render_composition
from legal_skill_guard.skill_evolution.source_observations import (
    decode_visible_inputs,encode_source_observations,fact,signatures)
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units,expand_unit_support

ROOT=Path(__file__).resolve().parents[1]
SOURCE='ContractNLI:354623271a5433b9d6fe42ec70538acd25e9f7e37aee568c81e2e7d4912f9450'
read=lambda p:json.loads(p.read_text())


def ledger_snapshot():
    con=sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True)
    try:
        calls=con.execute('select * from calls order by id').fetchall()
        oracles=con.execute('select * from oracle_views order by rowid').fetchall()
        meta=con.execute('select * from meta order by rowid').fetchall()
        return {'calls_sha256':digest(calls),'oracle_views_sha256':digest(oracles),'meta_sha256':digest(meta),
            'rows':len(calls),'by_role':dict(con.execute('select role,count(*) from calls group by role')),
            'by_status':dict(con.execute('select status,count(*) from calls group by status'))}
    finally:con.close()


def run(out):
    public_path=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    bundle_path=ROOT/'artifacts/legal_skill_evolution_semantic_operations_v2_20261113/focused_execution_v2/LearnedOperations/bundle.json'
    result_path=ROOT/'reports/legal_skill_evolution_run_20261111/reader_operation_evidence/raw/constructive/focused_execution_v2/smoke/LearnedOperations'/(SOURCE.replace(':','_')+'.json')
    original_paths=[public_path,bundle_path,result_path]
    original_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in original_paths}
    before=ledger_snapshot();source=next(s for s in read(public_path) if s['key']==SOURCE)
    if source['split']!='train':raise ValueError('Existing original TRAIN only')
    bundle=read(bundle_path);old=read(result_path);runtime=old['runtime'];pub=source['views'][0]['public']
    spans=source_spans(material_public(pub));units,supports=execution_source_units(pub['source_text'],spans)
    plan=prepare_queries(bundle['program'],bundle['operations'],pub['source_text'],units)
    assert plan==runtime['query_plan']
    encoded=encode_source_observations(SOURCE,source_text=pub['source_text'],units=units,
        source_output=runtime['source_output'],operations=bundle['operations'],queries=plan,
        answers=runtime['semantic_answers'],scope='focus_last')
    assert decode_visible_inputs(encoded)==encoded['visible_inputs']
    x={'var':'X'}
    language={'signatures':{**signatures(),'keep_root':{'arguments':['term'],'kind':'output'}},
        'constants':{},'rules':[{'id':'identity','head':fact('keep_root',x),'body':[fact('legacy_root',x)],'cost':1}]}
    result=execute_composition(language,['identity'],encoded['context'])
    rendered=render_composition(language,[],encoded,result,bundle['spec'])
    assert rendered['statements']==runtime['source_output']['statements']
    nodes=[];schema=constructors(bundle['spec'])
    for i,row in enumerate(rendered['statements']):
        nodes.append({'id':i,'sort':term_sort(row['term'],schema),'term':row['term'],
            'support_ids':expand_unit_support(row['support_ids'],supports),'child_ids':[],
            'ambiguous':False,'source_semantics_verified':False})
    interpretation={'nodes':nodes,'roots':list(range(len(nodes))),
        'source_program_output':{k:rendered[k] for k in ('statements','complete','unresolved')},
        'complete':False,'unresolved':rendered['unresolved']}
    views=[]
    for view in source['views']:
        now=apply_current(bundle['spec'],{'rules':[],'disabled_rules':[],'acquired_pairs':[]},interpretation,view)
        previous=next(v for v in old['views'] if v['view']==view['id'])['execution']
        assert now==previous
        views.append({'view':view['id'],'execution':now,'identical_to_original':True})
    after=ledger_snapshot();assert before==after
    assert original_hashes=={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in original_paths}
    receipt={'source':SOURCE,'split':'original_train','original_files_sha256':original_hashes,
        'entire_g_input_roundtrip':True,'planned_queries':len(plan),'actual_answers':len(runtime['semantic_answers']),
        'unknown_groups_including_unread':len(encoded['context']['unknown_groups']),
        'actual_original_root_count':len(rendered['statements']),'views':views,
        'raw_text_and_all_semantic_literals_retained':True,'clingo_version':clingo.__version__,
        'identity_wiring_control_not_learned_G':True,'source_semantics_or_contribution_certified':False,
        'no_new_train_examples_or_model_calls':True,'ledger_before':before,'ledger_after':after,
        'goal_complete':False}
    immutable_json(out/'observations.json',encoded);immutable_json(out/'execution.json',result)
    immutable_json(out/'rendered.json',rendered);immutable_json(out/'receipt.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('source','planned_queries','actual_answers',
        'unknown_groups_including_unread','actual_original_root_count','clingo_version','goal_complete')},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,
        default=ROOT/'artifacts/legal_skill_evolution_open_acquisition_20261113/replay')
    run(parser.parse_args().out)
