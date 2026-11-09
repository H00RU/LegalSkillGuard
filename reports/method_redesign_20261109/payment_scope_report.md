# 原TRAIN88多事件输入：真实抽取、核实与条件执行

2026-11-09。继续原Goal，active、未完成。此次使用**2次executor＋1次teacher**，全部计入原账本，累计 **1364E/52T、pending0**。只处理固定20池中既有的TRAIN88原文，没有新增来源、seed或原生标签，没有启动完整建库、评测矩阵、TEST或论文。

## 得到的实际能力

紧凑事实IR完整保留了四笔支付。源文逐字段核对、另一教师模型独立列出的四事件及其关系/完整性检查一致。既有71/79训练所得的工作分类路径实际用于三笔农业劳动事件；确定性作用范围聚合得到20597，排除反向4520。普通同信息路径学习器和聚合对照得到完全相同结果。

| payer→payee | 模型抽取金额 | 工作分类 | 作用范围执行 |
|---|---:|---|---|
| Alice→Bob | 6771 | agricultural labor→true | 纳入 |
| Alice→Charlie | 6954 | agricultural labor→true | 纳入 |
| Alice→Dan | 6872 | agricultural labor→true | 纳入 |
| Bob→Alice | 4520 | 未见通用work→unknown | 因payer方向排除，不把unknown改成false |

Alice范围内合计 **20597**；给定条款阈值为20000，条件聚合比较为true。此前仅focus Bob会得到6771；把整段所有金额相加则为25117，后者虽然也跨阈值，却没有正确归属。不能靠最终真假吻合证明作用范围正确。

这是**一个母来源中的四个事件**，不是四个独立来源，也不是跨库迁移。它补上原任务所需的多收款人/反向事件输入，证明真实模型事实IR可被接纳并执行；没有把共享前端、普通聚合或训练词典复用认定成新方法贡献。

## 为什么需要这次真实验证

原已付TRAIN88修复响应只有注释`# b_agricultural_wage_threshold = (sum of wages paid to agricultural laborers >=20000)`，没有可执行赋值。之前的局部二标签IR又没有amount和全部事件。已有输出不能靠保持语义的格式适配补出缺失程序或其他收款人，故采用新的紧凑事实接口，而非重买旧完整法条翻译。

两次executor提示都只含原事实，不含法律答案、旧回答、金额合计或阈值；模型负责列关系，代码负责精确金额读取和普通聚合。20000来自提供的农业条款逐字跨度，>=是普通参考控制，不称学得的法律规则。

## 失败、具体修改与无歧义适配

| 请求 | 实际结果 | 处理 |
|---|---|---|
| v1 | 四事件其余28个字段均逐字命中；四个medium都填了不存在的`payment` | 拒绝并保留原输出，未改成null |
| v2 | schema/提示明确种类与物理媒介；medium输出字符串`"null"` | 原输出仍拒绝且不修改；另存派生IR，将无歧义unknown哨兵渲染成JSON null |

v2的修改有[真实失败逐字段证据](payment_scope_v1_failure.json)及[修复协议](payment_scope_repair_protocol.md)：`wages/payment`是报酬种类/交易，`cash/hay`才是支付物，金额本身不证明cash；没有调温度、seed或thinking。

适配只接受**允许null的字段＋值恰为字符串null＋源文不存在竞争字面null跨度**。有字面null则不转换；非nullable证据不补；payment不是null别名。原生成、原拒绝状态与新派生文件分列，事实未新增，类型/来源/去重检查未放宽。9项相关回归通过，见[日志](payment_scope_null_rendering_regression.txt)。没有再为字符串null新增executor请求。

教师核实前，转换和完整源指针检查已落盘。教师只看事实及规范化后的模型提议，核对局部事件，不看原生答案。四个独立列出的event与派生IR完全相同，四条审阅索引0—3齐全且均支持；核实仍是TRAIN教师判断，加逐字/源文复核，不等同形式化自然语言真值证明。

## 完整原生法律答案尚未产出

原查询是§3306(a)(2)(A)在2017年是否适用于Alice。模型与教师均将`Feb2017至Sep2017`等作为**service period**，没有支付日期。当前执行器没有擅自把服务期间复制为支付日期，也未实现完整原生查询与日期约定；返回`native_legal_answer=null`。

已阅读[SARA v2作者说明](https://nlp.jhu.edu/law/sara_v2/)及缓存法规程序。后者在`a_2_is_wages`使用`start_(Remuneration,Time)`选择年份，与服务事件的日期是不同角色；未用它补当前事实或充当完整oracle。未打开原生答案、TRAIN隐藏实例事实或TEST标签。

这里**不把“支付年必须逐字写出”新增为验收门槛**，也没有判定该基准原任务必然不可回答。原任务的上下文/日期解释还需按原口径接入核定；本小试只执行已核实关系上的条件聚合。因此不将20597或阈值true统计为完整法律IR、原生任务成功或整体训练就绪。普通未决和允许fallback不是全Goal停工理由。

## 调用、费用与保存

- executor：两次均`stop`，输出完整；总输入489、输出1125 token，耗时29.877秒。thinking OFF，原Qwen3-8B、采样及8192/32768不变。
- teacher：一次，输入14741、输出967 token，耗时32.361秒；reasoning85为输出子集，不重复加算。沿用既有模型/配置，未升级资源。
- 本地executor无逐请求API现金费用；GPU分摊及教师现金账单不可取得，记unknown，不把总费用报为0。配置重试0，v1拒绝与v2验证均收费记账；供应商内部HTTP重试不可观测。
- 原1382行请求、184项meta、130行oracle及52份前阶段工件逐项不变。旧v1源码和seal保全；499个当前绑定文件及2个精确归档版本核对通过。旧完整128/六臂DEV记录和失败结果保留。

[本轮全部来源/执行/公平性核验](payment_scope_delivery_audit.json) · [完整调用与费用](cost_snapshot.json) · [账本增量](request_ledger_delta.json) · [保存核验](preservation.json)

原始目录：[v1](../../artifacts/rr_method_redesign_20261109/payment_scope_native_input_v1_20261109) · [v2、规范化、教师与执行](../../artifacts/rr_method_redesign_20261109/payment_scope_native_input_v2_20261109)

实现：[共享事件IR](../../legal_skill_guard/rr/payment_scope.py) · [既有客户端/账本上的运行入口](../../experiments/rr_v2_payment_scope_pilot.py) · [限定哨兵处理](process_payment_scope.py)

## 阶段结论

这次实际解决了一个此前无法执行的输入作用范围缺口，并记录了训练分类的真实复用；同信息普通对照同样成功，故没有改变此前两项独立贡献未成立的结论。M1配对依赖项冗余、M2分类与完整角色误读的差异均保留。

当前没有资源缺口，原Goal未完成。不会用单来源条件执行替代全部方法验收，也不为缺失支付日期反复请求模型或擅自追加事实。后续只有在现有TRAIN能提供可信监督、且明确不同于普通抽取/程序学习的判别操作上继续方法验证；没有这样的依据，不扩完整建库或原样追加请求。
