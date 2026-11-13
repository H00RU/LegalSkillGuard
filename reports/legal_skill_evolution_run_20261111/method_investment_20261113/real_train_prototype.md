# 第一项真实TRAIN获取、拟合与后续使用

2026-11-13。同一Goal active，继续既定C/U。**首次真实获取主路径已执行，尚未得到第一项相对强对照的额外收益，第二项U未实现。** 本页不是Goal完成或完整训练就绪结论。

## 实际学到并执行了什么

固定获取来源为原TRAIN的`35462327…`和`78adf3b3…`，后续来源为预先固定的`e7b78d42…`和`de427b59…`；四个不同母合同。两臂从同一已有真实源程序/59构造子/消费者开始，独立获取更新，收到的完整任务JSON逐值相同。旧资产的全部历史结果和成本保持；这是共享底座的更新比较，不是独立从空库端到端获取，也不是两个创新的删除消融。

C教师取得两项窄语义操作：**当前条款授权的接收者类别**、**该许可的保障条件**，并提出三个不同接收者组合及旧规则保留候选。8B在78ad的当前单位18真实返回`employees_and_contractors`和`need_to_know_and_written_confidentiality`，两次均正常stop，thinking OFF。当前原文明确写出“employees or contractors of the Recipient”、need-to-know及written confidentiality agreements；单位8定义Recipient为收到另一方信息的一方。

有限理论检查在354上检查8种集合、允许2种，在78ad上检查16种集合、允许5种；这些是相对当前候选语言的结果。全历史约束拟合选出`retain_existing_roots`和`emit_limited_employee_contractor_permission`，代价4。实际安装并执行后，从当前单位18与其真实保障条件引文构造permission；原生消费者的两个披露任务实际使用该新规则。另两个返还/保留任务沿旧有效规则执行。

这证明**教师取得概念→实际8B观察→全局拟合→当前源规则→原生消费者**首次真实接通，不是只写了技能文本。但自动拟合的选择与教师初选完全相同，NoFit也答对，故目前不能将成功归因于自动约束学习。强自由更新也用一次实际语义读取及当前文本条件检查取得相同原生结果。

## 固定结果

|范围/系统|核心路径答对/全部目标|核心实际执行|未覆盖，需fallback|
|---|---:|---:|---:|
|两份获取材料，旧共同库|6/8|6/8|2/8|
|两份获取材料，C拟合后|8/8|8/8|0/8|
|两份获取材料，NoFit|8/8|8/8|0/8|
|两份获取材料，FreeUpdate|8/8|8/8|0/8|
|两份后续材料，C冻结|0/8|2/8|6/8|
|两份后续材料，FreeUpdate冻结|0/8|2/8|6/8|

组件试验未执行fallback，未覆盖项留在分母。表中不是含fallback的总体原生准确率。新增规则在获取材料上支持2个目标；后续两份材料没有新概念查询，新增规则未使用。原分数和逐来源结果不改。

## 后续失败已定位，继续同一设计

这次不是8B读错：后续两份均**没有调用它**。两臂教师生成的规划器都把候选限制在当前一句已有员工/承包商、Confidential Information及特定许可短语的情况：

- e7b单位62写的是`restrict disclosure ... employees and/or consultants ... need to know`，还限制向affiliates等第三方披露；C的短语过滤漏掉了它。另有单位28支配的返还、留存等子条，旧公共程序仍有覆盖缺口。
- de42单位20声明许可及书面协议前提，单位23列员工、官员、代表及受控法人人员，许可、对象和条件跨列表项分散。两臂均未为它计划读取；旧程序也没有取得相应规则。返还条款同样分散。

在两份实际旧观察上分别穷尽2种、1种当前输出集合，均无满足全部目标的理论；诊断为**局部输出语言/约束问题**，没有表示冲突证书。这表明当前已取得观察及输出候选不能覆盖目标，不能宣布原文不可识别或8B能力不足。

**下一项已准备**：把这两份冻结后失败作为正常原TRAIN反馈，与原两份历史共同进行一次真实更新；修复可复用的候选窗口规划、支配/列表作用域读取及其组合，不换机制。新后续来源预先固定为原TRAIN的`5cad3f37…`与`a5b0361f…`，尚未用于本次学习或评分。保留初次冻结分数；下一更新后的旧四份是训练回查，不包装成新验证。相同问题、原文和合法监督也提供给强自由更新。当前入口仍是`experiments/legal_skill_evolution_open_acquisition_train.py`，当前run为`legal_skill_evolution_open_acquisition_update_20261113`；初版runner保存在[冻结源码](real_train/frozen_initial_runner.py.txt)及git历史，不增设同级项目/平行入口。

## 真实费用、格式修复与数据边界

本次物理请求**3E/2T**，累计**9518E/211T，9729行，在途0**；此前9724行逐条保持。执行器1941输入/203输出token、5.717服务秒，三次实际payload均thinking OFF、max_tokens8192、正常stop；教师77266输入/15107输出token（含10414 reasoning）、311.539服务秒。CLI现金实付和GPU分摊未知；公共旧资产逻辑获取成本需一致计入两臂，不能把物理复用说成对照免费。逐请求详见[费用与保持记录](real_train/cost_and_preservation.json)。

两份teacher响应分别出现了完整函数模块封装；C还使用`TRAIN`作为示例来源占位，并遗漏提示已声明的公开keep_root签名。仅作确定性适配：按唯一当前原文引文解析来源、拆分纯函数且AST完全相同、补齐提示中已有的签名。原始响应保持，无再次教师请求、无补造源规则。两臂同样采用AST保持拆分。类型与语义正确性检查没有放宽。

71项相关软件回归通过；新增回归还覆盖“每个可能世界单独答对，但保守交集不能回答”的情形，防止用臆测世界制造通过。原始TRAIN标签合法用于学习；后续来源标签在冻结前未供教师或拟合使用。runner读取整个TRAIN grading文件但只将获取键供学习，见[原协议措辞澄清](real_train/protocol_interpretation.json)。没有DEV/TEST、新数据、完整训练或论文。

## 可检查证据

- [C原始教师响应](real_train/ConstraintAcquire/teacher.json)、[实际拟合结果](real_train/ConstraintAcquire/fit.json)、[学习库](real_train/ConstraintAcquire/learned.json)。
- [强自由更新原始响应](real_train/FreeUpdate/teacher.json)、[实际库](real_train/FreeUpdate/learned.json)。
- `real_train/acquisition/`、`real_train/reuse/`逐来源保留实际读数、原文、出处、类型化输出与全部原生执行；C拟合后的获取执行单列在`real_train/ConstraintAcquire/fitted_execution/`。
- [冻结指纹](real_train/library_freeze.json)、[真实失败诊断](real_train/ConstraintAcquire/failure_diagnosis.json)。

目前贡献状态：C有一次真实获取执行证据，独立增量和后续复用尚未成立；U未实现。继续实际窗口/作用域缺口修订，Goal保持未完成。
