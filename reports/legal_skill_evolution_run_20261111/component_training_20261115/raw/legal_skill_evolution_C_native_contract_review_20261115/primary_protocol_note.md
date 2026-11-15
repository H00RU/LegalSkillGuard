# C原生任务合同核对

原始archive只打开contract-nli/train.json。三个固定TRAIN母案的完整原文均与作者文档逐字相同；原生题目、标签及证据索引逐项相同。没有重跑既有根子集或all-rules实验。

- 文档280/nda-5：作者标注Entailment，证据25、28为引入句及受控公司员工许可；当前程序保存该所有权区别并返回NotMentioned。
- 文档111/nda-16：作者标注Entailment，证据28明确是if requested返还；当前程序保存request而非termination触发并返回NotMentioned。
- 文档34/nda-20：作者标注NotMentioned，没有证据跨度；当前消费者从完整处置义务派生Contradiction。这一否定派生需要原生任务语义论证，不能仅凭未抽到保留许可成立。

[作者任务说明](https://stanfordnlp.github.io/contract-nli/)规定三分类及证据跨度；[原论文](https://aclanthology.org/2021.findings-emnlp.164.pdf)§2.1和附录A.1.1说明固定假设、按假设举例的标注指南。公开材料未提供把上述三种区别机械合并的规则。本轮只得到任务解释存在差异的证据，不能断言标签错误或声称已取得缺失英文概念。

研究决定：保留源语义及原标签，不为这三题购买相同的规则获取，也不通过受控员工→自身员工、请求→终止或强化OR拟合标签。它们不再被笼统归为“缺规则”，也不新增必须零残余的Goal门槛。学习主线继续；解释冲突与获取/执行错误分开报告。
