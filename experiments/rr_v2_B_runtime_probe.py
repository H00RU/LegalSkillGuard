"""Execute the learned B graph on a later original TRAIN source and saved views.

No model or reference generation occurs here. Original-input production execution
and offline re-execution of previously labelled views are reported separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import SourceLedger,digest
from legal_skill_guard.rr.engine import source_text
from legal_skill_guard.rr.horn_connectors import predict_with_library
from legal_skill_guard.rr.preflight import science_files,scientific_code_binding,score_source
from legal_skill_guard.rr.scoring import task_score


SOURCE='ProofWriter_OWA_depth5:f39b4cd5a6faf7e199c568e2487db5b6b0e27fadefef4f319d42655e4fe04d94'


def run(root,run_id):
    out=root/'artifacts/rr_method_runtime_20261107'/run_id
    files=science_files(root)
    offline=json.loads((root/'reports/rr_method_runtime_20261107/offline_multi_source_B_v1.json').read_text())
    if offline['exit_code'] or not offline['network_blocked'] or offline['files']!=files:
        raise ValueError('Current B runtime needs matching offline evidence')
    manifest=json.loads((root/'reports/rr_v2_evidence/data_manifest.json').read_text())
    packet_path=root/'data/packets/rr_v2/public_train.json'
    assert hashlib.sha256(packet_path.read_bytes()).hexdigest()==manifest['packet_sha256']['public_train']
    source=next(s for s in json.loads(packet_path.read_text())['sources'] if s['key']==SOURCE)
    assert digest(source['public'])==source['content_hash']
    oldrun=root/'artifacts/rr_v2_formal_build_20261106/run_citation_fix'
    library_file=oldrun/'B1.frozen.json';frozen=json.loads(library_file.read_text());library=frozen['content']
    assert digest(library)==frozen['sha256'] and library['frozen']
    position=manifest['formal_train_order'].index(SOURCE)+1
    positions={s:manifest['formal_train_order'].index(s)+1 for p in library['patterns'] for s in p['evidence_sources']}
    assert positions and all(p<position and p<=16 for p in positions.values())
    compatibility=json.loads((root/'reports/rr_method_runtime_20261107/prior_B1_component_compatibility.json').read_text())
    assert compatibility['library_for_later_probe']==library
    db=sqlite3.connect('file:'+str(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True)
    before={t:db.execute('select * from '+t).fetchall() for t in ('calls','meta','oracle_views')}
    assert not any(r[6]=='reserved' for r in before['calls'])
    seal={'run_id':run_id,'files':files,'code_hash':scientific_code_binding(files),'source':source,
          'source_position':position,'library_file_sha256':hashlib.sha256(library_file.read_bytes()).hexdigest(),
          'library_content_hash':frozen['sha256'],'pattern_origins':positions,'original_source_selection':'first original ProofWriter source after B1, before reading its grade',
          'new_model_calls':0,'new_reference_calls':0,'full_goal_complete':False}
    immutable_json(out/'seal.json',seal)
    if (out/'result.json').exists():return json.loads((out/'result.json').read_text())
    primary=predict_with_library(source['public'],library)
    masked=predict_with_library(source['public'],{'patterns':[]})
    # Labels are opened only after production predictions. The predictor itself
    # has no training/reference/model-client imports and receives public data.
    grade_path=root/'data/packets/rr_v2/grading_only/train.json'
    assert hashlib.sha256(grade_path.read_bytes()).hexdigest()==manifest['packet_sha256']['grading_train']
    grade=json.loads(grade_path.read_text())['sources'][SOURCE]
    score=score_source(source,{'answer':primary['answer']},grade)
    original=json.loads((oldrun/'sources'/(digest(SOURCE)+'.json')).read_text())
    view_rows=[];charged={(r[0],r[1]) for r in before['oracle_views']}
    oracle_root=root/'artifacts/rr_v2_preflight/oracle_guard/oracle_views'/digest(SOURCE)
    for row in original['learning']['oracle_views']:
        view=row['view'];key=digest(view);assert key==row['view_hash'] and (SOURCE,key) in charged
        directory=oracle_root/key
        request=json.loads((directory/'request.json').read_text())
        assert request['view']==view and request['reference_hash']==digest(grade)
        if not (directory/'result.json').exists():
            view_rows.append({'view_hash':key,'status':'preserved_reference_unavailable'});continue
        cached=json.loads((directory/'result.json').read_text())
        assert cached['view_hash']==key and cached['reference_hash']==digest(grade)
        prediction=predict_with_library(view['public'],library)
        view_rows.append({'view_hash':key,'status':'offline_reexecution_of_original_saved_view',
            'prediction':prediction,'cached_reference_answer':cached['answer'],
            'semantic_check':task_score(source['dataset'],prediction['answer'],cached['answer'])})
    ledger=SourceLedger.from_text(source_text(source))
    for use in primary['pattern_uses']:
        text=source['public']['rules'][use['rule_index']]
        use['source_units']=[c.id for c in ledger.clauses if ledger.text[c.start:c.end]==text]
    after={t:db.execute('select * from '+t).fetchall() for t in before}
    result={'run_id':run_id,'source':SOURCE,'source_position':position,
        'original_input_production_execution':primary,'original_TRAIN_semantic_check':score,
        'offline_saved_views':view_rows,'availability_negative_control':masked,
        'negative_control_is_accuracy_gain_evidence':False,'pattern_origins':positions,
        'same_bank_use':True,'cross_bank_use':False,
        'historical_same_pattern_rediscovery_at_target':original['learning']['learned_pattern'] is not None,
        'new_model_calls':0,'new_oracle_views':0,'new_reference_labels':0,
        'ledger_unchanged':before==after,'bound_files_unchanged':files==science_files(root),
        'frozen_library_bytes_unchanged':hashlib.sha256(library_file.read_bytes()).hexdigest()==seal['library_file_sha256'],
        'B_component_accepted':primary['status']=='closure_complete' and score['task_correct'] and
            any(u['query_relevant'] for u in primary['pattern_uses']) and not primary['fallback_used'] and
            all(v.get('semantic_check',{}).get('correct',False) for v in view_rows),
        'full_goal_complete':False,'full_fixed128_build_complete':False,'DEV_complete':False,
        'predefined_components_not_counted_as_learning':primary['predefined_components']}
    immutable_json(out/'result.json',result)
    immutable_json(root/'reports/rr_method_runtime_20261107'/('B_runtime_'+run_id+'.json'),result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args()
    result=run(Path(__file__).resolve().parents[1],args.run_id)
    print(json.dumps({'source':result['source'],'B_component_accepted':result['B_component_accepted'],
        'answer':result['original_input_production_execution']['answer'],
        'actual_stored_graph_calls':len(result['original_input_production_execution']['pattern_uses']),
        'saved_views':len(result['offline_saved_views']),'new_model_calls':0,'full_goal_complete':False}))


if __name__=='__main__':main()
