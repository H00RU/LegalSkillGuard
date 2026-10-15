# ScienceClaw evidence scorer

`scienceclaw_contracts.py` is an attributed adaptation of
`packages/scienceclaw/scilib/contracts.py` from author commit
`e925f732c7ca435f557e88075bc47a58f1e984f1`:
https://github.com/beita6969/ScienceClaw

Original upstream SHA256: `131d6883f47371b0a1d9f744539c39b77697931a493bc7f1698aa4f3bc00d57d`.
The MIT license is preserved as `SCIENCECLAW_LICENSE.txt`.

Local modification: when `use_not_mentioned=True`, `scoring_pairs` also contains
the original NotMentioned pairs with all-negative evidence membership targets.
Their first-stage out-of-fold scores and second-stage training rows are included.
Positive evidence-neighbour records, stage-one AP and the unused label model
still use original E/C evidence pairs. This fixes an all-negative training
population omission for three-way inference; it is not an upstream reproduction.
The frozen source snapshot identifies the exact adapted file hash.

Our query-feature extension lives outside this file. We use evidence scores
with `plm=False` and do not use the author's binary E/C label predictions.
The external scorer is supervised from original seen TRAIN span membership;
it must not be described as a frozen-parameter language model or pure verbal memory.
