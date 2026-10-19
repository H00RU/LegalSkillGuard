# 当前Goal执行索引

更新：2026-10-20 03:55 Asia/Shanghai。Goal active，未完成，无外部阻塞。
本页仅作续接入口。真实状态必须亲核systemd/PID、原始工件，不能仅信游标。
本轮是实质progress：完整核两次B2拒绝、实际B3新案与真实MERGE提案；没把提案当发布。

## 完整目标和用户有效边界

让同一冻结8B因可管理、可进化的技能，在后续新案和最终隔离TEST上强于同工具/
同推理预算强空库和可信成熟经验方法，形成可靠论文证据。法律任务、主方法仍开放；
不能把跑完当前小试或某个好点缩成Goal成功。OpenExempt+重放本身不是创新，已有
SkillCommit，最终贡献仍须真实机制和对照支撑。

- 不另设验证集；TRAIN重放/准入是训练优化，不是独立验证或泛化证明。
- 训练标签辅助已获授权。新批三臂全部预测后才读其Gold，教师无未来案件/答案。
  官方TEST未打开；最终冻结方法/库后才评，不按测试挑库或改方法。
- 每批核真实教师CRUD、拒绝/发布、父子hash、token、送达/调用及损益。数量增长、
  指导看似合理和文字送达不是收益证明；缓存函数没调用继续记0，不为计数强制调用。
- 数据规模须够，法律意义/覆盖与合理迁移要明确。聚焦任务不等于无效，但不能
  把一个小合成任务泛化为通用法律能力。不同难度裸批次不要求机械单调。
- 不新增付费服务/模型/32B/第二实例，不恢复客户路由。不加fallback、答案修补、
  Gold solver推理工具或无关框架，不选好案/旧好库/改评分造提升。失败/成本全保留。
- 自主推进，师兄paper-ideation与paper-experiments-appendix用于失效假设、公平
  对照和证据边界；不采用固定三创新、隐瞒借鉴或预设好数字。每个新Goal轮完整读。
- 每小时以实际时钟复核。**最近03:28:18已实际自检，下次04:28**。主训练独立于
  对话；没有声称另建了能自动唤醒模型的提醒产品。

用户追加要求、完整小时记录见[生效补充](research/GOAL_ADDENDUM_SKILL_EVOLUTION_20261019.md)。

## 当前唯一live主训练

- Run `legal_openexempt_official_sampling_online_20261020_run01`。
- unit `legal-openexempt-official-sampling-20261020-run01.service`，原PID3085974，
  01:52:27启动，03:50:36亲核仍同PID active；B3新案已于03:49:49完整评分。
  03:54:13 progress为B3候选1重放，91 native/4教师、11次跨阶段同wire复用，
  46号案。不能把观察超时或观察者正常退出当主训练停止理由。
- progress `runs/<run>/progress.json`；日志
  `artifacts/research/openexempt_mechanism_20261019/official_sampling_run01.log`。
- config `configs/openexempt_official_sampling_online_20261020_run01.json`及frozen.json；
  源码6eb3302，158绑定文件。活跃Run不热改源/协议/输入/初库；终态保全后再变。
- 同一Qwen3-8B PID3889231，engine3889870，A40约26GB/49GB、97–98%忙；
  权重b968826d9c46dd6066d109eabc6255188de91218，127.0.0.1:8000/v1。
- 三臂统一T.6/P.95/K20、seed45、thinking ON、8192 completion/32768 context。
  官方min_p0默认已核。没有切成非思考、没有重启服务或换模型。
- 24来源、48派生EC/EV任务、6批各4来源。45–52旧未查询来源原文/源键保留；
  seed2026102002补53–68，排除所有旧开发source keys，未按结果重采样。
  B1=45–48，B2=49–52，B3=53–56已反馈；B4=57–60、B5=61–64、B6=65–68尚未反馈。
  packet SHA c6dc406906afcbc563ac4d038453aa9ab47590217d048cae9b9bfa5b88293aca。
- 启动用blind C0，7条/40函数/3462tokens，不是旧训练C1；160源/数据/清单成员
  双盘逐字节核验。14必要CPU边界检查0.24s完成，没新造测试模块。
- 原始模型行为/数学工具/原评分保留。只加载ALL和给定AE法域技能；公开引用用
  可读ASCII citation（§写section），无旧L编号fallback。推理不给私有category/
  applicable_exemptions或solver。EC/EV各自start2，EV没有Gold EC。
- 协议：[官方采样六批](research/OPENEXEMPT_OFFICIAL_SAMPLING_20261020.md)。

## 已经真实完成的指标，不扩大解释

原生逐案宏F1，百分数。B1 online=frozen，在线进化效应为0。

|新案批次|空库EC/EV|冻结C0 EC/EV|在线EC/EV|
|---|---|---|---|
|B1|80.83 / 65.28|72.01 / 69.44|72.01 / 69.44|
|B2|42.08 / 54.79|46.04 / 52.08|64.79 / 50.57|
|B3|67.92 / 45.83|72.08 / 69.58|85.83 / 77.08|

B2对空库EC+22.7083pp、EV-4.2262pp，两项均值+9.2411pp；对C0均值+8.6161pp。
这是真实分类迁移，但EV仍负，不是全方法已稳定成功。B2全输出EV为empty56.4354/
frozen52.4242/online51.2121%。24次物理回答全stop、无协议/动作错误、真实存储调用0。
累计12来源：empty63.6111/55.3009%，online74.2130/65.6978%，frozen63.3796/63.7037%。
online对C0 EC+10.8333pp、EV仅+1.99405pp，两项均值+6.41369pp；不掩盖EV小幅。
这不是正式规模、显著性、成熟方法胜利或官方TEST。

**B3增益边界**：对empty EC+17.9167pp/EV+31.25pp；对C0 +13.75/+7.5pp。
对C0全部增益集中53号（EC25→80、EV40→70），另外54–56都平，非均匀跨案改善。
53_EV empty写V<=700/V<=27900，非法数值程序按原规则0分，不修补/重答。
去掉该案的敏感性仅作诊断：其余三案online=C0 EV79.4444%，empty61.1111%。
53_EV online正确claim4对C0的2，仍把住宅单项27900写成55800；未解决所有问题。
B3共24逻辑/20物理回答（AZ/IL的4条online与C0同wire），20全stop、1空库动作错，
137352prompt/43582completion，真实存储调用0。此前说9/24物理进度已向用户澄清：
24是逻辑/最大生成数，实际20，不当独立重复。66个B3工件已双盘逐成员核验。

**实际发布C1**：B1教师UPDATE3+CREATE3，将Fed/OR/WI部分拆成EC与EV作用域，
并修700单项、OR400残余、WI车辆转用额度。新增不是三个新函数。
bankSHA b1c4fb26a715558ad27e8c48d253b0b08e95be928efef7df379a787d19b09c0a，
10条/40函数/4008tokens。仅已见TRAIN重放81.0417/71.1012%，全EV73.1424%；
5好1坏2平，EV TP17→19、FP4不变。45_EV仍重复两claim，48_EV退步，全部保留。
B1共22物理/1教师（156965prompt/51141completion；教师45682/6024、110.313s），
两条全wire未变重放复用，不当独立成功。78工件双盘保全；B2前向75工件亦保全。

**B2候选1已拒绝**：教师UPDATE7，10条/40函数/3998tokens，bankSHA
32fcb3a0a149a1cbddcf19a55ace2906e861efa6b15dd8ed1f9c98b5b71b9233。
修车辆单项4450/3000、火器1000、通用条款/资产清单和重复；教师66680input/
6180output、97.746s。16次物理重放后，当前TRAIN EC64.7917→52.5%、
EV50.5655→60.625%；旧B1 EC81.0417→74.5833%、EV71.1012→75.9524%。
因两组EC退步拒绝，不按EV好分挑库；七条同时改，不能归因于单一ALL技能。

**B2候选2亦已拒绝**：教师只UPDATE2（联邦/俄勒冈EV-only），同C1为父，
10条/40函数/3987tokens，bankSHA a1481cb75a9992ad46dadb38a45805507270dc320baabba9e17f8237019884e4。
教师83829input/3599output、63.651s。完整EC可见投影不变，全部8个已见EC
messages/schema及47_EV不变；9个逻辑重放复用既有真实输出，7个EV需新生成。
这是作用范围保持证据，不是9次独立新胜利。实际当前EC不变、EV50.5655→54.7917%，
旧EC不变，但旧EV71.1012→65.2778%、全EV73.1424→66.6667%，旧EV正确claim19→15。
所以03:28:48实际发布仍为C1同hash，B2未更新；B3自动沿用C1继续。23个物理候选
重放均stop、172584prompt/58975completion，两个失败和97工件已双盘保全。

**B3候选1重放中，未发布**：MERGE1+UPDATE3，联邦EC/EV合并，更新PA/IL/AZ；
9条/40函数/3851tokens，比父库少1条，并非只增技能。SHA
aed467bfa464fc2fd97852a5d726954df0e2a4363855e019bcae0d4f37db863f。
教师83253input/5912output、113.212s，实际4次累计返回。提案修住宅/车辆单项
不应*N、先通用条款再特定条款，仍需核重新合并是否伤及已学分类，不能看内容放行。

## 当前断点和有用的否证

- B2在线EV漏21配对（14为Fed(d)(5)），另6金额错：3个车辆公式盲目*N；
  2个单人PA案写成600而非300；1个WI车只用4000基额忽略16000可用最大额度。
  PA案公共N确为1、现存300*N程序本已正确，是原生写了600，不是N解析器bug。
- C1全部B1 EV共23个操作，已有程序只可修1个金额错；不能以函数0解释所有低分。
  EC21个真配对中5个没进入EV，但EV又有4个EC漏项。硬限制EV为EC子集会传播错误。
- 本地生成推理确有“更具体所以排除通用条款”的说法，和最终漏项一致；它不是
  内部因果证明。教师收到Gold/最终程序/分数，没有本地reasoning_content；这是
  信息边界，不保证加更多思考就有效。EV schema把额度放法条前也是待验证负担，
  不能单凭新设想重启/热改当前轮。核心关注独立法律选项覆盖与真实执行。
- 原资产池505种；本轮74次出现/70不同描述、4种跨来源重复。B2十五种描述全新
  于B1，后批不能混称新source与新asset/category泛化。结构检查不证明标签质量。
- 新的已见TRAIN观察：拒绝候选45只保州法而丢联邦；46以已有特定条款为由舍弃
  wildcard；50生成文字谈到不存在的PA8124(a)(10)，最终又输出别的错误合法引用。
  同一原文仍含AZ法，但不据共现断言唯一原因，不热改当前上下文/字段顺序。
- 53住宅目标27900是原作者married_limit55800除married_item_claim_count2的单项
  约定，不是本项目改标签；这里只读核源码/公开statutes/federal.json，未调用solver
  推理或给教师私有结构字段，也不把此benchmark约定当现行法律咨询结论。

**已完成且拒绝的非思考配置诊断**：不是主训练，不再运行，不追加参数网格。
全部B1四来源×EC/EV×empty/C1，共16次/0新教师，官方T.7/P.8/K20/同seed与上限。
03:01:43完成，3828completion tokens；C1变70.625/62.6488%，低于原81.0417/71.1012%；
empty变61.0417/24.3056%，也更差，含1次非法算式。相对技能差值变大来自削弱空库，
**不采用，不以其作好看的方法结果**，主训练始终维持thinking ON。
原汇总脚本在全部16预测后因历史C1 arm=candidate、分析组=skills不一致退出1；
已按调用前留存的分组说明只纠正分析标签，0重新生成/答案修补，56工件双盘核验。
session47498已终态，不重启；结果在`official_nonthinking_C1_all_B1_20261020/result.json`。

## 下一直接工作与停止边界

先完成B3候选1真实重放/准入，若拒只允许原协议的一次修订；随后B4–B6新案。
核仍有效C1与后续真实发布的迁移、CRUD/预算和送达/调用，不只看B1或53一个好案。
不额外追加B2第三次教师，不把训练内候选拒绝当系统故障重启或宣布新库已生效。
本轮B2两项均值正，未触发连续两批伤害停止规则；不因EV一个负点停止或凑机械单调。
实质系统问题或预定连续伤害时先保全终态再修，不选旧好库、不硬拖无效训练。
不要在当前正向分类证据上另起B1，不把临时观察超时/诊断汇总报错当主进程故障。

尚缺：足量正式预冻结数据、成熟经验方法公平对比及总成本、独立学习重复、来源级
不确定性、适当法律迁移、冻结最终库后的隔离TEST、实证支持的新贡献。Goal不完成。
扩量决策草案：[正式证据下一步](research/FORMAL_EVIDENCE_NEXT_GATE_20261020.md)。
草案不是已冻结实验，不启动对照队列，也不把规模提议当功效已充分。

## 证据、恢复和工具

研究主目录：`artifacts/research/openexempt_mechanism_20261019/`。关键文件：
`official_sampling_run01_launch_receipt.json`、`official_sampling_B1_real_publication_and_actual_skill_use_audit.json`、
`official_sampling_B2_complete_forward_and_actual_error_audit.json`、`official_sampling_hourly0328_actual_direction_review.json`、
`official_sampling_B2_rejected_broad_edit_and_EV_only_refinement_impact_audit.json`。
最新发布审计：`official_sampling_B2_final_rejections_actual_skill_management_audit.json`。
最新前向/提案审计：`official_sampling_B3_fresh_forward_and_actual_skill_management_audit.json`；
实际教师费用字段在response.invocation，B2总150509input/9779output/161.397s，
前一B2审计optional顶层usage为null不等于0，见`official_sampling_B2_actual_teacher_cost_receipt.json`。
只读机制前缀：`official_sampling_public_source_and_asset_overlap_readonly_audit`、
`official_sampling_B1_published_routine_amount_only_diagnostic`、
`official_sampling_B1_post_decode_fix_EC_EV_coverage_audit`、
`official_sampling_teacher_information_and_claim_order_readonly_audit`。

源码/结果双盘：`/media/sangfor/vdb/legal-skill-backups`与
`/home/yndx/hhy/legal-skill-rootdisk-backups`；独占创建tar并逐成员SHA核验，不覆盖历史。
repo `/media/sangfor/vdb/legal-skill-evolve`，hhy下`legal-skill-current`指向此处。
`.venv/bin/python -m pytest`；系统git不在PATH，使用Git runtime：
`/media/sangfor/vdb/legal-skill-forensics-20261015.pr9fln/git-runtime/usr/bin/git`，
配GIT_EXEC_PATH同根`usr/lib/git-core`。五个用户未跟踪report目录不清理，不删旧失败。

历史已完整保全：[前游标](CURRENT_GOAL_history_archived_20261020_0312.md)、
[早期游标](CURRENT_GOAL_history_through_20261019_2228.md)。旧namespace/active_case/
ContractNLI及32B相关流程均不是当前live任务，不恢复旧队列。
