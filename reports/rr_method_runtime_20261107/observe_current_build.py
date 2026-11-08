"""Read-only experiment observation; writes only unbound status/evidence files."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.preflight import science_files


def committed_source_records(stage, seal):
    state_file = stage / 'build/state.json'
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    committed = state.get('complete_sources', 0)
    hashes = state.get('source_hashes', [])
    assert len(hashes) == committed
    records = []
    for position, source in enumerate(seal['sources']['train'][:committed]):
        path = stage / 'build/sources' / (digest(source) + '.json')
        record = json.loads(path.read_text())
        assert record['source'] == source and digest(record) == hashes[position]
        records.append(record)
    assert len(records) == committed
    source_files = len(list((stage / 'build/sources').glob('*.json')))
    return state, source_files, records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--session-id', type=int, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    stage = root / 'artifacts/rr_method_runtime_20261107' / args.run_id
    seal = json.loads((stage / 'seal.json').read_text())
    assert science_files(root) == seal['files'], 'Frozen experiment files changed'
    controller = json.loads((stage / 'controller.json').read_text())
    try:
        process_stat = (Path('/proc') / str(controller['pid']) / 'stat').read_text().split(') ', 1)[1].split()
        identity_live = int(process_stat[19]) == controller['start_ticks']
        if identity_live and process_stat[0] in {'T', 't'}:
            controller = {**controller, 'recorded_status': controller['status'],
                          'status': 'held_between_requests', 'process_state': process_stat[0]}
    except FileNotFoundError:
        identity_live = False
    with sqlite3.connect('file:' + str(root / seal['ledger_path']) + '?mode=ro', uri=True) as db:
        db.execute('begin')
        counts = dict(db.execute('select role,count(*) from calls group by role'))
        pending = [{'call_id': cid, 'role': role, 'seconds_since_reserved': round(time.time() - reserved, 1)}
            for cid, role, reserved in db.execute("select id,role,reserved_at from calls where status='reserved'")]
        prefix = args.run_id + ':'
        run_calls = db.execute('select role,status,result from calls where substr(id,1,?)=?', (len(prefix), prefix)).fetchall()
    build_state, source_files, records = committed_source_records(stage, seal)
    committed = build_state.get('complete_sources', 0)
    rows = []
    for position, record in enumerate(records):
        outcome = record['prediction']['result']
        controlled_fallback = bool(outcome.get('model_source_IR_still_unresolved'))
        native_fallback = outcome['fallback_used']
        rows.append({'source': record['source'], 'source_position': position, 'dataset': record['dataset'],
            'program_status': outcome['program_status'], 'certificate_status': outcome['certificate_status'],
            'TRAIN_match_including_predefined_paths': record['score']['task_correct'],
            'fallback_used': native_fallback or controlled_fallback,
            'native_fallback_used': native_fallback,
            'controlled_Horn_fallback_used': controlled_fallback,
            'model_source_IR_compiled': outcome['program_status'] == 'source_IR_compiled',
            'conditional_source_IR_certificate': outcome['A_main_path_executed'],
            'stored_pattern_executed': outcome['B_main_path_executed'],
            'learning_status': record['learning']['status']})
    completion_file = stage / 'build/completion.json'
    completion = json.loads(completion_file.read_text()) if completion_file.exists() else None
    now = datetime.now(timezone.utc).isoformat()
    observation = {'captured_utc': now, 'run_id': args.run_id, 'controller': controller,
        'identity_live': identity_live, 'session_id': args.session_id, 'sealed_science_unchanged': True,
        'counts': counts, 'pending': pending, 'source_records': source_files, 'committed_sources': committed,
        'uncommitted_source_records': source_files - committed,
        'TRAIN_metric_scope': 'state_committed_prefix_with_verified_record_digests',
        'expected_sources': 128, 'expected_batches': 8,
        'completed_batches': build_state.get('completed_batches', 0),
        'datasets_completed': dict(Counter(row['dataset'] for row in rows)),
        'source_IR_compiled': sum(row['model_source_IR_compiled'] for row in rows),
        'conditional_source_IR_certificates': sum(row['conditional_source_IR_certificate'] for row in rows),
        'stored_pattern_execution_sources': sum(row['stored_pattern_executed'] for row in rows),
        'TRAIN_matches_including_predefined_paths': sum(row['TRAIN_match_including_predefined_paths'] for row in rows),
        'fallback_sources_including_Horn_recovery': sum(row['fallback_used'] for row in rows),
        'controlled_Horn_fallback_sources': sum(row['controlled_Horn_fallback_used'] for row in rows),
        'native_fallback_sources': sum(row['native_fallback_used'] for row in rows),
        'primary_source_IR_B_execution_sources': sum(row['stored_pattern_executed'] and row['model_source_IR_compiled'] and not row['fallback_used'] for row in rows),
        'TRAIN_matches_without_fallback': sum(row['TRAIN_match_including_predefined_paths'] and not row['fallback_used'] for row in rows),
        'program_status_counts': dict(Counter(row['program_status'] for row in rows)),
        'this_run_physical_counts': dict(Counter(row[0] for row in run_calls)),
        'build_completion_saved': completion is not None, 'new_generation_or_grading_by_observer': 0,
        'these_counts_do_not_certify_translation_faithfulness_or_goal_readiness': True,
        'full_goal_complete': False}
    folder = Path(__file__).resolve().parent
    (folder / (args.run_id + '_build_observation.json')).write_text(json.dumps(observation, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    finished_executor = [json.loads(result) for role, _, result in run_calls
                         if role == 'executor' and result]
    metrics = {'captured_utc': now, 'run_id': args.run_id,
        'metric_role': 'Current sealed build TRAIN prefix; not DEV, TEST or a source-faithfulness certificate',
        'sealed_code_hash': seal['code_hash'],
        'active_build_controller': identity_live and controller['status'] == 'running',
        'committed_sources': committed, 'expected_sources': 128,
        'completed_batches': observation['completed_batches'], 'expected_batches': 8,
        'prefix_denominator': len(rows),
        'source_status_scope': 'state_committed_prefix_with_verified_record_digests',
        'TRAIN_matches_including_fallback': observation['TRAIN_matches_including_predefined_paths'],
        'TRAIN_matches_without_fallback': observation['TRAIN_matches_without_fallback'],
        'model_source_IR_compiled': observation['source_IR_compiled'],
        'conditional_A_certificates': observation['conditional_source_IR_certificates'],
        'primary_model_IR_B_execution_sources': observation['primary_source_IR_B_execution_sources'],
        'fallback_sources': observation['fallback_sources_including_Horn_recovery'],
        'stored_pattern_execution_sources_including_fallback': observation['stored_pattern_execution_sources'],
        'settled_executor_responses': len(finished_executor),
        'response_count_scope': 'all_settled_physical_responses_in_this_run_including_uncommitted_sources',
        'executor_finish_reasons': dict(Counter(result.get('finish_reason') for result in finished_executor)),
        'this_run_physical_counts': observation['this_run_physical_counts'],
        'cumulative_physical_requests': counts, 'pending_requests': len(pending),
        'current_unified_128_build_complete': completion is not None,
        'current_six_arm_DEV_complete': False, 'full_goal_complete': False,
        'historical_metrics_preserved_separately': 'training_metrics_status_20261107_before_ast_build.json',
        'new_model_calls_by_this_status_check': 0, 'original_response_and_ledger_modified': False}
    (folder / 'training_metrics_status_20261107.json').write_text(json.dumps(metrics, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    if rows:
        with (folder / (args.run_id + '_source_status.csv')).open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)
    state_path = root / 'docs/rr_v2/method_runtime_state_20261107.json'
    state = json.loads(state_path.read_text())
    state.update(current_run_id=args.run_id, current_run_stage='build', active_build_run_id=args.run_id,
        previous_completed_thinking_run_id='method_runtime_c6_20261107',
        latest_completed_probe_run_id=state.get('latest_completed_probe_run_id','executor_compiler_contract_v2_20261107'),
        phase='fixed128_declarative_build_live' if identity_live and controller['status']=='running' else 'fixed128_build_' + controller['status'],
        implementation_commit=state['implementation_commit'], controller_pid=controller['pid'],
        controller_start_ticks=controller['start_ticks'], controller_session=args.session_id,
        controller_identity_live=identity_live, executor_total=counts['executor'], teacher_total=counts['teacher'],
        pending_requests=len(pending), last_update_utc=now, current_complete_sources=committed,
        current_source_records=source_files, full_fixed128_build_completed=completion is not None,
        next_action='Continue this exact sealed fixed128/8-batch build and record ordinary model errors without repair sweeps; preserve source budgets, frozen libraries and ledger. Observe the real PID/session, do not duplicate or change bound files. After build perform original six-arm DEV and mechanism/cross-bank audits; no TEST, paper or premature completion.')
    state['controller_processes'] = [controller] if identity_live else []
    if completion is not None and controller['status']=='completed':
        state['phase']='fixed128_build_completed_pending_DEV_and_core_audit'
        state['next_action']='Verify all original128 records,8 batches,B1/B8 and same-material MB with the sealed controller, then run original six-arm DEV once under locked OFF. Preserve the completed build; do not launch it again, inspect TEST or mark Goal complete before core/semantic/cross-bank delivery.'
    state_path.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    activity='运行中' if identity_live and controller['status']=='running' else controller['status']
    line = (f'实时状态（{now}）：统一版本{state["implementation_commit"][:7]}的原128来源/8批建库{activity}，来源记录{source_files}/128、已提交前缀{committed}；'
        f'实际PID{controller["pid"]}/start_ticks{controller["start_ticks"]}，身份存活={identity_live}，session{args.session_id}。'
        f'累计{counts["executor"]}E/{counts["teacher"]}T、pending{len(pending)}。'
        f'当前模型IR编译{observation["source_IR_compiled"]}、条件完成证书{observation["conditional_source_IR_certificates"]}；'
        f'Horn回退来源{observation["controlled_Horn_fallback_sources"]}，其图调用不计核心主路径通过；'
        '这些不等于源文语义验收。518项离线回归、八项实际解码后端及128输入容量核验通过，OFF已锁定。'
        '普通模型错误保留，旧结果/冻结库/账本不变；六臂DEV和TEST未启动，Goal active未完成。')
    report = root / 'reports/legalskillguard_method_runtime_20261107.md'
    text = report.read_text(); start, end = '<!-- current_live_status -->', '<!-- /current_live_status -->'
    text = text[:text.index(start)] + start + '\n' + line + '\n' + end + text[text.index(end) + len(end):]
    prefix_start, prefix_end = '<!-- current_train_prefix -->', '<!-- /current_train_prefix -->'
    denominator = len(rows)
    matches = observation['TRAIN_matches_including_predefined_paths']
    rate = f'{100 * matches / denominator:.2f}%' if denominator else '尚无已结算来源'
    prefix_text = (prefix_start + '\n## 当前统一版本的TRAIN前缀\n\n'
        f'更新时间：{now}；仅统计已结算的{denominator}个来源。\n\n'
        '| 指标 | 当前结果 |\n|---|---:|\n'
        f'| 已提交来源 / 原定来源 | {committed} / 128 |\n'
        f'| 已完成批次 / 原定批次 | {observation["completed_batches"]} / 8 |\n'
        f'| TRAIN匹配（含允许的回退） | {matches} / {denominator}（{rate}） |\n'
        f'| 无回退的TRAIN匹配 | {observation["TRAIN_matches_without_fallback"]} / {denominator} |\n'
        f'| 接纳的模型IR | {observation["source_IR_compiled"]} / {denominator} |\n'
        f'| A条件完成证书来源 | {observation["conditional_source_IR_certificates"]} / {denominator} |\n'
        f'| B模型IR路径实际执行来源 | {observation["primary_source_IR_B_execution_sources"]} / {denominator} |\n'
        f'| 回退来源 | {observation["fallback_sources_including_Horn_recovery"]} / {denominator} |\n\n'
        '回退答对和回退中的存储图调用单列，不计核心机制成功。IR接纳或条件证书也不单独证明源文语义忠实。'
        '[当前指标JSON](rr_method_runtime_20261107/training_metrics_status_20261107.json)、'
        f'[来源状态CSV](rr_method_runtime_20261107/{args.run_id}_source_status.csv)保留分母与路径；'
        '下方其他科学版本分别保存，不拼接成绩。\n' + prefix_end)
    if prefix_start in text:
        text = text[:text.index(prefix_start)] + prefix_text + text[text.index(prefix_end) + len(prefix_end):]
    else:
        text = text.replace(end, end + '\n\n' + prefix_text, 1)
    report.write_text(text)
    for directory in (root, Path('/home/yndx/hhy/legal-skill-current')):
        for name in ('PROJECT_MAP.md', 'docs/CURRENT_GOAL.md', 'docs/handoff_next_stage.md'):
            path = directory / name; lines = path.read_text().splitlines()
            index = next(i for i, value in enumerate(lines) if value.startswith(('实时状态（','当前执行更新（')))
            lines[index] = line; path.write_text('\n'.join(lines) + '\n')
    print(json.dumps(observation, ensure_ascii=False))


if __name__ == '__main__':
    main()
