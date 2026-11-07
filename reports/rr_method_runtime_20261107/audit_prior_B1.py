"""Read-only component compatibility check; never queries a new label/model."""
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import parameterize_graph
from legal_skill_guard.rr.source_learning import learn_source


def denied(*args,**kwargs):raise RuntimeError('No new network, process or reference query in this audit')


def main():
    root=Path(__file__).resolve().parents[2]
    manifest=json.loads((root/'reports/rr_v2_evidence/data_manifest.json').read_text())
    public={s['key']:s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']}
    grade=json.loads((root/'data/packets/rr_v2/grading_only/train.json').read_text())['sources']
    cfg=json.loads((root/'configs/rr_v2_formal.json').read_text())
    origin=root/cfg['artifact_directory'];oracle_root=root/cfg['oracle_artifact_directory']
    frozen=json.loads((origin/'B1.frozen.json').read_text())
    assert digest(frozen['content'])==frozen['sha256']
    socket.socket.connect=denied;socket.create_connection=denied;subprocess.run=denied
    results=[]
    with sqlite3.connect('file:'+str(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
        charged={(s,v) for s,v in db.execute('select source,view_hash from oracle_views')}
    for pattern in frozen['content']['patterns']:
        for source_id in pattern['evidence_sources']:
            position=manifest['formal_train_order'].index(source_id)+1
            assert position<=16
            record_path=origin/'sources'/(digest(source_id)+'.json')
            original=json.loads(record_path.read_text())
            views=original['learning']['oracle_views']
            allowed={v['view_hash']:v for v in views}
            used=[]
            class Cached:
                def cached_views(self):return [v['view'] for v in views]
                def query(self,view):
                    key=digest(view)
                    assert key in allowed and (source_id,key) in charged
                    directory=oracle_root/'oracle_views'/digest(source_id)/key
                    request=json.loads((directory/'request.json').read_text())
                    response=json.loads((directory/'result.json').read_text())
                    assert request['view']==view and request['source']==source_id
                    assert request['reference_hash']==response['reference_hash']==digest(grade[source_id])
                    assert response['view_hash']==key and response['answer']==allowed[key]['answer']
                    used.append(key);return response['answer']
            trace={}
            learned=learn_source(public[source_id],grade[source_id],Cached(),trace=trace)
            comparison={'source':source_id,'python_equal':learned==original['learning'],
                'canonical_equal':digest(learned)==digest(original['learning']),
                'field_hash_differences':[k for k in learned if digest(learned[k])!=digest(original['learning'].get(k))]}
            if not comparison['python_equal']:
                (root/'reports/rr_method_runtime_20261107/prior_B1_initial_comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
            assert comparison['canonical_equal'],comparison
            assert digest(learned['learned_pattern'])==pattern['pattern_hash']
            results.append({'source':source_id,'original_position':position,
                'original_record_sha256':hashlib.sha256(record_path.read_bytes()).hexdigest(),
                'cached_views_reexecuted':used,'learning_exactly_matches_original':True,
                'canonical_comparison':comparison,
                'pattern_hash':pattern['pattern_hash'],'retained_candidates':learned['connector_candidates_retained']})
    proof={'component':'historical B1 collision-supported patterns only, not a new B1 build',
        'original_B1_file_sha256':hashlib.sha256((origin/'B1.frozen.json').read_bytes()).hexdigest(),
        'original_B1_content_hash':frozen['sha256'],'source_prefix_limit':16,
        'results':results,'new_model_calls':0,'new_oracle_views':0,'new_reference_labels':0,
        'network_and_subprocess_blocked':True,'library_for_later_probe':frozen['content'],
        'future_training_material_injected':False,
        'remaining':'Actual later-source graph invocation and native semantic check; full new128 build/DEV are still incomplete.'}
    (root/'reports/rr_method_runtime_20261107/prior_B1_component_compatibility.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'origins_checked':len(results),'new_model_calls':0,'new_oracle_views':0,'exact':True}))


if __name__=='__main__':main()
