# 从作者代码到当前执行瓶颈：一个待验证改动

2026-10-28。按用户要求，优先直接改善EC/EV，不先铺开长控制。
使用师兄paper-ideation的接缝分析；以下是已经核查的研究依据，不是新增性能结果。

## 已确认的断点

已有技能正确要求保留独立条款、按资产值与限额取较小值，实际8B仍会漏项或复制限额。
第三版完整14次提案的自适应选择相对固定依赖组成，只有一次EV下发差异，EC差异为零。
第四版同父库反馈对照中，4正4负见证的新教师又改写了正确规则，80源完整准入拒绝，
两臂都保留父库，48后续TRAIN增益为零。继续改见证比例或抽象口号没有当前收益证据。

## 已读原始论文与实际实现

### AMD：给弱执行器具体行为示范

[Agent Memory Distillation](https://arxiv.org/abs/2608.07169)，2026-08-07，面向冻结4B--8B。
作者仓库固定commit `2895d10c07105432325b088f4803dc94a10003c9`。

- [builder.py/build_subtask_segments](https://github.com/taeilkim2465/agentic_memory_distillation/blob/2895d10c07105432325b088f4803dc94a10003c9/bfcl/common/memory/builder.py#L388)：从成功轨迹中保留具体调用形式，不只摘要原则。
- [store.py/format_for_prompt](https://github.com/taeilkim2465/agentic_memory_distillation/blob/2895d10c07105432325b088f4803dc94a10003c9/bfcl/common/memory/store.py#L200)：短说明配最多两条具体调用例子。主代理直接读取并核验文件SHA256为 `04489aa12d6b0196e55458c789786567476a80393e8fe339ea1c5033a1e3ff9d`。

借鉴的是具体行为表示，不是工具调用任务的headline收益。作者完整方法有分层记忆、
embedding及某些分支的额外模型调用，不搬入本项目。作者代码没有明确LICENSE，不能
称为MIT或直接复制；自行实现所需概念。其参数mask保留数字，法律金额绑定不能照搬。

### EmbodiSkill：先区分规则错误和没有遵循规则

[EmbodiSkill](https://arxiv.org/abs/2605.10332)，首发2026-05-11，v2为07-11，明确属于回溯工作。
作者commit `760126030eab1d33ec6a6f30988f0f1fb58df3a7`，MIT。

- [prompt.py的失败归因](https://github.com/air-embodied-brain/EmbodiSkill/blob/760126030eab1d33ec6a6f30988f0f1fb58df3a7/agentkit/skill/embodiskill_skill/prompt.py#L154)：要求引用当前技能原文，区分FAIL_SKILL与FAIL_EXECUTION。
- [EmbodiSkill.py/revise_manual](https://github.com/air-embodied-brain/EmbodiSkill/blob/760126030eab1d33ec6a6f30988f0f1fb58df3a7/agentkit/skill/embodiskill_skill/EmbodiSkill.py#L1146)：知识修订与执行提醒分开处理。

借鉴精确锚点及保护正确规则，不引入其独立执行附录/多次反思调用。其ALFWorld数字清洗
会破坏法律金额与条号，不能复制；找不到原文锚点时应不改，而不是转为允许改知识正文。

### SkillOpt：有界编辑及拒绝历史

[SkillOpt](https://arxiv.org/abs/2605.23904)，首发2026-05-22，亦为明确回溯。
作者commit `e2edfa9721ce41c98e50fa129da87cf1f53c2f7f`，MIT。

- [reflect.py](https://github.com/microsoft/SkillOpt/blob/e2edfa9721ce41c98e50fa129da87cf1f53c2f7f/skillopt/gradient/reflect.py#L265)：当前技能、实际执行上下文及此前编辑反馈一起参与局部反思。
- [skill_aware.py](https://github.com/microsoft/SkillOpt/blob/e2edfa9721ce41c98e50fa129da87cf1f53c2f7f/skillopt/optimizer/skill_aware.py#L61)：当前可选实现引入上述知识/执行归因。主代理已直接读完206行，文件SHA256为 `ea37beb95056ac52a61167153a2e05b05692d55fbe2b3bcfb039516801f0b418`。

可选当前实现不等于五月论文主机制已验证。借其有界修改，不搬入验证集、无条件slow
接受、独立附录运行层或失败回退。保留现有原生/完整输出门槛，不以一句“反思通过”准入。

## 当前只验证一个接缝

现有抽象规则假定弱模型能自行把原则编译为完整最终输出；真实轨迹已经显示这一步会失败。
候选改动是让单教师先区分知识缺陷与执行遗漏。已有正确规则原文保留，执行遗漏不再触发
同义改写，而是用极短、可复用的完整输出微示范教会具体动作。示范仍在原技能文本内，
不新增检索层、规划器、执行器、复核器、数值求解器或付费服务。

法律示范要表达两种执行行为：一个资产的具体条款与独立通配条款同时列出；金额低于
限额时绑定资产值，不把法条限额直接复制进答案。这些只是训练中已知的通用问题，不为
测试案件写例外、不复制训练案完整答案、不把抽象后的示范冒称新验证成功轨迹。

## 紧接的最小验证责任

1. 使用同一较强第三版实际B8库作为父库，避免只对空库取得收益就宣布修复。
2. 只用已释放TRAIN材料和原始真实成功/失败子回答，由现有授权教师生成一个候选。
   单库4096-token上限，operators为空，执行器仍独立判断法律并生成原EC/EV最终答案。
3. 调用前固定样本、教师输入、父库、候选预算、原始模型/解码及采用门槛；不扫格式或
   成功失败比例。优先复用既有按公开法域/时间分位选取的20来源40任务，而非按分数挑案。
4. 同案原生及完整输出F1、漏报/错误金额/多报、成本一起比较；候选首答保存后才评分。
   这是TRAIN开发中的组合改动有效性检验，不拆称两个成分各自的因果提升或未见泛化。
5. 有实际净收益才将学习规则融入新空起点完整连续学习。没有收益就保留该负结果，
   不因为文献看起来合理再开一轮长训练。当前尚未调用这名新教师或开始该新验证。

原v0.23、全部旧版与不利结果不覆盖。新的源案隔离主表和公平比较仍是完整目标的一部分，
但长对照此时后置；所有额外主方法/ACE/Text独立重复仍按用户决定暂缓。
