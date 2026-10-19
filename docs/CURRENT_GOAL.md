# 当前Goal执行索引

更新：2026-10-20 05:33 Asia/Shanghai。Goal active，未完成，无外部阻塞。
本页仅作续接入口。真实状态必须亲核systemd/PID、原始工件，不能仅信游标。
本轮完成B4最终准入、实际技能损益与05:28小时复核，主训练自动进入B5，未重启。

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
- 每小时以实际时钟复核。**最近05:28:32已实际自检，下次06:28**。主训练独立于
  对话；没有声称另建了能自动唤醒模型的提醒产品。

用户追加要求、完整小时记录见[生效补充](research/GOAL_ADDENDUM_SKILL_EVOLUTION_20261019.md)。

## 当前唯一live主训练

- Run `legal_openexempt_official_sampling_online_20261020_run01`。
- unit `legal-openexempt-official-sampling-20261020-run01.service`，原PID3085974，
  01:52:27启动，05:28亲核仍同PID active；05:28:44自动完成B4、进入B5。
  05:30:05 progress为B5新案，168 native/7教师、33次跨阶段同wire复用，61号案。
  不能把观察超时或观察者正常退出当主训练停止理由。
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
  B1=45–48，B2=49–52，B3=53–56，B4=57–60已反馈；B5=61–64预测中，
  B5反馈尚未释放，B6=65–68尚未查询。预测结束前不读取其Gold。
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
|B4|77.92 / 79.17|70.76 / 71.04|83.89 / 74.17|

B2对空库EC+22.7083pp、EV-4.2262pp，两项均值+9.2411pp；对C0均值+8.6161pp。
这是真实分类迁移，但EV仍负，不是全方法已稳定成功。B2全输出EV为empty56.4354/
frozen52.4242/online51.2121%。24次物理回答全stop、无协议/动作错误、真实存储调用0。
累计16来源：empty67.1875/61.2674%，online76.6319/67.8150%，frozen65.2257/65.5382%。
online对C0 EC+11.40625pp、EV仅+2.27679pp，两项均值+6.84152pp；不掩盖EV小幅。
这不是正式规模、显著性、成熟方法胜利或官方TEST。

**B3增益边界**：对empty EC+17.9167pp/EV+31.25pp；对C0 +13.75/+7.5pp。
对C0全部增益集中53号（EC25→80、EV40→70），另外54–56都平，非均匀跨案改善。
53_EV empty写V<=700/V<=27900，非法数值程序按原规则0分，不修补/重答。
去掉该案的敏感性仅作诊断：其余三案online=C0 EV79.4444%，empty61.1111%。
53_EV online正确claim4对C0的2，仍把住宅单项27900写成55800；未解决所有问题。
B3共24逻辑/20物理回答（AZ/IL的4条online与C0同wire），20全stop、1空库动作错，
137352prompt/43582completion，真实存储调用0。此前说9/24物理进度已向用户澄清：
24是逻辑/最大生成数，实际20，不当独立重复。66个B3工件已双盘逐成员核验。

**B4新案**：对empty EC+5.9722pp/EV-5pp，两项均值仅+0.48611pp；对C0均值+8.125pp。
完整EV online72.5/empty74.1667/C0 69.375%，同样未胜empty。58_EV online80对C0
37.5、empty50，但60_EV online50对C0 80、empty66.67。60_EC online已100%，
独立EV却丢联邦，只剩州法3个正确claim，不能靠修金额函数补回全部遗漏。
57_EV带库漏真实硬盘，empty全对；59_EV的耳环是真实事实，三臂均错给服装豁免，
并非虚构资产/名称问题。原EV忽略该额外claim给100，全输出EV罚为80，两项原样保留。
B4共20物理/24逻辑，141607prompt/48311completion，全stop、无动作错误、实际缓存调用0；
66个B4新案和教师工件已双盘保全。有效库仍C1，不把批次难度变化称为新进化。

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

**B3候选1已拒绝**：MERGE1+UPDATE3，联邦EC/EV合并，更新PA/IL/AZ；
9条/40函数/3851tokens，比父库少1条，并非只增技能。SHA
aed467bfa464fc2fd97852a5d726954df0e2a4363855e019bcae0d4f37db863f。
教师83253input/5912output、113.212s，实际4次累计返回。提案修住宅/车辆单项
不应*N、先通用条款再特定条款。24物理重放全部stop，177358prompt/67963completion。
实际当前EC85.8333→90.8333%、EV77.0833→68.3333%，旧EC72.9167→76.3938%、
旧EV60.8333→63.1597%；当前EV退步而拒绝。**合并伤害分类的猜测在本次不成立。**
53住宅金额修对，却将PA正确600写成300/30000并漏wildcard；56丢3个正确联邦配对。

**B3候选2也拒绝，B3无更新**：仅UPDATE AZ，10条/40函数/4056tokens，SHA
5dec10bc9e662d2c555c254ecc30a78cdd3fb7380a4c241b91d9c516d5732403。
教师103223input/1245output、23.75s。20条请求与父库完全相同，4条AZ新生成；
29816prompt/5962completion，全stop。实际所有原分项与父库相同，无严格改善。
**不能把同分说成没学会额度**：55_EV确将车辆30000修为15000，却把原本正确的
投影仪household residual误改成trade tools，TP/FP/FN仍3/1/1，单案F1仍75%。
数值修复与新分类损害抵消。缓存函数仍0，这里是inline知识采用，不是缓存调用证据。
04:27:56 publication父子同C1 hash；只有B1实际发布过一次。B4继续真实C1，不是候选。

**B4两候选均未发布，已进入B5**：第一候选MERGE Fed EC/EV+UPDATE AZ，
9条/40函数/3934tokens，
SHA a512d61ea25816d5b3c6d5b24b928eb0d44e4dfa51b0ab7c4a1046456fb40900。
教师99253input/4618output、78.923s。强调同一法条集合、wildcard与特定项并列、
贸易用途须事实支持、AZ珠宝不等于服装、ring条件和车辆单项上限。
完整32逻辑/30物理重放后，当前EC83.8889→77.2917%、EV74.1667→82.5%；
旧EC77.2222→62.4967%、EV66.25→62.2421%，因此拒绝。30回答全stop，
224272prompt/73188completion，实际缓存调用0。60_EV恢复特定联邦条款至80%，
但仍漏wildcard；不能把恢复部分选项说成完全修好。
按实际公开送达范围，AZ的8个已见任务3好0坏5平，55/57_EV均100%，59去掉
错误耳环claim使全EV80→100%；联邦相关22任务3好16坏3平。分组是实际观察，
不是另跑的隔离候选，更不后验挑AZ部分发布。不能一概说教师没有学到正确规则。
第二候选只UPDATE AZ，教师121907input/1936output、36.285s；整库4113超过
4096token上限，尚未生成重放就拒绝，**效果未知，不是NOOP或已测负效应**。
没有覆盖上限或第三次教师。05:28:43 publication父子同C1，仍只有B1真实更新。

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
- 本轮已核教师实际结构：B3为83253input token、236321 user字符；172210字符是
  累计训练，法条20447字符仅一份。不能称主要因法条重复或已发生输入截断。
  B2修订带同批拒绝反馈，B3首提案不带跨批拒绝历史，但仍有累计Gold/父库回答；
  这是信息边界假设，不证明根因。完整只读审计已双盘保全，不重复做提示长度诊断。
- 新已核编辑粒度：B3 AZ修订除了1个operator，还改procedure/avoid_when，影响4条
  已见请求；纯公式改动的未查询反事实只影响2个EV请求。后者没有生成/分数，不作效果。
- 两项纯CPU机制准备已完成：既有execute_claims可对同一显式调用按新程序重新计算；
  实际服务环境xgrammar0.1.23可编译最小缓存null/未缓存inline分支。均是合成机制检查，
  0新增模型/教师调用、不算8B实际使用或指标，不再扩资格测试。客户端venv缺xgrammar
  不代表服务不可用，不安装依赖。ScienceClaw本次runtime入口读取失败，不反复重试。

**已完成且拒绝的非思考配置诊断**：不是主训练，不再运行，不追加参数网格。
全部B1四来源×EC/EV×empty/C1，共16次/0新教师，官方T.7/P.8/K20/同seed与上限。
03:01:43完成，3828completion tokens；C1变70.625/62.6488%，低于原81.0417/71.1012%；
empty变61.0417/24.3056%，也更差，含1次非法算式。相对技能差值变大来自削弱空库，
**不采用，不以其作好看的方法结果**，主训练始终维持thinking ON。
原汇总脚本在全部16预测后因历史C1 arm=candidate、分析组=skills不一致退出1；
已按调用前留存的分组说明只纠正分析标签，0重新生成/答案修补，56工件双盘核验。
session47498已终态，不重启；结果在`official_nonthinking_C1_all_B1_20261020/result.json`。

## 下一直接工作与停止边界

直接核当前B5–B6新案及真实教师/准入，按原有界研究或预定连续伤害止损。
核仍有效C1与后续真实发布的迁移、CRUD/预算和送达/调用，不只看B1或53一个好案。
不额外追加B2第三次教师，不把训练内候选拒绝当系统故障重启或宣布新库已生效。
本轮B2两项均值正，未触发连续两批伤害停止规则；不因EV一个负点停止或凑机械单调。
实质系统问题或预定连续伤害时先保全终态再修，不选旧好库、不硬拖无效训练。
不要在当前正向分类证据上另起B1，不把临时观察超时/诊断汇总报错当主进程故障。
已确认的瓶颈是局部修复与无关输出漂移会抵消，不只是没标签/没学规则/函数0。
当前不加更长教师提示或第三候选。B4又证实跨范围整包修订可抵消有益局部修订，
且预算拒绝和效果拒绝必须区分；不以放宽门槛/容量或后验截取好改动制造进化。
若后续仍停滞，下一有据的结构候选是把法律选择
指导与数值程序执行分离，使纯程序修订不必触发原生重新推导；详见下一步草案。
它尚未实现/验证；不能声称自动调用便能补回遗漏法条，更不允许用Gold分类或修答案。
60的EC/EV失配进一步支持检验EV共享分类指导，而非硬过滤到一次EC答案；旧B1已
发现EC/EV各自有对方漏项，不能把预测EC当Gold。现阶段仍先看B4真实准入及B5–B6。

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
候选拒绝/收窄：`official_sampling_B3_rejected_merge_and_AZ_only_refinement_audit.json`；
最终补正与小时记录：`official_sampling_B3_final_rejections_and_compensating_skill_effects_audit.json`、
`official_sampling_hourly0428_actual_direction_review.json`。候选2车辆已修正，不要误续成仍30000；
其净零来自新投影仪分类错误，原生完整回答/分项及202工件双盘收据均已保留。
实际教师费用字段在response.invocation，B2总150509input/9779output/161.397s，
前一B2审计optional顶层usage为null不等于0，见`official_sampling_B2_actual_teacher_cost_receipt.json`。
教师输入新审计：`official_sampling_teacher_input_structure_and_history_boundary_readonly_20261020.json`。
最新B4：`official_sampling_B4_fresh_forward_consistency_and_actual_skill_audit.json`。
最终B4：`official_sampling_B4_final_rejections_scope_effects_and_budget_audit.json`；
小时复核：`official_sampling_hourly0528_actual_direction_review.json`。第二候选4113tokens
被预算拒绝、未重放；B5已自动开始，不要误续成仍在等待B4或模型停止。
粒度与CPU准备：`official_sampling_B3_AZ_edit_granularity_and_request_dependency_audit.json`、
`synthetic_same_call_different_program_CPU_only_20261020.json`、`synthetic_compiled_call_schema_CPU_only_20261020.json`。
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
