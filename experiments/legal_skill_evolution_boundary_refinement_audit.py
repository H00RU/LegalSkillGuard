"""Settle the fixed screen, preserving raw scores and semantic distinctions.

The review statements concern only actually reached paths. They are not new
training labels, source repairs, a whole-library equivalence claim, or TEST.
"""
from collections import Counter
import base64
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT/'artifacts/legal_skill_evolution_boundary_refinement_20261113'
OUT = ROOT/'artifacts/legal_skill_evolution_boundary_refinement_role_grounding_20261113'


def read(path):
    return json.loads(path.read_text())


def run():
    db=sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True)
    rows=[list(r) for r in db.execute('select * from calls order by id')]
    current={r[0]:r for r in rows};before=read(OLD/'ledger_before.json')['rows']
    assert all(current[r[0]]==r for r in before)
    new=[r for r in rows if r[0] not in {b[0] for b in before}]
    assert all(r[0].startswith((OLD.name+':',OUT.name+':')) for r in new)
    assert not any(r[6]=='reserved' for r in rows)
    costs={k:Counter() for k in ('executor','teacher')};calls=[]
    for r in new:
        result=json.loads(r[8]);role=r[1]
        usage=result.get('invocation',{}).get('usage',{}) if role=='teacher' else result.get('usage',{})
        costs[role].update({'physical_requests':1,'input_tokens':usage.get('input_tokens',usage.get('prompt_tokens',0)),
            'output_tokens':usage.get('output_tokens',usage.get('completion_tokens',0)),
            'reasoning_output_tokens':usage.get('reasoning_output_tokens',0),
            'service_seconds':result.get('elapsed_seconds',0)})
        calls.append({'id':r[0],'role':role,'source':r[4],'status':r[6],
            'request_hash':r[5],'usage':usage,'seconds':result.get('elapsed_seconds'),
            'finish_reason':result.get('finish_reason')})
    assert Counter(r[1] for r in new)=={'executor':12,'teacher':3}
    profile=[]
    for f in sorted((OUT/'execution/calls').glob('*/wire_request.json')):
        wire=read(f);payload=json.loads(base64.b64decode(wire['body_b64']))
        assert payload['chat_template_kwargs']['enable_thinking'] is False
        assert payload['max_tokens']==8192
        profile.append({'file':str(f.relative_to(OUT)),'sha256':wire['body_sha256'],
                        'thinking':False,'max_tokens':8192})
    assert len(profile)==12
    records=[read(f) for f in sorted((OUT/'execution').glob('*/*/*/result.json'))]
    assert len(records)==12
    stats={};reviews=[]
    for r in records:
        stage=r['stage'];arm=r['arm'];key=r['source'].split(':')[1]
        bucket=stats.setdefault(stage,{}).setdefault(arm,Counter())
        bucket.update({'cases':1,'definite':int(r['core_executed']),
            'raw_native_correct':int((r['native_score'] or {}).get('correct',False)),
            'fallback_required':int(r['fallback_required']),
            'declared_contract_called':int(bool(r['declared_contract_functions_actually_called']))})
        eligible=bool((r['native_score'] or {}).get('correct',False))
        note=''
        if arm=='BoundaryRefine':
            eligible=False
            if stage=='calibration':
                note='Derived residence=True is incorrectly accepted as an explicit GIVEN before raw dates; helper called, calendar branch bypassed. The true relationship-qualified premise is correctly read but cannot fix this.'
            elif key.startswith('cd2ab8'):
                note='False is text-absence of the GIVEN formulation, not a negative death-period premise. It bypasses the supplied actual death date; that date also fails the requested ISO format. Raw verdict wrong.'
            elif key.startswith('982d53'):
                note='Hospital commitment dates are misbound to penal commitment; 2017-01-01 service start is invented from a year-only case. Resolver remains unknown, so no false core success is credited.'
            else:
                note='Enrollment bounds are correctly observed, but exact service endpoints are unavailable. The learned total-interval contract cannot use the stated service year to establish sufficient temporal containment.'
        elif arm=='FreeReflect':
            if stage=='calibration':
                note='Raw ISO interval dates drive 34/365 computation and a decisive negative conjunct. The still-wrong coarse True is not consumed by the reached primitive-first branch.'
            elif key.startswith('cd2ab8'):
                note='Actual spouse death date2014-07-09 is used by source code to compare query year2015 with the preceding two years. Correct leaf condition, not entire surviving-spouse claim.'
            elif key.startswith('982d53'):
                note='Case names psychiatric hospital, not penal commitment; negative primitive event classification is consistent with native finite-case semantics. Source exclusion code consumes that classification, not a native verdict oracle.'
            else:
                note='The same employing university, enrollment and class attendance cover the queried2017. Three factual conditions are actually composed by the source rule; no whole-clause GIVEN field is bound.'
        else:
            if stage=='calibration':
                note='Actual raw ISO dates drive the source residence comparison and decisive negative conjunct; no fabricated age/joint-return premise is reached.'
            elif key.startswith('cd2ab8'):
                eligible=False
                note='Native answer correct, but source code returns on a supposed complete GIVEN legal condition inferred by the reader from the death date. It bypasses available raw-date computation. This actual path is not eligible evidence of the claimed core computation.'
            elif key.startswith('982d53'):
                note='Service is read but penal commitment is unresolved. Fallback required and not executed; not an erroneous final answer or core success.'
            else:
                note='School service, enrollment and attendance are case-grounded and combined by actual source code. Correct corresponding path.'
        bucket.update({'correct_with_corresponding_semantic_evidence':int(eligible)})
        reviews.append({'stage':stage,'arm':arm,'source':r['source'],
            'raw_native_score_unchanged':r['native_score'],
            'correct_with_corresponding_semantic_evidence':eligible,'review':note,
            'no_raw_value_replaced_or_new_grading_label_sent_to_model':True})
    summary={'same_goal':True,'goal_complete':False,'results':records,'stage_statistics':stats,
        'semantic_review':reviews,'calls':calls,'physical_cost':costs,
        'cumulative':Counter(r[1] for r in rows),'ledger_rows':len(rows),'pending':0,
        'old_rows_unchanged':len(before),
        'ledger_sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
        'teacher_cash_invoice_available':False,'executor_incremental_API_cash':0,'GPU_cash_allocation_unknown':True,
        'historical_seed_costs_not_free':'BoundaryRefine/FreeReflect share source151 acquisition and scoped-premise repair. Charge the actual seed creation/repair cost to each logical end-to-end arm; physically count shared requests once.',
        'fair_comparison':'BoundaryRefine vs FreeReflect share seed, law and feedback: matched update screen. PrimitiveGiven independently acquires from the same current law/date feedback but does not receive the seed earlier151 calibration history; it is an additional strong simple diagnostic, not a matched-lifetime-supervision end-to-end claim.',
        'known_input_selector_scope':'Offline diagnostic only; actual teachers receive the same complete calendar counterexample. No claim that the host selector was an independently tested online learning mechanism.',
        'decision':'Close this finite instance. Reuse actual FreeReflect source program as a working asset, not a proven contribution. No post-transfer retuning or expanded experiment. Two contributions still unestablished.'}
    immutable_json(OUT/'executor_wire_profile_check.json',{'requests':profile,'all12_thinking_OFF_and8192':True})
    immutable_json(OUT/'stage_result.json',summary)
    print(json.dumps({k:summary[k] for k in ('stage_statistics','physical_cost','cumulative','ledger_rows','old_rows_unchanged','pending')},ensure_ascii=False))


if __name__=='__main__':
    run()
