"""Render the completed, fixed study for the primary scientific review.

Reads settled evidence only. This is neither an experiment nor an automatic
method/Goal approval. Partial TEST outputs are never opened.
"""
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent
DATASETS = ('OpenExempt', 'SARA_v2_Binary', 'ContractNLI', 'RuleArena_Airline', 'MAUD')
ARMS = ('NoSkill', 'FreeEvolution', 'LiftOnly', 'CoRevOnly', 'Full', 'Lift+GenericJoint', 'AllPorts+CoRev')


def read(path):return json.loads(path.read_text())


def number(value):return 'unknown' if value is None else f'{value:.6f}'


def interval(values):return '[' + ', '.join(number(v) for v in values) + ']'


def main():
    folder = ROOT / 'artifacts/legal_skill_evolution_20261111/frozen_test_v1'
    ops = ROOT / 'artifacts/legal_skill_evolution_20261111/fixed_pipeline_v1'
    # Check these before opening the audit, summaries, annotations or predictions.
    needed = (folder / 'TEST_completed.json', folder / 'transfer/completed.json',
              ops / 'final_report_completed.json')
    missing = [str(p.relative_to(ROOT)) for p in needed if not p.exists()]
    if missing:
        print(json.dumps({'stage': 'waiting_for_complete_fixed_evidence',
            'missing_completion_receipts': missing, 'TEST_outputs_opened': False,
            'new_model_calls': 0, 'goal_complete': False}))
        return
    primary_path = REPORT / 'primary_scientific_review.json'
    if not primary_path.exists():
        print(json.dumps({'stage': 'awaiting_primary_scientific_review',
            'new_model_calls': 0, 'goal_complete': False}))
        return
    primary = read(primary_path)
    for name, expected in primary['evidence_sha256'].items():
        if hashlib.sha256((REPORT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Primary review evidence changed: ' + name)
    final = read(needed[-1])
    for name, expected in final['report_sha256'].items():
        if hashlib.sha256((REPORT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Settled analysis changed after completion: ' + name)
    audit = read(REPORT / 'fixed_study_completion_audit.json')
    costs = read(REPORT / 'stage_costs.json')
    footprints = read(REPORT / 'frozen_cost_footprints.json')
    mechanics = read(REPORT / 'formal_mechanism_inventory.json')
    required = ('128_TRAIN_8_batches_48_updates_42_DEV_points',
                'B8_fixed_seven_system_five_dataset_TEST', 'registered_foreign_skill_mask_contrast')
    if any(audit['requirements'][key]['status'] != 'verified' for key in required):
        raise ValueError('The existing fixed experiment is not fully reconciled')
    summaries = audit['TEST_native_summaries']
    contrasts = audit['all_four_registered_TEST_contrasts']
    transfer = audit['registered_transfer_summary']
    lines = ['# 固定研究的阶段复核', '',
        primary['conclusion_paragraphs'][0], '',
        '完整固定实验与两项贡献分开判断。主要执行者已复核代码、原始记录与注册统计；两项独立贡献仍未获支持，Goal未完成。本报告不调用模型、不更新技能、不使用TEST修补方法，也不自动批准后续训练或论文。', '',
        '## 固定实验结果', '',
        '128个TRAIN母来源、8批、48次学习更新、42个DEV点完成；固定B8七系统均完成五库各32个TEST母来源，每系统352个原生视图。注册外库技能掩码使用同一冻结库和来源，未新增教师或学习。', '',
        '得分先聚合到母来源，再按库取均值、五库等权。以下均为原生评分；回退保留在总分分母，另报执行路径。', '',
        '| 系统 | OpenExempt | SARA | ContractNLI | Airline | MAUD | 五库宏平均 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        metrics = summaries[arm]['metrics']
        values = [metrics['datasets'][d]['native_parent_mean'] for d in DATASETS]
        lines.append('| ' + arm + ' | ' + ' | '.join(number(x) for x in values + [metrics['equal_five_dataset_macro']]) + ' |')
    lines += ['', '## 独立消融与强对照', '',
        '区间按数据集分层、母来源成组进行配对bootstrap；同案多个视图不当作独立样本。四项主比较同时给出Bonferroni 98.75%区间，未加入新效应阈值，不据单一显著性判据代替实际收益判断。', '',
        '| Full减对照 | 五库宏平均差 | 95%区间 | 四项校正98.75%区间 |', '|---|---:|---|---|']
    for arm, result in contrasts.items():
        lines.append('| ' + arm + ' | ' + number(result['equal_dataset_macro_difference']) + ' | ' +
            interval(result['paired_source_bootstrap_95_percent_interval']) + ' | ' +
            interval(result['four_contrast_Bonferroni_98_75_percent_interval']) + ' |')
    lines += ['', '## 两项机制是否发生', '',
        '| 要求 | 实际证据 |', '|---|---|']
    for key in ('Lift_independent_cross_parent_mechanism', 'CoRev_independent_cross_parent_mechanism'):
        lines.append('| ' + key + ' | ' + audit['requirements'][key]['status'] + ' |')
    accepted = audit['accepted_operation_counts_independently_recounted']
    lines += ['',
        '原正式学习接纳操作为' + json.dumps(accepted, ensure_ascii=False) +
        '。所有B8库的依赖端口和已学共同修订模式见下表；提议、接纳、执行及跨来源使用分开核对。', '',
        '| 系统 | 技能 | 技能依赖端口 | 已学修订模式 |', '|---|---:|---:|---:|']
    for row in audit['arm_state']:
        lines.append('| {arm} | {skill_count} | {actual_dependency_ports} | {revision_pattern_count} |'.format(**row))
    lines += ['',
        'Full B6同时修改两个已有程序的候选已做完整版本交叉表，分类为single_sufficient：分别处理航空和财产任务，不能算依赖规则必须共同修订的证据。原32个受控直接基线32/32正确，MAUD受控角色条件全部为True；它们不能证明新增角色归属能力。', '',
        '隔离修复已让真实Lift小型reader生成与执行接通，但旧航空程序缺少国际航线费用逻辑，提升尺寸前提后得分不变，按原准入拒绝。独立Full与Free都获取到§152依赖技能，效果被真实强对照吸收；创建依赖技能不等于修订已有依赖规则。错把§152终端用于§151而碰巧标签正确的问题已有离线保守范围修复，未注入原冻结结果，修复后的泛化收益仍待真实验证。', '',
        '因此，普通程序获取/修补的分数收益、格式和类型修复、缓存回放以及原生标签碰巧正确，都不能替代Lift与CoRev的独立证据。当前固定实验没有提供两项机制验收所需的训练期事件；完成TEST不能补出此前没有发生的学习。', '',
        '## 真实程序路径与回退', '',
        '程序主路径表示执行了已学终端程序；“原生全对”只表示对应原生评分全对，不自动证明法义推导或两项专门机制。未知、失败和回退均保留分母。', '',
        '| 系统 | 原生视图 | 程序主路径 | 其中原生全对 | 回退 | 未解决 | 回退率 |', '|---|---:|---:|---:|---:|---:|---:|']
    source_rows = []
    for arm in ARMS:
        totals = {name: sum(summaries[arm]['metrics']['datasets'][d]['path_counts'].get(name, 0)
                            for d in DATASETS) for name in
                  ('native_views', 'core_views', 'fully_correct_core_views', 'fallback_views', 'unresolved_views')}
        lines.append('| ' + arm + ' | ' + ' | '.join(str(totals[k]) for k in totals) + ' | ' +
            f"{totals['fallback_views'] / totals['native_views']:.2%}" + ' |')
        for row in summaries[arm]['metrics']['source_rows']:
            source_rows.append({'arm': arm, 'source': row['source'], 'dataset': row['dataset'],
                'native_grade': row['native_grade'], 'native_view_grades': json.dumps(row['per_view_grade'], ensure_ascii=False),
                **{k: row['path_counts'].get(k, 0) for k in totals}})
    diff = transfer['paired_source_uncertainty']
    lines += ['',
        'Full的CNLI 128视图均回退：检索到的税法程序需要taxable_income/is_agricultural_labor，当前读取未知后触发KeyError。MAUD 96视图均因税法终端枚举与Yes/No不相容而跳过。其余回退为OE22、SARA27、Airline3，实际缺失字段及逐候选计数见[完整路径失败统计](Full_TEST_path_failure_summary.json)。这说明当前程序覆盖和字段读取存在缺口，不能把全部回退解释成传输或schema系统故障，也不补默认字段让程序通过。错误类别按视图可重叠，不冒充独立来源数。', '',
        '## 注册跨库复用', '',
        f"外库技能开启减目标库技能保留的宏平均差为{number(diff['equal_dataset_macro_difference'])}，95%区间{interval(diff['paired_source_bootstrap_95_percent_interval'])}。",
        f"实际外库终端路径视图{transfer['actual_foreign_final_path_views']}，其中原生全对{transfer['fully_correct_foreign_core_views']}；母来源变化为" + json.dumps(transfer['parent_outcomes'], ensure_ascii=False) + '。', '',
        '外库技能存在、被词面检索到和实际产生正确复用分别报告，不能相互替代；外库掩码也不等于未发生的共同修订模式消融。', '',
        '## 实际成本', '', '| 阶段 | executor物理请求 | teacher物理请求 |', '|---|---:|---:|']
    for phase in ('first_pass', 'repair', 'activation_TRAIN_diagnostic', 'formal', 'frozen_TEST_and_transfer'):
        lines.append(f"| {phase} | {costs[phase]['executor']['physical_requests']} | {costs[phase]['teacher']['physical_requests']} |")
    lines += ['',
        '原1893E/74T起点和持续账本保留。总物理请求按实际派发只计一次；各臂获取＋推理响应使用量是消费足迹，含精确共享缓存，不能相加冒充支出或据首次消费者宣称成本优势。3次异常请求的逐臂引用已用28个TRAIN原生视图禁网回放补齐，总费用和评分没有改变。', '',
        'executor本地增量API现金为0；GPU和教师实际发票不可见，未将总成本填成0。CLI reasoning输出是输出字段的组成，不重复相加。详细tokens、失败、耗时及消费足迹见[阶段成本](stage_costs.json)、[正式学习成本](formal_cost_footprints.json)和[冻结费用](frozen_cost_footprints.json)。', '',
        '## 固定OFF与实际响应', '',
        '| 阶段 | 已结算executor响应 | 明确OFF标志 | 非空reasoning内容 | 正常stop | 截断length |', '|---|---:|---:|---:|---:|---:|']
    for phase, observed in audit['requirements']['fixed_model_thinking_OFF_no_parameter_training']['actual_response_transport'].items():
        lines.append('| ' + phase + ' | ' + ' | '.join(str(v) for v in (
            observed['physical_statuses'].get('completed', 0), observed['completed_OFF_flags'],
            observed['completed_nonempty_reasoning_content'], observed['completed_finish_reasons'].get('stop', 0),
            observed['completed_finish_reasons'].get('length', 0))) + ' |')
    lines += ['', '正常stop只证明响应传输结束，不能替代字段、执行、原生评分或法律语义验收。', '',
        '## 结论与最小下一步', '',
        *[paragraph for text in primary['conclusion_paragraphs'][1:] for paragraph in (text, '')],
        '[学习曲线与阶段报告](README.md) · [原验收逐项核对](FIXED_STUDY_COMPLETION_AUDIT.md) · [完整逐来源TEST表](fixed_TEST_source_results.csv) · [原始证据清单](settled_evidence_manifest.json)', '']
    report_path = REPORT / 'FIXED_STUDY_STAGE_REVIEW.md'
    report_path.write_text('\n'.join(lines))
    csv_path = REPORT / 'fixed_TEST_source_results.csv'
    with csv_path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(source_rows[0]));writer.writeheader();writer.writerows(source_rows)
    receipt = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'goal_complete': False, 'method_contributions_automatically_approved': False,
        'source_rows': len(source_rows), 'primary_scientific_review_required': False,
        'primary_scientific_review_sha256': hashlib.sha256(primary_path.read_bytes()).hexdigest(),
        'report_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (report_path, csv_path)},
        'frozen_costs_available': footprints['transfer_complete'],
        'observed_pattern_transplants': len(mechanics['actual_pattern_transplant_candidates'])}
    (REPORT / 'stage_review_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':main()
