# SARA 原生语义口径核查（2026-11-13，只读）

## 结论与建议

**需要纠正我们自行增加的求值口径；不是修改 SARA 的正确答案或放宽评分。** 原始 SARA 是法条适用/不适用的二分类；作者的可解性参照是 Prolog，其中明确采用否定即失败及少量公开默认。它并未要求所有合法结论都附带经典逻辑下的显式反面证明，也没有统一开放世界三值验收。当前 reader 的不确定、未解析文本和缺失学习规则仍须保留为实现层 `unknown`，不可因本核查一律变成 `False`。两层必须分开。

本次没有调用 executor/teacher、没有实验、没有读 DEV/TEST 或官方 case formal facts/标签；只读作者论文、官方说明、官方法条代码及本地已暴露 TRAIN 的修复提示。对两个例子的结论是源码推导，**不是新增真实验证成绩**。本地旧结果、账本及冻结产物完全保留。

## 明确的一手依据

| 依据 | 原作者的具体口径 | 对当前问题的含义 |
|---|---|---|
| [SARA 2020 论文](https://arxiv.org/pdf/2005.05257)，§2.1、§3.1、§5.1 | 每个 subsection 编一例适用、一例不适用；Prolog 对适用返回 true，反之 false；模型使用 Entailment/Contradiction 二分类。税年等同对应日历年。 | `Contradiction` 是该二元任务的不适用结果，不能擅自要求 classical explicit-negation proof；2015 可直接作为该税年的开始年份。 |
| [SARA v2 论文](https://arxiv.org/html/2105.07903)，§2 | `@truth` 只有 True/False；明确举例指出 §152(b)(1) 中的 taxpayer 要映射为 §152(a) 的 dependent。 | §152 的跨条角色转换是原任务的一部分，不是新增任务；不存在 native 的第三个 NLI 标签。 |
| [SARA v2 官方格式说明](https://nlp.jhu.edu/law/sara_v2/)，Argument instantiation | 不适用的输出 `false` 对应 `@TRUTH=False`；适用则附 True。 | 二分类不是当前项目重新解释出来的。 |
| [官方运行说明](https://nlp.jhu.edu/law/sara/) | 以 SWI-Prolog 7.2.3 加载法条，可输入 case facts 并调用 predicates。 | 必须结合实际 Prolog 运算符理解参照语义。 |
| [SWI 官方文档](https://www.swi-prolog.org/pldoc/man?predicate=%5C%2B/1) | `\+` 是目标无法证明时成功的否定即失败，不是证明强否定。 | 负条件可由有限失败满足；不能把所有此类失败改成开放世界 unknown。 |

法条代码从作者 [官方发布包](https://nlp.jhu.edu/law/sara_v2/sara_v2.tar.gz) 流式读取，仅打开 `statutes/prolog/` 下的 151、152、utils、init、events。逐文件 SHA256 与 exact member 记在 [receipt.json](/tmp/lsg_sara_semantics_source_only_20261113/receipt.json) 和 [events_receipt.json](/tmp/lsg_sara_semantics_source_only_20261113/events_receipt.json)；没有打开包内 cases、split 或 argument_instantiation。以下代码行号均对应这份原始下载件。

## 1. GIVEN 法律中间结论与一般事实

“Bob 满足 §152(c)(1)，相对于 Alice、2015 年”是作用域明确的法律谓词前提，不是要求重新证明 c1 全部 antecedents 的普通亲属词。按法条源码，这个谓词可以沿 `c1 → c → a1 → a` 消费；它不直接等于所有 §152 顶层条件，因为顶层还处理 b1/b2 例外。仅 GIVEN §152(c)(2) 则只满足关系入口，不能提升成整个 c1。

这是对给定自然语言与作者公开谓词接口的一致解释。**本次未读取这两例的官方 formal facts，因而不声称核实了其 exact assertion 编码。** 不能将题目假设当 GIVEN，不能反向填入其答案，不能借法条代码补造案例中的年龄/结婚事实。引用、主体/客体与年份必须绑定。

## 2. §152(b)(1) 例子：不必另外证明 Alice 不是他人的 dependent

[section152.pl](/tmp/lsg_sara_semantics_source_only_20261113/section152.pl:2) 的真实调用关系：

- 顶层 `s152(Dependent,Taxp,Year)` 先检查 `\+ s152_b_1(Taxp,_,Year)`，再证明 a，最后 `\+ s152_b_2(Dependent,_,_,Year)`。
- [b1](/tmp/lsg_sara_semantics_source_only_20261113/section152.pl:38) 直接调用 `s152(Taxp,OtherTaxpayer,Year)`。
- [a1](/tmp/lsg_sara_semantics_source_only_20261113/section152.pl:19) 调用 c，c 调用 c1。

因此，在完整 case 中断言 Bob 为 Alice 的 qualifying child 后，查询 Bob 是否受 b1 限制，可经 Bob→Alice 的 dependent 关系完成。若没有任何事实/其他规则证明 Alice 自己是别人的 dependent、没有 Bob 的 joint-return 例外，原生负守卫可由证明失败通过，**不要求额外给出“不是”的句子**。Bob 有 qualifying child Charlie 不能消除 Bob 自身受 b1 限制；它也不能代替其他人的依赖关系。

这是从官方代码得出的操作语义推断，没有执行 Prolog，也没有利用标签。现实法律的开放事实世界、原始 case 的有限参照世界和神经程序当前掌握的信息量，不应混成一个层次。

## 3. §151(a)/§151(d)(2)：不要求额外 `individual` 布尔事实

[151(a)](/tmp/lsg_sara_semantics_source_only_20261113/section151.pl:63) 只有对 `s151(...)` 的接口调用；[151(d)(2)](/tmp/lsg_sara_semantics_source_only_20261113/section151.pl:134) 检查另一纳税人的 b/c deduction applicability，并令该人的 exemption amount 为 0。两者均没有 `individual(Person)` 之类的独立条件，官方 events 签名中也没有该独立谓词。

若案例已把 Alice 作为自然人纳税人/家庭成员并 GIVEN 相关 exemption entitlement，不能再因未出现单独的“is an individual”而阻断。可以保留 person/taxpayer 的角色类型校验；不能将其变成额外案例证据门槛。与此同时，**GIVEN entitlement 仍不自动完成所有金额/税年推理**；exemption→deduction 的源法连接若方法实际缺失，仍是规则获取/执行缺口，不能由 reader 猜造法律补齐。官方代码只用于公共语义核查，不应整段灌入某一学习臂。

## 4. 未提及事实是否都默认为假：不是一条全局 blanket rule

原生参照按具体法条调用及默认处理：

- §152(c)(1)(E) 通过 NAF 检查同年与配偶 joint return 的存在；未证明这个事件即可通过该负条件（152:143–155）。
- 亲属是正向关系，可由明确事件或亲属链推出；不是把任意未识别字符串都判作 non-relative。
- 居住开始/结束未写时，官方代码取税年首日/末日（152:93–123）。2020 论文 §2.2 也把事件无开始/无结束的持续语义列为共享常识。
- 年龄源码更有局部默认：若 descendant 且未写生日，先默认 younger-than 关系成立以免缺日期使其失败；但 under-25 仍使用 birth/son/daughter 事件的开始日期计算（[152:192–230](/tmp/lsg_sara_semantics_source_only_20261113/section152.pl:192)）。所以不能把“所有未提及年龄为假”当 native 规则，更不能把这个局部默认扩大成所有年龄条件均成立。

以上直接反证“原生要求统一三值”及“原生一切缺失均假”两种简化。作者参照含有操作细节；复现时应用已公开的任务约定，其他四库继续各自原生语义。

## 建议的最小公共修正与仍未定事项

1. 修正当前提示中“absent claimant-dependency statements are not proved False”这一无条件说法：**reader 未解析/缺规则≠完整 native case 内的可失败证明**。不要求显式负句，不把拒读、字段缺失、角色不明当作“未发生”。
2. 保留实现层 unknown，但区分“原文未提及该事件并完成相应读取”和“抽取/程序覆盖不完整”；只有前者可进入该 source property 允许的 NAF/default。无需给所有未到达分支追加穷尽证明，不追加实验验收门槛。
3. 取消额外 individual 守卫，使用已有角色/实体类型；GIVEN 法律谓词按明确 citation/角色/年份接入本已学得的规则链。此为两臂共同正确性修复，不是独立创新。
4. 先基于已有原始响应作有修改记录的离线重放，分别记录 native 结果、reader错误、缺失 head/rule、unsupported。旧原始得分不改写；新结果标明公共语义修订。原 §152(c)(1) 日期误读仍是实质模型错误，不能靠 NAF 掩盖；方法缺 b1 head 仍是实际覆盖缺口。
5. 本核查足以确定二分类/NAF/无独立 individual 守卫；**不证明现有两个学得程序已等价原生，不证明两项创新或任何新增真实收益**。GIVEN 的 exact case encoding、现有程序修订后能否走通、来源级覆盖仍须由主执行者依原协议核实，不能将本报告当成实证完成。

数据暴露附注：一次限定术语的网页搜索意外返回第三方 SARA 镜像的一条 §151 例子摘要，含 formal facts/negative query 片段与标签；未打开该网页、未核对 split、未用于上述判断或交给任何模型。上述原生口径均以作者论文、官方说明及 source-only 法条代码独立成立；不把该搜索摘要计入新验证。
