"""Export the completed finite mechanism check and its physical request cost."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json

ROOT=Path(__file__).resolve().parents[3]
RUN=ROOT/'artifacts/legal_skill_evolution_binding_TRAIN_v2_20261113'
OUT=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


if __name__=='__main__':
    p=read(RUN/'protocol.json')
    for path,h in {**p['source_snapshot'],**p['data_sha256']}.items():assert sha(ROOT/path)==h,path
    before=read(RUN/'ledger_rows_before.json')['rows']
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as c:
        after=[list(r) for r in c.execute('select * from calls order by id')]
        columns=[v[1] for v in c.execute('pragma table_info(calls)')]
    old={r[0]:r for r in before};current={r[0]:r for r in after}
    assert all(current[k]==v for k,v in old.items())
    added=[dict(zip(columns,r)) for r in after if r[0] not in old]
    assert len(added)==1 and added[0]['role']=='teacher' and added[0]['status']=='completed'
    result=json.loads(added[0]['result']);counts=Counter((r[columns.index('role')],r[columns.index('status')]) for r in after)
    assert not any(status=='reserved' for role,status in counts)
    cost={'new_physical_requests':{'executor':0,'teacher':1},'requests':added,
        'cumulative':{role:sum(n for (r,s),n in counts.items() if r==role) for role in ('executor','teacher')},
        'pending':0,'old_rows_unchanged':len(before),'total_rows':len(after),
        'ledger_sha256':hashlib.sha256(json.dumps(after,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
        'usage':result['invocation']['usage'],'elapsed_seconds':result['elapsed_seconds'],
        'reasoning_included_in_output_not_added_twice':True,
        'teacher_actual_cash_invoice_available':False,'teacher_actual_cash_usd':None,
        'GPU_cash_allocation_usd':None,'new_executor_API_cash_usd':0,
        'extra_free_model_request_not_dispatched':True,'held_reuse_not_opened':True,
        'pre_dispatch_transport_failure_physical_calls':0,'old_pre_dispatch_protocol_and_metadata_retained':True,
        'goal_complete':False}
    immutable_json(OUT/'cost_and_preservation.json',cost)
    selected=['protocol.json','frontend_teacher_input.json','frontend_teacher.json','frontend_compiled.json',
        'selector_preflight.json','grounded_demo_recovery.json','grounded_training_cases.json',
        'demo_recovery_execution_manifest.json','demo_recovery_execution_manifest_v2.json',
        'binding_opportunity_audit.json','mechanism_audit_decision.json','Joint_model.json','UnaryRelations_model.json',
        'development_controls/completed.json']
    for name in selected:
        dst=OUT/'raw'/name;dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert dst.read_bytes()==(RUN/name).read_bytes()
        else:dst.write_bytes((RUN/name).read_bytes())
    previous=ROOT/'artifacts/legal_skill_evolution_binding_TRAIN_20261113'
    for name in ('protocol.json','frontend_teacher_input.json','pre_dispatch_failure.json'):
        dst=OUT/'raw/pre_dispatch_v1'/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes((previous/name).read_bytes())
    dst=OUT/'raw/demo_adapter_initial.py.txt';dst.write_bytes((RUN/'demo_adapter_versions/initial.py').read_bytes())
    r=read(RUN/'development_controls/completed.json');audit=read(RUN/'binding_opportunity_audit.json')
    immutable_json(OUT/'stage_conclusion.json',{'summary':r['summary'],
        'actual_open_claims':len(audit['actual_open_claims']),
        'distinct_semantic_terms_before_learning_each_open_claim':[a['distinct_closed_terms_before_learning'] for a in audit['actual_open_claims']],
        'cross_slot_literals_used':sum(a['cross_slot_literals_used'] for a in audit['actual_open_claims']),
        'Joint_and_Unary_policies_identical':audit['joint_and_unary_policies_identical'],
        'actual_primary_interpretations_and_all_views_identical':r['joint_unary_source_and_all_native_outputs_exactly_identical'],
        'not_independent_end_to_end_acquisition':True,'fallback_not_core_success':True,
        'semantic_review_does_not_claim_all_source_conditions_verified':True,
        'source_typing_and_native_scores_not_source_truth':True,
        'decision':'Do not pursue cross-slot binding as the first contribution on this acquired material. Do not force holes, new negatives, features or extra validation to activate it. Keep the learner as a common tool; no additional free-model call or held-reuse exposure.',
        'first_contribution_established':False,'second_contribution_established':False,
        'Goal_active_incomplete':True,'new_full_training_DEV_TEST_or_paper':False})
    print(json.dumps({'cumulative':cost['cumulative'],'new':cost['new_physical_requests'],
        'usage':cost['usage'],'pending':0,'bound_source':len(p['source_snapshot']),'bound_data':len(p['data_sha256'])}))
