#!/usr/bin/env python3
# ruff: noqa: E501
"""Add the frozen four-arm comparison plan to the working manuscript.

The source DOCX is never overwritten.  This script edits OOXML directly so the
existing styles, equations, drawings, and embedded media are retained.  It does
not read experiment data; every unmeasured result remains an explicit yellow
PENDING marker.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import NamedTemporaryFile
from xml.dom import Node, minidom
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from revise_legal_skill_evolve_docx import (
    direct_children,
    paragraph_text,
    replace_paragraph,
    shade_run,
    with_pending,
)

MODIFIED_AT = "2026-09-11T10:00:00Z"
FIGURE3_MEDIA_PATH = "word/media/rId39.png"
FIGURE3_ASSET = (
    Path(__file__).resolve().parents[1] / "figures" / "Figure3_current_protocol.png"
)


def plain(text: str) -> list[tuple[str, bool]]:
    return [(text, False)]


def find_paragraph_by_prefix(document: minidom.Document, prefix: str) -> Node:
    matches = [
        paragraph
        for paragraph in document.getElementsByTagName("w:p")
        if paragraph_text(paragraph).startswith(prefix)
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one paragraph starting {prefix!r}, found {len(matches)}"
        )
    return matches[0]


def replace_prefix(
    document: minidom.Document,
    prefix: str,
    segments: list[tuple[str, bool]],
) -> None:
    replace_paragraph(find_paragraph_by_prefix(document, prefix), segments)


def cell_text(cell: Node) -> str:
    return "".join(paragraph_text(p) for p in cell.getElementsByTagName("w:p"))


def row_cells(row: Node) -> list[Node]:
    return direct_children(row, "w:tc")


def table_rows(table: Node) -> list[Node]:
    return direct_children(table, "w:tr")


def table_header(table: Node) -> list[str]:
    rows = table_rows(table)
    if not rows:
        return []
    return [cell_text(cell) for cell in row_cells(rows[0])]


def find_table(document: minidom.Document, first_header: str) -> Node:
    matches = [
        table
        for table in document.getElementsByTagName("w:tbl")
        if table_header(table) and table_header(table)[0] == first_header
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one table headed {first_header!r}, found {len(matches)}"
        )
    return matches[0]


def set_cell(cell: Node, text: str, pending: bool = False) -> None:
    paragraphs = direct_children(cell, "w:p")
    if paragraphs:
        paragraph = paragraphs[0]
        for extra in paragraphs[1:]:
            cell.removeChild(extra)
    else:
        paragraph = cell.ownerDocument.createElement("w:p")
        cell.appendChild(paragraph)
    replace_paragraph(paragraph, [(text, pending)])


def find_row(table: Node, first_cell: str) -> Node:
    matches = [
        row
        for row in table_rows(table)
        if row_cells(row) and cell_text(row_cells(row)[0]) == first_cell
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one row beginning {first_cell!r}, found {len(matches)}"
        )
    return matches[0]


def set_row(row: Node, values: list[tuple[str, bool]]) -> None:
    cells = row_cells(row)
    if len(cells) != len(values):
        raise RuntimeError(
            f"Row has {len(cells)} cells but {len(values)} values were supplied"
        )
    for index, cell in enumerate(cells):
        value, pending = values[index]
        set_cell(cell, value, pending=pending)


def insert_row_after(reference_row: Node, new_row: Node) -> None:
    parent = reference_row.parentNode
    sibling = reference_row.nextSibling
    if sibling is None:
        parent.appendChild(new_row)
    else:
        parent.insertBefore(new_row, sibling)


def remove_table_column(table: Node, column_index: int) -> None:
    grids = direct_children(table, "w:tblGrid")
    if grids:
        columns = direct_children(grids[0], "w:gridCol")
        if column_index >= len(columns):
            raise RuntimeError("Table grid does not contain requested column")
        grids[0].removeChild(columns[column_index])
    for row in table_rows(table):
        cells = row_cells(row)
        if column_index >= len(cells):
            raise RuntimeError("Table row does not contain requested column")
        row.removeChild(cells[column_index])


def highlight_pending_runs(document: minidom.Document) -> None:
    for text_node in document.getElementsByTagName("w:t"):
        if not text_node.firstChild:
            continue
        if "[PENDING " not in text_node.firstChild.data and "[PLANNED " not in text_node.firstChild.data:
            continue
        ancestor = text_node.parentNode
        while ancestor is not None and getattr(ancestor, "tagName", "") != "w:r":
            ancestor = ancestor.parentNode
        if ancestor is not None:
            shade_run(ancestor)


def revise_document(xml_bytes: bytes) -> bytes:
    document = minidom.parseString(xml_bytes)

    replace_prefix(
        document,
        "Effective legal consultation depends",
        with_pending(
            "Effective legal consultation depends on eliciting material information without imposing unnecessary questioning. We introduce LegalSkillEvolve, a framework that accumulates reusable natural-language consultation skills while keeping the underlying language models frozen. In the reviewed implementation, an opening-only planner is skill-blind; a fixed session bundle is supplied only to the consultation policy, and a deterministic StopGate can redirect premature termination or actions disallowed by encoded structural and stopping rules. Across eight sequential blocks, four full trajectories per training case provide reward-separated, outcome-typed contrasts for fact elicitation, evidence-gap recognition and efficient stopping. A teacher abstracts cumulative evidence into candidate skill documents, which enter the working library only after static format, provenance, information-boundary, duplication and capacity checks. These gates establish admissibility, not legal correctness or effectiveness. The planned final evaluation crosses 30 official Chinese DLawBench benchmark cases that are absent from the 128-case skill-learning corpus with four client personas. The primary estimand is the case-level mean of session new-fact-bearing-question rates, accompanied by separate fact and question outcomes, quality metrics and failure counts. ",
            "[PENDING RESULT — insert the designated L8-versus-Base effect, 95% case-level confidence interval and the separately supported fact and question conclusions]",
        ),
    )

    replace_prefix(
        document,
        "For each experience block",
        plain(
            "For each experience block, all 16 case identifiers are selected in advance without reference to outcomes. Their sample-0 trajectories under the current library are paired with empty-library shadow consultations using the same case, persona and sampling stream. The current-library observation is neither the best of four trajectories nor their average. If the current library is empty, the identity shortcut yields a zero comparison without generating duplicate shadows."
        ),
    )
    replace_prefix(
        document,
        "Figure 3. Direct accumulation",
        plain(
            "Figure 3. Direct accumulation and library-level evaluation. Each block runs under L_{b−1} and can add qualified candidates to L_b. Diamonds denote report-only inspections. Prequential diagnostics compare all 16 predeclared sample-0 trajectories from each block with matched empty-library shadows; the block-1 identity shortcut avoids duplicate runs. These are development diagnostics for L0–L7. The final confirmatory comparison uses the designated frozen L8 library, including any additions made after block 8."
        ),
    )
    replace_prefix(
        document,
        "External memory can adapt behavior",
        plain(
            "External memory can adapt behavior without changing model weights. Verbal reflection, accumulated experience, workflow memory and evolving context have all been used to guide later agent actions [4–8]. For legal consultation, however, reward differences alone do not reveal whether a better trajectory asked a more informative question, recognized an external evidence requirement or stopped at an appropriate point. LegalSkillEvolve therefore records outcome-typed trajectory contrasts as evidence for procedural hypotheses; the final library, rather than any admitted document, is the treatment evaluated on official benchmark cases excluded from its source evidence."
        ),
    )
    replace_prefix(
        document,
        "LegalBench and LawBench evaluate broad legal capabilities",
        plain(
            "LegalBench and LawBench evaluate broad legal capabilities [1,2], while DLawBench models multi-turn consultation using finite client beliefs, reference facts and evaluation rubrics [3]. LeCoDe, UCL-Bench, MILE, LegalAgentBench and PLawBench further illustrate the move toward realistic legal documents, interactive environments and agentic legal tasks [18–22]. We evaluate a modified local consultation system on the public 30-case Chinese DLawBench subset; this is not a reproduction of the benchmark's full simulator or scoring configuration. The external cases are absent from trajectories and teacher evidence, but planned inspection of comparator-level aggregate scores makes method development benchmark-aware rather than fully outcome-blind. Public availability also precludes any claim about foundation-model pretraining exposure."
        ),
    )
    replace_prefix(
        document,
        "The 30-case Chinese collection is excluded",
        with_pending(
            "The 30-case Chinese collection is excluded from training trajectories, teacher inputs, skill source evidence and case-level outcome-informed debugging. Under the planned baseline-first sequence, method-level aggregate Base, Luna-Direct and ExpeL-adapted scores may be inspected before Ours is frozen and used as coarse benchmark targets; official case content, per-case outcomes, trajectories and judge rationales remain unavailable during Ours development. The collection is therefore absent from the skill-learning corpus but the evaluation is benchmark-aware, not sealed blind. Public availability precludes any claim about foundation-model pretraining exposure. The reviewed software can hash its bytes and the current adapter can parse records during executor initialization; hashing, record parsing, model-prompt exposure and human inspection are reported separately. ",
            "[PENDING PROTOCOL — before the first comparator run, freeze the shared evaluation/routing contract and record every official-set access; before Ours execution, record the known comparator aggregates and the frozen L8 hash]",
        ),
    )
    replace_prefix(
        document,
        "The confirmatory hierarchy is frozen",
        plain(
            "The primary inferential hierarchy is frozen before the first and only official Ours execution. Comparator aggregates may already be known, so the analysis is benchmark-aware rather than a fully outcome-blind preregistration: (i) the primary two-sided yield comparison; (ii) the stronger directional conjunction ΔF>0 and ΔQ<0 assessed by an intersection–union test, with both one-sided component nulls rejected, or Holm adjustment if separate component discoveries are claimed; (iii) a Benjamini–Hochberg family for prespecified quality endpoints that does not duplicate F; and (iv) Holm-adjusted yield contrasts across additional baselines. Failure to detect a quality difference is not equivalence. Non-inferiority requires a justified margin and a prespecified test."
        ),
    )
    replace_prefix(
        document,
        "All planned cells, failures and repairs",
        with_pending(
            "All planned cells, failures and repairs will be disclosed. Invalid execution is not silently removed. Report the complete matrix, paired valid-case analysis, a conservative failure sensitivity, raw case differences and leave-one-case-out influence. Design sensitivity or simulation-based power uses assumptions fixed before the official Ours run; any calculation informed by already revealed comparator aggregates is labelled benchmark-aware or descriptive. ",
            "[PENDING ANALYSIS — before Ours execution, freeze estimands, directional hypotheses, multiplicity families, failure/missing-data rules and non-inferiority margins, and record which comparator aggregates were already known]",
        ),
    )
    replace_prefix(
        document,
        "The primary estimate uses the library",
        with_pending(
            "The primary estimate uses the library and randomization stream designated before Ours first enters the official benchmark. If resources permit, independently trained replications assess learning variability; no replicate may be selected or revised using an Ours official result. Each replicate receives its own paired case-level effect. A secondary run-level analysis can use a hierarchical run×case bootstrap or an explicitly specified mixed model; it must not treat 30×R observations as mutually independent. Dialogue seeds 43 and 44 on six cases assess sampling sensitivity only, not learning replication. ",
            "[PLANNED EXPERIMENT — freeze the primary Ours run, replicate seeds, run-specific analysis and any hierarchical secondary analysis before the first Ours official execution]",
        ),
    )
    replace_prefix(
        document,
        "6.1. Main held-out comparison",
        plain("6.1. Main official benchmark comparison"),
    )
    replace_prefix(
        document,
        "LegalSkillEvolve provides an auditable protocol",
        with_pending(
            "LegalSkillEvolve provides an auditable protocol for accumulating external procedural memory from full simulated consultations while keeping model weights fixed. Outcome-typed contrast records, static admission gates and case-level paired evaluation make the intended attribution testable, provided external routing and the shared evaluation contract are frozen before comparator execution and Ours is frozen before its first and only official run. Comparator aggregate scores may be known during development; official case content and case-level outcomes are not used to revise Ours. ",
            "[PENDING RESULT — state only the empirical yield, fact, question and quality conclusions supported by the official benchmark evaluation]",
        ),
    )
    replace_prefix(
        document,
        "Reflexion uses verbal feedback",
        plain(
            "Reflexion retains verbal reflections for later attempts on the same task [4]. ExpeL is the closer cross-task comparator: it gathers success and failure trajectories on training tasks, maintains natural-language insights, and recalls both insights and similar successful experience for one-attempt evaluation on unseen tasks [5]. Agent Workflow Memory induces recurring workflows from trajectories [6]. TF-GRPO organizes group-relative feedback into an evolving experience representation without weight updates [7], while ACE studies structured context maintenance [8]. LegalSkillEvolve uses group-relative reward only to organize observational trajectory contrasts; it performs neither gradient-based policy optimization nor a counterfactual estimate of action effects."
        ),
    )
    replace_prefix(
        document,
        "Recent work also studies evolving skills.",
        plain(
            "Recent work also studies evolving skills. SAGE combines sequential skill accumulation with parameter-updating reinforcement learning [9], and SkillOpt refines strategy documents through bounded edits and validation-based selection [10]. LegalSkillEvolve instead directly admits source-bound natural-language procedures after static gates and evaluates the accumulated library. This combination is a design contribution, not a claim that skill memory or group-relative experience is new. The attribution design therefore includes a same-teacher static prior (Luna-Direct) and an independently learned ExpeL adaptation; a mechanism-agnostic reward-gap variant remains a separate internal ablation."
        ),
    )
    replace_prefix(
        document,
        "The primary question is whether",
        with_pending(
            "The primary question is whether the designated L8 skill library changes case-level mean new-fact-bearing-question rate relative to an empty library under an intervention-isolated route. Luna-Direct tests whether a fixed library authored by the same teacher from the task specification is sufficient. ExpeL-adapted tests the full method against an established cross-task experiential-memory design with its own training pool. LegalSkillEvolve (Ours) remains the library produced by outcome-typed contrasts, admission gates and accumulation; it is not replaced by direct teacher synthesis. SFT is outside the minimum main matrix. The evaluation contract and all three comparator protocols are frozen before the first official comparator run. Their method-level aggregate scores may then serve as coarse benchmark targets during Ours development, without inspection of official case content, case-level outcomes or trajectories. Ours is frozen before its first and only official execution; the design is therefore benchmark-aware rather than fully outcome-blind. ",
            "[PLANNED EXPERIMENT — construct and freeze Base, Luna-Direct, ExpeL-adapted and the shared evaluation contract before revealing the first comparator aggregate]",
        ),
    )
    replace_prefix(
        document,
        "Table 2 defines the comparison matrix",
        plain(
            "Table 2 defines the four-arm comparison needed for the present attribution claim. Only Base and Ours are implemented as main external arms in the reviewed executor. Luna-Direct and ExpeL-adapted require separate, artifact-frozen implementations under the shared evaluation contract. The former is a same-teacher static-prior control; the latter is a consultation-domain adaptation of a published method, not a relabelled reward-gap ablation. Blank result cells are prospective reporting structure, not evidence."
        ),
    )
    replace_prefix(
        document,
        "† Required planned extension",
        plain(
            "† Required planned controls that are not implemented as main external arms in the reviewed archive. Luna-Direct is a strong static prior, not an oracle: it is neither conditioned on external cases nor selected on external outcomes. ExpeL-adapted must construct an independent training-only experience pool and cannot receive Ours' selected contrasts, candidates or skill text."
        ),
    )
    replace_prefix(
        document,
        "All compared arms use the same cases",
        with_pending(
            "All arms use the same official cases, personas, dialogue seeds, client environment, StopGate and offline evaluation, conditional on a route that is independent of every learned library. Luna-Direct is generated once by the same Luna deployment from the frozen task description, policy capability contract, skill schema, domain taxonomy and safety constraints. It receives no official-case content, trajectories, labels, outcomes or aggregate effects and is never invoked per test case. Its capacity is fixed independently of the future L8 realization: at most 24 documents, 2,000 characters per document and 8,000 delivered characters per session. Candidate count, decoding, deterministic aggregation/selection, failure handling and the final artifact hash are frozen before its official evaluation. Because this arm has no trajectory witnesses, it is labelled teacher-authored rather than source-grounded. ",
            "[PLANNED EXPERIMENT — freeze the Luna-Direct prompt, candidate ledger, selection rule, capacity report and artifact hash before official evaluation]",
        ),
    )
    replace_prefix(
        document,
        "If SFT is included",
        with_pending(
            "ExpeL-adapted independently gathers at most four consultations on each of the same 128 training cases under the shared Qwen policy and environment. Because this consultation task has no native binary success signal, the ranked-feedback adaptation designates a healthy within-case maximum-reward trajectory as positive and a minimum-reward trajectory as negative only when a prespecified reward gap and hard-failure rule are satisfied. Its Luna-based insight updater retains the defining ADD, EDIT, UPVOTE and DOWNVOTE operations over within-task positive–negative pairs and cross-task positive sets. At official evaluation, the frozen insight bank and top-k training-only positive trajectories retrieved from the public opening are delivered to the policy; official hidden fields, outcomes and Ours-derived routing are unavailable. Retrieval model, k, truncation, memory capacity, teacher budget and all deviations from the original environments are reported. SFT is considered only as a supplementary extension and is not represented by an empty main-table column. ",
            "[PLANNED EXPERIMENT — implement and fidelity-audit ExpeL-adapted using an independent experience pool before official evaluation]",
        ),
    )
    replace_prefix(
        document,
        "The main treatment-attribution ablation",
        plain(
            "The main internal mechanism ablation is a fresh learning run that removes outcome-typed mechanism filtering while preserving reward-gap trajectory evidence, case order, model calls and teacher-attempt budget. It is not labelled ExpeL because it lacks ExpeL's independent experience pool, insight-maintenance operations and successful-trajectory retrieval. Further fresh runs can replace the cumulative bank with current-block evidence only or remove the additional-question reward penalty. Each ablation learns its own library. Comparator aggregate scores may define a coarse engineering target, but the primary library is frozen before its first official execution and is never revised using its own official result."
        ),
    )
    replace_prefix(
        document,
        "The active run identifier is",
        with_pending(
            "The previously reviewed runtime01 snapshot was superseded by a user-reported restart after contrast/planner alignment corrections. This manuscript does not treat the restart as evidence that the correction or training is complete. The nominal Ours budget remains 512 main consultations, up to 112 non-learning shadows and up to 48 teacher attempts, before retries and qualification; ExpeL-adapted adds up to 512 independent training consultations. ",
            "[PENDING METADATA — insert the designated restarted run identifier, final manifest/hash chain, environment, failures, final L8 hash and actual method-specific costs only after completion]",
        ),
    )
    replace_prefix(
        document,
        "Table 3. Planned main results",
        plain(
            "Table 3. Planned four-arm results on 30 official Chinese benchmark cases absent from the skill-learning corpus and crossed with four personas. Entries are case-level macro means; arrows show favorable directions. † Required planned control. The primary and additional paired effects are reported in Table 4."
        ),
    )
    replace_prefix(
        document,
        "Every pending cell is unmeasured.",
        plain(
            "Every pending cell is unmeasured. No rank, significance marker or imputed value is assigned before results exist. The reviewed executor currently implements only Base and Ours; † controls require artifact-frozen implementation under the same evaluation contract. Lower question counts are favorable only when interpreted with information and quality outcomes. Ours-versus-Base, Ours-versus-Luna-Direct and Ours-versus-ExpeL-adapted paired differences, 95% case intervals and complete denominators appear in the companion effect table."
        ),
    )
    replace_prefix(
        document,
        "Table 4. Planned paired case-level estimates",
        plain(
            "Table 4. Planned paired case-level estimates. Ours−Base is the sole primary yield comparison; its fact–question conjunction uses the frozen intersection–union rule. Ours−Luna-Direct and Ours−ExpeL-adapted yield contrasts form a separately Holm-adjusted family."
        ),
    )
    replace_prefix(
        document,
        "[PENDING RESULT — complete Tables 3–4",
        [(
            "[PENDING RESULT — complete Tables 3–4; report Ours−Base ΔY/ΔF/ΔQ, Ours−Luna-Direct ΔY, Ours−ExpeL-adapted ΔY, 95% case intervals, raw case differences, prespecified raw/adjusted p-values, failure denominators and the directional fact–question decision]",
            True,
        )],
    )
    replace_prefix(
        document,
        "LegalSkillEvolve treats skill documents",
        plain(
            "LegalSkillEvolve treats skill documents as source-bound procedural hypotheses available to a frozen consultation policy. The four-arm design separates three explanations: Ours−Base estimates the overall conditional effect of the evolved artifact; Ours−Luna-Direct estimates trajectory-grounded evolution beyond the same teacher's task prior; and Ours−ExpeL-adapted compares outcome-typed, source-bound evolution with established experiential memory. If Ours and Luna-Direct perform similarly while both exceed Base, the evidence supports teacher-authored procedural prompting but not an incremental benefit of evolution. None of these contrasts identifies an individual skill's causal effect."
        ),
    )

    replace_prefix(
        document,
        "[4] Shinn",
        plain(
            "[4] Shinn N, Cassano F, Gopinath A, Narasimhan K, Yao S. Reflexion: Language agents with verbal reinforcement learning. Advances in Neural Information Processing Systems 36 (2023). doi:10.52202/075280-0377."
        ),
    )
    replace_prefix(
        document,
        "[5] Zhao",
        plain(
            "[5] Zhao A, Huang D, Xu Q, Lin M, Liu YJ, Huang G. ExpeL: LLM Agents Are Experiential Learners. Proceedings of the AAAI Conference on Artificial Intelligence 38(17), 19632–19642 (2024). doi:10.1609/aaai.v38i17.29936."
        ),
    )
    replace_prefix(
        document,
        "[6] Wang",
        plain(
            "[6] Wang ZZ, Mao J, Fried D, Neubig G. Agent Workflow Memory. Proceedings of the 42nd International Conference on Machine Learning, PMLR 267, 63897–63911 (2025)."
        ),
    )

    design_table = find_table(document, "Partition or stage")
    learning_row = find_row(design_table, "Main learning rollout")
    expel_row = learning_row.cloneNode(deep=True)
    set_row(
        expel_row,
        [
            ("ExpeL-adapted experience collection", False),
            ("Same 128 cases; up to four independent consultations/case", False),
            ("At most 512 training-only consultations; separate experience pool", False),
        ],
    )
    insert_row_after(learning_row, expel_row)
    prequential_row = find_row(design_table, "Prequential diagnostic")
    set_row(
        prequential_row,
        [
            ("Prequential diagnostic", False),
            ("All 16 sample-0 cells/block", False),
            ("At most 112 extra empty-library consultations after block 1", False),
        ],
    )
    set_cell(
        row_cells(find_row(design_table, "Official external test"))[2],
        "120 consultations/method; 480 for the frozen four-arm main matrix",
    )
    set_cell(
        row_cells(find_row(design_table, "Dialogue-seed sensitivity"))[2],
        "48 additional consultations/method; 192 if applied to all four arms",
    )

    method_table = find_table(document, "Method")
    luna_row = find_row(method_table, "Static†")
    set_row(
        luna_row,
        [
            ("Luna-Direct†", False),
            ("Frozen Qwen3-8B; fixed same-teacher library generated from task specification only", False),
            ("Controls teacher prior, procedural context and prompt capacity", False),
        ],
    )
    expel_method_row = find_row(method_table, "Reward-gap memory†")
    set_row(
        expel_method_row,
        [
            ("ExpeL-adapted†", False),
            ("Frozen Qwen3-8B; independent training experience pool, insight bank and successful-trajectory retrieval", False),
            ("Published cross-task experiential-memory comparator adapted to consultation", False),
        ],
    )
    sft_row = find_row(method_table, "SFT‡")
    method_table.removeChild(sft_row)
    ours_row = find_row(method_table, "Ours")
    set_row(
        ours_row,
        [
            ("Ours", False),
            ("Frozen Qwen3-8B; outcome-typed contrasts, static admission and direct L0→L8 accumulation", False),
            ("LegalSkillEvolve treatment arm produced by the complete evolution pipeline", False),
        ],
    )

    results_table = find_table(document, "Metric")
    expected_header = [
        "Metric",
        "Base",
        "Static†",
        "Reward-gap memory†",
        "SFT‡",
        "Ours",
    ]
    if table_header(results_table) != expected_header:
        raise RuntimeError(f"Unexpected main-result header: {table_header(results_table)!r}")
    remove_table_column(results_table, 4)
    result_header_cells = row_cells(table_rows(results_table)[0])
    set_cell(result_header_cells[2], "Luna-Direct†")
    set_cell(result_header_cells[3], "ExpeL-adapted†")

    effect_table = find_table(document, "Endpoint")
    effect_rows = table_rows(effect_table)
    set_cell(row_cells(effect_rows[0])[0], "Contrast and endpoint")
    set_cell(row_cells(effect_rows[1])[0], "Ours − Base: Yield ΔY")
    set_cell(row_cells(effect_rows[1])[4], "Primary two-sided test")
    set_cell(row_cells(effect_rows[2])[0], "Ours − Base: New facts ΔF")
    set_cell(row_cells(effect_rows[2])[4], "Directional IUT component")
    set_cell(row_cells(effect_rows[3])[0], "Ours − Base: Questions ΔQ")
    set_cell(row_cells(effect_rows[3])[4], "Directional IUT component")
    direct_effect = effect_rows[1].cloneNode(deep=True)
    set_row(
        direct_effect,
        [
            ("Ours − Luna-Direct: Yield ΔY", False),
            ("[PENDING RESULT]", True),
            ("[PENDING RESULT]", True),
            ("[PENDING RESULT]", True),
            ("Holm family: evolution beyond same-teacher prior", False),
        ],
    )
    insert_row_after(effect_rows[3], direct_effect)
    expel_effect = effect_rows[1].cloneNode(deep=True)
    set_row(
        expel_effect,
        [
            ("Ours − ExpeL-adapted: Yield ΔY", False),
            ("[PENDING RESULT]", True),
            ("[PENDING RESULT]", True),
            ("[PENDING RESULT]", True),
            ("Holm family: comparison with experiential memory", False),
        ],
    )
    insert_row_after(direct_effect, expel_effect)

    highlight_pending_runs(document)
    return document.toxml(encoding="UTF-8")


def update_core_properties(xml_bytes: bytes) -> bytes:
    document = minidom.parseString(xml_bytes)
    subjects = document.getElementsByTagName("dc:subject")
    if subjects:
        node = subjects[0]
        while node.firstChild:
            node.removeChild(node.firstChild)
        node.appendChild(
            document.createTextNode(
                "Four-arm protocol manuscript: Base, Luna-Direct, ExpeL-adapted and LegalSkillEvolve; empirical results pending"
            )
        )
    modified = document.getElementsByTagName("dcterms:modified")
    if modified:
        node = modified[0]
        while node.firstChild:
            node.removeChild(node.firstChild)
        node.appendChild(document.createTextNode(MODIFIED_AT))
    return document.toxml(encoding="UTF-8")


def copy_info(info: ZipInfo) -> ZipInfo:
    clone = ZipInfo(info.filename, date_time=info.date_time)
    clone.compress_type = ZIP_DEFLATED
    clone.comment = info.comment
    clone.extra = info.extra
    clone.create_system = info.create_system
    clone.external_attr = info.external_attr
    return clone


def build(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve():
        raise ValueError("Source and destination must differ")
    if not source.is_file():
        raise FileNotFoundError(source)
    if not FIGURE3_ASSET.is_file():
        raise FileNotFoundError(FIGURE3_ASSET)

    figure3_bytes = FIGURE3_ASSET.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(source) as source_zip:
        document_xml = revise_document(source_zip.read("word/document.xml"))
        core_xml = update_core_properties(source_zip.read("docProps/core.xml"))
        with NamedTemporaryFile(
            prefix=destination.name + ".",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary_file:
            temporary = Path(temporary_file.name)
        try:
            with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as output_zip:
                for info in source_zip.infolist():
                    payload = source_zip.read(info.filename)
                    if info.filename == "word/document.xml":
                        payload = document_xml
                    elif info.filename == "docProps/core.xml":
                        payload = core_xml
                    elif info.filename == FIGURE3_MEDIA_PATH:
                        payload = figure3_bytes
                    output_zip.writestr(copy_info(info), payload)
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    build(args.source, args.destination)


if __name__ == "__main__":
    main()
