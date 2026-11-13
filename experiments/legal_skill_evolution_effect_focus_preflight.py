"""Check the actual mixed-actor clause, preserving the full source as context."""
import fcntl
import json
from pathlib import Path
import jsonschema
from experiments.legal_skill_evolution_refutation_learning import ROOT,OUT,RUN,read,sha
from experiments.legal_skill_evolution_residual_calibration import source_record
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.scoped_grammar import constructors
from legal_skill_guard.skill_evolution.scoped_reader import decode_expression

DEST=OUT/'effect_focus_preflight'


def run():
    old=read(OUT/'protocol.json');bundle=read(ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113/seed.json')
    source=next(s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json') if s['key'].startswith('ContractNLI:8af247'))
    path=OUT/'slim_expression_preflight/calls'/digest(RUN+':slim_expression_preflight:one')/'request.json'
    request=read(path);prompt=request['payload']['messages'];body=json.loads(prompt[1]['content'])
    body['focus_source_unit_ids']=[58]
    prompt=[{**prompt[0],'content':prompt[0]['content']+
        '\nFor this bounded interface check, interpret ONLY the focus_source_unit_ids. All other current-source units are context for that focus, not additional effects to emit. The selected focus is an actual clause with potentially distinct effects; discover their actors/limits from its words. This does not request a full-contract formalization.'},
        {**prompt[1],'content':json.dumps(body,ensure_ascii=False,separators=(',',':'))}]
    host=request['payload']['response_format']['json_schema']['schema']
    p={'run_id':RUN+':effect_focus_preflight','source':source['key'],'focus_units':[58],
        'full_current_source_context_unchanged':True,'shared_acquired_assets_unchanged':True,
        'messages_sha256':digest(prompt),'code_sha256':sha(Path(__file__)),
        'bounded_engineering_check_of_preexisting_TRAIN_actor_collision':True,
        'not_full_source_or_learned_method_success':True,'same_goal':True,'goal_complete':False,
        'profile':old['executor_profile'],'no_new_source_or_validation_or_TEST':True}
    immutable_json(DEST/'protocol.json',p)
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=p['run_id'],
        sources={'train':old['train_sources']+[source['key']],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,DEST,old['executor_profile']);client.readiness()
    r=client.generate(p['run_id']+':one',source=source['key'],purpose='skill_replay',messages=prompt,thinking=False,schema=host)
    immutable_json(DEST/'raw_result.json',r)
    if r['finish_reason']!='stop':raise ValueError('Incomplete; no unchanged retry')
    value=json.loads(r['content']);jsonschema.validate(value,host)
    units={u['id']:u for u in body['current_source_units']};rows=[]
    for item in value['statements']:
        ids=item['support_ids']
        if len(set(ids))!=len(ids) or not set(ids)<=set(units):raise ValueError('Invalid source evidence')
        term=decode_expression(item['expression'],constructors(bundle['spec']),' '.join(units[i]['text'] for i in ids))
        rows.append({'term':term,'support_ids':ids})
    result=source_record(bundle,source,{'source_output':{'statements':rows,'complete':False,
        'unresolved':['Only the declared focus was requested; remaining source was context, not formalized.',*value['unresolved']]},
        'raw_result':r,'engineering_focus_only_not_learning_evidence':True})
    immutable_json(DEST/'result.json',result)
    print(json.dumps({'source':source['key'],'scope':[58],'typed_roots':len(rows),
        'core':sum(v['core_executed'] for v in result['views']),
        'correct':sum(bool(v['score'] and v['score']['correct']) for v in result['views']),
        'tokens':r['usage'],'seconds':r['elapsed_seconds'],'not_full_source_or_method_success':True}),flush=True)


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
