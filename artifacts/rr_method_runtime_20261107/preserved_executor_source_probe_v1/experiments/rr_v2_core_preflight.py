"""Fresh A/B primary-path validation on four original PW sources, not fallback scores."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import ExecutorClient
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.ledger import BudgetLedger,BudgetError
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.preflight import science_files,ingest_source
from legal_skill_guard.rr.readiness import current_binding
from legal_skill_guard.rr.source_learning import learn_source

ROOT=Path(__file__).resolve().parents[1]
REVISION='core_primary_v1'
DIRECTORY='artifacts/rr_v2_preflight/core_primary_v1'
INDICES=(3,8,13,18)  # all four originally fixed PW sources, no outcome-based sampling

class CoreLedger(BudgetLedger):
    def reserve_oracle(self,*args):
        raise BudgetError('Core validation may only reuse the exact existing oracle cache; no new views')


def checks(record,trace):
    a=record['analysis']
    main_a=a['certificate_status']=='completion_stable' and a.get('certificate_basis') in {
        'complete_restricted_public_grammar_not_connector_H',
        'partial_public_Horn_complete_fact_observations_not_H'}
    semantic=record['score']['task_correct']
    b=trace.get('selected_connector_semantics',[])
    rejected=trace.get('initial_candidates',0)-trace.get('base_retained',0)+sum(x['removed'] for x in trace.get('events',[]))
    pattern=record['learning'].get('learned_pattern') or {}
    b_primary=record['learning']['status']=='identified_on_observed_collisions' and bool(pattern.get('graphs')) and bool(b)
    b_semantic=b_primary and all(x['prediction']==x['reference_answer'] for x in b)
    collisions=trace.get('refinement',{}).get('collisions',[])
    fields=set(pattern.get('fields',[]))
    separated=bool(collisions) and all(fields & set(c['distinguishing_fields']) for c in collisions)
    return dict(A=dict(primary_executed=main_a,semantic_pass=main_a and semantic,fallback=not main_a,
        certificate_basis=a.get('certificate_basis'),native_task_correct=semantic,
        source_grammar_assessment=a.get('public_grammar_assessment')),
        B=dict(primary_executed=bool(trace),semantic_pass=b_semantic and separated,
        fallback=not b_primary,collision_status=record['learning']['status'],
        rejected_wrong_candidates=rejected,candidate_count_decrease_required=False,
        refined_collisions_separated=separated,connector_semantic_observations=len(b),
        refined_fields=pattern.get('fields'),oracle_reference_labels_from_exact_cache=True,
        old_learning_result_used_as_output=False,finite_H_not_Omega=True))


def prepare(root):
    cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text());data=PreflightData(root,root/cfg['source_manifest'])
    assert not cfg['formal_run_enabled'] and not cfg['frozen_test_enabled']
    offline=json.loads((root/'reports/rr_v2_evidence/offline_latest.json').read_text())
    if offline['exit_code'] or not offline['network_blocked'] or any(
        hashlib.sha256((root/p).read_bytes()).hexdigest()!=h for p,h in offline['files'].items()):
        raise ValueError('Current offline regression required')
    wire=json.loads((root/'reports/rr_v2_evidence/semantic_preflight/wire_replay.json').read_text())
    learning=json.loads((root/'reports/rr_v2_evidence/semantic_preflight/learning_replay.json').read_text())
    binding=current_binding(root)
    if wire['execution_binding']!=binding or learning['execution_binding']!=binding or not wire['all_payloads_equal'] or not learning['all_exact']:
        raise ValueError('Current generation and B semantic compatibility checks required')
    origin=json.loads((root/'artifacts/rr_v2_preflight/seal.semantic_path.json').read_text())['binding']
    ledger=BudgetLedger(root/cfg['ledger_path'],sources=data.manifest['allowlist'],**{k:origin[k] for k in ['code_hash','config_hash']})
    ledger.register_study_revision(REVISION,new_binding={k:binding[k] for k in ['code_hash','config_hash']},
        change='Remove cached-B-result shortcut from validation; execute true learner with bound oracle cache and semantic connector trace; fresh audited A grammar main path',
        offline_evidence_hash=digest(dict(offline=offline,wire=wire,learning=learning)))
    result=dict(binding=binding,protected_files=science_files(root),config=cfg,
        source_indices=list(INDICES),sources=[data.order[i] for i in INDICES],max_executor_calls=8,
        teacher_calls=0,new_oracle_views=0,formal_training_enabled=False,
        actual_learner='learn_source with observation/candidate trace; cached labels only, never cached learner result')
    immutable_json(root/DIRECTORY/'seal.json',result)
    return result


def one(root,index):
    if index not in INDICES:raise ValueError('Only the four original PW sources')
    seal=json.loads((root/DIRECTORY/'seal.json').read_text());cfg=seal['config']
    if science_files(root)!=seal['protected_files']:raise ValueError('Frozen core validation code changed')
    data=PreflightData(root,root/cfg['source_manifest']);sid=data.order[index]
    path=root/DIRECTORY/'sources'/f'{digest(sid)}.json'
    if path.exists():return json.loads(path.read_text())
    ledger=CoreLedger(root/cfg['ledger_path'],sources=data.manifest['allowlist'],**{k:seal['binding'][k] for k in ['code_hash','config_hash']})
    client=ExecutorClient(ledger,root/DIRECTORY,cfg['executor'])
    library=SkillLibrary.restore(root/'artifacts/rr_v2_preflight/semantic_common_path_v3/partial_library.frozen.json')
    trace={}
    def actual_learner(source,grade,oracle,*,proposal=None):return learn_source(source,grade,oracle,proposal=proposal,trace=trace)
    def call(**kw):
        payload=client.payload(messages=kw['prompt'],thinking=kw['thinking'],schema=kw['schema'])
        ledger.register_study_request(kw['call_id'],revision=REVISION,source=sid,
            request={'thinking':kw['thinking'],'payload':payload},step=int(kw['call_id'].rsplit(':',1)[1]))
        return client.generate(kw['call_id'],source=sid,purpose=kw['purpose'],messages=kw['prompt'],thinking=kw['thinking'],schema=kw['schema'])
    record=ingest_source(source=data.public(sid),grade=data.grade(sid),library=library,thinking=True,
        call=call,learner=actual_learner,ledger=ledger,artifacts=root/DIRECTORY,
        oracle_artifacts=root/'artifacts/rr_v2_preflight/oracle_guard',binding=seal['binding'],
        purpose='preflight_bug_retry',id_prefix=REVISION,offline_mock=False)
    result=dict(record=record,trace=trace,checks=checks(record,trace),fresh_physical_requests=len(record['calls']),
        no_new_sources=True,new_oracle_views=0,teacher_calls=0)
    immutable_json(path,result)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','one']);p.add_argument('--index',type=int);a=p.parse_args()
    if a.action=='prepare':r=prepare(ROOT);print(json.dumps({'binding':r['binding'],'sources':r['source_indices']}));return
    r=one(ROOT,a.index);print(json.dumps({'source':r['record']['source'],'requests':r['fresh_physical_requests'],'checks':r['checks']},ensure_ascii=False))

if __name__=='__main__':main()
