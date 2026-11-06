"""Assemble evidence only after the complete current-stage receipt validates."""
from pathlib import Path
import json,sqlite3
from collections import Counter
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.readiness import validate
root=Path(__file__).resolve().parents[3];out=root/'reports/rr_v2_evidence/semantic_preflight';base=root/'artifacts/rr_v2_preflight'
seal=json.loads((base/'seal.semantic_path.json').read_text());stage=base/seal['processing_continuation']['artifact_subdirectory']
ready=validate(root,seal['binding']);data=PreflightData(root,root/'reports/rr_v2_evidence/data_manifest.json')
summary=json.loads((out/'summary.json').read_text());sources=json.loads((out/'source_status.json').read_text())
offline=json.loads((root/'reports/rr_v2_evidence/offline_latest.json').read_text());backend=json.loads((out/'backend.json').read_text());breplay=json.loads((out/'learning_replay.json').read_text());thinking=json.loads((out/'thinking_rescore.json').read_text());restore=json.loads((out/'restore_after_core.json').read_text())
rows=json.loads((out/'request_ledger.json').read_text());new=[r for r in rows if r['id'].startswith(seal['study_preflight_revision'])]
assert [s['source'] for s in sources]==data.order and all(s['current_record_exists'] for s in sources)
assert summary['historical_call_rows_preserved']==98 and summary['historical_meta_preserved']==77 and summary['oracle_records_preserved']==50
assert all(r['status'] in {'completed','failed'} for r in rows)
assert not offline['exit_code'] and offline['network_blocked'] and len(backend['records'])==12
assert breplay['all_exact'] and thinking['selection_unchanged']
assert restore['model_calls_added']==restore['oracle_views_added']==0 and ready['engineering_ready']
core_e=[r for r in rows if r['id'].startswith('core_primary_v1:')]
new_e=[r for r in new if r['role']=='executor'];new_t=[r for r in new if r['role']=='teacher']
assert 0<len(new_e)<=24 and len(new_t)==1 and all(1<=n<=2 for n in Counter(r['source'] for r in new_e).values())
assert len({r['source'] for r in new_e})==12 and {r['source'] for r in new_e}<=data.allowed
assert not json.loads((root/'configs/rr_v2_preflight.json').read_text())['formal_run_enabled']
assert not json.loads((root/'configs/rr_v2_formal.json').read_text())['run_enabled']
assert not json.loads((root/'reports/legalskillguard_rule_reasoning_protocol_v2.json').read_text())['run_enabled']
checks=[c for s in sources for c in s.get('IR_checks',[])]
native_good=[s['source'] for s in sources if s['current_score']['task_correct']]
native_bad=[s['source'] for s in sources if not s['current_score']['task_correct']]
full_good=[s['source'] for s in sources if s.get('strict_repair_check_passes',0)]
stable=[s for s in sources if s['certificate_status']=='completion_stable']
assert all(s['current_score']['task_correct'] for s in stable)
def usage(records):
    counts=Counter();seconds=0
    for r in records:
        result=r['result'] or {};u=result.get('usage') or result.get('invocation',{}).get('usage') or {}
        for k,v in u.items():
            if type(v) in (int,float):counts[k]+=v
        seconds+=result.get('elapsed_seconds',0)
    return dict(counts),round(seconds,3)
new_e_u,new_e_s=usage(new_e+core_e);new_t_u,new_t_s=usage(new_t)
all_e_u,all_e_s=usage([r for r in rows if r['role']=='executor']);all_t_u,all_t_s=usage([r for r in rows if r['role']=='teacher'])
core=json.loads((out/'core_acceptance.json').read_text());assert core['complete'] and core['A_pass'] and core['B_pass']
metrics=dict(core_A_primary_validated=4,core_B_primary_validated=4,core_A_fallback_sources=16,core_B_no_verified_connector_sources=16,
    core_fixed_source_denominator=20,new_core_executor_requests=len(core_e),native_task_correct_sources=native_good,native_task_unresolved_sources=native_bad,
    current_strict_repair_pass_sources=full_good,strict_repair_pass_requests=sum(c['full_strict_repair_check'] for c in checks),
    current_model_IR_executed=sum(c['executed'] for c in checks),schema_valid_requests=sum(c['typed_schema_pass'] for c in checks),
    program_native_correct_requests=sum(c.get('native_task_correct') is True for c in checks),
    public_literal_grounded_requests=sum(c.get('public_literal_grounding') is True for c in checks),
    stable_sources=len(stable),stable_wrong_sources=0,new_executor_usage=new_e_u,new_executor_seconds=new_e_s,
    new_teacher_usage=new_t_u,new_teacher_seconds=new_t_s,all_executor_usage=all_e_u,all_executor_seconds=all_e_s,
    all_teacher_known_usage=all_t_u,all_teacher_seconds=all_t_s,
    acceptance_basis='Original handoff engineering/data/parsing/interface/execution/freeze/resume/accounting requirements; unresolved semantics retained; no20/20 accuracy or gain threshold',
    full_task_semantics_claim=False,main_training_started=False)
(out/'final_metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n')
lines=['# LegalSkillGuard RR-v2 当前检查报告','',
'本阶段实现与原固定20来源工程预检已完成，当前版本恢复及正式路径准备凭据已核验。主训练、六臂正式评测、冻结测试和论文均未启动。Goal是否标记完成以最后一次Goals工具结果及交接状态为准。','',
'本结论依据原交接的工程验收条件（第42、54、56行）和方案第三步：语义未解决项须保留状态，不要求20/20正确或显著涨分。最新补充要求A、B各有真实主路径和对应语义证据，已单列，回退不计入核心成功。下面单独报告所有语义失败；“工程预检完整”不表示法律推理或法条翻译全部通过。','',
 '## A、B核心验收与fallback','',
'按最新验收补充，fallback答对、旧结果重放和默认输出均不计核心成功。另在原固定4个ProofWriter来源上各进行1次新的真实executor请求，调用共用ingest_source，B直接执行learn_source，未返回缓存学习结果；缓存只提供原已扣账oracle的期望标签。',
'',
'| 方法 | 新真实主路径语义通过 | 固定20来源覆盖 | 非核心/回退比例及原因 |',
'|---|---:|---:|---|',
'| A | 4/4新验证来源 | 4/20（20%） | 16/20（80%）：12个自然语言规则来源未获完整语义/稳定证书，4个ContractNLI按设计native fallback；其中native回退答对6条，不计核心成功 |',
'| B | 4/4新验证来源 | 4/20（20%） | 16/20（80%）未获已核验可执行连接：8个金融/费用来源仅membership字段，4个SARA为字段提议/无碰撞/参考失败，4个ContractNLI无反事实oracle；这些均不计核心成功 |',
'',
'A真实证据来自当前受限公开文法编译、completion_theory及Ω稳定性检查，输出为Unknown/False而非固定默认标签；本次真实样本覆盖全编译后稳定分支，残余TOP、相关未译例外、无关残余和联合补译等分支有离线反例验证，本次不宣称这些分支已真实命中。B分别观察6、4、6、6个真实粗粒度碰撞，细化entity_equality后观察映射无冲突，执行连接在原来源及4个参考视图上共20次语义检查全匹配；真实覆盖仅为实体见证连接，分组cap和共享额度等未被冒充为真实主路径成功。',
'',
'最初核验脚本附加了“候选H必须减少”的条件，已撤销这一非原方案门槛。原始检查与全部候选数保持不变；当前以碰撞被字段区分及实际连接执行语义核验。保留H歧义，不宣称H等于Ω或唯一识别。详见[独立A/B证据](rr_v2_evidence/semantic_preflight/core_acceptance.json)及[新真实路径逐字恢复](rr_v2_evidence/semantic_preflight/core_wire_compatibility.json)。',
'',
'## 实际结果','', 
f'- 20/20当前记录齐全：12个受影响来源经共用两次联合调用重新验证，8个未受影响来源免费重放，来源、seed、模型与采样不变。新增executor{len(new_e)+len(core_e)}次（契约修复{len(new_e)}、核心主路径{len(core_e)}）、teacher{len(new_t)}次，无应用层自动重试。',
f"- 新{len(new_e)}条中schema有效{metrics['schema_valid_requests']}条、模型IR实际执行{metrics['current_model_IR_executed']}条、IR输出匹配原TRAIN答案{metrics['program_native_correct_requests']}条；完整严格修复检查通过{metrics['strict_repair_pass_requests']}条、涉及{len(full_good)}来源。未通过项均保留。",
f'- 最终native任务答案匹配{len(native_good)}/20来源，未解决{len(native_bad)}/20。稳定来源{len(stable)}条，稳定但错误0条；未解决NL任务均未获得稳定性证书。最终native答案、IR候选结果和严格语义检查分列，未按训练答案选择二者。',
'- 144项相关离线检查通过；12来源72个实际token类型用例和1个真实第二次输入复用用例通过。当前20来源B学习在禁网络、禁子进程、禁新增oracle条件下复算，全部与原结果一致。',
'- 首批16来源完成实际教师汇总，最后4来源按原方案保留待接续的部分批次。20来源checkpoint、部分库和六臂共享材料已保存；禁网络和子进程重复恢复不新增模型调用或oracle。',
'- 修复后的评分器免费重算原40条thinking比较：ON9/20、OFF10/20，ON正确而OFF错误来源仍存在，按原固定判据继续ON。没有新增对照调用。','',
'## 问题分类与修改','',
'已修复的实现缺陷是：跨适配器提示示例外溢；预检仍发送旧source-free schema；共用训练和推理的第二次调用没有传递一致的source/previous schema；OE评分缺原生类型校验、把数组顺序及1/1.0当作语义差异。现在统一schema传递，已有公开字面值可按原值复用，原生EC/EV映射采用保留重复项的无序完整比较，金额精确比较，官方F1不变。',
'',
'原工程预检36条共用请求及另外4条新核心主路径请求已全部免费重建：24条新请求的wire字节精确一致；12条沿用请求仅规范化三项结构化元数据内部的JSON键顺序，公开文本、值、schema和其他字段不变。全部输出重放一致。跨适配器修复后重新完成20来源零调用恢复，生成绑定保留`077a748c30fd1acf3dd447c1e54bab826374bc1fd74e0709503c3e09006dd14a`，当前执行绑定另列，历史记录未覆盖。\n\n删除按`s_asset`变量名推断资产已提取完整的额外假设；执行器仍拒绝重复输出键。旧95号错误没有被合并为新答案。旧36条输出经47次可逆格式修正仍缺规则/query/分支或已截断，不能恢复可执行IR；旧85–96号响应现行代码免费重放后严格检查仍0通过。',
'',
'剩余模型错误包括：错解法律查询、错用费用或豁免规则、错引用源段、把节号自身相等当作规则条件，以及在固定token上限内未完成JSON。SARA有IR标签正确而native fallback错误的实例，也有恒真空壳程序标签碰巧正确的实例；未借助参考答案补造规则或改选答案。公共字面值检查不证明普遍自然语言等价，原方案的翻译忠实性条件保持明确。',
'',
'先前验收解释把“严格修复闸门0通过、9来源未在修复后重验”泛化为整体小试未完成。原20来源小试当时已执行；真正工程缺口是现行共用路径及当前版本恢复/准备凭据。本次补齐这些缺口，同时保留严格语义失败，未追加100%准确率门槛。','',
'## 原验收逐项核验','',
'| 条件 | 当前证据 |','|---|---|',
'| A覆盖/TOP/冲突/域外/超时、H与Ω分离；B join/cap/共享额度/次序/见证 | 144项网络阻断离线检查；原方法和实现映射保留 |',
'| 五库适配、数据划分与隔离 | 固定数据manifest、TRAIN访问白名单、分区测试；无新来源/测试标签 |',
'| thinking真实开关与一次固定选择 | 原真实记录及本次40条免费重评分，继续ON |',
'| 20来源真实流程、解析/执行/接口、失败处理 | 当前20来源完整记录；24条新真实请求；B20来源缓存复算完全一致 |',
'| 首16来源教师汇总、剩4来源待接续 | 当前实际teacher_batch1及partial batch状态 |',
'| 部分库、checkpoint、同账恢复 | 当前20来源免费恢复；98旧请求/77旧meta/50oracle逐项不变 |',
'| 六臂共享材料及正式路径接续 | 当前科学绑定的formal_readiness_core.json已validate，未启动正式运行 |',
'| 调用、token、费用、时间、旧记录保留 | request_ledger.csv/json、summary.json、final_metrics.json及原SQLite |',
'| 原范围、预算及关闭开关 | 原6000/20及原桶；固定20来源；全部正式开关仍false |','',
'## 来源级结果','',
'“native正确”只指完整任务答案匹配；“严格通过”另外包含IR执行与公共溯源检查。完整ID、每次检查和工件位置见[source_status.json](rr_v2_evidence/semantic_preflight/source_status.json)。','',
'| 原index | 数据集/ID前缀 | 方式 | native正确 | 可执行IR数 | 严格通过数 | 状态 |','|---:|---|---|---|---:|---:|---|']
for s in sources:
    sid=s['source'];suffix=sid.split(':',1)[1][:12]
    lines.append(f"| {s['index']} | {s['dataset']}:{suffix} | {'免费重放' if s['generation'].startswith('free') else '真实重验'} | {'是' if s['current_score']['task_correct'] else '否'} | {s['current_executable_IRs']} | {s.get('strict_repair_check_passes','—')} | {s['certificate_status']} |")
lines+=['','## 请求、实际费用和时间','',
f"累计executor **{summary['executor_used']}/6000**、teacher **{summary['teacher_used']}/20**。原thinking40、建库36、恢复{sum(r['bucket']=='shared_retries_and_recovery' for r in rows)}；恢复桶原上限232不变。失败、截断、重试均计数，待结算0；没有清账或重置历史限额。旧96/100与teacher2仅是已被最新用户授权取消的预检子上限。",'',
f'本次executor输入/输出token：`{new_e_u}`，累计请求时延{new_e_s}秒；本次teacher可观察usage：`{new_t_u}`，时延{new_t_s}秒。executor全历史token：`{all_e_u}`，时延{all_e_s}秒；teacher全历史已知usage：`{all_t_u}`。reasoning token是输出的子集，不重复相加。','',
'本地executor新增按次API现金费用为US$0（既有服务，无按次API账单），GPU成本没有可用计价账单，不能记作零总计算成本。teacher通过既有授权CLI运行，现金账单不可得；旧失败teacher调用usage/费用未知，次数已扣除。未新增付费资源，也未使用未授权模型。','',
'## 可复现与证据','',
f"科学绑定`{ready['execution_binding']['code_hash']}`；配置语义绑定`{seal['binding']['config_hash']}`；数据绑定`{seal['binding']['data_hash']}`；manifest绑定`{seal['binding']['source_manifest_hash']}`。",'',
'工作目录`/home/yndx/hhy/legal-skill-rr-v2`，分支`research/legalskillguard-rr-v2`。离线复现：`/home/yndx/hhy/legal-skill-current/.venv/bin/python -m experiments.rr_v2_offline`。当前已完成记录的`python -m experiments.rr_v2_semantic_preflight finish`可再次免费恢复；先核实账本和进程，不能重复启动未结算请求。', '',
'[诊断及字段证据](rr_v2_evidence/semantic_preflight/diagnosis.md) · [逐请求账本](rr_v2_evidence/semantic_preflight/request_ledger.csv) · [费用与计数](rr_v2_evidence/semantic_preflight/summary.json) · [完整指标及成功/未解决ID](rr_v2_evidence/semantic_preflight/final_metrics.json) · [B复算](rr_v2_evidence/semantic_preflight/learning_replay.json) · [免费恢复](rr_v2_evidence/semantic_preflight/restore_after_core.json) · [当前准备凭据](rr_v2_evidence/formal_readiness_core.json) · [授权](../docs/rr_v2/original_budget_preflight_authorization.json)。','',
'## 阶段结论与最小下一步','',
'本次没有调整研究问题、A/B机制、数据或模型方案；已完成当前范围的工程修复和完整固定来源预检，另补齐A、B各自新真实主路径语义证据。模型法条翻译与任务语义仍存在上表所列未解决项，未宣称法律推理质量已验证。核心覆盖和fallback比例已明确；未把这些任务回退计为A或B核心验证成功。原方案允许将这些状态保留进入后续固定研究流程；它们不被当作已核验编译结果或稳定证书。','',
'无需新增预检额度。本阶段停止；最小下一步是审阅未解决来源和本报告，再另行决定是否授权原定128来源主训练。本次保持全部正式开关关闭，不自动进入训练、评测或论文。','',
'<!-- HISTORICAL_REPORT -->','',
'以下为最新授权前历史报告；其旧额度、blocked及尚未重验数量均已由上述当前状态取代。','',
'---','', (out/'report_before_latest_authorization.md').read_text()]
(root/'reports/legalskillguard_rr_v2_implementation_check_report.md').write_text('\n'.join(lines).rstrip()+'\n')
print(json.dumps({k:v for k,v in metrics.items() if not isinstance(v,list)},ensure_ascii=False))
