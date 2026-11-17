# M1 源码与最小复核包

此包先交付当前修订及既有证据；M1 可行性核验尚未完成，M2 保持停止。

在研究分支的本次提交检出后，用 Python 3.11 创建环境并运行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r reports/two_method_followthrough_20261116/M1_evidence_20261117/requirements.txt
.venv/bin/python -m experiments.m1_replay_evidence
```

该命令不连接模型或教师，不训练、不读 DEV/TEST。它验证文件哈希，并对24份既有真实响应及其源文参考输入运行同一 `decode_response` → 确定性消费者 → 原生评分链，核对66项原生评分结果；再检查原固定32来源小试的228行原生任务×候选分数。原 M1 选中的 columns 有76行，正分0。参考输入是诊断夹具，不能当模型正确率。

文件对应关系：

| 文件 | 内容 |
|---|---|
| `chain_cases.json.gz` | 按来源/视图/接口关联原公开输入、版本化接口、参考源审、真实响应、修订后解码拒绝和执行/评分结果、修订前输出；仅 TRAIN 开发/校准注释 |
| `key_raw_calls.json.gz` | 对应24次物理请求的原请求体、精确 base64 wire、原始响应及结算结果；没有鉴权头或凭据 |
| `ledger_index.json` | 连续账本中的物理 ID、状态、请求 hash 和结果 hash，不导出整库 |
| `pilot_native_scores.json` / `pilot_report.json` | 原固定小试全部逐来源结果，包含已暴露的内部结构评价；不是新盲测 |
| `existing_offline_results.json` | 177参考同链检查、117付费读数不变检查、MAUD共同 F 修复前后结果 |
| `selection_freeze.json` | 原候选选择及冻结依据 |
| `manifest.json` | 必要源码/依赖及证据文件 SHA256、选择规则、输入范围 |

24个关键案例按每库最小来源 ID 取一个视图，另完整保留已定位的 MAUD 上下文缺失来源三个视图；没有按得分挑样。原177份参考、所有历史失败和连续账本原地保留，未全部上传。`frozen_F_library.json.gz` 是消费者依赖的一个完整历史 F 库；保留完整压缩字节是为了满足既有整文件哈希绑定，复现命令仅在目标文件不存在时解压，并验证 SHA256。其附带历史提案不作为执行队列。原库未改写。

同链实现位于 `legal_skill_guard/paired_interfaces/production_decode.py`，参考编码在 `reference_wire.py`，共同部分消费者修复在 `partial_legal_consumer.py`。程序生成器位于 `asset_interfaces.py`、`program_residual.py`、`airline_interfaces.py`，三种布局模板本身不是自动语义改写的贡献。源文件闭包中有历史共享的图结构/消费者支持代码，但不启动 M2 学习。

输入缺失例：MAUD 原任务截取遗漏同一 Section 的疫情例外；完整 Section 恢复仍是输入提案，旧参考不自动升级。消费者覆盖例：MAUD 参考探针经共同 F 修复，可执行9→66，D/C正分6→51；同54份真实输出仍可执行0、正分0，不能称 M1 学习增益。CNI 等未覆盖范围保留拒绝，不从缺失推导否定。

原官方 OpenExempt 评价依赖包含在 `data/cache/openexempt/servantez-OpenExempt-ec6fa25/` 的必要源码中，版本 `ec6fa2547431096588ce2d3ef107b8adc33cd4fe`，CC BY 4.0；没有上传整套数据缓存。SARA 执行还需系统 SWI-Prolog；本包选定的拒绝案例不以安装缺失制造成功。执行器原配置为 Qwen3-8B、thinking关闭；离线复现不会加载该模型。
