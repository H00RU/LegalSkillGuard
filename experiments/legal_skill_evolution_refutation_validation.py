"""Freeze learned source probes and same-information controls before reuse."""
import fcntl
import json
from pathlib import Path

from experiments.legal_skill_evolution_refutation_learning import ROOT,OUT,RUN,read,sha
from experiments.legal_skill_evolution_refutation_context import DEST as TRAIN
from experiments.legal_skill_evolution_refutation_atomic import FOLDER,generic
from experiments.legal_skill_evolution_residual_calibration import source_record
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.refutation_reader import execute
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units

DEST=OUT/'fixed_validation'
ARMS=['LearnedChecks','GenericLocalFeedback','GenericFullFeedback','DirectFeedback','NoChecks']


def prepare():
    original=read(OUT/'protocol.json');trained=read(TRAIN/'completed.json')
    data=read(FOLDER/'input.json');chosen=set(trained['policy']['selected_tests'])
    assert chosen,'No learned usable check; do not run an empty mechanism as new verification'
    tests=[t for t in trained['tests'] if t['name'] in chosen]
    common=read(ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113/seed.json')
    full=generic(data);local={**full,'name':'generic_source_judge_local',
        'window_program':read(FOLDER/'validated_bank.json')['tests'][0]['window_program']}
    feedback={'original_TRAIN_source_texts':{k:s['source_text'] for k,s in data['sources'].items()},
        'candidate_interpretation_supervision':data['training_cases'],
        'same_acquired_operation':data['operations'][0],
        'explicit_source_feedback':data['explicit_source_negative_feedback'],
        'uncertain_interpretations_not_negative':True,
        'instruction':'These examples supervise source interpretation, not current answers. Do not copy a TRAIN source conclusion into a different current contract. Re-read the current focus with its context.'}
    paths=[Path(__file__).resolve()]+[ROOT/'legal_skill_guard/skill_evolution'/n for n in
        ['refutation_learning.py','refutation_reader.py','source_python.py','source_evidence_codec.py']]
    p={'run_id':RUN+':fixed_reuse','same_goal':True,'goal_complete':False,
        'train_sources':original['train_sources'],'validation_sources':original['validation_sources'],
        'executor_profile':original['executor_profile'],'arms':ARMS,
        'source_sha256':{str(q.relative_to(ROOT)):sha(q) for q in paths},
        'seed_sha256':digest(common),'learned_policy_sha256':sha(TRAIN/'learned_policy.json'),
        'banks':{'LearnedChecks':tests,'GenericLocalFeedback':[local],'GenericFullFeedback':[full],
                 'DirectFeedback':[],'NoChecks':[]},'feedback_sha256':digest(feedback),
        'shared_initial_acquisition_execution_update_comparison':True,
        'not_independent_end_to_end_initial_acquisition':True,
        'all_controls_receive_same_original_TRAIN_source_and_semantic_supervision':True,
        'no_validation_adaptation':True,'new_DEV_TEST_or_full_training':False,
        'fallback_not_executed':True,'validation_IDs_fixed_before_current_learning':True,
        'partial_training_coverage_not_an_all_errors_gate':True}
    immutable_json(DEST/'protocol.json',p);immutable_json(DEST/'control_feedback.json',feedback)
    for q in paths:
        target=DEST/'source_snapshot'/q.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert target.read_bytes()==q.read_bytes()
        else:target.write_bytes(q.read_bytes())
    for name,h in p['source_sha256'].items():assert sha(ROOT/name)==h
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=p['run_id'],
        sources={'train':p['train_sources']+p['validation_sources'],'dev':[],'test':[]},binding=digest(p))
    return p,common,feedback,ledger


def run():
    p,bundle,feedback,ledger=prepare()
    # Both the learned assets and every comparison are frozen before selecting
    # the actual fixed validation bodies from the preserved TRAIN manifest.
    public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    for arm in p['arms']:
        client=FrozenExecutor(ledger,DEST,p['executor_profile'])
        client.exact_replay_roots=(DEST,ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113/fixed_validation')
        client.readiness()
        for key in p['validation_sources']:
            target=DEST/arm/(key.replace(':','_')+'.json')
            if target.exists():continue
            source=public[key];pub=source['views'][0]['public']
            units,_=execution_source_units(pub['source_text'],source_spans(material_public(pub)))
            count=[0]
            def save(e):
                count[0]+=1
                immutable_json(DEST/arm/'events'/(digest(key)+'.'+str(count[0])+'.json'),e)
            r=execute(client,p['run_id']+':'+arm+':'+key,key,bundle,pub['source_text'],units,
                bank=p['banks'][arm],feedback=feedback if arm in ['GenericLocalFeedback','GenericFullFeedback','DirectFeedback'] else None,
                direct_feedback=arm=='DirectFeedback',save_event=save)
            result=source_record(bundle,source,r);immutable_json(target,result)
            es=[e for e in r['events'] if 'result' in e]
            print(json.dumps({'arm':arm,'source':key,'core':sum(v['core_executed'] for v in result['views']),
                'correct':sum(bool(v['score'] and v['score']['correct']) for v in result['views']),
                'exclusions':r['exclusions'],'new_physical':sum(not e['result'].get('cache_hit',False) for e in es),
                'logical':len(es)}),flush=True)
    immutable_json(DEST/'completed.json',{'arms':p['arms'],'sources':p['validation_sources'],
        'source_semantic_review_pending':True,'goal_complete':False})


if __name__=='__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_refutation_learning_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
