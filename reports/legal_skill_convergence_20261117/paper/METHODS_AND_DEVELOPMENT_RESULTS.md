# Learning Reader Interfaces and Validating Skill Updates under Shared Interpretations

## Abstract

External legal skills let a fixed language model apply reusable rules, but their behavior depends on how the model reads source facts and how later updates are checked. We develop two methods for these stages. Consumer-preserving synthesis derives alternative local reader interfaces and their decoders from a shared legal consumer. Shared-interpretation supervision synthesizes source variants and tests whether one admissible assignment explains the outputs of a candidate skill across those variants. Development on a fixed 20-source training pilot separates reader errors, decoder failures, and update errors. A synthesized diversity-jurisdiction interface resolves a grounded calibration case, then reverses a same-state comparison when reused on another case. A controlled citizenship edit excludes a joint output that either variant permits separately, but the measured updates all abstain on the edited cases. These experiments identify the conditions under which the two mechanisms provide usable learning signals.

## Introduction

Legal reasoning tasks often depend on facts that refer to a particular party, item, claim, or clause. An amount must attach to the correct claim, and an exception must attach to the obligation it qualifies. A legal skill can compute the right result from these facts and still fail when a fixed model reads the wrong relationship. The same distinction matters during skill updates. A mistake observed on a single source may reflect a faulty reader, a faulty rule, or an unresolved fact that admits more than one interpretation.

We study the interface seen by the reader and the evidence used to accept a skill update. We derive candidate interfaces from an executable legal consumer and check equivalence on the declared domain. Actual paired reads then identify which interface is worth carrying to another source. For updates, we generate source variants under independently audited constraints. A candidate must satisfy the relation that one shared assignment induces across the variants, while also improving the original training task. These mechanisms act at different points in the same external skill pipeline.

The development study uses five distinct benchmark families, with source mothers as the unit of comparison. The evaluation reports native metrics separately for each family and records whether a method was applicable, executed successfully, and used only source-supported observations.

## Methods

The study keeps the language model fixed and learns external components at two stages of legal reasoning. The first stage changes the representation that a model reads from the source, with a decoder certified against the original consumer. The second stage evaluates a proposed skill update on source variants that share legal interpretations and unedited case facts. Both stages preserve the original benchmark outputs.

### Consumer-preserving interface learning

Let $F(s,c)$ be a fixed consumer of local source facts $s$ in context $c$. A candidate contains a representation $H$ and a decoder $D$. On the enumerated legal domain, the compiler checks

$$
D(H(s),c)=F(s,c).
$$

The comparison covers the complete registered output signature and any protected source distinctions. If two admissible states produce the same encoding and lead to different consumer outputs, the compiler records the pair and rejects the candidate. This criterion admits different representations of the same legal computation. In the diversity-jurisdiction tasks, for example, a local interface can represent whether two named parties have different citizenship states and whether claims attached to a single plaintiff–defendant pair cross the amount threshold. Different parties and claim pairs retain separate anchors.

The compiler extracts comparisons, arithmetic expressions, and Boolean composition from a restricted consumer syntax. The decoder resolves the finite representation without access to native annotations. Unknown source attributes remain unknown whenever the preserved output depends on them. For local contract scope, Boolean candidates combine evidence about the target slots of a named exception. The wire schema enumerates the certified joint support when independent field domains admit impossible tuples. Training compares real reads of the candidates on paired source mothers. A native score contributes to selection when the source audit also supports the model's observations. The library records the source-independent reader template and executor version, and it selects a template for a new source before that source's reading or label arrives.

### Skill-update validation under shared interpretations

A source group consists of cases assembled from explicit source edits. The compiler recomputes the derived quantities and relations affected by each edit. One interpretation of a law or definition is shared within its declared legal scope. An unresolved factual attribute is shared among variants of its source mother and receives a separate variable for each independent mother.

Let $Q=(x_1,\ldots,x_k)$ be a group, $\Omega_K$ the independently audited set of compatible assignments, and $R_\omega$ the reference projection under assignment $\omega$. The permitted signatures are

$$
\Sigma_K(Q)=\{(R_\omega(x_1),\ldots,R_\omega(x_k)):\omega\in\Omega_K\}.
$$

For every measured candidate, each group contributes a finite factor over the assignments that support its asserted outputs. A join over these factors determines whether one assignment remains compatible with the full observed prefix. The selector can identify a contradiction that is invisible when examining groups separately. An explicit abstention leaves the corresponding value unobserved. Adoption requires paired positive native supervision in addition to compatibility. The ordinary native-score selector and the shared-interpretation selector use the same proposed programs, source inputs, executor calls, native labels, and budget. Independent completions and a fixed single witness serve as additional controls on the same signatures.

A local output can express either an interpretation-dependent projection or a claim that the literal source establishes a fact. Compatibility with one explanation suffices for the first check. A literal assertion requires support under every audited interpretation. For example, even when one common ownership assignment explains a pair of predictions, those predictions cannot serve as evidence that the text establishes ownership if another admissible assignment denies it.

### Data and execution

The sealed roster comprises OpenExempt, ContractNLI, MAUD, RuleArena Airline, and the LegalBench Diversity task family. It contains 128 training sources in eight fixed batches, 80 development sources, and 160 test sources. The matching unit is the source mother. The development pilot takes four training mothers per dataset from this roster. The held-out identities are checked against the historical exposure index and the continuous request ledger. Development diagnostics and controlled variants retain their parent identity and are recorded outside the independent test denominator. The local reading comparisons use the same frozen Qwen3-8B checkpoint with thinking disabled. The teacher is invoked through the Codex CLI with an explicit gpt-6.1-sol model and high reasoning effort. The diversity task family is part of LegalBench [1]. We draw the clauses for the contract-scope diagnostics from MAUD [2] and audit the selected clauses under our source review protocol.

### Evaluation protocol

The study asks five questions. **RQ1** asks how each method changes native task performance against matched external skill learning. **RQ2** asks how those changes develop as the training prefix grows. **RQ3** asks whether a synthesized representation improves source-grounded reading over fixed fields and format-only changes. **RQ4** asks when shared constraints change skill selection relative to native scores, one admissible interpretation, and independent completions. **RQ5** asks whether a learned skill helps beyond its source dataset.

The main design pairs five systems on the same training history. The first learns teacher skills using native supervision. The next three add interface learning, shared-interpretation supervision, or both. The last uses the strongest prespecified external adaptation measured on the fixed training pilot before the main study. The systems share the initial program, frozen executor, source scope, and comparable learning budgets. The component comparisons keep each candidate pool and scored inputs fixed where the research question allows. In the update comparisons, the native and relation-aware selectors can reuse the exact same candidate responses.

The design evaluates the same development cohort at B0, B1, B2, B4, and B8. B8 is the prescribed test checkpoint across all five datasets. The cross-dataset comparison at B8 removes skills learned exclusively on other datasets while preserving the shared initialization and the retrieval policy. Source-derived cases share the same independent sample unit as their mothers. An unhandled or unresolved native unit remains part of the score denominator. OpenExempt EC and EV receive separate official F1 measures. ContractNLI reports three-way classification and evidence F1. MAUD reports native classification by task, Airline reports exact total-cost accuracy, and Diversity reports accuracy and balanced accuracy. Paired uncertainty intervals resample source mothers, keeping all their native tasks together.

## Development evaluation

The common initial program was run on all 20 locked training mothers. OpenExempt EC and EV were read separately because the EV input supplies premises that the EC task must infer. ContractNLI retained all 17 hypotheses of each of its four documents. Of 24 logical reads, 23 required new physical responses and one reused the same wire response.

| Dataset | Native task and metric | Common initial program |
|---|---|---:|
| OpenExempt | Source-mean official F1 | EC 0.2118, EV 0.0595 |
| ContractNLI | Hypothesis accuracy and evidence F1 | 30/68, 0.0276 |
| MAUD | Exact classification by subtask | Ordinary-course exceptions 4/4, negative-interim exceptions 4/4, knowledge definition 0/4 |
| RuleArena Airline | Exact total cost | 0/4 |
| LegalBench Diversity | Accuracy and balanced accuracy | 3/4, 0.750 |

The common B0 program also completes all 80 fixed development mothers in 96 physical reads. It scores 149/272 on ContractNLI, with evidence F1 of 0.256. Diversity accuracy and balanced accuracy are both 9/16. The three MAUD tasks score 14/16 for ordinary-course carve-outs, 10/16 for negative-interim carve-outs, and 8/16 for the knowledge definition. OpenExempt EC and EV score 0.251 and 0.161 source-mean official F1, respectively. Airline produces a valid integer on every source and obtains 0/16 exact totals. These measures establish the shared pre-learning baseline under the indexed ContractNLI input and separate OpenExempt inputs.

Reference inputs for the Diversity interface traverse the same decoder as model outputs. Across 24 training mothers and four certified candidates per mother, all 96 reference decodes reproduce the three scored reference fields. The matched model outcomes vary with the mother. The generated interface yields the correct native answer and source-supported reads on the calibration mother. Its subsequent invocation on a different training mother preserves the selected template but misclassifies one same-state relation, despite citing the two matching citizenship statements.

Pair-specific source excerpts recover the same-state comparison on the second mother. Both interfaces become source-faithful there. On the first mother, the fixed reader grounds citizenship and misreads a repeated amount in each of two claims shared by multiple plaintiffs. The synthesized reader misclassifies four citizenship pairs and two claim units. The two interfaces each score 1/2 on the paired revision. All four responses reach the production decoder and consume 7,101 tokens. The local records distinguish polarity errors from repeated reads of the same monetary clause.

| Diagnostic | Unit | Fixed or incumbent | Generated interface or shared selection |
|---|---|---:|---:|
| Diversity calibration | Native answers correct on the calibration mother | 0/1 | 1/1 |
| Diversity template reuse | Native answers correct on the second mother | 1/1 | 0/1 |
| MAUD joint-support wire | Audited local projections correct across two anchors | 5/6 | 2/6 |
| MAUD knowledge definition with scalar output | Native answers correct across four mothers | 0/4 | 0/4 |
| Diversity shared-update probe | Native answers correct on the scored mother | 1/1 | 1/1 |
| OpenExempt ownership update probe | Official EC F1 on one original mother | 0 | 0 |

The MAUD comparison isolates ordinary-course and negative-interim attachment at two explicit exception anchors from one training contract. The generated reader recovers both scope projections at one anchor, and its other response reaches the output-length limit. Table entries count the three local projections per anchor. Full-contract native answers are evaluated separately from this diagnostic.

The knowledge-definition comparison uses four separate MAUD mothers. The quote-based wire reaches the length limit on six of eight reads across both arms. We replace nested records with a finite scalar that encodes an exact source span and a certified relation symbol. The largest expanded grammar times out before a response. A factorized grammar completes the last pair using the same symbol set. All eight completed scalar responses abstain, including the six earlier responses retained unchanged. The repair resolves output production. The remaining error is the reader's inability to ground an operative inquiry qualification under this interface.

In ContractNLI, explicitly pairing every public span ID with its exact text raises common-baseline classification from 30/68 to 36/68 and evidence F1 from 0.0276 to 0.3571. The same four documents and all 68 hypotheses remain in the comparison. Resampling whole paired documents gives exploratory 95% intervals of 0.000 to 0.221 for the classification change and 0.176 to 0.465 for the evidence F1 change. This improvement informs the shared input representation for the study.

On the four employee-disclosure hypotheses, adding the same literal participant mentions and offsets to both readers raises fixed-coordinate classification from 0/4 to 3/4 and synthesized-relation classification from 0/4 to 2/4. Each reader supports one correct prediction with a clause that grounds the stated permission. Both readers cite a duty to inform employees as evidence that those employees may receive the information. The fixed reader also cites a definition where the permission itself is needed. This pairing keeps the consumer and grammar fixed and identifies event and clause attachment as the remaining source-grounding error.

A complete-bundle comparison places the local intervention and the other sixteen native hypotheses in one invocation, with the same literal event coordinates in both arms. Fixed and synthesized readings recover 39/68 and 37/68 classifications, respectively. Both classify all four target hypotheses correctly and cite an operative permission in two. Mean evidence F1 is 0.340 and 0.493. The change comes entirely from the direct hypotheses outside the local intervention, with most of the increase concentrated in one source document. A document-level comparison therefore gives no evidence gain on the task that received the synthesized interface.

The employee-disclosure hypothesis provides a separate same-input comparison. The compiler combines the receiving party and recipient-group coordinates while preserving the permission condition. This reduces the finite representation from 36 states to 12 and preserves the native sentence indices, including consecutive spans whose second sentence qualifies the first. Three audited clauses support an employee permission. A fourth establishes a permission for agents and professional advisers, with their employee status unresolved. All eight physical responses decode, but the fixed and synthesized readers each score 0/4. The synthesized reader returns no local observation on all four documents. The source-grounded TRAIN selector retains the fixed interface in every leave-one-document-out check using these measured reads.

Under controlled citizenship masking, one plaintiff's state is withheld in two variants and one defendant's explicit state changes between them. Equality can hold in either variant by itself. Equality in both variants is excluded by the shared plaintiff state. All three measured programs in the update probe abstained on both variants and answered the original native question correctly. Both selection methods retained the incumbent. This separates the existence of a discriminating reference relation from the availability of a discriminating model observation.

The OpenExempt source review gives a natural case of uncertainty. The source establishes possession and a stated amount for one asset while leaving ownership unresolved. A literal edit changes only the amount. The shared reference allows two ownership-and-amount signatures across the pair. Independent completion allows four. This offline calculation uses source evidence and does not estimate an effect on the native EC metric.

On that OpenExempt mother, the incumbent and two teacher patches all recover both stated amounts and assert ownership in both variants. They also all obtain zero native EC F1. A shared interpretation can explain the observed ownership values because ownership remains possible in the source. When the reader is instead evaluated on whether the source establishes ownership, none of the six positive assertions is licensed by the source audit.

Two Airline mothers give a complementary failure with a fully specified local rule. Swapping the weights of two checked bags preserves the oversize and overweight marginals. The published local consumer takes the larger surcharge within each bag. In both mothers, the correct change is −70, whereas both paired model responses give zero change relative to their recorded originals. The relation detects the wrong response without assigning a new scored benchmark label to either edited source.

A subsequent update comparison generates two reader revisions from the aggregate Airline failures. The original and both revisions score zero on the two original mothers. The revisions also fail the fee-difference and audited surcharge checks. Native-only selection and the two relation-aware selectors retain the incumbent.

A follow-up comparison holds four measured itemized reads fixed while changing only how charges are combined. All four responses copy the ticket and retain every original item ID. The model assigns only one of 56 audited oversize and overweight field values correctly. Every aggregator still scores zero. This locates the earliest unresolved error in the application of fee clauses to the listed items.

Compiling the public fee tables shifts the model's job from applying fee clauses to reading the ticket price and bag measurements. With the same four resulting reads held fixed, the same-bag maximum recovers both original native totals and both −70 differences. The sum and unpaired-marginal alternatives each score 0/2. Native-only and relation-aware selection choose the same program. The scoped common repair also changes Airline development accuracy from 0/16 to 2/16, using two new measurements for the publicly applicable domestic cases and retaining the fourteen other paired baseline observations.

Absolute regression and a fixed fee-difference check also select the same-bag maximum on those two pairs when given the identical four actual coordinate reads. This agreement exposes a case where native supervision already distinguishes the candidate and the audited rule has one local interpretation.

### Reversible interface control

The PARSE-style control learns field aliases, field order, and brief reading instructions. A reversible mapping restores the original answer schema and evidence indices. The control changes the presentation of the task while retaining its legal computations. The frozen teacher proposed one schema per dataset using the same public task descriptions and native TRAIN feedback. The executor measured all five proposals on the fixed 20 mothers. Each row reports the mean of native utilities within mothers and then across the four mothers.

| Dataset | Shared incumbent | Reversible candidate | Retained interface |
|---|---:|---:|---|
| OpenExempt | 0.1357 | 0.2254 | Candidate |
| ContractNLI | 0.5294 | 0.4853 | Incumbent |
| MAUD | 0.6667 | 0.8333 | Candidate |
| RuleArena Airline | 0.5000 | 0.0000 | Incumbent |
| LegalBench Diversity | 0.7500 | 0.5000 | Incumbent |

Native TRAIN selection retained the reversible candidate for MAUD and OpenExempt. The five-dataset ranking utility after selection was 0.5676. The completed comparison used five teacher requests and 24 executor reads, with 86,961 and 153,420 metered tokens, respectively. These measurements cover one eligible family in the prespecified external ranking.

The ordinary compact teacher control proposed one native-supervised program per dataset on the same pilot. It retained the incumbent in all five datasets. Candidate utilities were 0.1246 for OpenExempt, 27/68 for ContractNLI, 8/12 for MAUD, 0/4 for Airline, and 3/4 for Diversity. The completed comparison used five teacher requests and 24 executor reads, with 88,430 and 238,040 metered tokens, respectively. For OpenExempt, the direct composer forwarded the complete public task and native answer schema to the model. The redundant host-tool descriptors and deterministic assets stayed on the composition side. This brought the longest input among the eight in-scope reads to 7,391 tokens.

The SCOPE-style decomposition control retained an updated MAUD program with 9/12 correct classifications and kept the other four incumbents. Its candidate utilities were 0.1181 for OpenExempt, 29/68 for ContractNLI, 0/4 for Airline, and 3/4 for Diversity. The five teacher requests and 24 executor reads used 87,426 and 193,117 tokens, respectively. Replaying the first candidate error in each dataset reproduced all six original compositions, including separate EC and EV reads. In the finite-label domains, changing a single predicate label can change a wrong composed answer in ContractNLI, Diversity, and MAUD. These are counterfactual interventions on saved reads. The source-edit comparison requires independently validated edited cases.

Reversible renaming of the Company and Parent role tokens preserves the operative terms and benchmark labels of the four MAUD sources. On the edited bundles, the SCOPE candidate retained 9/12 correct classifications and the common program retained 8/12. The eight paid requests used 73,869 tokens. The fixed pilot ranked the PARSE-style adaptation first, with an equal-dataset selection utility of 0.567621, followed by the SCOPE-style adaptation at 0.533015. The SkillEvoReg-style and Synedrion-style selectors shared the ordinary teacher proposal pool. The five-library native comparison yielded no positive update for either selector to validate. Each retained the common program, with a selection utility of 0.516349. The targeted Airline pairs separately exercise the absolute and relational validation criteria. The formal external family follows this fixed ranking.

In Diversity, an express joint-claim clause can bind the same ordered amount observations to several plaintiff–defendant pairs. The read interface requests each bound amount once and retains each covered pair for the legal consumer. Across the 24 TRAIN mothers, 16 yield fewer read units. On the two calibration mothers, the interface that retains citizenship coordinates and synthesizes amount relations obtained 2/2 correct and source-grounded outputs. The fixed interface obtained 1/2 and the interface synthesizing both relations obtained 0/2. The next two compatible TRAIN mothers were selected by fixed roster order from outside the pilot before reading or grading. On these two mothers, the learned interface obtained 0/2 and the fixed interface obtained 2/2. The learned reader incorrectly asserted that three below-threshold claim clauses cleared the statutory threshold.

A controlled amount edit targets this failure mode. Both variants withhold the same second claim amount and change the first amount from 10,000 to 70,000 dollars. Across every nonnegative completion of the shared amount, a lower-amount variant can clear the threshold only if the higher-amount variant does. Across the two audited joint clauses, the compiler derives three allowed shared signatures versus four under independent completion. These are source-bound reference relations for future measured updates.

Adding an 80,000-dollar anchor gives one entailed outcome and preserves the distinction between the shared and independent signature sets. The incumbent and two matched teacher patches each scored 2/4 on the original TRAIN mothers. One patch repaired one error and introduced another. All three readers abstained on all three edited cases, including the entailed anchor. The original four incumbent predictions were reused. Seventeen additional executor reads used 15,344 tokens, and the single matched teacher request used 17,328 tokens. All four selection rules retained the incumbent. The missed anchor identifies an observation bottleneck even where the source independently settles the comparison.

The shared DEV B0 checkpoint includes the scoped Airline repair. The five arm records bind the same 80 development mothers and 384 native tasks per arm to the pre-pilot program. Identical outputs across the five arms were verified against the paid baseline and scoped repair responses. Airline scores 2/16 at this checkpoint.

A second diagnostic asks the same frozen reader to quote the known amount and preserve the censored amount as unknown. The legal consumer tests the lower bound against the statutory threshold. On the same three edits, the outputs were unknown, unknown, and above threshold. All three passed production decoding. The three new reads used 708 tokens. This diagnostic measures the recovery of the entailed anchor.

The first formal TRAIN batch contains 16 mothers and 74 native tasks per arm. The ordinary teacher retained the revised ContractNLI program, increasing exact classifications from 27/51 to 28/51. The locked PARSE-style arm retained a reversible OpenExempt update, increasing the mean native task utility from 0.135665 to 0.213021. The M1 arms share the same 12 measured candidate reads across the three Diversity mothers. In the OpenExempt scope where a source relation was certified, the ordinary candidate did not improve native TRAIN scores. The M2 selector therefore retained the corresponding entering program. These are training results.

At B1, both M1 comparisons improved Diversity accuracy and balanced accuracy from 9/16 to 12/16. Each paired contrast was 0.1875, with a mother-level bootstrap 95% interval of [−0.125, 0.500]. M1 selected the learned interface on nine mothers. Five baseline errors became correct and two baseline successes became errors. All five repaired outputs passed independent checks of the literal evidence for every local relation. Across the nine learned-route sources, 12 of 21 citizenship relations and 10 of 12 paired-claim amount relations agreed with the source. The ordinary teacher's ContractNLI update moved in the opposite direction on DEV, from 149/272 to 134/272 exact classifications. Its paired difference was −0.0551 [−0.1544, 0.0147]. The B2 retention rule adds a regression check on previously seen TRAIN contracts for both the ordinary teacher and the external control.

All five B1 DEV cells are complete. The locked PARSE control scored 9/16 in Diversity, yielding the same paired contrast of 0.1875 against the joint arm. Within OpenExempt, PARSE increased EV F1 from 0.161200 to 0.223942 while EC F1 moved from 0.250826 to 0.237771. The paired mean across the two tasks was 0.024843 [−0.017132, 0.068345]. Mean official EV MARE was 3.036917 for the common program and 0.561578 for PARSE, with official values available for 15 and 14 of the 16 mothers, respectively. Both independent M2 contrasts were unchanged in each dataset. The checkpoint used 57 additional executor reads and 476,710 tokens.

## Appendix. Evidence and replay

The evaluation binds source versions and native task IDs before dispatch. Each saved read records the model profile, exact request, source, and corresponding ledger entry. A compatible response can re-enter the pipeline only under the same request and execution binding. Reported native utilities use the benchmark grader after predictions are saved. Source audits are evaluated separately from native grades.

The finite interface check enumerates every allowed local state and groups states that produce the same interface symbol. The compiler accepts a symbol only if every state in its group has the same consumer result. Hence the decoder is well defined on all certified encodings. The claim concerns the declared consumer and the allowed states. Source-grounded model reading requires separate empirical evidence.

For the update checks, one shared assignment defines all outputs in a source group. Each measured candidate restricts the assignments to those consistent with its supported assertions. A candidate may pass each group separately while their assignment sets have no common member. This difference is the reason to retain assignment support explicitly. Literal source claims also require independent entailment. In the natural ownership example, compatibility leaves ownership possible in both variants, whereas the source audit rejects any assertion that ownership is established.

## References

[1] Neel Guha, Julian Nyarko, Daniel E. Ho, Christopher Ré, et al. 2023. LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning in Large Language Models. Advances in Neural Information Processing Systems 36. [Proceedings](https://proceedings.neurips.cc/paper_files/paper/2023/hash/89e44582fd28ddfea1ea4dcb0ebbf4b0-Abstract-Datasets_and_Benchmarks.html).

[2] Steven Wang, Antoine Scardigli, Leonard Tang, Wei Chen, Dmitry Levkin, Anya Chen, Spencer Ball, Thomas Woodside, Oliver Zhang, and Dan Hendrycks. 2023. MAUD: An Expert-Annotated Legal NLP Dataset for Merger Agreement Understanding. Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing, pages 16369–16382. [ACL Anthology](https://aclanthology.org/2023.emnlp-main.1019/).
