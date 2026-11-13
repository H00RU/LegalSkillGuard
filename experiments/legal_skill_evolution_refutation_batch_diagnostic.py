"""One controlled source-context-preserving question-isolation diagnostic."""
import fcntl
import json
from pathlib import Path

from experiments.legal_skill_evolution_refutation_learning import ROOT,OUT,RUN,read,sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.source_evidence_codec import schema,decode
from legal_skill_guard.skill_evolution.refutation_learning import canonical_evidence

DEST=OUT/'batch_diagnostic'


def run():
    old=read(OUT/'protocol.json');source=old['train_sources'][2]
    q1='sr_0_role:focus_express_disposal_action'
    q2='case_1:focus_express_retention_grant_complete_source'
    contexts=[(OUT/'training_mechanism_replay/check.json',q1),
        (OUT/'atomic_revision/context_measurement/focus_express_retention_grant_complete_source'/(source.replace(':','_')+'.json'),q2)]
    with __import__('sqlite3').connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        ledger_rows={r[0]:json.loads(r[1]) for r in db.execute("select id,result from calls where status='completed'")}
    # Actual preserved wire prompts contain the same current-source context;
    # remove other questions only, without changing a proposition or witness.
    chosen=[]
    for path,qid in contexts:
        record=read(path);result=record['events'][0]['result'] if 'events' in record else record['result']
        request_path=Path(result['artifact_directory'])/'request.json'
        request=read(request_path);prompt=request['payload']['messages'];value=json.loads(prompt[1]['content'])
        assert 'checks' in value and all('definition' in x for x in value['checks'])
        selected=[x for x in value['checks'] if x['query']['id']==qid];assert len(selected)==1
        before=value;after={**value,'checks':selected}
        assert before['source_units']==after['source_units']
        new_prompt=[prompt[0],{**prompt[1],'content':json.dumps(after,ensure_ascii=False)}]
        chosen.append({'original_request':str(request_path.relative_to(ROOT)),'source':source,
            'original_messages_sha256':digest(prompt),'isolated_messages':new_prompt,
            'operation':selected[0]['definition'],'query':selected[0]['query'],
            'original_question_count':len(value['checks']),'same_source_context':True,
            'old_raw_content':result['content']})
    p={'run_id':RUN+':batch_diagnostic','source':source,'cases':[{'query':c['query'],
        'original_request':c['original_request'],'original_messages_sha256':c['original_messages_sha256']} for c in chosen],
        'code_sha256':sha(Path(__file__)),'same_goal':True,'goal_complete':False,
        'question_and_source_unchanged_only_other_questions_removed':True,
        'not_validation_repair_or_new_source':True,'executor_profile':old['executor_profile']}
    immutable_json(DEST/'protocol.json',p)
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=p['run_id'],
        sources={'train':old['train_sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,DEST,old['executor_profile']);client.readiness();units=read(OUT/'input.json')['sources'][source]['units'];rows=[]
    for n,c in enumerate(chosen):
        op=c['operation'];q=c['query'];wire,_=decoder_schema(schema([op],[q]))
        r=client.generate(p['run_id']+':'+str(n),source=source,purpose='skill_replay',
            messages=c['isolated_messages'],thinking=False,schema=wire)
        if r['finish_reason']!='stop':raise ValueError('Incomplete; no unchanged retry')
        canonical,adapt=canonical_evidence(r['content']);_,answers=decode([op],[q],units,canonical)
        value={**c,'result':r,'answer':answers[0],'adaptation':adapt};rows.append(value)
        immutable_json(DEST/(str(n)+'.json'),value)
        print(json.dumps({'query':q['id'],'isolated_verdict':answers[0]['choice'],
            'original_questions':c['original_question_count']}),flush=True)
    immutable_json(DEST/'completed.json',{'rows':rows,'goal_complete':False,
        'not_a_replacement_validation_score':True})


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
