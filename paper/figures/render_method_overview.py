"""Render the implemented TRAIN information flow, not a result or new method.

Run with /usr/bin/python3. Uses the existing GI/Rsvg/Cairo stack. Reads only the
completed main run's config/source manifest and initialization, never TEST.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/openexempt_closed_feedback_public_assets128_20261021_run03.json"
OUTPUT = ROOT / "artifacts/research/method_overview_20261023/Run03_implemented_information_flow_v03"
ACTORS = (
    "experiments/openexempt_online.py",
    "legal_skill_guard/learning/task_scoped_skills.py",
    "legal_skill_guard/learning/legal_namespace.py",
    "legal_skill_guard/openexempt.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance():
    cfg = json.loads(CONFIG.read_text())
    frozen = json.loads(CONFIG.with_suffix(".frozen.json").read_text())
    initial = ROOT / "runs" / cfg["run_id"] / "initialization.json"
    assert digest(CONFIG) == frozen["config_sha256"]
    assert all(digest(ROOT / name) == frozen["files"][name] for name in ACTORS)
    assert json.loads(initial.read_text())["bank"] == []
    assert cfg["execution_contract"] == "direct_statutory_claims"
    assert cfg["skill_commit_policy"] == "legal_scope"
    assert cfg["candidate_feedback_policy"] == "carry_partial_and_refine"
    assert (cfg["source_cases"], cfg["batch_source_cases"], cfg["planned_batches"]) == (128, 16, 8)
    assert cfg["library_token_hard_cap"] == 4096 and cfg["max_candidate_attempts"] == 2
    names = [str(CONFIG.relative_to(ROOT)), str(CONFIG.with_suffix(".frozen.json").relative_to(ROOT)),
             str(initial.relative_to(ROOT)), *ACTORS]
    return {"classification": "Implemented method schematic, not empirical performance",
            "run_id": cfg["run_id"], "font": "DejaVu Serif; Georgia unavailable on this server",
            "public_scope_graph": "Illustrative dependencies, not a fixed partition or learned router",
            "source_sha256": {name: digest(ROOT / name) for name in names},
            "no_grading_targets_predictions_or_TEST_read": True,
            "no_model_teacher_tokenizer_or_new_package_calls": True}


def document(data):
    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="10in" height="4.75in" viewBox="0 0 1200 570">',
         '<title>Batchwise procedural skill evolution with a frozen legal executor</title>',
         '<desc>New cases are answered before feedback. Released TRAIN targets inform bounded teacher edits. Public legal co-visibility groups candidate edits for replay; admitted components are composed and checked before one library publication for the next batch. No TEST feedback enters learning.</desc>',
         '<metadata>' + escape(json.dumps(data, separators=(",", ":"))) + '</metadata>',
         '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="#808080" stroke-width="1.1"/></marker></defs>',
         '<rect width="1200" height="570" fill="white"/>',
         '<style>text{font-family:"DejaVu Serif",serif;fill:#252525} .flow{fill:none;stroke:#808080;stroke-width:1.6;stroke-dasharray:5 4;marker-end:url(#arrow)}</style>']

    def text(x, y, s, size=15, anchor="start", color="#252525", bold=False):
        weight = ' font-weight="bold"' if bold else ""
        p.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" style="fill:{color}"{weight}>{escape(s)}</text>')

    def box(x, y, w, h, fill="white", stroke="#9EC2DD", radius=9):
        p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.3"/>')

    def path(d):
        p.append(f'<path class="flow" d="{d}"/>')

    def node(x, y, label):
        p.append(f'<circle cx="{x}" cy="{y}" r="22" fill="white" stroke="#4C7D9D" stroke-width="1.5"/>')
        text(x, y+5, label, 14, "middle")

    text(30, 31, "Experience updates the skills, not the model weights", 22)
    text(30, 57, "One batch of the implemented legal rule-application learner", 15, color="#626262")
    path("M1135,412 C1190,412 1190,100 1160,100 L40,100 Q15,100 15,125 L15,284 Q15,304 39,304 L68,304")
    text(620, 93, "Published library serves the next batch; saved forecasts stay unchanged", 14, "middle", "#626262")

    box(30, 126, 290, 380)
    box(349, 126, 470, 380)
    box(848, 126, 322, 380)
    for x, title in ((48, "1  Answer new sources"), (367, "2  Learn from released TRAIN"),
                     (866, "3  Publish reusable guidance")):
        text(x, 151, title, 17, bold=True)

    # New-case inference uses public inputs plus the entering library only.
    box(51, 175, 248, 66, "#F9E8EF", "#E4A7C2")
    text(175, 201, "Facts + supplied law", 16, "middle")
    text(175, 223, "Known task and allowable scopes", 14, "middle", "#626262")
    path("M175,241 C175,250 175,254 175,265")
    box(68, 266, 214, 75, "#C6DCEC", "#4C7D9D")
    text(175, 291, "Frozen Qwen3-8B", 17, "middle", bold=True)
    text(175, 315, "Entering library K(b-1)", 15, "middle")
    text(175, 333, "Empty at the start of learning", 13, "middle", "#626262")
    path("M175,341 C175,354 175,358 175,371")
    box(51, 372, 248, 99)
    text(175, 395, "Save every first forecast", 16, "middle")
    text(175, 420, "EC: asset → statutory citations", 14, "middle")
    text(175, 443, "EV: asset → citations + amounts", 14, "middle")
    text(175, 462, "16 sources; both task views", 13, "middle", "#626262")
    path("M299,421 C324,421 329,209 370,209")

    # Labels are released only after all logical conditions have been saved.
    box(370, 175, 428, 66, "#F9E8EF", "#E4A7C2")
    text(584, 200, "Now release training targets and scores", 16, "middle")
    text(584, 223, "Teacher: targeted edits; at most two attempts", 14, "middle", "#626262")
    path("M584,241 C584,251 584,255 584,267")
    box(370, 268, 428, 57)
    text(584, 291, "Replay all seen TRAIN sources", 16, "middle")
    text(584, 313, "Paired parent / proposal outputs; no validation split", 13, "middle", "#626262")
    path("M584,325 C584,336 584,339 584,350")
    text(584, 373, "Assess dependent legal edits together", 16, "middle")
    # An illustrative subset shows dependencies, not three hard-coded groups.
    p.append('<path d="M429,433 Q467,396 509,414 M509,414 Q547,396 587,433" fill="none" stroke="#9EC2DD" stroke-width="2"/>')
    for x, y, label in ((429, 433, "PA"), (509, 414, "FED"), (587, 433, "OR"), (721, 433, "AZ")):
        node(x, y, label)
    text(584, 475, "Illustrative public co-visibility, not a fixed partition", 13, "middle", "#626262")
    path("M798,433 C832,433 831,209 869,209")

    # Publication is conditional on both component and composed-bank checks.
    box(869, 175, 280, 66)
    text(1009, 201, "Admit supported components", 16, "middle")
    text(1009, 223, "Retain parent text elsewhere", 14, "middle", "#626262")
    path("M1009,241 C1009,252 1009,257 1009,268")
    box(869, 269, 280, 61)
    text(1009, 293, "Compose + whole-library check", 15, "middle")
    text(1009, 316, "TRAIN means and audited error counts", 13, "middle", "#626262")
    path("M1009,330 C1009,342 1009,347 1009,358")
    for x, y in ((879, 368), (875, 364)):
        box(x, y, 264, 106, "white", "#E4A7C2")
    box(871, 360, 264, 106, "#F9E8EF", "#AA6281")
    text(1003, 385, "One published library K(b)", 16, "middle", "#AA6281", True)
    text(1003, 410, "WHEN  ·  PROCEDURE  ·  EXCEPTIONS", 12.5, "middle")
    text(1003, 434, "Public scope; no stored case answers", 13, "middle")
    text(1003, 456, "≤ 4,096 serialized tokens", 14, "middle")
    text(1009, 492, "No accepted edit → unchanged library", 13, "middle", "#626262")

    text(30, 537, "All seen-source replay is training optimization. Frozen-library TEST is separate and supplies no learning feedback.", 14)
    p.append("</svg>")
    return "\n".join(p)


def main():
    data = provenance()
    import gi
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg
    import cairo
    OUTPUT.mkdir(parents=True, exist_ok=False)
    svg = OUTPUT / "method_overview.svg"
    with svg.open("x", encoding="utf-8") as stream:
        stream.write(document(data))
    handle = Rsvg.Handle.new_from_file(str(svg))
    viewport = Rsvg.Rectangle()
    viewport.x, viewport.y, viewport.width, viewport.height = 0, 0, 1200, 570
    image = cairo.ImageSurface(cairo.FORMAT_ARGB32, 6000, 2850)
    context = cairo.Context(image)
    context.scale(5, 5)
    handle.render_document(context, viewport)
    image.write_to_png(str(OUTPUT / "method_overview_600dpi.png"))
    image.finish()
    preview = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1200, 570)
    handle.render_document(cairo.Context(preview), viewport)
    preview.write_to_png(str(OUTPUT / "method_overview_preview.png"))
    preview.finish()
    pdf = cairo.PDFSurface(str(OUTPUT / "method_overview.pdf"), 720, 342)
    context = cairo.Context(pdf)
    context.scale(0.6, 0.6)
    handle.render_document(context, viewport)
    pdf.finish()
    data["rendered_at"] = datetime.now(timezone.utc).isoformat()
    data["render_script_sha256"] = digest(Path(__file__))
    data["outputs_sha256"] = {p.name: digest(p) for p in OUTPUT.iterdir()}
    with (OUTPUT / "source_provenance.json").open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"output_directory": str(OUTPUT), "new_inference_or_TEST_calls": 0}))


if __name__ == "__main__":
    main()
