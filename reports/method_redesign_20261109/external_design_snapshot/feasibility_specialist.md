# LegalSkillGuard 语义失败机制与实现可行性独立复核

日期：2026-11-09。角色：失败机制/工程可行性专门复核。没有模型调用，没有读取 TEST 标签，没有修改生产代码或原始结果。

## 证据边界

本次逐代码检查使用已独立下载的 `6c2f2a5dce7e9e78c6aae6ccc000a3eb769f99c2` 科学快照；最新效果判断使用 `ced5c965e85103d80242b28852b29a1637696e5c` 的效果报告、逐来源状态、普通连接/静态切片对照。旧源码的具体行号不得直接映射到最新提交。最新报告说明已补通 compiler evolution，不应继续把“库不更新”当成当前事实。

复算程序：`feasibility_source_audit.py`；机器结果：`feasibility_source_audit.json`。这些是历史记录的审计，不是新增基准实验。

## 最值得解决的实际问题

**从规则语言到可执行计算的边界上，现系统既把许多可修复的表面表达拒绝，又能接纳来源真实但语义角色错误的事实判断；下游正确的符号执行无法弥补这一点。**

其中最具体、最有价值的科学问题不是“代码能否运行”，而是：**如何学习一个规则谓词应该依赖哪个事实事件及哪个角色，避免同一段文字中相关词汇、其他角色和其他事件污染判断，并把这种语义依赖迁移到新规则？**

应先从此处找方法。继续在显式正确 IR 后学习普通 join，或者在已知依赖图上换选批算法，没有当前证据支持。

## 真实来源级分布

| 数据集 | TRAIN 来源 | 原始最终状态 |
|---|---:|---|
| OpenExempt | 32 | 32 invalid_IR |
| Airline | 24 | 24 invalid_IR |
| SARA | 24 | 21 invalid_IR，3 source_IR_compiled；后者不能全算语义正确 |
| ProofWriter | 24 | 21 模型 Horn，2 controlled grammar，1 invalid_IR |
| ContractNLI | 24 | 24 invalid_IR |

按“该来源至少一次响应出现此错误”计数，以下类别非互斥，不能加总成失败来源数，也不能当真实语义错误率：

- OE：18/32 literal grounding、6/32逐字引文、14/32 Python 不完整。
- Airline：21/24 缺少 literal assignment 的 source annotation。
- SARA：7/24 重复变量名、8/24 Python 不完整，另13/24有其他错误。
- ContractNLI：19/24有不支持比较的错误；人工检查可见不少响应使用 `"reverse engineer" in "..."` 直接决定法律蕴含，不能把支持 `in` 运算视作语义问题已修复。

这些结果要求先做轻量 source-addressed extraction 和模板/变量名生成的公共工程基线。复杂新方法若仅比旧重型接口更容易生成，不足以证明方法贡献。

## 三个最有判别力的真实案例

### 1. 工作类型和支付媒介混淆：形式稳定仍答错

原始文件：
`outputs/audit_final_repo/artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109/dev/predictions/M11/96b6e8a08da8750d9d98fc0ae5abb5a919c5cf95e4e8a3a4da688a6821092441.json`

原文事实包含 Alice 向 Bob 支付 3200 美元维修屋顶，支付物是 eggs, grapes and hay。

`prediction.observation_rows` 把同一真实引文作为：

- `b_agricultural_remuneration = true`
- `b_non_cash_agricultural_payment = true`

最终程序给出 Entailment，completion_stable，但其农业工作判断没有被“支付农产品”支持。

这不是数字运算、join、输出格式或航空任务隐含约定问题。`work.activity` 与 `payment.medium` 的角色混淆是一个明确可解释的机制。此 DEV 已被诊断使用，不能再作为新设计的无污染确认集。

### 2. 同一真实引文既能支持正确观察，也能掩盖错误观察

原始文件：
`.../dev/predictions/M11/7a70d7f4d8919948923cad4cd5c0038cc10b5b6c1c18980927e05195ee0051d5.json`

事实是 Alice 支付 Bob 在 Toronto, Ontario, Canada 完成的工作。模型用完整事实句分别给出：

- `b_within_united_states = false`：地域判断合理。
- `b_employee_service = false`：同一引文不能支持“不是雇员服务”的否定。

最终正确答案由地域判断决定，不等于每个中间观察均正确。因此训练入库不能仅看最终 TRAIN 标签是否相等。

### 3. 纯表示错误与真正的角色检查缺失并存

TRAIN 顺序48，OpenExempt 来源 `1bb6328a07dda2ef71c58892c5c62e7cd99422123d9480d08c8e79130eb681ff`。

原始文件：
`.../build/sources/07b56aab02b010db99178546793f2f83d5a6392602fd51f73b544c5716fac8d1.json`

同一事实单元 s320 含日期 April 25th, 2024 和 blender115、booster95、icemaker130、windbreaker23。原模型将日期写作 `4/25/2024`，因不是逐字子串被拒绝。修复这种规范化应归公共前端工程。

另一方面，当前 `decode_source_bindings` 中所有数值都只需存在于整段 s320。人为把 `blender_value` 绑定成95而不是115会满足现有数值来源检查。**这是可复现的攻击/干预，不是历史模型自然产生此错的证据。** 父任务可用它检验简单 span/role 匹配基线。

## 源码机制

- `grounding.py:144` 附近 `binding_literal_audit`：数值只需属于 `_numbers(unit)`；字符串只需出现在单元；relation 每个cell出现即可。该函数没有检查实体—数值归属。
- `source_bindings.py:7` `decode_source_bindings`：把引用的单位全文合并再调用上述检查。正确承担字面来源检查，不应被描述成语义正确性证明。
- `source_program.py:448` `observation_request`：要求模型判定原子事实，true/false/null并给逐字证据。
- `source_program.py:470` `accept_observations`：检查每个name恰出现一次，非null有原文子串；不验证子串蕴含这个真假值。
- `source_program.py:421` `source_theory` 明确记录 accepted observations are faithful 为条件。形式证书并未声称已经证明自然语言忠实性；问题是研究中不能把条件性执行成功当作前提已成立。
- `atom_frontend.py` 对 ProofWriter 已把 if/and/then 连接装配移入确定性代码；这种成熟语法分工能提升工程可靠性，但不是新方法本身。

## 两个可具体实现的机制建议（本复核不单独认证文献新颖性）

### 机制一：通过角色干预学习谓词的最小证据路径

训练单元不是整题答案，而是一个 `(规则谓词, 事实事件图, 候选角色路径)`。

1. 公共前端抽取带 span 的 event frames，保留 agent、patient、activity、medium、location、time、amount、owner等通用字段，不由数据集标签挑字段。
2. 教师只在 TRAIN 建立语义锚点和局部对照：保持 work.activity 不变而换 payment.medium，或保持 payment.medium不变而换 work.activity。每条编辑保留完整文本与准确 span；非法/歧义编辑拒绝。
3. 系统在多个独立原来源上筛选“该谓词必须依赖/应当不依赖”的路径。库里保存角色依赖、适用条件、正反例及未解决边界，而不只是一个成功问答。
4. 测试时先抽角色值，再通过学到的依赖限制可用证据；不把文本中与角色无关的关键词交给下游作事实证明。依赖所需角色缺失则保持 unknown。

额外内容必须是**从对照中学习此前未知的谓词—角色依赖并跨新规则复用**；固定ontology、字段抽取、role prompting本身不能算贡献。

### 机制二：为证据路径构建可组合的规则变换技能，并以局部语义义务约束复用

技能保存 `(source pattern, typed role bindings, executable rule body, required semantic obligations, tested edit relations)`。规则变化例如比较符翻转、例外开关、额度所属者改变，要对应可复核的程序变化。

1. 从已核实 TRAIN source-program 对归纳可参数化骨架，常量、实体、期间都作为参数；不复制当前问题答案。
2. 每个技能附带最小局部义务，例如同一owner、同一period、活动类型支持、比较符极性、适用范围；编译器在调用时报告每个义务的当前证据路径。
3. 组合时只信已满足义务的部分；冲突义务或未支持的新语义保留残余，交模型局部翻译而不整题重写。
4. 学习更新应真正新增一个可复用变换或收紧适用边界，而不是把整题成功轨迹作为few-shot例子堆积。

**最危险的重叠**：上面若只是普通带前置条件的程序模板、CEGIS或skill contracts，可能被现有工作完全覆盖。需要查新专门复核给出更窄创新差异；仅此可实现性方案不能定为两项已过关创新。

## 必须先做的强对照

1. 同一source-addressed公共前端 + 固定通用event-role schema + 普通谓词判定。检验新方法不是靠多一个role字段。
2. 同成本教师提供的直接角色规则/最小few-shot；检验对照学习是否胜过一条清晰指令。
3. 相同已验证模板 + 普通相似度检索/完整元数据/常规程序拼接。检验所谓技能学习是否只是存例子。
4. 通用自纠错/round-trip验证，以及与新方法同数量的随机或均匀角色干预。检验选择干预的算法增量。
5. Oracle角色/程序只作诊断上界，绝不能给核心方法作测试输入。

旧A/B不应成为唯一强基线。旧A/B已经有结构性等价证据；赢它们不足以证明新方法有新东西。

## 五库适用性与最小实现

- SARA：活动/支付/雇主/时段角色是直接机会，且已发现自然错误；适合首批机制验证。
- OE：资产—金额—所有者—州制度绑定，数值归属和作用域机会明确；但先清理日期/引用ID公共前端故障。
- Airline：旅程—地域、行李—尺寸/重量、免费额度归属；先固定任务约定歧义分层，不能根据官方答案偷偷补入最优排序要求。
- PW：显式主客体/共享变量可作简洁对照，但接近饱和且有独立语法parser，不能用它独撑新方法。
- CNLI：主张/义务主体、例外作用域适合语义测试；完整文档转程序目前负担大，不应假定它已有可靠对照标签或每题都能转为金额/事件程序。

可复用：source_structure 的源单位/角色分段、source_bindings 的原始来源检查、现有 AST执行器、compiler模板版本/冻结账本、source级输出记录。

最小新增：`semantic_frames.py`（含span的公共frame）；`role_interventions.py`（有类型约束的编辑）；`evidence_path_learning.py`（从多来源对照归纳依赖）；`skill_obligations.py`（技能实例化和义务追踪）。不要先新建第二套数据/solver/费用/恢复系统。

## 可行性结论与致命假设

证据支持把研究焦点移到上游语义角色与规则映射；不支持目前仅靠复杂模板/更多自纠错就有两项新贡献。

最大未知是教师能否在原数据上给出可靠、明确、不泄漏目标的局部对照，并让Qwen对新任务角色抽取可靠。若只能由人手写对照或靠完整oracle程序完成，就没有得到自主学习方法。

另一个最大未知是简单固定role抽取是否已经吸收全部收益。必须在第一次小规模真实验证就比较，不能等全量训练后才补强对照。

建议近期应交付的是一个可运行闭环和有判别力的局部对照结果，而不是仅证明函数/类型检查通过。没有这里要求新增统计显著性、零回退或全部五库零错误；有意义的局部方法差异与真正的学习更新是前提。
