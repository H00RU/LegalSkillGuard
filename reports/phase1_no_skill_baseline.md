# Phase 1：无技能基线实施与实验报告

生成时间：2026-08-08（Asia/Shanghai）
阶段结论：**Phase 1 工程 pilot 完成并通过验收；它不是论文正式主实验。**

## 1. 实验范围与边界

本阶段在 DLawBench 官方公开的 30 个中国法案件上构建无技能基线。由于公开 release
少于论文报告的 264 个中国法案件，且没有逐案领域标签，本结果只用于验证项目架构、
基线行为和评测闭环，不能表述为 full DLawBench 复现或领域分层主实验。

固定划分为 20 个 `pilot_generation`、5 个 `acceptance`、5 个 `reserve` 案件；seed=42，
同一底层案件的四个 persona 永远处于同一 partition。split manifest SHA-256 为
`ea6eb089df4e2deebee6d5326d48c6cfba051b8710059492292bfd8f7b6e41d7`。

比较方法：

- B0 Direct Answer：每个案件只读取开场白并直接生成 memo，共 20 条；
- B1 Prompted Multi-turn：20 案 × `P_WD/P_WS/P_CS/P_CD`，共 80 条；
- 两者使用相同 Qwen3-4B backbone、memo 格式、公开案件和官方 evaluator；
- 本阶段不启用 structured state、技能、verifier、risk gate 或参数训练。

## 2. 冻结环境

| 项目 | 固定值 |
|---|---|
| Backbone | `Qwen/Qwen3-4B` |
| Revision | `1cfa9a7208912126459214e8b04321603b3df60c` |
| 模型 manifest SHA-256 | `e842cc2c71e527b27971d165c4a4a7af0da3b2b6caf0198d68326b4086770695` |
| 模型许可证 | Apache-2.0 |
| 精度 / 量化 | bfloat16 / 无量化 |
| GPU | NVIDIA A40 49140 MiB；driver 570.133.20 |
| Runtime | torch 2.8.0；transformers 4.56.2；vLLM 0.10.2 |
| 推理 | temperature=0，thinking disabled，server seed=42 |
| 确定性约束 | request worker=1；evaluation worker=1；`VLLM_ENABLE_V1_MULTIPROCESSING=0` |
| Git commit | `f92a0340d95f11ffcd8882e196b65d66a98d1c12` |

模型权重、配置、tokenizer、索引和许可证共 12 个运行关键文件已逐一对照官方冻结
revision 的字节数和 SHA-256。ModelScope 仅作为下载镜像，canonical source 仍为官方
Hugging Face revision。

vLLM 0.10.2 的 online serving 默认不承诺可复现。并发 8-worker 的两批吞吐试验确实
产生了措辞差异，因此未被选为最终基线。最终协议使用单 worker，并在相同硬件和版本上
完整运行两批；这一限制与 vLLM 的
[官方可复现性说明](https://docs.vllm.ai/en/v0.10.2/usage/reproducibility.html) 一致。

## 3. 实现产物

- DLawBench 最小权限 adapter：律师只读取 opening；客户只读取 `client_belief`；
  evaluator 才读取完整案件与 rubric；
- 冻结 LLM 客户模拟器，persona 与完整历史进入 client prompt，隐藏 prompt 不写入轨迹，
  只记录其 SHA-256；
- B0/B1 统一 Pydantic 轨迹 schema，记录可见输入、原始动作、规范化动作、客户回复、
  token、finish reason、seed、模型 revision 和运行 manifest；
- 本地 vLLM OpenAI-compatible client 明确绕过主机 HTTP proxy，避免本地敏感提示被代理；
- 官方 DLawBench `evaluate.py` 与 `metrics.py` 保持上游代码不变，通过本地模型桥接执行；
- custom metrics 与逐轨迹语义哈希复现检查均可独立重跑。

## 4. 验收结果

选定运行：`phase1_pilot_deterministic_seed42_a`；完整复现运行：
`phase1_pilot_deterministic_seed42_b`。

| 验收项 | 结果 |
|---|---:|
| 预期 / 实际轨迹 | 100 / 100 |
| B1 case-persona cells | 80 / 80 |
| 失败 | 0 |
| schema 校验 | 100% 通过 |
| 非空 memo | 100% |
| 五个必需章节 | 100% |
| Lawyer `finish_reason=length` | 0 |
| Client `finish_reason=length` | 0 |
| 完整官方 evaluation sessions | 100 / 100 |
| 官方必需分数缺失 | 0 |
| 两次全量语义哈希 | 100 / 100 完全一致 |

复现比较只排除 `run_id`、创建时间、总耗时和逐步延迟；模型输入、输出、客户回复、动作、
token 计数、finish reason 与 memo 均参与哈希。

## 5. 官方 DLawBench 指标

| 方法 | Sessions | Fact Coverage | Inquiry | Elicitation | Fact Resolution | Issue Resolution | Resolution | Fidelity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 Direct | 20 | 0.8081 | 0.0625 | 0.4353 | 0.7026 | 0.4317 | 0.5671 | 0.9067 |
| B1 Multi-turn | 80 | 0.7667 | 0.0898 | 0.4283 | 0.6803 | 0.6197 | 0.6500 | 0.9106 |

B1 相对 B0 的 Resolution 提高 0.0829，主要来自 Issue Resolution 提高 0.1880；
Fidelity 提高 0.0039。与此同时 Fact Coverage 下降 0.0414、Fact Resolution 下降
0.0223、Elicitation 下降 0.0070。Inquiry 虽提高 0.0273，但绝对值仍仅 0.0898，说明
普通多轮提示没有可靠覆盖官方期望问诊动作，不能把“多问了几轮”解释为有效取证能力。

B0 是每案一条，B1 是每案四 persona；官方表对 session 等权平均。该表适用于工程 pilot
的方向性诊断，不提供置信区间、显著性结论或独立 judge 结论。当前 judge 与被评模型均为
Qwen3-4B，这可能带来自评偏差，正式论文实验应冻结独立且更强的 judge 并做人评校准。

## 6. 自定义过程指标

| 指标 | B0 | B1 |
|---|---:|---:|
| 轨迹数 | 20 | 80 |
| 平均客户问答轮 | 0.0000 | 4.9125 |
| 平均总 token | 394.35 | 6684.03 |
| 平均 memo 字符 | 374.75 | 212.40 |
| 结构化动作解析率 | 不适用（自由文本 memo） | 0.9894 |
| 修复/fallback 动作 | 20（B0 记录方式） | 5 |
| 强制 memo | 0 | 1 |
| 轨迹内精确重复提问 | 0 | 3 |

B1 共提出 393 个客户问题。全语料精确重复问题率为 0.1832，主要来自不同 persona/案件间
复用通用问法；更直接的轨迹内重复发生在 3/80 条轨迹。这些是 Phase 2 的停止风险门、
状态覆盖和重复问题 verifier 应优先解决的失败信号。

## 7. 未绕过的问题与修复

1. 初次本地 API 请求受系统 `HTTP_PROXY/ALL_PROXY` 影响返回 502：client 改为 loopback
   显式无代理，官方 evaluator 设置 localhost `NO_PROXY`，并新增回归测试。
2. 联合动作槽只有 160 token，提前提交的 memo 被截断并误作客户问题：动作预算提升为
   1536，截断 `write_memo` 永不转成客户消息，并记录 finish reason。
3. 个别 B0 memo 在 1536 token 仍重复直至截断：三类 memo prompt 增加 1200 中文字符上限
   与去重要求；问题案例 `case_cn_0023` 专项回归后从 1536-token 截断变为 267-token 正常停止。
4. 并发在线推理在固定 seed 下仍非逐字确定：保留失败的并发复现实验作为证据，最终使用
   单 worker 完整运行两次并通过 100/100 哈希比较，没有把相似措辞冒充严格复现。
5. LeCoDe 数据仍需机构身份、签署和审批；未绕过访问协议。这不影响本阶段 DLawBench
   pilot，但仍阻塞后续 LeCoDe 外部评测。

## 8. 证据与复现入口

- 配置：`configs/experiments/phase1_pilot.yaml`
- split：`data/splits/dlawbench_public30_phase1_seed42.json`
- 模型 manifest：`data/manifests/qwen3_4b_model.json`
- 选定运行 manifest：`runs/phase1/phase1_pilot_deterministic_seed42_a/manifest.json`
- custom metrics：`runs/phase1/phase1_pilot_deterministic_seed42_a/evaluations/custom_metrics.json`
- 官方指标：`runs/phase1/phase1_pilot_deterministic_seed42_a/evaluations/official_metrics.{md,json}`
- 复现证据：`runs/phase1/phase1_pilot_deterministic_seed42_b/evaluations/reproducibility.json`

关键产物 SHA-256：custom metrics
`b359351ed0b7d8551cb10db848e0864f151db720f98aa0032de6038495de0b7d`；官方 metrics JSON
`2bd93511e64470dd297c1e4364b74f79854437546a812a53faf1964d8dd71107`；复现证据
`42cefcd33bbe99a9ae71134ed87b2f131a3d417694ff6d50727636190a515506`。

## 9. Phase 2 入口

Phase 1 已满足实施方案的三个完成标准：20 案 × 4 persona 无崩溃、全量轨迹严格复现、
官方和自定义指标均可生成。下一阶段可以开始结构化 consultation state、冲突合并、
8–12 条种子技能、技能 operation/verifier、停止风险门以及 B2/B3；仍应把 public-30 标记为
工程 pilot，直到取得正式全量数据与领域元数据。
