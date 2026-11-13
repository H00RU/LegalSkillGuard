"""Direct source-phrase control for the already identified mixed-actor clause."""
import fcntl
import json
from pathlib import Path
import jsonschema
from experiments.legal_skill_evolution_refutation_learning import ROOT,OUT,RUN,read,sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest


def run():
    original=read(OUT/'protocol.json');witness=read(OUT/'representation_audit/mixed_effect_actor.json')
    unit=witness['source_witnesses'][0];source=witness['original_TRAIN_source'];folder=OUT/'direct_actor_diagnostic'
    schema=record_schema({'return_actor_phrase':{'type':'string'},'maintain_copy_actor_phrase':{'type':'string'},
        'unresolved':{'type':'array','items':{'type':'string'}}})
    prompt=[{'role':'system','content':
        'Extract exact actor phrases from the CURRENT clause. Who is to perform the return, and who is allowed to maintain a copy? '
        'Copy each actor phrase verbatim from this clause. Keep distinct actors distinct. Use an empty phrase and explain in unresolved if the source does not supply one. '
        'This is literal source-role extraction, not a downstream legal answer. Return the schema.'},
        {'role':'user','content':json.dumps({'current_unit':unit},ensure_ascii=False)}]
    p={'run_id':RUN+':direct_actor_diagnostic','source':source,'focus_unit':unit['id'],
        'same_goal':True,'goal_complete':False,'profile':original['executor_profile'],
        'messages_sha256':digest(prompt),'code_sha256':sha(Path(__file__)),
        'existing_TRAIN_direct_role_control_not_full_IR_or_method_success':True,
        'no_new_source_validation_or_TEST':True}
    immutable_json(folder/'protocol.json',p)
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=p['run_id'],
        sources={'train':original['train_sources']+[source],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,folder,original['executor_profile']);client.readiness()
    r=client.generate(p['run_id']+':one',source=source,purpose='skill_replay',messages=prompt,thinking=False,schema=schema)
    immutable_json(folder/'raw_result.json',r)
    if r['finish_reason']!='stop':raise ValueError('Incomplete; no unchanged retry')
    value=json.loads(r['content']);jsonschema.validate(value,schema)
    for name in ['return_actor_phrase','maintain_copy_actor_phrase']:
        if value[name] and value[name] not in unit['text']:raise ValueError('Actor is not a literal current-source phrase')
    immutable_json(folder/'result.json',{'value':value,'raw_result':r,'verbatim_checked':True,
        'no_norms_or_native_scores_derived_by_host':True,'goal_complete':False})
    print(json.dumps({'value':value,'usage':r['usage'],'seconds':r['elapsed_seconds']}),flush=True)


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
