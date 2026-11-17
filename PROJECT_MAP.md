2026-11-17 最新维护任务：用户已要求同步整个legal-skill-current的核心代码到已明确授权的H00RU/LegalSkillGuard研究分支。范围包括全部核心模块、实验入口、对应测试/配置/依赖及当前交接；不是只同步M1复现子集。同步本身不恢复M1/M2扩展、正式训练或冻结测试，不新建/完成Goal；科学状态仍以M1/M2停止结论为准。范围、排除项和文件哈希见docs/CORE_CODE_SYNC_20261117.md及CORE_CODE_MANIFEST_20261117.json。下列旧任务段落保留为历史记录。

2026-11-17 当前任务结论：已完成M1源码/必要依赖/最小证据公开发布（b741b46a63cf3b95c6e99e7976b69ba7aff729fa）和固定有限可行性验证。原3个OE TRAIN来源复用18响应，新增2调用/5576 tokens；M1诊断F1=1/3但完整正确0/4，正分均涉及源审unknown→true，未建立保持源文语义的独有收益。停止当前M1版本扩展，M2继续停止，不启动正式训练/DEV/冻结TEST，不搜索替代方向。保留原分数、177参考、账本12427/reserved0和全部曝光事实。整Goal受阻未完成，不以报告或离线通过标完成。详见reports/two_method_followthrough_20261116/M1_FEASIBILITY_DECISION_20261117.md。下列旧阶段段落仅作历史记录。

2026-11-17 用户最新任务：M2 停止扩展，保留代码与证据，不在服务器寻找替代方向。当前仅推进 M1：先发布修订源码、必要依赖、复现命令及去凭据最小证据包到既有 GitHub 研究分支；再完成同链参考/真实输出核验、自动语义接口生成审计及固定有限的 TRAIN 来源公平比较。复用有效结果；不启动完整训练、DEV/冻结 TEST，也不因涨分追加实验。新授权覆盖旧的仅说明文档上传限制。系统 Goal 当前仍 blocked、未完成；本任务不新建 Goal、不恢复 M2 或旧队列。

# 当前项目入口：两项方法的新 Goal

最新结论：按用户M2两关复核，现有135份图对的6族候选上界仍均1；计算例仅支持附条件外推，且在例中被同假设的完整联合差分迁移复现。两关未过，M2扩展及新真实验证已停止，整Goal受阻、未完成。共同F修复和53项检查已交付；原177参考、账本及曝光事实保留。见 [M2两关决定](reports/two_method_followthrough_20261116/M2_TWO_GATE_DECISION_20261117.md)。以下active／待执行段落为此前历史截面，不构成新执行队列。


最新进展：已将MAUD唯一“参考可执行但原生不正确”案例定位为输入上下文遗漏，交付唯一原文锚定的完整Section恢复工具与版本化TRAIN输入提案，8项检查通过。原177参考、正式输入和历史分数保留；Goal仍active，正式训练继续暂缓。见 [MAUD上下文修订](reports/two_method_followthrough_20261116/MAUD_CONTEXT_REPAIR_20261117.md)。


本轮交付：已修订生产解码与M2主路径，完成765份固定离线预测、70项检查和官方库存核查；真实M2仍无有效风险排序，正式训练继续暂缓。详见 [修订结果](reports/two_method_followthrough_20261116/REVISION_RESULTS_20261117.md) 与 [数据安排](docs/INDEPENDENT_TEST_DATA_PLAN_20261117.md)。新代码未上传GitHub。


> 2026-11-17 最新授权：用户已要求继续同一 Goal 的阻断修订，系统状态 active。先交付 M1 同链参考输入检查与实现修复、M2 新可识别目标及算法验证、官方库存与独立测试数据方案；暂不启动正式训练或新增大规模调用。177 个参考视图、原始结果、连续账本和暴露记录保留。下文 blocked／停止扩展是修订前历史截面，不覆盖本次授权。见 [当前修订范围](docs/REVISION_SCOPE_20261117.md)。


当前Goal已由系统标记blocked（受阻、未完成，2026-11-17）：未暴露SARA库存0的条件连续三轮未变，且当前主M2固定columns的明确反证要求停止扩展。正式实验未启动，参考177/177和全部资产保留；先读CURRENT_GOAL与阻断回执，不按旧active截面派发。

当前科学结论（2026-11-17）：已证明当前主M2的unrestricted最坏风险恒为1，部署选择等价于固定columns；按PLAN明确反证条件停止双方法正式矩阵扩展，Goal未完成。先读reports/two_method_followthrough_20261116/M2_IDENTIFIABILITY_AUDIT.md；新测试范围答复不能单独解除此方法条件。

当前新增前提（2026-11-17）：源文参考已齐177/177，但root误检索已使原DEV72/TEST136暴露，不能再称新盲测。完整本地SARA Binary未暴露库存为0；正式入口在客户端前拦截。Goal保持active且未完成，评价范围决定待用户答复；先看CURRENT_GOAL最新段及docs/HELDOUT_EXPOSURE_20261117.json，不按旧准备派发。

唯一项目本体：`/home/yndx/hhy/legal-skill-current`。继续使用本目录、原有代码、数据、缓存及连续账本，不创建同级“最新项目”。

2026-11-16，用户明确设置新 active Goal：实现 M1 程序残差引导的成对接口学习、M2 结构错误迁移，完成固定真实小试、一次完整五库混训、固定 DEV 矩阵和未暴露冻结测试，并交付独立贡献比较、成本及复现资产。旧 Goal 保持 clear，历史候选和队列不自动恢复。

接续顺序：

1. [当前 Goal 与授权](docs/CURRENT_GOAL.md)、[最新交接](docs/NEW_CHAT_HANDOFF.md)。
2. [固定方案](reports/two_method_followthrough_20261116/PLAN.md)、[协议](reports/two_method_followthrough_20261116/protocol.json)、[相关工作](reports/two_method_followthrough_20261116/RELATED_WORK.md)、[方案评估](reports/two_method_followthrough_20261116/IDEA_EVALUATION.md)。
3. [实际执行状态](reports/two_method_followthrough_20261116/EXECUTION_STATUS.md)。方案未实现项须以实际文件、进程和账本核对，不凭方案宣布完成。
4. [既有资产与失败证据](docs/METHOD_REDESIGN_CURRENT.md)、[研究技能索引](docs/RESEARCH_SKILLS.md)。

当前分支 `research/paired-interface-structural-transfer-20261116`；原开发分支及全部未提交资产保留。交接前科学源码、文件哈希、工作树及账本截面见 `artifacts/two_method_followthrough_20261116/handoff/`。根 README 保持冻结历史。
