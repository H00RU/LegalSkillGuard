"""Replay one actual acquisition-TRAIN fault through the learned check.

Uses exact preserved neural observations and new evidence-based readings. This
is an instrumented TRAIN replay, never a fresh end-to-end or reuse score.
"""
import fcntl
import json
from pathlib import Path

from experiments.legal_skill_evolution_refutation_learning import ROOT,OUT,RUN,read,sha
from experiments.legal_skill_evolution_refutation_context import DEST as TRAIN
from experiments.legal_skill_evolution_residual_calibration import source_record
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.refutation_reader import check
from legal_skill_guard.skill_evolution.refutation_learning import canonical_evidence
from legal_skill_guard.skill_evolution.residual_reader import execute as complete_reader
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.source_evidence_codec import schema,decode,messages

DEST=OUT/'training_mechanism_replay'


def run():
    p0=read(OUT/'protocol.json');data=read(OUT/'input.json');learned=read(TRAIN/'completed.json')
    selected=[t for t in learned['tests'] if t['name'] in learned['policy']['selected_tests']]
    source=p0['train_sources'][2]
    assert source.startswith('ContractNLI:442c36c')
    old_path=ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113/calibration'/(source.replace(':','_')+'.json')
    old=read(old_path);bundle=read(ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113/seed.json')
    paths=[Path(__file__).resolve(),ROOT/'legal_skill_guard/skill_evolution/refutation_reader.py',
           ROOT/'legal_skill_guard/skill_evolution/residual_reader.py']
    p={'run_id':RUN+':training_mechanism_replay','source':source,'old_result_sha256':sha(old_path),
        'old_seed_sha256':digest(bundle),'learned_policy_sha256':sha(TRAIN/'learned_policy.json'),
        'source_sha256':{str(q.relative_to(ROOT)):sha(q) for q in paths},'same_goal':True,'goal_complete':False,
        'TRAIN_replay_not_new_generalization':True,'no_validation_based_repair':True,
        'no_host_replacement_legal_value':True,'executor_profile':p0['executor_profile']}
    immutable_json(DEST/'protocol.json',p)
    for path in paths:
        target=DEST/'source_snapshot'/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert target.read_bytes()==path.read_bytes()
        else:target.write_bytes(path.read_bytes())
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=p['run_id'],
        sources={'train':p0['train_sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,DEST,p0['executor_profile']);client.exact_replay_roots=(OUT,ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113')
    client.readiness();units=data['sources'][source]['units'];text=data['sources'][source]['source_text']
    queries=old['runtime']['query_plan'];by_q={q['id']:q for q in queries}
    answers={a['id']:a for a in old['runtime']['semantic_answers']}
    cases=[{'id':a['id'],'operation':a['operation'],'candidate_choice':a['choice'],
            'focus_unit_id':by_q[a['id']]['unit_ids'][-1],'unit_ids':by_q[a['id']]['unit_ids']}
           for a in answers.values() if a['operation']=='disposal_retention_clause_role' and a['choice']!='unknown']
    rejected,events=check(client,p['run_id']+':audit',source,selected,cases,bundle['operations'],units)
    immutable_json(DEST/'check.json',{'rejected':rejected,'events':events})
    changed=[]
    for qid,witnesses in rejected.items():
        q=by_q[qid];before=answers[qid];prompt=messages(bundle['operations'],[q],units,scope='focus_last')
        prompt[1]['content']=json.dumps({'current':json.loads(prompt[1]['content']),
            'explicit_current_source_exclusion':before['choice'],'new_source_observations':witnesses,
            'instruction':'Re-read this operation. The excluded candidate was refuted, but no replacement value is supplied. Use unknown if remaining choices lack source support.'},ensure_ascii=False)
        raw=schema(bundle['operations'],[q]);values=raw['properties']['answers']['properties'][qid]['anyOf'][0]['properties']['choice']['enum']
        values.remove(before['choice']);wire,_=decoder_schema(raw)
        r=client.generate(p['run_id']+':reread:'+qid,source=source,purpose='skill_replay',messages=prompt,thinking=False,schema=wire)
        if r['finish_reason']!='stop':raise ValueError('Incomplete; no automatic retry')
        normalized,adapt=canonical_evidence(r['content']);_,value=decode(bundle['operations'],[q],units,normalized)
        answers[qid]=value[0];changed.append({'id':qid,'before':before,'after':value[0],'result':r,'adaptation':adapt})
    immutable_json(DEST/'rereads.json',changed)
    result=complete_reader(client,p['run_id']+':continue',source,bundle,text,units,
        scope='focus_last',lookup='_sr_get',initial_observations=list(answers.values()))
    public=next(s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json') if s['key']==source)
    record=source_record(bundle,public,result)
    immutable_json(DEST/'result.json',{'old_result_path':str(old_path.relative_to(ROOT)),
        'old_source_output':old['runtime']['source_output'],'changed':changed,'result':record,
        'new_semantic_calls':sum(e['kind']=='neural' for e in result['events']),
        'TRAIN_replay_not_reuse':True,'goal_complete':False})
    print(json.dumps({'source':source,'changed':[(r['id'],r['before']['choice'],r['after']['choice']) for r in changed],
        'old_roots':len(old['runtime']['source_output']['statements']),'new_roots':len(result['source_output']['statements']),
        'native_correct':sum(bool(v['score'] and v['score']['correct']) for v in record['views'])}),flush=True)


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
