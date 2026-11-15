"""Read-only audit of actual intermediate selection and one fixed TRAIN probe.

No model client is created. Existing frozen results are retained verbatim; no
DEV score is recomputed under the new runtime or used to edit a source fact.
"""
import base64
import json
from pathlib import Path
import sqlite3

from experiments import legal_skill_evolution_mixed_component_training as train
from experiments import legal_skill_evolution_native_scope_pilot as pilot
from experiments import legal_skill_evolution_observation_TRAIN_replay as cache_index
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT=train.ROOT
OUT=ROOT/'artifacts/legal_skill_evolution_training_chain_audit_20261115'


def run():
    read=train.read
    roots=[train.OUT,train.PREVIOUS_OUT,train.PRIOR_OUT]
    roots +=[ROOT/'artifacts'/n for n in reversed(cache_index.CACHE_NAMES)]
    batches=[]
    for b in range(1,9):
        folder=next(p/f'B{b}'for p in roots if (p/f'B{b}/checkpoint.json').exists())
        checkpoint=read(folder/'checkpoint.json');arms=[]
        for arm in train.ARMS:
            choice=checkpoint['libraries'][arm]
            selected_folder=(ROOT/choice['path']).parents[1]
            scores=[]
            for path in sorted((selected_folder/'candidate_scores').rglob('*.json')):
                name=str(path.relative_to(selected_folder/'candidate_scores'))[:-5]
                if not (name.startswith(arm+'/') or name.startswith('coordinate/'+arm+'/')):continue
                value=read(path);m=value['metrics'];rows=value['rows']
                scores.append({'name':name,'native_correct':m['native_correct'],
                    'partial_source_failures':m['partial_source_failures'],
                    'unresolved':m['unresolved'],
                    'handled_wrong':sum(bool(r['execution']['handled']) and not r['native_score']['correct']for r in rows),
                    'path':str(path.relative_to(ROOT))})
            selected=next(s for s in scores if s['name']==choice['candidate'])
            peers=[s for s in scores if (s['native_correct'],s['partial_source_failures'])==
                (selected['native_correct'],selected['partial_source_failures'])]
            arms.append({'arm':arm,'selected':selected,'same_correct_sourcefail_peers':peers,
                'selected_tie_group_has_wrong_count_difference':len({s['handled_wrong']for s in peers})>1})
        batches.append({'batch':b,'checkpoint':str((folder/'checkpoint.json').relative_to(ROOT)),'arms':arms})
    current=read(pilot.OUT/'result.json');before=read(pilot.OUT/'ledger_before.json')
    with sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True)as db:
        db.row_factory=sqlite3.Row;rows=[dict(r)for r in db.execute('select * from calls order by id')]
    assert all(digest(tuple(r.values()))==before['row_hashes'][r['id']]for r in rows if r['id']in before['row_hashes'])
    added=[r for r in rows if r['id']not in before['row_hashes']]
    assert len(added)==1 and added[0]['role']=='executor'
    costs=[]
    for row in added:
        response=json.loads(row['result']);costs.append({k:row[k]for k in ('id','role','source','purpose','status')})
        costs[-1].update(usage=response.get('usage'),elapsed_seconds=response.get('elapsed_seconds'),
            row_sha256=digest(tuple(row.values())))
    wires=[]
    for path in (pilot.OUT/'calls').glob('*/wire_request.json'):
        record=read(path);body=json.loads(base64.b64decode(record['body_b64']))
        assert body['chat_template_kwargs']['enable_thinking'] is False
        assert body['max_tokens']==8192
        wires.append({'path':str(path.relative_to(ROOT)),'thinking':False,'max_tokens':8192,
            'wire_sha256':record['body_sha256']})
    assert len(wires)==1
    summary=[{'arm':r['candidate'],'policy':r['phase'],'core_handled':r['execution']['handled'],
        'native_correct':r['native_score']['correct'],'known_source_failures':r['partial_source_review']['failures'],
        'read_order':r['component_read_order'],'feedback_state':r['learning_signal']['state']}
        for r in current['rows']]
    result={'new_calls_by_this_audit':0,'goal_complete':False,'TEST_opened':False,
        'historical_candidate_selection':batches,
        'historical_selected_ties_affected_by_wrong_count_bias':sum(a['selected_tie_group_has_wrong_count_difference']for b in batches for a in b['arms']),
        'latent_rank_bias_is_not_evidence_of_historical_score_damage':True,
        'actual_native_scope_pilot':summary,'physical_cost':costs,'wire_checks':wires,
        'previous_ledger_rows_unchanged':len(before['row_hashes']),
        'cumulative_roles':{role:sum(r['role']==role for r in rows)for role in ('executor','teacher')},
        'reserved':sum(r['status']=='reserved'for r in rows),
        'no_DEV_rerun_no_full_training':True,
        'shared_runtime_repair_is_not_independent_method_evidence':True}
    immutable_json(OUT/'result.json',result)
    print(json.dumps({k:result[k]for k in ('historical_selected_ties_affected_by_wrong_count_bias',
        'actual_native_scope_pilot','cumulative_roles','reserved')},ensure_ascii=False),flush=True)


if __name__=='__main__':run()
