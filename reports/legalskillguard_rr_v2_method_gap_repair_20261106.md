# RR-v2 方法缺口修复与训练就绪验收

2026-11-06。**工程验收通过：可以进入主训练的阶段审批；本次未启动主训练。** 此结论基于 A/B 实际入口、五库契约、固定20来源恢复、真实定点补验、账本和后续流程的联合证据，不以单个成功或零回退为门槛。交付正在开发分支核验；完成交付后关闭本阶段 Goal 并停止，等待复核。

## 缺口、修改与证据

| 原问题 | 本次实现 | 已检查的证据与边界 |
|---|---|---|
| A 的有限理论内核接不到生产文本；路由测试注入计划 | `source_completion.py`从公开完整声明提取域与观察；`public_horn.py`提供未读公开断言的完整布尔观察。`compilation.prepare_request`从已接纳程序重建理论，连接`ingest_source`及`route_prediction` | 原人工XOR和同见证PW微例经过真实业务入口：先解析、产生残余、选择联合批次、发送所选条款及上下文、第二次解析、稳定检查；没有注入assessment、theory或预计算计划。实际模型回复在该微例中是离线fixture，不称真实生成 |
| A 成本使用条款数 | 规划器调用生产tokenizer；消息只包含所选/上下文源单元，共享上下文去重，绑定实际序列化wire body | 当前Qwen请求输入 **1641 token=1585基础请求+56选择/上下文增量**，一次调用，输出预留8192、上下文32768。实际分词与服务端`/tokenize`逐token相等；请求体SHA见backend凭据。输出预留是容量，不冒称实际输出费用 |
| 五库接口外层允许解析器不接受的字段 | sender与runtime共用7种连接器及typed bindings的定义；空接口合法 | 原CNLI index4/9/14的坏字段原样保留，新sender和解析器都拒绝；index19合法空接口保留 |
| 第125次新响应暴露CNLI/PW程序体仍宽松 | 五库都使用有界程序体契约；expression必有bindings/query/source_links，字符串类型是scalar，名称有类型前缀；PW额外保留public_horn | 原响应缺query且使用不存在的type=string；未补字段或改成unsupported。154项离线检查及78个实际xgrammar用例通过；不同代码/配置绑定下再请求同一CNLI来源，第126次通过wire与解析，native回退单列 |
| B在非PW来源没有可执行候选学习入口 | `learn_source`对OE/RA/SARA调用`typed_learning`，从真实联合提议的typed primitive/interface构造≤32个有类型候选，执行、过滤、碰撞细化并参数化冻结；原4视图总账不变 | 离线SARA人工同实体例经ingest→DurableOracle→候选学习→真实join→冻结，2个事实视图匹配独立人工参考函数。额度例实际执行共享bank、数值投影与分配，但80/120顺序变化并非同I/O碰撞，不能计B碰撞正例。真实金融/税务来源仍没有已验证的数值连接成功，未冒称已经解决 |
| B旧“粗接口”使用事实摘要而非实际原语I/O | PW使用实际原语关系的exists输出与初始查询证据；typed路径用真实Relation/Amount等输出并保留顺序。旧单行SARA视图不能无歧义映射到自然语言时保留未绑定，不重解释标签 | 原4条PW旧记录按当前算法重算碰撞为 **3、0、6、3，共12对**，原22对口径撤回；index8无实际碰撞，B核心成功撤回。旧数据、旧判断、未成功视图均保留。没有附加H必须缩小、唯一识别或全视图可重绑要求 |
| 新代码错误沿用旧就绪凭据与teacher材料 | `readiness.py`直接核验当前材料、当前代码与真实补验；正式入口复用当前已检查的训练材料和原ledger origin；不要求与旧wire逐字兼容 | 当前20来源/冻结库禁网络禁子进程重算一致，120次六臂控制流完成（mock回调复用旧原文，非真实评测）；旧binding凭据被拒绝。B观察已改变，旧教师汇总不冒充当前汇总；本次新汇总仅接纳已验证的一个参数化模式，无待验提议 |

未知规则、未知作用范围、冲突、域外、空Ω和超时仍阻止不当稳定；H仍不是Ω。未增加来源、种子、调参轮次或正确率门槛。A的新自然语言观察域仍是受支持的受限公开文法；并不声称任意法律条款已被完整形式化。

实现路径为[compilation](../legal_skill_guard/rr/compilation.py)、[source completion](../legal_skill_guard/rr/source_completion.py)、[public Horn](../legal_skill_guard/rr/public_horn.py)、[typed B learner](../legal_skill_guard/rr/typed_learning.py)、[canonical contract](../legal_skill_guard/rr/strict_contract.py)、[shared ingestion](../legal_skill_guard/rr/preflight.py)及[readiness](../legal_skill_guard/rr/readiness.py)。基线与第一次OFF失败实现另存本地提交`138dd41`；最初研究源码、原始评分、前阶段失败和账本未重写。

## 真实流程与离线验证分列

| 证据 | A | B |
|---|---|---|
| 本轮新OFF真实请求：原PW index13 | `public_horn`实际执行，False与参考一致；非fallback；本次已读全部17单元，Ω中1个补全世界，残余0，不声称线上命中非平凡选批 | 真正运行learn_source，不返回缓存学习结果；使用原已计费oracle标签，6个同I/O异答碰撞由entity_equality分开；原例+4视图共5次连接语义检查匹配。H=8→8，保留歧义 |
| 原4个真实ON输出，当前算法离线重验 | index3/8/13/18均通过受限文法主路径语义；这是历史真实输出的当前重算，不是4条新OFF预测 | index3/13/18仍有效，index8无碰撞。对应原语、候选与连接执行重新计算，非复制旧学习结果 |
| 人工离线业务链 | XOR联合选批、共享上下文一次计费、PW未读相关/无关断言、TOP和错误声明等 | SARA实体连接正例；逐项/整体cap、共享额度不复制、守恒与顺序、无法恢复见证、候选与oracle上限等；额度微例不冒称碰撞学习成功 |

原固定20来源的唯一来源覆盖为A 4/20、B 3/20；其中新OFF核心证据各1/20。A最终任务回退16/20（80%），其中6条native正确，不计核心成功。B其余17/20缺少已验证的碰撞驱动连接，**不是测量得到的B预测fallback率**；本次PW真实B调用无fallback。当前20训练材料有19条历史ON生成的原文重处理、1条新OFF生成，保留各自生成绑定；不是完整20来源OFF小试，也不会充当未来OFF预测缓存。

第126次CNLI真实补验为合法unsupported/空接口，native正确，明确不计A/B核心。历史20材料native正确仍为10/20，不将其解释为新配置的准确率或质量等效证据。

## 原固定来源状态

以下归因沿用[前次逐来源复核](legalskillguard_rr_v2_readiness_review_20261106.md)，工程契约缺口按本次新验证更新。完整ID、诊断、生成来源与当前工件见[来源清单](rr_v2_evidence/method_gap_repair/source_status.json)。

| index | 数据集 | 目前状态与归因 |
|---:|---|---|
|0|OE|模型资产/引用/金额语义不完整；A回退。B提议未给可执行typed primitives，现有入口返回typed_inputs_unavailable，不能称已完成候选搜索无解 |
|1|RA|旧模型输出截断，既往费用错误；失败保留。B输入不足 |
|2|SARA|模型语义错误，另有一次历史oracle输出失败仍占额；flush缺陷已有修复，未重查抹除失败。B输入不足 |
|3|PW|A受限文法主路径；B实际粗I/O的3对碰撞与连接语义有效（历史输出当前重算） |
|4|CNLI|旧坏接口及第125次坏IR保留；第126次新契约通过，合法native回退；无正式反事实oracle |
|5|OE|模型遗漏资产/引用；A回退，B输入不足 |
|6|RA|费用计算语义错误；A回退，B输入不足 |
|7|SARA|native回退正确，旧IR规则不忠实；B输入不足 |
|8|PW|A主路径有效；按实际粗I/O没有碰撞，B核心成功撤回，属于允许不细化 |
|9|CNLI|旧坏接口不作语义适配；同一sender/parser缺陷已修并由index4补验。原native回退正确 |
|10|OE|模型规则、资产或引用错误；A回退，B输入不足 |
|11|RA|模型费用规则错误；A回退，B输入不足 |
|12|SARA|旧模型答案/规则错误；旧字段摘要不再算B已验证模式，typed输入不足 |
|13|PW|本轮新OFF真实A/B主路径均通过；A残余0，B 6对碰撞、5次语义检查，H未强制缩小 |
|14|CNLI|旧graph列表/字段形状不恢复；当前共同契约已修。原native回退正确 |
|15|OE|两次旧输出截断，未补造缺失内容；A回退，B输入不足 |
|16|RA|模型规则导致费用错误；A回退，B输入不足 |
|17|SARA|native回退正确、旧IR错误；无合格旧视图正例，B输入不足 |
|18|PW|A主路径有效；B 3对实际碰撞与连接语义有效（历史输出当前重算） |
|19|CNLI|合法unsupported、无oracle，预期native回退 |

没有剩余证据表明这16个非A核心来源会系统性中断其他四库正式循环。当前控制流重放全部完成，缺输入、模型错误、参考失败与合法回退被分开保存；未把流程可继续等同于语义答对。模型忠实性和数值任务的真实B效果仍留给原研究流程，不要求为解决这些错答反复补验。

## 账本、配置和费用

本轮新增 **3 executor、1 teacher**，累计 **127/6000、4/20**；pending=0，oracle仍50。原127条调用行（124E+3T）、111条meta逐值保留；元数据只追加授权/新绑定/精确请求。模型、seed45、temperature0.6、top_p0.95、top_k20及并发1不变，仅按用户明确指令关闭executor thinking。三次新executor均请求OFF且reasoning_content为空。旧40条对照与原ON选择保留，不伪装成OFF。

| 新物理请求 | 输入/输出token | 耗时 | 验证结果 |
|---|---:|---:|---|
|E125 CNLI，第一次OFF|3111 / 4072|113.248s|wire通过、IR缺query且类型错误；native正确不计通过 |
|E126 同CNLI，明确程序体修复后|3201 / 43|5.296s|wire和解析通过，合法无证书回退 |
|E127 原PW index13|921 / 113|6.190s|A/B主路径及语义通过 |
|T4 当前首16来源汇总|16943 / 199（含46 reasoning output）|29.615s|接纳已核验模式1个，pending 0；adapter attempt=1 |

executor合计输入7233、输出4228、124.734秒。现有本地服务无逐请求API新增现金支出（0美元）；GPU实际分摊费用没有账单，不能据此称算力免费。教师使用既有授权适配器，真实现金账单未暴露，USD为未知；不把token或估计credits当实际费用。教师temperature未显式设置且后端默认数值未暴露，`reasoning_effort=high`不是温度。

按原后续矩阵静态上界，127+5688=5815≤6000；教师4+7×2=18≤20。没有追加总预算。原服务PID958223/startticks486445918未变。逐请求原始记录与[CSV账本](rr_v2_evidence/method_gap_repair/request_ledger.csv)、[保全及成本](rr_v2_evidence/method_gap_repair/preservation_and_cost.json)均保存；失败不退款、不删行。

## 绑定、恢复与复现

科学代码：`88770943aff923680fb8a50561c1e844222dd5806beff032ef0db99b20e88afc`；语义配置：`d63cc65096cde35e10cf49ae012fcdf62ef66e8efb3b3bc43248e57e6f27bcaa`；数据：`5b7683f05c921598c4bab6dc29834df3dc7595e3795d46551732446efa3eacc0`；manifest：`ef0f419d13f5219f0faeb97543b52d27be8c50a67243103e542013dc24ae3ca4`。原README及当前范围外受保护文件未改，五个旧AST锁定失败不被本轮改写或计作新修复。

当前[就绪凭据](rr_v2_evidence/formal_readiness_method_gaps.json)同时绑定全部当前源码、20来源工件、教师与冻结库、真实补验及禁网络恢复；旧凭据保留且不能替新代码背书。154项相关测试、78个实际解码用例通过。报告所述“可开始主训练”是工程判断，正式run/full_build/frozen_test开关仍为false。

本地在开发目录执行下列零生成核验；已完成阶段不要重跑prepare/live_contract/live_primary/teacher来制造新请求。

```bash
python -m experiments.rr_v2_offline
python -m experiments.rr_v2_method_gap_repair restore
python -m experiments.rr_v2_method_gap_repair current_restore
python -c 'from pathlib import Path; from legal_skill_guard.rr.readiness import validate; print(validate(Path.cwd())["engineering_ready"])'
```

模型环境中的`python -m experiments.rr_v2_method_backend`只加载本地tokenizer/xgrammar，不加载权重、不生成；CPU部分禁网络，另对既有服务做只读/tokenize核对。当前[backend证据](rr_v2_evidence/method_gap_repair/backend.json)、[历史核心重验](rr_v2_evidence/method_gap_repair/historical_core.json)、[当前恢复](rr_v2_evidence/method_gap_repair/current_restore.json)、[逐项验收](rr_v2_evidence/method_gap_repair/acceptance_audit.json)分开提供。

本轮属于现有研究方案的工程补齐，未改研究问题、五库来源、评分与验收门槛；thinking OFF为用户明确覆盖的执行配置。推荐的最小下一步是完成本阶段复核后，按原协议一次共享建库；本次停在此处，不启动训练、正式评测或论文。
