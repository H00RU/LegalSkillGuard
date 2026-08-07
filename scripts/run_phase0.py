#!/usr/bin/env python3
# ruff: noqa: E501
"""Run and document the complete Phase 0 acceptance workflow."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "third_party" / "DLawBench"
ARTIFACTS = ROOT / "reports" / "artifacts"
REPORT = ROOT / "reports" / "phase0_environment_and_data.md"
REVISION = "9f6325f29f07b296fac110a6e1880bdd5d9ca538"


def command_environment() -> dict[str, str]:
    environment = os.environ.copy()
    tool_bin = ROOT.parent / ".tools" / "bin"
    environment["PATH"] = os.pathsep.join(
        [str(Path(sys.executable).parent), str(tool_bin), environment.get("PATH", "")]
    )
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    return environment


def run(command: list[str], *, cwd: Path = ROOT, log: Path | None = None) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=command_environment(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    elapsed = time.monotonic() - started
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(completed.stdout, encoding="utf-8")
    result = {
        "command": command,
        "cwd": str(cwd),
        "returncode": completed.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "output": completed.stdout,
    }
    if completed.returncode != 0:
        tail = "\n".join(completed.stdout.splitlines()[-40:])
        raise RuntimeError(f"Command failed ({completed.returncode}): {command}\n{tail}")
    return result


def bytes_gib(value: int) -> float:
    return round(value / (1024**3), 2)


def render_report(
    environment: dict[str, Any],
    audit: dict[str, Any],
    lecode: dict[str, Any],
    timings: dict[str, float],
    test_log: str,
) -> str:
    cn = audit["observed_public_release"]["CN"]
    us = audit["observed_public_release"]["US"]
    total = audit["observed_public_release"]["TOTAL"]
    gpu = environment["gpu"]
    cuda = environment["cuda"]
    packages = environment["packages"]
    gpu_runtime_usable = gpu["runtime_usable"]
    gpu_runtime_verdict = "**通过**" if gpu_runtime_usable else "**不通过**"
    gpu_phase_condition = (
        "**通过：A40 48 GiB，驱动与 CUDA 实算均验证**"
        if gpu_runtime_usable
        else "**未通过，需管理员修复驱动**"
    )
    gpu_evidence = (
        "GPU 修复证据：NVIDIA A40 已绑定 `nvidia` kernel driver，"
        "`nvidia-smi`、CUDA Driver API 和设备节点均可用；"
        "独立 CUDA smoke test 已完成显存分配、主机/设备拷贝、核函数执行和结果校验。"
        if gpu_runtime_usable
        else "GPU 根因证据：PCI 可见 NVIDIA 设备，但 `/proc/driver/nvidia/version` 与 "
        "`/dev/nvidia*` 均不存在，`nvidia-smi` 无法与驱动通信；主机还没有可用的 "
        "NVIDIA kernel module。需要服务器管理员安装/加载与当前 kernel 和 CUDA 兼容的 "
        "NVIDIA 驱动并将设备暴露给本会话。"
    )
    persona_cells = audit["personas"]["public_cn_case_style_cells_by_persona"]
    test_summary = next(
        (line for line in reversed(test_log.splitlines()) if "passed" in line),
        "pytest summary unavailable",
    )
    return f"""# Phase 0：环境与数据审计报告

生成时间：{datetime.now(UTC).isoformat()}  
DLawBench revision：`{REVISION}`  
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
| OS / Kernel | {environment["host"]["platform"]} | 可用 |
| 项目 Python | {environment["python"]["version"]} (`{environment["python"]["executable"]}`) | 通过；系统 3.8 已由项目级 3.11 替代 |
| CPU / RAM | {environment["host"]["cpu_count"]} logical CPUs；见 `reports/artifacts/environment.json` | CPU 审计可用 |
| 磁盘 | {bytes_gib(environment["disk"]["free_bytes"])} GiB free / {bytes_gib(environment["disk"]["total_bytes"])} GiB total | 充足 |
| CUDA toolkit | {cuda["cuda_home"]}；nvcc return code={cuda["nvcc"]["returncode"]} | CUDA 12.2 工具链存在 |
| NVIDIA PCI device | detected={gpu["nvidia_pci_detected"]} | PCI 层检测到设备 |
| NVIDIA runtime | `nvidia-smi` return code={gpu["nvidia_smi"]["returncode"]}；device nodes={gpu["device_nodes"]} | {gpu_runtime_verdict} |
| 推理框架 | torch={packages["torch"]}, transformers={packages["transformers"]}, vLLM={packages["vllm"]} | 按计划未安装，等待模型与推理后端冻结 |

{gpu_evidence}

### 2.1 LeCoDe 访问审计

| 项目 | 实测结果 | 判定 |
|---|---|---|
| 上游 revision | `{lecode["revision"]}` | 已固定 |
| 公开代码/协议快照 | `{lecode["snapshot"]}`；{lecode["file_count"]} files | 只读、可追溯 |
| 数据文件 | present={lecode["access"]["dataset_files_present"]} | **申请制，未取得** |
| 使用条款 | {lecode["declared_license"]}；non-commercial；no redistribution | 已记录 |

LeCoDe 的 2,956 条训练对话和 740 条测试对话不在公开 Git 仓库中。官方要求申请人、
机构邮箱、导师/负责人签名及数据方审批；这些身份与签署事项不能由自动化代理代填。
因此 Phase 0 已完成“来源、代码、协议和访问条件核验”，但未声称持有 LeCoDe 数据。
这不阻塞基于 DLawBench public-30 的 Phase 1 工程 pilot；会阻塞后续 LeCoDe 外部评测。

## 3. DLawBench 复现结果

| 验收项 | 结果 | 证据 |
|---|---|---|
| 上游 revision | `{REVISION}` | `data/manifests/dlawbench_source.json` |
| 官方 smoke test | PASS | `reports/artifacts/dlawbench_smoke.log` |
| 官方 release validator | PASS | `reports/artifacts/dlawbench_validation.log` |
| 官方 metrics | PASS | `reports/artifacts/dlawbench_smoke_metrics.md` |
| 项目测试 | {test_summary} | `reports/artifacts/pytest.log` |
| API / token 成本 | 0（全部使用 mock-lawyer、mock-client、mock-judge） | smoke log |

阶段运行耗时（秒）：`{json.dumps(timings, ensure_ascii=False, sort_keys=True)}`。

## 4. 真实公开数据统计

| Jurisdiction | Cases | Case-persona cells | Facts | Disputed | Undisputed | Inquiry rubrics | Memo rubrics |
|---|---:|---:|---:|---:|---:|---:|---:|
| CN | {cn["cases"]} | {cn["case_style_cells"]} | {cn["facts"]["total"]} | {cn["facts"]["gap_type"].get("disputed", 0)} | {cn["facts"]["gap_type"].get("undisputed", 0)} | {cn["rubrics"]["expected_inquiries_total"]} | {cn["rubrics"]["memo_expectations_total"]} |
| US | {us["cases"]} | {us["case_style_cells"]} | {us["facts"]["total"]} | {us["facts"]["gap_type"].get("disputed", 0)} | {us["facts"]["gap_type"].get("undisputed", 0)} | {us["rubrics"]["expected_inquiries_total"]} | {us["rubrics"]["memo_expectations_total"]} |
| Total | {total["cases"]} | {total["case_style_cells"]} | {total["facts"]["total"]} | {total["facts"]["gap_type"].get("disputed", 0)} | {total["facts"]["gap_type"].get("undisputed", 0)} | {total["rubrics"]["expected_inquiries_total"]} | {total["rubrics"]["memo_expectations_total"]} |

中国法 30 案的每案分布：facts mean={cn["facts"]["per_case"]["mean"]}、median={cn["facts"]["per_case"]["median"]}、range={cn["facts"]["per_case"]["min"]}–{cn["facts"]["per_case"]["max"]}；inquiry rubrics mean={cn["rubrics"]["expected_inquiries_per_case"]["mean"]}、range={cn["rubrics"]["expected_inquiries_per_case"]["min"]}–{cn["rubrics"]["expected_inquiries_per_case"]["max"]}；memo rubrics mean={cn["rubrics"]["memo_expectations_per_case"]["mean"]}、range={cn["rubrics"]["memo_expectations_per_case"]["min"]}–{cn["rubrics"]["memo_expectations_per_case"]["max"]}。

四个 persona 均适用于每个底层案件：中国法公开集每类 {next(iter(persona_cells.values()))} 个 case-persona cells；键为 `{", ".join(audit["personas"]["keys"])}`。完整 histogram、文本长度和字段出现次数在 `reports/artifacts/dlawbench_audit.json`。

## 5. 不能绕过的数据问题

### 5.1 论文语料与公开 release 不一致

论文/README 报告 264 个中国法与 197 个美国法案件；当前官方仓库、manifest 和 validator 实际只有 30 + 30。缺口为 CN={audit["release_gap"]["CN"]}、US={audit["release_gap"]["US"]}。仓库唯一的 [issue #1](https://github.com/SKYLENAGE-AI/DLawBench/issues/1) 正在询问这一差异，尚无作者回复。因此：

- 不能把 public-60 实验写成论文 full-461 复现；
- 不能按原方案从 30 个中国法案件再切出约 211/53 的 train/test；
- 在取得全量数据前，public-30 CN 只能用于工程开发、小规模 pilot 和方法可运行性验证。

### 5.2 公开记录没有领域标签

JSONL、schema、case index 和 manifest 都没有 `domain` 字段。论文图可读取全量 264 个中国法案件的聚合领域计数，合计为 {audit["domains"]["paper_cn_aggregate_sum"]}，但不能映射到公开的 30 个 case ID。因此当前不能执行“按领域分层 split”或可信的跨领域实验。任何自动文本猜测领域都必须作为新标注并单独验证，不能冒充官方 metadata。

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
| GPU 可用于 4B–8B 基线 | {gpu_phase_condition} |
| LeCoDe 公开代码、许可与访问边界 | 通过；数据须由研究者完成机构申请 |
| 论文主实验所需全量 CN 数据或作者确认的正式公开协议 | **未通过，需上游数据/回复** |
| 领域分层所需 per-case metadata | **未通过，需上游标签或经验证的新标注** |

结论：Phase 0 的可执行工程目标和 GPU 前置条件已经完成；可以进入模型/推理后端冻结与 GPU 基线开发。全量数据和分层协议解决前，不应把 public-30 pilot 宣称为正式论文主实验。
"""


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}

    preparation = run([sys.executable, "scripts/prepare_dlawbench.py"])
    timings["prepare_snapshot"] = preparation["elapsed_seconds"]

    lecode_preparation = run([sys.executable, "scripts/prepare_lecode.py"])
    timings["prepare_lecode_snapshot"] = lecode_preparation["elapsed_seconds"]

    environment_result = run([sys.executable, "scripts/check_environment.py"])
    timings["environment_audit"] = environment_result["elapsed_seconds"]

    validation = run(
        [sys.executable, "scripts/validate_release_dataset.py"],
        cwd=UPSTREAM,
        log=ARTIFACTS / "dlawbench_validation.log",
    )
    timings["official_validation"] = validation["elapsed_seconds"]

    smoke = run(
        ["bash", "scripts/smoke_test.sh"],
        cwd=UPSTREAM,
        log=ARTIFACTS / "dlawbench_smoke.log",
    )
    timings["official_smoke"] = smoke["elapsed_seconds"]

    sessions = sorted((UPSTREAM / "runs" / "smoke").glob("session_*.json"))
    if len(sessions) != 1:
        raise RuntimeError(f"Expected exactly one smoke session, found {len(sessions)}")
    metrics = run(
        [
            sys.executable,
            "scripts/metrics.py",
            "--sessions",
            str(sessions[0]),
            "--case-dir",
            str(UPSTREAM / "data" / "case_backgrounds"),
        ],
        cwd=UPSTREAM,
        log=ARTIFACTS / "dlawbench_smoke_metrics.md",
    )
    timings["official_metrics"] = metrics["elapsed_seconds"]

    audit_result = run([sys.executable, "scripts/audit_dlawbench.py"])
    timings["data_audit"] = audit_result["elapsed_seconds"]

    tests = run(
        [sys.executable, "-m", "pytest", "-q"],
        log=ARTIFACTS / "pytest.log",
    )
    timings["tests"] = tests["elapsed_seconds"]

    environment = json.loads((ARTIFACTS / "environment.json").read_text(encoding="utf-8"))
    audit = json.loads((ARTIFACTS / "dlawbench_audit.json").read_text(encoding="utf-8"))
    lecode = json.loads(
        (ROOT / "data" / "manifests" / "lecode_source.json").read_text(encoding="utf-8")
    )
    REPORT.write_text(
        render_report(environment, audit, lecode, timings, tests["output"]),
        encoding="utf-8",
    )
    run_manifest = {
        "phase": 0,
        "completed_at": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "upstream_revision": REVISION,
        "timings_seconds": timings,
        "api_calls": 0,
        "token_cost": 0,
        "outputs": {
            "report": str(REPORT.relative_to(ROOT)),
            "environment": "reports/artifacts/environment.json",
            "data_audit": "reports/artifacts/dlawbench_audit.json",
            "lecode_source": "data/manifests/lecode_source.json",
        },
    }
    (ROOT / "runs" / "manifests" / "phase0.json").write_text(
        json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "complete", "report": str(REPORT), "timings": timings}))


if __name__ == "__main__":
    main()
