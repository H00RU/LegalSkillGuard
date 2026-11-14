# Actual paired editing with learned repair-impact requirements

[Results](unbound_actual_check/summary.json) · [cost and preservation](unbound_actual_check/cost_and_preservation.json) · [actual representation collision](unbound_actual_check/actual_graph_feature_collision.json) · [common task](common_task.json) · [frozen learned requirements](learned_generation_scope.json) · [copy/hash manifest](artifact_copy_manifest.json).

Both editors independently receive the same current library, full original eight TRAIN sources, actual before executions, historical repair graphs/feedback and joint source/consumer/G/renderer edit capacity. ImpactGuided additionally receives requirements derived by the frozen V1 footprint model. FreeHistory can freely learn impact itself and reuse all actual correct historical patches. This isolates update guidance on a shared library, not end-to-end independent rule acquisition.

The new repair target62fd was not in the three footprint-training event mothers. It is still a historically exposed original TRAIN source, not blind DEV/TEST. Its source clause expressly qualifies a restriction by written authorization or required purposes, but the current path also preserves an unconditional duplicate. Both editors remove the incorrect duplicate and keep the qualified restriction, evidence and actor.

|Actual result|ImpactGuided|FreeHistory|
|---|---:|---:|
|Nominal compilation and main execution|pass|pass|
|Known unconditional error removed|yes|yes|
|Supported qualified restriction retained|yes|yes|
|Eight-mother native correct, before → after|25/32 →25/32|25/32 →25/32|
|Changed source functions|5|4|
|Teacher input tokens|110540|108847|
|Teacher output tokens, including reasoning|4142|3580|
|Teacher service seconds|87.991|79.911|

This example establishes that learned scope requirements reached a real editor and actual selection checks. It does not establish a U accuracy or cost advantage. Source checks are partial; unchanged native scores do not certify every field. All sixteen actual source executions, candidate libraries, raw teacher requests/responses and failures remain available in this directory. There are no fallback model calls.

Exactly0E/2T new physical requests,10583→10585 cumulative, now10343E/242T and0 pending; all old10583 rows are unchanged. Summed usage219387 input/7722 output, including4868 reasoning tokens,167.902 teacher service seconds. Actual cash invoice/GPU allocation is unavailable. An attempted parallel orchestration conflicted with the serial ledger policy: FreeHistory was rejected before reservation. The first completed response was retained; the second arm was then dispatched once serially. The [recovery record](unbound_dispatch_recovery.json), original log and original frozen source are retained. The current driver now follows the serial policy. Completed scientific hashes were verified before that correction; use the frozen source snapshot when examining this closed run, rather than trying to reopen its call identities under modified code.

Subsequent V2/V3 offline learning consumes genuine source/harm/repair feedback. Those updated models are not retrospectively substituted for V1 in this paired comparison. No new full training, DEV/TEST or paper is started. Same Goal remains active and incomplete.
