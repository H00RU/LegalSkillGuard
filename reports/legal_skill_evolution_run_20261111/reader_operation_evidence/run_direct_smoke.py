"""Real validation of the ordinary JSON decoder repair on the original smoke."""
import json

from recover_actual_smoke import setup
from direct_source_control import read_direct
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.scoped_reader import apply_current
from experiments import legal_skill_evolution_semantic_operations as study


if __name__=='__main__':
    folder,p,ledger,source,spans,units,supports,b,answers,queries=setup()
    b=study.read(folder/'lowering_repair/bundle.json')
    interpretation,result=read_direct(FrozenExecutor(ledger,folder,p['executor_profile']),
        study.RUN+':smoke:SharedDirectV3',source['key'],b,units,supports)
    out=folder/'smoke_DirectSourceV3';immutable_json(out/'raw_result.json',result)
    grading=study.read(study.ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    views=[]
    for v in source['views']:
        r=apply_current(b['spec'],{'rules':[],'disabled_rules':[],'acquired_pairs':[]},interpretation,v)
        core=r['value']['handled']
        proof=sorted({spans[i]['public_sentence_id'] for n in r['value']['used_nodes']
            for i in interpretation['nodes'][n]['support_ids'] if 'public_sentence_id' in spans[i]})
        score=grade_view(source['dataset'],v,grading[source['key']][v['id']],r['value']['answer'],proof) if core else None
        views.append({'view':v['id'],'core_executed':core,'fallback':not core,'execution':r,
                      'score':score,'proof_sentence_ids':proof})
    immutable_json(out/'result.json',{'source':source['key'],'arm':'SharedDirectSourceV3',
        'same_acquired_semantics_and_existing_common_IR_examples':True,
        'not_independent_acquisition':True,'interpretation':interpretation,'views':views,
        'source_semantic_review_pending':True,'goal_complete':False})
    print(json.dumps({'core':sum(v['core_executed'] for v in views),
        'correct':sum(bool(v['score'] and v['score']['correct']) for v in views),
        'seconds':result['elapsed_seconds'],'usage':result['usage']}))
