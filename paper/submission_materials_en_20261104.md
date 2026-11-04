# English submission materials

Updated 4 November 2026 from the v16 evidence-led revision. This is a journal-neutral working packet, not a submission record. The title and abstract below reproduce the current English manuscript. Journal and author fields in the cover letter require confirmation before use.

## 1. Manuscript title

Evidence-guided skill evolution for statutory exemption reasoning

## 2. Abstract for the submission system

We study whether reusable legal procedures continue to improve a frozen language model after initial skill acquisition. Statutory exemption classification and valuation require identifying independently applicable provisions and assigning their protected amounts. Evidence-guided skill evolution revises task-specific procedures from released training targets and observed executor errors. A library-level controller compares whole proposals with dependency-consistent edits, retaining revisions that improve complete-output utility while constraining current and historical mean performance. Qwen3-8B processes 128 training cases in eight batches; its first-batch library is then held fixed as a reference for continued evolution. On 128 source-disjoint cases, the final seven-record library reaches 95.46% classification F1 and 87.90% valuation F1. Classification improves by 11.95 percentage points over its own first-batch library, with a family-adjusted source-paired interval of [7.33, 16.60]. The valuation continuation estimate is 3.65 points, with interval [-2.82, 10.28]. Chronological first encounters, matched learning controls and recorded instruction changes explain the results for these completed builds. The findings establish further classification gains after initial skill acquisition through a compact, editable procedural memory.

## 3. Keywords

Legal reasoning; skill evolution; experience-based learning; frozen language models; statutory exemptions; execution feedback

## 4. Highlights

- Editable legal procedures improve a frozen 8B model without weight updates.
- Execution-grounded teaching preserves task-specific legal instructions.
- Frozen-test F1 reaches 95.46% for classification and 87.90% for valuation.
- Continued evolution adds 11.95 classification points over the first library.

## 5. Cover letter draft

Dear Editor,

Please consider our manuscript, "Evidence-guided skill evolution for statutory exemption reasoning," for publication in [Journal name].

The manuscript asks whether an initially useful external skill library continues to improve a small language model as legal experience accumulates. We study statutory exemption classification and valuation, where an answer must preserve independently applicable legal alternatives and their protected amounts. Our method couples task-focused teaching from observed execution errors with complete-output utility admission. The learned state is a bounded, editable procedure library; the Qwen3-8B executor's weights remain fixed.

After eight learning batches covering 128 training sources, the final library achieves 95.46% classification F1 and 87.90% valuation F1 on 128 source-isolated cases. These are gains of 30.98 and 32.02 percentage points over the strong empty-library condition. Continued evolution adds 11.95 classification points over the library acquired after the first batch, with a family-adjusted source-paired interval of [7.33, 16.60]. The classification improvement therefore extends beyond initial skill acquisition.

The evaluation combines chronological first encounters, a fixed first-batch reference, matched learning controls and frozen-library comparisons with static and experience-learning memories. Teacher-visible execution evidence and the admission/selection policy are examined through separate learning controls. Recorded instruction changes and same-candidate decision readouts make the evolving procedures inspectable; actual instruction delivery and model-token costs accompany answer quality. The valuation continuation estimate is 3.65 points, with adjusted interval [-2.82, 10.28], distinguishing it from the supported classification gain.

The work connects legal procedure content to its measured execution by a small frozen model. We believe it will interest readers studying legal reasoning, knowledge-based AI and learning through external memory.

Sincerely,

[Confirmed corresponding author name and affiliation]

## 6. Technical facts for author-completed declarations

**AI-assisted work.** An AI coding and research assistant supported implementation, experiment monitoring, literature retrieval, analysis, manuscript drafting and editing. The executor and teacher used within the experimental method are specified separately in the manuscript. Authors must confirm the final description of tool use and their actual review and responsibility before submission.

**Data and code.** The experiments use generated OpenExempt cases from pinned commit `ec6fa2547431096588ce2d3ef107b8adc33cd4fe`. The upstream README declares CC BY 4.0. Generated packets, source splits, learned libraries, predictions, per-case scores and analysis artifacts are preserved with the study. A final public or anonymous access address and the project's own license remain author decisions; the existing private backup is not a public release claim.

**Research scope.** The study evaluates generated statutory benchmark cases using supplied facts, statutes and jurisdiction prerequisites. It does not describe a deployment advising real clients. An institutional ethics determination, if required, must come from the authors and their institution.

## 7. Human confirmations before submission

| Field | Required information |
|---|---|
| Journal | Final journal, school-recognized quartile system and applicable edition; journal-specific formatting and submission requirements |
| Author page | Confirmed names, order, official affiliations, correspondence details and any required identifiers |
| Contributions and approval | Actual individual contributions and all authors' approval of the final manuscript |
| Submission status | Authors' confirmation of originality, prior dissemination and any concurrent-submission restriction |
| Funding | Actual funders, grant numbers and institutional support, or a confirmed absence of funding |
| Competing interests | Each author's actual declaration |
| Ethics | Applicable institutional determination and truthful use-scope statement |
| Availability and license | Approved release scope, access URL, third-party attribution and project license |
| AI use | Confirmed tool-use description, actual author review and responsibility |

No approval, absence of funding or competing interests, ethical exemption, public release, or submission has been inferred from missing information.

## 8. Evidence and current files

- [English and Chinese manuscript files](README.md)
- [Original frozen results and eighteen-endpoint family](tables/utility_frozen_results_20261101.json)
- [Eleven-condition presentation and separate SkillCommit supplement](tables/utility_frozen_results_with_skillcommit_20261104.json)
- [Actual learning, skill-revision and construction-cost evidence](tables/utility_training_evolution_cost_20261030.json)
- [Completed SkillCommit scoring, delivery and paired-comparison audit](../artifacts/research/openexempt_skillcommit_20261102/run05_complete_frozen_TEST_scores_delivery_cost_and_pairing_20261104.json)
- [Reproduction guide](../docs/research/PAPER_REPRODUCTION_GUIDE_20261102.md)
- [Submission preparation and official journal-source checks](../docs/research/PAPER_SUBMISSION_PREPARATION_20261102.md)

This packet is synchronized with v16 and introduces no new model run, score or public-release decision. The original v15 sources and exports remain preserved separately.
