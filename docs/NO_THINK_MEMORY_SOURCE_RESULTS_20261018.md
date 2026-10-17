# 完整16源的模式、候选提示与技能对照

`legal_contractnli_no_think_memory_source_20261018_run01`于2026-10-18 01:17:59 CST完成。
48全新律师回答、0教师；固定同一R2，不是在线学习完成。全48原生输出有效，无修复/重试。
另32条thinking回答为明确历史参考，包含原384无效答的完整分母。

| 条件 | 分类% | Gold-NN原SPAN硬F1% | 严格联合% | TP/FP/FN |
| --- | ---: | ---: | ---: | --- |
| 新no-thinking，M2+R2 | 78.68 | 50.31 | 53.31 | 123/52/191 |
| 新no-thinking，完整原文+R2 | 72.79 | 61.62 | 50.37 | 175/79/139 |
| 新no-thinking，完整原文空库 | 69.12 | 62.43 | 45.96 | 167/54/147 |
| 历史thinking，M2+R2（含无效答） | 74.63 | 48.23 | 52.21 | 109/29/205 |
| 历史thinking，完整原文空库 | 74.26 | 60.48 | 48.90 | 163/62/151 |

全部条件同16源、272命题、144 Gold非NM、314 Gold成员。

## 可以和不可以得出的结论

移除低召回M2候选提示，同R2/no-thinking下依据F1净增11.31pp，但分类/联合反向下降，
故不是全指标改善。原文+R2相对匹配空库分类+3.68pp、联合+4.41pp、F1−0.81pp：
多8个真成员同时多25误引；E/C正确合计都为120，分类净增10主要来自NM改善。
不能据此宣布取证技能成功、达到论文目标，或故意忽略thinking空库更高的分类分数。

384旧失败请求与重放请求仅差显式disable-thinking，重放有效；只证该请求的模式干预
有效，不证明vLLM内部唯一bug。0.10.2服务不重启。更不能把协议成功当语义成功。

R2来自thinking+M2接口，源接口下未新学习过。下一步是唯一干净原文主链路的新完整
32源四批在线episode，不是继续固定库小探针、按效果选R2或宣称无标签学习不可能。
原始17命题、三类、原SPAN硬评分、当前8B和已授权教师不变。后续仍须强thinking空库、
等调用无技能复核、公平成熟方法、独立重复和未调优TEST；开发正差不是成功保证。

## 独立原始工件核对

另从原作者TRAIN.zip重算48新+32历史全部80答，每份实际wire/payload/source/schema/
thinking profile与原始分母核对，全部分数一致；同16实际输入投影验证仅有声明的
候选清单/完整同R2准则差异。无新推理调用、无官方DEV/TEST内容读取。

- 原始completion：`runs/legal_contractnli_no_think_memory_source_20261018_run01/completion.json`。
- 独立audit：`artifacts/research/no_think_memory_source_20261018/complete80_actual_wire_and_original_author_score_audit.json`，
  SHA256 `c330ba7b2bbf7f0ac5184fc5017ededfc2de64850746f74acd0823f275b789ba`。
- 实际终态双文件系统archive SHA256：
  `5e435b3af73c70f5eab89653a3c2b6602359cc3b042ec218ea360a849ef48d15`。
  这是同机两盘保全，不是异地备份、权重或整机快照。
