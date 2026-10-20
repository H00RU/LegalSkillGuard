# 当前 Goal 执行索引

更新：2026-10-20 08:44 Asia/Shanghai。Goal active，未完成，无外部阻塞。
**最高优先纠正：下文旧v10已因确证EOS约束缺口在07:47:30停止，43native/1教师，
B2未完整评分/未读Gold。8B同服务已重启为PID3613253并健康；依赖修复已通过真实
失败前缀/有效回答的CPU检查，无新GPU资格生成。新Run eos_aligned已冻结136源
绑定并于07:55:50真实后台启动，主PID3621135。不要恢复旧v10或旧8B PID3889231。**
这是续接入口；每次以真实 systemd/PID、冻结清单与原始工件重新核验。
旧轮已经计划终止，新契约已真实部署并启动，不要误恢复旧 v9 或另建 GPU 队列。
上一版详细索引保存在 Git ddb98e7；原失败、协议、审计、双盘备份均未清理。

## 完整目标与用户追加要求

同一冻结 8B 因可复用、可管理、持续进化的技能，在后续新案及最终隔离 TEST
上强于同权限/预算强空库及可信成熟经验方法，形成可复核论文证据。任务和主方法
仍开放，但不每遇负点就换任务重启 B1，不把小试正点、启动成功或技能数增长当成功。
OpenExempt、重放、数值程序本身不是原创；最终贡献必须有真实机制与公平对照支撑。

- 用户本轮提醒已经加入 active Goal 的[生效补充](research/GOAL_ADDENDUM_SKILL_EVOLUTION_20261019.md)：
  每批查真实教师 CRUD、拒绝/发布、父子 hash、内容、token、实际送达/执行及新案损益。
  未发布不算学到，文本送达不是因果证明，函数调用数也不是收益证明。
- 任务需有法律意义、覆盖与合理迁移。聚焦不自动无效，广泛任务也不自动证明泛化。
  不把同案 EC/EV 算两个独立数据集，不从豁免小试外推通用法律能力。
- 不另设验证集。全已见 TRAIN 重放/准入就是训练优化，不称独立验证或泛化。
  训练标签辅助已授权；当前全部控制臂先预测完才读 Gold，无未来/TEST 标签。
  反复调优看过的案例始终是 TRAIN，最终冻结方法/库后才评隔离 TEST。
- 正式样本量须按覆盖、来源级方差、效果量与完整成本事先冻结。12/24 来源小试
  都不是足量论文实验；仍缺成熟公平对照、独立学习重复、不确定性与冻结最终 TEST。
- 不新增付费服务/模型/32B/第二实例，不恢复客户路由，不加 fallback、答案修补、
  Gold solver 推理或无关框架，不选好案/旧好库/改评分造提升，失败与成本全保留。
- 师兄 paper-ideation / paper-experiments-appendix 用于实际失效假设、机制日志、
  公平成本与结论边界；不采用隐瞒借鉴、固定创新数或预设好指标。当前 Goal 轮已完整读。
- 每小时以实际时钟复核五件事，记录在生效补充。最近实际 **08:28:10，下次09:28**。
  07:01批次续记不是额外小时检查。无独立唤醒产品；训练独立后台运行不依赖对话。
  卡住先定位原始失败，再查近期权威原文/作者实现并落实，不空转调研或重复资格测试。

## 当前唯一后台主训练：EOS对齐后的v10接口三批小试

- Run **legal_openexempt_eos_aligned_online_20261020_run01**；unit
  `legal-openexempt-eos-aligned-20261020-run01.service`，原主PID **3621135**，
  **07:55:50** 启动。07:56:37亲核active/running、B1首预测中、0完成native/教师。
  不把启动/CPU检查或旧B1的重放分数称作本Run表现。没有新GPU资格生成。
- config `configs/openexempt_eos_aligned_online_20261020_run01.json`及同名frozen.json，
  SHA **b89e23cfd2154671dbf117a20ba4dcc77f536ca11e08cafb603d72dccd11be53**，
  source commit **762301b**，**136绑定**先双盘核验。绑定活跃期间不热改。
- 同一模型服务unit `legal-qwen3-8b.service`，现PID **3613253**，原权重目录、
  版本和全部启动参数原样。profile `artifacts/live_8b_environment_EOS_aligned_20261020.json`。
  新增六个实际依赖源hash每次调用核验。只修EOS定义，没升级模型或另起实例。
- 根因：模型generation_config EOS为151645/151643，采样器两者均认；旧HF语法
  默认只认tokenizer151645。实际74_EV_skills以151643在未闭合JSON结束；CPU真实
  前缀确认该token仍允许。实际后端修复后两EOS在坏前缀皆禁、完整好回答皆可终止。
  这是格式保障缺口，**不解释所有法律错误、不保证技能收益**，不回改失败分。
  复现diff `patches/vllm-0.10.2-hf-generation-eos-alignment.patch`与third_party/vllm/NOTICE。
  修复模块SHA673dc25710d9f59c42baa2c0e4e665b48aa8c1a3b8f9670a89af649875fe49da。
- 数据73–84共**12来源/24任务/3批各4源**。旧流未反馈的73–80全部原顺序保留，
  seed2026102004只补81–84四源，排除七旧packet，无看标签/效果重抽。73/74已有
  无反馈四臂观察、75仅frozen EC，config明列；76–80未查询。**标签未释放不等于
  输入从没查询**。不导入旧回答/cache/分数，不带旧C1，仍同blind C0开始。
  packet SHA **df4bf51b0ec6758d11bdc7072bad6da56c5cc57e54137518e5c98e1dc2e493d3**。
  当前新批全部四臂预测前不读Gold/私有construction，官方TEST未打开。
- 法律接口、四臂、采样预算、教师/两候选/4096容量/有界证据和全TRAIN准入均
  沿用下述v10。B1还是静态先验，进化看B2/B3；两个强控制都使用正确EOS环境。
- 新日志 `artifacts/research/openexempt_mechanism_20261019/eos_aligned_run01.log`；
  启动 `eos_aligned_run01_launch_receipt.json`，source与runtime修复/启动10工件已双盘。
  协议 `docs/research/OPENEXEMPT_EOS_ALIGNED_20261020.md`。**仍非正式规模或Goal完成**。
- 只读观察session **27566已结束**，B1全四臂08:22:45落盘；不要再resume该句柄。
  08:41:21已真实发布B1的C1并自动进入B2，32native/2教师/16跨阶段wire别名。
  唯一主PID3621135与模型PID3613253均仍active/running。新只读观察session
  **45152**从08:30:06起，最长至09:15:06，每10秒核同一主PID并报告不可变批次/
  候选/发布；观察超时不等于训练失败，不据观察终止重启。B2整批未完成前不读Gold。
  A40持续约23GB/49GB、97–98%忙；不是GPU不可用，也不是指标突破证明。
  下一动作是真实准入/发布及B2/B3前向，不开第二GPU队列或资格网格。

### 08:28：新B1完整实绩、真实技能内容与当前未解断点

|B1，原宏F1百分数|EC|EV|完整输出EV|
|---|---:|---:|---:|
|程序empty|69.0972|34.1667|34.5238|
|强直接数值empty|69.0972|63.6806|64.1667|
|同blind C0 / online|66.8750|57.0139|57.3214|

在线=B1初库，对C0进化效应0；对强直接empty两项均值**-4.4444pp**，不是突破。
强程序empty的74/75真实非法算式原样0分，不能只凭击败该控制宣传有效。
20物理/32逻辑前向，131246prompt/56140completion。带库EV逻辑轨迹真实调用
10次存储程序、3次inline；C0与online同wire别名，不算20次独立程序行为。
完整输出claim为带库13正确/0多余/25漏项，对照直接empty17/4/21。
整答拒绝按无可接受预测补足漏项的次级统计：程序empty7/4/31，原评分未改变。
当前主要损失是覆盖不足而非已证明的数值计算失败，调用数非收益。

教师1在08:23:39真实返回UPDATE3（Federal/PA/OR），改顺序化分类/通用条款指导，
40程序体均不变；44166input/3244output、53.621s，历史账本seq1501。
教师已收到父库3462tokens/4096上限/634剩余空间。**还在重放，未发布**；不得把
提案当新库或训练重答当新案。73_EV本地思考列四资产，最终仅提交住宅，且使用
了未向演员明确说明的JSON字段层级；另有Fed/PA/OR通用条款在推理本身就遗漏。
两种断点并存，不能全部归因于语法/知识或直接断言隔离caller候选能提升。
全部136绑定未改变；90个原始B1/教师/审计工件已逐成员双盘核验。
审计`eos_aligned_B1_actual_skill_generation_use_and_control_audit.json`及preservation。

正式足量/独立学习重复/成熟同权限方法/合理迁移/隔离TEST均未完成，仍无验证集。
下一个决策依据是候选真实差分、完整TRAIN准入以及B2/B3后续新案净益；不因冷
B1负差停掉健康学习、不盲扩128、不按已知Gold补单案，沿用连续伤害/系统故障
止损。完整目标不缩小，小时复核下次09:28。

### 08:44续记：B1实际发布与已落实、未采用的caller修正

B1第一提案UPDATE3被拒：重答EC69.0972/EV50%、完整EV50%，两好两坏四平。
74_EV修到100%但73_EV空算式失败、75_EV在表达式内重复到8192，原样0分。
6物理重放43597prompt/21999completion，5stop/1length；IL76两任务同wire复用。
不能把这个length归为教师输入截断或只因提示变长，教师对此的归因尚属假设。

第二提案仅UPDATE联邦技能，40程序体不变；08:41:21通过准入并实际发布C1：
**7条/40程序/3475tokens，SHA d716b7d3c4da5f408b090e025ac52a26b2e365b1f5718335bb91ad7a180167dc**。
已见TRAIN重答EC70.6845/EV60.5556%、完整EV60.4167%，两好一坏五平。
改善是75_EC57.7778→73.0159、75_EV40→66.6667；73_EV12.5→0，不能略去。
可核验成功回执中12次存储调用/3次inline（含3次IL原生别名下重新执行），不代表
失败动作此前尝试过的完整调用数，更不代表新案收益。Fed wildcard在本候选EV
成功回执仍0；修订意图不等于每项已被8B执行。6物理重放43093prompt/12966completion，
全stop。第二教师53346input/2073output、cached11392、seq1502，非新增第三候选。
新案B2正在运行，不能拿训练重答对比强empty宣布泛化；本Run尚未有后批分数。
原始两提案/重放/发布/审计54工件逐成员双盘核验，审计
`eos_aligned_B1_actual_publication_training_effect_and_remaining_failures.json`及preservation。

隔离候选新增提交**6d8a083**，接在ccb5108/899252e之后：inline生成schema与既有
execute_limit的非空/512字符边界对齐；不是剪输出、重试或扩大有效表达式集合。
两项原有测试0.21s、Ruff通过，无新测试模块或模型调用。实际安装xgrammar0.1.23
用三个原始失败/有效输出的CPU完整schema前缀检验：新schema拒73空串/75超长串，
仍收74有效输出。使用小RAW词表的字符串匹配，**不是Qwen token-mask或8B表现证据**。
第二提案73的短非法字符串仍可满足长度边界，不能称长度约束解决了所有语法/语义。
6源/检查工件双盘，receipt在隔离树`bounded_inline_prepared_not_adopted.json`和
`bounded_inline_preservation.json`；原活跃136绑定全未改变，**三新提交均未采用**。

本轮已实际读到ScienceClaw固定e925f732的agent/prompts.py和agent/solver.py，
不是之前失败的tree读取：其真实提示明确Deliverable schema、Operator签名与契约，
技能在公开任务之后。借鉴接口可见性，不复制整图框架/parse重试/隐藏验证择优或
验证集；排序差异不构成注意力失效的因果证明，本候选未叠加改排序。
若当前多批终态后需要诊断caller，只用事先记下的两已见TRAIN见证：73_EV/C0、
75_EV/empty，同8B/预算/事实法律、0教师、只改公开调用合同。不当新案成绩或
另开资格网格；当前继续B2/B3真实进化，仍非正式规模、成熟方法胜利或Goal完成。

### 08:22补充：本轮实际进度和隔离候选，不要混成已采用方法

08:22亲核同PID，19 native/0教师，B1最后76_EV生成中；27566仍等完整四臂。
当前没有再次出现JSON未闭合，但程序empty的74/75有真实非法算式，原样判错。
强直接数值空库保留，不以赢这些错误程序为充分收益证据。当前批Gold尚未读。
公开事实覆盖已核：B1两N1/两N2，B2四N2，B3两N1/两N2；本12来源没有Arizona
案件，不能从完整法条语料包含AZ就说案件覆盖了六法域。裸批次难度变化不等于
库回退；仍看同案C0/两个强控制与实际技能变化，不调整样本顺序。

当前caller消息删除整个operators、只在schema区分cached/inline；缺少调用清单，
也没有明确展开JSON字段层级。实际empty74写冒号前缀数值、75把引用写成算式。
这是可证实的信息边界/无效动作，不证明单一根因或新接口能提高F1。
独立分支`prospective-compiled-call-20261020`已准备**ccb5108+899252e**：EV只暴露
citation_ref调用签名、隐藏id/程序体，明确原有assets/claims层级与标量字符串类型，
EC不变、纯程序更新保持原生wire不变，不增加路由/模型/新测试模块。只在现有测试
补断言，2项定向CPU检查0.14s通过，0模型/教师新增调用，**尚未合入活跃主树**。
当前136绑定完整未变，不能称此候选已被8B采用或取得指标改善。先看当前多批结果，
后续若采用须新冻结，不以新假设即刻停止健康运行或反复重启B1。
隔离工作树仍`.venv/compiled-call-20261020.2VOZzd`；最新5工件双盘归档
`compiled_call_contract_preparation_20261020-typed_citation_interfaces_not_adopted.tar.gz`。
receipt在该树`artifacts/compiled_call_contract_preparation_20261020/typed_interfaces_prepared_not_adopted.json`。

补充报表审计：失败EV没有TP/FP/FN字段，缺失不能按0相加。旧已释放B1的程序
empty本应在整答拒绝口径计8漏项，而不是raw有效记录的2，差6来自拒绝70_EV。
原F1/完整每案F1/准入未改，不改活跃评分。审计和双盘收据
`compiled_skills_B1_rejected_answer_counter_completeness_audit.json`；新公开分布
`eos_aligned_public_debtor_and_legal_context_coverage.json`，均在研究前缀。

## 已结束的v10 compiled小试及其真实证据

- Run `legal_openexempt_compiled_skills_online_20261020_run01`。
- unit `legal-openexempt-compiled-skills-20261020-run01.service`，原 PID **3543668**，
  2026-10-20 **07:03:32** 启动，**07:47:30**因真实EOS缺口安全停止，不是分数挑库。
  B1于07:25:56真实发布C1；07:28:55为31 native/1教师、13跨阶段wire别名。
  B2全部四臂完成前不读其Gold。两个旧只读观察1185/34771已正常退出0，不再resume。
  旧观察96460已经正常退出0，168终态成员和原运行时六文件已双盘核验。
  43物理/1教师，B2没有完整分数或标签释放。不要重启这个Run。
- config `configs/openexempt_compiled_skills_online_20261020_run01.json`，
  SHA9498bb2f029f9cbe168ac368cafd21d2d6ed2a8ed8c9b6b0c1769e5aa37becfa，
  同名 frozen.json **134绑定文件**；启动前 source tar 已逐成员双盘核验。
- source implementation commit **9c15c8d**；采用四提交 4be939c / 714fb3d / 0a4faa1 /
  9c15c8d，对应隔离分支18cc817 / cef7142 / fc595de / 8dc67b8。
  新 Run 活跃期间不热改绑定源码、协议、config、输入或初库。
- 新来源 **69–80，12源 /24 EC+EV任务 /3批各4源**，seed2026102003；
  排除全部六个旧开发 packet source keys，一次生成，无按标签/模型表现重抽。
  packet SHA41b10b70e571bcab387a37e6fd7f79f71d84734fae32e3ca567f1d7989866619。
  不读未完成批次 Gold、construction 私有类别或官方 TEST。
- 初库仍 blind bank02（7条/40程序/3462tokens），不是旧训练 C1 或好候选。
  模型仍同一冻结 Qwen3-8B，T.6/P.95/K20/seed45、thinking ON，
  8192 completion/32768 context；教师同现有 gpt-5.6-sol/high，历史账本不重置。
- 同一模型 unit `legal-qwen3-8b.service`，PID **3889231**、engine3889870，
  A40约26GB/49GB，127.0.0.1:8000/v1；权重b968826d9c46dd6066d109eabc6255188de91218。
  不因客户端 venv 缺 xgrammar 而重装模型服务；服务环境已有 xgrammar0.1.23。

### 新契约到底改了什么

1. 8B仍独立选择法律资格、引用、资产名和值，完整公开法条和AE法域先验不变。
   已存程序的法条显式null调用，未存法条原生inline；移除给演员重抄的operator字段。
   宿主不选资格、不补漏法条、不改名字/数值，不以函数存在判断适用。
2. 请求相同只复用**原生response**，每个库重新解析/执行并绑定execution_bank_sha256；
   不复用已算答案、评分或旧执行错误，不把wire别名算独立生成。失败照实记错，不重答。
3. 教师当前案全部提供、旧案最多16源，按公开法域见证/拒绝提案退化/父库失败固定选，
   明列选中/未选ID，引用只允许实际提供者。**准入仍重放全部已见TRAIN**，非证据子集。
   教师收到完整父库的8B tokenizer实测tokens、4096上限和净增长空间，不提高容量。
4. 四臂固定轮转：程序empty、强直接数值empty_direct_numeric、frozen_initial、skills。
   直接数值空库自行回答金额、没有解释器/修补；EC同empty完全相同则记真实别名。
   该控制不作为额外示范给教师。四臂全部预测后才读本批Gold；不是k=4组内探索。
5. 每批最多两教师提案，每个可多次CRUD；全TRAIN两家族及全输出EV非退步且当前严格
   改善才发布。前向连续伤害从B2起、至少B3判断，比较两个空库与C0；B1不是在线收益。
   无实际发布/调用/后续新案净益时，不以计数进步或盲目扩128案替代解决机制。

协议：[新三批机制运行](research/OPENEXEMPT_COMPILED_SKILLS_20261020.md)；
设计：[数值执行与教师证据](research/COMPILED_NUMERICAL_CALL_CONTRACT_20261020.md)。
18项定向CPU检查通过、1项上游评分检查未在隔离树运行，原评分没改；
没有新GPU资格网格。这不是8B性能证据，接下来查真实运行。

### v10已完成B1，已真实发布；不要与旧v9 B1混同

B1前向为初库，不含在线学习效应：C0/online EC70.4167%、EV78.3333%、全EV72.5%；
strong直接空库67.9167/77.5%、全EV72.5%，程序空库67.9167/65.8333%、全EV60%。
程序空库70_EV写字符串"null"，非法动作整答0，失败原样保留，不修补或削弱强控制。
20物理/32逻辑（EC直接与empty共享，online与C0共享），133762prompt/32731completion。
skills逻辑EV实际程序调用11，非11次独立模型生成；不是学习收益证明。

教师首提案**UPDATE3**（Fed/AZ/PA），程序体全部未改；初批69–72四个公开事实
都是单债务人，不能据此说已学共同债务人规则。教师实际42499input/3641output、
58.911s，输入107840字符，收到实测父库3462/4096tokens、净余634，无未来来源或
直接数值额外示范。第二提案没调用；不要误续成首提案只有2个UPDATE。

候选完整8物理重放全stop，57572prompt/11478completion，13次真实程序执行无错误。
TRAIN EC70.4167→74.1667、EV78.3333→85.8333、全EV72.5→80%，2好0坏6平。
**逐案更正：改善的是70_EV0.5→0.8和71_EC0.65→0.8，不是同一来源两任务。**
初步审计/小时记录曾人工误写集中70，原件不覆盖，corrected审计与gain_source_correction
明确更正。总体分数/Help-Hurt原本正确，不能再沿用错误归因。
07:25:56发布C1，7条/40程序/**3599tokens**，
bankSHA **f224a7ea133b0ca2e9bbfca4dda4dee4d00bd76c31f03ffce664c084af2b55ef**。
这是TRAIN优化，不能混成B1前向曲线或新案迁移，B2才检验在线对C0净益。

未解内容/执行风险：教师Fed指导仍要求对某些已缓存引用改用inline，而v10此时只
允许null；原教师规则已要求无法统一表达则去掉程序，候选没遵守。当前案例尚未
证明这个例外导致分数损失，不后验改接口/偷读未来标签，但不称形式正确即完整可用。
72_EV的原生本地8B reasoning对家具/衣物映射正确，最终却多加错误vehicle/apparel
引用，父子两次皆有。69的首饰泛化、70的"联邦更多所以舍弃PA300"、71漏wildcard
则在推理本身已发生。不能一概说法律知识不足、全部是输出格式或只贴72号补丁。
本地原始reasoning保存在raw calls[0].response；normalized response与教师视图未带它，
不是文件丢失。此信息边界不证明加CoT就会修好。若后续重复吞掉收益，优先检验
任务目标/决策到提交的断点，不再只扩写法律 prose、金额函数或加教师输入。

## 已结束 v9：完整六批前向，不是最后一批更新完成

- Run `legal_openexempt_official_sampling_online_20261020_run01`，
  原 unit `legal-openexempt-official-sampling-20261020-run01.service` /PID3085974。
  01:52:27开始，07:02:14计划终止，247物理回答 /10教师 /35跨阶段wire别名。
- 06:48:53在B6完整结果前记录开发停止计划；guard 07:00:31仅SIGTERM旧主进程，
  第10教师已发出，正常等到返回，再在artifact-safe边界结束。没有停8B。
  systemd exit1和failure中InterruptedError是预定人为停止，**不是模型故障**；
  最后教师126953input/6693output、103.823s照计，未重放/发布，不当已学到。
- 原158冻结绑定在合入前全未变，871终态成员已逐文件双盘再核验。
  boundary guard现已正常退出0，不重启旧队列。只读观察39052/25393等已退出。
- B1发布C1（10条/40函数/4008tokens），B2–B5均无更新；全文本修订存在有益修复
  与其他决策漂移抵消。B4第二4113、B5第二4206超过4096、未重放，效果未知。
  父库仅88tokens净空间，旧教师没收到实测用量。缓存函数实际调用始终0。
- B3 AZ车辆30000确实修成15000，却新错投影仪，净分持平；B4 AZ范围3好0坏5平，
  Fed相关3好16坏3平，但未后验抽好部分发布。不能说教师完全学不会规则。

以下全部是旧v9前向原宏F1百分数，不与新v10曲线拼接：

|批次|程序空库EC/EV|冻结C0 EC/EV|在线EC/EV|
|---|---|---|---|
|B1|80.83 /65.28|72.01 /69.44|72.01 /69.44|
|B2|42.08 /54.79|46.04 /52.08|64.79 /50.57|
|B3|67.92 /45.83|72.08 /69.58|85.83 /77.08|
|B4|77.92 /79.17|70.76 /71.04|83.89 /74.17|
|B5|65.56 /61.39|55.83 /60.56|68.89 /76.94|
|B6|47.22 /36.11|75.97 /57.92|84.03 /65.56|

六批24源累计empty63.5880/57.0949%、C065.4514/63.4375%、online76.5741/68.9600%。
B6对C0三好零坏五平，EV完整claim TP/FP/FN为online13/2/11、C010/3/14、empty8/4/16。
这支持B1文本学习后保留跨案收益，但不证明持续进化、强直接数值空库胜利、
统计显著性、足量规模、成熟方法优越或TEST。B3/B5增益集中少数案且对手有非法
动作0分，敏感性和原失败均保留，不据好总分撤销已预定停止或挑选好库。

## 下一直接工作和证据路径

优先核EOS新Run的真实执行/预算与教师CRUD，继续B2/B3前向，不只看B1、旧案
重答或函数计数。持续核新库是否真实发布、纯程序更新是否重新执行、两个强空库
及同C0是否都净胜、帮助/伤害和完整成本。明显系统性错误先保全终态再修；
真实负效应按预定边界，不挑案修补、第三教师或换解码削弱空库。
小时复核09:28。正式规模及创新判据见[下一证据门槛](research/FORMAL_EVIDENCE_NEXT_GATE_20261020.md)，
该草案旧计算量是v9三臂；v10额外直接EV必须计费，不能当同成本。

研究前缀 `artifacts/research/openexempt_mechanism_20261019/`：
- 新日志 `compiled_skills_run01.log`，新启动 `compiled_skills_run01_launch_receipt.json`。
  这两个是已停止旧compiled流；当前新日志和启动见上方EOS小节，不要混用。
- EOS实际失败与修复：`compiled_skills_B2_74_invalid_JSON_actual_EOS_grammar_CPU_check.json`、
  `compiled_skills_EOS_repair_actual_backend_CPU_receipt.json`，终态/原runtime双盘收据
  `compiled_skills_EOS_safe_terminal_and_original_runtime_preservation.json`；新runtime/启动
  `eos_aligned_run01_runtime_repair_launch_preservation.json`。首个CPU会话31909、修复
  CPU57874、模型重启10645、数据生成10411均已成功终态，不再resume或重复prepare。
- 新B1权威审计 `compiled_skills_B1_publication_actual_skill_use_and_training_effect_audit_corrected.json`；
  小时 `compiled_skills_hourly0728_actual_direction_review_corrected.json`；归因更正
  `compiled_skills_B1_gain_source_correction.json`。原错误版本和备份保留，不沿用错误归因。
  B1/小时123成员及更正3成员已双盘核验。原生推理/最终错位
  `compiled_skills_B1_local_reasoning_vs_delivered_answer_readonly_audit.json`。
- 旧六批 `official_sampling_B6_complete_forward_actual_use_and_cumulative_audit.json`；
  B5最终 `official_sampling_B5_final_rejections_actual_management_and_budget_audit.json`。
- 停止 `official_sampling_B6_boundary_development_stop_plan.json`、stop_signal/guard_outcome；
  终态核验 `official_sampling_B6_terminal_verified_before_source_adoption.json`。
- 新source归档 `legal_openexempt_compiled_skills_online_20261020_run01-source.tar.gz` 两盘，
  freeze清单绑定134成员；旧终态归档871成员，源/检查早前归档全部保留。
- 新运行目录 `runs/legal_openexempt_compiled_skills_online_20261020_run01/`；
  旧运行目录与原始Gold/回答/教师/拒绝全部保留，不迁移成新Run成绩。

repo `/media/sangfor/vdb/legal-skill-evolve`，hhy软链legal-skill-current。
双盘 `/media/sangfor/vdb/legal-skill-backups` 和 `/home/yndx/hhy/legal-skill-rootdisk-backups`。
Git runtime在 `/media/sangfor/vdb/legal-skill-forensics-20261015.pr9fln/git-runtime/usr/bin/git`，
须配同根usr/lib/git-core的GIT_EXEC_PATH。五个用户untracked reports不清理。
隔离worktree `.venv/compiled-call-20261020.2VOZzd` 早先四提交已采用；新增
ccb5108/899252e/6d8a083调用清单/类型/边界说明**尚未采用**，详见08:22与08:44小节。不是第二个运行
项目，暂保留注册状态，不递归删除或恢复旧32B/ContractNLI队列。
