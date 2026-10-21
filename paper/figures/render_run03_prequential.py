"""Render completed Run03 TRAIN forecasts; no model, labels or TEST access.

Uses the existing system Python GI/Rsvg/Cairo stack, not the frozen learner env.
Run: /usr/bin/python3 paper/figures/render_run03_prequential.py --through-batch 6
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
RUN = "legal_openexempt_closed_feedback_public_assets128_20261021_run03"
CURVE = ROOT / "artifacts/research/openexempt_legal_scope_20261020/Run03_learning_curve_complete_prequential_batches_20261021.json"
COLORS = {"empty": "#808080", "frozen_after_B1": "#3C78A8", "skills": "#D6337F"}
ROLES = ("empty", "frozen_after_B1", "skills")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plot_data(through):
    curve = json.loads(CURVE.read_text())
    assert curve["run_id"] == RUN and 1 <= through <= 8
    rows = [r for r in curve["batch_rows"] if r["batch"] <= through]
    assert [r["batch"] for r in rows] == list(range(1, through + 1))
    paths = {str(CURVE.relative_to(ROOT)): digest(CURVE)}
    for row in rows:
        assert row["source_cases"] == 16 and row["tasks"] == 32
        path = ROOT / "runs" / RUN / "batches" / f'b{row["batch"]}_prequential.json'
        original = json.loads(path.read_text())
        for role, heads in row["first_encounter_native_F1"].items():
            for head in ("EC", "EV"):
                assert heads[head] == original[role][head]["f1"]
        paths[str(path.relative_to(ROOT))] = digest(path)
    return {
        "run_id": RUN, "through_batch": through, "planned_batches": 8,
        "source_cases_per_batch": 16, "complete_forecast_sources": 16 * through,
        "rows": rows, "source_artifact_sha256": paths,
        "endpoint": "original per-source task macro-F1, displayed as percent",
        "boundary": "One adaptive learner's first-encounter TRAIN trace, not replay or TEST",
        "uncertainty": "Independent learning repeats incomplete; no uncertainty bands drawn",
        "B1_control": "Undefined at B1; exact own first-final-B1 bank starts at B2",
        "font": "DejaVu Serif; Georgia unavailable on this server",
    }


def svg_document(data):
    rows, parts = data["rows"], []
    parts.append('<svg xmlns="http://www.w3.org/2000/svg" width="10in" height="4.5in" viewBox="0 0 1200 540">')
    parts.append('<rect width="1200" height="540" fill="white"/>')
    parts.append('<style>text{font-family:"DejaVu Serif",serif;fill:#252525} .grid{stroke:#e4e4e4;stroke-width:1}</style>')
    parts.append('<title>Run03 learner-first TRAIN forecasts, not replay or TEST</title>')
    parts.append('<desc>Two original macro-F1 panels. Same-case empty, own frozen B1, and evolving library; unfinished batches have no values.</desc>')
    parts.append('<metadata>' + escape(json.dumps(data, ensure_ascii=False, separators=(",", ":"))) + '</metadata>')

    def text(x, y, value, size=15, anchor="start", color=None, extra=""):
        fill = f' style="fill:{color}"' if color else ""
        parts.append(f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size}" text-anchor="{anchor}"{fill} {extra}>{escape(value)}</text>')

    def line(x1, y1, x2, y2, color, width=1.5, dash=""):
        parts.append(f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/>')

    def marker(x, y, role):
        color = COLORS[role]
        if role == "empty":
            parts.append(f'<path d="M{x:.3f},{y-4:.3f} L{x-4:.3f},{y+3.5:.3f} L{x+4:.3f},{y+3.5:.3f} Z" fill="{color}"/>')
        elif role == "frozen_after_B1":
            parts.append(f'<rect x="{x-3.5:.3f}" y="{y-3.5:.3f}" width="7" height="7" fill="{color}"/>')
        else:
            parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="5" fill="white" stroke="{color}" stroke-width="2.5"/>')

    text(42, 29, "Run03: first-encounter TRAIN performance", 22)
    text(42, 54, "Same frozen Qwen3-8B; 16 source cases per batch; scores saved before batch feedback", 14)
    text(1160, 29, f'{data["through_batch"]}/8 batches complete', 15, "end")
    for x, role, label in ((320, "empty", "Strong empty"), (535, "frozen_after_B1", "Own frozen B1"), (785, "skills", "Evolving skills")):
        line(x-25, 78, x+3, 78, COLORS[role], 2.2)
        marker(x-11, 78, role)
        text(x+12, 83, label, 14)

    for left, head, title in ((75, "EC", "(a) Exemption classification"), (680, "EV", "(b) Exemption valuation")):
        width, top, bottom = 460, 120, 395
        px = lambda batch: left + (batch - 1) * width / 7
        py = lambda value: bottom - value * (bottom - top) / 100
        if data["through_batch"] < 8:
            start = px(data["through_batch"] + 0.5)
            parts.append(f'<rect x="{start:.3f}" y="{top}" width="{left+width-start:.3f}" height="{bottom-top}" fill="#f4f4f4"/>')
            text((start + left + width)/2, 242, f'B{data["through_batch"]+1}-B8', 14, "middle", "#626262")
            text((start + left + width)/2, 265, "pending", 14, "middle", "#626262")
        text(left, 109, title, 18)
        for value in range(0, 101, 20):
            y = py(value)
            line(left, y, left+width, y, "#e4e4e4", 1)
            text(left-12, y+5, str(value), 14, "end")
        line(left, top, left, bottom, "#4d4d4d")
        line(left, bottom, left+width, bottom, "#4d4d4d")
        for batch in range(1, 9):
            x = px(batch)
            line(x, bottom, x, bottom+5, "#4d4d4d", 1)
            text(x, bottom+24, f"B{batch}", 14, "middle", "#626262" if batch>data["through_batch"] else None)
        for role in ROLES:
            points = [(px(r["batch"]), py(100*r["first_encounter_native_F1"][role][head])) for r in rows if role in r["first_encounter_native_F1"]]
            xy = " ".join(f"{x:.6f},{y:.6f}" for x, y in points)
            parts.append(f'<polyline data-role="{role}" data-endpoint="{head}" points="{xy}" fill="none" stroke="{COLORS[role]}" stroke-width="2.5"/>')
            for x, y in points:
                marker(x, y, role)
        latest = rows[-1]
        if "difference_vs_own_B1_pp" in latest:
            delta = latest["difference_vs_own_B1_pp"][head]
            text(left+15, 354, f'B{latest["batch"]} vs own B1: {delta:+.2f} pp', 15, color=COLORS["skills"])
        text(left+width/2, 443, "Batch (different source cases)", 15, "middle")
        text(left-47, 258, "Original macro-F1 (%)", 15, "middle", extra=f'transform="rotate(-90 {left-47} 258)"')

    sizes = ", ".join(str(r["entering_library_records"]) for r in rows)
    last_status = "published" if rows[-1]["completed_unique_final_publication"] else "update pending"
    text(42, 474, f'Entering library sizes: {sizes}. B{rows[-1]["batch"]} {last_status}; skill count alone is not learning evidence.', 13.5)
    text(42, 498, "Descriptive single-learner TRAIN trace. Cohorts differ; compare same-case arms. No repeated-run uncertainty shown.", 13.5)
    text(42, 522, "No replay scores or TEST outcomes plotted. ACE/static comparisons and sealed evaluation remain pending.", 13.5)
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through-batch", type=int, default=6)
    args = parser.parse_args()
    data = plot_data(args.through_batch)
    import gi
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg
    import cairo
    output = ROOT / f"artifacts/research/learning_curves_20261022/Run03_B1_B{args.through_batch}_prequential"
    output.mkdir(parents=True, exist_ok=False)
    svg = output / "learning_curve.svg"
    with svg.open("x", encoding="utf-8") as stream:
        stream.write(svg_document(data))
    handle = Rsvg.Handle.new_from_file(str(svg))
    viewport = Rsvg.Rectangle()
    viewport.x, viewport.y, viewport.width, viewport.height = 0, 0, 1200, 540
    image = cairo.ImageSurface(cairo.FORMAT_ARGB32, 6000, 2700)
    context = cairo.Context(image)
    context.scale(5, 5)
    handle.render_document(context, viewport)
    image.write_to_png(str(output / "learning_curve_600dpi.png"))
    image.finish()
    pdf = cairo.PDFSurface(str(output / "learning_curve.pdf"), 720, 324)
    context = cairo.Context(pdf)
    context.scale(0.6, 0.6)
    handle.render_document(context, viewport)
    pdf.finish()
    data["rendered_at"] = datetime.now(timezone.utc).isoformat()
    data["render_script_sha256"] = digest(Path(__file__))
    data["outputs_sha256"] = {p.name: digest(p) for p in output.iterdir()}
    with (output / "source_data_and_provenance.json").open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"output_directory": str(output), "complete_forecast_sources": data["complete_forecast_sources"], "new_model_teacher_TEST_calls": 0}))


if __name__ == "__main__":
    main()
