# 从真实误读学得观察程序，以及整案阻断的定位

2026-11-15。**观察程序已真实学得并执行，但两项贡献和整案收益仍未成立。** 本轮新增2次教师、11次执行器调用；未新增原始来源、种子或模型配置，未启动完整训练或DEV/TEST。当前DEV仍为ours46.884%、NoC48.134%，没有用本轮TRAIN结果替换它。

## 实际学习对象、实现和固定比较

学习对象是`education_service_states`的可执行事实观察程序。它仅接收当前原始`facts`，看不到问题、原生查询、法条、源ID、评分或答案。输出沿用原组件schema，由原转换器变成原生事件。程序由真实教师提议取得，host没有手写教育事实或法律规则；所有原schema、出处和源检查继续执行。已学程序先于有成本的神经观察执行，所有版本和程序hash保留。

两臂分别独立调用同一教师，各提出两份程序；普通教师获得同样的输入、代码和执行能力。固定获取为原TRAIN的大学就业案250fc5、农业工资误读案d9d6b2；固定后案为原TRAIN的干草工资案d5e113，未进入这次教师输入。三个来源都有既有B8暴露，不能称新盲测；固定后案为教育负例，不提供新的教育正例跨案泛化证据。[完整教师输入](../raw/legal_skill_evolution_compiled_observer_learning_20261115/teacher_task.json)、[冻结协议](../raw/legal_skill_evolution_compiled_observer_learning_20261115/protocol.json)、[两臂真实提议及原始响应](../raw/legal_skill_evolution_compiled_observer_learning_20261115/)。

更新步骤为：实际源误读→教师生成观察程序→原类型/转换及对应源检查→仅按获取来源选择版本→冻结版本→固定后案复用。候选选择没有使用native答案或后案结果。两臂均选择版本0。观察器只负责事实读取，法律核和权重不变。

## 实际结果

|同一教育观察接口|获取源检查通过|固定后案通过|运行时执行器请求|
|---|---:|---:|---:|
|方法学得程序|2/2|1/1|0|
|独立普通教师学得程序|2/2|1/1|0|
|同schema/转换的神经读取|1/2|0/1|按实际缓存/调用记账|

四份候选都通过获取检查；具名大学、学生、入学/到课及其原文期间实际进入原生事件，农业工资不再变成学校。神经消融在同3例中只有大学正例通过对应源检查，两个工资案未通过。该比较隔离观察执行方式，没有把新程序换成一个不同的法律核。[全部程序、转换、选择及固定复用](../raw/legal_skill_evolution_compiled_observer_validation_component_abi_20261115/result.json)、[选择发生在复用前](../raw/legal_skill_evolution_compiled_observer_validation_component_abi_20261115/selected_before_reuse.json)、[同契约神经消融及整案原始结果](../raw/legal_skill_evolution_compiled_observer_whole_validation_20261115/result.json.gz)。

**普通教师吸收了这项能力，不能把3/3归为第二项的独立收益。** 观察程序本身也不是新颖性证据：[PAL](https://github.com/reasoning-machines/pal)已有程序辅助推理，[SymBa作者代码](https://github.com/lbox-kr/symba#code-anatomy)已有符号求解与未证明目标触发的生成。当前仍需证明从错误学习表示/转换及其复用的额外作用，不能把公共执行能力改名成创新。

整案验证使用两臂原B8的其余组件，只替换真实学得的教育观察程序；补齐缺失的实际神经读取，精确旧输出直接复用。**两臂3例的整案主路径均0/3。** 普通教师两例本身缺声明覆盖，未为它们浪费读取；其余路径中的角色、日期及无关组件未解决继续保留。局部观察3/3没有被计为整案native正确。[完整整案记录](../raw/legal_skill_evolution_compiled_observer_whole_validation_20261115/whole_results.json.gz)、[逐次请求与费用](../raw/legal_skill_evolution_compiled_observer_stage_review_20261115/cost.json)。

## 找到并修复的路由缺陷

大学就业案的原生入口`s3306_c_10_A(Service,Employer,Employee,Workday)`直接读取服务事件的`patient_`、`agent_`，正文未显式调用`service_`。旧规划器主要以一元事件标签/GIVENS选择组件，因此**库中已有可用的独立`service_events`，但两臂都没有选它**。实际服务信息落在付款观察器的关联字段中，付款日期/角色失败后无法提供服务输入；亲属等其他观察的失败又被全组件complete的AND传导到整案。教育组件修好后，这些问题继续阻断主路径。[逐组件原始转换、实际native查询和漏选证据](../raw/legal_skill_evolution_compiled_observer_stage_review_20261115/result.json)。

已补上当前实际入口的公共输入ABI声明：第0参数是来源服务事件，按冻结的作者函数签名及源文件hash核对，将`service_`加入读取需求。**只改变路由需求，不添加服务事实、法律规则、标签或答案，也不放宽原检查。** 修复后方法从7组件变8组件，普通教师从8变9，均实际选择已有服务观察器。两个臂共享该修复；这次0调用路由回归不冒充新的整案正确。[修复前后计划及来源](../raw/legal_skill_evolution_native_query_route_repair_20261115/result.json.gz)。全组件完整性捆绑尚未解决，不能据此宣称效果已恢复。

另做了0调用B8历史保持检查：方法可联合比较6案，前后均6个主路径正确；普通教师16案中前后均8个。其余15/5案缺精确付费读取，不计错误。因此未证实“B8遗忘”是主因，没有借机增加历史全对的验收门槛。[原始保持检查](../raw/legal_skill_evolution_observation_retention_regression_20261115/result.json.gz)。

## 工程失败、成本和阶段判定

两次0调用验证失败属于运行接口问题：纯字符串`zfill`未暴露；组件自己的值被当成批量外层值。已保留原失败，补纯字符串支持、统一组件值ABI并由host加已知外层；没有改教师程序、重发教师或删除事实。[首检失败](../raw/legal_skill_evolution_compiled_observer_learning_20261115/candidate_results/)、[第二次原失败](../raw/legal_skill_evolution_compiled_observer_validation_zfill_20261115/candidate_results/)。本轮最终22项相关回归通过。

累计executor10864、teacher305，reserved0。新增11E/2T全部记入原连续账本，原11156条记录完整字段hash不变。执行器输入19774、输出3574 token；教师输入38546、输出22593，其中reasoning11213已包含在输出中，不重复加总。教师两次各214.06/217.62秒、并行执行，不能把相加耗时当墙钟。学得观察程序运行不调用执行器，但总获取/验证已有上述费用，不宣称净成本优势；实际现金发票/GPU分摊仍未知。[费用、逐次请求和旧账本校验](../raw/legal_skill_evolution_compiled_observer_stage_review_20261115/cost.json)。

本阶段完成了真实观察程序学习、强控制、固定复用、同契约消融、整案验证及一处实际输入路由修复；**C负增益、第二项独立收益和整案可用性仍未解决**。下一项工作是原生证明路径所需输入与观察完整性的衔接：先在原TRAIN做保持未知的离线验证，再仅获取确实缺失的事实输入；公共执行修复对控制同步开放。不重发本轮同类请求、不重跑固定DEV追分、不启动完整训练或TEST。Goal继续active、未完成。
