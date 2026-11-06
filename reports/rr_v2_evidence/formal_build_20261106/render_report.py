"""Render factual build evidence; no training, prediction or model API entry."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from audit_build import audit,ROOT,OUT,BASE,RUN,RUN_ID,read,dump


def render(final=False,mechanisms=False):
    summary=audit(final=final,mechanisms=mechanisms)
    sources=read(OUT/'source_status.json');requests=read(OUT/'request_ledger.json')
    E=[r for r in requests if r['role']=='executor'];T=[r for r in requests if r['role']=='teacher']
    def total(rows,key):return sum((r['usage'] or {}).get(key,0) for r in rows)
    cost={'formal_executor_requests':len(E),'formal_teacher_requests':len(T),
        'executor_prompt_tokens_reported':total(E,'prompt_tokens'),
        'executor_completion_tokens_reported':total(E,'completion_tokens'),
        'teacher_input_tokens_reported':total(T,'input_tokens'),
        'teacher_output_tokens_reported':total(T,'output_tokens'),
        'teacher_reasoning_output_tokens_reported':total(T,'reasoning_output_tokens'),
        'executor_usage_unavailable_calls':sum(r['usage'] is None for r in E),
        'teacher_usage_unavailable_calls':sum(r['usage'] is None for r in T),
        'executor_request_seconds_reported':sum(r['elapsed_seconds'] or 0 for r in E),
        'teacher_invocation_seconds_reported':sum(r['elapsed_seconds'] or 0 for r in T),
        'time_unavailable_calls':sum(r['elapsed_seconds'] is None for r in requests),
        'executor_incremental_api_cash_usd':sum(r['incremental_api_cash_usd'] or 0 for r in E),
        'gpu_cost_usd':None,'teacher_cash_usd':None,'teacher_cash_invoice_available':False,
        'role_cumulative_counts':summary['cumulative_counts'],
        'role_original_caps':{'executor':6000,'teacher':20},
        'post_build_evaluation_executor_reserve':5472,'additional_budget_requested':0}
    dump(OUT/'cost_summary.json',cost)
    fields=['index','source','dataset','record_hash','calls','task_correct','A_status','A_fallback','IR_status',
            'B_status','B_synthesis_status','B_pattern_graphs','B_collisions','oracle_views','reference_failures','length_truncated_calls']
    with (OUT/'source_status.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r[k] for k in fields} for r in sources)
    with (OUT/'request_ledger.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(requests[0]) if requests else ['id','role','status'])
        w.writeheader();w.writerows(requests)
    bybank=[]
    for dataset in ['OpenExempt','RuleArena_Airline','SARA_v2_Binary','ProofWriter_OWA_depth5','ContractNLI']:
        rows=[r for r in sources if r['dataset']==dataset]
        bybank.append({'dataset':dataset,'sources':len(rows),'A_stable':sum(r['A_status']=='completion_stable' for r in rows),
            'A_fallback':sum(r['A_fallback'] for r in rows),'native_reference_match':sum(r['task_correct'] for r in rows),
            'B_collision_pattern_with_graphs':sum(r['B_status']=='identified_on_observed_collisions' and r['B_pattern_graphs']>0 for r in rows),
            'B_missing_typed_inputs':sum(r['B_synthesis_status']=='typed_inputs_unavailable' for r in rows)})
    dump(OUT/'mechanism_coverage.json',{'scope':'observed_fresh_formal_training_not_evaluation',
        'complete_sources':summary['complete_sources'],'source_coverage_by_dataset':bybank,
        'A_translation_actions':sum(len(r['translation_actions']) for r in sources),
        'A_separation_complete_actions':sum(a.get('joint_separation_complete',False) for r in sources for a in r['translation_actions']),
        'B_collisions_observed':sum(r['B_collisions'] for r in sources),
        'B_graph_field_only_patterns_are_separate':True,'fallback_correctness_is_not_core_success':True})
    failures={'classifications_may_overlap':True,'schema_or_execution_invalid_final_sources':sum(r['IR_status'] in {'parse_failure','invalid_IR'} for r in sources),
        'output_length_limited_sources':sum(r['length_truncated_calls']>0 for r in sources),
        'output_length_limited_calls':sum(r['length_truncated_calls'] for r in sources),
        'native_reference_mismatch_sources':sum(not r['task_correct'] for r in sources),
        'unresolved_A_sources':sum(r['A_status']!='completion_stable' for r in sources),
        'B_missing_typed_inputs_sources':sum(r['B_synthesis_status']=='typed_inputs_unavailable' for r in sources),
        'B_executed_no_valid_connector_sources':sum(r['B_synthesis_status']=='NO_VALID_CONNECTOR' for r in sources),
        'B_view_rebinding_unavailable_sources':sum(r['B_synthesis_status']=='view_rebinding_unavailable' for r in sources),
        'source_reference_failures_retained':sum(r['reference_failures'] for r in sources),
        'transport_failed_formal_calls':sum(r['status']=='failed' for r in requests),
        'pending_formal_calls':sum(r['status']=='reserved' for r in requests),
        'no_counterfactual_oracle_sources':sum(r['B_status']=='no_counterfactual_oracle' for r in sources),
        'stability_reference_mismatch_sources':[r['source'] for r in sources if r['A_status']=='completion_stable' and not r['task_correct']]}
    dump(OUT/'failure_classification.json',failures)
    bank_table='\n'.join('|'+ ' | '.join(str(row[k]) for k in ['dataset','sources','A_stable','A_fallback','native_reference_match','B_collision_pattern_with_graphs','B_missing_typed_inputs'])+' |' for row in bybank)
    freeze='\n'.join('| '+row['checkpoint']+' | '+str(row['patterns'])+' | `'+row['sha256']+'` |' for row in summary['frozen_libraries'])
    batch_table='\n'.join('| [B'+str(row['batch'])+'](../artifacts/rr_v2_formal_build_20261106/run/batches/B'+str(row['batch'])+'.json) | '+str(row['batch']*16)+' | '+str(row['teacher_requests'])+' | '+str(row['teacher_accepted'])+' | '+str(row['pattern_count'])+' | `'+row['checkpoint_sha256']+'` |' for row in summary['batches'])
    material_note=''
    if (OUT/'material_audit.json').exists():
        material=read(OUT/'material_audit.json')
        material_note=f'\n[共享材料与MB复算](rr_v2_evidence/formal_build_20261106/material_audit.json)当前覆盖{material["source_prefix"]}个来源、{len(material["batches"])}批，逐字核对六臂材料投影并重新拟合同材料普通对照；未生成评测预测。\n'
    restore_note=''
    if (OUT/'cached_recovery.json').exists():
        restored=read(OUT/'cached_recovery.json')
        if restored['binding']!=summary['binding']:raise ValueError('Cached recovery evidence has another binding')
        restore_note='\n[完整实际缓存恢复](rr_v2_evidence/formal_build_20261106/cached_recovery.json)已调用生产`FormalRun.train`访问全部128条当前记录，禁止生成、分词请求、新预留、网络和子进程；仅在内存捕获状态写入。终态、全部run文件字节和三张账本表保持一致，新增模型与oracle均0。\n'
    truncation_note=''
    if (OUT/'truncation_evidence.json').exists():
        truncated=read(OUT/'truncation_evidence.json')
        if truncated['binding']!=summary['binding']:raise ValueError('Truncation evidence has another binding')
        if not truncated['all_selected_prefixes_accepted'] or not truncated['all_selected_EOS_rejected']:
            raise ValueError('Selected prefix checks do not support the truncation attribution')
        truncation_note=f'''\n[实际长输出抽查](rr_v2_evidence/formal_build_20261106/truncation_evidence.json)覆盖第26、29、30来源的两次请求，共{len(truncated['checks'])}条，均以8192输出token结束。用同一tokenizer重编码保留原文，并按实际wire中的schema字段顺序检查，全部前缀可接受、EOS全部被拒绝；这只能证明JSON未完成，不能据此排除schema缺陷。进一步对5个字符串值位置检查闭合引号，4个当前位置被拒绝。公共输入核对发现旧`CITATION_PATTERN`强制含§，会拒绝全部32个OE TRAIN来源中9种合法Illinois引用；[输入引用审计](rr_v2_evidence/formal_build_20261106/citation_public_header_audit.json)。schema错误和模型重复需分列，不能把全部截断归为模型错误，也未补闭合符号或缺失语义来制造通过的IR。\n\n首次离线检查从排序后的`request.json`读取schema，改变了xgrammar所用的属性顺序，导致第2个token即假拒绝；[原诊断](rr_v2_evidence/formal_build_20261106/truncation_evidence.sorted_request_check.json)保留。检查工具已改读带SHA核验的真实wire body。已停止本轮控制器并保全修复前源码、响应和账本；新代码未与旧生成结果混作同一绑定。\n'''
    status='128来源及8批已完成并通过只读工件审计，交付核验待完成。' if final else f'运行中：已持久化{summary["complete_sources"]}/128来源、{summary["completed_batches"]}/8批。Goal未完成。'
    if not final and not summary['controller_alive']:
        status=f'已停止真实派发：已持久化{summary["complete_sources"]}/128来源、{summary["completed_batches"]}/8批。citation schema存在已确认缺陷，修复前结果保全，Goal未完成。'
    report=f'''# RR-v2 正式共享建库

更新：{summary['captured_utc']}。**{status}** 本阶段没有进行六臂正式评测、冻结测试或论文写作；训练参考匹配只是训练材料检查，不是性能评测或机制涨分证据。

从空技能库按原固定顺序执行一次128来源、8批建库。旧20来源及其teacher汇总保留为历史，不作为本轮完成记录。原来源仍在128中，没有新增来源或种子；每个正式来源最多2次executor，每批最多2次teacher。适用的旧oracle仅通过同source/view/reference哈希复用，每来源额外视图累计最多4，不重置旧计数。

## 当前结果与机制覆盖

| 数据集 | 已处理来源 | A稳定 | A回退 | native/参考匹配 | B观察碰撞且有图 | B缺typed输入 |
|---|---:|---:|---:|---:|---:|---:|
{bank_table}

上表保留所有已处理来源，不按成功筛选。A稳定和B有图是两种覆盖口径，fallback答对不计核心成功。B输入不足、真实候选执行后无有效连接、无法重绑、无碰撞和无正式oracle分别保存，不能把缺输入写成已经完成搜索无解。已记录B碰撞共{sum(r['B_collisions'] for r in sources)}对；A共记录{sum(len(r['translation_actions']) for r in sources)}次第二次解析规划，其中{sum(a.get('joint_separation_complete',False) for r in sources for a in r['translation_actions'])}次声称分离完备。核验仍保留H≠Ω和条件性语义包含假设，不作全域等价声明。

来源级完整列表见[source_status.csv](rr_v2_evidence/formal_build_20261106/source_status.csv)及[详细JSON](rr_v2_evidence/formal_build_20261106/source_status.json)；[机制覆盖](rr_v2_evidence/formal_build_20261106/mechanism_coverage.json)、[失败分类](rr_v2_evidence/formal_build_20261106/failure_classification.json)分列。可用`audit_build.py --mechanisms`仅用本轮实际记录的视图及既有结果重新执行B学习；这属于禁网络/子进程的离线核验，不是新增真实模型调用，不返回缓存学习结果，也不向历史较早attempt注入后来取得的标签。
{truncation_note}

## 检查点与冻结库

每批保存来源前缀、逐记录哈希、当时库状态、该批新teacher记录及当时累计账本快照。B1/B8另保存不可变冻结库与同材料MB普通对照冻结状态；只做材料投影，不为六臂各自重新建库。

| 检查点 | 来源前缀 | 新teacher请求 | 记录接纳 | 库模式数 | 检查点文件SHA256 |
|---|---:|---:|---|---:|---|
{batch_table}

| 冻结点 | 模式数 | 文件SHA256 |
|---|---:|---|
{freeze}

原始请求/响应、source记录、batch B1至B8检查点及冻结库位于[本轮run目录](../artifacts/rr_v2_formal_build_20261106/run/)。各批checkpoint中的ledger是当时快照；当前累计消耗读同一SQLite，不能将多个checkpoint费用相加。
{material_note}

## 固定配置与版本

Executor：Qwen/Qwen3-8B，thinking OFF，temperature0.6，top_p0.95，top_k20，seed45，max_tokens8192，context32768，串行请求。Teacher：gpt-5.6-sol、reasoning_effort=high、既有已验证Codex CLI；temperature未显式设置，后端数值未暴露。配置、原语/机制、提示/schema代码及源数据冻结，普通模型错误不触发调参或额外来源。

8192来自项目[executor.max_tokens](../configs/rr_v2_preflight.json)，作为每次HTTP请求的`max_tokens`发送给vLLM；32768是另一个总上下文设置。正式建库沿用并冻结该输出预算，teacher CLI不读取此项。

科学代码：`{summary['binding']['code_hash']}`；语义配置：`{summary['binding']['config_hash']}`；数据：`{summary['binding']['data_hash']}`；manifest：`{summary['binding']['source_manifest_hash']}`。启动实现提交`474211d`，运行seal保存逐文件哈希、128个初始请求契约哈希及有效模型/teacher transport。启动前156项相关检查通过；原128初始输入均放入当前上下文（最长14178 token），没有截断原文。旧科学记录与本轮结果按绑定分列，不混用不兼容结果。

## 实际消耗与保全

当前本轮executor {len(E)}次、teacher {len(T)}次；累计executor {summary['cumulative_counts']['executor']}/6000、teacher {summary['cumulative_counts']['teacher']}/20，pending {summary['pending']}。本轮executor已报告输入{cost['executor_prompt_tokens_reported']}、输出{cost['executor_completion_tokens_reported']} token；teacher输入{cost['teacher_input_tokens_reported']}、输出{cost['teacher_output_tokens_reported']}、reasoning输出字段{cost['teacher_reasoning_output_tokens_reported']} token。未报告usage的请求仍计费/占额，未知量不当作零：executor {cost['executor_usage_unavailable_calls']}次、teacher {cost['teacher_usage_unavailable_calls']}次。

Executor请求墙钟耗时已报告{cost['executor_request_seconds_reported']:.3f}秒，teacher invocation {cost['teacher_invocation_seconds_reported']:.3f}秒；这是请求耗时，不是测得GPU时长。已有本地executor服务新增逐请求API现金支出0美元；GPU分摊成本与teacher实际现金账单未知，不能称算力免费或将estimated credits当真实USD。[逐请求账本](rr_v2_evidence/formal_build_20261106/request_ledger.csv)和[成本摘要](rr_v2_evidence/formal_build_20261106/cost_summary.json)保留失败、重试、原usage与未知费用。

原131条调用行（127E+4T）、118条meta及50条oracle逐值保留。本轮调整建库桶292（历史36+正式最多256）、恢复桶196，其余后续评测预留5472不变，合计仍6000。teacher原4+本轮8批最多16=20。完整审计核对来源限额、模型wire、空库起点、文件冻结、历史行及oracle总上限；[审计结果](rr_v2_evidence/formal_build_20261106/{'final_audit' if final else 'live_audit'}.json)。原始baseline与SQLite备份保留在本地`artifacts/rr_v2_formal_build_20261106/`。

## 观察与恢复

控制器身份为run目录的`process_identity.json`，核实实际PID与start_ticks，再读取`state.json`和账本。存活时仅观察，不重复启动。退出后用同一冻结版本及`python -m experiments.rr_v2_formal_build run`恢复：已完成的本轮记录免费恢复，失败/歧义请求保留收费，不隐式重新派发；恢复完整wire响应不新增模型请求。旧预检入口不是本轮的恢复队列。
{restore_note}

零模型审计（在本地开发目录、用已有环境）：

```bash
PYTHONPATH=. python reports/rr_v2_evidence/formal_build_20261106/audit_build.py
# 控制器结束且128来源/8批全部完成后：
PYTHONPATH=. python reports/rr_v2_evidence/formal_build_20261106/audit_build.py --final --mechanisms
PYTHONPATH=. python reports/rr_v2_evidence/formal_build_20261106/check_completion.py --restore
```

完整环境、恢复与复现边界见[本轮复现说明](../docs/rr_v2/FORMAL_BUILD_REPRODUCE.md)。当前评测与冻结测试开关仍关闭。本阶段完成交付后停止，等待用户复核；不自动进入评测。
'''
    target=ROOT/'reports/legalskillguard_rr_v2_formal_build_20261106.md'
    if not (BASE/'initial_live_report.md').exists() and target.exists():
        (BASE/'initial_live_report.md').write_bytes(target.read_bytes())
    target.write_text(report)
    print(json.dumps({'report':str(target),'final':final,'sources':summary['complete_sources'],'batches':summary['completed_batches']}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');p.add_argument('--mechanisms',action='store_true');a=p.parse_args()
    render(a.final,a.mechanisms)
