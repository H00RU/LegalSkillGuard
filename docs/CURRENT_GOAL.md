# 当前Goal执行索引

更新时间：2026-10-19 23:14，Goal仍active，未达成、无外部阻塞。
本页是续接入口，不以游标替代真实进程/原始输出。旧2690行游标原样保留于
[历史索引](CURRENT_GOAL_history_through_20261019_2228.md)，原始字节已Git及双盘保存。

## 完整目标与有效用户要求

让现有单实例冻结Qwen3-8B因可演化技能，在后续新案及最终隔离测试上强于同权限、
同推理预算强空库和可信成熟经验方法，形成可复核论文证据。法律任务、主方法仍开放；
OpenExempt只是当前候选，不能以一个小试跑替代完整目标或因投入而锁死任务。

用户追加要求及实际小时记录：[技能进化、任务覆盖、规模与小时自检](research/GOAL_ADDENDUM_SKILL_EVOLUTION_20261019.md)。
不另设验证集；TRAIN重放/准入是训练优化，不是独立验证或泛化证据。
不能以技能数量、提示注入、B1静态教师知识收益或已见案拟合冒充在线进化。
逐批核实际CRUD、送达、执行及收益。数据规模和法律覆盖要足够，最终TEST隔离。
不要求不同难度裸批次机械单调。不新增付费服务/模型/32B/第二实例，不恢复客户路由。
不引入fallback、答案修补、案例特调、Gold solver推理工具或无关框架；失败和成本全保留。
沿用师兄paper-ideation的失效假设检查与paper-experiments-appendix的真实机制/公平证据，
不采用预设好数字、固定创新数量或隐瞒借鉴建议。本轮已完整读过，不反复泛泛调研。

## 当前唯一训练与冻结边界

**23:14最新：下方active_case旧Run已于22:54:49安全停止，不再训练。**
实际88 native/4教师返回、B3无调用、290终态工件逐成员双盘核验，原141源绑定
在编辑前亲核。失败文件中的InterruptedError是主动artifact-safe停止，不是模型崩溃。
两次B2候选均被拒：第一当批EC100%、EV86.67%，旧案却被不适用辖区干扰；
第二旧源全输出EV95.00→91.43%，末库保持C1，未挑旧库。停止及真实原因收据：
`artifacts/research/openexempt_mechanism_20261019/active_case_run01_manual_stop_and_scope_root_receipt.json`。

当前正在冻结并启动 `legal_openexempt_namespace_online_20261019_run01`，不是已启动声明。
14项CPU边界检查0.25s通过，无额外GPU资格生成。作用域代码已从唯一staging模块
移入 `legal_skill_guard/learning/legal_namespace.py` 并接主入口；没有保留旧接口fallback。
统一公开label语法、仅加载给定AE法域技能、精确相同wire旧重放复用均已实现。
元数据迁移只添加公开jurisdiction，原blind bank02内容不改、0新教师/0标签；初库
7条/40函数/3462tokens，SHA f6549092d1c1fb3bd5ce01a3d0a53f109a6abb3ad3987580b9cf9ffc3f72353f。
不使用已训练C1作起点，不把旧正指标归到修复后协议。
新16源29–44：原29–36原文/源键保留，seed2026101911新增37–44，旧源排重、无重采样。
packet SHA 7313de9a7ddc3d52292a6055e209e37e2ca03e31957dcc9550172e8aa2bf5220。
新协议：[法律命名空间](research/OPENEXEMPT_LEGAL_NAMESPACE_20261019.md)。
下一步提交/冻结/核双盘，直接启动四批真实机制训练；8B服务PID3889231不动。
当前仍非正式论文规模；下次小时复核23:28。启动后必须用新unit/PID确认，不恢复旧队列。

**下方旧进程/分数只作历史证据，不能认为旧Run仍live。**

- Run：`legal_openexempt_active_case_online_20261019_run01`。
- user unit：`legal-openexempt-active-case-20261019-run01.service`，PID2672609。
  21:09:19启动，22:28:55亲核仍active/running；同进程未重启。
- 实时状态：`runs/<run_id>/progress.json`，并用systemd/PID亲核，不能只读文件。
  22:28快照为B2 candidate1 replay，65 native/3教师返回，正在源25。
- 原单8B服务PID3889231不变，Qwen3-8B b968826…，32768上下文；各臂T0、seed45、
  原生thinking、8192生成上限、同工具权限。GPU A40实测98%、约35tokens/s，不是GPU不可用。
- config：`configs/openexempt_active_case_online_20261019_run01.json`及同名frozen.json。
  代码源74a860f，141绑定文件22:30再次逐项确认未变；之后提交仅未绑定执行记录。
  不热改活跃Run的源、协议、输入或初库。终止/完成后先确认终态及双盘保全再修改。
- 输入21–36共16源、32派生任务、4批；B1=21–24，B2=25–28，B3=29–32，B4=33–36。
  SHA `73838a87619f7f49f195ccba66e72ff046a70fd0f8b181cc729411af33fe523f`。
  21/22曾旧协议无状态查询但未反馈，17–20已暴露训练诊断因此排除；不称独立复现。
- 所有7原始prompt组件留在packet。推理保留5个法律/事实组件原文，去格式假案示例，
  技能在前、当前Facts在后。统一渲染，不是名字过滤/补事实/答案修复。
  当前协议：[输入契约](research/OPENEXEMPT_ACTIVE_CASE_INPUT_20261019.md)。

## 已有真实结果，不扩大解释

起点为一次无案件/答案的公开法条盲编译bank02，7条/40函数/3411tokens，
SHA `ecc5c7160e33a9cfe6b77c5fdce27bb2ff0d1dca3c67c74f911f5ff3136b576c`。
三个臂每批共同回答后才读Gold；完全相同wire共享真实生成并记录alias，不算独立调用。

|新案指标，%|强空库|冻结同一起点|在线库|
|---|---:|---:|---:|
|B1 EC F1|77.08|68.75|68.75|
|B1 EV F1|33.33|66.67|66.67|
|B2 EC F1|51.25|86.67|82.92|
|B2 EV F1|79.17|45.42|80.42|

B1全输出EV为35.00/68.33/68.33%；B2为79.17/45.83/80.42%。
B1在线=冻结，在线学习收益0。B1教师第一候选UPDATE3，EC降37.50被拒；
第二候选UPDATE2（IL/AZ）真实发布C1，7条/40函数/3765tokens，
SHA `69b194ccaec0e94f58161cf5dd60e410255aa653305f153376c311923334d556`。
仅4旧TRAIN重放EC68.75%、EV95.83%、全EV95.00%，4任务改好/2改坏/2平，不叫泛化。

B2新案在线对空库两项均值+16.458pp、对冻结起点+15.625pp；但EV对空库只+1.25pp，
EC对冻结-3.75pp。冻结EV在28发生一次8192思考截断；EV对冻结+35pp中18.75pp来自
该失败、另16.25pp来自另外三源。失败不重答/修补，不只报聚合好点。
累计8源：在线对空库均值+14.479pp，对冻结+7.8125pp，仍非正式显著/广泛泛化证据。

实际断点：B2在线有效EV中17条正确，漏11条引用、1条错误引用、0金额算错；
漏项集中通用残余/默认条款，错项是把步枪用车辆条款。空库26_EC错用联邦法，
不是简称问题；初库26_EV虚构Illinois(f)。不要把所有低分归为格式或金额能力。
所有已完成候选/新案缓存函数调用仍0，实际EV是inline数学；不冒称编译函数贡献。
B2教师已真实提出UPDATE3（Federal/Oregon残余条款、Illinois适用边界），正在重放，
尚未发布。没有ADD不等于没进化；也不能把合理文字直接算有效学习。

## 紧接着做什么与小时边界

先读B2候选完整重放/拒绝/发布及真实差分，再看B3、B4在线对两个控制的配对新案损益。
当前有实际新案正收益，不因单点或新的接口设想重启B1。按声明的连续负收益/系统故障
条件停止整轮，不挑最好历史库，不强拖128正式训练。当前16源只是有界机制试跑。
后续不足时先干预法律覆盖/适用条件与执行一致性的实际断点，不机械堆金额函数。
B1只读诊断发现EV已选法条与独立EC不一致，但空库投影也可能更差，不能换口径造分。

尚缺：足量预先冻结数据、成熟方法公平对比、独立学习重复、来源级不确定性、合理迁移、
冻结最终库后的隔离TEST、完整成本和机制消融。不能以启动、训练内95%或一个正批次完成Goal。
每次Goal续接/长工具返回先看实际时钟是否到小时复核；最近22:28，下次23:28 Asia/Shanghai。
没有唤醒模型的独立调度产品；这是持续Goal执行规则，训练本身由systemd独立运行。

证据主目录：`artifacts/research/openexempt_mechanism_20261019/`。
关键为`active_case_B1_actual_publication_audit.json`、`active_case_B1_actual_cost_audit.json`、
`active_case_B1_independent_vs_EV_label_projection_diagnostic.json`、
`active_case_B2_forward_and_error_audit.json`及各自双盘保全收据。
B1完整113不可变工件已双盘逐字节核验。正式终态由现有runner自动保存，
不能把活跃progress文件的旧备份当终态。此前失败Run均终止封存，不要恢复static eval旧队列。
