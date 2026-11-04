# Supplementary Data 1 — evidence-guided statutory skill evolution

This is the offline evidence supplement for the 4 November 2026 revision. It
contains existing observations and new analyses of those observations, not new
model predictions, teacher calls or independent learning repeats. All original
records are byte-preserved; `SUPPLEMENT_MANIFEST.json` lists their hashes.
The main, original frozen evaluation and SkillCommit binding manifests are
included unchanged. The complete local Python modules are additionally captured
for offline import portability; this is not a retroactive extension of the
historical binding lists.

Extract the ZIP into a new directory and work from its root. Paths reproduce the
project layout. The archive deliberately excludes model weights, credentials and
environment directories. It is not an installer or a claim of public release.

## Read the learned skills and implemented decisions

- Main: `runs/legal_openexempt_complete_output_utility_public_assets128_20261030_run01/`.
  Complete `publications/b1.json` and `publications/b8.json` contain the actual
  banks, hashes and teaching decisions. All eight publications, 16 diagnosed
  proposals, teacher wire requests, first answers and assessment records are kept.
- Strict-policy control:
  `runs/legal_openexempt_v6_strict_policy_control_public_assets128_20261030_run01/`.
- Main learner: `experiments/openexempt_online.py`; task projections/components:
  `legal_skill_guard/learning/task_scoped_skills.py`; schema/delta application:
  `legal_skill_guard/learning/publication.py`.
- Same-candidate policy readout:
  `artifacts/research/manuscript_revision_astra_20261104/recorded_candidates_both_policies.json`.
  It reproduces all 32 actual-policy selections and reports the alternative
  policy on those fixed pools. It is not a regenerated counterfactual stream.

## Reproduce original scores, intervals and figures' source values

Use Python 3.11 and the project's pinned `uv.lock`/`pyproject.toml`, including its
OpenExempt optional dependencies. The original software capture is in the frozen
configuration manifests. In an existing project checkout use `.venv/bin/python`.
In a separate environment the project can be installed with
`python -m pip install -e '.[openexempt]'`; no GPU or model download is needed for
the following commands. Dependency installation itself may require network access;
the checks disable network connections once running.

From the extracted project root:

```bash
python artifacts/research/manuscript_revision_astra_20261104/offline_checks/all_2816_frozen_scores_and_aggregates.py
python artifacts/research/manuscript_revision_astra_20261104/offline_checks/paired_bootstraps_tables_and_training_curves.py
python artifacts/research/manuscript_revision_astra_20261104/offline_checks/raw_HTTP_decode_cost_and_source_split.py
```

The first check regrades every saved EC/EV answer and compares all score fields
and all eleven aggregates. The second reproduces the original 18-endpoint family,
separate SkillCommit two-endpoint supplement, bilingual display tables and all
eight batches' first answers. The third traces raw response envelopes through
decoding and saved pre-grading predictions, and checks costs/source separation.
These scripts print diagnostic differences rather than silently overwriting data.
They are copied from the previously audited read-only commands; only import setup
and table lookup are adjusted for the newly inserted appendix tables.

The original ten-condition and separate SkillCommit predictions precede their
own scoring; original unfavorable and invalid outputs are retained. Complete
scored records, pre-grading copies and raw executor envelopes are included. The
pinned upstream evaluator and archive are under `data/cache/openexempt/`.
The primary 20,000-draw intervals remain unchanged. The separate 200,000-draw
numerical-sensitivity readout is not substituted for them.

## Additional existing-record analyses

The revision directory contains the per-source 2,816-row CSV, error decomposition,
TRAIN/TEST distributions, same-candidate policy decisions, bootstrap sensitivity
and actual SkillCommit delivery-scope analysis. `analyze_existing_records.py`
recreates those derived outputs **in its own revision directory**; run it in an
extracted copy if the supplied analysis files should remain untouched. It needs
NumPy and `tokenizers`, plus the Qwen3-8B `tokenizer.json`, not model weights:

```bash
python artifacts/research/manuscript_revision_astra_20261104/analyze_existing_records.py /path/to/Qwen3-8B/tokenizer.json
```

No server tokenization or generation is used. All policy and scoring functions
remain frozen. The one composed candidate is checked against complete measured
parent/proposal requests; no answer is selected by its individual score.

## Scope and attribution

EC and EV are source-paired tasks on custom 2–4-asset OpenExempt IID packets,
not official Advanced-suite results. Independent learning variance and transfer
to new legal regimes are not measured. The SkillCommit comparison is a later
supplement on the existing TEST packet with the declared local BGE adaptation;
its four delivered EV patterns all concern Illinois. Full memory contents and
delivery IDs are included so that this limitation can be inspected directly.

OpenExempt is preserved at `ec6fa2547431096588ce2d3ef107b8adc33cd4fe` with its
upstream attribution. This local delivery does not select a license or authorize
public distribution on the authors' behalf. The complete historical backup and
retired project experiments are separate from this focused paper supplement.
