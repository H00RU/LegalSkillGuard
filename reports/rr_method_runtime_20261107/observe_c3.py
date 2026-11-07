"""Read-only c3 process/ledger observations; writes unbound status/evidence only."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time


def main():
    root=Path(__file__).resolve().parents[2]
    stage=root/'artifacts/rr_method_runtime_20261107/method_runtime_c3_20261107'
    controller=json.loads((stage/'controller.json').read_text())
    proc=Path('/proc')/str(controller['pid'])
    try:alive=int((proc/'stat').read_text().split(') ',1)[1].split()[19])==controller['start_ticks']
    except FileNotFoundError:alive=False
    records=[json.loads(p.read_text()) for p in sorted((stage/'thinking/records').glob('*.json'))]
    with sqlite3.connect('file:'+str(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True) as db:
        counts=dict(db.execute('select role,count(*) from calls group by role'))
        calls=[]
        for call_id,source,status,reserved,result in db.execute(
                'select id,source,status,reserved_at,result from calls where id like ? order by reserved_at',
                ('method_runtime_c3_20261107:thinking:%',)):
            result=json.loads(result) if result else {}
            item={'id':call_id,'source':source,'status':status,'usage':result.get('usage'),
                  'elapsed_seconds':result.get('elapsed_seconds'),'finish_reason':result.get('finish_reason')}
            if status=='reserved':item['seconds_since_reserved']=round(time.time()-reserved,1)
            if result.get('finish_reason')=='length':
                raw=result.get('content') or ''
                names=re.findall(r'"name"\s*:\s*"([^"\\]*)"',raw)
                item['truncation_observation']={'raw_content_sha256':hashlib.sha256(raw.encode()).hexdigest(),
                    'raw_characters':len(raw),'complete_names':len(names),
                    'max_complete_name_characters':max(map(len,names),default=0),
                    'repeated_phrase_60_days_fuel_and_provisions':raw.count('60_days_fuel_and_provisions'),
                    'top_fields_seen':[k for k in ('bindings','observations','rule_residuals','nodes','scopes','clauses','query') if '"'+k+'"' in raw],
                    'interpretation':'Physical output limit was reached; this is not an executor execution timeout. Long repeated internal names, if observed, cannot be cured by claiming more legal semantics.'}
            calls.append(item)
    profiles=[{'source':r['source'],'dataset':r['dataset'],'thinking':r['thinking'],
               'structural_pass':r['structural_pass'],'TRAIN_correct':r['task_correct'],
               'usage':r['usage'],'elapsed_seconds':r['elapsed_seconds'],
               'last_error':r['prediction']['result'].get('error')} for r in records]
    now=datetime.now(timezone.utc).isoformat()
    status={'captured_utc':now,'controller':controller,'identity_live':alive,'session':59074,
        'counts':counts,'pending':sum(c['status']=='reserved' for c in calls),'completed_profiles':len(profiles),
        'expected_profiles':40,'profiles':profiles,'calls':calls,'comparison_complete':len(profiles)==40,
        'settled_c3_tokens':{k:sum(c['usage'][k] for c in calls if c['usage'])
            for k in ('prompt_tokens','completion_tokens')},
        'settled_c3_request_seconds':sum(c['elapsed_seconds'] or 0 for c in calls),
        'finish_reasons':dict(Counter(c['finish_reason'] for c in calls if c['finish_reason'])),
        'API_incremental_cash_usd':0,'GPU_allocation_cost_usd':None,'full_goal_complete':False,
        'new_model_calls_by_observer':0}
    folder=root/'reports/rr_method_runtime_20261107'
    (folder/'current_c3_live_status.json').write_text(json.dumps(status,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    p=root/'docs/rr_v2/method_runtime_state_20261107.json';state=json.loads(p.read_text())
    current=state['current_run_id']=='method_runtime_c3_20261107'
    if current:
        state.update(executor_total=counts['executor'],teacher_total=counts['teacher'],pending_requests=status['pending'],
            current_complete_thinking_profiles=len(profiles),new_model_calls=counts['executor']-424+counts['teacher']-14,
            controller_processes=[controller] if alive else [],last_update_utc=now)
        p.write_text(json.dumps(state,ensure_ascii=False,sort_keys=True)+'\n')
    p=root/'reports/legalskillguard_method_runtime_20261107.md';text=p.read_text()
    marker='<!-- current_live_status -->';end='<!-- /current_live_status -->'
    summary=(f'实时状态（{now}）：修复提交cadff0a，c3固定20来源配对已完成{len(profiles)}/40配置；'
        f'controller PID{controller["pid"]}/start_ticks{controller["start_ticks"]}，真实身份存活={alive}，'
        f'现存session59074。累计{counts["executor"]}E/{counts["teacher"]}T、在途{status["pending"]}。'
        '源配置仍OFF，仅此明确配对可ON；未完成配对不能选择配置或声明语义通过。'
        '实际错误和输出截断、逐请求用量见[当前证据](rr_method_runtime_20261107/current_c3_live_status.json)。'
        '325项离线检查及128来源输入容量检查完成；旧c1六条响应、原账本和历史库保留。'
        '新128建库、六臂DEV、TEST尚未开始，Goal active未完成。核实现存任务，不重复启动或热改冻结文件。')
    if current and marker in text and end in text:
        text=text[:text.index(marker)]+marker+'\n'+summary+'\n'+end+text[text.index(end)+len(end):]
        p.write_text(text)
    print(json.dumps({k:v for k,v in status.items() if k not in {'calls','profiles'}},ensure_ascii=False))
    for p in profiles:print(json.dumps(p,ensure_ascii=False))


if __name__=='__main__':main()
