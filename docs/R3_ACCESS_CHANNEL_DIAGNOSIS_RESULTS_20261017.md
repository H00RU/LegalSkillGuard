# Complete fixed-R3 delivery diagnosis

2026-10-17 23:20 CST actual completion.16 NEW native answers,0 teachers;24
historical actual B4 answers explicitly reused,40 unique raw IDs on all8 sources.
No partial scores were used to change prompts. The completed source/code snapshot
is preserved before the subsequent main-chain revision; do not run its old frozen
configuration under modified current source and claim byte-identical reproduction.

| Input | Accuracy % | Original hard Gold-NN micro-F1 % | Strict joint % | TP/FP/FN |
|---|---:|---:|---:|---:|
| Original strong empty |73.53|51.49|47.06|52/19/79|
| Original ordinary M2 |70.59|60.29|50.00|63/15/68|
| Original fullR3 |80.15|28.08|52.94|57/218/74|
| Lossless compressed fullR3 |79.41|35.47|54.41|61/152/70|
| Ordinary M2+sameR3 criteria |79.41|54.00|58.82|54/15/77|

Compression changes representation and an explanatory legend, not only length;
it preserves every role membership/source/criterion, and is insufficient. Source624
still has128 false positives,430 rises to18; there is no universal range repair.
The ordinary-plus-criteria condition removes noisy learned windows and supplies
the existing calibrated candidates simultaneously; do not call it an isolated
query pruning ablation. Its15 FP equal ordinary but9 fewer TP, so skill evidence
benefit over ordinary is not demonstrated. Two endpoints improving is not all
three endpoints improving, and small adaptive development data are not TEST.

More seriously, ordinary E/C/NM correct45/9/42 becomes43/7/58. Nonnneutral joint
26→22 despite overall joint68→80. The apparent label/joint gain is driven by NM,
not uniform substantive legal performance. Some evidence is lost after a wrong NM
verdict; some is omitted despite the right verdict. Original dense Gold members
are not to be discarded as inconvenient or replaced with minimal rationales.

Teacher content is not universally missing: R3's nda-20 rule explicitly says a
complete return/destroy duty without a retention exception opposes retention.
Yet on two sources the actor returned NM with the public reason that no retention
exception was specified. This is actual instruction-execution failure despite a
correct rule, not proof that adding labels or more teacher prose alone will fix it.

The selected next implementation removes the noisy query channel globally and
learns fresh criteria over the SAME actual ordinary aids as its control. Teacher
feedback now comes from the native actor's saved candidate payload, not a stale
no-retriever interface. This is a justified next online experiment, not a claimed
solution; it still must establish new-contract evidence and nonneutral gains.
Keep one active actor and atomic editor, no additional judge/repair/admission layer.

New native usage139998 input+30181 completion tokens; all adverse outcomes kept.
Original-author/wire audit SHA
`bf19f11c8431d4347b598e87595160a660ab53cf105f8a599fb912010f64a48a`:
`artifacts/research/r3_access_channel_diagnosis_20261017/complete40_original_author_execution_and_skill_benefit_audit.json`.
Actual terminal archive on both local filesystems, all232 members verified:
`aedafeec47ba1b205dbcc3466a11ed09aeecf0646f3f47192e96d3051ca0d3a2`.
Same host, not offsite/model-weight backup. Main Goal remains pending.
