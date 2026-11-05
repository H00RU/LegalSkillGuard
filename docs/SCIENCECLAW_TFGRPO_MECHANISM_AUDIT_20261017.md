# 法律技能学习与公开参考实现：机制边界核对

核对日期2026-10-17。本文是开发研究记录，不是方法效果、SOTA复现或论文主张。
没有新增模型、教师调用、训练标签重写、候选准入或运行中改动。不能据此宣称已解决根因。

## 纠正此前的过度归因

“教师不能生成/交付技能”不符合当前实际记录。至少复制权限准则已完整生成、单次交付，
并准确写出保留已有副本不等于获准新建副本。律师仍有违背该区分的公开回答。
生成、交付、行为遵循与新案收益是不同命题，后一环失败不能倒推前一环完全不存在。
当前教师确实得到完整已见TRAIN原文、Gold、最新own回答及成员差分；不能把缺Gold说成主要已证根因。

## TF-GRPO并非无答案不可学习，也不保证弱模型必获益

原论文：https://arxiv.org/html/2510.08191 ，§2与§3.2、表5。
方法按多条rollout的相对结果提炼语义经验。原文也报告不给标准答案的版本，说明无答案路线有实证依据。
网页任务的该消融pass@1为66.7，与ReAct相同；pass@3为78.4，对照74.5。
QwQ-32B的TF-GRPO pass@1为25.5，低于本身ReAct27.5；作者也指出效果依赖底层能力。
这些是作者指定任务/预算上的报告，不是当前8B法律任务的预测，更不能用来宣布必须换模型。
相对比较有价值的前提是能辨别有效行为及其适用条件，不是机械取四条中最高的两条。

## ScienceClaw需要区分版本和可编辑对象

同名其他作者仓库不能混用。本次核对的是beita6969的公开ScienceClaw。

旧评测数据说明 https://github.com/beita6969/ScienceClaw-EvalData/blob/master/README.md
列20学科，法律为LegalBench。当前论文 https://arxiv.org/html/2610.08691
列23学科，FoR48为ContractNLI合同-命题证据排序，跨源为ACORD，主要报告mAP。
不能将其mAP与本项目三类+原Gold-NN硬集合F1/严格联合直接比较。

当前公开方法同时进化Skills与typed executable Operators，从重执行验证的失败-成功修复中抽象能力，
不是仅向冻结律师加入一段建议。源重放与独立验证选择也是方法组成。
§C.5明确load_train暴露源角色带标签样例，待评价样例的标签不暴露。
源码 https://github.com/beita6969/ScienceClaw/blob/main/packages/scienceclaw/scilib/contracts.py
提供train_annotations/evidence_spans、ContractModel.fit、LR与LightGBM训练接口。
这说明“待答样例不提供答案”不等于“整个学习和工具链无监督”。接口存在本身不证明每次作者实验都调用了它。

真实候选准入见
https://github.com/beita6969/ScienceClaw/blob/main/packages/scienceclaw/scienceclaw/evolution/validation.py
的ValidationGate、feasible、improves。当前Goal禁止效果准入和最佳库回滚，不因参考工作使用就暗中加入。
当前论文§F.4的编排模型为Qwen3.5-27B，主进化模型GPT-5.4；不是本项目同一个8B配置的受控证明。

## FlowSteer不能与TF-GRPO直接画等号

本次公开代码 https://github.com/beita6969/FlowSteer/blob/main/train_interactive.py
明确get_peft_model/LoRA、compute_grpo_loss、optimizer.step；正确性调用传ground_truth或代码测试。
轨迹奖励 https://github.com/beita6969/FlowSteer/blob/main/src/interactive/trajectory_reward.py
将外部correctness纳入结构条件满足后的奖励。
不能据此否定用户参与过的内部/历史版本，但该具体TF-GRPO版本尚未定位，不能假装已经审阅。

## 本项目下一动作需要什么证据

本轮B2首遇全部24回答已完成。复制准则范围内1修正1损害；范围外8修正18损害。
实际返回原文、源/命题键和原作者评分核验通过。说明局部知识到可靠全局行为仍有断点，
不证明唯一串题机制或把技能移到某个提示字段就必然有效。

R2实际UPDATE1、CREATE11，12条覆盖13命题。全文与Gold不缺、1478准则tokens并未超容量。
先观察完整16源R2结果。若继续大幅配对损害，按Goal安全停止整轮，不挑最好库、不偷偷补答案。

可具体追查的学习窗口：当前24条实际own历史只提供16个current-parent最新答；
8个历史空库own答和R1学后答没有同时送入R2教师，虽然库版本与编辑历史有保存。
修补候选是将真实own版本变化忠实交付教师，保留所有成功/失败及原始来源，不加入新裁判/准入器。
这是信息路径假设，不是收益保证。旧历史反馈已有实现且其工具状态变化，不能宣称历史对比从未试过，
也不能用其负结论彻底排除固定无工具条件下的更新反馈。

机制分析的接缝测试在这里仅用于审查“比较信号可转化为可执行经验”这条假设。
不以包装、命名、固定创新点数量或新多智能体层代替指标证据。
