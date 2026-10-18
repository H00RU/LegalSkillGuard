# Source-attributed online skill learning, 128 sources — 2026-10-19

## Purpose and unresolved claim

Run `legal_contractnli_source_attributed128_online_20261019_run01` tests a new runtime interface and independent online skill learning. It is NOT an independent repeat of the previous interface, an official TEST result, or a demonstrated improvement. The preceding complete32 episode remains adverse overall: skills80.51/73.03/60.48%, common-tool empty81.62/72.46/61.21% (classification/original Gold-NN SPAN micro-F1/strict joint). No best-bank selection, answer repair, semantic acceptance gate or rollback is introduced.

The historical source audit found both overly restrictive learned boundaries and failures to apply already-present correct distinctions. Full source/Gold reached the teacher and the preceding32 paired answers had zero token truncations. More labels, skill count, scope tags or a reasoning toggle alone are not established repairs. Earlier sourcewise17-label assignment, per-hypothesis/block calls, two-action source readback, free quote review, program feature heads and teacher-only witness accounts were tried, with adverse or inconclusive net results; this run does not present those as untried ideas.

## Borrowed mechanism and limits

Primary reference: Attribute First, then Generate, https://github.com/lovodkin93/attribute-first-then-generate/tree/cc7b995dfb288da7982ae388994f182bef030b75 and https://aclanthology.org/2024.acl-long.182/ . Reviewed the actual source-selection and alignment functions in `few_shot_experiments/subtask_specific_utils.py` (SHA256 5b53cbce128747db6659ef548ee4c83c9ebdc99385ed3e96100c17281472b108). The borrowed idea is source selection before generation with explicit attribution, not the authors' complete pipeline or reported gains. No author code is copied.

Our original ContractNLI spans already supply exact offsets. We therefore do NOT copy fuzzy matching, whitespace/punctuation stripping, source reassignment, LCS repair, clustering, additional NLP models or three agent roles. This is our one-action task adaptation, not a reproduction of their method.

## Native lawyer action and metric boundary

Single frozen Qwen3-8B call per source, same generation profile in both arms. For each unchanged original hypothesis key the native object has this order:

1. `spans`: sparse `[{source_text: exact complete original SPAN text, span: explicit original integer}, ...]`;
2. `reason`: bounded public source comparison, instructed at most64 words, not private chain of thought;
3. `choice`: original Entailment/Contradiction/NotMentioned.

The source-specific grammar allows EVERY original span and binds each quoted full text to its original native integer. No Gold is read to construct it. This is literal source readback, NOT independent semantic verification, evidence relevance or proof of a correct legal label. NM has an empty list; E/C has at least one member, as in the coherent original answer contract.

The host validates literal pairs and projects EVERY native selected integer and the native label unchanged into the existing scorer. It does not add, filter, deduplicate, realign, repair or vote on answers. Original raw responses, quotes, usage, source hashes and the explicit projection receipt remain archived. Invalid or truncated output is scored invalid, not replaced. Existing original classification, Gold-non-neutral SPAN hard micro-F1 and strict-joint denominators are unchanged. No soft semantic replacement score is used.

Both arms retain the full original source and the SAME ordinary membership anchors. Learned procedures are optional fallible guidance, not facts about the present source. There is no case-specific retention/oral/purpose rule hand-written into the new runtime.

## Sources and online chronology

Before any new source scoring, pure source metadata fixed seed2026101902: eligible130 source components, sample128, all distinct from previous episodes, ordinary202 and inherited exclusion closure. Selection artifact SHA256 `bb3f9dfc434f3bd2c78ef2bc96b1dad0c48da7c9f49cb668999d0fe2d489e378`. No label, outcome, span-count or document-length selection. The two unsampled sources are not a validation set.

The skill library starts EMPTY prospectively for this new method. No chosen older bank, prior R17 prose, previous32 answers or Gold is supplied as teacher experience. Old parent publication/terminal archive is used only to verify the common202 data/model lineage and exclusions.

Sixteen chronological batches of8. Every source in each batch is answered in skills and common-tool empty conditions BEFORE that batch's Gold is revealed. Only after all8 paired answers and scores:
- one existing authorized teacher call receives current8 plus immediately preceding8 full original sources/Gold, actual native own answers, complete original feedback, current bank, and the previous actual published edit's ALL8 matched before/after outcomes and tool versions;
- it performs ordinary CREATE/UPDATE/MERGE/SPLIT/DELETE or NOOP; the number and content of skills are not fixed;
- every structurally valid edit publishes unconditionally, subject only to the disclosed4096-target-model-token storage cap (target3200); no efficacy gate or selected revision;
- the actual published bank reanswers this batch's8 with the SAME current ordinary model; those real answers become next batch's teacher evidence;
- the common ordinary model is fitted on the newly revealed8, identically available to both arms next batch.

The teacher's current source-id provenance is limited to the supplied chronological window, not invented earlier examples. Lossless catalogs share repeated strings and round-trip check all source, quote, annotation, ordering and feedback content; no summarizing or truncation. Window-external old sources are NOT reanswered every batch; no all-seen forgetting/retention claim is made.

B1 before teaching has byte-identical empty policies, so its8 physical native answers are explicitly aliased as both logical conditions. They are NOT counted as independent generations. Later batches always use the actual current bank; no batchwise forced empty-library reset.

## Resources, cost and reporting

Initial ordinary membership model was already supervised on202 TRAIN sources. This common resource and its growth are NOT attributed to skills. New skill-teacher data128; terminal ordinary model supervision330; no claim that the whole system used only128 sources.

Planned physical cost:376 native answers,16 teacher calls,16 CPU ordinary fits. Logical answers384:256 first-encounter arm answers plus128 post-publication training answers;8 cold aliases account for the physical difference. Existing teacher ledger reservations remain intact, cap1426->1442, old-byte copies verified on two same-host filesystems.

No reserved development24/144 probe or additional validation set in this run. Each later batch is a prequential new-source evaluation; its labels are subsequently used in training. Raw batch curves can vary with difficulty. Primary skill contribution is the paired same-source, same-tool gap and complete aggregate, not raw monotonicity or post-publication fit. All adverse batches and costs are retained. Monitor beyond B1; clear systemic failure warrants stopping the run and diagnosing rather than mechanically finishing a bad episode.

Single existing model service and teacher only; no extra paid API,32B model, second GPU instance, fallback, semantic judge or host answer patch. Bounded existing CPU contract checks and actual-backend schema compilation precede the first formal source; no extra model qualification examples.

Official DEV/TEST remain unopened for tuning. Mature experience-learning and equal-call no-skill baselines, independent algorithmic repeats, final frozen TEST, statistical uncertainty and cost comparisons remain required for paper claims. This protocol itself does not satisfy the full Goal.
