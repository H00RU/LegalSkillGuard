"""Observe one sealed live method run; no model, oracle, or grading access."""
import argparse
import base64
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from legal_skill_guard.rr.source_inference import _decode
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.source_validation import validation_feedback
from legal_skill_guard.rr.wire_validation import validate_wire
from legal_skill_guard.rr.preflight import science_files


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[2];stage=root/'artifacts/rr_method_runtime_20261107'/args.run_id
    seal=json.loads((stage/'seal.json').read_text());unchanged=science_files(root)==seal['files']
    if not unchanged:raise AssertionError('Observe the sealed code only; do not regrade under changed science')
    controller=json.loads((stage/'controller.json').read_text());stat=Path('/proc')/str(controller['pid'])/'stat'
    try:alive=int(stat.read_text().split(') ',1)[1].split()[19])==controller['start_ticks']
    except FileNotFoundError:alive=False
    sources={s['key']:s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']}
    out=root/'reports/rr_method_runtime_20261107'/(args.run_id+'_source_only_observation.json')
    previous=json.loads(out.read_text()) if out.exists() else {};old={c['call_id']:c for c in previous.get('calls',[])}
    calls=[]
    with sqlite3.connect('file:'+str(root/seal['ledger_path'])+'?mode=ro',uri=True) as db:
        counts=dict(db.execute('select role,count(*) from calls group by role'))
        pending=db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
        rows=db.execute('select id,source,status,reserved_at,result from calls where id like ? order by reserved_at',
                        (args.run_id+':thinking:%',)).fetchall()
    for call_id,source,status,reserved,encoded in rows:
        if status!='reserved' and call_id in old and old[call_id]['status']!='reserved':
            calls.append(old[call_id]);continue
        result=json.loads(encoded) if encoded else {};raw=result.get('content')
        item={'call_id':call_id,'source':source,'status':status,'finish_reason':result.get('finish_reason'),
            'usage':result.get('usage'),'elapsed_seconds':result.get('elapsed_seconds')}
        if status=='reserved':item['seconds_since_reserved']=round(time.time()-reserved,1)
        elif raw is not None:
            item['raw_content_sha256']=hashlib.sha256(raw.encode()).hexdigest()
            try:program=_decode(raw)
            except Exception as exc:item['decode_error']={'type':type(exc).__name__,'message':str(exc)}
            else:
                item['decoded']=True
                wire=json.loads((Path(result['artifact_directory'])/'wire_request.json').read_text())
                schema=json.loads(base64.b64decode(wire['body_b64']))['response_format']['json_schema']['schema']
                try:validate_wire(program,schema);item['actual_wire_valid']=True
                except Exception as exc:
                    item.update(actual_wire_valid=False,wire_error={'type':type(exc).__name__,'message':getattr(exc,'message',str(exc)),
                        'path':list(getattr(exc,'path',[]))})
                try:item['source_only_feedback']=validation_feedback(sources[source],program)
                except Exception as exc:item['feedback_error']={'type':type(exc).__name__,'message':str(exc)}
                try:
                    compile_source(sources[source],program,library={'frozen':False,'patterns':[]})
                    item['offline_compiles']=True
                except Exception as exc:
                    item.update(offline_compiles=False,compile_error={'type':type(exc).__name__,
                        'message':getattr(exc,'message',str(exc)),'path':list(getattr(exc,'path',[]))})
        calls.append(item)
    profiles=[json.loads(p.read_text()) for p in sorted((stage/'thinking/records').glob('*.json'))]
    now=datetime.now(timezone.utc).isoformat()
    value={'captured_utc':now,'run_id':args.run_id,'controller':controller,'identity_live':alive,
        'sealed_science_unchanged':unchanged,'counts':counts,'pending_global':pending,
        'completed_profiles':len(profiles),'expected_profiles':40,
        'structural_profiles':sum(bool(r['structural_pass']) for r in profiles),
        'already_recorded_TRAIN_matches':sum(bool(r['task_correct']) for r in profiles),
        'profiles':[{'source':r['source'],'dataset':r['dataset'],'thinking':r['thinking'],
            'structural_pass':r['structural_pass'],'already_recorded_TRAIN_match':r['task_correct'],
            'usage':r['usage'],'elapsed_seconds':r['elapsed_seconds']} for r in profiles],
        'calls':calls,'finish_reasons':dict(Counter(c['finish_reason'] for c in calls if c['finish_reason'])),
        'settled_tokens':{k:sum((c['usage'] or {}).get(k,0) for c in calls) for k in ('prompt_tokens','completion_tokens')},
        'settled_seconds':sum(c['elapsed_seconds'] or 0 for c in calls),
        'decoded_responses':sum(bool(c.get('decoded')) for c in calls),
        'actual_wire_violations':sum(c.get('actual_wire_valid') is False for c in calls),
        'new_model_calls_by_observer':0,'grading_packets_opened':False,'oracle_calls':0,
        'fallback_or_synthetic_results_counted_as_core_success':False,'full_goal_complete':False}
    out.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    p=root/'docs/rr_v2/method_runtime_state_20261107.json';state=json.loads(p.read_text())
    if state['current_run_id']==args.run_id:
        state.update(executor_total=counts['executor'],teacher_total=counts['teacher'],pending_requests=pending,
            new_model_calls=counts['executor']-424+counts['teacher']-14,current_complete_thinking_profiles=len(profiles),
            controller_processes=[controller] if alive else [],last_update_utc=now,
            current_source_only_observation=str(out.relative_to(root)))
        p.write_text(json.dumps(state,ensure_ascii=False,sort_keys=True)+'\n')
        summary=(f'实时状态（{now}）：当前{args.run_id}，controller PID{controller["pid"]}/'
            f'start_ticks{controller["start_ticks"]}，真实身份存活={alive}，现存session{state["controller_session"]}。'
            f'原固定20配对已完成{len(profiles)}/40配置，结构通过{value["structural_profiles"]}、'
            f'已记录TRAIN匹配{value["already_recorded_TRAIN_matches"]}；'
            f'累计{counts["executor"]}E/{counts["teacher"]}T、pending{pending}。'
            f'{state["current_related_offline_checks_passed"]}项离线检查通过，运行绑定的{len(seal["files"])}文件不变；原配置仍OFF，仅本配对可ON。'
            '原始输出、账本和旧库保留，失败不补语义；不凭部分结果选择配置或宣布方法成功。'
            '新128建库/六臂DEV/TEST尚未开始，Goal active未完成。核实现存任务，不重复启动或热改冻结文件。')
        p=root/'reports/legalskillguard_method_runtime_20261107.md';report=p.read_text()
        start='<!-- current_live_status -->';end='<!-- /current_live_status -->'
        p.write_text(report[:report.index(start)]+start+'\n'+summary+'\n'+end+report[report.index(end)+len(end):])
        for directory in (root,Path('/home/yndx/hhy/legal-skill-current')):
            for name in ('PROJECT_MAP.md','docs/CURRENT_GOAL.md','docs/handoff_next_stage.md'):
                p=directory/name;lines=p.read_text().splitlines()
                i=next(i for i,line in enumerate(lines) if line.startswith('实时状态（'));lines[i]=summary
                p.write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k not in {'calls','profiles'}},ensure_ascii=False))
    for c in calls:
        print(json.dumps({k:c[k] for k in ('call_id','status','finish_reason','offline_compiles','compile_error','decode_error') if k in c},ensure_ascii=False))


if __name__=='__main__':main()
