"""Remove other questions' source units from one unchanged TRAIN probe."""
import fcntl
import json
from pathlib import Path
from experiments.legal_skill_evolution_refutation_learning import ROOT,OUT,RUN,read,sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_evidence_codec import schema,decode
from legal_skill_guard.skill_evolution.refutation_learning import canonical_evidence
from legal_skill_guard.skill_evolution.runtime import decoder_schema


def run():
    base=read(OUT/'protocol.json');old=read(OUT/'batch_diagnostic/0.json')
    prompt=old['isolated_messages'];data=json.loads(prompt[1]['content']);q=old['query'];op=old['operation']
    original=data['source_units'];data['source_units']=[u for u in original if u['id'] in q['unit_ids']]
    assert len(data['source_units'])==len(q['unit_ids'])
    prompt=[prompt[0],{**prompt[1],'content':json.dumps(data,ensure_ascii=False)}]
    folder=OUT/'window_diagnostic';p={'run_id':RUN+':window_diagnostic','source':old['source'],
        'code_sha256':sha(Path(__file__)),'original_request':old['original_request'],
        'same_query_definition_and_focus':True,'removed_other_queries_out_of_window_units':
            [u['id'] for u in original if u['id'] not in q['unit_ids']],
        'one_original_TRAIN_diagnostic_not_validation_repair':True,'goal_complete':False}
    immutable_json(folder/'protocol.json',p)
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=p['run_id'],
        sources={'train':base['train_sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,folder,base['executor_profile']);client.readiness();wire,_=decoder_schema(schema([op],[q]))
    r=client.generate(p['run_id']+':one',source=old['source'],purpose='skill_replay',
        messages=prompt,thinking=False,schema=wire)
    if r['finish_reason']!='stop':raise ValueError('Incomplete; no unchanged retry')
    units=read(OUT/'input.json')['sources'][old['source']]['units']
    normalized,adapt=canonical_evidence(r['content']);_,answer=decode([op],[q],units,normalized)
    immutable_json(folder/'result.json',{'result':r,'answer':answer[0],'adaptation':adapt,'messages':prompt,
        'prior_isolated_question_with_shared_source_verdict':old['answer']['choice'],'goal_complete':False})
    print(json.dumps({'old':old['answer']['choice'],'exact_window':answer[0]['choice']}),flush=True)


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
