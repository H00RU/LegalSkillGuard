---
name: nature-paper
description: Revise scientific manuscripts into concise, evidence-led, high-impact journal prose while preserving methodological precision, uncertainty, and unresolved results. Use for drafting or editing research papers, abstracts, titles, Results, Methods, Discussion, tables, figures, response letters, and DOCX/Markdown/LaTeX manuscripts—especially computational, AI, legal-AI, benchmark, or agent studies with pending experiments, preregistered analyses, or strict held-out boundaries.
---

# Nature Paper

## Objective

Produce a clear, selective scientific argument with the evidentiary discipline expected by selective journals. Treat “Nature style” as a standard of reasoning and presentation, not imitation of a particular author or article.

Never invent data, citations, implementation details, novelty, statistical support, human validation, or completed experiments.

## Workflow

### 1. Establish the evidence boundary

1. Identify the manuscript version, target audience, executable protocol, completed artifacts, and prohibited sources.
2. Rank sources of truth: frozen run artifacts and code/config first, current protocol second, manuscript prose third, plans last.
3. Build a claim ledger with four states:
   - `VERIFIED`: directly supported and safe to write as fact.
   - `PENDING`: requires a running or planned analysis.
   - `PLANNED`: protocol is frozen but execution is incomplete.
   - `UNSUPPORTED`: remove or narrow.
4. Preserve held-out boundaries. Do not inspect test content or outcomes to improve prose, baselines, endpoints, prompts, or thresholds.

For computational/LLM studies, read [references/computational-experiment-reporting.md](references/computational-experiment-reporting.md) before revising Methods, Results, or reproducibility claims.

### 2. Find the paper's single scientific message

State in one sentence:

- the unmet problem;
- the specific intervention;
- the estimand or test;
- the boundary of the intended claim.

Remove contributions that merely restate engineering components. Prefer one defensible central claim with two or three supporting claims over a long novelty list.

### 3. Restructure before polishing sentences

Use this default narrative:

1. **Opening problem**: establish the consequential gap, not a broad history of the field.
2. **Why existing approaches fail**: identify the exact missing capability or evaluation design.
3. **Proposed idea**: explain the mechanism in plain language before notation.
4. **Evidence plan/results**: order by research question, not implementation chronology.
5. **Boundary and implication**: say what changed, what did not, and why it matters.

Keep Methods sufficiently detailed for reproduction. Do not force a short main text by hiding essential intervention, exclusion, failure, or statistical rules.

### 4. Rewrite at paragraph level

Give each paragraph one job:

1. Lead with its scientific point.
2. Supply the minimum mechanism or evidence needed.
3. End with the implication or limitation.

Prefer concrete subjects and verbs. Define specialized terms once. Replace promotional adjectives with measurements or design facts. Use “suggests”, “is consistent with”, or “within this simulator” when evidence does not support causal or real-world claims.

Do not use significance as a synonym for importance. Report effect sizes and uncertainty before p-values.

### 5. Handle pending experiments visibly

Do not fill pending result cells with qualification, historical, partial-run, or live-monitoring numbers.

Use explicit placeholders:

- `[PENDING RESULT — endpoint, contrast, estimate, 95% CI, n]`
- `[PENDING ANALYSIS — frozen rule or artifact needed]`
- `[PENDING METADATA — author/hardware/cost/repository field]`
- `[PLANNED EXPERIMENT — method, matrix, freeze condition]`

In DOCX, apply yellow highlighting to the entire placeholder and keep it syntactically distinct from prose. Retain blank table cells only when the placeholder cannot fit; otherwise insert a highlighted pending label. Never let placeholders look like zero, missing-at-random data, or completed evidence.

### 6. Edit each manuscript component

#### Title

Name the phenomenon and method without claiming a result that is still pending. Include “simulated” or the benchmark boundary when omission could imply real-client validation.

#### Abstract

Use five moves: problem, gap, method, evaluation design/result, bounded implication. When results are pending, keep a highlighted result sentence rather than writing a conclusion in future-perfect language.

#### Introduction

Reach the research question quickly. Explain why the endpoint resolves a real ambiguity. End with contributions that correspond one-to-one with later evidence.

#### Related work

Compare mechanisms, supervision, adaptation location, evaluation environment, and evidence strength. Do not write a paper-by-paper catalogue. Verify all recent references against primary sources.

Before inserting or revising a bibliography entry, open the canonical publisher, proceedings, DOI, or repository record and copy the exact title, author order, year, venue, pages, and DOI. Never paraphrase a paper title inside the reference list. If any field cannot be verified, leave a highlighted `[PENDING METADATA — verify citation field]` marker instead of guessing. For DOCX deliverables, use a resolvable DOI/URL and preserve or create a clickable link when the house style permits it.

#### Results

Organize by question and figure. Start with the estimand and denominator. Report planned/completed/invalid counts, arm estimates, paired effects, uncertainty, multiplicity family, and adverse cases. Distinguish confirmatory from exploratory analyses.

#### Methods

Make information access, intervention isolation, randomization, stopping, fallback, model revisions, prompts, data provenance, exclusion, and statistical unit explicit. Describe the executed system, including shared post-processing—not the intended architecture.

#### Discussion

Open with the supported answer, then mechanism interpretation, comparison with prior work, limitations, and practical implication. Do not convert absence of a significant difference into equivalence or safety.

### 7. Design tables and figures as evidence

Each display must answer one question. Put the estimand, comparison direction, independent `n`, uncertainty, denominator, and pending/completed status in its caption or header.

Prefer:

- a design/fairness table;
- a qualification table clearly separated from outcomes;
- a main outcome table with arm estimates;
- a paired-effect table with CI and multiplicity family;
- a failure/safety/cost table;
- case-level effect plots and mechanism diagnostics.

Do not keep empty columns for methods that will not be run. Do not use arrows such as “higher is better” for metrics where overproduction can be harmful.

### 8. Preserve document integrity

For DOCX revisions:

1. Create a new revision file unless the user explicitly requests overwrite.
2. Preserve styles, section breaks, equations, references, hyperlinks, captions, alt text, and embedded media.
3. Keep pending text yellow-highlighted.
4. Validate the revised DOCX by reopening it and exporting to PDF or plain text in a temporary directory.
5. Compare paragraph/table/figure counts and inspect key pages visually.
6. Record which claims changed and which placeholders remain.

Do not silently alter numerical values, reference order, formula semantics, or table denominators during style editing.

## Final quality gate

Before delivery, verify:

- every strong claim maps to completed evidence;
- protocol and implementation describe the same intervention;
- the independent sample size is correct;
- numerator, denominator, failures, and missingness are visible;
- planned and completed experiments are never conflated;
- effect size and uncertainty precede significance;
- legal, causal, safety, and real-world claims match the validation level;
- all pending evidence is highlighted and searchable;
- the manuscript opens cleanly and no equation, table, figure, or citation was lost.
