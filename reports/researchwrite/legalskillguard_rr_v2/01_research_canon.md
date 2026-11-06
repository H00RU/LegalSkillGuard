# 研究事实与边界

## 用户和项目事实

- 用户报告旧论文单基准，训练一次约十几个小时，导师认为数据与创新不足；这些是用户提供的经历，未在本轮重新测时。
- 旧工程存在外部技能建库、冻结测试与EC/EV结果；当前两项新方法未实现，不能引用旧结果证明新方法。
- 导师要求至少五个独立基准，合计约128或256训练来源，冻结后每库约32或64测试来源；本方案选128/32作为第一轮固定规模。
- 现有数据计划为OpenExempt、RuleArena Airline、SARA v2、ProofWriter OWA depth5、ContractNLI；沿用来源分组，不把派生视图当独立来源。

## 已核文献事实

- SymBa(NAACL2025)用SLD控制逆向证明、按需求助LLM，已有回溯与变量绑定传播：https://aclanthology.org/2025.naacl-long.124/
- Logitext把文本约束与逻辑结构结合，并用LLM作为SMT的文本理论求解接口；不是仅一次全量翻译：https://arxiv.org/html/2602.18095v1
- AWS Automated Reasoning已区分未译输入、解释歧义及正反可满足情景；不能把这些输出名称当新机制：https://docs.aws.amazon.com/bedrock/latest/userguide/automated-reasoning-checks-concepts.html
- SkillFusion的类型包括format/behavior/tool/priority/style，scope为指令激活范围；它通过交互分类、路由/优先级/抽象/去重合并文本技能：https://arxiv.org/html/2610.15481v1
- SkillCompiler已有操作契约、混合编译与局部绑定修复：https://arxiv.org/html/2610.39508v1
- Morpheus已有类型/例子驱动的组件组合合成和SMT剪枝；连接器合成本身不是首次：https://www.cs.utexas.edu/~swarat/pubs/pldi17-morpheus.pdf
- Graded linear types用于资源受限程序合成已有工作：https://pmc.ncbi.nlm.nih.gov/articles/PMC7880237/
- OLAP已有分组互斥、完整覆盖与类型一致的可聚合性条件：https://www.sciencedirect.com/science/article/pii/S0169023X13001274

## 术语

- source ledger：逐原文单元登记已编译/残余/冲突，遗漏不能静默消失。
- completion：在声明的有限语义范围内，对残余条款/接口的允许补全；不等于所有自然语言真义。
- 稳定答案：非空补全集中目标答案一致；证书有明确模型和覆盖条件。
- scope effect：实体/分组索引、聚合闭合与额度余额流；不同于文本指令的激活scope。
- connector：join/group/map/reduce/额度状态传递等组件间连接；primitive内部语义保持不变。
- 接口碰撞见证：两种来源内合法情形在现有接口表示下相同，但参考任务答案不同；说明需要恢复丢失的角色、集合或用量信息，不能只重试下游模型。该信息充分性命题是经典事实，不单列新理论。
- 用量接口必须包含 allocation/priority/order_observable；余额守恒不能代替正确分配次序。
- B的有限搜索池H与A的语义补全集Ω是两个对象。H内同答不能证明Ω内同答；未搜索的合法连接、未核scope和域外情形不能静默排除。
- unknown：区分任务本身的Unknown标签、解析未定、求解超时，不混为一类。

## 禁止及尚未解决的主张

不得称首次使用类型、线性资源、SMT、CEGAR、反例、hitting set；不得称形式证明自动保证自然语言忠实；不得声称五库都有完备形式覆盖；不得用生成反例数量扩增来源数；不得称新方法效果已知。

A的实际成本收益、B的接口跨来源泛化、整体精度/覆盖均为待验证假说。公开文本的忠实解析不能单靠同一模型自证。预算耗尽时有明确fallback并如实记账。B可选metadata限制为实体同一性、成员关系、阶段、余额、顺序等语义结构，禁止case ID、gold与任意数值指纹；在实体重命名下规范化。保留全部metadata的编译器是必要强基线。
