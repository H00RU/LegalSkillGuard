# Phase 0：环境与数据审计报告

生成时间：2026-08-07T17:31:16.239754+00:00
DLawBench revision：`9f6325f29f07b296fac110a6e1880bdd5d9ca538`
阶段结论：**工程、公开数据和 GPU 运行环境的 Phase 0 闭环通过；论文全量数据尚未满足正式主实验条件。**

## 1. 已完成事项

- 完整读取项目实施方案以及 DLawBench README、case schema、runner、environment、client、evaluator 和 metrics。
- 拉取官方 DLawBench，并以 commit 为目录创建只读原始数据快照。
- 官方 deterministic smoke test 通过；官方 release validator 通过；官方 7 项 metrics 可生成。
- 建立配置模板、机器可读环境/数据审计、最小数据可见性边界和泄漏测试。
- 原始数据、上游代码、运行产物和项目包分层保存。
- NVIDIA 驱动、CUDA Driver API 与真实 CUDA 核函数计算通过。
- LeCoDe 官方代码与申请协议已固定；数据访问边界和许可证约束已归档。

## 2. 环境审计

| 项目 | 实测结果 | 判定 |
|---|---|---|
| OS / Kernel | Linux-5.15.0-139-generic-x86_64-with-glibc2.31 | 可用 |
| 项目 Python | 3.11.15 (`/home/yndx/hhy/legal-skill-guard/.venv/bin/python`) | 通过；系统 3.8 已由项目级 3.11 替代 |
| CPU / RAM | 32 logical CPUs；见 `reports/artifacts/environment.json` | CPU 审计可用 |
| 磁盘 | 895.1 GiB free / 1006.36 GiB total | 充足 |
| CUDA toolkit | /usr/local/cuda-12.2；nvcc return code=0 | CUDA 12.2 工具链存在 |
| NVIDIA PCI device | detected=True | PCI 层检测到设备 |
| NVIDIA runtime | `nvidia-smi` return code=0；device nodes=['/dev/nvidia-caps', '/dev/nvidia-modeset', '/dev/nvidia-uvm', '/dev/nvidia-uvm-tools', '/dev/nvidia0', '/dev/nvidiactl'] | **通过** |
| 推理框架 | torch=2.8.0, transformers=4.56.2, vLLM=0.10.2 | **通过；Phase 1 已固定兼容版本** |

GPU 修复证据：NVIDIA A40 已绑定 `nvidia` kernel driver，`nvidia-smi`、CUDA Driver API 和设备节点均可用；独立 CUDA smoke test 已完成显存分配、主机/设备拷贝、核函数执行和结果校验。

### 2.1 LeCoDe 访问审计

| 项目 | 实测结果 | 判定 |
|---|---|---|
| 上游 revision | `36104863438bd61c6ea7072cc8c63dcacb074631` | 已固定 |
| 公开代码/协议快照 | `data/raw/lecode/36104863438bd61c6ea7072cc8c63dcacb074631`；16 files | 只读、可追溯 |
| 数据文件 | present=False | **申请制，未取得** |
| 使用条款 | CC-BY-NC-ND-4.0；non-commercial；no redistribution | 已记录 |

LeCoDe 的 2,956 条训练对话和 740 条测试对话不在公开 Git 仓库中。官方要求申请人、
机构邮箱、导师/负责人签名及数据方审批；这些身份与签署事项不能由自动化代理代填。
因此 Phase 0 已完成“来源、代码、协议和访问条件核验”，但未声称持有 LeCoDe 数据。
这不阻塞基于 DLawBench public-30 的 Phase 1 工程 pilot；会阻塞后续 LeCoDe 外部评测。

## 3. DLawBench 复现结果

| 验收项 | 结果 | 证据 |
|---|---|---|
| 上游 revision | `9f6325f29f07b296fac110a6e1880bdd5d9ca538` | `data/manifests/dlawbench_source.json` |
| 官方 smoke test | PASS | `reports/artifacts/dlawbench_smoke.log` |
| 官方 release validator | PASS | `reports/artifacts/dlawbench_validation.log` |
| 官方 metrics | PASS | `reports/artifacts/dlawbench_smoke_metrics.md` |
| 项目测试 | 23 passed in 0.14s | `reports/artifacts/pytest.log` |
| API / token 成本 | 0（全部使用 mock-lawyer、mock-client、mock-judge） | smoke log |

阶段运行耗时（秒）：`{"data_audit": 0.071, "environment_audit": 0.387, "official_metrics": 0.034, "official_smoke": 0.142, "official_validation": 0.033, "prepare_lecode_snapshot": 0.031, "prepare_snapshot": 0.031, "tests": 0.344}`。

## 4. 真实公开数据统计

| Jurisdiction | Cases | Case-persona cells | Facts | Disputed | Undisputed | Inquiry rubrics | Memo rubrics |
|---|---:|---:|---:|---:|---:|---:|---:|
| CN | 30 | 120 | 319 | 226 | 93 | 202 | 182 |
| US | 30 | 120 | 439 | 338 | 101 | 397 | 365 |
| Total | 60 | 240 | 758 | 564 | 194 | 599 | 547 |

中国法 30 案的每案分布：facts mean=10.6333、median=11.0、range=5–16；inquiry rubrics mean=6.7333、range=2–12；memo rubrics mean=6.0667、range=2–12。

四个 persona 均适用于每个底层案件：中国法公开集每类 30 个 case-persona cells；键为 `P_WD, P_WS, P_CS, P_CD`。完整 histogram、文本长度和字段出现次数在 `reports/artifacts/dlawbench_audit.json`。

## 5. 不能绕过的数据问题

### 5.1 论文语料与公开 release 不一致

论文/README 报告 264 个中国法与 197 个美国法案件；当前官方仓库、manifest 和 validator 实际只有 30 + 30。缺口为 CN=234、US=167。仓库唯一的 [issue #1](https://github.com/SKYLENAGE-AI/DLawBench/issues/1) 正在询问这一差异，尚无作者回复。因此：

- 不能把 public-60 实验写成论文 full-461 复现；
- 不能按原方案从 30 个中国法案件再切出约 211/53 的 train/test；
- 在取得全量数据前，public-30 CN 只能用于工程开发、小规模 pilot 和方法可运行性验证。

### 5.2 公开记录没有领域标签

JSONL、schema、case index 和 manifest 都没有 `domain` 字段。论文图可读取全量 264 个中国法案件的聚合领域计数，合计为 264，但不能映射到公开的 30 个 case ID。因此当前不能执行“按领域分层 split”或可信的跨领域实验。任何自动文本猜测领域都必须作为新标注并单独验证，不能冒充官方 metadata。

### 5.3 上游 Python 声明存在兼容性细节

DLawBench README/pyproject 声明 Python >=3.9，但 `scripts/metrics.py` 使用 `str | Path` 等 Python 3.10+ 语法。项目固定 Python 3.11.15，已经实际运行 metrics，避免依赖声明与真实语法不一致。

## 6. 数据可见性与泄漏控制

已实现 `legal_skill_guard/data_visibility.py`：

- lawyer 与 online state 只能读取 `id/jurisdiction/language/opening`；
- client simulator 只得到 `client_belief`，不读取 `court_record` 或 rubric，与官方 client prompt 的最小权限设计一致；
- evaluator 才能读取完整记录；
- 泄漏测试递归检查隐藏字段并使用真实中国法记录验证。

正式 split、训练教师权限和 acceptance pool 尚未实现，因为 Phase 0 不应提前生成一个在 30 案 public subset 上看似正式、实际上不可支撑论文协议的划分。

## 7. 失败样例与处置

1. 系统无 Git：已在工作区安装隔离的 Git 2.25.1，并用它固定上游 commit；没有改系统包。
2. 系统 Python 3.8 不满足项目/metrics：已安装隔离的 CPython 3.11.15 与 uv 环境。
3. GPU driver 曾不可用：根因为只有手工注入的旧用户态组件、缺少 kernel module；现已安装并加载 Canonical 570-server 计算栈，真实 CUDA 核函数验证通过。
4. 全量 DLawBench 未公开：已确认所有 branch/tag/release/Hugging Face 入口和公开 issue；没有用合成案件补齐。
5. domain 缺失：审计输出明确为 null；没有进行无依据分类。
6. LeCoDe 数据申请制：已固定公开代码与申请协议；没有绕过审批或抓取非公开对话。

## 8. 下一阶段进入条件

| 条件 | 当前状态 |
|---|---|
| 官方 smoke / validator / metrics | 通过 |
| 能读取中国法案件并生成机器统计 | 通过 |
| 原始数据只读、revision/hash 可追溯 | 通过 |
| 隐藏字段泄漏测试 | 通过 |
| GPU 可用于 4B–8B 基线 | **通过：A40 48 GiB，驱动与 CUDA 实算均验证** |
| LeCoDe 公开代码、许可与访问边界 | 通过；数据须由研究者完成机构申请 |
| 论文主实验所需全量 CN 数据或作者确认的正式公开协议 | **未通过，需上游数据/回复** |
| 领域分层所需 per-case metadata | **未通过，需上游标签或经验证的新标注** |

结论：Phase 0 的可执行工程目标和 GPU 前置条件已经完成；可以进入模型/推理后端冻结与 GPU 基线开发。全量数据和分层协议解决前，不应把 public-30 pilot 宣称为正式论文主实验。
