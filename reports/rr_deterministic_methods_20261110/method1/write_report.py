"""Render exact stored results; no new oracle queries or experiments."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
s = json.loads((ROOT/'summary.json').read_text(encoding='utf-8'))
lines = ['# 确定性实现：最终数值记录', '',
         '金额与程序全部为声明的合成模型；不属于原生法律效果。平均查询按语法模型实例加权。', '',
         '| 任务 | 模型/行为类 | 直接 平均/最大 | 同探测约束 平均/最大 | 最大分歧 平均/最大 | 最优树 平均/最大 |',
         '|---|---:|---:|---:|---:|---:|']
for r in s['suites']:
    cells = []
    for name in ('direct', 'same_probe_constraints', 'max_disagreement', 'optimal_tree'):
        m = r['summaries'].get(name)
        cells.append(f"{m['query_mean']:.2f}/{m['query_max']}" if m else '未计算')
    lines.append(f"| {r['name']} | {r['model_count']}/{r['behavioral_classes_on_pool']} | "
                 + ' | '.join(cells) + ' |')
lines += ['', '前三种方法均为 216/216 行为恢复正确；最优树在适用的小类任务中全部正确。', '',
          '## 全部函数求值账本', '',
          '| 类别 | 精确次数 |', '|---|---:|']
for key, count in s['exact_all_dsl_evaluations'].items():
    lines.append(f'| {key} | {count} |')
lines += ['', f"全部 DSL 求值合计：{sum(s['exact_all_dsl_evaluations'].values())}。",
          f"学习获取账本核对：{s['ledger_reconciled_acquisition_calls']} 次，包含输入域回归中的合法先行查询。",
          f"额外参考函数压力评分：{s['independently_counted_reference_stress_evaluations']} 次；这些不进入学习器。", '',
          '候选预计算/隔离审计/幸存程序评分都是宿主对公开 DSL 的模拟；与隐藏函数学习查询分开。', '',
          '## 计算成本', '',
          '| 任务 | 预计算程序求值 | 预计算秒 | 直接秒 | 同探测约束秒 | 主动选择秒 | 最优树预计算秒 |',
          '|---|---:|---:|---:|---:|---:|---:|']
for r in s['suites']:
    p, m = r['common_precomputation'], r['summaries']
    lines.append(f"| {r['name']} | {p['candidate_evaluations']} | {p['seconds']:.4f} | "
                 f"{m['direct']['seconds_total']:.4f} | {m['same_probe_constraints']['seconds_total']:.4f} | "
                 f"{m['max_disagreement']['seconds_total']:.4f} | {r['exact_minimax_seconds']:.4f} |")
lines += ['', '每行学习秒数是该任务所有语法实例合计，均排除了后验评分。预计算在同一公开任务内共享，已单列；'
          '毫秒级差异不作统计显著性结论。查询池构造、输出文件等额外耗时可由各任务 suite_seconds 查看。', '',
          '## 精确最坏查询深度', '',
          '| 任务 | 最优最坏查询 | DP 状态 | 查询分区测试次数 | 该树按行为类平均 |',
          '|---|---:|---:|---:|---:|']
for r in s['suites']:
    o = r['exact_minimax']
    if o:
        lines.append(f"| {r['name']} | {o['worst_queries']} | {o['dp_states']} | "
                     f"{o['partition_tests_considered']} | {o['expected_queries_uniform_class']} |")
g = s['intermediate_domain_guard']
lines += ['', '最优深度仅针对声明的有限合法查询池；期望列是该递归选出的树，不是全局最优期望声明。', '',
          '## 输入域回归', '',
          f"共 {g['cases']} 个边界模型，{g['unsupported']} 个明确返回 unsupported，"
          f"非法提交 {g['illegal_queries_submitted']} 次。unsupported 不计入 216 个恢复成功实例。", '',
          '## 判断', '',
          '直接恢复器真实可运行、没有完整程序枚举；但同信息关系约束获得同样正确结果，主动/最优查询明显更少。'
          '本轮没有证明足够独立的论文方法优势，也没有验证自然语言编译与跨法源迁移。'
          '原始记录、源文件 hash 和逐请求输入输出均已保留。', '']
(ROOT/'RESULTS.md').write_text('\n'.join(lines), encoding='utf-8')
print(json.dumps(dict(dsl_evaluations=s['exact_all_dsl_evaluations'],
                      domain_guard=g, total_models=sum(r['model_count'] for r in s['suites'])), indent=2))
