# 当前工程验收通过，交付核验中 — 主训练关闭

A残余理论/分离批次/实际解析/token成本、五库有界程序体及接口契约、B非PW typed候选入口均已接通。154项相关检查、78个实际解码用例、当前20来源禁网络/子进程恢复及120次六臂控制流通过。新OFF真实PW主路径A/B分别语义通过；CNLI明确为合法回退，不计核心。B旧粗接口计数已纠正：22→12对，历史4个来源中保留3个B成功，index8无实际碰撞；原记录不删除。

同一账本executor127/6000、teacher4/20，新增3E（含一次IR失败）、1T；原124/3请求及50oracle完整，pending0。executor thinking固定OFF；教师temperature未显式设置、reasoning_effort=high。原数据/来源/seed未改，其他来源模型错误及B输入不足如实保留，不新增零回退、每库成功或涨分要求。

执行目录`/home/yndx/hhy/legal-skill-rr-v2`，分支`research/legalskillguard-rr-v2`，当前科学绑定`88770943aff923680fb8a50561c1e844222dd5806beff032ef0db99b20e88afc`。完整报告`reports/legalskillguard_rr_v2_method_gap_repair_20261106.md`；当前就绪凭据`reports/rr_v2_evidence/formal_readiness_method_gaps.json`。19条历史ON训练原文在当前算法重新处理、1条新OFF原文，生成来源分列，不作为新OFF预测缓存；新首16材料教师汇总已接纳。

Goal仍active，待开发分支交付独立核验后关闭；本阶段不再新增模型请求、不启动主训练/正式评测/论文。下文旧complete、blocked、额度、ON和旧准备凭据均是历史，不作为恢复队列。

---

# 当前版本与真实核心主路径核验

当前执行目录`/home/yndx/hhy/legal-skill-rr-v2`；科学绑定`47cddfaed75c295bf7655a7a2167e940db85c7c2b7520625a9534e746baa6b14`。新增核心生成绑定`c5aaeb53088af3c175468ac15e8d3599d8bd4c6ea3f81fccfa2d02bc63ffcb73`；原工程生成绑定077a748c…保留。账本124 executor、3 teacher，原总预算6000/20，来源仍为原20。

- 离线实现检查：`/home/yndx/hhy/legal-skill-current/.venv/bin/python -m experiments.rr_v2_offline`，144项，禁网络。
- 当前全部20来源保存恢复：`python -m experiments.rr_v2_semantic_preflight finish`。已完成记录只读恢复原预算快照；实际累计账本另读同一SQLite，不重写旧完成记录。
- 新真实A/B主路径原始记录：`artifacts/rr_v2_preflight/core_primary_v1/sources/`。4个原固定PW来源各1次新物理请求，不重复运行生成；计费已扣总账。
- 当前独立语义核验：`PYTHONPATH=. python reports/rr_v2_evidence/semantic_preflight/core_acceptance.py`；对应新真实请求与算法的免费重放：同目录`replay_core_wire.py`。
- 首次核验脚本多加了H必须缩小条件，已修正并保留原始记录。原生连接语义与碰撞分离不放宽；H仍不是Ω。
- 当前准备凭据`reports/rr_v2_evidence/formal_readiness_core.json`绑定执行代码、原20来源和新4条真实核心证据；不授权主训练。

A/B核心成功只计新真实4来源。原20的native答案10/20；其中6条fallback答对不计核心成功。A、B主路径验证覆盖各4/20，非核心/回退各16/20，原因和未覆盖能力见当前检查报告。数据、模型、seed45、thinking ON及原分区不变；所有主训练和正式评测开关仍关闭。

下方为历史复现记录，旧预算和旧启动规则不作为当前授权。

---

# 当前复现入口（96额度已用完）

实现a00ce55，science binding见typed_contract_v8/seal.json；当前不再发生成请求，不启动主训练/正式评测/测试。旧轮次数/首错停止规则均被最新授权替代，当前停止原因是96额度及验收未通过。

在/home/yndx/hhy/legal-skill-rr-v2执行以下离线/缓存核验：

```bash
/home/yndx/hhy/legal-skill-current/.venv/bin/python -m experiments.rr_v2_offline
/home/yndx/hhy/legal-skill-current/.venv/bin/python reports/rr_v2_evidence/cumulative_repair/verify_restore.py
/media/sangfor/vdb/legal-skill-runtime/inference-qwen3-8b-vllm0102/bin/python -m experiments.rr_v2_check_compiler
/home/yndx/hhy/legal-skill-current/.venv/bin/python reports/rr_v2_evidence/cumulative_repair/update_report.py
```

前两项阻断网络/生成并核对实际缓存。第三项只加载本地tokenizer和xgrammar、阻断网络，不加载模型权重；第四项只读取账本写报告。当前账本不重置。不要重启旧thinking/pilot、schema_round2或prepare/one来新增请求；副本已验证第97次被拒绝。历次对应源码、ledger及科学seal均在preserved_before_*及cumulative_repair/typed_contract_v*/，仅使用对应版本重放历史结果。

数据5b7683f05c921598c4bab6dc29834df3dc7595e3795d46551732446efa3eacc0；语义配置ce3f15a5e0544b1dab5c84bfb7a4a122c7f072bf42a9efa60c4f8f4f4b3946a3；清单ef0f419d13f5219f0faeb97543b52d27be8c50a67243103e542013dc24ae3ca4；最终科学代码4ccc8f79e9a367de41cbea11ae52189d0fc72e7f28a6e99124206ceab2ec1dac。旧formal_readiness凭据不代表当前训练就绪。

---

以下为历史复现记录，不作为当前启动队列。

# RR-v2 第二轮结果核验与复现

更新：2026-11-06。第二轮首请求未通过IR类型/执行闸门，已按用户停止规则停止。实际executor85/100、teacher2/2，本轮1/12，余11不自动使用；goal未完成、主训练未就绪。当前没有RR客户端。

## 只读核对账本和停止状态

```bash
cd /home/yndx/hhy/legal-skill-rr-v2
/home/yndx/hhy/legal-skill-current/.venv/bin/python - <<'PYCODE'
import sqlite3, json
from pathlib import Path
root = Path.cwd()
db = sqlite3.connect('file:' + str(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True)
print(db.execute('SELECT role,status,COUNT(*) FROM calls GROUP BY role,status').fetchall())
s = json.loads(db.execute("SELECT value FROM meta WHERE key='strict_schema_round2_state'").fetchone()[0])
print({k:s[k] for k in ('phase','next_index','inflight','gate_passed','stop_reason')})
print(json.loads((root / 'reports/rr_v2_evidence/strict_contract_round2/round2_summary.json').read_text()))
PYCODE
```

预期85条completed executor、teacher各1条completed/failed；第二轮phase=stopped、next_index=1、inflight=null、gate_passed=false。API请求完成也占额，其IR验证失败，不退款。`stop_reason=no_executable_model_IR`，具体原因为Nonboolean operand。不要启动旧thinking/pilot、round2 run/continue或主训练来验证计数。

## 离线代码和严格响应语法

```bash
/home/yndx/hhy/legal-skill-current/.venv/bin/python -m experiments.rr_v2_offline
/home/yndx/hhy/legal-skill-current/.venv/bin/ruff check legal_skill_guard/rr experiments/rr_v2*.py tests/test_rr*.py
/media/sangfor/vdb/legal-skill-runtime/inference-qwen3-8b-vllm0102/bin/python reports/rr_v2_evidence/check_round2_schemas.py
```

相关125项通过，测试进程禁止网络；后一个命令只加载固定tokenizer，12个source-bound schema各26个语法用例，不加载模型权重或请求模型。312个语法用例不证明程序语义或主训练就绪。原始日志、文件hash和语法检查收据分别在offline_latest和strict_contract_round2/backend_schema_precheck.json。

## 原始输出的确定性恢复核查

`legal_skill_guard/rr/raw_recovery.py:recover_format`只转换明确表示别名，并保存逐项逆向还原记录。不补query/分支/来源，不读取评分标签。原36条详细记录在raw_recovery_audit.json，原84条扩展核查在all_original_outputs_recovery.json。可用同一固定TRAIN公开包与原保存账本复现扩展核查：

```bash
/home/yndx/hhy/legal-skill-current/.venv/bin/python - <<'PYCODE'
from pathlib import Path
import sqlite3, json
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.raw_recovery import recover_format
from legal_skill_guard.rr.engine import analyze
root = Path.cwd()
data = PreflightData(root, root / 'reports/rr_v2_evidence/data_manifest.json')
db = sqlite3.connect('file:' + str(root / 'artifacts/rr_v2_preflight/preserved_before_strict_schema_round2/research_ledger.sqlite3') + '?mode=ro', uri=True)
checked = recovered = 0
for source, raw in db.execute("SELECT source,result FROM calls WHERE role='executor'"):
    value = recover_format(json.loads(raw)['content'])
    checked += 1
    if 'proposal' in value:
        a = analyze(data.public(source), json.dumps(value['proposal']))
        recovered += a['program_status'] in {'executed_expression', 'candidate_pool_agreement_only'}
print({'original_outputs_checked': checked, 'executable_recovered': recovered})
PYCODE
```

预期84、0。这个核查只读公开TRAIN输入，不调用grade；公开Horn独立执行不计作模型IR恢复。

## 真实阶段与证据保存

本轮实现提交ecd0ea8，科学代码hash`ef4dd1e10bac8190ad4ad5a35aed728940c3442612bbf4e9d899d5c153ef1d58`；配置语义hash`ce3f15a5e0544b1dab5c84bfb7a4a122c7f072bf42a9efa60c4f8f4f4b3946a3`，数据hash`5b7683f05c921598c4bab6dc29834df3dc7595e3795d46551732446efa3eacc0`。轮次授权已同步2，源码/协议没有在实测中改变。

- 当前stage为`artifacts/rr_v2_preflight/strict_contract_round2/`，包含seal、12个原提示payload、1个真实request/wire/result、validation、round_result和停止状态。
- `reports/rr_v2_evidence/strict_contract_round2/`保存失败原因、费用、20来源清单、原86行/metadata不变证明，以及禁止generation的实际终态恢复证明。
- 原始一轮40对照+8修复+36小试的SQLite与科学源/运行时在`preserved_before_strict_schema_round2/`。原完整20来源库与旧绑定515e46ed…在oracle_guard及preserved_before_formal_routing_integration。
- 新请求只替换schema，原消息、ON、seed45、max_tokens8192、temperature0.6/top_p0.95/top_k20、串行1和重试0均不改。新旧payload与请求hash可逐项比对；原serving tokenization与当前本地tokenizer精确相同。
- 最多2次的初始闸门和总12/96/100上限由同一账本执行。首次失败后停止状态禁止再reserve新ID；实际账本副本已验证拒绝下一请求。终态恢复增加模型0、oracle0，没有重新发送原请求。

重新运行真实阶段需要匹配的冻结源、同一账本/数据/工件以及新的明确执行决定；现有剩余11次不能覆盖已触发的停止条件。不要删ledger或将failed/reserved记录改为免费重试。

原源、v0.23、utility v6、全部失败、原Qwen服务PID958223/startticks486445918保留。模型目录和所有环境仍在本机。当前正式训练/六臂评测/冻结测试/论文开关均关闭，formal_readiness.json仅为上一阶段历史组件兼容性收据，不能当作当前启动许可。
