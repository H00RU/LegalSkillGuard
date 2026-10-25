"""Render the complete single-build TRAIN traces, never replay or TEST.

Uses the existing system GI/Rsvg/Cairo stack without learner dependencies.
Run: /usr/bin/python3 paper/figures/render_granularity_prequential.py
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / (
    "artifacts/research/openexempt_legal_scope_20261020/"
    "TaskLocal45_phase4_B8_complete80stop_firsts_EC9609_EV8743_all160_"
    "true_teacher14_full8_online_not_final_TEST_20261025.json"
)
OUTPUT = ROOT / "artifacts/research/learning_curves_20261025/Granularity_firsts128_seed45_v01"
METHODS = ("main", "whole_bank", "task_local")
LABELS = {"main": "Context groups (main)", "whole_bank": "Whole bank", "task_local": "EC/EV task groups"}
COLORS = {"main": "#D6337F", "whole_bank": "#808080", "task_local": "#3C78A8"}
PANELS = (("EC", "firsts", 105, 155, 390), ("EV", "firsts", 700, 155, 390),
          ("EC", "gain", 105, 535, 770), ("EV", "gain", 700, 535, 770))
WIDTH = 430


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plot_data():
    report = json.loads(REPORT.read_text())
    comparison = report["completed8_firsts_training_comparison"]
    sources = comparison["source_sha256"]
    assert len(sources) == 48
    for name, expected in sources.items():
        assert digest(ROOT / name) == expected, name
    series = []
    for method in METHODS:
        run = comparison["runs"][method]
        rows = run["firsts8_curve"]
        assert [row["batch"] for row in rows] == list(range(1, 9))
        for head in ("EC", "EV"):
            raw, paired = [], []
            for row in rows:
                original = json.loads((ROOT / "runs" / run["run_id"] / "batches" /
                                       f'b{row["batch"]}_prequential.json').read_text())
                assert original["source_cases"] == 16 and not original["official_test_opened"]
                assert row[head] == original["skills"][head]["f1"]
                raw.append(100 * row[head])
                if row["batch"] > 1:
                    assert row["own_B1_" + head] == original["frozen_after_B1"][head]["f1"]
                    paired.append(100 * (row[head] - row["own_B1_" + head]))
            series.extend([
                {"method": method, "head": head, "kind": "firsts", "batches": list(range(1, 9)), "values": raw},
                {"method": method, "head": head, "kind": "gain", "batches": list(range(2, 9)), "values": paired},
            ])
    assert sum(len(s["values"]) for s in series) == 90
    return {
        "rendered_at": datetime.now(timezone.utc).isoformat(), "series": series,
        "report_path": str(REPORT.relative_to(ROOT)), "report_sha256": digest(REPORT),
        "source_artifact_sha256": sources, "render_script_sha256": digest(Path(__file__)),
        "distinct_source_cases": 128, "source_cases_per_point": 16, "learning_builds_per_policy": 1,
        "firsts_unit": "Original within-task source macro-F1, percent",
        "gain_unit": "Same-cohort online minus that run's own frozen-B1 macro-F1, percentage points",
        "own_B1": "Undefined at cold B1, equal to online at B2; B1 placeholders are not gains",
        "task_local_EC": "Own B1 has no EC skill head, so later EC gain includes initial acquisition",
        "uncertainty": "No independent-learning repetition or confidence band; no significance claim",
        "boundary": "Completed8 first forecasts, not final B8 library, post-update fit or TEST",
        "fairness": "Main learning serial; both controls four-worker. Single-build descriptive traces, not isolated causal effects",
        "font": "DejaVu Serif, matching existing project figures; Georgia unavailable on this server",
        "physical_size_inches": [7.2, 5.4], "png_pixels": [4320, 3240], "png_dpi_at_declared_size": 600,
        "all_expected_rank_constraints": False, "new_model_teacher_grading_or_TEST_calls": 0,
    }


def coordinates(batch, value, left, top, bottom, kind):
    lower, upper = (50, 100) if kind == "firsts" else (-15, 35)
    assert lower <= value <= upper
    return left + (batch - 1) * WIDTH / 7, bottom - (value - lower) * (bottom - top) / (upper - lower)


def svg_document(data):
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="7.2in" height="5.4in" viewBox="0 0 1200 900">',
             '<rect width="1200" height="900" fill="white"/>',
             '<style>text{font-family:"DejaVu Serif",serif;fill:#252525}</style>',
             '<title>Single-build TRAIN forecasts and own-B1 contrasts</title>',
             '<desc>EC and EV first forecasts and same-cohort gains for three policies; no TEST results or independent-repeat uncertainty.</desc>',
             '<metadata>' + escape(json.dumps(data, ensure_ascii=False, separators=(",", ":"))) + '</metadata>']

    def text(x, y, value, size=20, anchor="start", extra=""):
        parts.append(f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size}" text-anchor="{anchor}" {extra}>{escape(value)}</text>')

    def line(x1, y1, x2, y2, color="#555555", width=1.5, dash=""):
        parts.append(f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/>')

    def marker(x, y, method):
        color = COLORS[method]
        if method == "whole_bank":
            shape = f'<rect x="{x-4:.3f}" y="{y-4:.3f}" width="8" height="8"'
        elif method == "task_local":
            shape = f'<path d="M{x:.3f},{y-6:.3f} L{x-5.5:.3f},{y+5:.3f} L{x+5.5:.3f},{y+5:.3f} Z"'
        else:
            shape = f'<circle cx="{x:.3f}" cy="{y:.3f}" r="5"'
        parts.append(shape + f' fill="white" stroke="{color}" stroke-width="2.2"/>')

    text(40, 34, "Single-build TRAIN forecasts and continued-learning contrasts", 27)
    text(40, 64, "Same 128 source cases per policy; 16 cases per batch; scores precede batch feedback", 19)
    for x, method in ((70, "main"), (510, "whole_bank"), (835, "task_local")):
        line(x, 96, x+40, 96, COLORS[method], 2.8)
        marker(x+20, 96, method)
        text(x+52, 102, LABELS[method], 20)
    for panel, (head, kind, left, top, bottom) in enumerate(PANELS):
        heading = f'({chr(97+panel)}) {head}: ' + ("first forecasts" if kind == "firsts" else "gain over own B1")
        text(left, top-19, heading, 23)
        ticks = range(50, 101, 10) if kind == "firsts" else range(-10, 31, 10)
        for value in ticks:
            _, y = coordinates(1, value, left, top, bottom, kind)
            line(left, y, left+WIDTH, y, "#d8d8d8", 1.0)
            text(left-15, y+7, str(value), 20, "end")
        if kind == "gain":
            _, y = coordinates(1, 0, left, top, bottom, kind)
            line(left, y, left+WIDTH, y, "#606060", 1.8, "5 4")
        line(left, top, left, bottom)
        line(left, bottom, left+WIDTH, bottom)
        for batch in range(1, 9):
            x, _ = coordinates(batch, 50 if kind == "firsts" else -15, left, top, bottom, kind)
            line(x, bottom, x, bottom+5)
            text(x, bottom+29, f"B{batch}", 19, "middle")
        text(left+WIDTH/2, bottom+60, "Batch (different source cases)", 19, "middle")
        mid = (top+bottom)/2
        label = "Macro-F1 (%)" if kind == "firsts" else "Difference (pp)"
        text(left-65, mid, label, 20, "middle", f'transform="rotate(-90 {left-65} {mid})"')
        for method in ("whole_bank", "task_local", "main"):
            s = next(s for s in data["series"] if (s["method"], s["head"], s["kind"]) == (method, head, kind))
            points = [coordinates(b, v, left, top, bottom, kind) for b, v in zip(s["batches"], s["values"])]
            xy = " ".join(f"{x:.6f},{y:.6f}" for x, y in points)
            parts.append(f'<polyline data-method="{method}" data-head="{head}" data-kind="{kind}" points="{xy}" fill="none" stroke="{COLORS[method]}" stroke-width="2.8"/>')
            for x, y in points:
                marker(x, y, method)
    text(40, 861, "First forecasts, not replay or TEST. Own-B1 starts at B2; no repeated-learning uncertainty shown.", 17)
    text(40, 888, "Task-local B1 has no EC head; its EC gain includes acquisition. Learning execution differs as disclosed.", 17)
    parts.append("</svg>")
    return "\n".join(parts)


def verify_svg(svg, data):
    tree = ElementTree.fromstring(svg)
    polylines = tree.findall("{http://www.w3.org/2000/svg}polyline")
    assert len(polylines) == 12
    points_checked = 0
    for poly in polylines:
        method, head, kind = (poly.attrib["data-"+k] for k in ("method", "head", "kind"))
        s = next(s for s in data["series"] if (s["method"], s["head"], s["kind"]) == (method, head, kind))
        _, _, left, top, bottom = next(p for p in PANELS if p[:2] == (head, kind))
        actual = [tuple(map(float, point.split(","))) for point in poly.attrib["points"].split()]
        assert len(actual) == len(s["values"])
        for point, batch, value in zip(actual, s["batches"], s["values"]):
            expected = coordinates(batch, value, left, top, bottom, kind)
            assert all(abs(a-b) < 1e-6 for a, b in zip(point, expected))
            points_checked += 1
    assert points_checked == 90
    return points_checked


def main():
    data = plot_data()
    svg = svg_document(data)
    data["all_original_points_and_coordinates_verified"] = verify_svg(svg, data)
    import gi
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg
    import cairo
    OUTPUT.mkdir(parents=True, exist_ok=False)
    (OUTPUT / "online_granularity.svg").write_text(svg, encoding="utf-8")
    handle = Rsvg.Handle.new_from_file(str(OUTPUT / "online_granularity.svg"))
    viewport = Rsvg.Rectangle()
    viewport.x, viewport.y, viewport.width, viewport.height = 0, 0, 1200, 900
    for filename, width, height in (("online_granularity_600dpi.png", 4320, 3240),
                                    ("online_granularity_print_preview.png", 1200, 900)):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        context = cairo.Context(surface)
        context.scale(width/1200, height/900)
        handle.render_document(context, viewport)
        surface.write_to_png(str(OUTPUT / filename))
        surface.finish()
    pdf = cairo.PDFSurface(str(OUTPUT / "online_granularity.pdf"), 518.4, 388.8)
    context = cairo.Context(pdf)
    context.scale(0.432, 0.432)
    handle.render_document(context, viewport)
    pdf.finish()
    data["outputs_sha256"] = {p.name: digest(p) for p in OUTPUT.iterdir()}
    (OUTPUT / "source_data_and_provenance.json").write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"output_directory": str(OUTPUT), "points_verified": 90,
                      "new_model_teacher_grading_or_TEST_calls": 0}))


if __name__ == "__main__":
    main()
