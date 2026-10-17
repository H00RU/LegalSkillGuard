# Learning curves, temporary regressions and credible effect targets

2026-10-17: user clarification, after the current48-call diagnostic was frozen.
This document changes future evaluation interpretation, NOT its running inputs,
sources, bank, model, endpoint definitions or stopping/publication mechanism.
The full active Goal remains unchanged and unachieved.

## Evidence boundary and claim ledger

| State | Claim | Actual evidence / limitation |
| --- | --- | --- |
| VERIFIED | Published skill evolution need not have monotone raw performance | ERSkill Fig5 and COBRA Fig4, original PDF page9 in each, viewed directly |
| VERIFIED | Some improving trajectories include selection/gating | WikiSkill §3.2.4; COBRA checkpoint selection §4.2, distinct from its raw per-round plot |
| UNSUPPORTED | A universal acceptable regression is1/2/5 percentage points | No such cross-task rule established by these sources |
| UNSUPPORTED | Our small or negative present gains are sufficient for a strong paper | Actual same-source ordinary controls still match or beat evidence/joint results |
| PLANNED | Final cross-contract gains survive independent learning and fair controls | Not completed; no formal TEST outcome has been inspected |
| PENDING | Existing-score delivery improves native skill use | Current48-call run; no partial quality scoring |

## What the original figures actually establish

**ERSkill**, [v2](https://arxiv.org/html/2608.12720v2), §3.4/Fig5:
the deployed routed-accuracy trace temporarily declines and later recovers.
Direct visual estimates are about77% at step3 and71% at step4, not raw values
digitized from author data. The rising oracle frontier is a different quantity.
Its trainable router and validation deployment gate are not our frozen-lawyer
method; this is evidence against mandatory monotonicity, not a6pp permission.

**COBRA-Skills**, [v1](https://arxiv.org/html/2609.11682v1), §4.2/Figs3--4:
per-round optimization scores fluctuate despite larger overall gains. The
checkpoint test figures evaluate the best optimization-observed skill so far,
not every raw candidate. Curves show three independent runs and SE. Neither
those optimization scores nor cross-benchmark averages equal ContractNLI SPAN F1.

**WikiSkill**, [v1](https://arxiv.org/html/2608.27454v1), §3.2.4:
accepted proposals must strictly improve validation score; other updates roll
back. This enforces a property of the retained validation state, not unseen
test monotonicity. Table1's Qwen3.5-4B OfficeQA30.2→28.5 is a final-setting
negative result, NOT a per-step drop or a normative tolerance margin.

Primary PDF files and viewed pages, SHA256 and URLs are preserved in
`artifacts/research/learning_curves_20261017/primary_figures_provenance.json`.
No external paper score is a same-protocol ContractNLI SOTA or publication bar.

## Our intended curves: noisy learning, not a manufactured staircase

1. **Actual first encounters.** Plot each batch's raw accuracy, original-SPAN
   Gold-non-NM micro-F1 and joint exact, plus the matched same-contract controls.
   Different batches contain different contracts: a lower next raw score alone
   is not forgetting. Keep the actual bank used before that batch's Gold.
2. **Paired skill benefit.** Plot skill-minus-control differences on those same
   sources and the cumulative first-encounter difference. Accuracy/joint use
   summed correct counts; evidence F1 is recomputed from cumulative TP/FP/FN,
   never the unweighted average of batch F1. Repeated retention answers are not
   independent new contracts. A useful story is positive overall benefit with
   occasional dips, then a stable late-stage benefit, not a best-so-far envelope.
3. **Retention.** Compare later actual bank versions on the same earlier
   contracts with their original prior-bank answers. Show fixes AND damage,
   E/C versus NM joint exact and true-member gains/losses. A return to the
   original empty baseline after initially gaining is not successful retention.
4. **Final confirmation.** Freeze the method and predeclared final bank, then
   evaluate untouched official TEST with strong empty, fixed shared tools,
   equal-call memoryless review and faithful mature-method comparisons. Do not
   tune on TEST, select a checkpoint by TEST or label exposed TRAIN diagnostics
   as untouched validation. Report learning repetitions separately from source
   resampling uncertainty conditional on one bank.

We do NOT add validation admission, best-bank selection, rollback, fallback,
answer repair or a different task to make a curve look monotone. All valid
teacher updates publish. Stopping an entire clearly harmful development trial
must preserve every answer, update and cost, not deploy a favored old bank.

## How to judge a temporary drop

There is no adopted fixed percentage-point tolerance. Consider together:

- Same contracts versus a harder new batch; finite-set resolution (8 sources
  ×17 questions means one question is0.735pp of accuracy/joint, NOT8×17
  independent contracts; evidence F1 has no single-question fixed resolution).
- Paired case-level fix/damage and original TP/FP/FN; a correct label with
  irrelevant citations is not legal evidence improvement.
- Uncertainty across contract clusters and independently learned banks;
  overlapping intervals / failure to reject harm do not establish equivalence.
- Temporary versus persistent loss, recovery in later published banks, late
  performance and cumulative first-encounter benefit, with all adverse points.
- Severity: recurrent missed operative clauses or topic/polarity errors deserve
  inspection even when the aggregate percentage is small.

A lone small dip is insufficient reason to cancel an otherwise useful study.
Repeated same-contract harm and absent cumulative benefit cannot be excused as
normal learning merely because another paper's router recovered from a dip.

## Optimization milestones, not journal acceptance thresholds

Current same-interface skill gains are insufficient: on the completed revised
16-source retention, accuracy+0.74pp, evidence F1-0.21pp, joint-2.21pp versus
ordinary; on the subsequent8 actual new sources,-4.41/-1.52/-8.09pp. These are
not yet a useful positive trajectory. The current24-source mechanism diagnostic
does not become a new-contract confirmation when it finishes.

For the NEXT frozen development learning study, aim for the following practical
effect sizes against strong same-interface no-skill controls:

| Endpoint | Development optimization milestone |
| --- | --- |
| Original3-way accuracy | +3--5 absolute percentage points |
| Original-SPAN Gold-non-NM micro-F1 | +5--10 absolute percentage points |
| Joint label plus exact evidence correctness | +5--8 absolute percentage points |

These are our prospective prioritization goals, NOT values asserted by papers,
skill admission thresholds, a license to tune to a number, or a guarantee of
SCI acceptance. Absolute90% is not a universal bar. Near-ceiling controls,
case-level importance, cost and mature alternatives affect interpretation.

For a paper claim, prefer demonstrable positive effects with contract-level
uncertainty and independent learning repeats, meaningful advantage against the
strongest fair alternatives, and supporting mechanism/cost evidence. Small
reliable gains can matter under a narrower claim; larger unrepeatable gains do
not suffice. All three original endpoints stay visible, and the present priority
is improving evidence selection/completeness without sacrificing classification.

The nature-paper evidence checklist is used to separate verified, pending and
planned statements and to prevent post-hoc non-inferiority or publication claims;
it is not evidence that the current method works.
