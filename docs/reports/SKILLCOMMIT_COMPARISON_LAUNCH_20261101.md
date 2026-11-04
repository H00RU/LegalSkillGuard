# SkillCommit同设置对照启动记录

## 当前状态更新：18:15:30 CST，run02已启动

当前Run ID为`legal_openexempt_skillcommit_paper_public_assets128_seed45_20261101_run02`，
服务`legal-skillcommit-paper-20261101-run02.service`，配置同名run02.json。
该版本648绑定文件已双盘保全；11项小型算法检查及静态检查通过。
正常完成构建后自动固定末库，接续原128来源/256任务的冻结测试。

run01在首案阶段操作员停止，已完整保存失败与终态原件。原因是修正防泄漏的
不合理额外限制：公共schema字段名及法条已有的类别应允许进入可复用操作说明；
仍禁止案件特有标签/答案。这不是根据测试分数或种子选择结果。
原主方法379绑定再次全核未变。run01实际5次8B、3次教师，教师63145输入及2100
输出tokens；这些已作为retired_implementation_attempt绑定到run02配置，成本不归零。
run02冷起步，不导入run01的任何回答、教师输出或技能。run01未生成任何TEST。

以下保留最初run01启动历史，不能代替当前run02真实进度。

## 最初启动历史

2026-11-01 18:05:30 CST启动。用户授权：固定现有方法，补最近直接同任务方法比较。

## 实际完成

- 独立实现SkillCommit论文三阶段、逐案在线学习、EC/EV独立层级、残余修补保留、
  范围缩小后的再次重放以及最终冻结评价，不调用我们的学习或准入控制器。
- 10项小型无模型算法检查通过；新模块静态检查通过。没有额外全量资格运行。
- 语义短名单编码器BGE-base-en-v1.5已下载并核验6个文件hash，CPU768维编码实测
  正常。原文text-embedding-3-small不可用的替换、测试检索和pass二值化均在协议披露。
- 646文件源码/数据清单冻结并双盘归档。原主方法379文件逐一核查无变化。
- systemd用户服务已启动，初始主PID528603。原8B服务958223未变。18:06:45前后
  进度处于第一案181/EC真实推理，GPU利用率98%；这不是新增成绩。

## 文件与运行

Run ID：`legal_openexempt_skillcommit_paper_public_assets128_seed45_20261101_run01`

配置：`configs/openexempt_skillcommit_paper_public_assets128_seed45_20261101_run01.json`

冻结：同名`.frozen.json`，646个绑定文件。源归档位于两处独立盘：
`/media/sangfor/vdb/legal-skill-backups/`与`/home/yndx/hhy/legal-skill-rootdisk-backups/`，
名称均为`<Run ID>-source.tar.gz`。公开编码器权重不重复收入研究归档，由配置固定公开
revision、文件hash与原始下载位置。

实现：`experiments/openexempt_skillcommit.py`和`legal_skill_guard/learning/skillcommit.py`。

协议：`docs/research/OPENEXEMPT_SKILLCOMMIT_PAPER_ADAPTATION_20261101.md`。

服务：`legal-skillcommit-paper-20261101-run01.service`。

## 自动顺序及后续检查

同TRAIN128源逐案构建，按原8批汇总进度。构建结束写`publications/final.json`及
`build_completion.json`，固定真实末库，然后自动预测同TEST128源的256个任务。
全部预测保存后才统一评分。终态写独立`completion.json`和双盘终态归档。
不重跑主方法、旧十条件或额外独立重复，不覆盖现有主表和原统计族。

进度看Run目录`progress.json`；逐批看`batch_summary.json`；实际准入/抽象/split看
`events/`及`replays/`；真实下发看`forecasts/`和`TEST_delivery/`；教师与原生输出
分别在`teacher/`、`native/`。这份报告是启动记录，不能代替真实运行阶段。

比较目的是取得真实排序及收益/开销证据，不以是否超过我们的方法决定停止、删改
或保留。本次为既有已查看TEST上的新增方法比较，不称全新未见确认性实验。
