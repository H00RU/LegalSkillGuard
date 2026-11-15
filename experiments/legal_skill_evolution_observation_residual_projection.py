"""Replay actual failed reads through a minimal demanded field projection.

No new observation is invented. The same paid common background is supplied
to before/after; native execution, scopes and source checks are unchanged.
This tests the handoff problem, not new-generation accuracy or novelty.
"""
from copy import deepcopy
import json

from experiments import legal_skill_evolution_observation_contract_transfer as previous
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import record_schema, grade_view
from legal_skill_guard.skill_evolution.native_observation_execution import evaluate
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_observation_contract import split, schema, pullback

ROOT=previous.ROOT
OUT=ROOT/'artifacts/legal_skill_evolution_observation_residual_projection_20261115'


def run():
    before_ledger=previous.previous.generation.runtime.lineage.ledger_snapshot()
    parent=ROOT/'artifacts/legal_skill_evolution_observation_contract_transfer_compact_saved_20261115'
    failed=next(previous.read(p)for p in(parent/'cases/Method/1').glob('residual_*.json'))
    control=next(previous.read(p)for p in(parent/'cases/FreeTeacher/0').glob('residual_*.json'))
    sid=failed['source'];assert sid==control['source']and ':982d5316'in sid
    public,kernels=previous.runtime.previous.data()
    library=previous.read(previous.previous.PARENT/'candidate_libraries/Method/1.json')
    free=previous.read(previous.previous.PARENT/'candidate_libraries/FreeTeacher/0.json')
    cid='institutional_status_events'
    assert digest(next(c for c in library['components']if c['id']==cid))==digest(next(c for c in free['components']if c['id']==cid))
    observation=deepcopy(failed['observation'])
    observation[cid]=deepcopy(control['observation'][cid])
    initial=evaluate(library,kernels[sid],public[sid]['views'][0]['public'],observation,sid)
    scopes=[s for w in initial['binding_executions']for s in w['execution'].get('unread_factual_scopes',[])]
    assert scopes and scopes[0]['predicate']=='agent_'
    target={'predicate':scopes[0]['predicate'],'arguments':[scopes[0]['event'],{'var':'ObservedValue'}]}
    component=next(c for c in library['components']if c['id']=='service_events')
    contract=component['relation_contract'];original=next(g for g in contract['relations']if g['name']=='service_core')
    partitions=[{'name':'service_core_'+f['name'],'fields':[f['name']],
        'prompt':original['prompt']+'\nRead only this already declared field: '+f['name']}
        for f in original['fields']if f['name']!=original['key']]
    refined=split(contract,original['name'],partitions)
    demands=pullback(refined,target)
    needed={d['relation']for b in demands['branches']for d in b['joined_demands']}
    needed.add(refined['enumerator'])
    assert needed=={'service_core_worker'}
    raw=observation['service_events']['views'][0]['service_core']
    view={}
    for g in refined['relations']:
        if g['name']not in needed:continue
        names=[f['name']for f in g['fields']]
        view[g['name']]={'status':raw['status'],'witnesses':deepcopy(raw['witnesses']),
            'records':[{n:deepcopy(row[n])for n in names}for row in raw['records']]}
    projected=deepcopy(library)
    pc=next(c for c in projected['components']if c['id']=='service_events')
    pc['relation_contract']=refined;shape=schema(refined);shape['required']=[]
    pc['schema_json']=json.dumps(record_schema({'views':{'type':'array','minItems':1,'items':shape}}))
    changed=deepcopy(observation);changed['service_events']={'views':[view]}
    after=evaluate(projected,kernels[sid],public[sid]['views'][0]['public'],changed,sid)
    grading=previous.read(parent/'TRAIN_grading.json')[sid]
    score=grade_view(public[sid]['dataset'],public[sid]['views'][0],grading[public[sid]['views'][0]['id']],after['answer'])
    assert not initial['handled']and after['handled']and score['correct']
    assert previous.previous.generation.runtime.lineage.ledger_snapshot()==before_ledger
    immutable_json(OUT/'result.json',{'source':sid,'actual_initial_observation':observation,
        'before':initial,'native_residual':target,'derived_demands':demands,
        'projected_contract':refined,'projected_observation':changed,'after':after,'native_score':score,
        'common_background_component_byte_identical':True,
        'source_values_witnesses_and_keys_unchanged':True,
        'unrequested_semantics_not_invented_or_closed':True,'new_model_calls':0,
        'offline_replay_of_real_paid_outputs_not_new_generation':True,
        'not_an_independent_learning_or_novelty_result':True,'goal_complete':False})
    print(json.dumps({'before_handled':initial['handled'],'after_handled':after['handled'],
        'native_correct':score['correct'],'selected_groups':sorted(needed),'new_model_calls':0}),flush=True)


if __name__=='__main__':run()
