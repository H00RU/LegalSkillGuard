"""Preserve the finished finite update comparison without more model calls."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.scoped_grammar import material_public

ROOT = Path(__file__).resolve().parents[3]
RUN = 'legal_skill_evolution_open_effect_acquisition_20261113'
FOLDER = ROOT / 'artifacts' / RUN
OUT = Path(__file__).resolve().parent
read = lambda p: json.loads(p.read_text())
sha = lambda b: hashlib.sha256(b).hexdigest()


def copy_raw(src, dest):
    raw = src.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.read_bytes() != raw:
        # Recover an exporter-only key-sort change (integer keys round-trip to
        # strings). The authoritative input is copied byte for byte.
        assert json.loads(dest.read_bytes()) == json.loads(raw)
    dest.write_bytes(raw)
    assert sha(src.read_bytes()) == sha(dest.read_bytes()), str(src)


if __name__ == '__main__':
    protocol = read(FOLDER / 'protocol.json')
    assert (FOLDER / 'cache_reuse/completed.json').exists()
    for path, expected in {**protocol['source_snapshot'], **protocol['data_sha256']}.items():
        assert sha((ROOT / path).read_bytes()) == expected, path
    with sqlite3.connect(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') as conn:
        before = read(FOLDER / 'ledger_rows_before.json')['rows']
        after = [list(r) for r in conn.execute('select * from calls order by id')]
        cols = [v[1] for v in conn.execute('pragma table_info(calls)')]
    old = {r[0]: r for r in before}
    current = {r[0]: r for r in after}
    assert all(current[k] == value for k, value in old.items())
    new = [dict(zip(cols, r)) for r in after if r[0] not in old]
    assert len(new) == 3 and all(r['role'] == 'teacher' and r['id'].startswith(RUN) for r in new)
    assert not any(r[cols.index('status')] == 'reserved' for r in after)
    requests = []
    for row in new:
        value = json.loads(row['result'])
        invocation = value.get('invocation', {})
        requests.append({k: row[k] for k in ('id','role','purpose','bucket','source','request_hash','status','reserved_at')})
        requests[-1].update(elapsed_seconds=value.get('elapsed_seconds'),
            usage=invocation.get('usage'), actual_cash_usd=None,
            result_or_failure=value)
    totals = Counter((r[cols.index('role')], r[cols.index('status')]) for r in after)
    known_usage = Counter()
    for row in requests:
        for key, value in (row['usage'] or {}).items():
            if isinstance(value, (int, float)): known_usage[key] += value
    existing_cost = OUT / 'cost_and_request_ledger.json'
    captured = read(existing_cost)['captured_utc'] if existing_cost.exists() else datetime.now(timezone.utc).isoformat()
    ledger = {'captured_utc': captured,
        'new_physical_requests': {'executor':0,'teacher':3},
        'new_statuses': dict(Counter(r['status'] for r in requests)),
        'cumulative': {role:sum(n for (r,s),n in totals.items() if r==role) for role in ('executor','teacher')},
        'status_counts': {role:{s:n for (r,s),n in totals.items() if r==role} for role in ('executor','teacher')},
        'pending':0,'old_rows':len(before),'new_rows':len(new),'total_rows':len(after),
        'old_rows_unchanged':True,'ledger_sha256':sha(json.dumps(after,ensure_ascii=False,separators=(',',':')).encode()),
        'requests':requests,'known_usage_on_two_successes':dict(known_usage),
        'failed_request_usage_unknown':True,
        'sum_request_elapsed_seconds':sum(r['elapsed_seconds'] or 0 for r in requests),
        'sum_request_time_is_not_parallel_wall_time':True,
        'reasoning_included_in_output_tokens_not_added_twice':True,
        'teacher_cash_invoice_available':False,'actual_teacher_cash_usd':None,
        'new_executor_api_cash_usd':0,'GPU_cash_allocation_usd':None,
        'existing_acquisition_costs_not_zeroed':True,'goal_complete':False}
    immutable_json(OUT / 'cost_and_request_ledger.json', ledger)
    stages = {}
    public = {s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    review_material = []
    for stage, arms in [('development',('SourceEffect','IndependentOpen')),
                        ('reuse',('SourceEffect','IndependentOpen')),
                        ('cache_development',('SharedRuleCache',)),
                        ('cache_reuse',('SharedRuleCache',))]:
        stages[stage] = {}
        for arm in arms:
            result = read(FOLDER / stage / arm / 'completed.json')
            copy_raw(FOLDER / stage / arm / 'completed.json', OUT / 'results' / stage / (arm+'.json'))
            rows = result['results']
            stages[stage][arm] = {}
            for group, targets in [('disclosure',('nda-5','nda-7')),('new_effects',('nda-16','nda-20')),('all',None)]:
                views=[v for r in rows for v in r['views'] if targets is None or v['view'] in targets]
                stages[stage][arm][group]={'total':len(views),'core_executed':sum(v['core_executed'] for v in views),
                    'core_native_correct':sum(v['core_executed'] and v['score']['correct'] for v in views),
                    'fallback':sum(v['fallback'] for v in views),
                    'fallback_fraction':sum(v['fallback'] for v in views)/len(views),
                    'native_correct_including_fallback':sum(v['score']['correct'] for v in views),
                    'not_full_source_semantics_certification':True}
            if arm=='SharedRuleCache':continue
            for row in rows:
                spans=source_spans(material_public(public[row['source']]['views'][0]['public']))
                item={'stage':stage,'arm':arm,'source':row['source'],'new_effects':[]}
                for view in row['views']:
                    if view['view'] not in ('nda-16','nda-20'):continue
                    execution=(view.get('execution') or {}).get('value')
                    nodes=[]
                    if execution and row['interpretation']:
                        for idx in execution['used_nodes']:
                            n=row['interpretation']['nodes'][idx]
                            nodes.append({'id':idx,'term':n['term'],'support_ids':n['support_ids'],
                                'actual_cited_source':[spans[i] for i in n['support_ids']]})
                    item['new_effects'].append({'view':view['view'],'answer':view['answer'],
                        'core_executed':view['core_executed'],'native_correct':view['score']['correct'],
                        'error':view['error'],'execution':execution,'used_source_nodes':nodes})
                review_material.append(item)
    immutable_json(OUT/'stage_result.json',{'stages':stages,'goal_complete':False,
        'two_effects_are_not_two_method_contributions':True,
        'first_contribution_established':False,'second_contribution_established':False,
        'both_independent_updates_used_compiler_architecture':True,
        'shared_initial_library_not_independent_end_to_end_acquisition':True,
        'reuse_frozen_before_source_or_grading_access':True,'adaptive_reuse_repair':False,
        'new_DEV_TEST_or_full_study':False})
    immutable_json(OUT/'actual_effect_proofs.json',{'results':review_material,
        'native_correct_is_not_source_truth':True,'review_by_main_executor_separate':True})
    raw_files=['protocol.json','recovery_execution_manifest.json','structural_execution_manifest.json',
        'teachers_settled.json','reuse_freeze.json','shared_rule_bank.json',
        'SourceEffect/teacher_input.json','SourceEffect/compact_retry_input.json','SourceEffect/teacher.json',
        'SourceEffect/offline_compile_error.json','SourceEffect/structural_recovery.json',
        'SourceEffect/adapted_proposal.json','SourceEffect/compiled.json','SourceEffect/induced_grammar.json',
        'IndependentOpen/teacher_input.json','IndependentOpen/teacher.json',
        'IndependentOpen/offline_compile_error.json','IndependentOpen/metadata_recovery.json',
        'IndependentOpen/adapted_proposal.json','IndependentOpen/compiled.json','IndependentOpen/induced_grammar.json']
    for name in raw_files:copy_raw(FOLDER/name,OUT/'raw'/name)
    failures=list((FOLDER/'teacher_adapter_cache/_failures/skill_teacher').glob('*.json'))
    assert len(failures)==1
    copy_raw(failures[0],OUT/'raw/first_SourceEffect_timeout.json')
    unit=ROOT/'artifacts/legal_skill_evolution_source_unit_preflight_20261113/completed.json'
    copy_raw(unit,OUT/'source_unit_preflight.json')
    immutable_json(OUT/'preservation.json',{'bound_source_files_unchanged':len(protocol['source_snapshot']),
        'bound_data_files_unchanged':len(protocol['data_sha256']),
        'old_ledger_rows_unchanged':len(before),'pending':0,
        'raw_original_teacher_responses_preserved':True,
        'no_model_or_sampling_change':True,'no_new_executor_calls':True,
        'no_test_or_dev_labels_used':True,'no_adaptive_reuse_repairs':True,
        'lossless_representation_recoveries_are_not_method_contributions':True,'goal_complete':False})
    print(json.dumps({'stages':stages,'ledger':{k:ledger[k] for k in ('new_physical_requests','cumulative','pending','known_usage_on_two_successes','sum_request_elapsed_seconds')}}))
