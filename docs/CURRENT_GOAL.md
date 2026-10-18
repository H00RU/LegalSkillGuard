# 当前Goal：法律技能执行的可信净收益

2026-10-17整理。此文件是操作索引，不替代实际Goal、进程和冻结工件。
近4000行历史游标已完整保存在
`docs/history/CURRENT_GOAL_before_compaction_20261017.md`；旧“下一步”不是当前指令。

## 完整目标不变

Goal状态以实际工具为准，目标尚未达成。保持ContractNLI法律任务、冻结律师参数及在线外部技能学习，
在不同合同上取得分类、原SPAN依据和联合正确性的稳定、实质净收益，胜过强空库、
等调用无技能核查和公平成熟经验学习方法。还须独立学习重复、机制消融、真实成本及
未调优正式TEST。不同难度批次裸分不要求机械单调，不预先承诺显著性或发表。
8案或32案已见训练拟合、单个固定库、输入/schema审计均不能替代这些要求。

原目标提及的 `legal_contractnli_answer_review_learning_20261015_run01` 不再运行。
其历史结果已归档；不要重启它或据此恢复9月多轮客户路由。

## 最新快照：2026-10-18 12:58 CST，用户清除旧Goal后显式新建

- 实际Goal工具12:45新建，状态active。今天优先争取完整、可信的实质净收益，
  不保证今日必然突破，不以协议通过或B1拟合冒充论文结果。单个原8B和原授权教师，
  不增付费API/模型、fallback、答案修补、效果准入/较好库回滚或案件特调。
- ScienceClaw/FlowSteer/TF-GRPO的昨晚源码审计已接回；重新核对官方论文/代码。
  ScienceClaw的技能与可执行工具、FlowSteer公开参数训练和TF-GRPO无标签版本不能
  混成同一种机制。按师兄paper-ideation第3节做接缝检查，不重开月度大调研或堆新代理。
- 前一条语义特征run实际上12:28:17已launch、12:34:09失败，2native/1教师，非仍运行。
  教师真实UPDATE3、47语义条件/1659tokens；第二训练源334出现大范围枚举，8192未完成。
  第一训练源也有将无外部接收人许可误作特征激活的错误。不能宣称特征F1或主训练收益。
  102成员实际失败终态双盘已核验，SHA
  `f8151aafde21949e8680df06e9275be0b9bd9c57f8cd6fe549f42b79d53acb1d`。
  不重跑47条件共同执行、不用截短/去重/扩大输出掩盖。原服务PID3889231仍健康。
- 本轮已在原`member_contract.py`/`member_learning.py`实现公开适用范围执行块，
  scope匹配的命题共同作答，每块完整原文、原命题和适用程序。不是客户语义路由、
  TF-GRPO rollout组或17次逐题隔离。历史17次隔离小收益、不及更强joint空库已保留。
- 当前负收益真实R3七技能自然形成七块。新有限Run
  `legal_contractnli_skill_block_execution_20261018_run01`已prepare，**截至本快照未launch**。
  配置`configs/contractnli_skill_block_execution_20261018.json`，协议
  `SKILL_BLOCK_EXECUTION_PROTOCOL_20261018.md`，同原已暴露16，256native/0新教师。
  joint空库/技能、scope同块空库/技能四臂；输入全部冻结后生成，全部完成才统一评分。
- 合并仅复制不重叠的真实原生字段，明确composite/所有raw_ids；一个子块失败则整案
  保留原17题失败分母，不修答案。88项检查7.66秒通过，无模型资格生成。
  首次准备中的两处合成测试夹具错误及未launch冻结包已原样归档，0native/teacher，
  更正后重冻；不是在看成绩后调整。下一步双盘保全后立即独立后台执行。
- 即便本项正向也不标Goal完成：还需后续在线批次、强普通监督工具、等调用核查/
  公平成熟经验方法、独立学习重复、真实总成本与未调优官方TEST。不会只比弱空库。

## 已归档恢复快照：2026-10-18 12:26 CST，单服务恢复并续接代码工作

- 用户取消双实例和相关并发链路改造。只恢复同一Qwen3-8B；保留任务、教师、律师最终
  输出责任，不重启旧负收益run。不是重新开始全量资格测试或新建研究Goal。
- 五片权重全部按官方hash验证，12:18:56准备任务成功，12:20:09服务完成启动。
  当前`legal-qwen3-8b.service`MainPID3889231、engine3889870，localhost8000健康200。
  新进程、模型root/revision和实际argv/ticks收据为
  `artifacts/live_8b_environment_restored_20261018.json`。旧运行冻结收据不改写。
- 实际3次合成生成：普通生成、结构化生成、旧故障同一1-token/logprobs请求均200，
  最后服务仍健康。普通文本READY.多句号的字面遵循失败已保留，不重采样；不能据
  新logprobs成功反推旧EngineCore异常的确切根因。没有教师/训练案件启动检查。
- 模型文件在两文件系统有完整副本，五片SHA分别核验；源码完整Git1eb59a2两盘bundle
  SHA`fd201b0433a5bfbae18a6908fed02f2b602e3445932a78f713404f92565736e9`。
  同主机双盘不是异地备份或整机回滚。完整推理环境位于独立runtime而非CPU项目venv。
- 已续接昨晚未完成断点：在原`executable_features.py`新增显式语义谓词表示，通过
  同一8B每源一次执行全谓词；原锚定scorer/CRUD/原SPAN指标及最终律师权责不变。
  无新代理、另模型、失败返回零/正则替代、输出修补或效果准入。纯代码仍按原约束执行。
- 原实验入口已接教师和真实native记录；85项检查8.31秒通过，不等于有效。
  新有限run`legal_contractnli_semantic_feature_feedback_20261018_run01`已prepare，
  **截至本条尚未launch**。真实末次负收益父库，不选旧较好库；同18/原已暴露16，
  教师完整输入943757chars，0新教师/语义执行。计划1现有教师、最多34native及7base fits。
  配置`configs/contractnli_semantic_feature_feedback_20261018.json`，完整协议
  `SEMANTIC_SOURCE_FEATURE_PROTOCOL_20261018.md`。先完整固定库组件转移，不冒充主训练、
  独立held-out、端到端收益或论文Goal已达成。下一步保全冻结源码后实际后台执行。

## 已归档恢复快照：2026-10-18 11:55 CST，已授权恢复同一模型

- 用户已明确要求把训练模型服务恢复，允许重新获取同一Qwen3-8B并重建完整环境。
  不等于换模型/教师、修改任务、恢复负收益训练或自动新开研究Goal。
  实际Goal工具仍blocked，研究目标未完成；原恢复授权缺失已由本条用户指令解除。
- 独立后台`legal-qwen3-8b-restore.service`正在执行；11:52:55这次启动MainPID3851150，
  InvocationID`724744ed51984059bdfb69d25ad42522`。11:55核实同身份live且文件增长，
  不是仅凭进度文件声称运行。此前为切换慢速传输路径停止的准备进程已如实留在journal。
- 官方HF版本`b968826d9c46dd6066d109eabc6255188de91218`，五片16.38GB BF16。
  官方Qwen ModelScope镜像版本`7c9709d23bd2136dac1d6ea1fe30f4107d681cd6`
  的五个SHA256/size与HF完全相同，选择直连续传；完整下载后仍逐片验证。
  元数据/词表从固定HF版本取，原实例SHA未找回，不声称位级等同原RAM实例。
- 新环境位于`/media/sangfor/vdb/legal-skill-runtime/inference-qwen3-8b-vllm0102`，
  核心版本按旧推理lock固定；不借用其他项目的不同版本环境。
  当前下载/安装进行中，**尚未声称8B ready或训练已启动**。
  GPU驱动动态库确认为570.133.20匹配；用户原有Linger=yes未更改。
- 常驻服务单元`legal-qwen3-8b.service`由准备任务在文件/环境完成后启动，
  同名localhost8000、32768/seq1/KV5GiB、原采样/解析服务配置。
  `Restart=no`不掩盖引擎失败；journal日志不依赖旧的被删server.log路径。
  只做合成输入健康/结构化输出/故障路径核验，不进行正式案件全量资格生成。
- 用户问双模型是否提速：尚未部署第二模型或改并发配置。共享一份权重的seq2通常
  更节省显存，但需要实际客户端并发与单独吞吐/正确性验证；批间库更新依赖不并行。
  具体恢复边界与命令见`QWEN3_8B_SERVICE_RECOVERY_20261018.md`；ops仅基础设施，未改主方法。

## 已归档恢复快照：2026-10-18 04:32 CST，第三轮同一恢复阻塞核验

- 原用户触发轮及两次自动续行中，同一恢复阻塞连续存在。上一轮仅复核状态，
  属no progress，不是verified wait：没有可确认live的服务或训练句柄。
- 04:32:27再查`/health`为curl7/连接拒绝，原2261314/2261698均不存在，
  两个已知Qwen3-8B权重路径仍缺失。未收到用户允许重新获取同一模型并重建服务的答复。
- 源码、CPU结果、排序及事故证据已双盘保全；已查日志/存活句柄/常见缓存无安全恢复路径。
  不以重复负收益CPU拟合、相同库改词或状态文档更新冒充向完整目标推进。
  当前具备blocked审计条件：恢复推理必须等待明确恢复决定或外部提供同权重副本。
  将调用Goal状态更新为blocked，目标范围不变、未达成，不标complete或擅自pause。

## 已归档恢复快照：2026-10-18 04:29 CST，推理服务事故

- **当前没有律师后台训练或可用8B服务。** 04:23:25在同RAM8B上做两项合成输入能力检查：
  embeddings返回不支持；随后max_tokens1/logprobs请求HTTP500 EngineCore错误，
  原2261314及2261698均退出，显存释放。请求由本助手发起；具体退出堆栈未找到，
  不能断言OOM或以10月15日旧NCCL日志解释本次事故。没有重试、kill、重启、下载或删除。
- 原模型磁盘权重及旧环境此前已缺失；已查路径/缓存没有找到同一模型完整副本。
  不用其他Qwen3-VL模型替代。若需重新获取同一8B并恢复环境，先明确请求用户确认，
  记录新revision/hash和运行身份，不能声称与原RAM实例位级一致。详见
  `docs/INFERENCE_SERVICE_INCIDENT_20261018.md`和实际请求/错误目录
  `artifacts/research/frozen_8b_semantic_feature_capability_20261018/`。
- 上条反馈更新实际04:16:55已完成，worker3190570/preserver3190571终态，
  0native/1教师/7普通base fits。teacher1395，实际UPDATE3，最新3程序/37特征全部发布。
  普通F1=69.7959%，更新后67.6923%，比实际父库69.2607%更差；不选父库回滚。
  普通与最新mAP85.6246/83.7352%，不能仅归咎阈值；停止同类正则特征重写路线，
  没有据此开启长训练，没有端到端/在线进化/显著性或正式TEST成功声明。
- 最近实际终态105成员在两文件系统重新校验相同SHA
  `e947349e6cd518a5a27ff1f5586860895d010cc1261899d2e700d5cacd6a1f76`，
  完整Git eb69017两盘bundle SHA
  `580bedb22a35614c61fc896e4e92187e27f7301d4aa6fc6a6cd3a15d04d196a6`。
  源码/CPU模型/原始实验结果不是本次故障丢失项；运行权重不在这两盘归档中。
  新只读排序审计SHA`4c5f6ddd2a5f18efeae6556ca591c7f04d931597e7125a6e05bb4d1e7848ff43`。
- Goal active未完成，服务恢复授权为新事项，不能在首次事故就标blocked。
  上条证据集合复用边界仍未获确认且未实施，不与这次运行事故混为一个阻塞。

## 已归档恢复快照：2026-10-18，代码归纳完成后的锚定修正

- 锚定固定库CPU检验已完成：`legal_contractnli_anchored_source_features_20261018_run01`，
  0新native/教师、6普通scorer fits，19.91秒。普通171/32/116/F1=69.7959%，
  锚定178/49/109/F1=69.2607%，条件源区间跨0。19952零特征位置精确保持，
  普通分数与保存控制差0；局部性已修，净收益仍未解决，不能据此启动长训练。
- 下一项不是再换编译器：同一锚定机制下，向教师补交真实当前代码库/系数和完整18
  训练组件行为，让它做一次实际CRUD更新。仍不传16来源/Gold/成绩，不手改代码规则。
  已准备`legal_contractnli_executable_feature_feedback_20261018_run01`，尚未launch。
  teacher prompt934891 chars<1048576，当前父库3、37列、18完整诊断，native-lawyer rollout0。
  当前诊断有真实源外折普通分数与当前训练系数修正，但非整个归纳算法独立外折预测。
  老历史30条律师记录不再冒充当前learner轨迹。计划0新native/1教师/2 factory（最多7 base fits）。
  cfg`configs/contractnli_executable_feature_feedback_20261018.json`及专门protocol为准。
  最终输出责任仍不改，上条未获同意的证据集合复用未实施，Goal active未完成。

- 03:53:23纯源代码检验已完整结束，worker3154758/preserver3154759均终态。
  不是仍在teacher：实际0native/1teacher/2 CPU fit。教师1394/high67.618秒，
  192776输入/5086输出（其中reasoning2792），无工具/缓存/重试。全3程序/37特征、
  1929tokens均发布执行，无强制3类设计或择程序。代码已逐字审阅，无案件答表/ID/直接判决。
  普通TP171/FP32/FN116/F1=69.7959%，代码联合拟合TP157/FP34/FN130/F1=65.6904%。
  仅CPU辅助指标，不是端到端或新在线训练完成。102成员实际终态双盘SHA
  `af4972b92238742345d64993f122b44248740d37dd6b6f49454594da5c0094d0`。
- 代码覆盖209/287 Gold，但仍失27/增13真成员，9个丢失位置没有任何代码特征。
  audit SHA`9ed5fb92f1b20cfa4bd38c68a654888100e5ca4a9bd2a6f46a19cd0ce8ee0fb7`。
- 当前修正保持**同一完整发布代码库不变**，把可学习特征用于普通最终log-odds上的
  一个局部项，普通词头/校准器不因程序重拟合。训练项使用TRAIN内真实合同外折基分数，
  原C10/阈值.5，不拿16选系数。特征0则分数精确等于普通，非答错后fallback；
  执行/概率/优化失败直接停止。只保证工具层零特征区域，不保证律师整段输出。
  新`AnchoredFeatureModel`复用原source executor/scorer，不增路由/判官/语义中间层。
  旧joint类型仅为真实历史pickle及方法对照保留，新factory单一路径使用锚定。
  83项现有及扩展检查7.25秒通过；不把通过当效果。固定库CPU检验尚待新声明执行，
  0新native/教师、1完整普通+5训练内合同外折fit，另计校正优化。
  具体边界`docs/ANCHORED_SOURCE_FEATURE_PROTOCOL_20261018.md`。
  最终证据复用问题仍待用户决定，**尚未实施**；不以此阻塞既定输出范围内的内容修复。

## 已归档恢复快照：2026-10-18 03:53 CST

- 纯源特征有限检验已于03:52:02实际后台launch，不再是仅准备：
  worker3154758/ticks427324024、terminal-preserver3154759/ticks427324025。
  03:53:07核实同身份live，teacher_attempts1/完成0、native0，无publication/failure/completion。
  现有教师账本1225历史下界+169新reservation=1394/1400，没有重置额度或新付费API。
  配置SHA`30afe26d8e80a32b54e762dde98d337794ea7d579cf9c3eafd26587229c3209e`，
  frozenSHA`19abdf5840a86f96208a9f861926979867dcbdf91354e5f622534bf452c927d4`。
- 新源码及完整Git commit`d4d8b9a42d3c080a43d0085af3231bcc49c8c189`已双盘保全：
  92成员prelaunch archive SHA`e1090d36935d7ce0965dc5cf26d31423ee337a744b3581ace171d3a3d6c7dcb2`，
  自包含完整Git bundle SHA`d0d5173e9547ddfcd81eca76fc6beec2f496dd80047655c402d22829fae5111f`。
  同机两文件系统，不是权重/认证/异地/整机快照。
  守护保全沿用已验证代码，并明确加入.pickle，使实际成功或失败及CPU模型均归档。
- 下一步只核验这次真实teacher输出、全库合法发布、实际特征执行与同18/16普通配对。
  不热改84绑定，不挑feature/库/来源/阈值，不把代码能跑或CPU正差当论文目标完成。
  最终证据复用边界仍未实施，当前分支严格0律师生成，不需要据该待答问题阻塞其他既定工作。

## 已归档恢复快照：2026-10-18 03:50 CST

- 新只读内容归因已完成，0新fit/native/teacher。旧查询库训练18覆盖Gold284/416，
  新16仅80/287；全query未命中题92/306→190/272。v2相对普通丢48真成员、增13，
  丢失中40不在任何query特征命中处。训练拟合ordinary99.0291/v299.3969%，
  不是新案收益。audit SHA`05adb3b02e6fad9f0a3136bcba9ec8f18d364c8f56959065cdb0ddaec15ac92f`。
- 上条最终证据复用边界仍未获用户同意，**不实施**。它不等于整个Goal必须停止：
  既定输出责任下仍可研究外部技能内容的表达能力。没有全局blocked条件。
- 依师兄paper-ideation第3节接缝检查，只检验一个已有短板，不重开选题雷达或包装创新：
  固定短语+邻居窗口不能一般表达跨句源计算。已新增纯源特征函数API和资源受限CPU
  执行器，重用同一个ScienceClaw归属scorer及OOF hook。不是新规划/路由/判官或新模型。
  原n_spans×固定特征列，有限[0,1]，无Gold/ID/文件/网络或直接法律/最终证据输出。
  源码限定能力并不等同于通用敌对代码安全沙箱；仅既有可信教师可生成。
- 新有限开发检验已准备、**截至本快照尚未launch**：
  `legal_contractnli_executable_feature_induction_20261018_run01`，同历史18、原固定已暴露16，
  空父库1现有教师/2 CPU fit/0新native。原子有效修改全发布，不按效果准入或重选。
  教师只见完整18+30条真实历史公开观察及旧查询库，不伪称新learner轨迹，不见新16/成绩。
  实际完整prompt797241 chars<1048576；无截断/思考标记，84冻结绑定核验。
  82既有与扩展检查7.12秒通过，无全量资格生成。保全后用新worker后台执行。
  `configs/contractnli_executable_feature_induction_20261018.json`及
  `docs/EXECUTABLE_SOURCE_FEATURE_INDUCTION_PROTOCOL_20261018.md`是具体声明。
  此项不是已完成在线学习/端到端律师收益/独立held-out或正式TEST。

## 已归档恢复快照：2026-10-18 03:30 CST

- thinking-transfer已于03:10:11完整生成并统一评分34/0；505技能臂length8192，
  按协议保留全分母并记录failed，无completion。原worker3033735/preserver3033736均已消失，
  不再声称后台还在训练或34仍待完成。仅RAM8B2261314继续服务，未重启。
- 原定新16空库/技能分别76.8382/73.1618%分类、62.1622/61.8762%硬F1、
  46.6912/44.4853%联合。全部34从原作者及实际wire独立重算一致。
  audit SHA`cccf14fce02d3830d03b450bc956978519d4a91701739d716f753b4de8097689`。
  186成员实际终态双盘SHA`71d36fddba6df704478a5cb5273f59336ff28673eadafe656f6ca83e12f76b2a`。
- 失败源贡献分类−9/联合−7；其余15有效配对仅分类−1/联合+1，不能靠删失败宣布有效。
  已知89硬F1仍负收益；不扩大同一文字库+thinking配置为成功主训练。
  完整结果与限制见`SOURCE_CRITERION_THINKING_TRANSFER_RESULTS_20261018.md`。
- 新只读CPU证据：已有24来源普通M4对同16 F1=69.4915%，不是技能收益；
  历史查询库全部3前缀普通/程序F1为56.4334/56.3063、65.0104/64.5702、
  69.7959/69.1511%。实际模型hash、同源组件排除、逐分数query-zero=ordinary均核验。
  audit SHA`b2b9bb0f1a762b5d9187b97eedf6a6e60e3983babe33e2d78e1f6c9f3a2f996a`。
- 当前根因级改动是修正**旧可执行程序支路**的fit/inference分布不一致，不是再改律师提示：
  v1先完成ordinary OOF校准再附加query logits；v2使相同word+query设计进入final LR、
  每个合同训练折及相应OOF校准，树特征维度/参数不变，无第二中间模型或fallback。
  不强行冻结辅助词头/校准器；冻结的是8B律师。普通控制独立同数据拟合，mask-only非普通基线。
  保留旧pickle类型仅为历史可读，无旧训练路径开关。新teacher API说明及现有单测同步修改。
  78项检查7.12秒通过，没有新增测试脚本；源码改动在全部旧worker终态之后发生。
- CPU有限比较已预先冻结14工件，同实际末次历史M3/18来源、原固定16、原阈值.5，
  2次fit/0新native教师。声明SHA`aff09a01b36c8c589a78b460cb778ec549893167645a72917c17eece700b7d71`。
  exec session96757已于03:25:43完成，不再运行。新空程序预测与旧普通模型逐分数相同；
  新joint-query图反而TP136/FP23/FN151、F1=60.9865%，旧普通TP171/FP32/FN116、
  F1=69.7959%，旧程序69.1511%。修正接法并未建立技能收益，不启动该配置的长GPU训练。
  完整结果双盘SHA`815450217835a2e9a45c809d85f9958f189939006e4b0f8f61af6ebfae35c298`。
  文件夹`artifacts/research/query_calibration_repair_20261018`；两次真实CPU fit共8.89秒，
  没有新GPU/native/teacher，旧模型预测仍与修改前审计1e-12内一致。无阈值/参数网格。
  不改任务、不把程序输出拼成新律师成绩、不自动委托其最终证据决定。
  Goal active，完整在线收益、成熟对照、独立重复、成本/消融及未调优TEST仍待完成。
- 方法输出边界需用户决定，**尚未实施**：是否允许律师显式选择并确认可执行选证技能的
  完整结果，避免重新自由枚举全部索引；关系仍由律师判断，原始SPAN指标不变，
  不空命中判NM、不后台修答案、不以普通监督收益冒充技能收益。
  这改变此前“最终依据索引全部自由生成”的运行契约，不能默认扩大权限。
  此为该新边界的首次请求，不满足blocked阈值；没有pause或complete请求，Goal仍active。
  在得到决定前，保全/核验及既定输出边界内的内容修复可以继续；
  不能据此改正式输出责任或启动证据结果复用架构的训练。

## 已归档恢复快照：2026-10-18 02:50 CST

- **source-only主run已停止，不再运行**。原worker2959984、preserver2959985、observer2959986
  均已消失。02:21:44在完整B3后按预设条件安全停止，96新native/3教师，0 B4回答/0第四教师，
  没有completion；InterruptedError是安全边界，不是模型崩溃。R3仍是实际最后发布库，没有回滚。
  B3-after全24为68.6275/38.3824/40.4412%（分类/原硬F1/联合），TP261/FP629/FN209；
  父库同24为69.1176/54.2891/41.9118%，R3 F1−15.9067pp且低于匹配累计空库23.0834pp。
  预设双重>=5pp仅F1触发，停止动作/原始分母/不利结果均保留。
  实际终态双盘447成员校验SHA`c685d85fde57d3305d70144a49ba45b7a60821420be534decb4577e5295a49ee`。
- R2完整16已从原作者重算：15标签修复28损害、14联合修复32损害，NM7修复22损害；
  真成员20新增24丢失、误引43新增33移除；这是同父库真实损害，不归因于不同批难度。
  audit SHA`2737aa4f8c6411387353beab2a549373f6810e6e24b7b88295a3b4890b6d3e3d`。
- R3已知89的长回答有效stop/5238tokens/0私人思考，共977个引用、0重复；多个问题
  各自引用150–158个不同SPAN。不是重复数字、输出截断、检索清单复制或没拿到Gold。
  不用maxItems/去重/截短当修复；不据一条长答判断服务死掉，实际GPU98%且tokens前进。
- 下一项已于02:31实际后台launch：
  `legal_contractnli_source_criterion_thinking_transfer_20261018_run01`，34新native/0教师，
  原同RAM8B启用已有thinking能力，解码其余参数、完整原文/原17命题/schema/评分不变。
  固定实际末次R3（7技能、bank SHA`113dd8441543832ea2543e6da8b7e10e10a6f76c3bc865e277127a14b0fd73a2`），
  不选较好R1/R2。16新TRAIN来源+已知失败89，两臂各17；全部34后统一评分，
  新16/旧1/全17分开报告，不把已知旧案称未见、不忽略它，也不把本项称正式在线训练。
  63绑定，0生成输入核对最大prompt10567。只新增有限research入口，生产代码未改。
  新16为[553,122,580,248,385,481,410,417,317,153,297,436,191,192,505,130]，
  排除138旧配置/识别教师/原TRAIN-FUTURE常量/同URL或规范化全文组件。
  初版未运行选择含388/424/489旧常量，已在任何推理前剔除并留存原选择；不隐藏此准备更正。
  174真实teacher wire中47非JSON仅扫描case-ID字段，不宣称全部匿名文本完全还原。
  官方DEV/TEST未开，本项不是独立held-out确认；目标全部仍未达成。
  完整源码/Git/全部tracked源双盘10067成员核验，SHA
  `7ea1c6ebba198b5ee2b10b47f8fafa7dc3b29148f8e0bf5e71838775b8b614d8`。
  worker3033735/ticks426839277、preserver3033736/ticks426839278实际live；63绑定未改。
  02:32:25实际1/34，首个已知89空库完成，技能臂正在生成，0教师，无failure。
  首真实wire与旧89空库除移除disable-thinking模板参数外整个请求相同；原无私人思考，
  新响应私人思考2277chars（仅计数、不展示），finish stop/1079completion tokens/prompt8624。
  不是仅在config写了thinking，实际服务模式已核实。全34前不看效果、不改输入或选库。
  旧run全96原作者评分与实际wire/58绑定重算一致，R3相对同24父库TP+30/FP+479，
  其中89贡献FP+462、545贡献+28。没有删异常案或换微平均指标；新完整audit已直接双盘，
  SHA`e10a534819d24bd2d90bd1bd421c23e25b71629ec3e93e3c82defb86c7c88304`。
  下一步继续新34固定对照；区分新16净收益、已知89是否仍过选及全部17，不把它称主训练。
  完整在线学习、强成熟对照、独立重复及未调优TEST仍待完成；不要重开已停止的96/3坏run。
- 02:43:00实际11/34，worker3033735/ticks426839277仍同身份live，0教师，无failure，
  尚未统一评分。实际完成的6个wire均有私人思考（只计数），归一化response字段不含
  reasoning_content，对它get默认0不是有效模式统计；先前控制台0统计已纠正且不影响评分。
- 新发现R3非局部变化：只改3记录/9命题范围，对应过程逐字未变的192题仍有66题改变
  choice或引用集、FP净增174，89/nda-4引用1→158。全局库共同可见，不能把局部相同
  误说成整体请求相同，不宣称唯一attention原因；audit SHA
  `1d93c91050f8e8e46a5bcb2d48a55aedcfa09c7e5134b10871a22dc10004a1e6`。
- 恢复档案已找到真正逐项strict-scope和旧TF-GRPO源码/配置/报告，不再把两者当从未试过。
  恢复scoped源是后续版本，不匹配旧冻结SHA，旧raw不全，因此历史分数不是当前独立重算。
  历史逐项经验未胜更强共同空库；旧N5/98教师TF仅小幅分类/F1提升、非NM联合46→45。
  来源和限制见`docs/SOURCE_CRITERION_LOCALITY_AND_HISTORY_BOUNDARIES_20261018.md`。
- 当前16对本轮R3教师未见成立，但新恢复元数据排名证明192/505曾做旧TF开发评估、
  297属于更早前76开发组件；**不是全项目首次见到或独立held-out**。不热改冻结输入、
  不重选或删这3案，原16主分析照常，官方DEV/TEST仍未开，披露补充单独归档。
- 02:49:34已将17份完成且不可变的native/公开unit/payload和来源披露中途双盘保全，
  68归档成员核验，SHA`b8deaae5f14a8797c49e485da6d82cad4576ba1ac2488dcdf0be7ec4fa98abb7`；
  不是完整34相位、未读取部分效果、没有修改模型或训练。继续同一3033735，不重复launch。

## 已归档的02:01状态（不是当前运行状态）

- 固定R2的no-thinking对照已于01:17:59完整结束，48新native/0教师，原worker2900999/
  preserver2901000均终态；不是仍在启动。全48有效，实际终态双盘SHA
  `5e435b3af73c70f5eab89653a3c2b6602359cc3b042ec218ea360a849ef48d15`。
- 同16源原文+R2对匹配空库：分类72.7941 vs69.1176、硬F1 61.6197 vs62.4299、
  联合50.3676 vs45.9559%；TP+8同时FP+25，仍未解决真正的证据净收益。
  去M2让同R2 F1从50.3067→61.6197，但分类/联合下降，不能片面宣布全指标成功。
  80真实新/历史答已从原作者TRAIN及实际wire独立重算一致，audit SHA
  `c330ba7b2bbf7f0ac5184fc5017ededfc2de64850746f74acd0823f275b789ba`。
  报告`docs/NO_THINK_MEMORY_SOURCE_RESULTS_20261018.md`。
- 旧job终态后才修改唯一生产主链路，删除M2加载、候选缓存/字段/教师候选诊断，
  原文+一次准则，不留生产模式开关。保持在线外部技能、冻结8B、同法律任务及原指标，
  不是恢复客户路由/更换模型。教师同时看到真实漏选和误选，要求可观察源条件动作。
  当前不是严格TF-GRPO组内探索，不要在论文中冒用其名称；无标签学习有实证，不可
  据我们的失败宣布教师不能生成技能。参考核对在SCIENCECLAW_TFGRPO_MECHANISM_AUDIT。
- 新完整run `legal_contractnli_source_criterion_learning_20261018_run01`已于01:42实际后台launch。
  同32 TRAIN/4批8案、144全新native/4教师、空库起步，
  无R2或旧答继承；`configs/contractnli_source_criterion_learning_20261018.json`。
  58绑定、teacher ledger1390/1400，预留4次在原额内。78既有检查7.13秒通过，
  32原文干净接口、空库等价检查0生成，最大prompt8628；no-thinking计数/生成一致。
  源码/Git及全部tracked源9972归档成员逐一核验并双盘，SHA
  `f47abfb746b49938b4858346b3f6c678988407bac2527a8269b5d48e8885f366`。
  worker2959984/ticks426546946、preserver2959985/ticks426546947、完整边界
  observer2959986/ticks426546947均实际live；未热改原58绑定。
  02:00:57已完成R2学后6/16，即至少46/144 native、2/4教师，完整R2效果尚未出；无热改。
  B1学后完整且已自动B2：分类63.9706→73.5294%、硬F1 59.3548→59.1045%、
  联合36.7647→47.0588%。TP92→99、FP35→53、FN91→84；E/C/NM正确
  50/11/26→51/9/40，非NM联合均24，全部净联合收益来自NM，不宣布取证突破。
  首真实教师1391/high92.041秒，52087输入/5190输出(reasoning3171)，0缓存/工具/重试；
  CREATE7覆盖17，master1554/scope1783/实际一次准则1441tokens。
  全8原源/Gold/own/成员差分与实际teacher request核对；已完成学后wire仅完整追加准则。
  136题全部变化：16修正3损害，真成员12新增5丢失，误引25新增7移除；
  非NM联合4修复4损害。copy89有正确已交付准则却仍把必要同意当许可；
  反向工程被个人识别条款误判、207技术范围串入7个来源排除项，notice任务多引后果条款。
  不能说没拿到原文/Gold/准则，也不宣称唯一attention原因；不据B1停机或局部改词。
  全题原作者audit SHA`f0282bbe3cdbe2110fe143d466c282e6c742ebba17580b46b756588fb6b58156`；
  真实执行/误引例audit SHA`1f33d586680298766b38a178f7210f5c76b82bb122e748cf6d5104f7b0074e71`。
  B1完整147绑定工件已双盘，SHA`4074331d3263288bfd6968a3104296c70f73efdf8d56a6da4911d7fb9d06bd3a`。
  B2首遇16答完整：空库64.7059/61.9403/44.8529%，R1为72.7941/54.7170/55.8824%
  （分类/硬F1/联合）。空库TP83/FP54/FN48，技能TP58/FP23/FN73；E/C/NM正确
  38/13/37→40/9/50，非NM联合24→26。不能以总体分类/联合改善掩盖依据负迁移。
  全136新案变化：22标签修正11损害；真成员4新增29丢失，误引9新增40移除。
  丢失真成员21发生于关系仍正确、8发生于错关系（其中6为新错NM），主要不是标签错误。
  319/nda-2在关系仍C时由完整列表缩为开头SPAN12，一题损失18真成员；不补bullet parser，
  当前链路没有该查询/解析器，不把这一个案例当独立评估子集。
  B2全原作者评分/实际同源输入投影和R2信号audit SHA
  `c10b01145ee1c906758ae7d6e091060b3fe1099e8a4a17cd5fb158b3f5e4be9c`，该audit已直接双盘。
  R2教师1392/high83.514秒，80847输入/4968输出(reasoning2624)，0缓存/工具/重试；
  UPDATE7，总数仍7，master1775/scope2004/一次准则1662；完整parent/delta/publication核对。
  R2确实拿到B1-after8+B2-before8当前R1的全部真实own、完整源/Gold和原成员差分。
  其准则修订了copy同意、privacy与reverse engineering等错误，尚不保证行为被修正。
  R2真实教师及早期6份交付audit SHA
  `e82a04fb99812432babe3e306bc8a9f6206fb56ae251fa2e4802c398f3fdb526`。
  下一步必须完整R2后16源、父库配对/旧8保持，再看B3–B4；不按首批或跨合同裸分停机，
  不热改、不再开零碎探针。外部边界observer只在完整B2–B4规定双重>=5pp损害时安全停本轮。
  `strong_empty`仅是同no-thinking匹配空库键，不冒称最强基线；强thinking同接口
  对照/等调用review/成熟经验方法/独立重复/官方TEST仍PENDING。Goal active未达成。
  旧ACE模块依赖另一24源packet及M1–M4，旧52native/28teacher分数不能冒充当前32源
  干净接口公平比较；新对照须独立适配，不将其旧结果宣布为本轮已胜。

## 已归档的01:00状态（不是当前运行状态）

- `legal_contractnli_grounded_criterion_learning_20261017_run01`已于00:43:12.458
  自然失败，**不是仍在训练**。main2769948/preserver2769949/observer2769950均已消失。
  共72全新native/2教师，无R3。B2-before24和R2-after16均完整，后者存在scored phase但无
  batch2_summary，因为384原始输出JSON不闭合：finish stop、stop_reason151643、输出2815/8192，
  尾部泄出closing-think标记，不是length cutoff；不补JSON、不删无效分母。
  全16含该失败case仍为74.6324/48.2301/52.2059%，不能作为正常完成4批。
  实际终态双盘全330成员核验SHA`20687cf274227219d83b5b9ed2f765f41f7a0af910c483ebcf47dcde20713303`。
- B2新案同源：强空69.8529/64.9123/47.7941%，普通78.6765/54.6341/59.5588%，
  R1技能80.8824/52.2613/61.0294%。NN联合28→25，NM53→58；不能把总联合微升当取证收益。
  前16实际强空/普通对照：GoldNN314成员，M2只列121；律师选117列内+16列外。
  加入提示导致58个原空库真成员丢失，其中57不在候选，另28新得；不是原文删掉或top-k截断，
  实际是全部p>0.5交付。普通F1相对同16强空60.4824→54.3967%。高度符合低召回清单锚定，
  不宣称证明隐藏attention因果。receipt `B2_complete16_ordinary_aid_coverage_and_actor_anchoring_audit.json`，
  SHA`f6fc1baf343bcccff256f2a29948a17881c948e63a88089b5114aaac37879951`。
- R2真实教师1390/high80.864秒、86271输入/4155输出(reasoning1981)，0缓存/工具/重试。
  UPDATE6、保留2、总数仍8、master1822/scope2018/实际准则1703，**不是只增不改**。
  全16当前R1父库own（旧8after+新8before）、原源/Gold/实际M2和原始hash均核对，
  学后16输入仅替换完整准则，不能再说缺原文、标签、未交付或不看旧错。
  R2audit SHA`4e4bebb6168f99faf3007cbd7ac7213d468f252b7e414f30790fd1ece3441012`。
- 旧run全部终态保全、旧60绑定仍一致核验后，才修改三处模式接口：
  WireClient显式disable_thinking并同步server tokenizer，生成前拒绝模板模式不同；
  Comparison.call采用该已验证profile；实际wire审计核对chat_template_kwargs。
  旧thinking-on计数/生成原本一致，不冒称它原来数错；这是支持新固定profile的必要修改。
  既有78测试7.03秒通过，0模型/教师调用。服务实测vLLM0.10.2，不能拿新版Responses问题
  当当前Chat Completions唯一bug证据；工程协议原因与语义收益问题必须分开。
- 新有限核心对照已实现，**尚未prepare/launch**：
  `legal_contractnli_no_think_memory_source_20261018_run01`，固定同R2/全部前16合同，48新native/0教师；
  no-thinking同模空库、M2+R2、完整原源+R2。384只因旧协议失败被排为首个重放、全部16保留。
  首次若仍无效，原始成本保留后停止，不修补/重试；否则全48后统一效果分数。
  直接复用旧32原始结果作明确历史参考，不冒充新生成或新未见测试。
  协议`docs/NO_THINK_MEMORY_SOURCE_COMPARISON_PROTOCOL_20261018.md`，runner
  `experiments/no_think_memory_source_comparison.py`。冻结/双盘源码保全后立即后台启动，
  不继续空讲假说、不重开旧坏主训练。8B2261314/2261698仍不允许重启/下载/切换。
  Goal active，可信不同合同净收益、强成熟对照、独立重复及正式TEST全部仍未达成。

## 已归档的00:14状态（不是当前运行状态）

- 原主进程2769948/ticks425778700继续运行，不重复launch；首批已完整、已自动B2。
  00:10实际39/176native、1/4教师，B2 before第三源319；60冻结代码/输入绑定未热改。
- B1完整同8源ordinary/空库skills80.8824/54.2254/48.5294%，R1学后
  85.2941/51.0791/54.4118%。分类+4.4118、F1−3.1462、联合+5.8824pp，尚非证据学习成功。
  TP77→71、FP24不变、FN106→112。E/C/NM正确55/12/43→57/9/50；联合+8中7是NM、1是NN。
  源级F1胜平负2/2/4，描述性F1差区间[−7.3991,+0.5208]pp，不称显著或新案迁移。
- 首真实教师1389/high93.273秒，54951输入/4702输出(reasoning2588)，无缓存/工具/重试。
  CREATE8覆盖17命题，master1618/scope1814/实际单次准则1499tokens。
  其全8原源/Gold/own/原生M2候选和成员差分独立核对；学后8输入只增加完整准则，
  system/原文/模型候选/Schema/解码完全相同，未添加查询或修答案。
- 全B1原作者/32真实wire重算通过。8个gross真成员丢失中6由错判NM强制空引用，
  2为关系正确但漏引用；另有2真新增，净−6。原文口头限定SPAN56存在却改引52，
  混合识别规则的公开答案描述条件却返回NM，不能继续归因为缺原文、缺Gold或未交付。
  不据公开reason推断忠实内部推理，也不把8条一起变更归因到某一条。
  当前5个字面NotMentioned、旧坏库均0，不把删词/改标签当新根因修复。
- 新报告`docs/GROUNDED_CRITERION_B1_LEARNING_AND_EXECUTION_AUDIT_20261018.md`；
  完整audit双盘SHA`e302f83540b81f9c3acf84db9de66172fa291c7692a9c13edf228cbae717244c`。
  完整B1 phase archive双盘SHA`768605623236d90fcbc9c39af5c399105934c2a5629274c277ef954c5fa704e3`。
  下一完整节点B2 before24及R2 after16/旧8保持；不要因B1混合结果又开8案旁路或热改。
  Goal仍active：实质不同合同证据净收益、公平成熟方法、独立重复和正式TEST均PENDING。

## 已归档的23:35状态（不是当前进度）

- 固定R3诊断`legal_contractnli_r3_access_channel_diagnosis_20261017_run01`已完整成功，
  不是主训练完成。worker2725825/preserver2725826均已退出，全部16新回答、0教师。
  两盘232终态归档成员已核验SHA`aedafeec47ba1b205dbcc3466a11ed09aeecf0646f3f47192e96d3051ca0d3a2`。
  独立40答原作者/wire审计SHA`bf19f11c8431d4347b598e87595160a660ab53cf105f8a599fb912010f64a48a`。
  压缩R3为79.4118/35.4651/54.4118%，普通M2+同R3准则79.4118/54.0000/58.8235%。
  后者仍低于同M2的60.2871%依据F1，且E/C正确45/9→43/7、NM42→58，NN联合26→22。
  **尚未证明真正的法律正反关系/依据学习收益**。报告`R3_ACCESS_CHANNEL_DIAGNOSIS_RESULTS_20261017.md`。
- 据实际结果已修改唯一主链路：共享固定普通M2取证底座、进化判断与完整选证准则；
  删除主技能schema/actor/teacher中的source_queries与额外窗口，删除主run旧冷答复用方法。
  教师直接从保存的own native输入读取实际候选，而非事后缓存或控制臂可见性。
  原子增改删合并/NOOP、单次准则交付、完整原文、原SPAN及原评分全部保留；无额外模型/层。
  现有76链路检查6.98秒通过；32源空库own与普通输入/schema相等，最大普通prompt9947，0生成。
- 新完整在线run**已于23:34:29左右实际后台launch**：
  `legal_contractnli_grounded_criterion_learning_20261017_run01`，config
  `configs/contractnli_grounded_criterion_learning_20261017.json`、60冻结绑定，
  全176新native/4新教师、空库起步，无继承R3/旧回答。32源4批8案，不冒称独立重复或TEST。
  教师ledger1388/1400，4调用在原限额内，未重置。main2769948/ticks425778700，
  terminal preserver2769949/ticks425778701，完整边界observer2769950/ticks425778702实际live。
  23:35已1/176新native，B1 before617普通臂，0教师，无失败；不是效果结果。
  终态保全沿用已验证代码，仅扩展收录研究目录中的控制metadata；源码hash写入definition。
  观察器只在完整B2-B4 all-seen后看同一指标是否既比实际父库下降>=5pp、
  又低于同源累计普通对照>=5pp；满足双重退化才只SIGTERM原worker。
  不按B1坏分或跨案件批裸分终止，不回滚/否决技能、不动模型，不读部分相位分数。
  初始6537归档成员逐一验证并双盘，SHA
  `31e741ba9f2d82cae46eccd6ff49462826155a2e37808b672e0dd508d5387d72`。
  configSHA`77fe9ef2ea9c29b1a19734e18ec96fb5168e984806134c2e10047a74f28c8843`，
  frozenSHA`3c035f73bf2417f4652f6255fc9c1b754f3038d139ca5a48801fddc480d4f0f8`。
  实际launch及冻结输入已提交Git`3a36fbc86679ce17d2b502b06393d24814fe6f38`。
  完整Git bundle双盘SHA`e504dbaf80e784f61b3b3020a346a473a3d08ffd19981de2fc9b75d4ba030621`，
  receipt research `actual_launch_complete_Git_preservation.json`，SHA
  `e757974451eb2c53df0fa2e676be9c9bffee02387c00212a414060859775cba0`。
  初次bundle已成功生成，仅中文成功信息不匹配英文断言；原有效bundle经LC_ALL=C完整历史
  复核后复制，未覆盖/重新生成bundle、未中断训练，失败事实也在receipt中保留。
  没有证据表明新链路已解决8B执行失败；不能写方法有效。
  恢复看research `grounded_criterion_learning_20261017/actual_launch.json`和/proc，避免重复launch。
  **现在所有旧run均终态，新run冻结代码不可再随意修改；原RAM8B不能重启。**
- 23:47实际重新核实三个原进程均live/ticks匹配、60绑定不变，15/176native、0教师，
  B1-before尚未完整，不评分部分。前5源ordinary/空库skills的完整native请求和最终公开答案
  均逐字相同且raw ID各异；新receipt
  `actual_first_phase_live_identity_and_cold_wire_equivalence_20261017_2347.json`，
  SHA`32b7ef9a9c050af4df0205286cee386966c2ca2f4514d78a7dd58b70d3752ade`。
- 本Goal轮progress：真实核验历史matched-teacher intervention的18原观察/6配对/16终点，
  原作者集合重算一致；不能把同工具无技能反馈或本地CoT当作从未试过的修复。
  旧单次配对更新83.0882/70.5882/61.7647→82.3529/68.6695/57.3529%，不能默认部署。
  限定为一次旧接口更新，不能据此宣布所有组内学习无效；教师body两字段额外之外还附加
  system比较说明，不是整个请求只有两字段差。新audit双盘SHA
  `ebccbe1fa66b6a567f239d68a23e2b89665b676c42e118e9b7a103289e59b066`，详见
  `docs/MATCHED_FEEDBACK_HISTORY_AND_CURRENT_CHAIN_BOUNDARY_20261017.md`。
  当前run继续，不热改教师；下一重点实际首教师/后续新案，而非再造8案配对旁路。

## 已归档的23:05快照（不是当前运行状态）

- `legal_contractnli_member_learning_one_copy_20261017_run03`已于22:40:52.851
  在完整B4 before24答后安全停止，不再运行。真实120新native+24明确继承空库、3教师；
  没有第四次教师wire，没有R4发布，也没有completion。失败记录为现有安全handler的
  `InterruptedError('Operator stop at artifact-safe boundary')`，不是模型/网络崩溃。
- 完整B4空库73.5294/51.4851/47.0588%，普通M2为70.5882/60.2871/50.0000%，
  R3技能80.1471/28.0788/52.9412%（分类/Gold-NN硬micro-F1/联合）。技能TP57/FP218/FN74；
  其中624一源196误引，出现大片连续区间，零局部检索提示的问题也出现过选。
  不能归结为完全复制检索集合，不能用补充bullet列表解析解释这次误引崩溃。
- 原114冻结绑定未改。原main2518027、preserver2518028、边界观察器2629900
  均已终态。真实终态archive双盘全成员校验SHA
  `73087b422a4b10abbaa53569b7eb354cb9d8077ed43f6483a1d6c7a63f3811ba`。
  见research `member_learning_one_copy_20261017/terminal_preservation_completion.json`。
  B4完整原作者/wire复核SHA`9bed81660b588cd981bb929dfb2ad47f5b03793ddf457e76c75d65fe54a3399e`。
- 下一步为**固定原R3的交付诊断**，不是重启坏主训练或回滚R2：
  `legal_contractnli_r3_access_channel_diagnosis_20261017_run01`，两条件各原B4全部8源，
  共16新律师调用、0教师；原24回答作为明确历史参照，不假装新生成。
  一是保留全部访问事实/15条准则，改用可严格还原的三角色索引列表及编码说明；
  二是原普通M2输入只追加同一套逐字R3准则，不执行或交付库中查询。
  全16生成后统一评分，不中途看分改提示、不按效果选库。结果用于主链路全局修正，
  随后必须重新完整在线演化验证；诊断本身不满足Goal。
  协议`docs/R3_ACCESS_CHANNEL_DIAGNOSIS_PROTOCOL_20261017.md`。
- **诊断已于23:04:56左右实际启动**：worker2725825/ticks425601380，
  terminal preserver2725826/ticks425601382。23:05真实progress为0/16，首源362的compact条件。
  172冻结绑定、全部16输入原文/准则/访问角色还原校验通过，最大prompt16027tokens，0教师。
  启动前完整Git+源码6620归档成员逐成员校验，双盘同SHA
  `7c7dc2e20ec0ce269fce7364574c55fa4b7ab3ed7bf0c5f92feab20119863119`。
  receipt `artifacts/prelaunch_backups/legal_contractnli_r3_access_channel_diagnosis_20261017_run01.json`。
  恢复时检查research `r3_access_channel_diagnosis_20261017/actual_launch.json`、run progress及/proc，
  不重复launch、不热改冻结实现。8B2261314/2261698仍须保留，不重启无磁盘权重的服务。
- 23:11新核验旧run全部144答、完整32源首遇：空库75.9191/59.6728/49.2647%，
  普通77.0221/56.2633/51.4706%，技能77.3897/50.7806/52.7574%。技能仍未达标。
  技能原标签E/C/NM正确204/37/180，空库202/46/165，分类净收益掩盖了C类损害。
  全32审计双盘SHA`63bc94f15eeba21b7799876d814a10cacbd1c8cd130ea0870c0ad764f1eba60c`，
  报告`docs/B4_STOP_AND_COMPLETE32_PREQUENTIAL_AUDIT_20261017.md`。不改主指标/删除624。

## 已归档的22:19快照（不是当前运行状态）

- 唯一主run仍是`legal_contractnli_member_learning_one_copy_20261017_run03`。
  main2518027/ticks424752842、preserver2518028/ticks424752843实际live。
  最新98/152新native、另24明确继承空库、3/4教师；**B3已完整，当前B4 before**。
- B3完整新案首遇的R2技能相对同案空库三项均正：74.2647→80.8824、
  Gold-NN F157.5439→60.0760、联合40.4412→51.4706%。普通固定检索为81.6176/61.7284/50.7353%。
  不是稳定胜过普通工具或成熟方法；三个指标源级95%描述区间中，分类/F1仍跨0，非独立重复显著性。
- 新案分类19修复10损害，联合25修复10损害；联合净增15中10为NM、5为有依据题。
  TP82→79/FP47→28/FN74→77，F1收益主要为少误引，不能说事实召回已提升。
- B3 before原作者/wire完整24答审计已双盘，research
  `B3_complete_before_original_author_execution_audit.json`，SHA
  `b13a67e1b4eb73c63c886fe951cae5c5723562d6883d6ef26f824297fc164a2f`。
- R3教师1388已真实完成，105.906秒、171787输入/5685输出（reasoning3035），0缓存/工具/重试。
  3 CREATE+5 UPDATE，12→15条覆盖16命题，master3132/范围3336/单次准则2014tokens。
  其24源/Gold/24当前own实际wire复核通过；48可用own历史中24旧答未送。原技术定义技能仍逐字未改。
- 后续独立安全观察器**2629900/ticks425207406**已实际live。
  定义`tail_boundary_observer_definition.json`、启动`tail_boundary_observer_actual_launch.json`。
  只等完整B3 after（全部24及旧16）和完整B4 before24，再检查任一主指标配对下降≥5pp。
  这是开发止损，不是统计标准/技能准入；只SIGTERM原main现有安全handler，不动模型、不回滚库。
  B3 before三项正，原观察器已正常退出且未发信号。第一版观察器因解析venv软链误用系统Python失败，
  已保留日志/失败收据；第二次以未resolve的venv路径实际运行并完成，主训练从未因此重启。
- 模型仍是原RAM中的8B，2261314/2261698；磁盘权重已失，**禁止重启/下载/换模型**。
  114冻结绑定未热改，不重新prepare。当前R3最大actor prompt23888+8192=32080，未超32768；
  不能据此保证未来R4所有输入都适配，不做截断或fallback。
- **22:17完整R3 after24**：相对当前R2父库同案分类+2.451/F1+2.171/联合−0.245pp，
  旧16三项+2.206/+3.634/+1.103pp；本批8拟合分类+2.941、F1−0.766、联合−2.941pp。
  不称每项单调。实际R3全24为82.5980/59.3137/52.6961%；其中F1仍低于同24强空库61.6487%。
  full48原作者/真实wire/教师/保持审计已双盘，research
  `B3_complete48_original_author_teacher_and_retention_audit.json`，SHA
  `29819fb8f452f0cf59a401fbe1d08432828b1d3bf3410219c57c6ccdd8ffa302`。
  B3全部phase archive双盘SHA`f64c16ed6063f4af14858447fbeb014b08b5ba573221def87519fc87d7a84a09`。
  `tail_B3_complete_after_actual_result.json`实际未触发止损；观察器仍等完整B4 before，未重启训练。
- 前24首遇总分（不是R3全24拟合）：强空库76.7157/61.6487/50.0000%，
  技能76.4706/62.1455/52.6961%。不得只报B3好点或把整体微小增益当目标达成。
  319/nda-2在h2技能逐字未改下，R2 TP0→R3 TP9，仍漏12且误引31；不能冒称来自h2新技能修正。
- 本Goal turn属progress：得到不同合同真实三项净收益、教师R3及50个已提供却漏选成员的证据，
  据此继续原训练，而不是自动重写B1或部署未验证新结构。Goal完整目标仍PENDING。
  详细新证据见`docs/B3_NEW_CONTRACT_TRANSFER_AND_R3_PUBLICATION_20261017.md`。

## run03启动及已完成节点时间线（不是重复启动指令）

唯一当前主run：`legal_contractnli_member_learning_one_copy_20261017_run03`。
20:43:30实际启动，main **2518027**、ticks **424752842**；preserver **2518028**、ticks
**424752843**。20:43:54两真实句柄live；0/152新native、24逐字继承空库回答、0/4已闭合教师，
首次教师已在进行。用研究目录`member_learning_one_copy_20261017/actual_launch.json`与run
`progress.json`恢复，不凭旧文重新启动。**114冻结绑定已live，禁止编辑/再次prepare。**
config SHA `e8c6876c71ab4403db9fd24ff849c0acfb3846501bba146e8eab07a1c2a966f3`，frozen SHA
`6babebdbee0074226c02cee0322d3c7c322114ac753bcd3b9a1317502c6d800f`。
已有77无模型边界检查通过（7.45秒）和24完整原始请求/schema/解码/实际token逐字等价证明。
无模型检查不是效果证据。所有学后和B2-B4都是新回答；初始库空，不继承旧教师编辑。
完整源码/Git269404b与原始引用已在20:43:05校验双盘，3486项目/3488成员，同SHA
`859bbc2f9ef653231c667b6eec5c41e7a787d655009cc2e7be71f6ee70d81bac`。
receipt `artifacts/prelaunch_backups/legal_contractnli_member_learning_one_copy_20261017_run03.json`。
终态保全定义及actual_launch已实际存在；终态archive尚未产生，不称训练完成。
本轮重点后续不同合同prequential收益和同旧案损害，不因B1正收益夸大或因一批裸分降重启。

20:45首次真实教师1386已完成，41.524秒、55824输入/1631输出（reasoning1217）、0缓存/工具/重试。
实际CREATE1，`nda-copy-permission-polarity`仅适用nda-17、1查询/完整选择准则；master274、
scope379、实际单次准则208tokens。该题学前8案仅2分类正确、3C误判E/3NM误判E；
教师确实选择了高错误事项，不是代码规定每批只能一次编辑。实际完整末句、8个prospective
只交付一次；已闭合首1个真实native请求也相等。无部分效果评分，0新案迁移结果。
新research `actual_cold_reuse_and_first_teacher_input_audit.json`、
`actual_first_publication_and_one_copy_delivery_no_partial_effect_grading.json`保存实际守卫。
20:45:44 main/preserver尚live，B1 after第2案进行，已1/152新native+24继承、1/4教师。

**20:51:21已完整B1并自动进入B2；最新修订并未改善效果。** 学后分类69.1176、
Gold-NN micro-F150.0000、联合39.7059%，相对相同空库−10.294/−10.377/−11.029pp。
逐题均值F166.2827→52.1889%，完整正确非NM28→21，TP96→75/FP39→42/FN87→108。
8源F1仅1胜7负，分类5修正19损害。不得拿“格式已完整”当方法有效或隐藏这个负结果。
目标nda-17正确仍2/8，1修复1损害；其余128题4修复18损害，分类82.8125→71.875%。
实际准则明确“保留存档副本/记录复制不构成创建许可”，但617/147等公开答案仍作同样推断；
另有负命题公开理由描述禁止行为却输出C。可确认未可靠执行及范围外损害，不证明隐藏推理、
唯一串题机制、改字段或单题隔离必能解决。历史报告中的单题/排序负结论不等于本轮已核原始请求；
实际证据范围的收窄见下文21:09记录。去relation有独立原始回答，不盲目重跑。
独立从原作者TRAIN重数全部32actual wires/源/键/schema/成员，114绑定仍等，见新research
`B1_complete32_original_author_scoped_execution_and_outside_damage_audit.json`。
保持主进程不热改，让B2完整新案首遇和真实负反馈后的R2更新/旧案保持给出下一证据；
若大幅配对损害在完整B2再现，再整轮安全停止，不用一批坏分立刻重写B1或回滚挑库。
20:56:26真实main2518027/preserver2518028仍live，13新native+24继承，B2 before第2新案进行。

21:09:02新核对没有热改114绑定，main/preserver真实live，27新native+24继承、1教师；
B2 before完成19/24调用，尚不评分部分新案。新research
`actual_instruction_and_historical_experience_scope_audit.json`已双盘原样保全，SHA
`bfc2c6382a7fb12bdf41307fd0c063247c6daed2784f1fbff1bd5c337db287c0`。
实际system在空库/非空库完全相同，明确允许准则并要求命题极性/原文，不存在已发现的禁用技能指令。
具体纠错示范并非未试：旧corrective run实际使用原关系/纠正关系+原Gold/实际引用并集片段，
8源分类82.353→83.088/F167.257→66.667/联合55.882→60.294%；旧full-context16新案
85.662→77.574/F165.147→58.246/联合48.529→39.706%。不能又把加few-shot作为必然修复。
历史配对末次干预使用同工具空库对照而非全程固定工具的父→发布更新反馈；一次负面不排除所有配对学习。
**收窄“单题隔离已核对”的说法**：历史报告确有负结论，本轮定向搜索尚未定位该单题试验的
完整原始请求/配置；未找到不等于从未跑，也不足以彻底排除所有单题执行。去relation有实际独立8答。
不因文档结论或当前一批就自动部署单题/排序/例子/配对反馈；优先完成本轮B2真实演化反馈。

**21:25续Goal：完整B2新案首遇已独立按原作者/wire/原SPAN集合重算，仍为负。**
研究收据`B2_complete_before_original_author_execution_audit.json`，SHA
`07d3fa51258be2265059e63e86b4cefea45eb49e0d2cd15147c99b0fc9cd069b`，实际双文件系统同SHA，
全部24真实原始回答、原文/schema/解码/准则单次交付和114旧绑定核验通过，0新增生成。
空库分类76.4706、Gold-NN F168.3761、联合58.8235%；技能69.1176/66.9565/55.8824%。
分类9修复19损害，nda-17范围内1修复1损害，范围外8修复18损害；不能说唯一损害机制已证明。
当前新案nda-17为1E/7NM，没有C；R1范围内分类仍6/8，原正确E额外误选相邻SPAN导致严格联合损害。
426纠正了复制误判，384却把“副本须返还”当复制许可；不是完全不能用技能，也不是可靠执行。

21:15:38真实教师1387闭合，124.719秒、89400输入/6983输出（reasoning3714），0工具/缓存/重试。
实际UPDATE1+CREATE11，**发布12条，不是口头一度误报的10条**，覆盖13个公共命题；
master2307/范围2489/实际一次准则1478tokens，直接有效发布，无效果准入。其后16个seen答仍在进行，
只看完整phase才判断R2旧案保持及本批拟合，不用部分回答挑库。21:24:43 main/preserver实际live，
43/152新native+24明确继承、2/4教师，当前第12个R2 after答；未启动重复训练。

本Goal turn已产生新完整B2差分及教师窗口证据，属progress，不是只重述status。
`learning_inputs/update_b2.json`实际24条own历史中只传16条current-parent最新答，
原8条空库own答仍在归档，却未与R1学后答共同送入这次教师；完整Gold、各版本库及编辑历史确实已送达。
因此教师看到了当前错法，但没拿到同案完整前后表现，不能把它误称成全程版本效果反馈。
这不是已证明的唯一根因；旧`feedback_history.py`确实做过历史反馈，但其工具状态变化，
旧paired-final诊断又是同工具空库控制，不能直接当成当前固定无工具own版本转移已验证。
保留B2完整结果优先，再决定是否以忠实更新反馈修正学习窗口；不热改冻结代码、不退回重跑B1。
师兄paper-ideation本轮只用于“机制假设在哪失效”的接缝审查，不搬多智能体层、验证准入、固定三创新或热点包装。
外部版本差异和原论文反例另存`docs/SCIENCECLAW_TFGRPO_MECHANISM_AUDIT_20261017.md`。

**21:29 B2完整闭合，R2不是全面无效，而是分类回升与取证损害并存。**
本批R1→R2分类69.1176→77.9412/F166.9565→56.1576/联合55.8824→58.8235%；
分类6源胜2平0负，F11胜0平7负；逐题平均F170.8218→66.9158%。
旧B1 R1→R2三项69.1176→81.6176/50.0000→55.3846/39.7059→48.5294%，不能称整体遗忘。
全16 R2为79.7794/55.6818/53.6765%，仍未满足三项净收益。已开始B3新案首遇，继续同一2518027。
独立全部40本批wire/原作者/教师完整源Gold及实际窗口审计已经执行并双盘，research
`B2_complete40_original_author_teacher_and_retention_audit.json`，SHA
`6fd4eb9c398d0d508f4edfe5f54b90bac17cfae4fdb7631d4c945e181042a5d1`，0新生成、114绑定不变。

新证据分解：本批TP77→57/FP22→15/FN54→74。双方关系都对的46题TP66→47，
不是主要由改判NM清空造成。319 nda-2一题丢18个真成员，R2只引原31而理由说员工信息；
原31实际为披露形式句，员工信息在18。原Gold包含完整定义列举，不能删案或改Gold。
去每个来源的敏感性差值仍负；去319仅说明跌幅受其放大，不能代替主结果。
详见`docs/B2_LEARNING_SIGNAL_AND_EVIDENCE_AUDIT_20261017.md`。
暂不针对319加规则或改输出映射。先让B3完整不同合同首遇验证R2是否迁移，按真实配对损害决定停止，
不因单次分类回升就跑完所有批次、不因一题主导F1就宣称无问题。

## 已停止run02及run03修订前证据（历史，不是live状态）

**20:35已核实没有主训练live。** 上轮
`legal_contractnli_member_learning_tool_independent_20261017_run02`
在19:56:14 CST启动，20:25:23完成B1后安全停止；实际32native/1教师1385、0B2。
原main2447187、preserver2447188、stop watcher2488070均已missing，8B服务2261314/2261698不变。
终态双盘保全实际20:25:31完成，210项目/211成员，同SHA
`c1bf4315c507606b69d4650feb7ecdabf99d8c850f96016bde08e59fa84304bd`。
整32/原作者/wire/教师完整反馈/旧65绑定在改动前的独立守卫见research同目录
`complete32_original_author_teacher_profiles_and_terminal_guard_before_one_copy_repair.json`。

B1学前强空库79.4118/60.3774/50.7353，学后80.1471/66.8750/52.9412%（分类/F1/联合）。
这是8案拟合，不是新案迁移。分类11修正10损害；逐题均值F1反降66.2827→63.6297%，
完整正确非NM仍28，3联合净增来自NM；不可仅凭micro-F1报稳定正收益。
教师实际一条跨15命题准则，恰好1200字符/末句不完整，0查询；实际文本直接发布无后改。
同段重复15次占3171投影tokens。内容停止决定先于读取学后分数；不能说已证明宿主截断。
内容审计`actual_teacher1385_incomplete_capped_criterion_and_repeated_delivery_audit.json`。

现在完成同一维护入口的一次交付修订：去单条字符上限，保留全库4096；程序随公开适用命题
只交付一次，教师按真正共享检查组织，不定类别/数量，不修补历史文本。新config
`configs/contractnli_member_learning_one_copy_20261017.json`，协议
`docs/ONE_COPY_MEMBER_LEARNING_PROTOCOL_20261017.md`。新Run ID
`legal_contractnli_member_learning_one_copy_20261017_run03`，**20:41已prepare114绑定，20:43已备份/launch**。
24个学前完整实际请求/schema/解码/响应身份/实际token数逐字等价证明已经完成，0模型生成：
新research `cold_reference_exact_wire_equivalence.json`，不得重做prepare或编辑114绑定。
固定同32/4批，初始空库；逐字请求/schema/解码核对通过后显式继承旧24个学前回答，
计划152新native/4新教师+24继承，176逻辑回答；不继承旧技能或学后答案，非独立重复。
后续首要B2-B4新案配对收益与旧案损害，而非再次反复B1或展开baseline网格。

以下保留的是run02启动时的历史元数据，不表示该run仍live。
配置`configs/contractnli_member_learning_tool_independent_20261017.json`，SHA
`9358427e3c2438a90565444cac31dc20b80a352b1a4c9608b4620f5e56c88348`；frozen65文件，SHA
`87ef5426807e3b64456594ecb4eb9d415d0fdffbb0365244cabca6852cccf963`。
**这65绑定已随终态保全，不重新prepare或launch旧run。**
实际入口保持`python -m legal_skill_guard.learning.member_learning run <上述新config>`。
新research目录`artifacts/research/member_learning_tool_independent_20261017/`中的
`actual_launch.json`、`stdout.log`和新run的`progress.json`是恢复入口。

完整32原来源顺序/空库/4批/176新native/4教师，own不计算/接收M2候选或分数；ordinary仅
是显式控制。所有新教师只拿实际无M2 own反馈，查询可为空、条件检查准则可单独存在；
没有强制技能数量/增长。主要看B2起同案配对强空库收益与跨版本旧案损害，不只重复B1。
首次B1 skills与strong_empty是相同空库输入，但真实分开调用，不能把它当学习收益。

终态保全已独立后台启动：**2447188**、ticks **424469214**；定义/actual_launch在新research
同名`terminal_preservation_definition.json`、`terminal_preservation_actual_launch.json`。
逐字复用旧已成功watcher代码，仅新配置/身份/底包元数据不同；不做分数准入或模型重启。
等真正终态后产生`terminal_preservation_completion.json`；目前不称新176结果已完成备份。

19:59新research `actual_first3_wire_and_own_tool_independence_no_effect_grading.json`已独立核
首3真实raw/精确request/schema/原文、3不同raw IDs；实际own无M2候选/分数，实际空库own/
strong_empty输入及公开回答相同但不共享raw。65文件仍相等，未对部分B1评分。真实学习收益待。

这轮先核新真实wire的source/Gold隔离/own无M2与native合法性，不提前评分部分B1，不再加
固定库拔工具/案例演示/位图等旧负实验。首个教师后核实际程序/准则发布、17原命题完整
反馈与真实交付；B2/B3及同旧案更新效果才决定方法是否有用。主方法未取得稳定净收益前
不扩张baseline网格，不把启动/75边界例/更多技能当作Goal达成。论文强对照、重复与TEST仍缺。
当前格式没有used_skill_ids输出；历史metrics里的reported_skill_use_queries=0不表示技能未交付。
新记录可仅有准则、0查询，查询hits=0也不等于无技能。以真实wire的准则投影、查询回执和
原生输出变化分别检查交付、定位与效果，不把自报或交付本身当因果使用证明。

20:06完成评分口径核对，未改变65绑定或运行指标：research
`official_metric_alignment_20261017/closed72_original_hard_evidence_metric_alignment.json`。
原作者官方代码固定commit `058c56fd62d56897bb4fcfbf1be71b17aee3a79c`，源码SHA
`f5acd4497e002652b2f29a6827fecd355b96ec041c4c174b1938eea2f8c42cf4`；只执行审阅过的
纯evaluate_predicted_spans函数，不导入其模型/loader、不读取官方DEV/TEST。
旧已闭合72回答/16来源/8组P/R/F1与官方Gold-NM排除的硬成员口径逐组1e-12内相等。
完整17命题等来源分母时，总准确率也等于按命题宏平均准确率；C/E类别F1不是依据F1。
官方任务明确要求全面识别冗余依据，所以不能将只选最小证明改称完成了原任务。
但原论文§4.2主报证据ranking mAP/P@R80，不是硬集合F1；不能拿本项目F1与其mAP比大小，
也不能借控制M2分数伪造主方法未产生的逐SPAN置信度。联合全对是本项目额外严格终点。
此核对只排除评分口径错误这一解释，不是新训练效果或SOTA证据；继续关注内容/执行。
该官方实现的原版权头和完整Apache2 LICENSE也保存于该research目录，仅作独立评分核对，
不成为运行依赖。当前训练不因此新增置信度字段、模型调用、评估门槛或主指标。

旧run `legal_contractnli_discriminative_evidence_full32_retention_20261017_run01`
18:25:37 CST完整完成，原worker2249247和保全worker2265836均已missing终态。
规范新调用计数`actual_new_native_teacher_calls:[48,0]`，另继承16个逐字相同实际回答，
共64不同raw，32原始已学合同配对。全部wire及原作者成员集合独立重数通过，0invalid/length。
**是固定库已学后保持，不是新案迁移、独立训练或四批学习曲线。**

| 条件（完整旧32） | 准确率% | 原SPAN Gold-NN F1% | 联合严格正确率% |
|---|---:|---:|---:|
| 技能 |85.294|66.734|56.618|
| 固定普通检索 |82.353|62.359|53.676|

净+2.941/+4.375/+2.941pp。分类39修正23损害，联合45修正29损害，真成员58增33失，
假引用25增39去。逐源F1 22胜4平6负；分类14/10/8、联合15/10/7。分类/联合区间跨0，
不能宣布稳定。第2原分组分类/联合为负；4组依据差值均正。分组不是学习曲线。
275漏证中224发生在分类正确时，context-only Gold仅采用13/118，取证尚未解决。
完整结果与全部变化在`runs/<旧run>/completion.json`，不可删坏结果或按分数选库。

终态保全已实际完成18:25:54：research目录
`full32_terminal_preservation_completion.json`，470项目文件/471成员，全部成员SHA核验，
两个不同文件系统同SHA`69a9db2ead1a1346029c97172209e88702fe5bc430884c07a529eaa48779d3a3`。
文件名`<旧run>-actual-terminal-recovery.tar.gz`。原317绑定未在运行/保全中修改。

新run **`legal_contractnli_member_learning_online_20261017_run01`**：

- 维护入口`python -m legal_skill_guard.learning.member_learning run configs/contractnli_member_learning_20261017.json`。
- 实际prepare及launch均已完成，**不得重复执行**。18:35:12 CST后台启动，worker
  **2326429**、start_ticks **423983002**；恢复时核真实`/proc`句柄，不只看状态文件。
- 实际launch/progress：`artifacts/research/member_learning_online_20261017/actual_launch.json`、
  `runs/<新run>/progress.json`；日志research同目录`stdout.log`。已冻结57文件。
- 19:44:22按已声明的整轮停止安排安全终止，实际72native/2教师；B2 after16完整，B3
  0native/教师。原main2326429、保全2328367、stop2415582、CPU控制2344522均已核终态。
  progress中的failed是安全handler的InterruptedError，不是协议出错或完整176调用完成。
- 新32源固定、空库起步、4批各8案，每批24真实before（空库/普通/技能），之后对全部seen
  8/16/24/32真实after，共176新native/4教师；不继承旧bank、raw或B1 aliases。
- 教师看所有seen原文/Gold及逐版本最新current-parent own，旧raw归档已教过；不按正确性选。
- 当前batch before是前向新案使用，after是拟合/保持，单独对同一旧案计算更新损害。
- 所有有效CRUD/NOOP/null直接发布；没有8案probe的“无准则终止”诊断guard。
- 协议`docs/MEMBER_LEARNING_ONLINE_PROTOCOL_20261017.md`；生成前已完整源码/Git双盘保全。
- 实际launch/progress为准，恢复时检查真实PID和ticks；观察超时不等于终止，绝不重复启动。

终态保全也已后台运行：worker **2328367**、start_ticks **423990359**，定义和实际launch
在新research同目录`terminal_preservation_definition.json`、`terminal_preservation_actual_launch.json`。
复用旧32已验证的保全程序，仅改3个run路径；成功/失败都等原worker真正终态后复制
全部闭合结果，实际完成须看`terminal_preservation_completion.json`，不凭计划说已备份。
现该receipt已实际完成19:44:28：341项目/342成员，完整校验双盘同SHA
`4a3efd38e898a109bf21b2ce0d129de6a36057cc6446dff2c093b59b80360aae`。
`complete72_original_author_terminal_and_R2_all_damage_audit_before_source_repair.json`又独立重数
全部72真实wire/原Gold/唯一raw；确认旧57文件在编辑前均未改，两盘整包SHA/设备及四原worker终态。
新research`old_trial_terminal_and_frozen_source_before_repair.json`记录正式编辑前守卫。

## 历史查询/准则库的已完成证据（不作为当前初始库）

下列是前版历史输入/固定库的证据，当前无M2主方法和真实空库起步见最上方。
历史8案/32案实现仍在research的`evidence_contract.py`、`run_study.py`，不作新主入口。
没有把以下旧技能库、回答或教师发布注入新run。

下列历史固定bank SHA：`36d640efa852f94a4a374d37866a493435b186c7903e44498f5a72be875a4fb4`。
出版物：`runs/legal_contractnli_discriminative_evidence_skill_20261017_run03/publications/b5.json`。
8 UPDATE，16→16记录，8条准则覆盖9原命题；master2997/scope3225/准则投影427 tokens。

完整8已见TRAIN，32新native/1教师，0invalid/length，独立原作者及实际wire核算通过：

| 条件 | 准确率% | 原SPAN Gold-NN F1% | 联合严格正确率% |
|---|---:|---:|---:|
| 完整技能 |86.765|77.457|69.853|
| 同库同查询/角色、仅隐藏准则 |80.882|73.118|60.294|
| 无技能＋固定普通检索 |82.353|71.856|59.559|
| 强空库 |80.882|59.296|54.412|

同普通检索+4.412/+5.600/+10.294pp。分类净增6题全为source295净贡献，其余7源
合计0；不可说稳定。F1逐源5胜1平2负，联合5胜2平1负；NN严格联合31vs25，
不全是NM收益。相对隐藏准则，净真成员少1、假引用少12，主要是减少误引；context
Gold仅引2/15，且多数分类收益发生在准则scope外，不称语义隔离或完整取证已解决。
分类/F1对ordinary的8源条件区间跨0；这些区间不是独立学习稳定性或正式显著性。

核算/分析/全部损害原文在上述run的 `monitoring/`。原始8案不删、不手写case规则。
之前run02实际2native/教师1381因没有真正发布任何准则、消融两臂逐字相同而停止；
所有失败、出版物及成本保留。不要把它计作成功或抹去费用。

## 已停止V1新32：B1历史结果（不能据此继续旧run）

| B1同8原始合同 | 准确率% | Gold-NN依据F1% | 联合严格正确率% |
|---|---:|---:|---:|
| 学前强空库 |82.353|63.300|52.206|
| 学前固定M2，无技能 |83.088|54.348|52.206|
| 学后实际R1 |81.618|50.179|52.206|

首次1383教师51.969秒，63225输入/3093输出（reasoning2547）、0缓存/工具/重试。
实际CREATE1，nda-7第三方披露，8查询+真实选择准则，master408/scope512/投影140 tokens。
已独立核对实际teacher wire：完整8源/原Gold/136 own判断/全部成员对照，0未来/其他臂答案。
编辑schema没有“最多一次操作”限制；不按技能数量强制增长。

同案学后净少2分类，联合3修正3损害；真成员5增10失。h7的Gold16，C覆盖3，C∪P覆盖12，
却仍只引用5真成员（与学前相同），且分类2修正2损害。所有NN Gold183，C仅71，R1仅扩至80；
学后66 C成员+3额外成员+1池外=70 TP。普通检索已在学习前降低F1，不能把它算成技能学习退化。
说明此轮同时存在薄弱的固定检索覆盖/候选依赖及新技能使用不佳，不再声称缺Gold导致。

独立审计research同目录：`B1_before24_actual_teacher_and_equal_label20_original_audit.json`、
`B1_complete32_actual_source_member_and_all_harm_audit.json`。全部B1评分、6个分类损害公开回答保留。
B1不理想不直接重启：当前让同一真实R1进入B2不同合同，且B2教师会获得实际R1负面反馈。
若B2/B3在新案和同案更新中重复系统性损害，应停止整轮诊断，不硬拖/回滚/换案。
下一改动候选须优先检查固定M2前提是否持续伤害完整取证，而不是继续加提示字段。
移除这一前提尚未实施，也不能在查历史实际无工具分支前宣称“从未试过”。
mandatory source_queries>=1可能偏置选证型技能的表达，但这是未证实的机制假设，不据此强制多技能。
已失败的稠密/稀疏位图、强制检查、单题、support/refute不包装为新招；完整历史源示例交付
也已实现并负面（`legal_contractnli_contextual_experience_online_continuation_20261017_run03`），
旧研究记录“尚未实现fewshot”已过时，不能重新据它安排同样实验。

19:19完成当前重建acquisition/member家族的实际输入清点：research同目录
`canonical_family_all402_actual_wire_M2_independence_inventory.json`。9个run共402个不同真实
native raw，逐项request/schema与显式prospective payload相等；其中242个非空库输入全部
使用同一固定M2，未发现这个具体链路下非空库独立于M2的已执行对照。不是全部已删历史、
其他技能表示或其他法律任务“从未试过”的证明，也不证明去M2必然有用。
初版清点没解析114条的metadata.path、漏纳88条旧inline接口；保留初版及明确更正的完整402版，
不能把初版unknown算无M2。当前新run仅纳入已闭合B1，无B2部分质量评分。
此前scored/unscored实验仍保留普通候选；不能用它代替这个缺口。

这个清点改变的是下一次根因干预的优先级，不立即插入新GPU实验：先取得B2完整新案/更新/
旧案结果。若仍重复系统性损害，才对完整预定案件及同一实际父库分离普通候选依赖和已学
准则/定位的作用，不重采案件、不再先换教师或追加标签、不另建路由或输出修补层。
现有source_messages可在records编码下接收无proposals；scored_records则需要原M2分数。
若未来主方法去M2，必须同步从真实own payload重建教师的候选/漏证反馈，不能继续把
self.proposals中的控制臂候选谎称为own可见。当前运行所有own仍有M2，这不是当前反馈失真。

## B2当前闭合证据、已执行停止安排和下一版

B2 before24在19:25:26完成，8新合同：空库74.265/69.027/56.618，普通M2
77.206/55.172/58.088，R1技能74.265/52.683/55.147（准确率/F1/联合%）。
相对ordinary分类8修复12损害，联合7修复11损害，真成员3增5失。M2只列出50/131 Gold，
R1扩至51但额外Gold采用0。已独立检查24 actual wires、原作者集合、完整16源/272 Gold/
16 own及所有成员对照的真实teacher2 wire，无未来/其他臂。完整审计research同目录
`B2_complete_before24_original_author_wire_and_actual_teacher16_audit.json`。

真实教师1384耗78.694秒，107206输入/4257输出（reasoning3624）、0工具/缓存/重试。
R2仅UPDATE原nda-7技能，8查询/1准则，master466/scope570/投影152；并非schema最多一次操作。
全16已见Gold314，仅nda-7有准则；该命题Gold25，查询覆盖18→21、总返回91→120。
未标注读取不等于错误证据，不能以覆盖增长冒充真实after收益。
内容和执行审计：`B2_actual_teacher_publication_content_and_seen16_acquisition_not_native_gain.json`。

19:35已后台设置**整轮在B2闭合并双盘保全后安全停止**：worker **2415582**、ticks
**424343200**。定义/actual_launch：research同目录`planned_B2_boundary_stop_definition.json`、
`planned_B2_boundary_stop_actual_launch.json`。核精确原PID/ticks后，仅向main2326429发SIGTERM
触发现有安全handler，不向模型服务发信号。结果须看`planned_B2_boundary_stop_actual_result.json`；
发出请求不等于已经终态。可能竞态产生的B3在途答案也完整保留，不隐藏。
这是两批持续M2依据损失后的整轮开发决策，不按R2分数挑库/回滚。原终态保全worker继续。

下一版已在原维护入口完成核心修订、零模型检查、prepare与真实launch（当前状态见最上）：
`configs/contractnli_member_learning_tool_independent_20261017.json`、
`docs/TOOL_INDEPENDENT_MEMBER_LEARNING_PROTOCOL_20261017.md`。新Run ID
`legal_contractnli_member_learning_tool_independent_20261017_run02`。
保持同32来源顺序、空库、4批/176native/4教师、同8B/解码/原任务/Gold，不继承旧库或答案。
skills自身不计算/接收M2候选或分数，ordinary仅作显式控制；records交付现有真实定位/角色。
技能可独立含有条件的法律取证程序、可选查询，不要求每条附查询，也不强制数量或类型。
教师候选/成员反馈同步依据真实own payload；同一教师内给原命题聚合原始成员错误，不加模型。
以强空库为主要对照；新开发episode不是正式TEST或成功方法的独立重复。

跨表示历史负证据**不能漏掉**：`legal_contractnli_M2_tool_influence_20261015_run01`
6实际新native/0教师、12实际引用，旧库直接拔M2后76.471/49.630/31.373，保留M2时
80.392/63.281/40.196，空库76.471/55.814/32.353。故不声称“拔工具”从未试过或一定有用，
也不再跑固定旧库拔工具网格。下一版是从空库按实际无工具执行/反馈重新学习，带可选
定位且取消强制查询限制；旧无工具复核/程序方法同样保留，不把本次改动包装为全新原语。

R2完整后新8为76.471/52.736/56.618%，旧8为80.147/54.286/49.265%。原8在R1→R2中
分类7修复9损害、联合5修复9损害；新8真成员2增3失。全16分类16修复15损害，联合12修复
14损害，F1仅53.638%。所有17个分类或联合损害已带原文保留，不把F1上升说成整体修复。

旧trial及原保全全部终态后，才修改3核心：`member_contract.py`、`member_learning.py`、
`acquisition.py`。取消强制查询，writer从“定位ONLY”的旧替换串改为一致的法律检查契约；
own输入不计算M2，teacher真实候选取own payload；两张重复派生错误表改为完整成员对照+
命题聚合，原文/Gold/公开回答/全部实际访问/编辑历史保留。没有新增运行时模型或输出层。
新增3个零模型边界例并入原test文件，原75 tests在7.18秒全部通过；严格teacher Schema检查
及6个member相关例0.36秒通过。初始anyOf缺少strict对象约束已在预约教师之前修正；未产生
失败教师调用。3个源码ruff通过，旧测试文件16个既有样式问题不做无关改写。

19:52:15真实prepare完成，**65冻结文件**，0native/教师；不得再次prepare同一配置。
新research`implemented_source_and_input_contract_check_no_generation.json`核32 source-only空库
输入、空库skills/strong_empty逐字相等、旧R2只用于8案编译检查未预置新库；最大空库8964
tokens，query读集合完整/无M2分数。不是未来所有库的容量或效果保证。当前预约仍1384。
prelaunch已真实完成19:54:46：3598项目/3600成员、完整Git b5789b1无前置，完整65绑定+
旧72raw/2教师，两盘同SHA `f6ccaff4b29220747ddefd9719506c46c562fe294fe3c9eeaeb3eb7e60aa1a7a`。
receipt在`artifacts/prelaunch_backups/legal_contractnli_member_learning_tool_independent_20261017_run02.json`。
随后19:56真实launch及独立终态保全均已完成，身份见最上。不再重复启动或模型资格测试。

## 旧32完整漏证/损害审计（不是新32成绩）

`artifacts/research/member_learning_online_20261017/parent32_membership_and_all_damage_audit.json`
完整保留35个分类或联合损害问题的Gold、原文成员、两臂公开理由、分数、角色和raw引用。
该报告实际执行源码保存在Git `00b86e39f65d8708bc5a8dfb06bd333ab29b57f1`；之后只整理
该分析脚本的导入/重复IO/风格，未重跑模型或改报告。勿用当前源码SHA冒充历史执行SHA。

65个Gold>=3问题：技能分类60正确、联合仅2正确；漏160/246真成员。Gold=2问题漏90，
两类合计250/275漏证（90.9%）。这指向多成员完整返回的缺口，不是已证明唯一内部原因。
普通候选中的真成员相对ordinary新得7、丢24，不能只归因于低分额外邻居；例如603定义
已高分可见且准则要求带定义，却只返回操作条款。360独立重复支持也只返回其中一处。
完整系统提示本来已要求全部冗余支持，故不能把“再加一句收全依据”包装成新根因修复。
其余损害包含条件/例外、近题混用及公开理由与标签不一致；不称所有损害来自教师错规则，
不依据局部摘录改Gold，也不据此手写案件例外。新空库四批是当前实际验证，不修改运行库。

## 本次新32在线学习的数据与对照材料

`artifacts/research/discriminative_evidence_new_contracts_20261017/`：

- 当前bank逐SHA追溯6个真实发布至空库，祖先教学来源合计仅这32案。
- 排除bank32及普通检索器训练12案后，seed2026101702从剩余379个原作者TRAIN抽32案。
- `source_only_reserve32_inputs.json` 是原文/id/spans逐项相等的无Gold输入。
- 选择未使用标注值/得分，TRAIN容器为提取来源曾被解析，不声称从未解析Gold字节。
- 与44案交叉及内部496对都无原文/分词序列完全相同项；词5gram相似度仅源诊断，
  不是语义等价证明，未据此重选。正式DEV/TEST仍未打开。

此reserve不是新验证集或技能准入集，也不是已完成迁移结果。现已接入上述真实空库
四批学习；当前仍未完成，不把旧继承库或新run的启动称为独立重复成功。

公平监督量控制：`artifacts/research/same_label_ordinary_control_20261017/`。
仅CPU用原作者44案拟合同架构普通检索器，7.12秒，748原始配对，同超参数/0查询，
无新encoder/教师/律师权重更新。它未替换当前M2，未生成新合同回答或成绩。
未来推理请用 `ordinary_equal_source_label44.inference.manifest.json`（有规范state_sha256），
不是原始fit元数据；模型SHA已独立核对。它控制唯一来源/标签访问量，不代表算法
容量、算力或成熟方法已公平比较完成。这个44案模型只匹配当前“旧32案bank＋12案
背景工具”的静态迁移比较；新空库episode或后续在线更新的对照必须按其实际已揭示
来源重新拟合，不能只因总数相近就称监督量匹配。

新32自己的prefix控制已实际后台启动：worker **2344522**、ticks **424055060**。
程序research同目录`fit_revealed_prefix_controls.py`，定义/实际launch为
`prefix_control_definition.json`、`prefix_control_actual_launch.json`。18:49实际live等待B1发布。
只在真实b1/b2/b3/b4 publication存在且教学source IDs逐项相等后，CPU拟合12背景+8/16/24/32
已见源（20/28/36/44案），0native/教师，无query/新encoder/主M2替换。未来前缀从fit排除；
完整TRAIN容器会被解析，不声称未解析未来Gold字节。每个真实fit自动双盘校验备份。
首个20案fit已实际完成18:59:08，340原配对，实际204.421秒，非先验估计7秒。模型/参数/IDs/
未来24排除及双盘归档已独立核查。后续28/36/44仍等待真实发布，尚无control native成绩。
不是主方法或成熟方法胜利；与旧44案控制的具体来源不同，不可混用。
源定义和超参数不按分数选择；主worker终态且等不到下一发布时，它记录已完成前缀并退出。
CPU首fit曾64线程/32核超配；已核PID/ticks后短暂停同一worker，全部64线程限定30/31两核并
原PID恢复，没有fit重启/参数变化/主链路修改。暂停19:00其实已在首fit完成之后：初始“pickle
仍在写”的假设错误，准确时序单独保存在`prefix_control_actual_completed_fit_and_pause_timing_correction.json`，
原记录不删不改。后续核CPU只查这一个2344522句柄，不重复启动控制。

## 必须保持的执行边界

- 唯一工作树 `/media/sangfor/vdb/legal-skill-evolve`，hhy入口 `legal-skill-current`。
  `/home/yndx/hhy/legal-skill-evolve` 是另一个旧恢复树，不要混写。
- 8B服务 **2261314**、engine **2261698**；原权重磁盘文件已删、仅原服务RAM存活。
  **绝不重启/下载/切换模型**。同Qwen3-8B/BF16，seed45/T.6/p.95/k20/max8192，thinking开。
- 当前M2仅原12案，状态 `c0d59bbe7fa962b43f7ee3fe5adff98c6134c37419483263355be23fc881edb8`，
  pickle SHA `8453c3ed11bc02e4cc46b5b425399a2e2a3dbcc294a47d19b870cd91867a96c9`。
- 现有gpt-5.6-sol/high教师账本上限1400，当前预约序号1384；历史计数含已声明下界。
  不静默重置/加额，不增加付费API。旧online已实际2教师，安排B2后整轮停止，不再预约余2。
- 不恢复客户路由，不改法律任务，不加fallback/答案修补/效用准入/最好库回滚。
- 正式TEST不调优；全部不利结果和成本保留；不得把prepare、source编译或schema通过当效益。
- 5个既有untracked报告目录属于用户，不删不合并。

## 可恢复源码与结果

当前新主链路的完整源码/完整Git（无增量前置）、完整旧32实际结果、57冻结文件：
`legal-member-online-fresh32-prelaunch-full-source-and-Git-20261017.tar.gz`，3273项目/3275成员，
Git `449383e06691740d9f70190a8cc88e4b24c807e3`，
SHA `5cd674ec64467dcfa23babd441608952e9f35771b7866ced0189c126fabc32de`。
实际receipt：`artifacts/prelaunch_backups/legal_contractnli_member_learning_online_20261017_run01.json`。
两文件系统逐成员/整包SHA及完整Git bundle核验通过；不含尚未生成的新176答案。

首批完整32真实native/1教师及根因审计、Git449383e之后至e88c1ec的增量已实际双盘保全：
`legal-member-online-complete-B1-and-root-audit-Git-e88c1ec-20261017.tar.gz`，
SHA `d8a67d7a4241da3b1a7fb233a7e20033f3503500a6f01be82dbee43e5b0ecd0e`，107项目/109成员。
research同目录`complete_B1_and_root_audit_verified_backup.json`。它要求上述449383e完整底包，
不是独立全量；19:19的402输入清点在其后生成，尚不在此增量里。

2026-10-17完整源码/完整Git（无增量Git前置）＋完整8案raw＋新317绑定：
`legal-complete-eight-fourarm-and-full32-prelaunch-full-source-and-Git-20261017.tar.gz`，
SHA `2e47f06c5c0eee567ec023f1f534c9fc4c34bcee7298378b6424fe0e0d2fb10d`，3096项目文件。
同SHA已校验在 `/media/sangfor/vdb/legal-skill-backups` 和
`/home/yndx/hhy/legal-skill-rootdisk-backups` 两个文件系统。
这是同服务器备份，不是异地、权重、auth或整机快照；旧hhy下backup软链不是第二磁盘。
旧48调用终态归档已完成，见上方实际receipt；新176调用终态保全仍在等待，不能混称完成。
