#!/usr/bin/env python3
# ruff: noqa: E501
"""Create an evidence-constrained revision of the LegalSkillEvolve DOCX draft.

The source document is never overwritten.  The transformation works directly on
OOXML so equations, styles, drawings and the other embedded media remain intact.
Unfinished empirical or administrative content is retained as an explicit,
yellow-shaded PENDING marker.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from xml.dom import Node, minidom
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

PENDING_FILL = "FFF2CC"
REVISION_MODIFIED_AT = "2026-09-11T06:00:00Z"
FIGURE3_MEDIA_PATH = "word/media/rId39.png"
FIGURE3_ASSET = (
    Path(__file__).resolve().parents[1] / "figures" / "Figure3_current_protocol.png"
)
HYPERLINK_RELATIONSHIP_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
)
REFERENCE_ENTRIES = [
    (
        "rIdNature18",
        "[18] Yuan W, Song K, Jiang Z, et al. LeCoDe: A Benchmark Dataset for Interactive Legal Consultation Dialogue Evaluation. Proceedings of ACL 2026;36019–36048.",
        "https://doi.org/10.18653/v1/2026.acl-long.1667",
    ),
    (
        "rIdNature19",
        "[19] Gan R, Feng D, Zhang C, et al. UCL-Bench: A Chinese User-Centric Legal Benchmark for Large Language Models. Findings of NAACL 2025;7960–8003.",
        "https://doi.org/10.18653/v1/2025.findings-naacl.444",
    ),
    (
        "rIdNature20",
        "[20] Yue S, Huang T, Jia Z, et al. Multi-Agent Simulator Drives Language Models for Legal Intensive Interaction. Findings of NAACL 2025;6552–6585.",
        "https://doi.org/10.18653/v1/2025.findings-naacl.365",
    ),
    (
        "rIdNature21",
        "[21] Li H, Chen J, Yang J, et al. LegalAgentBench: Evaluating LLM Agents in Legal Domain. Proceedings of ACL 2025;2322–2344.",
        "https://doi.org/10.18653/v1/2025.acl-long.116",
    ),
    (
        "rIdNature22",
        "[22] Shi Y, Liu H, Hu Y, et al. PLAWBENCH: A Rubric-Based Benchmark for Evaluating LLMs in Real-World Legal Practice. Proceedings of ACL 2026;10067–10116.",
        "https://doi.org/10.18653/v1/2026.acl-long.458",
    ),
    (
        "rIdNature23",
        "[23] Dou Y, Galley M, Peng B, et al. SimulatorArena: Are User Simulators Reliable Proxies for Multi-Turn Evaluation of AI Assistants? Proceedings of EMNLP 2025;35212–35290.",
        "https://doi.org/10.18653/v1/2025.emnlp-main.1786",
    ),
]


def paragraph_text(paragraph: Node) -> str:
    return "".join(
        node.firstChild.data if node.firstChild else ""
        for node in paragraph.getElementsByTagName("w:t")
    )


def direct_children(node: Node, tag_name: str) -> list[Node]:
    return [
        child
        for child in node.childNodes
        if child.nodeType == Node.ELEMENT_NODE and child.tagName == tag_name
    ]


def first_run_properties(paragraph: Node) -> Node | None:
    for run in paragraph.getElementsByTagName("w:r"):
        properties = direct_children(run, "w:rPr")
        if properties:
            return properties[0]
    return None


def remove_run_shading(properties: Node) -> None:
    for child in list(properties.childNodes):
        if child.nodeType == Node.ELEMENT_NODE and child.tagName in {
            "w:shd",
            "w:highlight",
        }:
            properties.removeChild(child)


def shade_run(run: Node) -> None:
    document = run.ownerDocument
    properties = direct_children(run, "w:rPr")
    if properties:
        r_pr = properties[0]
    else:
        r_pr = document.createElement("w:rPr")
        run.insertBefore(r_pr, run.firstChild)
    remove_run_shading(r_pr)
    shading = document.createElement("w:shd")
    shading.setAttribute("w:val", "clear")
    shading.setAttribute("w:color", "auto")
    shading.setAttribute("w:fill", PENDING_FILL)
    r_pr.appendChild(shading)


def make_run(
    document: minidom.Document,
    text: str,
    template_properties: Node | None,
    pending: bool,
) -> Node:
    run = document.createElement("w:r")
    if template_properties is not None:
        properties = template_properties.cloneNode(deep=True)
        remove_run_shading(properties)
        run.appendChild(properties)
    if pending:
        shade_run(run)
    text_node = document.createElement("w:t")
    if text.startswith(" ") or text.endswith(" "):
        text_node.setAttribute("xml:space", "preserve")
    text_node.appendChild(document.createTextNode(text))
    run.appendChild(text_node)
    return run


def replace_paragraph(paragraph: Node, segments: list[tuple[str, bool]]) -> None:
    """Replace paragraph content while retaining its paragraph-level formatting."""

    document = paragraph.ownerDocument
    template_properties = first_run_properties(paragraph)
    for child in list(paragraph.childNodes):
        if not (
            child.nodeType == Node.ELEMENT_NODE and child.tagName == "w:pPr"
        ):
            paragraph.removeChild(child)
    for text, pending in segments:
        paragraph.appendChild(
            make_run(document, text, template_properties, pending=pending)
        )


def add_hyperlink_style(run: Node) -> None:
    document = run.ownerDocument
    properties = direct_children(run, "w:rPr")
    if properties:
        r_pr = properties[0]
    else:
        r_pr = document.createElement("w:rPr")
        run.insertBefore(r_pr, run.firstChild)
    for child in list(r_pr.childNodes):
        if child.nodeType == Node.ELEMENT_NODE and child.tagName in {"w:color", "w:u"}:
            r_pr.removeChild(child)
    color = document.createElement("w:color")
    color.setAttribute("w:val", "0563C1")
    underline = document.createElement("w:u")
    underline.setAttribute("w:val", "single")
    r_pr.appendChild(color)
    r_pr.appendChild(underline)


def replace_reference_paragraph(
    paragraph: Node,
    citation_text: str,
    url: str,
    relationship_id: str,
) -> None:
    document = paragraph.ownerDocument
    template_properties = first_run_properties(paragraph)
    for child in list(paragraph.childNodes):
        if not (
            child.nodeType == Node.ELEMENT_NODE and child.tagName == "w:pPr"
        ):
            paragraph.removeChild(child)
    paragraph.appendChild(
        make_run(document, citation_text + " ", template_properties, pending=False)
    )
    hyperlink = document.createElement("w:hyperlink")
    hyperlink.setAttribute("r:id", relationship_id)
    hyperlink.setAttribute("w:history", "1")
    linked_run = make_run(document, url, template_properties, pending=False)
    add_hyperlink_style(linked_run)
    hyperlink.appendChild(linked_run)
    paragraph.appendChild(hyperlink)
    paragraph.appendChild(make_run(document, ".", template_properties, pending=False))


def plain(text: str) -> list[tuple[str, bool]]:
    return [(text, False)]


def with_pending(prefix: str, marker: str) -> list[tuple[str, bool]]:
    return [(prefix, False), (marker, True)]


def standardize_remaining_placeholders(document: minidom.Document) -> None:
    """Normalize legacy placeholders without inventing missing content."""

    for text_node in document.getElementsByTagName("w:t"):
        if not text_node.firstChild:
            continue
        old = text_node.firstChild.data
        new = old.replace("____", "[PENDING RESULT]")
        new = re.sub(
            r"\[TBD-[^\]]+\]",
            "[PENDING ITEM — complete and verify before submission]",
            new,
        )
        if new == old:
            continue
        text_node.firstChild.data = new
        ancestor = text_node.parentNode
        while ancestor is not None and getattr(ancestor, "tagName", "") != "w:r":
            ancestor = ancestor.parentNode
        if ancestor is not None:
            shade_run(ancestor)


def update_core_properties(xml_bytes: bytes) -> bytes:
    document = minidom.parseString(xml_bytes)
    metadata = {
        "dc:title": "LegalSkillEvolve: Evolving Skill Memory for Fact Elicitation in Simulated Legal Consultation",
        "dc:subject": "Evidence-constrained working manuscript; empirical results pending",
        "cp:keywords": "legal consultation; skill memory; fact elicitation; simulated interaction",
    }
    for tag_name, value in metadata.items():
        nodes = document.getElementsByTagName(tag_name)
        if not nodes:
            continue
        while nodes[0].firstChild:
            nodes[0].removeChild(nodes[0].firstChild)
        nodes[0].appendChild(document.createTextNode(value))
    modified = document.getElementsByTagName("dcterms:modified")
    if modified:
        while modified[0].firstChild:
            modified[0].removeChild(modified[0].firstChild)
        modified[0].appendChild(document.createTextNode(REVISION_MODIFIED_AT))
    revision = document.getElementsByTagName("cp:revision")
    if revision:
        try:
            value = int(paragraph_text(revision[0])) + 1
        except ValueError:
            value = 2
        while revision[0].firstChild:
            revision[0].removeChild(revision[0].firstChild)
        revision[0].appendChild(document.createTextNode(str(value)))
    return document.toxml(encoding="UTF-8")


def revise_document(xml_bytes: bytes) -> bytes:
    document = minidom.parseString(xml_bytes)
    paragraphs = list(document.getElementsByTagName("w:p"))
    if len(paragraphs) < 310:
        raise RuntimeError(f"Unexpected document structure: {len(paragraphs)} paragraphs")
    if not paragraph_text(paragraphs[0]).startswith("LegalSkillEvolve:"):
        raise RuntimeError("Unexpected source title; refusing an index-based rewrite")

    replacements: dict[int, list[tuple[str, bool]]] = {
        0: plain(
            "LegalSkillEvolve: Evolving Skill Memory for Fact Elicitation in Simulated Legal Consultation"
        ),
        1: [("[PENDING METADATA — authors, affiliations and corresponding author]", True)],
        2: plain(
            "Working manuscript · Protocol synchronized to the reviewed implementation on 11 September 2026 · Main training in progress; empirical results pending"
        ),
        4: with_pending(
            "Effective legal consultation depends on eliciting material information without imposing unnecessary questioning. We introduce LegalSkillEvolve, a framework that accumulates reusable natural-language consultation skills while keeping the underlying language models frozen. In the reviewed implementation, an opening-only planner is skill-blind; a fixed session bundle is supplied only to the consultation policy, and a deterministic StopGate can redirect premature termination or actions disallowed by encoded structural and stopping rules. Across eight sequential blocks, four full trajectories per training case provide reward-separated, outcome-typed contrasts for fact elicitation, evidence-gap recognition and efficient stopping. A teacher abstracts cumulative evidence into candidate skill documents, which enter the working library only after static format, provenance, information-boundary, duplication and capacity checks. These gates establish admissibility, not legal correctness or effectiveness. The planned final evaluation crosses 30 adaptation-held-out Chinese DLawBench cases with four client personas. The primary estimand is the case-level mean of session new-fact-bearing-question rates, accompanied by separate fact and question outcomes, quality metrics and failure counts. ",
            "[PENDING RESULT — insert the designated L8-versus-Base effect, 95% case-level confidence interval and the separately supported fact and question conclusions]",
        ),
        8: plain(
            "Recent legal benchmarks evaluate doctrinal reasoning, long-context synthesis, multi-turn consultation and agentic workflows [1–3,18–22]. DLawBench is especially relevant because it represents consultation as an interaction with clients who differ in disclosure behavior [3]. This setting raises a process question beyond final-answer quality: can an agent learn reusable interviewing procedures that increase information obtained per question? Higher final quality achieved through substantially more questioning is not equivalent to more efficient elicitation, while a short dialogue that omits material facts is not successful."
        ),
        9: plain(
            "External memory can adapt behavior without changing model weights. Verbal reflection, accumulated experience, workflow memory and evolving context have all been used to guide later agent actions [4–8]. For legal consultation, however, reward differences alone do not reveal whether a better trajectory asked a more informative question, recognized an external evidence requirement or stopped at an appropriate point. LegalSkillEvolve therefore records outcome-typed trajectory contrasts as evidence for procedural hypotheses; the final library, rather than any admitted document, is the treatment evaluated on held-out cases."
        ),
        10: plain(
            "The system separates online consultation from offline evidence accumulation. The opening-only planner constructs an initial investigation agenda without skill context. During dialogue, a policy receives a fixed session bundle selected from the current library; a shared memorandum renderer sees only the visible record. Between blocks, a teacher proposes compact procedures from cumulative training evidence. Static trust gates govern admission, while prequential diagnostics and the final frozen-library comparison evaluate the consequences of accumulation."
        ),
        11: plain(
            "The study makes three bounded contributions: an implementation-auditable skill-memory framework for simulated legal consultation; outcome-typed evidence records linking full-trajectory variation to reusable procedural hypotheses; and an evaluation design that treats elicitation yield, absolute facts, question burden, quality and failures as distinct outcomes. The empirical contribution remains prospective until the frozen experiments are complete."
        ),
        14: plain(
            "LegalBench and LawBench evaluate broad legal capabilities [1,2], while DLawBench models multi-turn consultation using finite client beliefs, reference facts and evaluation rubrics [3]. LeCoDe, UCL-Bench, MILE, LegalAgentBench and PLawBench further illustrate the move toward realistic legal documents, interactive environments and agentic legal tasks [18–22]. We evaluate a modified local consultation system on the public 30-case Chinese DLawBench subset; this is not a reproduction of the benchmark's full simulator or scoring configuration. The project-level holdout claim is limited to exclusion from adaptation and tuning, not absence from foundation-model pretraining."
        ),
        16: plain(
            "Reflexion uses verbal feedback to improve later attempts [4], ExpeL extracts reusable experience [5], and Agent Workflow Memory induces recurring workflows [6]. TF-GRPO organizes group-relative feedback into an evolving experience representation without weight updates [7], while ACE studies the maintenance of structured agent context [8]. LegalSkillEvolve uses group-relative reward only to organize observational trajectory contrasts; it performs neither gradient-based policy optimization nor a counterfactual estimate of action effects."
        ),
        17: plain(
            "Recent work also studies evolving skills. SAGE combines sequential skill accumulation with parameter-updating reinforcement learning [9], and SkillOpt refines strategy documents through bounded edits and validation-based selection [10]. LegalSkillEvolve instead directly admits source-bound natural-language procedures after static gates and evaluates the accumulated library. This combination is a design contribution, not a claim that skill memory or group-relative experience is new; a static prompt control and a simpler adaptive experience-memory baseline are therefore necessary for the present attribution claim."
        ),
        19: plain(
            "Consultation efficiency requires both a numerator and a denominator. We distinguish first-disclosed client fact identifiers from opening content and repeated disclosures, and report question counts so that a favorable ratio cannot conceal reduced information recovery. Model-based assessment remains useful for semantic inquiry and memorandum quality, but agreement between language-model judges is not independent legal validation [11]. Event reconstruction, controlled perturbations, a second model, and domain-expert review answer different validity questions. SimulatorArena similarly underscores that environment validity is part of agent evaluation rather than a background assumption [23]. Statistical inference therefore uses cases as the independent units [12,13]."
        ),
        25: plain(
            "Writing completed sessions with index i, an immediate finalization has Y_i=0. Opening repetitions and repeated disclosures do not increase F_i. On the normal contract path—at most one fact identifier per response, disclosure triggered by a question, and exceptional fallbacks reported separately—Y_i equals the fraction of question turns that produce a new fact and is bounded by one. It does not measure the number of facts a human might bundle into an open-ended answer. The primary aggregate is the mean of session ratios after averaging personas within cases; the pooled ratio ΣF/ΣQ is a sensitivity analysis, not the same estimand. Client beliefs are statements, not automatically legal or factual truth."
        ),
        26: plain(
            "The primary confirmatory claim concerns yield. The stronger phrase “more facts with fewer questions” is used only if the directional evidence jointly supports ΔF>0 and ΔQ<0. Equality of quality outcomes is not assumed from a non-significant difference; preservation claims require a prespecified non-inferiority design or appropriately narrow descriptive wording."
        ),
        29: plain(
            "Figure 1 reflects the reviewed implementation. The online process uses a frozen Qwen3-8B snapshot for an opening-only, skill-blind investigation plan, policy decisions and memorandum rendering [14]. Active skills are supplied only to the policy. The policy proposes an action, after which a deterministic StopGate can execute it, redirect it to a clarification or information request, or invoke a factual fallback. The client router and offline judge use frozen gpt-oss-20b weights [15]. Offline learning occurs only between experience blocks."
        ),
        31: plain(
            "Figure 1. Current LegalSkillEvolve protocol. (a) The planner receives the public opening but no skill text and produces one shared agenda per K=4 group; the policy receives the fixed session bundle and retains four independent action-sampling streams. Public-opening routing selects general skills and at most one domain bundle, and the StopGate can alter the executed action. (b) Four trajectories per case provide outcome-typed observational contrasts. At each block, the teacher may make up to six attempts and stops after three unique proposal fingerprints; qualified documents enter the next library. (c) Full-block sample-0 current-versus-empty shadows measure the input library and guide only the next teacher direction, while the frozen L8 library is designated for external evaluation."
        ),
        33: plain(
            "The offline judge uses a stateless prompt but the same frozen gpt-oss-20b weights as client routing. Prompt, input and cache isolation prevents direct state sharing; shared weights nevertheless remain a potential common source of model bias. The teacher receives training evidence only. Neither an additional model judge nor these architectural separations constitute legal-expert validation."
        ),
        35: plain(
            "A skill is a structured natural-language document with scope, recognition cues, a procedure, question guidance, expected effects, contraindications and failure modes. These fields advise the policy; they are not compiled into executable triggers. System-owned evidence records separately retain source cases, trajectories and reference labels. Independently of skills, the StopGate may redirect a proposed action, so original and executed actions must both be logged and reported."
        ),
        36: plain(
            "At session start, the system selects and deterministically orders active general skills and, when routed, at most one domain-scoped set. The rendered bundle remains fixed for the consultation and is supplied to the policy only—not to the opening planner or memorandum renderer. Each policy-facing document is limited to 2,000 characters and each applicable bundle to 8,000 characters including its wrapper. These are character limits rather than tokenizer-derived budgets."
        ),
        37: with_pending(
            "For the reviewed external path, a Qwen3 router sees the public opening together with the active skill catalogue and predicts a general-plus-domain route. That prediction is passed to both arms and stored in policy-visible state. Consequently, an empty skill bundle alone does not guarantee that Base and Ours differ only by skill text: the learned library can affect the shared route. ",
            "[PENDING PROTOCOL — before any confirmatory external execution, freeze and verify a library-independent route (for example, public metadata fixed identically across arms or a general-only route); treat results produced before this freeze as exploratory]",
        ),
        39: plain(
            "The 128-case training corpus is partitioned into eight disjoint blocks B_1,…,B_8 of 16 cases. The initial library L_0 is empty. Within block b, each case is run under the same block-start library L_{b−1} and cooperative persona. Four sampling streams produce independent complete trajectories. Their opening plans are independently sampled by the skill-blind planner, so trajectories need not share a plan or intermediate state."
        ),
        41: plain(
            "Figure 2. From full-trajectory variation to reusable skill hypotheses. (a) Four consultations share the opening, persona and block-start library but may differ in plans and visible histories. (b) A positive reward difference is paired with an observable outcome type: fact elicitation, evidence-gap recognition or efficient stopping. Stopping additionally requires equality of the corresponding identifier sets. (c) Immutable source witnesses remain separate from deployed advice. These criteria create auditable observational hypotheses; they do not identify an isolated causal effect of an action or skill."
        ),
        47: plain(
            "Here r̄ is the within-group mean reward and σ_r is its population standard deviation. This is GRPO-inspired relative-feedback bookkeeping, not gradient optimization. Mechanism selection additionally requires a positive reward gap between eligible trajectories. A group without informative variation cannot generate a positive contrast."
        ),
        54: plain(
            "The selector retains at most one pair per mechanism per case group. It records the first learnable action difference, each trajectory's own visible state and source-bound outcome evidence. The two witnesses are not required to share an identical plan, history or pre-action state. A source witness therefore demonstrates compatibility with the selection rule and provenance, not entailment, counterfactual sufficiency or causal effect."
        ),
        58: plain(
            "At each block end, the system can attempt up to six previously unattempted evidence fingerprints and stops once three unique proposal fingerprints have been obtained. Selection favors mechanism and domain coverage. A growing cluster may be reconsidered when its source-group fingerprint changes. Teacher context is bounded to 15 source groups, at most two per source case, while preserving the cross-domain rule for a general proposal."
        ),
        59: plain(
            "The teacher, configured through the mutable deployment alias gpt-5.6-luna, emits a candidate document or no-operation response. Across eight blocks, the configured hard ceiling is 48 teacher attempts, while at most three unique proposal fingerprints per block can proceed toward admission (24 across the run). No-operation responses, repeated fingerprints, hard-check rejection and capacity exclusion can reduce the number of admitted skills. Attempts, unique proposals and admitted skills are distinct counts."
        ),
        61: plain(
            "Each proposed document undergoes static checks for schema and procedural content, source-witness consistency, prohibited hidden information, bounded legal and operational language, duplication and joint prompt capacity. These checks verify conformity to the encoded rules. They do not establish legal correctness, safety in real consultations, effectiveness on source cases or an individual treatment effect."
        ),
        66: plain(
            "For each experience block, all 16 case identifiers are selected in advance without reference to outcomes. Their sample-0 trajectories under the current library are paired with empty-library shadow consultations using the same case, persona and sampling stream. The current-library observation is neither the best of four trajectories nor their average. If the current library is empty, the identity shortcut yields a zero comparison without generating duplicate shadows."
        ),
        68: plain(
            "Figure 3. Direct accumulation and library-level evaluation. Each block runs under L_{b−1} and can add qualified candidates to L_b. Diamonds denote report-only inspections. Prequential diagnostics compare all 16 predeclared sample-0 trajectories from each block with matched empty-library shadows; the block-1 identity shortcut avoids duplicate runs. These are development diagnostics for L0–L7. The final confirmatory comparison uses the designated frozen L8 library, including any additions made after block 8."
        ),
        69: plain(
            "Prequential observations are collected before learning from their own block, but the cases later become training evidence and the case set changes across blocks. They are therefore diagnostic, not a repeated fixed-test learning curve or a confirmatory trend test. Current-library observations reuse learning-temperature trajectories, whereas the final paired experiment uses the frozen evaluation configuration. Empty-library shadows do not enter teacher selection or admission."
        ),
        72: plain(
            "The primary question is whether the designated L8 skill library changes case-level mean new-fact-bearing-question rate relative to an empty library under an intervention-isolated route. A static generic procedure tests the value of learned rather than merely present context. A simpler reward-gap memory tests whether mechanism typing adds value beyond adaptive trajectory-derived advice. SFT is an optional, resource-intensive contrast rather than a prerequisite for the bounded external-memory claim. All confirmatory methods, prompts, diagnostics, judge models and analysis families must be frozen before any official outcome is inspected."
        ),
        73: plain(
            "Table 1. Data and nominal execution units for the reviewed protocol; qualification, retries, added baselines and independent reviews are reported separately."
        ),
        88: plain(
            "120 consultations/method; 240 for the current Base/Ours executor and 480 for the planned four-method matrix"
        ),
        91: plain(
            "48 additional consultations/method; 96 for two arms or 192 for four methods"
        ),
        93: with_pending(
            "The 30-case Chinese collection is excluded from training, teacher input, skill selection and outcome-informed tuning. Public availability precludes any claim about foundation-model pretraining exposure. The reviewed software can hash its bytes and the current adapter can parse records during executor initialization; hashing, record parsing, model-prompt exposure and human inspection are therefore reported as separate access levels. The defensible present claim is “held out from project adaptation,” not “never accessed” or “sealed blind.” ",
            "[PENDING PROTOCOL — before confirmatory evaluation, freeze the complete analysis and routing contract, record a parent-manifest hash, and document every official-set byte access, record parse, model exposure and human exposure]",
        ),
        95: plain(
            "Table 2 defines the comparison matrix needed for the current attribution claim. Only Base and Ours are implemented as main external arms in the reviewed executor. Static and reward-gap memory should be implemented and frozen before confirmatory evaluation. SFT is optional and should be reported outside the minimum matrix if compute or engineering validation is insufficient. Blank table cells are prospective reporting structure, not evidence."
        ),
        100: plain("Base"),
        101: plain("Frozen Qwen3-8B; empty policy skill bundle"),
        102: plain("No-memory control after library-independent route isolation"),
        103: plain("Static†"),
        104: plain("Frozen model; one development-frozen generic procedure"),
        105: plain("Controls for procedural context and prompt overhead"),
        106: plain("Reward-gap memory†"),
        107: plain(
            "Frozen model; adaptive trajectory-derived advice without outcome-typed mechanism filtering"
        ),
        108: plain("Tests the incremental value of mechanism-specific evidence selection"),
        109: plain("SFT‡"),
        110: plain("Training-only supervised adapter on visible-state demonstrations"),
        111: plain("Optional parameter-adaptation comparator with separately reported compute"),
        112: plain("Ours"),
        113: plain("Frozen model; outcome-typed contrasts and direct skill accumulation"),
        114: plain("Current LegalSkillEvolve treatment arm"),
        115: plain(
            "† Required planned extension for the current attribution claim; not implemented as a main external arm in the reviewed archive. ‡ Optional extension. Every adaptive baseline must generate its own training-only memory or checkpoint and must not receive Ours' selected evidence."
        ),
        116: plain(
            "All compared arms use the same cases, personas, dialogue seeds, client environment, StopGate and offline evaluation. Pairwise equality is conditional on freezing a route that does not depend on the learned library. Static uses the same document interface and should report realized characters and model-token counts; a length-matched inert or generic control can diagnose context overhead. Reward-gap memory matches the training cases, four-trajectory budget and teacher-attempt ceiling while omitting outcome-type filtering. It must construct its own adaptive history."
        ),
        117: with_pending(
            "If SFT is included, demonstrations must come only from development cases and use visible-state inputs with valid consultant actions as targets. Hidden labels may support offline selection but may not enter online inputs. Adapter settings, checkpoint selection, planning-policy scope, training compute and failure criteria require separate reporting; SFT is not compute-equivalent merely because it uses the same cases. ",
            "[PLANNED EXPERIMENT — decide outcome-blind whether SFT is in scope; if included, freeze demonstrations, optimizer, checkpoint rule and budget before official evaluation]",
        ),
        119: plain(
            "The primary session endpoint is Y_i=F_i/Q_i for Q_i>0 and zero for Q_i=0, where F_i counts distinct first-disclosed client fact identifiers after the opening and Q_i counts questions presented to the client. Persona sessions are averaged within each case; the primary effect is the mean of 30 paired case differences. Mandatory companions are F and Q. Fact Coverage, Elicitation, Resolution, Fidelity and disputed-fact recall assess quality. Correct evidence-gap recall is paired with precision or false-positive counts. Repeated questions, unsupported-claim rate, StopGate redirects, factual fallbacks, premature stopping and invalid sessions are reported with explicit denominators. The pooled ratio ΣF/ΣQ is secondary."
        ),
        122: plain(
            "The designated L8 library is the sole primary learned treatment. For each method, metrics are averaged across four personas within a case before computing paired differences. With 30 cases, not 120 sessions, the plan uses 10,000 case-bootstrap resamples for percentile intervals and 20,000 Monte Carlo paired sign flips, with a frozen random seed and add-one correction, for the primary yield effect. Estimates are conditional on the realized library. Every independently learned replicate is first analyzed against Base as its own 30-case experiment; sessions from 30×R case–run cells are not treated as independent."
        ),
        123: plain(
            "The confirmatory hierarchy is frozen before official outcomes: (i) primary two-sided yield comparison; (ii) the stronger directional conjunction ΔF>0 and ΔQ<0 assessed by an intersection–union test, with both one-sided component nulls rejected, or Holm adjustment if separate component discoveries are claimed; (iii) a Benjamini–Hochberg family for prespecified quality endpoints that does not duplicate F; and (iv) Holm-adjusted yield contrasts across additional baselines. Failure to detect a quality difference is not equivalence. Non-inferiority requires a justified margin and a prespecified test."
        ),
        124: with_pending(
            "All planned cells, failures and repairs will be disclosed. Invalid execution is not silently removed. Report the complete matrix, paired valid-case analysis, a conservative failure sensitivity, raw case differences and leave-one-case-out influence. Design sensitivity or simulation-based power uses only prespecified plausible case-level distributions and the smallest scientifically meaningful effect; calculations designed after viewing official outcomes are labelled descriptive. ",
            "[PENDING ANALYSIS — freeze estimands, directional hypotheses, multiplicity families, failure/missing-data rules, non-inferiority margins if any, and outcome-blind design-sensitivity assumptions]",
        ),
        126: plain(
            "The run-bound client qualification used 51 development cases, 142 chains and 144 frozen contrasts. Match selection was correct for 137/144 contrasts (0.951): 96/101 matched items (0.950) and 41/43 unmatched items (0.953). Disclosure decisions were correct for 144/144 (1.000), response kind for 137/144 (0.951), persona transitions for 2/2 (1.000), and contract fallbacks occurred in 0/144 (0.000). The frozen semantic judge passed its controlled eight-case development protocol. These numerator/denominator results qualify encoded behaviors only; full-precision values and hashes remain in the artifacts and do not estimate the method's treatment effect or legal validity."
        ),
        127: with_pending(
            "Validation should separate three samples: a case-level review of 30–40 stratified sessions for question relevance, stopping and memorandum errors; a skill-level review of every L8 document (at most 24) for source support, actionability, contraindications and legal risk; and a route-level audit of opening labels independent of treatment. A second frozen model measures judge sensitivity but is not a legal expert. Claims about legal correctness, safety or real-client usefulness require qualified legal reviewers; without them, conclusions remain limited to the finite simulator and encoded rubrics. ",
            "[PLANNED EXPERIMENT — freeze sampling frames, reviewer qualifications, blinded adjudication, rubrics, agreement statistics and handling of conflicts before selecting cases for review]",
        ),
        129: plain(
            "The main treatment-attribution ablation is a fresh learning run that removes outcome-typed mechanism filtering while preserving reward-gap trajectory evidence, case order, model calls and teacher-attempt budget. Further fresh runs can replace the cumulative bank with current-block evidence only or remove the additional-question reward penalty. Each ablation learns its own library; the primary library is never retroactively selected using external results. The question-cost ablation must report its realized source-mechanism mix because other stopping incentives remain."
        ),
        130: plain(
            "Lower-cost frozen-library diagnostics include general-only skill delivery, an active-library-derived routing sensitivity against the isolated primary route and length-matched context controls. They identify sensitivity of the final system conditional on the already learned L8 library; they do not substitute for relearning a mechanism ablation. A no-skill policy condition is not equivalent to Base while the route itself is derived from the active library. Prompt character count and tokenizer-derived token count accompany every component comparison."
        ),
        131: with_pending(
            "The primary estimate uses the library and randomization stream designated before external evaluation. If resources permit, at least three complete outcome-blind learning replications assess training variability. Each replicate receives its own paired case-level effect. A secondary run-level analysis can use a hierarchical run×case bootstrap or an explicitly specified mixed model; it must not treat 30×R observations as mutually independent. Dialogue seeds 43 and 44 on six cases assess sampling sensitivity only, not learning replication. ",
            "[PLANNED EXPERIMENT — freeze the primary run, replicate seeds, run-specific analysis and any hierarchical secondary analysis before official execution]",
        ),
        133: plain(
            "The reviewed configuration pins Qwen3-8B to revision b968826d9c46dd6066d109eabc6255188de91218 and gpt-oss-20b to revision 6cee5e81ee83917806bbde320786a8fb61efebee. Policy temperature is 0.7 during learning and 0.2 in paired external evaluation. The teacher is a deployment alias rather than a dated weight snapshot, so reproduction requires call timestamps, client version, request/response hashes and retained outputs; exact teacher-weight reproduction cannot be claimed."
        ),
        134: with_pending(
            "The active run identifier is main_experiment_128_legalskillevolve_formal_20260911_runtime01. At the 11 September 2026 13:48 CST manuscript snapshot, its run manifest still reported status=initialized, content_sha256=349885d608e2f6f875f234de3e738ccd07989297d29eaa7bc18e783a91060dda and file SHA-256 def4ee88ab6e45d3d09a72831691d26f54714167c845524669336ac6a7e19363; status is dynamic and does not establish block completion. The nominal single-run budget is 512 main consultations, up to 112 non-learning shadows and up to 48 teacher attempts, before retries and qualification. ",
            "[PENDING METADATA — regenerate the final manifest and report Python/package lock, vLLM/CUDA stack, hardware, wall time, role-specific tokens, failures, final library hash and actual per-arm costs]",
        ),
        137: plain(
            "No learned-library effectiveness experiment was complete in the supplied evidence at manuscript revision time. Tables 3–5 therefore retain explicit yellow pending markers. Qualification results in Section 5.5 and historical replay checks are not substituted for confirmatory external effects."
        ),
        138: plain(
            "Table 3. Planned main results on 30 adaptation-held-out Chinese cases crossed with four personas. Entries are case-level macro means; arrows show favorable directions. † Required planned control; ‡ optional comparator. The primary paired effect and uncertainty are reported in Table 4."
        ),
        141: plain("Static†"),
        142: plain("Reward-gap memory†"),
        143: plain("SFT‡"),
        145: plain("New-fact-bearing-question rate Y ↑"),
        151: plain("New client facts F ↑"),
        157: plain("Questions Q ↓"),
        187: plain("Disputed-fact recall ↑"),
        193: plain("Evidence-gap recall / precision"),
        199: plain("Unsupported-claim rate ↓"),
        205: plain("Invalid sessions / planned sessions ↓"),
        211: plain(
            "Every pending cell is unmeasured. No rank, significance marker or imputed value is assigned before results exist. The reviewed executor currently implements only Base and Ours; † controls require an extension and ‡ is optional. Lower question counts are favorable only when interpreted with information and quality outcomes. Ours-versus-each-baseline paired differences, 95% case intervals and n appear in a companion effect table."
        ),
        212: plain(
            "Table 4. Planned paired case-level estimates for the main efficiency claim. Differences are Ours minus Base. The directional fact–question conjunction is assessed only under the frozen intersection–union rule."
        ),
        216: plain("Prespecified p-value"),
        217: plain("Decision / adjusted p where applicable"),
        218: plain("Yield ΔY"),
        222: plain("Primary two-sided test"),
        223: plain("New facts ΔF"),
        228: plain("Questions ΔQ"),
        233: [(
            "[PENDING RESULT — complete Tables 3–4; report ΔY and its 95% case interval, raw case differences, prespecified Monte Carlo p-values, failure denominators, and whether ΔF>0 and ΔQ<0 are jointly supported]",
            True,
        )],
        235: plain(
            "The block-level report will give healthy source groups, mechanism counts, teacher attempts, unique proposals, no-operation responses, rejections, admitted general/domain skills, character and token lengths, exposure counts, StopGate redirects and fallbacks. Admission is not effectiveness. Prequential differences are indexed by their input library L_{b−1}; post-update sizes refer to L_b."
        ),
        236: plain(
            "Table 5. Planned attribution and routing analyses. The full-method row reports case-level means (95% CI; n); each other row reports variant-minus-full paired Δ (95% case CI; n). Fresh-learning rows and frozen-library diagnostics answer different questions; every value remains pending."
        ),
        262: plain("General-only skill delivery"),
        263: plain("Frozen-L8 diagnostic rerun"),
        267: plain("Active-library-derived routing sensitivity"),
        268: plain("Frozen-L8 exploratory rerun"),
        272: [(
            "[PENDING RESULT — complete the skill ledger and mechanism analyses; add a paired F-versus-Q plot, an F@k curve with valid-stop carry-forward, prequential diagnostics, route/StopGate counts and uncertainty with actual denominators]",
            True,
        )],
        274: plain(
            "Persona estimates separate the trained cooperative condition from dependent, withdrawn and adversarial transfer. Dialogue-seed sensitivity and each independently learned library are shown without best-run selection. Qualitative cases use complete paired trajectories and distinguish original policy actions from StopGate-executed actions. Case-level human review, skill-level legal review and route audit use separately frozen samples rather than outcome-selected anecdotes."
        ),
        275: [(
            "[PENDING RESULT — report persona, dialogue-seed, learning-replication, route-sensitivity, independent-judge and human/expert-review results, including adverse cases and all runtime failures]",
            True,
        )],
        276: [(
            "[PENDING RESULT — report role-specific input/output tokens, latency, wall time, teacher/API cost, local compute, memory overhead, retries, repairs and failed calls]",
            True,
        )],
        278: plain(
            "LegalSkillEvolve treats skill documents as source-bound procedural hypotheses available to a frozen consultation policy. Direct admission supports cumulative development without reserving later blocks as candidate-specific acceptance sets, but plausible documents can be ineffective, conflict or consume context. The designated L8 comparison estimates the combined system—including routing and StopGate—unless those pathways are experimentally isolated. It cannot identify an individual skill's causal effect."
        ),
        279: plain(
            "The primary endpoint has a deliberately narrow interpretation: because the simulator discloses at most one matched identifier per response, Y is a new-fact-bearing-question rate. A shorter dialogue may reflect better targeting, earlier stopping, StopGate intervention or omitted investigation. Joint reporting of Y, F, Q, quality, remaining targets at stop and prefix curves helps distinguish these mechanisms, but cannot reproduce multi-fact human answers, emotional burden or real consultation time."
        ),
        280: plain(
            "Source-constrained data and deterministic audits improve traceability but do not provide professional validation. Training annotations are AI-authored; the primary client router and judge share model weights; and a second model judge tests only model sensitivity. Without qualified legal reviewers, conclusions are restricted to consistency with the finite simulator and encoded rubrics. Claims about legal correctness, safety or deployment require separate expert assessment, privacy review and real-world validation."
        ),
        281: with_pending(
            "The external set contains only 30 public Chinese cases. Case-level inference respects the experimental unit, but power, domain generalization and subgroup precision remain limited. Current active-library-derived routing threatens treatment isolation until corrected. A single learned library gives a conditional estimate, and the mutable teacher alias limits exact reproduction. ",
            "[PENDING ANALYSIS — add result-dependent interpretation, smallest supported effect, negative findings, influential cases, learning-run variability and a bounded statement of practical scope]",
        ),
        283: with_pending(
            "LegalSkillEvolve provides an auditable protocol for accumulating external procedural memory from full simulated consultations while keeping model weights fixed. Outcome-typed contrast records, static admission gates and case-level paired evaluation make the intended attribution testable, provided external routing is isolated and the full analysis is frozen before outcome exposure. ",
            "[PENDING RESULT — state only the empirical yield, fact, question and quality conclusions supported by the designated held-out experiment]",
        ),
        285: with_pending(
            "Data and code availability. The working repository is H00RU/LegalSkillGuard; the repository name does not define the method name. ",
            "[PENDING METADATA — add release tag/DOI, executable environment, immutable artifact manifest, access levels for restricted evaluation data, and licenses for code, annotations, sources and benchmark materials]",
        ),
        286: with_pending(
            "Ethics, privacy and review scope. The study uses public court-derived research scenarios and simulated clients; it currently contains no study with real clients and no independent legal-expert assessment. Public legal records can still contain personal or sensitive information and require purpose limitation, minimization and documented redistribution decisions. ",
            "[PENDING METADATA — record institutional ethics determination, privacy/de-identification review, source permissions, benchmark license compatibility, retention policy and reviewer consent/compensation if human review is added]",
        ),
        287: [(
            "Funding, competing interests and author contributions. [PENDING METADATA — insert verified journal-form declarations and CRediT roles]",
            True,
        )],
        288: with_pending(
            "Use of generative AI. AI systems assisted corpus authoring and manuscript preparation; authors remain responsible for source verification, analysis and claims. ",
            "[PENDING METADATA — provide the target journal's required model/tool disclosure, dates, retained records and author-verification statement]",
        ),
    }

    for index, segments in replacements.items():
        replace_paragraph(paragraphs[index], segments)

    # Replace the old overview figure while preserving its relationship identifier.
    drawing_paragraph = paragraphs[30]
    for node in drawing_paragraph.getElementsByTagName("wp:extent"):
        node.setAttribute("cx", "5943600")
        node.setAttribute("cy", "4953550")
    for node in drawing_paragraph.getElementsByTagName("a:xfrm"):
        extents = node.getElementsByTagName("a:ext")
        if extents:
            extents[0].setAttribute("cx", "5943600")
            extents[0].setAttribute("cy", "4953550")
    for node in drawing_paragraph.getElementsByTagName("wp:docPr"):
        node.setAttribute("name", "Figure 1 — current LegalSkillEvolve protocol")
        node.setAttribute(
            "descr",
            "Three-panel protocol diagram showing skill-blind planning, policy-only skill delivery, offline skill accumulation and L8 external evaluation.",
        )
    for node in paragraphs[40].getElementsByTagName("wp:docPr"):
        node.setAttribute("name", "Figure 2 — outcome-typed trajectory contrasts")
        node.setAttribute(
            "descr",
            "Three-panel diagram of independent trajectory sampling, outcome-typed contrast criteria and source-bound skill hypotheses.",
        )

    appendix = paragraphs[307]
    reference_template = paragraphs[306]
    for relationship_id, citation_text, url in REFERENCE_ENTRIES:
        new_paragraph = reference_template.cloneNode(deep=True)
        replace_reference_paragraph(
            new_paragraph,
            citation_text,
            url,
            relationship_id,
        )
        appendix.parentNode.insertBefore(new_paragraph, appendix)

    standardize_remaining_placeholders(document)
    return document.toxml(encoding="UTF-8")


def update_document_relationships(xml_bytes: bytes) -> bytes:
    document = minidom.parseString(xml_bytes)
    root = document.documentElement
    existing_ids = {
        node.getAttribute("Id")
        for node in document.getElementsByTagName("Relationship")
    }
    for relationship_id, _citation_text, url in REFERENCE_ENTRIES:
        if relationship_id in existing_ids:
            raise RuntimeError(f"Relationship ID collision: {relationship_id}")
        relationship = document.createElement("Relationship")
        relationship.setAttribute("Id", relationship_id)
        relationship.setAttribute("Type", HYPERLINK_RELATIONSHIP_TYPE)
        relationship.setAttribute("Target", url)
        relationship.setAttribute("TargetMode", "External")
        root.appendChild(relationship)
    return document.toxml(encoding="UTF-8")


def copy_zip_with_replacements(
    source: Path,
    destination: Path,
    document_xml: bytes,
    figure1_png: bytes,
    figure2_png: bytes,
    figure3_png: bytes,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        prefix=destination.stem + "_", suffix=".docx", dir=destination.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
    try:
        with ZipFile(source, "r") as input_zip, ZipFile(
            temporary, "w", compression=ZIP_DEFLATED
        ) as output_zip:
            for entry in input_zip.infolist():
                data = input_zip.read(entry.filename)
                if entry.filename == "word/document.xml":
                    data = document_xml
                elif entry.filename == "word/media/rId27.png":
                    data = figure1_png
                elif entry.filename == "word/media/rId32.png":
                    data = figure2_png
                elif entry.filename == FIGURE3_MEDIA_PATH:
                    data = figure3_png
                elif entry.filename == "word/_rels/document.xml.rels":
                    data = update_document_relationships(data)
                elif entry.filename == "docProps/core.xml":
                    data = update_core_properties(data)
                new_entry = ZipInfo(entry.filename, date_time=entry.date_time)
                new_entry.compress_type = entry.compress_type
                new_entry.comment = entry.comment
                new_entry.extra = entry.extra
                new_entry.create_system = entry.create_system
                new_entry.external_attr = entry.external_attr
                output_zip.writestr(new_entry, data)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def validate_output(path: Path) -> dict[str, int]:
    with ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Corrupt ZIP entry: {bad}")
        document = minidom.parseString(archive.read("word/document.xml"))
        relationships = minidom.parseString(
            archive.read("word/_rels/document.xml.rels")
        )
        names = set(archive.namelist())
        for figure_name in (
            "word/media/rId27.png",
            "word/media/rId32.png",
            FIGURE3_MEDIA_PATH,
        ):
            if figure_name not in names:
                raise RuntimeError(f"Replacement figure is missing: {figure_name}")
        relationship_targets = {
            node.getAttribute("Id"): node.getAttribute("Target")
            for node in relationships.getElementsByTagName("Relationship")
        }
        for relationship_id, _citation_text, url in REFERENCE_ENTRIES:
            if relationship_targets.get(relationship_id) != url:
                raise RuntimeError(f"Citation hyperlink is missing: {relationship_id}")
        linked_ids = {
            node.getAttribute("r:id")
            for node in document.getElementsByTagName("w:hyperlink")
        }
        missing_links = {
            relationship_id
            for relationship_id, _citation_text, _url in REFERENCE_ENTRIES
            if relationship_id not in linked_ids
        }
        if missing_links:
            raise RuntimeError(f"Citation hyperlink nodes are missing: {sorted(missing_links)}")
    text = "\n".join(paragraph_text(p) for p in document.getElementsByTagName("w:p"))
    if "____" in text or "[TBD-" in text:
        raise RuntimeError("Legacy unresolved marker remains")
    pending_count = text.count("[PENDING ") + text.count("[PLANNED EXPERIMENT")
    shaded_pending_runs = 0
    for run in document.getElementsByTagName("w:r"):
        run_text = "".join(
            node.firstChild.data if node.firstChild else ""
            for node in run.getElementsByTagName("w:t")
        )
        if "[PENDING " not in run_text and "[PLANNED EXPERIMENT" not in run_text:
            continue
        fills = [
            node.getAttribute("w:fill").upper()
            for node in run.getElementsByTagName("w:shd")
        ]
        if PENDING_FILL in fills:
            shaded_pending_runs += 1
    if pending_count == 0 or shaded_pending_runs != pending_count:
        raise RuntimeError(
            f"Pending marker/shading mismatch: markers={pending_count}, shaded_runs={shaded_pending_runs}"
        )
    return {
        "paragraphs": len(document.getElementsByTagName("w:p")),
        "pending_markers": pending_count,
        "shaded_pending_runs": shaded_pending_runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("figure1", type=Path)
    parser.add_argument("figure2", type=Path)
    args = parser.parse_args()

    if args.source.resolve() == args.destination.resolve():
        raise SystemExit("Refusing to overwrite the source manuscript")
    if not FIGURE3_ASSET.is_file():
        raise FileNotFoundError(FIGURE3_ASSET)
    with ZipFile(args.source) as archive:
        document_xml = revise_document(archive.read("word/document.xml"))
    copy_zip_with_replacements(
        args.source,
        args.destination,
        document_xml,
        args.figure1.read_bytes(),
        args.figure2.read_bytes(),
        FIGURE3_ASSET.read_bytes(),
    )
    report = validate_output(args.destination)
    print(
        f"created={args.destination} paragraphs={report['paragraphs']} "
        f"pending={report['pending_markers']} shaded={report['shaded_pending_runs']}"
    )


if __name__ == "__main__":
    main()
