# Computational and LLM Experiment Reporting

Read this checklist when revising a computational, benchmark, agent, or LLM paper.

## Evidence hierarchy

Use the following order when sources disagree:

1. immutable completed-run artifacts and parent hashes;
2. executable code plus frozen configuration;
3. current protocol documents;
4. manuscript text;
5. proposed plans and checklists.

Mark runtime snapshots with date and time. Do not treat live files as completed evidence.

## Intervention and leakage

Report for every role:

- allowed inputs;
- forbidden inputs;
- model and exact revision;
- prompt and decoding settings;
- cache/randomness relationship across arms;
- deterministic repairs, gates, routers, and fallbacks;
- whether the role is shared across arms.

Check indirect channels: labels derived from a treatment artifact, shared caches, retrieval catalogues, domain tags, output-dependent retries, and post-output rewrites. “Shared” does not guarantee harmlessness when activation is affected by treatment.

For held-out data, distinguish byte hashing, schema parsing, record parsing, human exposure, model exposure, tuning, and outcome inspection.

## Estimands and statistical units

Define the session metric before aggregation. State whether a ratio is mean-of-ratios or ratio-of-sums and how zero denominators are handled.

Identify the independent unit. Repeated personas, seeds, turns, judges, or methods within one case do not create new independent cases. Collapse or model dependence explicitly.

For learned artifacts, distinguish:

- test-case uncertainty conditional on one learned artifact;
- dialogue-sampling uncertainty conditional on the artifact;
- variation across independently learned artifacts.

Do not claim algorithm stability from only the first two.

## Confirmatory analysis

Freeze before outcome access:

- primary contrast and direction;
- endpoint definition and aggregation;
- confidence interval method;
- hypothesis test and random seed;
- multiplicity families and gatekeeping;
- failure, missingness, retry, and invalid-session rules;
- non-inferiority margins, if any;
- planned robustness and subgroup analyses.

Use conjunction tests for conjunction claims. A ratio improvement does not prove both numerator gain and denominator reduction.

Report effect sizes, confidence intervals, case-level distribution, win/tie/loss, and harmful-tail frequency. Treat p-values as supporting information.

## Baselines and ablations

A baseline must target a credible alternative explanation. Match model, environment, interface, data exposure, optimization budget, and prompt length where possible; disclose unavoidable differences.

For evolving memory systems, normally separate:

- no-memory control;
- frozen generic/static memory;
- a credible adaptive-memory baseline;
- the proposed method;
- a mechanism-removal learning ablation;
- inference-only routing or delivery ablations.

Do not label a simplified method with a published algorithm's name unless its defining update principle is faithfully implemented.

## Model-based evaluation

Report judge prompt, model revision, repair/normalization, evidence spans, missingness, and qualification set. Model agreement is not expert accuracy.

Use blinded, shuffled reassessment by an independent model as sensitivity. For domain correctness or safety claims, add qualified human review or narrow the claim to the simulator.

## Tables and artifacts

Keep qualification separate from effects. Every results table must expose planned/completed/invalid denominators and independent `n`.

Bind tables and figures to machine-readable analysis artifacts. Preserve model responses, prompts, hashes, environment versions, token/call counts, wall time, compute, failures, and release permissions.

## Claim language

Use:

- “improved the prespecified metric in this benchmark” for supported effects;
- “was associated with” for observational mechanisms;
- “no evidence of a difference” for non-significant superiority tests;
- “met the prespecified non-inferiority margin” only after a valid non-inferiority test;
- “simulated consultation” unless real-client validation exists.

Avoid “causal”, “safe”, “robust”, “general”, “expert-validated”, and “real-world” unless the corresponding design directly supports each word.
