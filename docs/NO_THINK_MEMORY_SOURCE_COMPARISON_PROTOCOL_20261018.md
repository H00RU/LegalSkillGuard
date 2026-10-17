# Fixed16 source/memory comparison with an explicit no-thinking profile

Declared2026-10-18 before any new response. This is one bounded mechanism study,
not a new trained method, a validation set, an independent repeat or official TEST.
Zero teachers,48 new native answers; keep32 explicitly historical reference
answers distinct, including the invalid old answer with its full denominator.

## Two observed problems, neither hidden by this study

The old run terminated after72 native/2 teachers and a COMPLETE16-answer R2 phase.
Source384 returned finish_reason=stop,stop_reason151643,2815 output tokens, while
its public JSON string remained unclosed and ended with a raw closing think tag.
Max output was8192: this is not an output-budget cutoff or a client repair.
All16 original scores, including invalid384, were saved before the hard stop;
R2 all16 was74.63/48.23/52.21% (accuracy/Gold-NN hard F1/joint), not a completed
four-update run. Full actual terminal archive is dual-preserved, SHA
20687cf274227219d83b5b9ed2f765f41f7a0af910c483ebcf47dcde20713303.

Separately, across the first16 complete strong-empty/ordinary pairs, fixedM2
candidates cover121/314 original Gold-NN members. The ordinary actor cites117
of those and only16 unlisted true members. Introducing the aid loses58 true
members originally found by empty,57 unlisted;28 are newly gained,net−30.
F1 drops60.48→54.40% despite higher label accuracy. Full original text is always
present: this is an observed cue-induced selection deficit, not source deletion
or proof of the model's hidden attention process. M2 emits ALL scores>0.5, with
no top-k truncation. Do not invent a candidate-count fix or change Gold.

## Profile and safeguards

Same RAM-resident Qwen3-8B, same PID/start ticks, BF16/context/seed45/T0.6/p0.95/k20,
same8192 output allowance, same common system/schema/source text. No restart,
new model, weight update, generation retry, JSON repair, label remap or evidence
union. Explicit chat_template_kwargs.enable_thinking=false is applied identically
to actual generation and the live-server tokenizer. All native raw outputs remain.
The former thinking-on tokenizer/generator were mutually consistent; the new
mode required removing their hardcoded setting, not pretending old token counts
had already been wrong. A profile mismatch now fails before generation.

The live server identifies as vLLM0.10.2. Its pinned
[Qwen parser](https://raw.githubusercontent.com/vllm-project/vllm/v0.10.2/vllm/reasoning/qwen3_reasoning_parser.py)
uses token IDs for reasoning-end detection and string delimiters for nonstream
extraction. That supports checking this interface but does NOT uniquely prove
the internal cause of the observed malformed answer. Do not cite newer0.21
Responses-API bugs as proof about this0.10.2 Chat-Completions request.
No-thinking is a prospective mode comparison, not a promised syntax guarantee.

## Exactly three new conditions on the complete same16 sources

Use the entire previously selected first16 training contracts. Put384 first only
to replay the exact failed input as a protocol check; retain all16, not a good-
score subset. Within-source three-arm order rotates. All48 are generated before
any unified effectiveness score; if the FIRST replay is still invalid, stop with
that raw cost and no partial effectiveness claim, never retry until it parses.

1. `no_think_M2_R2`: identical actual old R2 input, same8 criteria and ordinary
   candidates. On384, the whole native request differs only by the explicit
   thinking-disable chat-template option. This also anchors the profile change.
2. `no_think_source_R2`: identical R2 bank/criteria and complete original source,
   remove ALL ordinary candidate lists and their duplicate text catalogue.
   No query window is introduced. This isolates the aid within the new profile.
3. `no_think_source_empty`: original strong-empty input, no library/no candidates.
   Source+R2 minus this condition measures the pure memory effect under the SAME
   profile. R2 versus old thinking-on empty is an additional strong reference,
   not a same-profile ablation; report both instead of weakening the baseline.

The same trained R2 library is held verbatim; no teacher, new edit, admission,
selected-best bank or rollback occurs. Original3 classes,17 hypotheses, all
original SPANs and Gold-NN scoring remain. Class counts, NN joint, TP/FP/FN and
source-paired descriptive intervals accompany the three primary endpoints.
No official DEV61/TEST123 contents are opened.

This study decides the next globally fixed online chain, not whether to patch
particular cases. Even a positive seen16 result still requires a complete fresh
online episode, later different contracts, fair mature-memory and equal-call
review controls, independently trained repeats and untouched final TEST.
Preserve all negative results/costs and the old failure. The new run is detached
and has terminal preservation; two local filesystems are not offsite or weights.
