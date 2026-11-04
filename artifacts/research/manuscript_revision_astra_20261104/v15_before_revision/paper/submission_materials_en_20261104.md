# English submission materials

Prepared 4 November 2026 from the completed v15 manuscript. This is a journal-neutral working packet, not a submission record. The title and abstract below reproduce the current English manuscript. Journal and author fields in the cover letter require confirmation before use.

## 1. Manuscript title

Evidence-guided skill evolution for statutory exemption reasoning

## 2. Abstract for the submission system

Reusable instructions offer a learning interface for small language models whose weights remain fixed, but an initially useful memory does not establish that further experience improves it. We study this distinction in statutory exemption classification and valuation, where an answer must preserve independently applicable alternatives and assign their protected amounts. Evidence-guided skill evolution combines task-focused execution teaching with complete-output utility admission: a teacher revises legal procedures from released training targets and actual executor errors, while replay-based publication checks both omitted and false claims. A frozen Qwen3-8B learns over 128 sources in eight batches and is then evaluated on 128 source-isolated cases. Its final seven-record library achieves 95.46% classification F1 and 87.90% valuation F1, gains of 30.98 and 32.02 percentage points over the strong empty-library condition. Compared with its own first-batch library, continued evolution adds 11.95 classification points, with a family-adjusted source-paired interval of [7.33, 16.60]. Under the shared executor interface, it also exceeds a SkillCommit paper adaptation by 27.49 classification and 23.08 valuation points. Matched controls connect final-library utility to teacher-visible execution evidence and the admission/selection policy. These results demonstrate continued improvement in legal classification through editable procedures rather than parameter updates.

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

The evaluation combines chronological first encounters, a fixed first-batch reference, matched learning controls and frozen-library comparisons with static and experience-learning memories. Under the shared executor interface, the final library also exceeds the SkillCommit paper adaptation by 27.49 classification and 23.08 valuation points. Teacher-visible execution evidence and the admission/selection policy are examined through separate learning controls. Actual instruction delivery and model-token costs are recorded alongside answer quality.

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

This packet introduces no new method, experiment, score or public-release decision. The v15 scientific manuscript and its exports remain unchanged.
