"""Summarize the frozen finite run; never dispatch models or edit raw results."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from experiments.legal_skill_evolution_focused_reader import material,PHASE
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def main():
    f,p,l,public,bundles=material();out=Path(__file__).resolve().parent
    with l.transaction() as db:
        rows=[dict(zip(['id','role','status','result'],r)) for r in db.execute('select id,role,status,result from calls')]
    assert not any(r['status']=='reserved' for r in rows)
    ledger={r['id']:{**r,'result':json.loads(r['result'])} for r in rows}
    summary=[]
    for stage in ['smoke','reuse']:
        completed=json.loads((f/PHASE/stage/'completed.json').read_text())
        for filename in completed['result_files']:
            row=json.loads((f/filename).read_text());runtime=row['runtime'];views=row['views']
            events=runtime['events'];physical=[e for e in events if not e['result'].get('cache_hit',False)]
            summary.append({'stage':stage,'arm':row['arm'],'source':row['source'],
                'planned':runtime['planned_queries'],'answered':runtime['answered_queries'],
                'new_physical_requests':len(physical),'recovered_or_exact_cached_batches':len(events)-len(physical),
                'new_request_seconds':sum(e['result']['elapsed_seconds'] for e in physical),
                'new_prompt_tokens':sum(e['result']['usage']['prompt_tokens'] for e in physical),
                'new_output_tokens':sum(e['result']['usage']['completion_tokens'] for e in physical),
                'core':sum(v['core_executed'] for v in views),'native_correct':sum(bool(v['score'] and v['score']['correct']) for v in views),
                'new_targets_correct':sum(bool(v['new_effect_target'] and v['score'] and v['score']['correct']) for v in views),
                'fallback_not_executed':sum(v['fallback'] for v in views),'all_views':len(views),
                'root_kinds':[n['term'][0] for n in row['interpretation']['nodes']],
                'unresolved':runtime['source_output']['unresolved'],'raw_result':filename})
    assert len(summary)==6
    for version in ['focused_execution',PHASE]:
        protocol=json.loads((f/version/'protocol.json').read_text())
        for name,h in protocol['source_sha256'].items():
            source=(f/version/'source_snapshot'/name) if version=='focused_execution' else ROOT/name
            assert hashlib.sha256(source.read_bytes()).hexdigest()==h
            if version==PHASE:
                dst=f/version/'source_snapshot'/name;dst.parent.mkdir(parents=True,exist_ok=True)
                if dst.exists():assert dst.read_bytes()==source.read_bytes()
                else:shutil.copyfile(source,dst)
            dest=out/'frozen_execution_versions'/version/(name+'.txt');dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():assert dest.read_bytes()==source.read_bytes()
            else:shutil.copyfile(source,dest)
    immutable_json(f/PHASE/'result_summary.json',{'rows':summary,'goal_complete':False,
        'first_contribution_established':False,'second_contribution_established':False,
        'same_goal':True,'finite_queue_closed':True,'no_reuse_adaptation':True,
        'NoExamples_not_dispatched':'No claimed reuse gain or operative reuse roots to isolate; planned ablation remains unperformed, not passed.'})
    # Preserve the published earlier usage checkpoint as historical evidence.
    old=out/'usage_summary.json';history=out/'usage_summary_first_checkpoint.json'
    if not history.exists():shutil.copyfile(old,history)
    initial=json.loads((ROOT/'artifacts/legal_skill_evolution_semantic_operations_20261113/ledger_before.json').read_text())['rows']
    ids={r[0] for r in initial};added=[r for r in ledger.values() if r['id'] not in ids]
    es=[r['result'] for r in added if r['role']=='executor'];ts=[r['result'] for r in added if r['role']=='teacher' and r['status']=='completed']
    usage={'executor_physical':len(es),'executor_input_tokens':sum(r['usage']['prompt_tokens'] for r in es),
        'executor_output_tokens':sum(r['usage']['completion_tokens'] for r in es),
        'executor_elapsed_seconds':sum(r['elapsed_seconds'] for r in es),
        'all_executor_thinking_OFF':all(r['thinking_requested'] is False and not r.get('reasoning_content') for r in es),
        'known_successful_teacher_input_tokens':sum(r['invocation']['usage']['input_tokens'] for r in ts),
        'known_successful_teacher_output_tokens':sum(r['invocation']['usage']['output_tokens'] for r in ts),
        'known_successful_teacher_reasoning_tokens_included_in_output':sum(r['invocation']['usage'].get('reasoning_output_tokens',0) for r in ts),
        'failed_teacher_token_usage':'unknown','no_new_models_or_configurations':True,'goal_complete':False}
    old.write_text(json.dumps(usage,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'summary':summary,'usage':usage,'cumulative':dict(Counter(r['role'] for r in ledger.values()))},ensure_ascii=False))

if __name__=='__main__':main()
