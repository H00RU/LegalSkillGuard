# Implemented method overview — caption and assets

Figure number will be assigned when integrating the final manuscript. This is
a schematic of the completed main Run03, not a new learning variant or an
empirical comparison. The existing Figure 1 curves and manuscript v0.6 are unchanged.

![Implemented batchwise skill evolution](../../artifacts/research/method_overview_20261023/Run03_implemented_information_flow_v03/method_overview.svg)

Experience changes the reusable legal procedures while the executor remains
fixed. A frozen Qwen3-8B answers new sources using only public task inputs and
the entering skill library. Every batch forecast, including its control
conditions, is saved before training targets are released. A teacher then
proposes edits and the same executor replays all seen TRAIN sources. Public
legal co-visibility determines which affected edits are assessed together;
the illustrated graph is not a fixed partition or a learned router. Admitted
components are composed and checked against paired current- and prior-TRAIN
aggregates and audited errors before one library publication. Unresolved
feedback can inform the next permitted attempt, up to two per batch; unchanged
parent components remain in place. The published library serves subsequent
batches without replacing saved forecasts. Frozen-library TEST is separate
and supplies no learning feedback. The diagram reports no performance estimate.

经验改变可复用的法律程序，执行器参数保持冻结。Qwen3-8B依据公开输入与批前技能库
回答新案；本批全部条件的首次预测保存后才释放训练标签。教师提出编辑，由同一执行器
重放全部已见TRAIN来源。公开法律情境的共同可见关系决定哪些受影响编辑需要共同
评估；示意网络不是硬设计的固定分组或学习路由器。通过的分量经过组合及本批、历史
TRAIN配对聚合成绩和错误审计后，形成一次发布。未解决的反馈可用于下一次允许的
尝试，每批最多两次；其他父库分量保留。新库服务后续批次，不替换已保存首答。
冻结库TEST单独进行，不向学习提供反馈。本图不承载成绩或显著性结论。

Assets: [vector PDF](../../artifacts/research/method_overview_20261023/Run03_implemented_information_flow_v03/method_overview.pdf),
[600-dpi PNG](../../artifacts/research/method_overview_20261023/Run03_implemented_information_flow_v03/method_overview_600dpi.png),
[source provenance](../../artifacts/research/method_overview_20261023/Run03_implemented_information_flow_v03/source_provenance.json).

Style follows the existing learning-curve figure: blue/pink/grey, vector text,
and DejaVu Serif. Georgia is unavailable; no font was downloaded or substituted
without disclosure. The render script uses the existing system GI/Rsvg/Cairo
stack and does not read grading targets or TEST, call a model, or change training.
