# 当前证据与下一项实际工作

2026-11-14。同一Goal **active、未完成**。目标、验收、授权及边界只由[CURRENT_GOAL.md](CURRENT_GOAL.md)规定。唯一项目`/home/yndx/hhy/legal-skill-current`，开发分支`repair/lift-corev-activation-20261112`，不改main。历史暂停、Goal卡及旧PID不触发操作。

## 当前实际执行与结论

MAUD固定四母获取、两母后续复用已经完成并终结保存，不再运行或重发。entry为experiments/legal_skill_evolution_MAUD_rule_acquisition.py，run为legal_skill_evolution_MAUD_compact_20261114；原rule_acquisition run的教师超时也完整保留。当前没有模型客户端或reserved请求，持久推理服务不是实验队列。

|固定范围|C拟合|同φ/建议G的NoFit|自由教师原版|公共句界修复后Free|简单控制|
|---|---:|---:|---:|---:|---:|
|四母获取，正确/12|12|12|11|12|12|
|获取核心执行/12|12|12|12|12|不计核心学习|
|两母后续，正确/6|4|5|4|5|5|
|后续核心执行/6|5|6|6|6|不计核心学习|

fallback物理调用0，错误/未覆盖保留全部分母。NoFit与公共修复在后续材料执行前冻结；两个原版及两个控制的24份无标签执行全部保存后才生成30份原生评分。旧完整TRAIN暴露已披露，不称新盲测。[报告](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/update_train_result.md)、[逐来源](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_MAUD/source_results.json)。

**实际学到什么。** C教师取得15构造子、3真实读取操作及10条类到结构的直接映射，36次获取读取、18次后续读取均完成。Free独立取得14构造子、一个可运行来源程序，神经操作0。二者均真正生成并消费有当前出处的类型根，不是fallback。但是本次C没有跨概念连接，原生分类由简单控制吸收；不存在额外C收益，U真实φ/G更新字典仍为空，两项未成立。不能把10条规则、426项软件检查或12/12当作贡献验收。

**原因已区分。** (1) contract_101的读取正确识别实际知情，G复杂度最小化却删掉获取四母均未激活的g_knowledge_actual_only，导致少覆盖1题；NoFit答对。(2) Free把Section 1.1(a)中的点当句号，丢失后文询问义务；相同公共标点重写对双方开放，C无此模式、Free4处改变，先修复并冻结再执行后续对；不能将这个普通解析缺陷算成C优势。(3) contract_101日常经营题各版都错；准备输入与固定官方TRAIN行逐字一致，核实母合同原文后找到被该题摘录省略的疫情视为日常经营限定。完整母合同只用于评分后的定位，没有补进actor输入、改标签或重跑。(4) C在13/41/70实际路径把未指定的询问对象补成知情人或雇员，原生Constructive正确不认证这些额外角色。[实际源检查](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_MAUD/actual_source_review.json)、[摘录/母合同核查](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_MAUD/postfreeze_contract101_context_audit.json)。

**具体修复已落地。** fit_composition与真实fit入口现支持明确的已有G选择先验，顺序为原生损失→最少选择编辑→复杂度；所有来源硬约束、可能unknown世界与谨慎执行检查保持。真实12份获取记录离线拟合仍12/12，保留全部10条建议规则，选择编辑0；原复杂度版7条及原冻结分数原样保留。430项软件回归通过，含反证必须删规则、原生错误优先于保留、unknown不填事实。没有重跑已评分两母，不能宣称新的5/6或新方法增益。[实际记录回归](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_MAUD_revision/result.json)。

**下一项实际工作。** 复用已有实际源观察、失败及更新记录，核对当前C真正缺的是可区分源概念、G组合，还是原题输入；只对有明确来源证据、会进入执行路径的缺口作下一次学习，不再重复无需组合的MAUD类别路由小试。该固定研究已经显示复杂度拟合没有额外作用，规则保留修复不能充当完整贡献。U仍需真正源绑定的可复用修订及独立作用，不能将句界补丁或规则保留凑作U正例。当前两个方向不因单个负例改名，若现有真实范围没有所需独立作用，再集中说明研究调整，而不批量追加请求。

**成本与恢复。** 整个MAUD研究新增54E/3T，含Free一次600秒超时；累计10156行＝9929E/227T，在途0。10099条此前记录及10101条continuation之前记录逐条hash保持。执行器99333输入/2109输出token、71.198服务秒；成功教师106513输入/28808输出（含15234reasoning），教师含超时1134.563服务秒，失败usage未知、现金发票/GPU分摊未知。thinking OFF/max8192实际wire全部核对。教师C付费输出原样复用，Free重试前仅删除可精确重建的重复编码表，12份回环一致；没有隐形自动重试。[逐请求成本与保持](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_MAUD/cost_and_preservation.json)。

逐视图MAUD类型/出处/消费者/原生标签接通；示例可来自同母任一实际独立视图，但不拼接引文。多阶段G精确枚举有真实软件回归，实际本次G均直接映射，不能以软件覆盖冒充机制实测。426项相关软件回归通过；绑定源码/数据、控制冻结hash及全部评分顺序核对后写TERMINAL_PRESERVATION。当前Goal active、未完成，继续原范围研究，不启动完整训练、DEV/TEST或论文。

## 前一闭环的终结状态

当前entry为`experiments/legal_skill_evolution_query_refinement_train.py`，run为`legal_skill_evolution_query_refinement_20261114`。固定八母获取、四版本冻结、原TRAIN最后两母bc93/6d10执行及原生评分均已完成，TERMINAL_PRESERVATION核验所有源码/数据绑定与10095条旧账本。session42510、20098、76212均结束，在途0，不重复启动。419项软件回归通过；源码快照完整保留，后续修改不用于重跑该协议。

|最新固定范围|C静态|C＋补读选择|Free静态|Free＋相同选择器|
|---|---:|---:|---:|---:|
|八母获取，正确/32|29|29|31|31|
|获取核心执行/32|30|30|32|32|
|bc93/6d10冻结后正确/8|3|5|3|3|
|冻结后核心执行/8|6|8|4|4|

fallback调用0，错误与未覆盖留在原分母。所有8份无标签后续执行保存后才评分；后续选择仅用unlabeled_core_coverage，未用其标签。原完整TRAIN历史暴露保留，不称新盲测。[当前报告](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/update_train_result.md)、[逐来源](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_query_refinement/source_results.json)。

## 实现与证据现在能支持什么

选择器在当前已学操作的有限条件答案上执行固定G/消费者，选择可能改善合法TRAIN误差或无标签执行覆盖的实际读取。反事实答案不能用于真实缓存或G训练，不冒充源语义。实际补读仍走原单位证据、类型、作用域和thinking OFF客户端。相同选择器对Free开放，并沿用实际已学query ID，避免因固定ID接口人为弱化对照。

获取时仅选择62fd处置问题，精确复用旧付费读数，新增请求0；actual candidate_found只引用交易讨论序言和存续句，未取得返还/销毁动作，故两项仍未覆盖。规划遗漏已处理，弱读取器误读保持，没有把假设有用的答案补成实际答案。

bc93的两项新增正确依赖一次真实全源读取、所学G生成complete_source_no_disclosure_permission、消费者实际使用新根。全文没有内部或专业接收者的披露许可；Company employees/third parties描述信息来历，逐案书面授权也在该操作排除范围，故本次负判断与路径有对应支持。**这是一母合同的局部正证据**；6d10两个披露答案仍错，不能以覆盖8/8替代语义正确。[逐路径核查](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_query_refinement/actual_incremental_source_review.json)。

普通完整读取的事后离线控制：复用三条已付费关键读取，枚举唯一未读处置操作的全部声明选项及unknown，原生预测均与实际C补读版相同。未读分支不称真实运行/源语义或实测费用，新增模型0。选择器少问一条无当前原生作用的问题，**不能据此认定C的开放概念发明、共同组合和U贡献均已成立**。[精确条件不变性](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_query_refinement/eager_read_offline_control.json)。

U保留源关系、旧/新AST共同typed参数、跨组件绑定、歧义保持、有限守卫、源常量检查、条件编码和source_program编辑接口。真实φ/G更新字典仍为空，尚无后续选用、负适用与独立收益。旧Airline/de42同例收益被完整修复复用吸收，保持关闭。两项均未达到Goal验收。

## 固定MAUD范围与输入边界

沿用原TRAIN顺序的contract_13、41、111、80四母获取，101、70两母后续复用，选择先于新MAUD反馈，未按错误挑选；[清单](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_query_refinement/next_MAUD_fixed_selection.json)。每母三视图仍是一来源，每视图只使用自身提供材料，不跨视图填omitted内容。旧Full/Free B8没有保留MAUD技能，真实已付费NDA来源程序作为共同资产而非补造初始MAUD知识。contract_101完整母合同核查是事后诊断，不能据此更改冻结输入；后续若改变材料可用范围必须明确作为协议变化记录，不能混入旧分数。

## 账本、成本与继承资产

唯一连续账本artifacts/rr_v2_preflight/research_ledger.sqlite3。前一NDA补读轮新增**4E/0T**，当时累计**10099行＝9875E/224T，在途0**，原10095条逐条hash保持。执行器8876输入/456输出token、13.630服务秒，实际wire均thinking OFF/max8192；现金发票/GPU分摊未知。[逐请求与保持](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_query_refinement/cost_and_preservation.json)。419项回归、补读选项枚举、源核查和完整读取离线控制模型新增0。

此前共同来源程序研究获取C29/32、NoFit29/32、Free31/32，ef7b/467e复用均2/8；2E/2T，10095行终结。双方source_functions真实编译并执行，逐根区分共享旧资产与来源程序新建/修改；16个真实输出均是合法构造子及当前出处，412软件回归通过。实际组件删除C来源更新29→28、Free31→28，不能据此宣称C独立贡献。[原证据](../reports/legal_skill_evolution_run_20261111/method_investment_20261113/real_source_functions/source_results.json)。

更早scalar研究C23/32、NoFit19/32、Free24/32，c46f/96361复用5/8、4/8、1/8，部分表面增益依赖错误的明示留存分类、角色/条件遗漏，语义未通过。125E/2T与之前154E/3T（含600秒超时）分别保持，不同后续对不混算。原A/B、M1/M2、Lift/CoRev、128母/8批、七系统DEV/TEST、源码快照、失败、原始响应和账本都保留。

原TEST已暴露，不用于新修补或声称新盲测；当前阶段不启动新完整训练、DEV/TEST或论文。持久vLLM服务不是实验队列。Goal保持active，未完成，不自行暂停或重置。
