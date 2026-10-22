# Current legal skill-evolution goal

更新：2026-10-22 23:41 CST。本页是当前执行入口。此前523行运行索引逐字保存在
[历史快照](research/checkpoints/CURRENT_GOAL_before_ACEv4_20261022_2212.md)，
旧PID、观察会话和旧配置不能当作当前状态。

## 目标与用户边界

以现有单实例冻结Qwen3-8B证明技能在后续新来源与隔离TEST上的可复核净收益，
同时完成可信经验方法对比、独立学习、必要消融、技能内容/投递/管理分析及完整论文。
不是只监控、跑完八批或收集更多技能就算完成。法律任务和方法不预先锁死，但不因
单批裸分回退或对照较差就换任务。当前保留OpenExempt EC/EV。

用户最新补充：论文正文突出真实研究问题、方法与收益，不写成调试流水账；
必要的公平条件、成本及影响结论的局限放在恰当位置如实交代。若完整TRAIN对照表明
本方法或末库收益不够，则查根因、优化并以新Run ID重训，不把已跑完当成方法已定型。
调优只依据TRAIN；已看过的TEST不能继续充当反复调参后的未见测试。

不新增付费服务/模型/第二实例，不部署32B，不加fallback、答案修复、隐藏求解器或
无关框架。不挑案、改标注/评分、删不利对照、选旧好库或虚构单调/显著曲线。
不用验证集；已见TRAIN重放是优化。保留失败、实际调用成本与双盘备份。

## 已完成主方法

- 路径：`/media/sangfor/vdb/legal-skill-evolve`；
  用户入口：`/home/yndx/hhy/legal-skill-current`。
- Run：`legal_openexempt_closed_feedback_public_assets128_20261021_run03`，
  10月22日12:09:47自然完成128来源、8批各16来源、每源EC/EV两个任务及8次唯一发布。
- source方法`6896246`；四个主actor/scorer文件仍匹配原371绑定。
  当前整份工作树因ACE专属修订而不同，不能说原371所有文件仍逐字未变。
- 首答使用批前库，所有本批条件保存后才读标签/训练。批后回放不覆盖首答。
  是标签辅助的外部技能学习，不是参数更新或无标签TFGRPO。
- 完整原始成本1158次native/HTTP、7655443输入/3232344输出、全stop；
  15新教师响应，3232522输入/51361输出；失败候选在成本中。
- 末库7条/2486tokens，SHA
  `3387b5b450f4b9107c9738562fa224915bb4405ff329ca8f113fc05d0e9c76e7`。
  7次实际创建、14次记录更新、0删除/合并；支持接口不等于实际发生。
- 全112个B2–B8来源：对自身首次唯一B1库EC+0.85565、EV+9.39396pp。
  全96个B3–B8来源：EC+0.99826、EV+10.95961pp。单学习器TRAIN，不是TEST/显著性。
- B8首答EC83.90129/EV85.20585%，同案空库59.11954/59.96032%；
  本批后新WI技能不能说已经在更晚TRAIN新案验证。

| 批次 | 强空库EC/EV % | 在线EC/EV % | 批后记录/tokens |
|---|---:|---:|---:|
| B1 | 63.45/66.35 | 63.45/66.35 | 5/1591 |
| B2 | 68.71/64.51 | 83.68/74.45 | 6/1945 |
| B3 | 64.70/60.79 | 91.42/82.42 | 6/1945，NOOP |
| B4 | 54.95/57.17 | 83.85/79.84 | 6/2179 |
| B5 | 55.97/65.31 | 86.77/80.83 | 6/2182 |
| B6 | 56.31/67.72 | 84.60/83.44 | 6/2202 |
| B7 | 58.13/61.56 | 78.55/80.76 | 6/2223 |
| B8 | 59.12/59.96 | 83.90/85.21 | 7/2486 |

完整曲线、736条原HTTP重构、15教师/14候选/8发布的机制证据见
[当前证据表](../paper/evidence_and_completion_20261020.md)。
EC后续96案中80案实际指导与B1相同，只有16案改变；EV有75案改变。
这是覆盖与收益的观察分解，不是随机化因果消融，也不能把EC弱收益归因于天花板：
该区间EC原评分最大96.79%，本方法84.85%，仍有11.94pp空间。

## 当前真正运行的进程

### 唯一模型

`legal-qwen3-8b.service`，PID3613253/start446037091，engine3613750。
Qwen3-8B bf16 revision
`b968826d9c46dd6066d109eabc6255188de91218`；
vLLM0.10.2/xgrammar0.1.23，32768/8192，thinking开，temp0.6/topP0.95/topK20，
serverseed42，maxseq1，prefixcache关。控制venv不含xgrammar，别查错解释器。
23:30核到A40 27833/49140MiB、97%，同一模型没有替换。

### ACE v4 同一学习器接续

Run `legal_openexempt_ace_public_assets128_20261022_run03`，
unit `legal-openexempt-ace-public-assets128-20261022-run03.service`，
PID812509/start468900048，23:21:23启动；source修正`3dc28b5`。
[配置](../configs/openexempt_ace_public_assets128_20261022_run03.json)及其frozen：
380文件/50packages，已冻结与双盘保全。不能热改绑定源码/测试/协议。

v3 Run02在23:04:02安全停止，294native/114教师与1643成员两份终态档已保留。
不是模型退出，也不是因指标低停训。已核实适配层在解析失败时漏传公开输出给反思器；
上游将完整公开gen_response交给Reflector。v4仅补齐失败文本，原零分、答案与8192上限
不改，不恢复部分JSON、不猜ID或重试推理。该缺陷不能解释反馈前已保存的B3首答差距。

接续唯一最后完整B2：12条/1214tokens，SHA
`701ee9b2b2edaa8c48de2d13b187cd47cf0fb557c9fc6595c7a2b365bb095e52`。
1301原始制品逐字绑定；348个已完成前缀回答均无解析失败，故修正分支未触及该前缀。
恢复220个B1/B2原始生成、102教师及64个完整B3首答原始生成，总284origins。
B3全部96逻辑回答仅按同完整请求复用，路径/法律答案/错误/评分全部不变：
ACE61.53646/48.69296%，空库64.70486/60.79365%；两条EV截断保留零分。
旧B3的10native/12教师不导入，另计失败成本。不是新的独立seed重复。
23:40实际在B3第217案学习，累计292native/113教师，其中新增8native/11教师。
新B3反思是真实新调用；不以当前重答拟合代替新案成绩。

[修正及接续协议](research/OPENEXEMPT_ACE_FAILED_PUBLIC_TRACE_V4_20261022.md)。
当前观察session **1511**：B3唯一实际发布与32条TRAIN逐字匹配；
23:24:34开始、10月23日05:24:34为观察期限，过期不停止训练。
57953/65985/77174/49243/98184/64872等均完成，不能再轮询。
目标/终态制品优先，再核PID/start/argv；观察超时不构成重启理由。

### 静态TRAIN控制仅后台等待

新unit `legal-openexempt-fixed-static-train128-20261022-run02.service`，
PID821776/start468935458，是Bash等待，不是第二模型/推理。
[配置](../configs/openexempt_fixed_static_train128_20261022_run02.json)400文件/50packages，
零教师、256预测全部保存后才评分；实际原静态7条/2411tokens、SHA
`4809c3b2fe336a682ad36544f036206f158c0890adad4e87bde6eb4fa6502321`不变。

只在当前ACE全8批自然完成、保存终态后执行；Python仍独立验证完整主/ACE、同锁、
源码、模型和库。ACE失败不能开始模型调用。旧waiter705766已停，旧run01无运行目录。
同PID有意exec为Python是正常转换，不是进程被替换。
取消未来阶段应只停新静态unit；用户明确暂停时须同时考虑此排队阶段。

## 后续真实实验，不是已完成结果

23:30全部九份新配置当前源码/50packages匹配、均未启动。旧冻结文件保留，
不原地更新。source374为主/消融，380为ACE，375为文本构建；见commit`2d07f55`。

| 相对顺序 | 当前配置（configs/） | 未来教师累计上限 |
|---|---|---:|
| 静态控制后1 | openexempt_whole_bank_public_assets128_20261022_run01.json | 3381 |
| 2 | openexempt_first_commit_public_assets128_20261022_run01.json | 3413 |
| 3 | openexempt_closed_feedback_public_assets128_seed145_20261022_run02.json | 3445 |
| 4 | openexempt_ace_public_assets128_seed145_20261022_run04.json | 4997 |
| 5 | openexempt_closed_feedback_public_assets128_seed245_20261022_run02.json | 5029 |
| 6 | openexempt_ace_public_assets128_seed245_20261022_run04.json | 6581 |
| 7 | openexempt_trace2skill_text_public_assets128_seed45_20261022_run02.json | 7223 |
| 8 | openexempt_trace2skill_text_public_assets128_seed145_20261022_run02.json | 7865 |
| 9 | openexempt_trace2skill_text_public_assets128_seed245_20261022_run02.json | 8507 |

当前共享账本仍3349，历史预约不清零；未来扩额只在前序终态及保全后。
ACE145/245从空库用同v4算法；Trace2Skill是text-analysis/OpenExempt适配，
不是原工具式ReAct复现，不声称胜全部原方法。ExpeL/SkillCommit未量化复现。
不新增嵌入模型、模型服务或通用队列。

## 论文、统计与测试边界

[初稿v0.6](../paper/manuscript_v1_20261021.md)正文用研究问题、机制与真实收益组织，
旧v0.5全文保留；图1完整46个F1点及六条折线坐标不改，无平滑或虚构误差带。
矢量PDF和600dpi PNG在
`artifacts/research/learning_curves_20261022/Run03_B1_B8_prequential_final_publications/`。
师兄实验/图表skill负责实证结构，nature-paper核结论边界，不按模板虚构创新或五次重复。

最终矩阵16arms、10主要EC/EV对比、4次要消融对比，128来源为独立单位。
3个实际独立学习库不是384个独立案例。配对source bootstrap20000/PCG64seed2026102192，
区间以实际学得库和固定seed45评价为条件。独立学习变异与损害/成本另报。
首次真实TEST预测之前，所有实际末库、完整矩阵、统计与评价源码都必须冻结。
隔离评价worktree `.venv/evolution-control-20261020.qLon9T`当前8a55e73；
**还需加入此次接续来源校验和同步v4 actor，不能原样视作TEST已可启动。**
这项CPU实现不需要等待ACE完成，也不授权读取TEST。

TEST packet SHA
`6a5f72559a021d425d5b6ee41ba19f1a8e10d7da1ac11e0725d469a281c5164d`，
HFrev842cedec770ff2e45636fb5cb526ba0708ceb908、IDs1000001–1000128。
仅字节哈希可核；语义、标签、预测和结果未读。不是官方Advanced/OOD、真实律师或
广泛法律能力证明。主八批有效不等于已胜成熟对照/可直接投稿。

## 下一步动作与保全

1. 继续同一个1511观察与原812509模型服务链，B3发布后审计全部32TRAIN、实际ADD/
   计数、失败文本确实进入教师及只新增调用成本；不看部分新案来挑库。
2. GPU运行时完成隔离评价的接续来源闸门与v4 actor同步；只做有针对性的合成检查，
   不跑真实TEST或重做全量资格测试。
3. 完成v0.6数字/图形/链接核对及当前全部代码、前缀、图表、论文/索引增量双盘保全。
4. 下一小时00:30核当前380、九新配置、静态400、原模型/新ACE/新waiter句柄及大方向。
   当前小时证据为hourly2330_ACEv4_Run03_actual380_nine_rebased_profiles_static400_original_model_and_direction_20261022.json。
5. 成熟ACE及静态结果齐后判断主方法是否需要根因优化重训，再执行既定重复/消融与
   文本归纳对比；最终完成可信论文，不把当前八批当作整个goal完成。
