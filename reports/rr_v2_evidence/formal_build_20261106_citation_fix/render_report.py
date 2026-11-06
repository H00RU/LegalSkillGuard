"""Render factual build evidence; no training, prediction or model API entry."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from audit_build import audit,ROOT,OUT,BASE,RUN,RUN_ID,read,dump
from inspect_mechanism_use import inspect as inspect_mechanisms


def render(final=False,mechanisms=False):
    summary=audit(final=final,mechanisms=mechanisms)
    interpretation=inspect_mechanisms(summary)
    dump(OUT/'mechanism_interpretation.json',interpretation)
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
    older=read(BASE/'preserved_before_citation_contract_fix/evidence/cost_summary.json')
    cost.update(aborted_build_executor_requests=65,aborted_build_teacher_requests=2,
        goal_executor_requests_including_aborted=65+len(E),goal_teacher_requests_including_aborted=2+len(T),
        goal_executor_prompt_tokens_reported=older['executor_prompt_tokens_reported']+cost['executor_prompt_tokens_reported'],
        goal_executor_completion_tokens_reported=older['executor_completion_tokens_reported']+cost['executor_completion_tokens_reported'],
        goal_teacher_input_tokens_reported=older['teacher_input_tokens_reported']+cost['teacher_input_tokens_reported'],
        goal_teacher_output_tokens_reported=older['teacher_output_tokens_reported']+cost['teacher_output_tokens_reported'])
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
            'A_fallback':sum(r['A_fallback'] for r in rows),'training_reference_match':sum(r['task_correct'] for r in rows),
            'B_collision_pattern_with_graphs':sum(r['B_status']=='identified_on_observed_collisions' and r['B_pattern_graphs']>0 for r in rows),
            'B_missing_typed_inputs':sum(r['B_synthesis_status']=='typed_inputs_unavailable' for r in rows)})
    n=len(sources)
    rates={'denominator_completed_sources':n,
        'A_stable_sources':sum(r['A_status']=='completion_stable' for r in sources),
        'A_stable_reference_match_without_fallback_sources':sum(r['A_status']=='completion_stable' and r['task_correct'] and not r['A_fallback'] for r in sources),
        'A_native_fallback_sources':sum(r['A_fallback'] for r in sources),
        'A_without_stable_certificate_sources':sum(r['A_status']!='completion_stable' for r in sources),
        'B_collision_pattern_with_graphs_sources':sum(r['B_status']=='identified_on_observed_collisions' and r['B_pattern_graphs']>0 for r in sources),
        'B_prediction_fallback_rate':None,'B_prediction_fallback_rate_measured':False}
    rates.update({k.removesuffix('_sources')+'_fraction':v/n if n else None for k,v in list(rates.items()) if k.endswith('_sources') and k!='denominator_completed_sources'})
    def share(key):return f'{rates[key]}/{n}（{rates[key]/n:.1%}）' if n else '0/0（尚无已处理来源）'
    dump(OUT/'mechanism_coverage.json',{'scope':'observed_fresh_formal_training_not_evaluation',
        'complete_sources':summary['complete_sources'],'source_coverage_by_dataset':bybank,
        'source_rates':rates,
        'A_translation_actions':sum(len(r['translation_actions']) for r in sources),
        'A_separation_complete_actions':sum(a.get('joint_separation_complete',False) for r in sources for a in r['translation_actions']),
        'B_collisions_observed':sum(r['B_collisions'] for r in sources),
        'B_graph_field_only_patterns_are_separate':True,'fallback_correctness_is_not_core_success':True})
    failures={'classifications_may_overlap':True,'schema_or_execution_invalid_final_sources':sum(r['IR_status'] in {'parse_failure','invalid_IR'} for r in sources),
        'output_length_limited_sources':sum(r['length_truncated_calls']>0 for r in sources),
        'output_length_limited_calls':sum(r['length_truncated_calls'] for r in sources),
        'training_reference_mismatch_sources':sum(not r['task_correct'] for r in sources),
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
    bank_table='\n'.join('|'+ ' | '.join(str(row[k]) for k in ['dataset','sources','A_stable','A_fallback','training_reference_match','B_collision_pattern_with_graphs','B_missing_typed_inputs'])+' |' for row in bybank)
    freeze='\n'.join('| '+row['checkpoint']+' | '+str(row['patterns'])+' | `'+row['sha256']+'` |' for row in summary['frozen_libraries'])
    batch_table='\n'.join('| [B'+str(row['batch'])+'](../artifacts/rr_v2_formal_build_20261106/run_citation_fix/batches/B'+str(row['batch'])+'.json) | '+str(row['batch']*16)+' | '+str(row['teacher_requests'])+' | '+str(row['teacher_accepted'])+' | '+str(row['pattern_count'])+' | `'+row['checkpoint_sha256']+'` |' for row in summary['batches'])
    usage_table='\n'.join('|'+ ' | '.join(str(row[k]) for k in ['dataset','sources','sources_shown_prior_patterns','sources_with_model_typed_candidates','sources_with_learned_pattern','sources_with_prior_graph_structure_executed'])+' |' for row in interpretation['B_by_dataset'])
    pattern_table='\n'.join('| `'+p['pattern_hash'][:12]+'` | `'+', '.join(p['pattern']['fields'])+'` | `'+json.dumps(p['pattern']['graphs'],ensure_ascii=False,separators=(',',':'))+'` | '+str(len(p['evidence_sources']))+' |' for p in interpretation['B_patterns'])
    mechanism_note=f'''
## 实际输入、残余处理与模式使用

本节只检查已有原文、wire和执行记录，未调用模型、oracle或正式预测。{interpretation['input_evidence']['initial_full_public_inputs_exact']}/{interpretation['input_evidence']['initial_inputs_checked']}条首请求与当前完整公开输入逐字一致；已观察到的最长输入为{interpretation['input_evidence']['max_observed_input_tokens']} token，输出预留仍8192、总上下文32768。公开源文本已送达不等于模型返回了足够的可执行原语；数值任务还需可重绑的typed bindings、候选图与观察证据。详见[逐来源机制使用检查](rr_v2_evidence/formal_build_20261106_citation_fix/mechanism_interpretation.json)。

在{interpretation['input_evidence']['wire_calls_checked']}条已保存请求中，{interpretation['input_evidence']['wire_calls_allow_connector_program']}条实际wire允许`connector`程序，{interpretation['input_evidence']['wire_calls_interface_max_items_8']}条接口数组上限为8，非强制空接口；具体kind列表与上限逐请求保存。共享typed binding/连接契约已有前阶段离线回归，不把声明允许当成真实执行。当前缺少typed候选的来源按模型实际输出记录，不归因为发送schema把该入口关闭。

源文检查只比较编号公开源文块，并单独核对SARA逐字查询；归档字典序和查询后缀位置所致的中间误报、原检查结果及修正原因保留在[检查器修正记录](rr_v2_evidence/formal_build_20261106_citation_fix/source_text_checker_correction.json)。真实wire/token核对始终独立，未改科学代码、原响应或评分。

A实际记录{interpretation['A_observed']['actions']}次再次解析，选批依据为`{json.dumps(interpretation['A_observed']['selection_bases'],ensure_ascii=False)}`，其中分离完备批次为{interpretation['A_observed']['joint_separation_complete_actions']}次。选中源文、实际输入token及wire哈希分别核对，源文不一致{interpretation['A_observed']['selected_wire_mismatches']}次、成本或请求体不一致{interpretation['A_observed']['token_or_body_mismatches']}次。保守地重新解析残余是实际控制流，但不作为非平凡分离选批成功；受限Horn内置编译器产生的稳定证书也不计为学到新法律规则。此前人工残余/数值微例属于离线实现验证，与本轮真实命中分列。

当前{interpretation['A_observed']['sources_with_unknown_scope_residuals']}个来源的最终完成性分析仍含未知作用范围残余，另有{interpretation['A_observed']['sources_without_completion_assessment']}个来源未记录该残余完成性分析；后者以未验证记录，不填成零残余。B有{failures['B_missing_typed_inputs_sources']}个来源缺少模型提供的可执行typed输入，不能据此声称候选搜索已完成无解；ContractNLI无正式反事实oracle的来源另列。输入充分性因此分为完整公开文本送达、原语/作用范围可形式化、可执行候选及已观察语义证据四层，前一层不能替代后一层。

据现有证据，公开输入完整性通过；ProofWriter的受限Horn子域支持了实际A执行和源内B观察。法律、数值来源主要欠缺足以闭合A残余、供B执行的模型产物，现有记录不支持把它们写成已经学得可跨库复用规则；这与源文被截断或发送schema关闭接口不同。ContractNLI的oracle缺口属于原方案边界。本阶段没有据此更换研究方案、模型或数据。

B当前保存{len(interpretation['B_patterns'])}个去重参数化模式，字段、图结构及证据来源见上述JSON的`B_patterns`。学习部分是由实际碰撞支持的接口义务及保留结构；Horn文法、`join_on`等连接算子和数值执行语义均为预定义组件，不冒称学到了这些规则。后续独立产生同一模式只增加证据来源，不自动算作库驱动复用。

| 模式哈希前缀 | 碰撞支持的接口字段 | 保存的参数化连接结构 | 证据来源数 |
|---|---|---|---:|
{pattern_table}

其中`entity_equality`记录实体键对齐义务，`join_on`连接两个参数槽。按`column0`连接与空键连接同时保留时，后者是笛卡尔积候选，表示现有有限视图尚未区分全部结构；不能把候选数量当作学到多个独立规则。学习证据只支持当前观察下的约束选择和结构保留，不声称新算子发明或全域等价。

| 数据集 | 已处理 | 提示中收到旧模式 | 模型typed候选非空 | 产出模式的来源 | 执行过匹配旧图结构的来源 |
|---|---:|---:|---:|---:|---:|
{usage_table}

本次`FormalRun.train`将已学模式发送到后续提示，但没有调用正式预测路径的`apply_interfaces`库策略。表中结构匹配也只证明相同结构出现/执行，不能据此声称因果迁移或涨分；提示曝光、源内B候选语义检查、后续库驱动执行与最终fallback分别记录。法律/数值任务或后续来源缺少相应真实执行时如实记为未观察到，不用内置规则、格式通过或回退答对补齐。本节不增加技能数量、涨分、全分支实测或零回退验收门槛。

已有SARA第70来源第二次响应确实给出一个接口候选，不能归入“从未进入typed入口”。[原候选离线定位](rr_v2_evidence/formal_build_20261106_citation_fix/sara_actual_typed_candidate_diagnosis.json)直接执行原图：`join_on`引用`slot0/slot1`，实际只绑定五个`n_*`整数，因缺`slot0`而被拒绝。其真实学习记录为生成1、保留0、`NO_VALID_CONNECTOR`，语义观察0；这是具体模型绑定错误，不是数值接口已学成，也不是需要放宽执行检查的工程阻断。诊断不读取评分目标、不修补原响应，新增模型/oracle均0。
'''
    numeric_path=OUT/'airline_original_target_consistency.json'
    if numeric_path.exists():
        numeric=read(numeric_path)
        mechanism_note += f'''\n[Airline原始目标一致性检查](rr_v2_evidence/formal_build_20261106_citation_fix/airline_original_target_consistency.json)仅对已处理来源的原始TRAIN参数重算，{numeric['original_targets_match_reference']}/{numeric['airline_sources_checked']}个目标与固定参考代码一致；{numeric['native_equals_base_only_sources']}个native输出只等于机票价，没有统一的native/目标偏移。该检查覆盖原固定{numeric['original_airline_TRAIN_sources']}个Airline训练来源中的{numeric['airline_sources_checked']}个，不包含其他数据集；没有新增模型调用或反事实视图，也没有修补预测或评分。这些来源未发现共同评分定义错位，不能把格式合法或费用片段当作完整任务成功。\n'''
    material_note=''
    if (OUT/'material_audit.json').exists():
        material=read(OUT/'material_audit.json')
        material_note=f'\n[共享材料与MB复算](rr_v2_evidence/formal_build_20261106_citation_fix/material_audit.json)当前覆盖{material["source_prefix"]}个来源、{len(material["batches"])}批，逐字核对六臂材料投影并重新拟合同材料普通对照；未生成评测预测。\n'
    restore_note=''
    if (OUT/'cached_recovery.json').exists():
        restored=read(OUT/'cached_recovery.json')
        if any(restored.get(k)!=summary[k] for k in ('binding','processing_binding','processing_revision')):
            raise ValueError('Cached recovery evidence has another generation/processing binding')
        restore_note='\n[完整实际缓存恢复](rr_v2_evidence/formal_build_20261106_citation_fix/cached_recovery.json)已调用生产`FormalRun.train`访问全部128条当前记录，禁止生成、分词请求、新预留、网络和子进程；仅在内存捕获状态写入。终态按生产端规范JSON序列化逐字节核对，全部run文件字节和三张账本表保持一致，新增模型与oracle均0。初次检查将SQLite运行时tuple与JSON读取后的array直接作Python类型比较而误报；[字段路径及原失败证据](rr_v2_evidence/formal_build_20261106_citation_fix/cached_recovery.initial_python_type_failure.json)保留全部130处类型差异及相同序列化哈希，修正只涉及离线检查器，不改原始结果或正确性条件。\n'
    truncation_note='''
故障版本已保留为历史：65次executor、2次teacher、34条完成记录及B1/B2检查点，不计作当前修复版本的完成记录。旧schema强制citation含§而拒绝9种公共Illinois引用；[修复前后真实前缀探测](rr_v2_evidence/formal_build_20261106/citation_fix_decoder.json)确认合法引用后的闭合引号由拒绝变为允许，71种公共引用均通过，畸形字符串仍被拒绝。这是离线语法回归，不是对原截断响应补造IR或新真实语义成功。

修复版本第16个来源的首个真实响应以784个输出token正常结束，4个native字段中的合法Illinois引用已闭合，IR进入`executed_expression`。对应[原始wire哈希与字段路径](rr_v2_evidence/formal_build_20261106_citation_fix/live_citation_closure.json)表明旧citation模式拒绝这些字符串、当前模式接受；没有改写原文或新增验证调用。该来源最终语义检查仍失败，不能将语法兼容性恢复计为A/B核心语义成功，也不能据此声称所有截断均已消除。

第26个来源在当前版本的两个请求仍均达到8192上限；原文中分别可解码出168和166个完整`pair`对象，同一对象最多重复84和83次，最终外层JSON未结束。[重复输出原文诊断](rr_v2_evidence/formal_build_20261106_citation_fix/remaining_length_repetition.json)仅截取已有完整子对象并保留字符偏移与原文哈希，没有补写IR或重新评分。这类已观察到的重复输出与旧Illinois引用闭合缺陷分列，不能将其一概归为schema故障，也不能假定提高上限就会得到正确答案。

原始故障响应、两次离线检查的顺序问题及停止前审计见[故障版本证据](rr_v2_evidence/formal_build_20261106/)。修复后的模型生成保持同一冻结版本从空库执行，不混用旧版本完成记录。
'''
    repair_note=f'''
## 同一运行的SARA参考查询修复

第77个来源原公开查询含两个法规谓词合取，旧参考适配器只允许单谓词而抛出异常；这属于具体实现缺陷，不是模型格式错误或研究方案变更。旧控制器在76条完成记录后退出，已付费首响应及全部351条调用行保全。修复只接纳安全法规谓词的正向合取，不补造缺失规则，也不放宽IR正确性检查。当前24条原始SARA查询/目标均与固定参考一致，原23条既有语义保持不变；164项原相关检查通过，另8项新增查询回归通过。初次安全边界测试暴露的失败及随后收紧谓词规则的记录同时保留。

[兼容修复清单](../artifacts/rr_v2_formal_build_20261106/run_citation_fix/processing_repair.json)封存当前处理绑定、证明文件哈希及76条原记录哈希。修复前76条、148次原响应的解析与B学习离线重算完全一致；生产恢复路径在禁止生成、网络、子进程及账本预留时，按完全一致的请求体/哈希读取第77条已付费响应，新增请求0，持久进度不倒退。[完整证据](rr_v2_evidence/formal_build_20261106_citation_fix/sara_reference_recovery/)分别记录查询回归、旧记录兼容和真实缓存恢复。本阶段仍是同一run接续，没有重启空库、重做旧来源或重置预算。

当前处理修订`{summary['processing_revision']}`仅覆盖参考查询解析、必要缓存字典顺序恢复和续接状态记录；模型、提示、schema、数据、seed及语义检查不变。前76条保留原始绑定，新来源另附当前处理绑定/修订，报告不将旧生成契约冒充当前完整源码。引用格式修复与本次查询修复分别保留原版本和失败原文；修复后的普通模型语义错误继续如实记录。
'''
    status='128来源及8批已完成并通过只读工件审计，交付核验待完成。' if final else f'运行中：已持久化{summary["complete_sources"]}/128来源、{summary["completed_batches"]}/8批。Goal未完成。'
    if not final and not summary['controller_alive']:
        status=f'已停止真实派发：已持久化{summary["complete_sources"]}/128来源、{summary["completed_batches"]}/8批。本轮控制器已停止，Goal未完成。'
    report=f'''# RR-v2 正式共享建库

更新：{summary['captured_utc']}。**{status}** 本阶段没有进行六臂正式评测、冻结测试或论文写作；训练参考匹配只是训练材料检查，不是性能评测或机制涨分证据。

从空技能库按原固定顺序执行一次128来源、8批建库。旧20来源预检、故障版本34个完成来源及其teacher汇总保留为历史，不作为本轮完成记录。原来源仍在128中，没有新增来源或种子；每个正式来源最多2次executor，每批最多2次teacher。适用的旧oracle仅通过同source/view/reference哈希复用，每来源额外视图累计最多4，不重置旧计数。

## 当前结果与机制覆盖

| 数据集 | 已处理来源 | A稳定 | A回退 | TRAIN回答/参考匹配 | B观察碰撞且有图 | B缺typed输入 |
|---|---:|---:|---:|---:|---:|---:|
{bank_table}

上表保留所有已处理来源，不按成功筛选。A稳定和B有图是两种覆盖口径，fallback答对不计核心成功。B输入不足、真实候选执行后无有效连接、无法重绑、无碰撞和无正式oracle分别保存，不能把缺输入写成已经完成搜索无解。已记录B碰撞共{sum(r['B_collisions'] for r in sources)}对；A共记录{sum(len(r['translation_actions']) for r in sources)}次第二次解析规划，其中{sum(a.get('joint_separation_complete',False) for r in sources for a in r['translation_actions'])}次声称分离完备。核验仍保留H≠Ω和条件性语义包含假设，不作全域等价声明。

以当前已处理来源为分母：A稳定证书{share('A_stable_sources')}，其中无fallback且TRAIN参考匹配{share('A_stable_reference_match_without_fallback_sources')}；实际记录native回退{share('A_native_fallback_sources')}，未获稳定证书{share('A_without_stable_certificate_sources')}。后者也包含未产生有效IR或答案的来源，因此与实际回退数不同。B观察到碰撞并形成可执行图的覆盖为{share('B_collision_pattern_with_graphs_sources')}；其余来源的机制覆盖缺口及原因单列。本阶段是建库，没有测量B正式预测的fallback率，不能用缺图比例替代该数值。

来源级完整列表见[source_status.csv](rr_v2_evidence/formal_build_20261106_citation_fix/source_status.csv)及[详细JSON](rr_v2_evidence/formal_build_20261106_citation_fix/source_status.json)；[机制覆盖](rr_v2_evidence/formal_build_20261106_citation_fix/mechanism_coverage.json)、[失败分类](rr_v2_evidence/formal_build_20261106_citation_fix/failure_classification.json)分列。可用`audit_build.py --mechanisms`仅用本轮实际记录的视图及既有结果重新执行B学习；这属于禁网络/子进程的离线核验，不是新增真实模型调用，不返回缓存学习结果，也不向历史较早attempt注入后来取得的标签。
原因分开解释，计数可重叠：

- **实现缺陷及修复**：旧Illinois引用闭合约束、SARA合取参考查询拒绝已分别定位并修复，保留修复前代码、原响应及兼容证明；故障版本完成数不计入当前建库。
- **模型输出错误或不完整**：{failures['schema_or_execution_invalid_final_sources']}个来源的最终IR为解析失败或无效，{failures['output_length_limited_calls']}次响应达到输出上限，{failures['training_reference_mismatch_sources']}个来源的训练回答不匹配参考；错误原文与来源状态保留。SARA缺槽绑定和Airline费用片段有具体原记录诊断，不用合法格式或默认值补全。
- **验证覆盖缺口**：真实A解析规划尚未形成分离完备批次；本阶段未调用B正式预测库策略，法律/数值上的库驱动执行与迁移效果未证实。未知残余、缺typed候选和未区分的图保留为未决，不能写成已经验证无解或成功。
- **既定回退与验收口径**：ContractNLI按既定范围不发反事实oracle、没有A稳定证书；模型声明unsupported和native回退如实单列。固定Horn语法、内置算子及fallback答对均不算新法律规则学习。建库完成按原128来源、8批及工件/账本交付判断，不追加涨分、技能数量、全分支实测或零回退要求。

{mechanism_note}
{truncation_note}
{repair_note}

## 检查点与冻结库

每批保存来源前缀、逐记录哈希、当时库状态、该批新teacher记录及当时累计账本快照。B1/B8另保存不可变冻结库与同材料MB普通对照冻结状态；只做材料投影，不为六臂各自重新建库。

| 检查点 | 来源前缀 | 新teacher请求 | 记录接纳 | 库模式数 | 检查点文件SHA256 |
|---|---:|---:|---|---:|---|
{batch_table}

Teacher记录接纳只表示汇总结构和来源绑定通过，其提议分为既有模式复述或未验证提议，不直接扩充B库；当前未验证提议共{sum(row['teacher_pending_proposals'] for row in summary['batches'])}条。冻结库接纳的是源内观察支持的模式，不能把汇总格式通过算作新技能学习。

| 冻结点 | 模式数 | 文件SHA256 |
|---|---:|---|
{freeze}

原始请求/响应、source记录、batch B1至B8检查点及冻结库位于[本轮run目录](../artifacts/rr_v2_formal_build_20261106/run_citation_fix/)。各批checkpoint中的ledger是当时快照；当前累计消耗读同一SQLite，不能将多个checkpoint费用相加。
{material_note}

## 固定配置与版本

Executor：Qwen/Qwen3-8B，thinking OFF，temperature0.6，top_p0.95，top_k20，seed45，max_tokens8192，context32768，串行请求。Teacher：gpt-5.6-sol、reasoning_effort=high、既有已验证Codex CLI；temperature未显式设置，后端数值未暴露。配置、原语/机制、提示/schema代码及源数据冻结，普通模型错误不触发调参或额外来源。

8192来自项目[executor.max_tokens](../configs/rr_v2_preflight.json)，作为每次HTTP请求的`max_tokens`发送给vLLM；32768是另一个总上下文设置。正式建库沿用并冻结该输出预算，teacher CLI不读取此项。

原始生成契约代码：`{summary['binding']['code_hash']}`；当前处理代码：`{summary['processing_binding']['code_hash']}`；语义配置：`{summary['binding']['config_hash']}`；数据：`{summary['binding']['data_hash']}`；manifest：`{summary['binding']['source_manifest_hash']}`。初次启动实现提交`{read(ROOT/"docs/rr_v2/formal_build_runtime.json")["initial_launch_source_commit"]}`，兼容续接修复提交`{read(ROOT/"docs/rr_v2/formal_build_runtime.json")["source_commit"]}`；原运行seal保存逐文件哈希、128个初始请求契约哈希及有效模型/teacher transport。启动前相关检查及本次teacher剩余额度/已付费结果恢复回归通过；准备阶段逐一确认128个空库首请求可放入上下文（最长14178 token）；本轮实际输入的完整源文、分词数和上下文占用另逐条核验，没有截断原文。旧科学记录与本轮结果按绑定分列，不混用不兼容结果。

## 实际消耗与保全

当前本轮executor {len(E)}次、teacher {len(T)}次；累计executor {summary['cumulative_counts']['executor']}/6000、teacher {summary['cumulative_counts']['teacher']}/20，pending {summary['pending']}。本轮executor已报告输入{cost['executor_prompt_tokens_reported']}、输出{cost['executor_completion_tokens_reported']} token；teacher输入{cost['teacher_input_tokens_reported']}、输出{cost['teacher_output_tokens_reported']}、reasoning输出字段{cost['teacher_reasoning_output_tokens_reported']} token。未报告usage的请求仍计费/占额，未知量不当作零：executor {cost['executor_usage_unavailable_calls']}次、teacher {cost['teacher_usage_unavailable_calls']}次。

计入本Goal故障版本后，共{cost['goal_executor_requests_including_aborted']}次executor、{cost['goal_teacher_requests_including_aborted']}次teacher；executor已报告输入/输出合计{cost['goal_executor_prompt_tokens_reported']}/{cost['goal_executor_completion_tokens_reported']} token，teacher输入/输出{cost['goal_teacher_input_tokens_reported']}/{cost['goal_teacher_output_tokens_reported']} token。故障版本还有1次中断请求的usage未知，仍全额占用请求次数；没有把这65E/2T退账或移出历史。

Executor请求墙钟耗时已报告{cost['executor_request_seconds_reported']:.3f}秒，teacher invocation {cost['teacher_invocation_seconds_reported']:.3f}秒；这是请求耗时，不是测得GPU时长。已有本地executor服务新增逐请求API现金支出0美元；GPU分摊成本与teacher实际现金账单未知，不能称算力免费或将estimated credits当真实USD。[逐请求账本](rr_v2_evidence/formal_build_20261106_citation_fix/request_ledger.csv)和[成本摘要](rr_v2_evidence/formal_build_20261106_citation_fix/cost_summary.json)保留失败、重试、原usage与未知费用。

修复版本启动前198条调用行（192E+6T）、119条meta及50条oracle逐值保留，包含最初127E/4T和本Goal故障版本65E/2T。本轮调整建库桶357（历史36+故障版本65+修复正式最多256）、恢复桶131，其余后续评测预留5472不变，合计仍6000。teacher已用6+本版本最多14=20；每批最多2次，重试前先为未处理批次各保留1次调用。Executor含后续5472评测预留的上界为192+256+5472=5920≤6000；没有追加总预算。完整审计核对来源限额、模型wire、空库起点、文件冻结、历史行及oracle总上限；[审计结果](rr_v2_evidence/formal_build_20261106_citation_fix/{'final_audit' if final else 'live_audit'}.json)。原始baseline与SQLite备份保留在本地`artifacts/rr_v2_formal_build_20261106/`。

## 观察与恢复

控制器身份为run目录的`process_identity.json`，核实实际PID与start_ticks，再读取`state.json`和账本。存活时仅观察，不重复启动。退出后用同一冻结版本及`python -m experiments.rr_v2_formal_build run`恢复：已完成的本轮记录免费恢复，失败/歧义请求保留收费，不隐式重新派发；恢复完整wire响应不新增模型请求。旧预检入口不是本轮的恢复队列。
{restore_note}

零模型审计（在本地开发目录、用已有环境）：

```bash
PYTHONPATH=. python reports/rr_v2_evidence/formal_build_20261106_citation_fix/audit_build.py
# 控制器结束且128来源/8批全部完成后：
PYTHONPATH=. python reports/rr_v2_evidence/formal_build_20261106_citation_fix/audit_build.py --final --mechanisms
PYTHONPATH=. python reports/rr_v2_evidence/formal_build_20261106_citation_fix/check_completion.py --restore
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
