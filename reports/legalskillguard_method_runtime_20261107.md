# LegalSkillGuard 主方法与开发验证

<!-- current_live_status -->
Current snapshot: Goal active and incomplete. Previous code-v1 and typed-v1 builds were stopped and preserved at69 and5 committed sources, respectively; neither has an accepted primary model IR. Current phase: fixed128_declarative_build_live. Current compiler uses the canonical typed AST with source-keyed nullable scopes, finite provenance and input-first declaration order. Truncated responses provide complete-prefix errors only, never reconstructed IR. Latest settled probe: executor_ast_typed_operands_v1_20261107. Thinking remains OFF. Current runtime passed518 offline checks and8 installed-backend syntax checks; these are not semantic method scores. Coherent original fixed128/8-batch build, six-arm DEV, core mechanism and cross-bank evidence remain incomplete. Fallback and exact reused teacher material do not establish core success. No TEST or paper work has started.
<!-- /current_live_status -->

<!-- current_train_prefix -->
## 当前统一版本的TRAIN前缀

更新时间：2026-11-07T17:30:35.079981+00:00；仅统计已结算的12个来源。

| 指标 | 当前结果 |
|---|---:|
| 已提交来源 / 原定来源 | 12 / 128 |
| 已完成批次 / 原定批次 | 0 / 8 |
| TRAIN匹配（含允许的回退） | 1 / 12（8.33%） |
| 无回退的TRAIN匹配 | 0 / 12 |
| 接纳的模型IR | 0 / 12 |
| A条件完成证书来源 | 0 / 12 |
| B模型IR路径实际执行来源 | 0 / 12 |
| 回退来源 | 1 / 12 |

回退答对和回退中的存储图调用单列，不计核心机制成功。IR接纳或条件证书也不单独证明源文语义忠实。[当前指标JSON](rr_method_runtime_20261107/training_metrics_status_20261107.json)、[来源状态CSV](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_source_status.csv)保留分母与路径；下方其他科学版本分别保存，不拼接成绩。
<!-- /current_train_prefix -->

## 前10来源的完整响应定位与输入审计补齐

第10个ContractNLI来源的首响应正常stop，输出1921 token、耗时70.684秒，通过实际wire schema和规范解码，但未通过编译。[原响应离线重放](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_ContractNLI_complete_output_audit.json)确认：模型将20个公开段落逐个复制成字符串binding，未生成观察、计算节点、scope或条款；查询把已声明的s19（公开假设原文字符串）用作布尔条件，实际类型诊断为expected=boolean、actual=string。另有未翻译的条件前文s8，查询没有读取任何受保护条款输出。原提示已要求对应类型和guard，编译器拒绝与之相符；不是未声明变量，也不是正常执行后的错误。第二响应达到8192上限而不完整。两条输出原样保留，不补法律规则、猜类型或用答案修补。

本次还修正了一个报告层核验缺口：旧实际发送审计仅在旧code接口下比对完整源单元，对当前结构化接口跳过该断言，旧收据的对应字段为false。现已在未绑定的报告脚本中对当前每条请求强制比对原TRAIN公开units、dataset、task_id及task_metadata，并保留[修正前收据](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_dispatch_audit_v1_before_public_unit_assertion.json)。前10来源20次实际请求全部一致；[离线负例](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_dispatch_audit_v2_regression.json)只在内存副本删去最后一个源单元，确实被源文完整性断言拒绝。未修改原请求、响应或账本，未新增模型及oracle调用；正在运行的科学源码、配置和seal绑定不变。

这两项证据分别定位模型输出错误和报告验证缺口，不将离线审计通过计作A/B成功。继续同一封存版本的原128来源/8批建库，再完成原定DEV与机制审计；不增加数据、种子或逐样例提示扫描。

## 已结算前12来源实际提供了哪些B学习输入

公开任务输入与内部可执行输入分开核对：前12来源24次实际请求均包含完整原公开源单元，未发生源文裁剪；但当前没有接纳的模型IR，真实A残余/分离批次后续请求仍为0。下表按本次前12来源快照列出B入口状态，[机制与逐来源记录](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_mechanism_prefix_audit.json)持续保存具体来源、候选数及原始记录SHA。

| 数据集 | 来源数 | 当前B入口证据 |
|---|---:|---|
| OpenExempt | 3 | typed_inputs_unavailable；模型源程序连接候选0 |
| Airline | 3 | typed_inputs_unavailable；模型源程序连接候选0 |
| SARA | 2 | typed_inputs_unavailable；模型源程序连接候选0 |
| ContractNLI | 2 | 原协议无反事实oracle；预测另有IR失败，不能混为一个原因 |
| ProofWriter | 2 | 公共Horn输入；1次碰撞识别模式、1次无新碰撞，模型源程序连接候选0 |

当前零候选停在类型化源程序入口，不能表述为“B已检查这些法律/数值连接器但没有效果”。记录里的primitive_source=model_source_linked_inputs标记预定路径，并不证明已有可用类型化输入；实际生成、执行和完整检查的候选数另列。已有oracle视图被读取或回放也不补造缺失IR。ProofWriter的一个已存模式为entity_equality/join_on的参数化连接形状，当前只有回退中的同库实际使用，未学得新的法律规则或数值连接模式，尚无外库实际复用。上述内容来自现有代码和原记录的离线核对，不是新增模型实验，也不添加验收门槛。

## 历史版本训练指标复核（2026-11-07，原时点快照）

| 独立科学版本 | 已提交来源 / 原定来源 | TRAIN匹配（含回退） | 接纳的模型IR | 核心主路径匹配 |
|---|---:|---:|---:|---:|
| code-v1，已停止保留 | 69 / 128 | 3 / 69（4.35%，均为回退） | 0 | 0 |
| typed-v1，已停止保留 | 5 / 128 | 0 / 5（0%） | 0 | 0 |
| AST v2，独立单来源修复验证 | 1个原定来源 | 未评分，输出未完整 | 0 | 0 |
| 输入优先AST，独立单来源修复验证 | 同一个原定来源 | 未评分，输出未完整 | 0 | 0 |

以上版本不混合统计，未完成来源不当作已评分错误。最新AST v2输入3344、输出8192 token，240.810秒，finish=length；已完整的条款段出现重复名称，尚未生成bindings及后续字段。之前来源数组无限重复的尾部已消失，生成仍因重复条款声明而截断；不补齐JSON或缺失语义，不算执行器运行错误。实际HTTP、原源文及锁定OFF配置一致，见[实际发送核验](rr_method_runtime_20261107/executor_ast_scope_v2_20261107_dispatch_audit.json)与[原始失败诊断](rr_method_runtime_20261107/ast_scope_v2_length_diagnosis.json)。

当前typed-v1前缀形成1个entity_equality/join_on连接形状，来自既定Horn输入，后续实际图调用0；不能据此宣称学会法律规则或跨库迁移。当前两版建库没有A残余/分离批次或B模型IR主路径成功；原128统一建库及六臂DEV仍未完成。493项离线检查全部通过属于工程回归，不等于主方法效果。

历史完整旧版TRAIN为59/128（46.09%），92/128（71.88%）走fallback；该分数只作旧版材料核验，不能充当当前修复版本的训练结果。[原时点指标快照](rr_method_runtime_20261107/training_metrics_status_20261107_before_ast_build.json)保留各版本分母和证据。该次状态复核新增模型调用0，原始结果、请求账本及冻结库未改；Goal保持未完成。



## 首个TRAIN匹配：回退中的真实同库图调用

第9个ProofWriter来源在两次模型IR输出均截断后进入原方案允许的受限Horn恢复，原TRAIN语义匹配通过。执行trace记录28次query_relevant的已存entity_equality/join_on图调用，均发生在这一个来源中；模式支持来自当前前缀第4个ProofWriter来源，属于同库存储模式复用，不是28个成功来源，也不是跨库迁移。两次模型请求输入合计7454、输出16384 token，耗时合计950.271秒；恢复没有新增模型请求。[原始记录/调用及路径核查](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_first_fallback_graph_use_audit.json)保留source记录、hash、实际graph调用与物理请求。

截至前9来源，TRAIN匹配为1/9（11.11%，来自回退），回退比例1/9，核心IR接纳0/9、无回退匹配0；A真实后续选择0、B模型IR主路径0。日志中的B=true仅表示该恢复路径实际执行了存储图，不作为核心机制验收。未用这个匹配宣称主训练就绪，原128/8建库和六臂DEV仍未完成，未启动TEST或论文。

## 其余四库的曝光与实际复用边界

前8个已结算来源中，ProofWriter识别的entity_equality图已在ContractNLI、OpenExempt、Airline、SARA四库后续来源的实际提示里提供，实际图调用仍0。[四库曝光核查](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_four_bank_exposure_audit.json)逐项列出消费者来源、原模式来源和证据类别。当前只能报告曝光，不能称为迁移成功，也不能称为已经测出“无效迁移”或负迁移；尚未有实际外库调用供原定开发对照及必要最小屏蔽诊断归因。未为此追加模型请求、来源、种子或额外对照矩阵。

当前前8来源均未接纳IR，16条实际HTTP已核对；第9来源仍按原预算解析。原128/8建库、六臂DEV与机制语义验收继续，所有失败作为结果保留，不因本次审计或少量样例结束Goal。

## 法律数值来源中的连接模式曝光

第6个来源为第二个OpenExempt来源，已获得第4个ProofWriter来源识别的entity_equality/join_on模式；两次请求后仍无接纳IR，未实际调用该图。当前已确认ContractNLI及OpenExempt两种外库来源的提示曝光，实际复用0；不能将公共模式在提示中出现称为跨库迁移，也未据此声称受益或负迁移。[OpenExempt逐请求/曝光核查](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_OpenExempt_exposure_audit.json)与[机制前缀审计](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_mechanism_prefix_audit.json)保留原始来源和实际结果。运行按原顺序继续，数据、配置及8ea35e0绑定实现保持冻结，Goal未完成。

## 五库首个来源与原协议数据边界

当前统一版本已结算前5来源，五库各1个；10条响应中9条length、1条stop，接纳的可执行IR、A/B主路径与TRAIN匹配均为0。第4来源的完整wire因真实引用语义错误被拒绝，其余为生成未完整；这些不是执行器运行后产生的错误，也不据此前缀推断剩余来源的成绩。[来源及请求矩阵](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_complete_prefix_failure_matrix.json)持续保存各阶段、token、耗时和原始哈希。

ContractNLI原协议明确automatic_gold_variants=False、formal_completeness_claim=False，当前no_counterfactual_oracle是原有数据边界，不是缺失的工程接口；它的两条预测另因8192截断未形成IR，不能混为同一失败原因。该来源确已曝光到ProofWriter前缀识别的entity_equality图，但实际调用0，不能据混合输入或曝光声称跨库复用。[协议/曝光核查](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_ContractNLI_scope_and_exposure_audit.json)同时保留两项事实。本次不追加来源或反事实gold、不改变正确性条件；运行持续，尚未完成原128/8、六臂DEV和核心机制/跨库验收。

## 首个完整响应与B连接模式的前缀证据

当前第4个ProofWriter来源第二次响应正常stop，输入3783、输出2826 token，102.784秒；完整JSON通过当前wire schema，但源文观察引用未通过编译器检查。[完整响应逐字段核查](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_first_complete_output_audit.json)发现16个predicate与所引单元不匹配、9个entity与所引事实不匹配；多个is/needs/sees统一引用了不含该词的s14，部分entity其实是规则或查询。不是空白格式误差，不能靠无歧义空白适配恢复；候选原样保留，不替换来源、补实体/谓词或借答案修复。其余完整类型/规则诊断也保存，未将wire通过计作IR执行或核心成功。这说明失败不仅来自输出token上限。

该来源的B获取路径从既定公共Horn原语及4条已有碰撞视图识别出entity_equality，对应join_on(column0)的参数化连接图a0e975c…；与历史库同形。当前仅证明该组件在新前缀中识别/保存了连接模式，不是新法律规则，尚无预测中的实际图调用或跨库复用。[前缀机制审计](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_mechanism_prefix_audit.json)将原语来源、重复发现、曝光和真正执行分列。前4来源8次实际HTTP均与封存输入/配置一致；A/B主路径及TRAIN匹配仍为0，按原固定版本继续后续来源。

## 统一AST版本建库的已结算前缀

当前原128来源运行继续。已结算的前三个来源分别为OpenExempt、Airline、SARA，各使用原定两次请求；六条均finish=length、输出8192 token，尚未形成接纳的IR、执行、A/B或TRAIN匹配。此为生成不完整阶段的失败，不能归为执行器运行错误，也不据此推断未完成来源的结果。[实际逐来源/逐请求矩阵](rr_method_runtime_20261107/method_runtime_ast_v1_20261107_complete_prefix_failure_matrix.json)列出原始响应哈希、token、耗时、失败阶段和原学习状态。控制器存活、科学绑定不变，按原顺序继续；不增加来源、seed、第三次TRAIN请求或针对单条样例再调提示。

## 前次公开快照的核验记录

[此前规范AST/完整前缀诊断代码及报告快照](https://github.com/H00RU/LegalSkillGuard/blob/1c5f201219cfdc383d05b53899f81f77454fc3b0/reports/legalskillguard_method_runtime_20261107.md)已同步开发分支，科学实现8ea35e0，包含518项相关离线检查及原始失败。已独立从GitHub拉取，2881个清单文件、清单及2份核验文件逐项SHA256一致；[对应核验收据](https://github.com/H00RU/LegalSkillGuard/blob/d325ce331adcda7c8c88c04fdeb5fe510fe58249/reports/rr_method_runtime_20261107/publication_verified.json)确认main保持ae7e092，私有本地Git祖先未上传。机器运行身份/备份物理路径仅作明确portable variants，原始TRAIN响应字节不变，variant的byte_identical与实际哈希一致。

这是当前原128来源/8批建库运行中的快照，非完整建库/六臂DEV或核心语义通过。发布流程没有新增模型调用；运行中的建库请求仍在同一账本正常计数。此前公开快照均按各自时间保留，不替代当前实现的完整Goal验收。

## 严格操作数真实结果与统一版本接续

严格操作数探针输入3613、输出8192 token，396.899秒，finish=length；没有进入IR执行或TRAIN评分。[实际发送核验](rr_method_runtime_20261107/executor_ast_typed_operands_v1_20261107_dispatch_audit.json)确认原公开源文、模型/OFF配置和schema一致。旧的直接嵌套pair及字符串数值向量形状被生成约束排除，但模型转为重复节点声明；完整前缀98个声明，存在规范化日期/法律关系表等未通过完整grounding的内容。不能闭合JSON、补造缺失条款/query或把类型约束计作核心成功。

[当前前缀类型诊断](rr_method_runtime_20261107/typed_operands_v1_paid_prefix_types_diagnosis.json)只从完整、唯一的primitive声明和已通过实际类型检查的表达式节点取得类型。relation输入被当作字符串键的错误可以直接定位；未生成/重复歧义变量仍不猜类型。类型问题优先反馈，同类重复名称保留路径、次数与总数，避免十二个重复名称占满反馈。模型输入、生成schema和执行语义相对4020044不变；这是反馈缺口修复，未添加业务规则、来源、种子或调参轮次。

B记录路径也已核对：ScopedQuery.execute通过LazyInputs仅求值查询真正读取的分支，只有实际执行的连接器追加pattern_uses，当前未发现无关节点误计的实现缺陷。此为代码/离线检查，当前真实B主路径成功仍为0。原始响应和全部3750余个绑定文件已[保存](rr_method_runtime_20261107/typed_operands_before_prefix_types_preservation.json)。[518项完整禁网络回归](rr_method_runtime_20261107/offline_method_run_v21.json)通过（8项既有警告），原128输入字节及生成schema相对上一版完全相同；46项相关定向通过。科学实现8ea35e0已提交，以固定实现执行method_runtime_ast_v1_20261107原128来源/8批建库，正常模型失败/回退照实保留，不再围绕同一个样例原样重发。原六臂DEV、实际机制和跨库证据仍为未完成交付，Goal保持未完成。

## 已有操作数类型要求同步到生成约束

输入优先探针真实响应耗时296.961秒，输入3921、输出8192 token，仍以length结束，没有IR、执行或TRAIN评分。[实际发送核验](rr_method_runtime_20261107/executor_ast_input_first_v1_20261107_dispatch_audit.json)确认HTTP与封存提示、源文、schema属性顺序及锁定OFF一致。其完整前缀含26个声明，两个观察/规则残余名称冲突，并出现20个完整节点，反复把pair嵌入pair的键及数值向量中。原始响应不改写，见[诊断](rr_method_runtime_20261107/input_first_v1_paid_diagnosis.json)与[结算后保存收据](rr_method_runtime_20261107/input_first_before_typed_operands_preservation.json)。顺序与反馈修复已落实，但未证明能消除模型重复生成。

当前定点修复只同步原有操作数类型：pair的第一个参数必须是字符串表达式；number_at必须读取数值向量表达式。支持变量、条件分支、算术生成的数值向量及向量连接；不推断变量含义，不新增运算符、默认值、规则或声明数量上限。既有运行时类型、grounding、scope及完成检查原样保留。实际旧完整表达式在旧wire可接受、在原类型检查器失败；新wire提前拒绝，付费正确程序仍能精确编码/解码。

同时核对了运行中vLLM后端源码：实际服务配置disable_any_whitespace，调用XGrammar的any_whitespace=False。新后端回归采用相同配置，保留旧宽空白检查原记录；这补足验证配置的一致性，不把它宣称为过去重复生成的原因。[515项完整离线回归](rr_method_runtime_20261107/offline_method_run_v20.json)通过（8项既有警告）；[六个阳性后端用例](rr_method_runtime_20261107/ast_scope_backend_v4.json)通过，[两个真实错误的修正序列化负例](rr_method_runtime_20261107/typed_operand_backend_negatives_v1.json)确实在body操作数处拒绝。最初负例因节点字段顺序被先拒绝，旧证据保留，只重查相同两个负例，未增加样本或模型请求。62项定向检查和原128输入21746≤24576通过，科学实现4020044已提交；当前对同一SARA来源独立真实验证。

## 当前生成顺序与截断诊断修复

AST v2已结算后，3756个绑定文件及整个付费探针已封存，[SHA与保存收据](rr_method_runtime_20261107/ast_v2_before_input_first_preservation.json)保留原始失败。实际完整前缀含34个声明；除条款内重复名称外，还与此前scope名称冲突，并有真实number_at数值向量类型错误。旧重试仅携带JSON截断位置，遗漏这些已可确定的错误，这是具体诊断缺口；模型输出错误本身不会因此被改判成功。

当前调用路径让bindings、observations、rule_residuals先于nodes、scopes、clauses和query生成；同一字段常量控制提示、schema属性顺序和已接纳程序编码。规范IR、源文、作用范围、未知空间、A选批和B图执行语义保持不变，也未限制一个源单元只能有一个条款。提示明确区分声明变量引用与字符串字面量。生产TRAIN修复与独立探针共用新截断诊断：只读取完整JSON值，返回重复声明和不依赖未来符号的类型错误；不闭合JSON、不创造候选IR，不推断缺失变量类型。诊断按同类错误聚合，仅反馈前12种并记录总数，不影响完整程序的任何正确性检查。

[实际前缀诊断](rr_method_runtime_20261107/ast_scope_v2_complete_prefix_feedback.json)包含254处已确定错误、12类紧凑反馈，覆盖重复名称及数值向量错误；这些数字是语法/类型诊断数量，不是评分。35项定向检查通过，实际付费IR、完整理论及A选s10的等价检查仍通过；实际XGrammar及Qwen token六项检查已通过，原128来源最长21711≤24576。[500项完整禁网络回归](rr_method_runtime_20261107/offline_method_run_v19.json)通过（8项既有警告）。初次499通过/1旧顺序断言及日志保留，断言已与新顺序同步。科学实现737eddf已提交；当前对同一SARA来源以新契约、真实诊断和既定OFF做独立executor验证，不把离线通过当作主路径成功。

## 严格声明字段与短表达式的定点修复

原code-v1建库已在所有物理请求结算后安全停止，69来源已提交，另一个来源的已付费首响应和恢复journal仍完整保留；累计686E/21T、pending0。3747个绑定文件及整个运行目录已备份，哈希见[封存收据](rr_method_runtime_20261107/source_code_v1_preservation.json)，原始响应、账本及冻结库不改写。此停点用于具体生成契约修复，Goal保持active；不恢复旧控制器，也不把其前缀拼入另一科学版本。

前69来源的138条响应中，133条没有完整可解析的声明式IR，5条即使仅作可逆变量重命名仍有事实/规则来源错误。旧wire只约束单个代码字符串，声明字段与来源角色依赖生成后检查。当前接口重新使用实际SourceIR的类型、事实/规则ID、b_命名和原生查询schema约束元数据，仅局部计算使用短表达式字符串。表达式不执行Python，禁止在字符串中绕过声明字段构造输入/规则；原内部IR、A/B算法、所有分支类型、源文见证、scope和完成检查不变。[前后归因与证据](rr_method_runtime_20261107/compiler_contract_v1_before_after.json)区分契约薄弱点、实际模型错误及尚缺真实验证，未把此次修复认作所有失败的唯一解释。

五条真实完整失败响应已按原始字节和SHA保存为回归；不会补造缺失语义。付费SARA程序的IR、完整理论哈希及A选择s10的离线结果保持一致。联合响应中的根schema引用位置已修正；初次回归中的旧提示字段/措辞断言也已同步，失败日志保留。原128来源的输入最大21810≤24576，无裁剪源文。新契约已通过[471项完整禁网络回归](rr_method_runtime_20261107/offline_method_run_v14.json)（8项既有警告）、[12项实际XGrammar/Qwen token约束检查](rr_method_runtime_20261107/compiler_contract_backend_v1.json)；自动节点名捕获未声明查询变量的问题已复现修正，原A选批及理论哈希不变。接着使用既定OFF及原采样配置开展独立executor验证；截至此离线节点没有新增调用，也没有新主路径成功或DEV成绩。此修复不改变研究方向、样本或验收口径。

## 新契约两次真实验证与统一版本接续

新契约两条独立executor响应均正常stop，输出分别366和498 token，未触及8192上限；实际HTTP正文与封存提示、来源、schema顺序及锁定OFF采样一致，原始公开units完整保留。两条声明元数据均通过，但第一条在布尔列表操作数处被IR schema拒绝，还存在重复名称、非原文谓词和整规则残余；第二条在nodes[0].code使用字符串下标，被受限解析器拒绝。[第一条实际wire和诊断](rr_method_runtime_20261107/executor_compiler_contract_v1_20261107_dispatch_diagnosis.json)、[第二条](rr_method_runtime_20261107/executor_compiler_contract_v2_20261107_dispatch_diagnosis.json)均保留，不补齐表达式，不把格式成功计主路径。没有执行、TRAIN语义匹配、A选批或B核心成功，也没有新增TEST/DEV来源。

第一条真实错误已加入原始字节回归，并明确了现有all_of/any_of的独立布尔参数形式；对应472项完整禁网络检查通过，原128来源最大输入21840≤24576。第二条属于实际提示已禁止的表达式API误用；不再围绕这个样例反复调提示。接续同一固定模型配置的原128来源/8批建库，所有错误与回退作为实际结果保留，整体Goal仍未通过。

为避免科学版本重建时重复支付完全相同的教师汇总，只在来源顺序、教师配置、系统/用户提示、schema映射全部相同，且原始请求/响应文件与已结算账本一致时复用；物理来源ID、原文件SHA和新增请求0写入新批次。缓存不导入未验证模式，当前库仍只接纳当前训练前缀已验证的模式；教师旧材料不替代当前executor核心机制验收。实际B1原文重放、任一字段改变不命中、记录篡改拒绝及控制器恢复共11项检查通过；[当前479项完整禁网络回归](rr_method_runtime_20261107/offline_method_run_v16.json)通过（8项既有警告），新生成契约及所有正确性检查未再改动。

本次两条物理请求合计输入7139、输出864 token、请求耗时75.695秒，executor688/teacher21，pending0。局部executor增量API现金为0；GPU分摊、教师现金账单仍未知。原438请求、121条meta、130条oracle、1233个旧运行文件及4份旧冻结库保全核验通过，见[累计费用](rr_method_runtime_20261107/goal_cost_snapshot_20261107.json)。以上修复未改变研究方向、模型或验收标准；原完整建库、六臂DEV和核心机制/跨库证据仍待完成。

## 当前严格契约与接续运行的公开交付

[当前开发分支报告快照](https://github.com/H00RU/LegalSkillGuard/blob/7e0a6eaa2447ab97cb3be5e310502035ebb59c5d/reports/legalskillguard_method_runtime_20261107.md)及代码已同步，科学实现474b5c3。已独立从GitHub核对2665个清单文件、清单与2份核验文件，SHA256一致；[远端核验收据](https://github.com/H00RU/LegalSkillGuard/blob/a31e674cd81ac8a9694900a89038e91d1d198606/reports/rr_method_runtime_20261107/publication_verified.json)确认main保持ae7e09230b4eb675b7299f73c4775787ccb2b65b，私有本地Git祖先未上传。公开状态/备份收据的机器信息仅作明确列出的portable variants，原始TRAIN响应不改。这是typed-v1建库刚接续时的快照，不能当作完整建库、DEV或核心语义通过。

新运行method_runtime_typed_v1_20261107从空库按原128来源/8批继续，[local process identity omitted]/[local process identity omitted]，[local process identity omitted]；所有绑定科学文件冻结。首个OpenExempt请求正常返回length，输入21417、输出8192 token，548.029秒；有重复声明且JSON未完整，未执行或评分。[实际长度失败证据](rr_method_runtime_20261107/typed_v1_first_length_output_diagnosis.json)保留原始哈希和paid artifact路径；没有补闭合、扩输出额度或修改模型参数。按原每来源两次预算接续修复请求，后续来源属于同一固定预检，不为单个请求再次调参。最新在途与来源级进度以顶部真实进程核验为准，旧69来源及两条短探针分别保留。

## 规范AST与源单元scope映射：当前修复

实际typed-v1前5来源的10条结果中，6条在8192输出处截断、2条表达式语法错误、2条ContractNLI字面量溯源错误；另一个来源的第1条已付费响应也保存。当前5来源没有被接纳的可执行IR、A/B主路径或TRAIN匹配。[来源级失败矩阵](rr_method_runtime_20261107/typed_v1_complete_prefix_failure_matrix.json)将字符串表示失败与实际语义/溯源错误分开，不把所有失败归为同一原因。当前库从第4来源已付费碰撞重新形成1个entity_equality连接形状，没有后续实际调用，不能算新法律规则或核心机制成功。

原运行在699E/21T、pending0边界安全停止；[3752个绑定文件及运行/候选证据的备份](rr_method_runtime_20261107/typed_v1_before_AST_preservation.json)保留，原始结果、库、账本和oracle不改写。停止后的当前调用路径改用既有SourceIR规范AST，scope按实际规则源ID设唯一槽位；null仅表示没有接纳的scope，对应原IR的缺省/未知，不默认false。它消除自由代码字符串和重复scope-source选择；实际错误金额、引文和规则仍由原检查拒绝，没有补语义、借标签或导入教师答案。

科学实现5e0e22a通过[489项完整禁网络回归](rr_method_runtime_20261107/offline_method_run_v17.json)（8项既有警告）、[实际付费SARA及五库共6项后端语法/Qwen token检查](rr_method_runtime_20261107/ast_scope_backend_v1.json)。实际付费程序IR、完整理论、A选择s10以及原B1图调用trace保持相同；原128来源输入最大21602≤24576，源文完整。历史代码读取器仅保留给已付费原文诊断，不作为当前模型格式的兼容入口。

新独立executor探针executor_ast_scope_v1_20261107只用原最短SARA来源743ac2e…和既定OFF配置；模型、温度、seed、context/output、重试和来源不变。后端与离线检查不等于真实IR或语义成功；当前原128/8批统一建库、六臂DEV、机制/跨库检查与冻结建议仍是未完成交付，不以本次修复完成Goal。

## AST真实首响应：有限来源集合的重复生成

executor_ast_scope_v1_20261107输入3258、输出8192 token，236.109秒，finish=length，JSON未完整。实际尾部停在clauses[0].sources，重复s1来源ID；没有完成IR、执行或TRAIN评分。[原始失败与具体修复证据](rr_method_runtime_20261107/ast_scope_v1_provenance_loop_diagnosis.json)不补齐截断内容，也不以较强的schema冒称模型已学会规则。

现将引擎已有的有限来源约束同步到生成：clause来源数量不超过当前规则单元数，primitive证据数量不超过当前源单元总数。空clause来源仍按原引擎允许，不新增单规则/零回退门槛；重复来源仍由原引擎拒绝。初次uniqueItems关键字被固定严格schema适配器拒绝，失败日志保留；改用支持的数量上限，未删除运行时唯一性。20项定向检查证明所有引擎接纳的来源列表仍符合新上限，并保留对重复、非规则及空primitive证据的拒绝。

已有不完整JSON可在schema修复后提供原始位置诊断，不能恢复成候选IR；新修复验证只使用相同原公共来源和当前模型配置。全量及实际后端检查完成后再发请求，目前累计700E/21T、pending0。原Goal所有后续建库、六臂DEV与机制/跨库验收继续保留，未完成，不启动TEST或论文。

## 完整配对结论及当前接口修复

c6已完成原固定20来源的全部40个配置，主路径结构通过0、对应TRAIN匹配0。新物理请求77次，另有3条完全相同的已付费响应重放，逻辑调用共80；新请求48条stop且符合实际wire schema、29条length，均未形成被接纳的完整程序。[来源级失败诊断](rr_method_runtime_20261107/c6_complete_failure_diagnosis.json)保存首个拒绝原因与完整配置选择，原始程序未改。

ON逻辑请求合计521227 token、4251.19秒；OFF为668174 token、10816.97秒，包含各自重放响应的原耗时。真实模板切换已核实，ON20个配置有reasoning输出、OFF为0；两边语义成功均0，较短失败不构成方法收益。按最新偏好[锁定OFF](../docs/rr_v2/locked_executor_configuration_20261107.json)，不重开ON/OFF扫描；原c6工程阻断记录不改写，也不据此宣称就绪。

当前修复移除了带完整业务语义的无关格式示例，把绑定字段顺序改为name/type/sources/value，并在wire中使根查询及if结果分支遵守现有原生输出类型。所有原源文单元保留，作用范围、未知残余、事实证据、类型、执行及语义检查不放宽。三个真实错误查询在原wire可接受、在新查询语法被拒绝；这表示更早拒绝错误，不表示旧输出恢复成功。[369项完整回归](rr_method_runtime_20261107/offline_method_run_v9.json)、[22项安装版本XGrammar与Qwen token-mask检查](rr_method_runtime_20261107/native_query_backend_v1.json)和[128来源容量检查](rr_method_runtime_20261107/compiler_input_budget_after_v9.json)通过。初次回归的两项拒绝顺序差异及日志原样另存，独立的11个虚构金额和整条规则残余仍明确被拒绝。修复后的真实生成效果尚待验证。

当前累计542E/17T，较同一Goal起点新增118E/3T；无在途、无新增oracle。已结算报告输入1396199、输出583369 token、请求耗时22417.64秒；现金费用未知部分继续保留未知，详见累计账本。新的[GitHub报告快照](https://github.com/H00RU/LegalSkillGuard/blob/873349abda7b32d03d7686604c2ec25e94c4c243/reports/legalskillguard_method_runtime_20261107.md)及[独立远端核验](https://github.com/H00RU/LegalSkillGuard/blob/db0582700e769b1e845ff671fcee7d405b63fbea/reports/rr_method_runtime_20261107/publication_verified.json)已同步开发分支，核对983个快照文件、清单和2个核验文件；该快照记录的是配对进行期间的阶段证据，当前完整40配置证据以本地此节及对应诊断为准，main不变。


## OFF修复验证及探针封存顺序修复

`executor_source_native_query_v3_20261107`在原最短SARA来源743ac2e…执行1次OFF真实调用，输入3447、输出8192 token，耗时290.52秒，finish=length；在bindings阶段写出123个不同名称，仍未生成后续字段，未形成IR、执行或TRAIN成绩。[原始结果](rr_method_runtime_20261107/source_probe_executor_source_native_query_v3_20261107.json)完整保留，本次累计543E/17T，无在途请求。

[实际wire前后顺序核对](rr_method_runtime_20261107/probe_schema_order_before_after_v1.json)发现，探针seal使用按键排序的immutable_json，恢复后误把这个映射直接当作生成schema：原设计顶层顺序和绑定name/type/sources/value被重排。主控制器的dispatch_json原本已保存字面顺序；此缺陷不是c6完整40失败的共同原因。探针现从封存源文/库及绑定代码重建主路径schema，再核对封存前的有序SHA256并发送；改变顺序的历史编译缓存不能当作相同请求复用。9项定向回归及[371项完整离线回归](rr_method_runtime_20261107/offline_method_run_v10.json)通过。该修复建立主路径与验证请求的一致性，不证明它是模型重复生成的唯一原因，也不把旧部分输出修补成成功。


## 真实完整IR的拒绝原因与下一次修复验证

v4实际OFF响应以stop正常结束，输入3447、输出4753 token、耗时186.53秒。实际输出字段顺序已与封存和主路径一致，但31个绑定中26个关系的单元格包含非原文字段或把sN元数据当成事实见证；还存在重复符号、未声明变量、14处条款if的参数个数错误等。原始程序不做适配补造，没有执行或TRAIN语义通过。原JSON及实际wire记录保留在[source probe结果](rr_method_runtime_20261107/source_probe_executor_source_native_query_v4_20261107.json)。

当前已把wire操作数个数与原类型检查器统一到同一签名表，固定常量操作数遵循原执行要求；反馈逐项报告关系单元格、未声明符号、局部节点和条款两分支，未知类型不会被猜成已知。独立executor探针直接复用M11的公共编译请求入口，使用同样的策略说明和输入预算。此修复通过[375项完整离线回归](rr_method_runtime_20261107/offline_method_run_v11.json)和[53项实际后端语法及mask检查](rr_method_runtime_20261107/native_query_backend_v2.json)。[下一次修复计划](rr_method_runtime_20261107/v4_to_v5_source_only_repair_plan.json)仅使用同一原SARA来源、未修改的失败候选及源文诊断；OFF和所有采样参数保持不变，未将部分IR或语法通过计作成功。

当前累计544E/17T、pending0；费用账本已纳入两次真实修复验证，原438请求、121条meta、130条oracle、1233个旧运行文件及冻结库不变。新版代码及完整配对证据已推送[开发分支快照](https://github.com/H00RU/LegalSkillGuard/blob/2f845d866e6b9b74d06209e4317da9429490ca7e/reports/legalskillguard_method_runtime_20261107.md)，独立抓取1395个清单文件和清单全部一致，main未变；本节新修复尚待后续真实结果同步。


## 最新训练指标复核与v5之后的表示层修复

本次只读核对SQLite及实际进程，未新增模型或oracle请求：executor累计545（544结算成功、1请求失败，模型输出错误仍计物理调用）、teacher累计17（16结算成功、1请求失败），pending0；v5控制器[local process identity omitted]已不存在。旧版128来源参考匹配仍为59/128（46.1%），包含92/128（71.9%）fallback；各库分子分母见下方训练指标表。这是历史TRAIN材料检查，不是当前实现成绩。当前统一版本完整128/六臂DEV尚无结果，原20来源×ON/OFF共40配置的主路径通过0，不能以旧内置Horn或回退的正确答案填补。

[v5真实响应](rr_method_runtime_20261107/source_probe_executor_source_native_query_v5_20261107.json)保留同一原SARA源文和v4未修改失败候选、156项源文诊断。修复后的真实wire已核实OFF、封存schema顺序与公共M11入口一致；实际输入13461、输出8192 token、耗时299.985秒、finish=length。输出再次复制并展开错误关系绑定，未完成JSON，未执行或评分。不能将此次失败描述成语义通过，也没有仅提高输出额度或放宽见证检查。

下一步在当前编译调用路径内把模型面对的嵌套JSON改为声明式代码，并确定性编译到同一个内部SourceIR。纯AST解析不运行Python，不推断事实、缺失规则或法律残余；现有schema、数值/见证溯源、所有分支类型、作用范围、资源唯一性和完成检查继续生效。A/B算法、来源、模型参数、账本及DEV/TEST边界不变。不再向下一轮提示复制完整错误候选；具体诊断仍保留，原始失败输出完整封存。

[离线表示层证据](rr_method_runtime_20261107/source_code_frontend_v1.json)与[141项回归日志](rr_method_runtime_20261107/source_code_frontend_v1.txt)核实：已有付费SARA程序的IR往返完全相等，完整理论哈希不变，A仍只选择s10事实并在4096完成下稳定；表示由4092字节降为3267字节。测试覆盖原21表达式操作、7连接器操作、显式存储图调用及资源线程，保留原v4错误程序的拒绝。首次4项负例测试错误地预期Unsupported；现有模式解析器实际抛InterfaceError，只修正了测试期待，初次失败日志原样保存。全部检查禁网络/子进程，三张账本表的前后哈希一致。

该前端当前为未接入模型请求的工作实现；这些是离线工程证据，不是新学习、独立模型编译、跨库或训练成绩。后续先接通必要的生成/解析入口并核对预算和回归，再做有具体变更依据的真实验证，继续原Goal；不把这一阶段检查标记为完成。

累计本Goal新增121E/3T，共124次物理请求；已报告输入1416554、输出604506 token，请求耗时23194.672秒。局部executor无逐请求API现金账单，GPU分摊与教师实际现金费用仍未知。原438请求、121条meta、130条oracle、1233个旧运行文件及4份冻结库保全核验通过，见[当前账本及费用](rr_method_runtime_20261107/goal_cost_snapshot_20261107.json)。

## 声明式编译入口已接通：真实首条为短代码语法失败

代码`c00000f`已经把独立编译、联合规则/事实后续解析和已付费响应恢复统一到`{code:STRING}`封装。内部仍是原七字段SourceIR，完整schema、公共字面量/关系见证、所有分支类型、作用范围、资源消耗及Omega检查继续执行；不接受旧响应格式别名或旁置原生答案。已接纳K通过无歧义渲染进入后续提示，拒绝的完整候选保留在原始记录而不再复制进修复提示。[447项完整离线回归](rr_method_runtime_20261107/offline_method_run_v12.json)、[9项XGrammar/Qwen token-mask检查](rr_method_runtime_20261107/source_code_wire_backend_v1.json)及[128来源输入容量](rr_method_runtime_20261107/source_code_input_budget_v1.json)通过；最大21597≤24576输入token，不截断。旧c6选择及失败记录原样保留，新控制器消费其已锁定OFF凭据，禁止重开对比；这项配置凭据不声称新方法已经就绪。

独立`executor_source_code_v1_20261107`仍选同一原SARA743来源，不使用教师程序、native标签、旧答案、fallback或内置规则。输入3253、输出74 token，耗时2.497秒，finish=stop；模型只写了一个不合法的query，代码在第1行第184列出现未配对右括号，还混入声明构造器、空字符串/sourceID图输入和未定义答案函数，未形成IR、执行或TRAIN评分。该失败与8192上限无关，不将源文规则补入它来制造恢复。[原始结果](rr_method_runtime_20261107/source_probe_executor_source_code_v1_20261107.json)、[完整失败诊断](rr_method_runtime_20261107/source_code_v1_failure_diagnosis.json)和真实fixture原样保存。

[实际HTTP正文核验](rr_method_runtime_20261107/source_code_wire_dispatch_v1.json)确认thinking OFF、所有原采样参数、新schema及其封存顺序一致；核对使用`wire_request.json`中base64保存的HTTP正文，而非会排序的检查用JSON映射。现有证据将本条归为模型输出语法/API错误，没有执行器运行故障的证据。

针对实际失败的后续工程修复增加code字段的行/列及期望/实际语法诊断；已结算但无法解析的真实响应现在只产生源文诊断，不虚构`program.json`。提示明确先作命名声明、最后query读取guarded结果，使用Python布尔字面量、真实原生标签字符串及正确连接器输入个数。新增真实失败回归及禁止补造操作数的API负例；原始代码不修改、不加入下一次完整候选提示。完整v13回归完成后才以该已付费来源与具体诊断做一次OFF纠正，不新增来源、教师、配置扫描或TEST。

## 当前接续：同一版本固定128来源建库已启动，Goal未完成

`executor_source_code_v2_20261107`使用同一原SARA源文和v1真实语法诊断，实际HTTP正文核对OFF及封存schema一致。输入3409、输出213 token，6.293秒，正常stop；首次能解析成内部IR，但在`observations[0].name`被拒绝，另有事实来源冒充规则来源、无条件scope、查询行冒充规则条款、Boolean查询等具体翻译错误。[完整源文诊断](rr_method_runtime_20261107/source_code_v2_failure_diagnosis.json)与[实际wire](rr_method_runtime_20261107/source_code_wire_dispatch_v2.json)分列保存，不将内部IR可解析算作核心成功，不通过适配补造规则，没有执行或TRAIN评分。两次code探针均未触及8192上限。

现有证据没有新增执行器、封装或原IR语义检查不兼容；这些错误按实际模型输出处理。最新授权不以普通模型错误、fallback或暂未涨分停工，因此停止追加逐样例提示修复扫描，直接接续原定、同一科学版本的完整建库。新run为`method_runtime_code_v1_20261107`，代码`ea34dbc`；它从空库按原128来源顺序形成8批，保留原B1/B8和同材料MB交付。先前建库对应不同实现，原样保留，不能拼接为新版本结果；这是同一Goal中为版本一致性所需的建库，不重置Goal、请求或oracle账本。

本版通过[454项完整禁网络回归](rr_method_runtime_20261107/offline_method_run_v13.json)，新封装9项后端核验通过，更新后[128来源输入容量](rr_method_runtime_20261107/source_code_input_budget_v2.json)最大21692≤24576；所有模型、温度、seed、输出/context及OFF配置不变。每来源最多2次生成、每批教师最多2次汇总、每来源最多4次原预算视图，保留已有相同视图缓存；原生回退、预定义Horn与模型主路径分列，不把格式、正确答案或旧模式冒称新核心学习。

[当前运行及PID身份核验](rr_method_runtime_20261107/method_runtime_code_v1_20261107_build_observation.json)、[来源级进度](rr_method_runtime_20261107/method_runtime_code_v1_20261107_source_status.csv)和[累计费用](rr_method_runtime_20261107/goal_cost_snapshot_20261107.json)持续写入不绑定的状态文件。训练输入、源码、测试、配置和协议均在seal内冻结；运行中不改科学文件，也不并发启动另一建库。完整建库后接续原六臂DEV及A/B/跨库审计，所有条件满足前保持未完成，不启动TEST或论文。

## 最新公开交付核验（建库进行中快照）

当前实现及报告已同步[开发分支快照](https://github.com/H00RU/LegalSkillGuard/blob/5cedb8401e419ad06c53cfc0d655d7b0172d62b3/reports/legalskillguard_method_runtime_20261107.md)，科学代码对应本地ea34dbc。已独立从GitHub抓取核验1481个清单文件、清单本身与2份核验收据，SHA256一致；[核验收据](https://github.com/H00RU/LegalSkillGuard/blob/03173c0086622807c0208cc9ec389a91ad0e3e82/reports/rr_method_runtime_20261107/publication_verified.json)及本地`publication_branch_head.json`记录完整链。main仍为ae7e09230b4eb675b7299f73c4775787ccb2b65b，私有本地Git祖先未上传，发布未新增模型调用。该公开版本是建库进行中的固定时间快照，最新来源进度以本报告顶部和当前observer为准；文件核验不等于核心语义验收，Goal仍未完成。

## 建库前缀的机制核验：首次碰撞模式与主路径使用分列

当前第4来源（原ProofWriter43ec4119…）从空的当前库重新执行碰撞学习，4个已付费TRAIN视图产生3对区分`entity_equality`的碰撞，得到按共同实体列`join_on`的参数化图。[首次形成证据](rr_method_runtime_20261107/current_B_first_acquisition_20261107.json)核实四个view_hash均已在本Goal前计入原账本，未新增标签/模型请求；原语来自预定义公共Horn文法，不能计作新法律规则学习。模式与历史B8中同形图哈希相同，当前重新形成及以后真实存储调用分别记录，不把旧结果直接当作本次主路径成功。

[当前前缀机制审计](rr_method_runtime_20261107/method_runtime_code_v1_20261107_mechanism_prefix_audit.json)按原来源顺序重算library_before_hash和每来源两次调用/四视图预算，区分模型SourceIR、预定义Horn、仅提示曝光、同形再发现和实际执行存储图。共享来源模式不直接计作外库独有贡献；真正外库调用还需原DEV及必要最小启用/屏蔽证据才能讨论因果效果。该审计只描述现存记录，不新增验收门槛、来源或模型调用。

本次审计至第4来源，当前独立模型IR编译、A实际后续解析、A分离完备请求及后续存储图调用均未观察到，不能把一个已形成的B模式等同于整体方法通过。OE、Airline和SARA因模型未提供可执行IR而缺少B原语输入，保持`typed_inputs_unavailable`，不写成已经搜索完候选但无解。建库继续，所有结论以各自时间戳和分母为准。

## 当前建库的实际输入核验

[实际HTTP正文审计](rr_method_runtime_20261107/method_runtime_code_v1_20261107_dispatch_audit.json)覆盖当前前6来源、12个已完成请求：HTTP原始字节与journal保存的完整dispatch、封存采样配置及OFF模板逐一相等；编译请求的原始公开units逐项相等，响应中的prompt_tokens也全部等于发送前serving tokenizer的计数。没有源文、schema或采样漂移，也没有输入被静默裁剪的证据；每条输出8192限制与输入预算分开记录。本审计只读原TRAIN公开包和已有请求/结果，未打开评分包、未生成或查询新标签。

这支持当前公开输入完整送达，不能推出已经获得足够的可执行原语或忠实规则翻译。当前模型SourceIR仍未编译通过，A残余选批尚未执行；缺输入来源与ContractNLI按原方案无反事实oracle分别记录，形成模式和实际调用也不混合。后续按同一封存运行继续，不根据这些普通输出错误追加来源或重新调参。

## B1检查点与回退口径核对

首批16来源的B1、B1.MB和教师汇总已保存。[B1核验](rr_method_runtime_20261107/current_B1_checkpoint_verification.json)逐项重算源记录哈希、库前缀和6臂共同材料哈希，全部一致；B1的模式证据来源均在前16来源内，MB也恰为16来源、额外准备调用0。教师本批实际1次汇总，只接纳当前公共训练证据已经验证的模式哈希，没有新增未验证的法律规则。原语/模式库仍只有实体等值连接这一种形状，不将库文件形成当作全部验收通过。

前缀14来源已有2个ProofWriter结果匹配参考答案，46次实际存储图执行均与查询依赖有关，来源为先前第4来源学得的同库模式。两条预测均在模型IR失败后进入`controlled_public_grammar`，因此是Horn回退中的真实组件执行，**不计当前核心模型IR主路径成功**，也不是跨库迁移。原始`fallback_used=False`只表示没有走原生答案回退；原记录另有`model_source_IR_still_unresolved=True`。目前报告和来源CSV按实际控制流分列原生回退、Horn回退、预定义快捷路径及模型SourceIR，不修改原记录；此前仅以原生回退标志统计会漏报Horn恢复，属于报告口径缺陷。此时总回退为2/14，核心模型IR、A实际后续解析和核心B主路径均为0；完整比例随原运行继续更新。

[确定性命名适配检查](rr_method_runtime_20261107/method_runtime_code_v1_20261107_name_adaptation_check.json)覆盖前17来源的34条已付费输出：31条没有完整可解析的声明式IR，另外3条即使只作可逆的内部变量alpha重命名，仍在原语事实/规则来源字段被拒绝。源文引用、数值和规则表达式未修改，也未补齐截断输出、读取评分包或安装生产适配分支；当前没有仅靠命名规范化就能恢复的合格IR。因此不能把上游缺可执行输入写成已经完成了A或B的语义验证。

此处是当前实际失败与验证覆盖的分类，不增加涨分、技能数量、全分支实测或零回退要求。原进程、预算账本和所有seal绑定文件保持，继续剩余原128来源、8批和原六臂DEV；主方法语义及整体Goal仍未通过。

## B1阶段公开快照已独立核验

[B1阶段报告快照](https://github.com/H00RU/LegalSkillGuard/blob/661b2e0256c4626e29f02d7624e2d40dd1abc427/reports/legalskillguard_method_runtime_20261107.md)已同步开发分支并独立抓取核验1908个清单文件、清单本身和2份核验收据，SHA256全部一致；[核验收据](https://github.com/H00RU/LegalSkillGuard/blob/b4260995292bbbb5f99f77dda3232d34733dc566/reports/rr_method_runtime_20261107/publication_verified.json)记录完整链，main仍为ae7e09230b4eb675b7299f73c4775787ccb2b65b。该快照保留原始失败、B1同材料核验及回退分类，不包含私有本地Git祖先。它是B1时点快照，之后建库持续运行；最新计数以顶部实际进程核验为准。发布没有调用模型，文件核验不等于核心机制或整体验收通过。

## 前三批共同材料与教师记录核验

[前三批核验](rr_method_runtime_20261107/method_runtime_code_v1_20261107_batch_material_verification.json)覆盖B1–B3、前48来源：每条源记录和每批库哈希均与保存的快照一致，6臂共同材料逐项相等，模式证据来源没有超出当时前缀。前三批教师分别成功汇总1次，记录模型均为gpt-5.6-sol，wrapper attempt为1、工具事件为False；接纳的模式哈希均来自当前已验证库，不将教师未验证提议当作新学习。

这3条教师记录合计报告输入48446、输出620 token，reasoning字段178单列不叠加；estimated_credits和现金账单均未提供，不能换算或填成0费用。教师账本计数是已知CLI调用/包装层尝试；成功记录保存事件日志哈希而不含完整日志，不能仅凭该哈希独立重数提供方底层HTTP重试。这里保留计数可核验范围，不补造未知重试或费用，也不重置原账本。

实际发送正文审计已扩至前51来源的102条请求，内容、原公开units、配置、OFF及输入token计数逐项匹配；命名适配检查同样覆盖102条，98条没有完整可解析IR，4条经只改内部名后仍被拒绝。当前核心输入生成的缺口持续记录，不能用回退中的58次存储图执行补作核心成功。该时点之后的进度以顶部真实进程和各审计时间戳为准；原建库继续。

## 当前阶段结论与证据分工

当前实现尚未达到冻结测试条件。原128建库只提供旧TRAIN材料检查（59/128，含92个fallback）；新实现还没有完整128或六臂DEV结果。当前工作的直接阻断是自然规则的可接受执行输入不足；其中已证实并修复的工程原因包括消息/执行契约不一致、后端源编号枚举、无限嵌套、英文数词误拒，以及OE错误的条款父子上下文。修复检查通过不等于模型已经返回语义正确的程序。

| 验收项 | 当前有效证据 | 当前缺口 |
|---|---|---|
| A真实作用范围、残余和分离选批 | 原SARA教师编译组件经实际事实解析、scope guard和完成空间执行；新控制器离线回归 | 当前统一Qwen编译流程尚无已接纳的完整真实来源，不能以组件重放替代 |
| B碰撞驱动接口学习与存储图执行 | 原B1两来源的视图重放；后续ProofWriter来源实际执行存储图12次 | 同库组件证据；新128中的形成、实际使用和跨库情况尚未测得 |
| 同一版本完整建库及原DEV六臂 | 控制器、同材料MB和恢复/标签隔离的离线证据 | 新128/8批及240个DEV来源预测尚未开始 |
| 历史、账本和公开交付 | 原始结果/冻结库保全；物理请求逐项记账；开发分支中间快照 | 本阶段仍在验证，最终费用/冻结与正式测试建议待原Goal全部完成 |

下面各节按日期保存原始诊断和修复证据；早期累计数和当时的“下一步”只表示当时状态。当前状态以顶部实时记录、SQLite及最新运行进程核验为准。


## 当前训练指标口径（2026-11-07）

目前唯一完整128来源指标仍来自旧版建库，不能视为当前实现的训练表现或DEV/TEST成绩：

| 来源库 | TRAIN参考匹配 | 比例 | 实际fallback来源 |
|---|---:|---:|---:|
| OpenExempt | 0/32 | 0.0% | 25/32 |
| RuleArena Airline | 0/24 | 0.0% | 22/24 |
| SARA | 15/24 | 62.5% | 21/24 |
| ProofWriter | 24/24 | 100.0% | 0/24 |
| ContractNLI | 20/24 | 83.3% | 24/24 |
| 合计 | 59/128 | 46.1% | 92/128（71.9%） |

[原来源级指标](rr_method_runtime_20261107/training_metrics_snapshot_20261107.json)包含fallback，ProofWriter的旧A证书主要来自预定义Horn路径；均不能替代新方法的独立编译、真实规则学习或实际存储图使用验收。新实现完整128建库尚未开始，六臂DEV尚无结果，TEST未启动。当前固定20配对进度见顶部实时记录，各旧版本的未完成配对分别保留，不能与当前配置或旧128拼接。

## c6新增响应的源文核对与成本（2026-11-07 04:59 UTC）

[SARA完整原始响应的源文诊断](rr_method_runtime_20261107/c6_first_SARA_source_only_diagnosis.json)核实：两条ON输出相同，但两次实际请求正文哈希不同；第二次确实携带了第一次的原程序和金额溯源错误，不是客户端漏发反馈。四个条件被模型写成数值0或1的amount，并附上event、condition、boolean、year单位；s52实际给出Alice/Bob的雇佣、残疾、解约及12980美元付款，没有这些金额字面量或单位。这些输出保持失败，不把0/1强转成事实Boolean，不补造规则。OFF首条在bindings阶段写出116次name字段，含重复名称，尚未输出nodes或query便达到8192 token；该条不能仅归因为正确完整程序所需长度超过上限。此诊断只读原TRAIN公开输入、已结算响应和请求，不打开评分包、不新增生成或oracle。

[5条实际截断前缀的逐字段分析](rr_method_runtime_20261107/c6_truncated_prefix_diagnosis.json)只读取未修改原文中已闭合的JSON数组项，不补上结束符、不把部分输出当作IR。4条在bindings、1条在scopes截断；其中4条已经出现重复内部名称：OE首条58处、OE第二条nodes22处及scopes82处、SARA两条分别95和151处。Airline该条的226个完整绑定名称不同，仍未输出后续规则节点。现有证据说明重复生成和绑定膨胀实际消耗了输出额度，不能据此声称单纯提高8192上限就会产生可接受程序；部分前缀也不计作主路径或语义通过。

[ContractNLI示例内容误用诊断](rr_method_runtime_20261107/c6_format_example_copy_diagnosis.json)核实首个来源ON第二条实际响应：finish=stop、内容727字符、completion1010 token。bindings、rule_residuals、nodes、scopes、clauses及query六个字段与无关格式示例完全相同，唯一差异是observations变为空数组，因此不是整个程序的原样复制。实际发送的dataset、source及格式示例均与当前绑定一致，系统提示也明确禁止复制示例；未发生客户端把当前任务替换成示例的问题。此项是错误模型输出，不是长度截断，不计格式或核心语义成功；原程序未做任何修补。该诊断只读取现存响应和请求，无新生成、oracle或评分信息。

[当前累计成本](rr_method_runtime_20261107/goal_cost_snapshot_20261107.json)及[逐请求账本](rr_method_runtime_20261107/goal_request_ledger_current.csv)于04:59 UTC核对为474E/17T、pending1；相对同一Goal起点新增50E/3T（含在途），已结算报告输入742641、输出261239 token、请求耗时10174.44秒。教师reasoning字段14139单列，不重复加到输出。局部executor每请求API增量现金支出为0，GPU分摊与教师现金账单未知，不能据此声称研究总费用为0。[历史保全](rr_method_runtime_20261107/history_preservation_current_runtime.json)再次核对原438条请求、121条meta、130条oracle及1233个旧运行文件不变。快照脚本不会改写c5等历史结算证据。




状态：Goal active，未完成。当前版本从本地提交7f96fc7续接，旧建库与冻结库完整保留。原固定128 TRAIN来源、五库划分和既有模型资源不变，TEST标签和冻结测试保持关闭。

本Goal起点为账本424E/14T、438条请求、121条meta、130条oracle。基线及旧run逐文件哈希在`artifacts/rr_method_runtime_20261107/baseline.json`；后续新增调用单列在下文，不重置历史。

最新完整TRAIN材料检查仍为旧版59/128（46.1%）：OpenExempt0/32、Airline0/24、SARA15/24、ProofWriter24/24、ContractNLI20/24。旧A稳定24/128均来自内置Horn，真实分离批次0；旧B两模式没有后续真实库调用证据；fallback92/128。这些不是DEV/TEST性能，也不能表示当前修复版已就绪。

当前修复版完整建库和六臂DEV尚未开始。统一控制器、B完整源程序候选过滤、同材料MB和六策略推理入口已实现，319项禁网络回归通过；临时128/8批/240来源预测的恢复与标签隔离检查是工程fixture，不计真实研究结果。实际B入口用原B1在原第19个ProofWriter来源执行12次存储图，所选执行器进入1个源完成世界的独立检查，TRAIN匹配；原第4/14来源的4+4付费视图重放学习哈希一致，仍是同库组件证据。初译提示重复原文和传递上下文膨胀造成最长73217输入token，已以完整源行一次登记和保全全部可达上下文的压缩图修复；原128来源带既有B8菜单、ON模板最长20648，均满足24576输入预算及8192输出预留。Qwen独立初译仍须当前完整契约的真实验证，原两条失败保留。即将执行原固定20来源的一次当前两步流程ON/OFF配对比较，未开始新128/DEV/TEST。当前累计427E/17T、oracle130、pending0；本轮至此新增生成/教师/oracle0，Goal active、未完成。

## 已定位的实现与契约问题

| 问题 | 当前证据 | 修复目标 |
|---|---|---|
| A的自然条款没有可接受的作用范围入口 | source_completion.declarations只识别人工Boolean/Integer/Enum声明；真实60来源残余scope未知 | 从实际源文结构与已接受翻译建立作用范围和完整性义务，未知范围继续fail closed |
| 连接器与A未衔接 | engine._program的connector返回completion_theory=None；compilation.source_theory只重建expression/public_horn | 具体执行图进入独立的全完成空间检查，不用H一致性替代Omega |
| B的库应用没有实例化所学图 | routing.apply_interfaces主要按两个字段过滤原候选，学习图未绑定到新输入 | 类型约束下实例化已学图，记录模式、源数据集、目标、新绑定与真实执行 |
| 提示和合法引用契约矛盾 | compiler_prompt仍要求所有引用含§，strict_contract已允许Illinois无§引用 | 源文引用约束与提示一致，并用已有失败原文离线回归 |

## 完成口径

按当前授权逐项验证A真实主路径与语义、B有效学习及使用、完整建库、原定DEV六臂对照、跨库启用/屏蔽证据、数据隔离、账本成本、冻结配置及公开交付。中间修复、离线绿灯、少量真实成功和本报告更新均不作为Goal完成。无需所有库涨分或零回退。

## 首轮离线修复与原始输入诊断（真实探针前）

已完成显式选定连接器进入A的完成空间检查；没有显式选择的H即使只剩一个图或所有图一致，也不会升级成Omega证明。连接器每个完成世界独立复制可消费资源，保留精确有理数；未识别源文作用范围继续阻断。新增`completion_program`记录实际执行语义，原始提议独立保留。

B新增显式模式调用并按当前输入的槽/列角色展开真实存储图，记录模式哈希、支持来源、绑定、图哈希和实际执行状态。独立写出同图、接口候选展开和未选中的图均与主路径复用分开。空候选池或已查询视图无法重绑时，不再发布可执行模式。Illinois提示与合法引用schema矛盾已修复。

[193项相关离线回归](rr_method_runtime_20261107/offline_runtime_foundation_v2.json)通过，测试过程禁网络、源文件字节未变；8个历史mock空OE指标警告保留。首轮183项中两个人工接口fixture未声明新增的显式选择，原失败日志保留；只更新其当前协议声明，语义断言未削弱。新增人工算例只证明实现连通与拒绝条件，不计真实方法效果。

[实际128来源输入诊断](rr_method_runtime_20261107/actual_source_contract_diagnosis.json)表明，128条真实输入没有一条符合旧人工有限声明语法。尤其80个OE/Airline/SARA来源均无独立true/false文字，旧schema同时禁止Boolean引用，却未提供从事实到规则条件的派生谓词接口。这是表达与任务契约缺口，不能仅凭原输出错误归因于模型能力。下一步需把真实事实/条款翻译成有源文依据的作用范围与观察契约，再验证真实主路径；任意模型范围猜测、未翻译整条规则仍不能自动消除TOP残余。

[保全检查](rr_method_runtime_20261107/history_preservation_after_foundation.json)确认旧438条请求、121条meta、130条oracle、全部旧run字节和四份冻结工件不变。本Goal仍为新增模型0、oracle0；未读取DEV/TEST标签。Goal active，主方法真实验证、完整建库、DEV六臂、跨库验证及正式测试冻结建议尚未完成。

当前账本入口已实现独立MethodLedger：撤销旧全局/轮次停工条件，保留固定TRAIN/DEV隔离、在途请求排他、精确缓存身份和失败不可退账；[5项单独账本测试](rr_method_runtime_20261107/method_ledger_unit_checks.json)通过，测试只写临时数据库。尚未接线真实新运行，不能把账本测试误当模型验证。继续顺序见[实现决策](../docs/rr_v2/method_runtime_design_20261107.md)。


源文结构登记已覆盖原128个TRAIN输入，保留逐字原文、规则/事实/查询/指令边界、标题及父条款前言、明确引用上下文；相对引用未解析时单独保留。登记器不推断适用性，也不把任何原文单元自动标为compiled。账本与源文结构共[9项禁网络检查](rr_method_runtime_20261107/source_structure_and_ledger_v1.json)通过，其中源文检查实际读取全部128个既定TRAIN公开输入，不读取DEV/TEST标签。

当前核心未决仍是实际条款和事实到可执行条件/观察的紧凑表示，以及把该表示接入新运行。不是资源耗尽或请求轮数阻断；尚未发出新Goal的模型请求。后续真实方法验证、完整建库和开发对照都未被这些离线检查替代。

## 紧凑源文IR与下一次真实定点验证

新增局部定义DAG、带事实/规则双重引用的原子观察和逐条源文覆盖；编译器不提供观察真值或native答案。类型检查遍历所有分支，实际执行按分支延迟求值，未执行的库节点不计复用。同一可消费资源只允许一个线程图拥有。A可按完整AST的传递读取集合证明某些已定型观察不影响查询；不删除未知整条规则，不把无关变量的见证值说成已解析。证书同时记录完整完成数与实际枚举数。

当前[227项禁网络回归](rr_method_runtime_20261107/offline_scoped_source_v1.json)通过，8个历史mock警告保留；[开发中间失败及修复](rr_method_runtime_20261107/scoped_source_development_failures.json)另存。仅有人工算例证明新路径及拒绝边界，尚不作为真实方法效果。已准备一个原TRAIN SARA来源的版本化探针：按公开规则文本长度选择，不读取标签挑样；编译完成后才做对应TRAIN语义评分。源、提示、schema、代码和模型绑定已封存，继续使用原物理账本与既有服务。

## 首个真实编译探针及定点修复

`source_contract_probe_v2`新增1次原教师调用，耗时127.56秒，报告输入17389、输出6736、reasoning输出字段5256 token（原字段分别保留，不假定额外相加）。实际现金账单和estimated credits均未知，不能记为0美元。当前累计424E/15T、oracle130、pending0。此前v1在初始化账本前遇到DEV清单为字典而非来源键的入口错误，新增调用0、policy行0；改用既有key后，原数据清单回归通过，v1 seal保留。

教师真实返回11个节点和14个观察。解析器首先拒绝缺少b_前缀；该要求未同时写入schema/提示，是具体契约不一致。完整[原响应离线诊断](rr_method_runtime_20261107/source_contract_probe_v2_audit.json)另发现5个法律/阈值观察，合计19处问题。原响应[逐字保留为回归fixture](../tests/fixtures/rr_actual_compiler_program_v2.json)，未补造规则或改写为成功，未派发executor，没有语义证书或TRAIN得分。变量名中带2018不等于AST实现了时间条件，后续要求时间限定出现在实际输入及表达式中。

下一版把b_写入strict schema；未完成的法律/数值子表达式可保留为Boolean残余，必须引用规则原文的真子片段，并由显式包含它的规则AST读取。其完整域保留False/True，不向事实观察器索取法律答案，也不能把整条未译规则或一个自由scope集合替换成Boolean。若残余影响当前查询则仍未决；只有AST依赖证明其不影响当前查询时，才可按静态非干扰做精确投影。规则翻译忠实性始终是独立声明的条件，类型通过或TRAIN答对不证明英语语义完整。

## 一个来源的真实A控制流及TRAIN匹配已通过，源文语义仍需修复

[完整探针证据](rr_method_runtime_20261107/source_probe_source_contract_probe_v4_processing.json)记录原SARA来源743ac2e5…：教师第二条输出的年份比较及规则残余原样保留；拒绝原因仅为无关内部记录的`taxable_year`/`determination_point`字段名。检查器现只允许已证明位于完整查询依赖闭包之外的内部记录标签，所有值及可达native输出键仍需公开溯源。原始程序未改写，source/prompt/schema/teacher逐项相同后复用原已付费响应，新增teacher0。[235项禁网络回归](rr_method_runtime_20261107/offline_scoped_source_v5.json)通过；两个真实输出均保留为固定fixture。中间1项回归暴露字面量来源与整条规则覆盖混淆，已把两种检查分开：能引用一个原文数值不等于翻译了该规则。

执行前12个未知Boolean形成不同答案完成；AST依赖表明只有`b_legally_separated`影响当前查询。A实际选中事实s10，分离查询2次，实际serving tokenizer计248输入token；Qwen thinking OFF仅返回该原子事实和逐字证据，耗时1.405秒、输出51 token。剩余11个条件（含4个规则子表达式）仍未知，没有由执行器判定法律残余；静态非干扰把全部2048个完成精确归并为1个查询世界，完成性检查及原TRAIN参考匹配均通过。没有native fallback、内置Horn代答或人工改写程序；本次没有B模式调用，`pattern_uses=[]`。这证明一个真实来源的A控制流及该候选翻译的完成检查，不证明完整源文的作用范围已被忠实覆盖，也不证明新128建库、B主路径、DEV或跨库效果已经通过。

本Goal当前[逐请求账本](rr_method_runtime_20261107/component_request_ledger.csv)及[费用摘要](rr_method_runtime_20261107/component_cost_summary.json)共1E/2T，已报告输入35264/输出14030 token，reasoning输出字段11186单独保留，不重复相加；请求耗时合计265.961秒。局部executor每次API现金支出0，GPU分摊和教师现金账单未知。当前累计425E/16T，无在途请求；[保全核验](rr_method_runtime_20261107/history_preservation_after_first_real_A.json)确认原438请求、121meta、130oracle和1233个旧run文件不变。

接续任务为B碰撞学习到新主路径的接线、真实后续来源复用验证，再完成统一128来源建库及原DEV/跨库对照。所有原验收条件保持，Goal active；未开始DEV/TEST或论文。

[随后的源文语义复核](rr_method_runtime_20261107/source_scope_semantic_review.json)发现具体未解决问题：s5的“仅对引用本款的条文适用”被存入`v_subsection_scope`/`n_b_scope`，该节点没有任何消费者，款b后果没有相应适用守卫。主查询a2的执行和TRAIN匹配是真实记录，但`node.sources`引用同一段文字不能单独证明这项条款义务已经执行。2048完成证书只对候选翻译及其忠实性假设成立，不能据此接受整个源文覆盖。这里是原A作用范围正确性的实现/契约缺口及不完整翻译，不是新增全分支实测、涨分或零回退门槛。后续先显式绑定条款作用范围与执行守卫，对纯元数据或缺失守卫保留残余，再继续B/完整建库/DEV。当前完整A语义接纳0、真实A控制流和TRAIN匹配1；Goal保持active。

## 显式源作用范围修复与真实纠正

[本次验证](rr_method_runtime_20261107/source_scope_repair_verification.json)把旧“sources既是引用又代表完整覆盖”的接口改为局部计算、单源Boolean scope、条款所有权三部分。引擎从登记的原文上下文生成条款if，不接受自由scope集合；未使用的scope和局部元数据不消除残余，漏掉显式条件前言仍保留TOP，native query不能绕过守卫直接读取局部原值。[243项相关禁网络回归](rr_method_runtime_20261107/offline_clause_scope_v1.json)通过，含原s5真实字段的字符串/Boolean不兼容回归。

真实教师修正使用同一原SARA公开源文及原不完整候选，没有发送评分或native答案。s5现在由未解析的Boolean `b_subsection_reference_applies`控制，后端将其挂到款b的后果；该值未交给事实观察器判定。原文来源、事实提示、schema和执行模型配置完全相同的248-token原语请求复用已有付费响应，新增executor0。[完整新运行](rr_method_runtime_20261107/source_probe_source_scope_probe_v5.json)实际进行分离选批及当前生产路径执行，保留其余12项未知、4096完成下答案稳定并匹配TRAIN。程序由教师原样返回，未人工补规则。

[真实旧/新程序的离线反例](rr_method_runtime_20261107/actual_scope_guard_counterexample.json)在同一个合法Boolean完成赋值（s5范围为False、其他款b条件为True）下，旧程序仍推出b后果，新程序正确禁用后果；该反例是离线语义回归，不冒充真实模型分支或新oracle视图。当前只按来源实例及其声明完成域接纳A路径，不宣称学到了通用日历算法，也不自动将该程序重绑到改变数值的其他来源。B、统一128、DEV、跨库及最终冻结交付仍待完成，Goal active。

[旧B1模式组件复算](rr_method_runtime_20261107/prior_B1_component_compatibility.json)仅使用原第4、14来源当时已记录的视图及已付费标签，碰撞学习结果与原记录规范JSON完全一致，模式哈希不变；网络、子进程和新标签查询均禁用，新增模型/oracle0。初次Python比较因tuple/JSON array容器差异失败，原比较记录保留，规范序列化无字段哈希差异。本核验只支持旧B1模式组件的兼容性及早于第19来源的来源顺序，不冒称新B1/128建库完成，也不向较早前缀注入未来来源。下一步是后续来源的真实图调用与语义检查。

## B实际存储图已接入后续原来源

[第19来源的当前生产执行](rr_method_runtime_20261107/B_runtime_B_main_path_probe_v1.json)只使用旧B1中原第4、14来源支持的模式，动态实例化12次与查询依赖有关的存储图；原TRAIN答案匹配，原来已记录的4个视图重新执行后全部匹配缓存标签（2个True、2个Unknown）。主源生产执行与这4项离线视图重放分列；新增模型、oracle及参考标签均为0，三张账本表和冻结库字节未动。受限公共文法解析、事实匹配和闭包调度是预定义组件，不算新法律规则学习；B学习部分仍是原碰撞识别出的entity_equality接口义务及参数化图，当前证据新增的是其在后续来源中的实际执行。

这次是ProofWriter内部的后续来源使用，不算跨库迁移。第19来源在历史建库中也曾独立发现同形模式，原历史不改写为复用；当前生产执行才有明确库调用。屏蔽库的检查返回pattern_unavailable及空答案，没有借用正确的内置join补位；这只是可用性负对照，不是准确率涨分证据。当前新128/DEV/跨库对照均未完成。

跨多行原语证据已替换旧单行字段，来源数组中的每一行都对应原文，关系见证仍逐值检查。单个Amount复用集合金额的原文数值检查；重复资源银行仍被拒绝。原SARA已付费程序仅把单个source改成singleton sources数组，输入值及完整理论哈希不变；该投影保存为显式工件，不是新模型输出或语义补全。[255项禁网络回归](rr_method_runtime_20261107/offline_multi_source_B_v1.json)通过，包括预测模块不导入训练/oracle/client的隔离检查。

下一步直接验证既定Qwen执行模型独立产生新IR的能力；当前教师纠正样例是编译契约与作用范围的验证，不能替代执行模型本身的生成验证。原公开TRAIN另显示3个来源确需“或其零头”向上取整，金额/状态数组到原生输出也需显式投影；这些具体调用路径会在统一建库前补齐，不增加来源/种子或调整模型参数。


## 执行模型独立编译：离线契约对齐通过，真实纠正仍失败

[首次完整诊断](rr_method_runtime_20261107/executor_source_probe_v1_diagnosis.json)逐字读取第426次executor响应，定位26项来源、命名、类型和守卫问题。原wire schema接受了该JSON结构，运行时正确拒绝了6个无原文支持的数值绑定；另有事实行充当规则来源、整数条件、同名观察/绑定和整条未译规则占位。没有通过改名、整数转Boolean或补规则恢复该候选，因为这些都需要增加或改变语义。原响应保留为真实失败fixture，未读取native评分来修复。

具体接口修复将已知规则/事实角色枚举和Boolean scope形状前置到发送schema，后端仍检查变量实际类型、全分支、源文引用及条款守卫。去掉段号不再允许把整条未译规则称作子表达式。新增反馈只包含公开源文及编译字段诊断，执行模型纠正入口核验候选必须来自同一个模型自身已付费响应；教师缓存/程序不能计为独立executor生成。[262项离线回归](rr_method_runtime_20261107/offline_executor_contract_v2.txt)通过，网络禁用，所有绑定文件测试期间字节不变。开发中一项新测试曾误取fixture包装层，修复为选择其canonical_program；该测试失误没有改变生产判据或原模型输出。

[第427次真实纠正诊断](rr_method_runtime_20261107/executor_source_repair_v2_diagnosis.json)记录同一原SARA来源、同一Qwen/Qwen3-8B配置、temperature0.6/seed45、thinking OFF；来源、schema、提示、代码和离线收据独立封存。模型把4个谓词来源从事实s10改为标题s1，却保留其余错误，26项诊断仍在，因此没有事实观察、fallback或TRAIN评分请求。原始结果为component_probe_unresolved，未改写成成功。

| 真实执行模型编译 | 输入token | 输出token | 耗时 | 停止原因 | 类型/语义结果 |
|---|---:|---:|---:|---|---|
|首次独立生成，第426次|2539|1559|42.863秒|stop|拒绝无原文数值；完整离线定位26项问题|
|具体反馈纠正，第427次|5353|1555|44.266秒|stop|仍拒绝相同数值；只改4个来源ID，未解决|

两次均未达到8192输出上限，reasoning_content为空且wire明确enable_thinking=false。这两条失败说明当前独立生成路径仍未验证通过；不据此推断所有未测来源必然失败，也不以教师成功样例或旧59/128答对代替该缺口。下一步先完成原公开输入确需的数值IR接口及新运行/六臂接线，核对既定actor任务分工，再做原定一次thinking比较与统一建库；不无变化重采样、不更换模型、不增加来源或种子。

[逐请求账本](rr_method_runtime_20261107/component_request_ledger.csv)和[费用摘要](rr_method_runtime_20261107/component_cost_summary.json)现含本Goal全部6次新增物理调用（3E/3T），已报告输入62784、输出21192 token；reasoning输出字段14139单独保留、不重复相加，请求耗时合计433.018秒。局部executor API按请求现金支出为0，GPU分摊和教师实际现金账单未知，不能填0费用。累计427E/17T、oracle130、pending0。[保全复核](rr_method_runtime_20261107/history_preservation_after_executor_contract_v2.json)确认原438条请求、121条meta、130条oracle、1233个旧run文件及4份冻结库均不变。新模型请求失败计数不退还。

[原128来源当前组件状态](rr_method_runtime_20261107/component_source_status.csv)逐行保留“新统一建库尚未开始”；A教师作用范围组件、executor独立生成失败及B实际图调用分列，不生成虚假的新版总体通过率。


## 原输入所需数值IR和联合后续请求已接线

原固定公开TRAIN中3个SARA来源包含“每$2,500或其零头”。新增ceil_divide_constant只支持精确数值与正字面量分母；恰好整除、跨一个增量、精确分数及负值边界均有回归，0/负/动态分母被拒绝。原公开收入276932与阈值250000的纯算术测试可计算增量数；这是离线运算验证，不是人工编写成功程序替代模型学习或原任务语义验收。

number_at只读取实际数值向量的非负字面量下标，越界不返回默认值。amount_values投影有独立数值向量类型；同一额度bank只由一个线程图消耗，多个EV元素复用这一次图的结果。具体额度100、资产80与70的离线检查得到剩余0与50，重复执行保持输入bank原样；混合字符串/Boolean、动态下标和不可达坏分支均拒绝。one-half只许可精确1/2字面量；100用于percent、2用于one-half时仅许可对应除法分母，不能据此生成100金额/事实绑定。结构性数组下标与原文金额分别记录。[75项相关检查](rr_method_runtime_20261107/offline_numeric_path_v1.txt)通过，不把预定义数值运算计作学到的新接口。

现有source_execution模块提供真实源文IR评估、原生格式与精确数值转换、A分离选批、全量编译和固定一单元策略。全量臂仍有残余时不以当前查询稳定早停。选中法律残余/未译源单元时，后续请求返回“完整program＋单独factual_observations”；只发送所选残余及共享上下文，规则子表达式不向事实观察器索取真值。此前事实已解析时，后续program改变其实体/谓词含义会拒绝继承旧真值。解析器仍逐条检查完整原始源文、守卫、类型、事实证据和native输出，没有借缩小请求删掉语义义务。

开发检查曾发现联合观察name枚举缺显式类型，以及固定批次按字符串排序使s10早于s5；[原失败日志](rr_method_runtime_20261107/offline_source_execution_v1.txt)保留。现已补齐联合schema类型，并按源文ledger顺序选择固定批次。[290项全量禁网络回归](rr_method_runtime_20261107/offline_source_execution_v2.txt)通过，8项历史mock空OE指标警告保留；随后只有探针接线改变，其余科学文件字节完全相同，[34项相关复查](rr_method_runtime_20261107/offline_source_runtime_wiring_v1.json)通过。不是两轮结果相加成324个独立测试。

[实际处理入口重放](rr_method_runtime_20261107/source_execution_paid_replay_v1.json)使用既有教师第17次输出的已审计source→sources单元素表示投影，并按完全相同source/payload/executor配置复用已付费事实响应；当前生产处理函数实际选中s10，服务端只读分词仍为248，12个未知/4096完成下稳定，理论哈希与原作用范围修复记录完全相同，既有TRAIN匹配记录沿用而未重新打开评分文件。此项是旧输出在新处理路径的重放加只读分词核对，不是新executor独立编译或新的真实联合规则修复成功；不增加通过来源数。三张持久表逐值不变。

当前仍待完成：Qwen独立初译的可靠生成及联合规则修复的真实验证、B候选在新源程序中的经验过滤与同材料MB、统一128建库控制器和原六臂DEV接线、原固定20来源的一次thinking配对比较、完整建库/开发/跨库证据及最终冻结交付。原Goal范围不变，不因本节修复或290项检查通过标完成。为避免生成契约继续变化后重做比较，先补齐共同运行契约再执行原定比较；当前仍OFF，不无变化重复SARA失败。

本轮模型生成0、教师0、新oracle0，累计仍427E/17T、oracle130、pending0。原始438请求、121meta、130oracle、1233旧run文件和4份冻结库的[保全复核](rr_method_runtime_20261107/history_preservation_after_source_execution_v2.json)通过。费用摘要和来源级完整建库状态均未将这次重放计为新实验成功。


## 当前统一控制器、B完整程序学习和同材料MB

新入口experiments/rr_v2_method_runtime.py只提供prepare/thinking/build/dev四个显式动作，使用原SQLite的MethodLedger，不启动历史FormalRun、不读取TEST。代码在当前开发分支保存；原128顺序、8批、B1/B8及同材料MB保持。源记录绑定当前科学版本、公开输入哈希和进入该来源前的库哈希；恢复重放原记录与请求，已提交进度不会回退。B1重建核验前16个来源，B8核验全部128个来源；DEV绑定完整父建库及冻结文件哈希。六臂共用原两次解析加一次固定fallback，全部240个来源预测落盘后才打开DEV标签，按48输出/臂及五库宏平均计入失败。

B现在从真实源IR中枚举最多32个单连接器替换，放回整条源程序并比较完整native任务结果；中间图成功不等于完整任务正确。数值事实编辑只有在原文位置对应唯一时才能重绑，改变实体/事实证据而无可验证抽取时保留未决，不用原答案补全。已付费视图与历史源级4视图预算共用，不因新运行买回丢失账本额度。空H、未绑定视图和从未实际执行的候选不发布图。输入来自既有受限Horn文法时单独标记预定义原语来源，不说模型学到了该文法。

MB直接拟合同一批候选、原始TRAIN标签和同一批预算视图，不要求先出现碰撞，不新增模型/参考准备调用。冻结只保存去掉数值、实体、case ID后的完整程序类型/结构签名、已匹配与已拒绝的图哈希及计数；原答案留在训练记录，不能变成路由指纹。完整法律wrapper与局部图共同决定候选族，不能拿局部布尔输出和完整法律答案直接相比。没有已知族的候选继续由原类型/执行/完成性检查处理，不将未观察到的候选默认为验证成功。

LibraryHornQuery将实际存储图执行器用于每一个源完成世界；缺图或图哈希不符不以普通Horn join替代发证。当前[真实旧材料接线重放](rr_method_runtime_20261107/current_B_entry_integration_replay_v2.json)在原第19来源执行12次主路径存储图、1个完成世界，TRAIN匹配；第4、14来源各4个已付费视图重放，学习结果与原记录哈希一致，三张持久表未动。这是旧兼容组件在当前入口的生产执行与离线视图重放，分列记录，不计新128来源完成、跨库迁移或新A规则学习。空库可用性负对照不能提供准确率涨分证据。

## 已核实并修复实际输入膨胀

[修复前服务端分词](rr_method_runtime_20261107/compiler_input_duplicate_before.json)确认初译消息同时复制public_task原文和units原文，并在每个单元重复大量传递上下文；最长73217输入token，原输入预算仅24576。这是实际工程契约缺陷，不能归因于8B模型能力或8192输出截断。移除重复原文，逐行保留所有原始非空单元；context改成保持每个单元完整可达闭包的等价依赖边，循环组件保留原边，所有单元逐一检查可达性完全相同，后端源文ledger未改。模式提示只发送抽象字段/图和pattern hash，来源证据仍在运行审计中，不把支持case ID发给模型作路由。

去重和上下文压缩后[128来源首次分词](rr_method_runtime_20261107/compiler_input_budget_after_v1.json)全部满足预算；进一步紧凑序列化、去掉模式提示中的支持来源后，[带原B8菜单及ON模板的128来源核对](rr_method_runtime_20261107/compiler_input_budget_after_v2.json)最长20648输入token，128/128满足原32768上下文和8192输出预留，未截断或删除条款。修复前后模板/菜单条件分别注明；这不是thinking性能比较，也不是增加模型上下文或输出配置。

修复请求保留具体字段诊断但不重复整段已提供的原文和整棵schema错误树；拒绝候选连同完整源文超预算时，由完整源文和具体错误重新生成，原候选/原响应仍在journal。每个实际请求的消息及schema属性顺序保存在不可变dispatch_json中，恢复后顺序不变，避免xgrammar属性顺序变化造成新请求。每步源状态和父程序/事实哈希都有记录；在途物理请求的BudgetError不吞作普通模型错误。

[319项全量禁网络回归](rr_method_runtime_20261107/offline_method_run_v2.txt)通过，8项既有mock空OE指标警告保留。临时账本测试实际完成模拟128来源/8批、B1未来来源污染拒绝、原失败请求保留、一次配对选择、240个来源预测的DEV标签屏障及零新增恢复；这些是离线工程证据，不是正式建库或模型效果。开发中的空params wire差异及fixture漏填answer_type等原日志保留，未改原始研究输出制造通过。

当前普通生成及联合事实/规则修复已经使用新的完整流程。原一次thinking比较的直接输出契约不适用于这个两步流程，因此按原20来源只做一次ON/OFF完整解析流程配对：每个配置最多两次原定解析请求，不调用native fallback、教师或反事实oracle；失败全部入原账本，不增加来源/seed/调参轮次。源文本与配置保持，实际模板分词差异和ON/OFF reasoning频道分别验证，再按原质量/时间/token规则选择并锁定。此前两条OFF失败及所有账本不重置，不无变化重采样。原固定20以外不加thinking小试。

本节离线修复、只读分词和原材料重放均新增模型生成0。真正的当前128建库、六臂DEV、跨库实际使用/收益诊断、源IR语义复核、费用汇总和冻结交付仍待完成；319项通过与当前B单来源不能替代原Goal验收。


## c1实际消息契约缺口与保留的六条失败（2026-11-07）

六条真实请求的chat-template token数均等于服务报告的prompt_tokens，原wire的response_format schema位于消息之外。消息称有“七个已提供typed算子”，七个算子名/参数签名实际全部缺失；原OE任务还引用了“所提供的回答schema”，当前IR schema只约束程序而没有说明原生EC/EV对象结构。证据见[prompt_contract_omission_v1.json](rr_method_runtime_20261107/prompt_contract_omission_v1.json)。这证明说明缺失，不证明六条模型错误全由它造成。金额错引、重复符号、把法律结论当事实、非逐字观察及错误来源编号仍按实际错误保留。

c1在SQLite在途为0且真实PID身份核对后停止，controller退出143；没有截断或取消物理请求。6条均finish_reason=stop，输入105909、输出18283 token，合计578.473296秒；已有本地API增量现金0美元，GPU分摊费用未知。没有新增教师或oracle；同一原账本累计433E/17T，Goal起点以来9E/3T。原始请求、响应、局部journal及[真实回归fixture](../tests/fixtures/rr_actual_method_prompt_c1.json)全部保留。[逐响应重放](rr_method_runtime_20261107/prompt_contract_paid_regression_v1.json)仍拒绝全部6条，不用新提示改写旧输出。两条完成配置和未完成Airline配置不能混入新提示的质量比较。

修复只向当前编译消息暴露共用decoder中的九类值结构、七算子参数/语义、投影及本任务原生结果schema；native fallback和主路径提示共用同一结果格式定义，正确性/源文隔离未降低。枚举类型正规化由prompt和wire共用。既有配置、数据、seed、8192输出上限和模型身份未改。46项定点检查通过；新增检查证明消息实际包含与wire一致的值结构及与fallback一致的五库原生格式，并保留六条真实错误拒绝。开发中一次测试路径拼写、枚举类型注记和本地dataset变量错误已在真实重试前修正，记录见[prompt_contract_development_failures.json](rr_method_runtime_20261107/prompt_contract_development_failures.json)。

[128来源容量检查](rr_method_runtime_20261107/compiler_input_budget_after_v3.json)仅调用既有服务tokenize，原B8菜单/ON模板下最长22149，全部可容纳原24576输入预算及8192输出预留；没有新增生成或标签。完整回归通过后，在同一Goal新科学绑定c2下执行原固定20来源的一次完整配对，不把c1半途结果拼接成比较，不扩展来源/seed/开关扫描。配置锁定后仍须完整128/8批、原六臂DEV、真实机制及跨库证据；本段不是完成声明。

完整检查收据：[offline_method_run_v3.json](rr_method_runtime_20261107/offline_method_run_v3.json)。全套首次321通过，唯一失败是测试保护器禁止了原本用于验证无训练/oracle/client导入的只读Python子进程；允许该精确脚本并在父子进程禁网络后，该测试单独通过（0.12秒）。源码/测试/配置在两次检查间完全相同，共322项，无未解决产品失败；初次失败与定点通过日志均保留。当前并未产生任何新方法成功样本或完整建库指标。


## c2后端有限枚举缺陷与内部符号重复生成（2026-11-07）

实际Airline ON响应的predicate_source指向事实编号s157，而捕获的原始wire仅允许规则s0至s154。本地JSON Schema校验正确拒绝；同一安装环境XGrammar0.1.23的原schema却接受该原文，155成员微例也错误放过s155至s159。排序枚举、附加普通pattern、分块enum和const列表均未修复，相关失败探针原样保留。上游报告有同类大型分支非成员被接受及状态合并修复；其报告版本不同，因此这里只作为相关背景，本机结论来自独立重放。[上游记录](https://github.com/mlc-ai/xgrammar/issues/618)。

修复只把原有限编号集合改写为按长度分组、合并相同后缀的数字字符类；源编号、原文、角色边界和本地检查保持一致，不加别名、不补语义。原128公开来源的360角色组归并为82集合，6748项后端成员检查无差异；真实Qwen3 tokenizer的原掩码放过s157，新掩码在越界数字处拒绝，s0/s154仍可生成。完整原始Airline wire旧接受/新拒绝，原OE wire仍通过格式而继续因整条法条残余被语义检查拒绝。[完整后端及掩码证据](rr_method_runtime_20261107/source_id_grammar_verification_v2.json)、[原始后端日志](rr_method_runtime_20261107/source_id_grammar_verification_v2.txt)。固定后端提示pattern组合时忽略长度关键字；数字模式本身已编码准确长度并通过上述检查，本地长度约束另关闭Python末尾换行锚点差异。未升级、重启或改写推理环境。

c2首OE来源ON两次正常结束但整条法条残余不合法，OFF两次均在8192输出token处截断。截断原文只进入bindings，已闭合变量名最长753字符且重复扩展燃料短语。内部符号现限定64个ASCII字符并同步声明语法；真实token掩码允许64、拒绝65及该753字符名称。事实引文、规则quote和native资产键不受此界限。此项修复防止已观察的重复路径，不声称解决所有模型错误或所有截断。[真实未闭合输出](../tests/fixtures/rr_actual_method_c2_repetition.json)保留，没有补JSON闭合或规则。

c2全部8个物理请求已结算、取消0；4个正常结束、4个达到输出上限。原始输入134146、输出43915 token，合计1386.363845秒。只有3/40配置形成最终记录，第四配置两条付费原文仍保留；不能据此前两个来源选定thinking。累计441E/17T，本Goal新增17E/3T、oracle新增0。已结算输入302839、输出83390 token，合计2397.854763秒；教师reasoning字段14139另存不相加。执行器API增量现金0美元，GPU分摊与教师实际账单/credits未知。[逐请求及费用证据](rr_method_runtime_20261107/c2_settled_call_evidence.json)、[Goal费用快照](rr_method_runtime_20261107/goal_cost_snapshot_20261107.json)。旧438请求、121meta、130oracle、1233运行文件和4冻结库核验不变。

先前编号修复全套324项通过；加入真实重复名称回归后[325项完整检查](rr_method_runtime_20261107/offline_method_run_v5.json)通过，8个既有mock指标警告保留。新[128输入检查](rr_method_runtime_20261107/compiler_input_budget_after_v5.json)最长22190，仍在原24576输入预算内，输出8192、模型、采样、seed不改。当前尚无新整体主路径语义成绩；c1/c2作为实际契约诊断保留，未完成比较不混用。下一科学绑定c3继续原固定20配对，完整配置选择后仍须128/8批、六臂DEV、跨库及冻结交付；本段不替代原Goal验收。

当前配置判读仍遵循用户“收益不明显保持OFF”：格式通过或更短的失败不计对应语义收益。c3完整配对先汇总真实语义、耗时和token，由当前执行者按这一口径复核后锁定；不把旧统计器默认ON当作授权，也不追加新的开关扫描。


## c3实际嵌套失控与最小契约修复（2026-11-07）

真实ProofWriter首ON响应的连接图嵌套达到1301个JSON容器，原始json.loads报RecursionError；输出达到8192上限。第二次响应及OFF响应还出现重复节点/作用范围，均保存为模型输出错误，没有补JSON、补规则或补真值。c3在账本pending0处停止、controller退出143、取消请求0；完成16个物理请求，7个配置已形成最终记录，其余已付费raw及journal原样保留。7次stop、9次length，输入173946、输出89040 token，请求耗时3670.970067秒。见[逐请求证据](rr_method_runtime_20261107/c3_settled_call_evidence.json)及[真实回归原文](../tests/fixtures/rr_actual_method_c3_depth.json)。7/40不是有效完成的比较，未据此切换配置或宣布主路径通过。

具体实现缺口是当前源IR schema未应用既有EXPRESSION_DEPTH=16，旧通用展开器也只识别args、不识别连接图inputs。现将两种子边统一有界展开，保留同一节点16层；长计算仍可用具名DAG节点分解，不限制总程序的可表达计算或减少源文义务。当前固定XGrammar0.1.23对原始失控图前缀旧允许、新拒绝；三类AST的0/1/16层允许、17层拒绝，真实Qwen3 token掩码与本地校验一致。[后端证据](rr_method_runtime_20261107/source_wire_bounds_backend_v1.json)是语法边界回归，不是任务执行或方法语义成功。

绑定schema另同步现有binding_literal_audit的必要词面条件：公开源文没有数值时关闭不可能通过的非空数值/金额原语，没有逐字true/false时不允许Boolean binding；仅含false时不允许True。空金额列表仍依原语义保留，relation的closed等结构属性未受影响。prompt和wire共用相同值结构，不推断句子的事实真值，不补造缺失法条，也不放宽正确性检查。已有OE错引s200标题、Airline派生总额及SARA错引工资金额仍按错误保留；没有虚构英文数词解析修复。

[342项完整离线回归](rr_method_runtime_20261107/offline_method_run_v6.txt)全部通过，8项原mock空OE指标警告保留；检查期间科学文件字节不变，父进程禁网络/子进程，只允许带相同禁用保护的精确只读导入检查子进程。[128来源容量核对](rr_method_runtime_20261107/compiler_input_budget_after_v6.json)在原B8菜单/ON模板下最长22220输入token，全部满足24576输入预算和8192输出预留。测试和tokenize没有新增模型生成或oracle。

当前运行的thinking判读已执行用户最新默认OFF偏好：原Pareto策略推荐只供审计，格式成功或更短失败不算语义收益；完整原20配对若没有主路径TRAIN匹配净收益则保持OFF。实际token和耗时仍分列报告，both-invalid与实际后端开关核验仍执行原工程门槛，不因少数样本或离线绿灯跳过原Goal。

累计457E/17T，本Goal起点424E/14T保留，新增33E/3T、oracle新增0。已结算输入476785、输出172430 token，请求耗时6068.824830秒；教师reasoning字段14139另存不加总。执行器API增量现金0美元，GPU分摊和教师实际账单/credits未知。见[总费用](rr_method_runtime_20261107/goal_cost_snapshot_20261107.json)、[本Goal每次请求CSV](rr_method_runtime_20261107/goal_request_ledger_current.csv)。[保全核验](rr_method_runtime_20261107/history_preservation_after_ast_depth_repair.json)确认原438条请求、121条meta、130条oracle、1233旧运行文件、4份冻结库不变。

下一步仅在上述离线证据对应的新科学绑定c4中接续同一原20来源完整配对，随后按选择锁定和原Goal执行统一128/8批、六臂DEV、机制及跨库证据。c1/c2/c3保留为真实故障/契约诊断，不拼接成新版本质量比较；不新建Goal、不重置账本、不增加来源/seed或模型采样配置。普通模型失败按原流程继续，不原样反复重试。当前Goal active，未完成。


## c4英文数词的真实误拒及修复（2026-11-07）

c4四个真实请求已全部结算，3次stop、1次length，输入91173、输出18152 token，耗时918.497385秒；没有取消请求或新增teacher/oracle。在账本pending0处停止、controller退出143。仅ON配置形成最终记录，OFF两条已付费raw/journal保留；不能用1/40选择thinking。ON首答和纠正答的程序content逐字相同，均将“exempt under…”法律结论装入原子事实观察，仍是模型错误，不按格式适配恢复。见[四条原始用量](rr_method_runtime_20261107/c4_settled_call_evidence.json)及[运行期源文审计](rr_method_runtime_20261107/method_runtime_c4_20261107_source_only_observation.json)。

OFF首答已正常结束、5346输出token，其20个被拒金额中9个确实对应逐字源文数词：five hundred→500、four hundred→400、one thousand→1000、two thousand→2000、two hundred fifty→250、five thousand→5000、two thousand five hundred→2500（两种来源各重复一次）。这是当前真实合法值的词面兼容缺口，与c3的500错引s200标题、15000错引s201“五百”不同。[逐字段修复前后](rr_method_runtime_20261107/cardinal_literal_before_after_v1.json)使用保存的1b64616审计器和当前审计器分别运行，旧20拒绝→新11拒绝，9个值仅作确定性词面识别；原模型candidate字节完全不变，没有读评分标签。

实现只支持普通基数词零至千位组合、连字符和hundred后的and等无歧义语法；复合数不拆出其组成数字，one-half仍只有1/2，畸形数词、大尺度/带符号的未支持表达不猜测。两行独立引用不会拼成新的数。无金额的健康辅助器具、衣物、宠物、婚姻权利等11个虚构额度仍拒绝，旧IR整体仍未恢复。因此本项修复不增加当前主路径成功来源或技能数量。

[362项完整禁网络回归](rr_method_runtime_20261107/offline_method_run_v7.txt)通过，8项原mock空OE指标警告保留，检查期间绑定文件字节不变；[128来源输入检查](rr_method_runtime_20261107/compiler_input_budget_after_v7.json)全部满足原预算，B8/ON最大22220输入token、原输出预留8192。没有新模型调用或新oracle。[历史保全](rr_method_runtime_20261107/history_preservation_after_cardinal_repair.json)确认原438请求、121meta、130oracle、1233旧文件和4份冻结库不变。

为避免为处理器修复重买相同响应，新科学绑定c5先经当前生产控制器重放与原公开source/model配置一致、实际HTTP body逐字一致的paid prefix；核对原ledger、wire_request、wire_response和result字段，仅取最早完全匹配的物理响应，不依据正确性选择。保存physical_origin_call_id、当前代码绑定及请求/原始响应哈希；重新执行当前解析、语义检查及TRAIN评分，不沿用旧分析/旧评分。重放脚本禁止executor.generate/teacher.summarize，在首个wire不匹配处留下当前journal，普通controller从此处继续。原请求始终计入原物理账本，不插入伪物理行、不返还失败额度；此前未复用的length响应仍计费。该兼容重放不被写成新独立生成或新增成功。

累计461E/17T，本Goal新增37E/3T、oracle新增0、pending0。已报告输入567958、输出190582 token，请求耗时6987.322216秒；教师reasoning字段14139单列不加总。执行器API增量现金0美元，GPU分摊与teacher实际账单未知。[实际物理请求CSV](rr_method_runtime_20261107/goal_request_ledger_current.csv)和[费用快照](rr_method_runtime_20261107/goal_cost_snapshot_20261107.json)保留全部调用；CSV仅统一行尾为LF，逐行字段核对未变。当前原20完整比较、统一128/8批、六臂DEV、实际机制/跨库证据和最终冻结交付仍待完成，Goal active未完成。


c5已实际完成[逐字兼容prefix重放](rr_method_runtime_20261107/c5_exact_paid_prefix_replay.json)：3条原executor响应分别对应原ON初译、ON纠正、OFF初译，HTTP body逐字相同、原始响应/来源/物理ledger/result核验一致。新生产控制器重新生成1条ON配置记录及OFF step0状态，新增模型/teacher调用0，物理账本逐行不变。两条ON输出的原模型错误保留，OFF初译只消除了9条词面误报，仍有11条无依据金额，不把重放记作核心成功。

[首个变化请求证据](rr_method_runtime_20261107/c5_first_changed_retry_proof.json)确认OFF step1实际body哈希已变化；原c4达到输出上限的纠正响应未复用，仍在原账本计费。当前正常controller从该请求继续，[local process identity omitted]；不重发前三条，不重启旧c4。该次兼容重放与新物理生成分列，当前完整20比较尚未结束。


## 原32个OE来源的真实作用范围边界修复（2026-11-07）

原始公开数据的EC/EV视图各提供72个独立法条标题，共144个；旧登记器仅识别Federal/Illinois的40个，遗漏Ariz./Or./Pa./Wis.的104个。层级又只按括号数量比较，令不同法域、不同法条甚至兄弟条款继承前一条款。真实首来源Ariz.33-1101(A)继承11U.S.C.522(m)，33-1101(B)又继承(A)；全32来源每个均有1368个错误标题祖先关系。它们会被lower_clauses物理用于守卫，属于作用范围实现错误，不应归因于模型。

现按原公开六种引用拼写识别标题，并只在相同statute base、真实括号前缀之间继承上下文。没有推断缺失的父条款或法律真值。重复的独立Illinois标题不再被登记成指向另一重复标题的“引用”；真正行内引用原接口保留，本批真实OE此前那两处都是独立标题。Statutes标签、Solved Reasoning Steps及固定boilerplate按原数据字段登记为标题/指令；原已公开提供的司法辖区前提作为问题给定前提登记，未推断真值、未增加内容，不拿它当学到的新规则。全部原文与sN编号逐字不变，未译法律规则仍留残余。

[全部128来源修复前后](rr_method_runtime_20261107/source_boundaries_before_after_v1.json)证明：32个OE来源均144/144标题识别、错误标题祖先关系0、伪标题引用0；其余96来源结构版本逐值不变。原s121/s282被错误传播的跨法域“条件前言”不再强加给别的法律，条款本身的条件仍须实际AST翻译。本证据证明登记和作用范围插入正确，不证明模型的自然语言翻译或任务答案。真实输入重复视图仅作[输入形状记录](rr_method_runtime_20261107/fixed20_public_source_shape_audit.json)，没有擅自去重或删除来源。

[366项完整回归](rr_method_runtime_20261107/offline_method_run_v8.txt)通过，8项既有mock警告保留，检查时绑定文件字节不变。新增实际32来源边界检查和跨法域守卫负对照，SARA原作用范围路径未改变。[6748项编号后端及真实token掩码检查](rr_method_runtime_20261107/source_id_grammar_verification_v3.json)通过，两个旧paid wire仍原样保存。首次检查曾误以为旧OE残余指向公开前提，查回真实原文后确认它引用s176/s201真实法条，故格式仍应允许、整条残余仍由语义检查拒绝；仅纠正离线探针的错误预期，原失败日志保留，没有新增模型调用。[128来源容量](rr_method_runtime_20261107/compiler_input_budget_after_v8.json)在原B8/ON模板下最大22033，保持24576输入预算和8192输出预留。

c5在物理请求全部结算后停止、退出143、取消0。新增4E，3次length和1次stop，输入56662、输出28641 token，耗时1118.402266秒；3/40配置与未形成配置的paid raw完整保留，旧三条兼容重放不新增物理行。Airline正常结束的纠正答仍把派生袋数作为字面量、错引用第三袋费用，按实际模型错误拒绝；OE边界修复不把该错误改判成功。[c5真实账本](rr_method_runtime_20261107/c5_settled_call_evidence.json)。

为避免重复调用未受影响的来源，单配置处理抽成同一thinking_profile生产函数，正常比较与禁模型的逐字重放共用。重放可处理后置、相互独立的原配置，未改变seal中的原20来源/顺序或空库比较条件，不读取未来库内容；每条只有实际wire字节一致才复用，不按正确性选择，不复用旧分析或旧评分。正常controller继续原顺序，只有完整40配置才能选择thinking。新OE上下文请求改变，旧OE输出不可冒充当前生成；原Airline等未变请求可逐字核验后重放。

累计465E/17T，本Goal新增41E/3T、oracle新增0、pending0；输入624620、输出219223 token，请求耗时8105.724482秒，教师reasoning14139另存不加总。执行器API现金增量0美元，GPU分摊和教师实际账单未知。[原始438请求/121meta/130oracle和1233旧文件保全](rr_method_runtime_20261107/history_preservation_after_source_boundary_repair.json)通过。原20完整比较、统一128建库、六臂DEV、实际学习/跨库使用与最终冻结交付仍待完成。当前Goal active未完成。

公开b44437d是未完成中间快照。导出中误带了冻结环境的依赖源码；当前公开树将收紧到科学源代码、测试和原始研究证据，原始实验结果不删改。第一次远端核验在一个空依赖文件处未完成，不能记成全文件核验成功；修正导出后重新独立fetch并核对全部清单，main保持原提交。


c6已完成[逐字兼容配置重放](rr_method_runtime_20261107/c6_exact_paid_profiles_replay.json)：3条原Airline真实wire分别匹配原ON初译、ON纠正、OFF初译。当前生产函数重新形成1个ON配置和OFF step0 journal；物理账本逐行不变，新增model/teacher0。原ON纠正的两项字面量错误照旧拒绝，不记核心成功。全部原20来源/顺序及空库比较条件未变，OE的上下文请求不匹配旧wire，未复用旧OE结果。正常controller现从原第1来源开始真实验证，后续遇到已兼容配置/状态则按原journal恢复，不重买这3条响应。当前完整比较仍未结束。


## 当前开发分支交付已核验（2026-11-07）

修正后的科学源代码/报告快照为[6b056b9](https://github.com/H00RU/LegalSkillGuard/commit/6b056b9f7fec7cae2c787776749a56b64428b754)，对应本地实现2db5ac8。1534个误带的环境或非科学备份路径已从当前公开树移除，原始科学源代码、测试、失败输出和物理账本保留。独立远端fetch逐项核对872个清单文件，SHA256全部匹配；当前导出没有环境镜像或空文件。此前未完成的核验没有记作成功。

[核验凭据](https://github.com/H00RU/LegalSkillGuard/blob/f041773f9b258ca5a1bfbd08cf6df93a8670cc3d/reports/rr_method_runtime_20261107/publication_verified.json)已单独推送并从远端核对两份凭据文件，开发分支现为f041773。源代码和原报告字节仍以6b056b9快照为准；main前后均为ae7e09230b4eb675b7299f73c4775787ccb2b65b，未更改，未上传私有Git祖先或SQLite私有meta。公开报告页面已实际打开验证可访问。发表动作新增模型/teacher/oracle0。

这是进行中的版本交付，不是最终冻结。当前c6仍按原20来源完整配对运行；截至2026-11-07T04:48:53Z，5/40配置（含逐字兼容重放）已经记录，结构和对应TRAIN匹配均0，源于现有模型的无依据字面量、错误法律谓词或输出截断。累计473E/17T、pending1。控制器真实身份和3737冻结文件保持一致，未重启、未改模型配置、未启动新128/DEV/TEST。后续依据完整当前版本结果继续原Goal，不凭本次修复或GitHub同步标记完成。
