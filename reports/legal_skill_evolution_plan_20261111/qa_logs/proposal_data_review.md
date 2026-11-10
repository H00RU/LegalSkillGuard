# Final data review — 2026-11-11

Reviewed `PLAN.md`, `DATA_PLAN.md`, `DATA_EVIDENCE.json`, base/pilot manifests, and both `CONTROLLED_LAYER` files. This pass used source identity metadata and TRAIN records only; it did not reopen TEST label files or run models. Protocol integration is owned by the parent agent.

## Verdict

**No P0 data contradiction or infeasible data prerequisite.** The fixed five-dataset route and 20-parent pilot are ready for implementation. Formal blind TEST remains conditional on the already-required server exposure audit.

**P1 wording correction:** PLAN's opening claim “本次没有……打开测试” is too broad. Data preparation mechanically inspected public official split files/labels, especially to regroup MAUD by parent agreement. Replace it with “本次没有恢复服务器、调用模型、启动模型测试或依据TEST结果修改方法；数据打包中的机械核验与后续暴露审计分别记录。” Mechanical packaging is not a model evaluation, and a public file's availability does not prove absence of human/teacher exposure. The parent was notified; no new experiment is needed.

## Checked invariants

- Base sources: OE32/8/32, SARA24/8/32, CNLI24/8/32, RA24/8/32, MAUD24/8/32. Totals **128 TRAIN / 40 DEV / 160 TEST**; native views **280 / 88 / 352**. Multiple views never increase independent-source counts.
- All **12 old partition source-key sets** (four retained datasets × TRAIN/DEV/TEST) exactly match the prior manifest. Source groups are disjoint across partitions within all five datasets. Base manifest was not edited; declared canonical hash remains `e90c138aaab2a069d2435e3e46f2ea81b3c81235569ce36c0aff9eeede3447f3`.
- MAUD regrouping does not claim to preserve its official row split: all official splits cover the same152 agreements, while this plan groups151 conservative parents after merging the identical-fulltext pair. All three native questions of a parent stay together. ContractNLI changes the task view to four existing native hypotheses while preserving parent identity; old exposure is not erased by that change.
- Controlled layer: six current MAUD TRAIN parents ×4 plus one SARA TRAIN parent ×4 plus one RA TRAIN parent ×4 = **8 existing parents / 32 derived views / 0 new sources**. Native labels are not relabelled. The layer is explicitly separate from native metrics and has **no prepared held-out controlled TEST**.
- MAUD controlled definitions have CSV compound selectors, fulltext hashes and normalized character offsets. Contract151's omitted IP exception is included in the full controlled input, with a non-IP scope guard. Native Actual/Constructive labels are not blindly converted to truth tables.
- RA has12 passing official component checks, not a claimed whole-system oracle audit; controlled fee120 is marked hypothetical. SARA checks only section151(d)(5)'s time applicability, not total tax/exemption. Actor-visible source and facts are separate from grading functions.
- The32 controlled views establish executable applications beyond returning a source field. They alone do not establish natural coupled-Lift failures, spontaneous joint-revision frequency, or method superiority. PLAN already places those questions in the bounded real-model pilot.

## Locked pilot

`pilot_source_manifest.json` fixes **MAUD6 + CNLI5 + OE3 + SARA3 + RA3 =20 TRAIN parents**, including all8 controlled parents. Other parents fill quotas by SHA256 of the fixed seed, dataset and source key; the same hash gives the global order. No model output, correctness result or TEST label enters selection.

All pilot systems reuse exactly these20 parents, same order, public inputs and allowed TRAIN feedback. Counts: **50 native views +32 controlled views =82 views if all controlled material is used**, still20 parents. DEV/TEST counts are0. Existing TRAIN exposure and pending server-history audit are explicit. Formal systems restart from the same empty library/public tools and do not silently warm-start from pilot skills.

Pilot canonical hash: `79e0b80a80c19437c437cda86eb0f2c6c5fc9088e689d85b22a1bc8d8d45c657`.

## Exposure gate retained

Previously inspected TEST errors or TEST-driven skill changes disqualify those parents from a new blind claim. Repackaging a question or resealing a file does not fix that. SARA has only8 potential unused native TEST groups beyond the old32; OE's current72-source package has no spare parents. PLAN/DATA_PLAN already require honest historical reporting or documented replacement before formal blind evaluation. This does not block the TRAIN-only pilot.
