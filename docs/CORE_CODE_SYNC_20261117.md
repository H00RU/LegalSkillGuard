# legal-skill-current 核心代码同步

本次按用户“那就同步”的要求，将当前唯一项目 `/home/yndx/hhy/legal-skill-current` 的核心代码补齐到 `H00RU/LegalSkillGuard` 的 `research/paired-interface-structural-transfer-20261116` 分支。同步源码不启动研究任务，不恢复M1、M2扩展、正式训练或冻结测试，整Goal仍未完成。

## 同步范围

- `legal_skill_guard/`：全部Python核心模块及随包许可证，包括58个配对接口模块、正式执行/训练实现、M2修订与停止条件。
- `experiments/`：全部Python实验入口、依赖文件及源审核锁；旧入口与旧方案保留为历史资产，不构成执行队列。
- `tests/`：全部Python测试及必要的既有测试夹具；上传测试不代表全部历史科学检查在当前源码下重新通过。
- `configs/`：当前本地配置；只同步代码/配置文件，历史TEST字样不代表重新授权测试。
- `pyproject.toml`、`uv.lock`、根目录冻结README、项目地图、Goal和交接文档，以及当前正式运行暂停、M2停止和数据曝光事实文件。

逐文件范围与SHA256/Git blob见 [CORE_CODE_MANIFEST_20261117.json](CORE_CODE_MANIFEST_20261117.json)。清单以本地当前字节为准；同步只补齐/更新所列文件，保留远端已有历史文件与证据，不把本地私有Git祖先整体上传。之前仅上传了M1可复现路径；本次补齐此前缺少的正式工作流及M2等模块。

## 获取与已有结果复现

```bash
git clone --single-branch --branch research/paired-interface-structural-transfer-20261116 https://github.com/H00RU/LegalSkillGuard.git
cd LegalSkillGuard
python3 -m venv .venv
.venv/bin/python -m pip install -r reports/two_method_followthrough_20261116/M1_evidence_20261117/requirements.txt
.venv/bin/python -m experiments.m1_replay_evidence
.venv/bin/python -m experiments.m1_replay_feasibility
```

两条复现命令只重放已封存证据，不连接执行器/教师、不重发有效请求。通用包依赖见 `pyproject.toml` / `uv.lock`，其他专项依赖见 `experiments/requirements_*.txt`。历史实验依赖的模型、官方数据归档、连续账本及其原始版本需要原资产；代码同步不等于所有历史运行环境或数据已公开。

## 科学状态与本地保留

M1自动程序改写原型已实现。原3个OE TRAIN来源的固定有限验证复用了18份响应、新增2调用/5576 tokens；诊断F1为1/3，但三臂完整正确均0/4，正分涉及既有源审unknown被断言为true，未建立源文语义保持的独有收益。当前M1版本停止扩展，M2两关未通过并继续停止。详见 [M1决定](../reports/two_method_followthrough_20261116/M1_FEASIBILITY_DECISION_20261117.md) 和 [M2决定](../reports/two_method_followthrough_20261116/M2_TWO_GATE_DECISION_20261117.md)。

原177参考、所有响应/失败/结果、连续账本12427条、原DEV/TEST曝光事实和源码快照继续保留。本次没有模型/教师调用，没有改写科学实现或重置账本。模型权重、全部历史缓存、177参考全集、完整SQLite账本、凭据和机器私有环境不在此次同步范围；已发布的最小证据、对应参考与账本索引继续可用。

根 `README.md` 是冻结历史文档；当前状态应从 `PROJECT_MAP.md`、`docs/CURRENT_GOAL.md`、`docs/NEW_CHAT_HANDOFF.md` 的最新段落进入。未修改 `main`，未覆盖原始失败或将暴露数据重新称作盲测。
