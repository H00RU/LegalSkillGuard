"""Observe the current sealed source probe; no generation, grading or repair."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time

from legal_skill_guard.rr.preflight import science_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    stage = root / 'artifacts/rr_method_runtime_20261107' / args.run_id
    seal = json.loads((stage / 'seal.json').read_text())
    assert science_files(root) == seal['files'], 'Sealed scientific files changed'
    state_path = root / 'docs/rr_v2/method_runtime_state_20261107.json'
    state = json.loads(state_path.read_text())
    assert state['active_probe_run_id'] == args.run_id
    pid, ticks = state['controller_pid'], state['controller_start_ticks']
    try:
        alive = int((Path('/proc') / str(pid) / 'stat').read_text().split(') ', 1)[1].split()[19]) == ticks
    except FileNotFoundError:
        alive = False
    cfg = json.loads((root / 'configs/rr_v2_preflight.json').read_text())
    prefix = args.run_id + ':'
    with sqlite3.connect('file:' + str(root / cfg['ledger_path']) + '?mode=ro', uri=True) as db:
        counts = dict(db.execute('select role,count(*) from calls group by role'))
        pending = db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
        rows = db.execute('select id,status,reserved_at,result from calls where substr(id,1,?)=? order by reserved_at',
                          (len(prefix), prefix)).fetchall()
    calls = []
    for cid, status, reserved, encoded in rows:
        result = json.loads(encoded) if encoded else {}
        calls.append({'call_id': cid, 'status': status, 'finish_reason': result.get('finish_reason'),
                      'usage': result.get('usage'), 'elapsed_seconds': result.get('elapsed_seconds'),
                      'seconds_since_reserved': round(time.time() - reserved, 1) if status == 'reserved' else None})
    result_path = stage / 'result.json'
    result = json.loads(result_path.read_text()) if result_path.exists() else {}
    now = datetime.now(timezone.utc).isoformat()
    observation = {'captured_utc': now, 'run_id': args.run_id, 'source': seal['source']['key'],
                   'identity_live': alive, 'pid': pid, 'start_ticks': ticks,
                   'sealed_science_unchanged': True, 'thinking': seal['config']['executor']['enable_thinking'],
                   'counts': counts, 'pending_global': pending, 'calls': calls,
                   'stored_result_status': result.get('status'), 'error_type': result.get('error_type'),
                   'error': result.get('error'), 'stored_after_status': result.get('after', {}).get('status'),
                   'stored_TRAIN_match': result.get('TRAIN_score', {}).get('task_correct'),
                   'observer_generation_and_oracle_calls': 0, 'grading_packets_opened_by_observer': False,
                   'full_goal_complete': False}
    (root / 'reports/rr_method_runtime_20261107' / (args.run_id + '_observation.json')).write_text(
        json.dumps(observation, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    state.update(executor_total=counts['executor'], teacher_total=counts['teacher'], pending_requests=pending,
                 new_model_calls=counts['executor'] - 424 + counts['teacher'] - 14, last_update_utc=now,
                 controller_processes=[{'pid': pid, 'start_ticks': ticks, 'action': 'source_probe', 'status': 'running'}] if alive else [])
    state_path.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True) + '\n')
    summary = (f'实时状态（{now}）：c6原固定20配对40/40结束、主路径通过0，OFF锁定；'
               f'当前{args.run_id}，PID{pid}/start_ticks{ticks}，身份存活={alive}，session{state["controller_session"]}，'
               f'累计{counts["executor"]}E/{counts["teacher"]}T、pending{pending}。'
               f'修复版{state["implementation_commit"]}经{state["current_related_offline_checks_passed"]}项离线和22项后端检查，当前真实结果={result.get("status", "in_progress")}。'
               '原始结果和冻结库保留；新128建库/六臂DEV/TEST尚未开始，Goal active未完成。')
    report = root / 'reports/legalskillguard_method_runtime_20261107.md'
    text = report.read_text(); start, end = '<!-- current_live_status -->', '<!-- /current_live_status -->'
    report.write_text(text[:text.index(start)] + start + '\n' + summary + '\n' + end + text[text.index(end) + len(end):])
    for directory in (root, Path('/home/yndx/hhy/legal-skill-current')):
        for name in ('PROJECT_MAP.md', 'docs/CURRENT_GOAL.md', 'docs/handoff_next_stage.md'):
            path = directory / name; lines = path.read_text().splitlines()
            index = next(i for i, line in enumerate(lines) if line.startswith('实时状态（'))
            lines[index] = summary; path.write_text('\n'.join(lines) + '\n')
    print(json.dumps(observation, ensure_ascii=False))


if __name__ == '__main__':
    main()
