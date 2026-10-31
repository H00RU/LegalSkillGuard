"""Render completed frozen-library effects; no new inference or scoring.

Uses the existing system GI/Rsvg/Cairo stack and existing figure palette.
Run: /usr/bin/python3 paper/figures/render_frozen_source_effects.py
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from render_run03_prequential import COLORS, ROOT, digest

COMPLETION = ROOT / "runs/legal_openexempt_continued_IID128_prospective_TEST_20261029_run01/completion.json"
COMPLETION_SHA = "099d14d5bd831879abeecca6b4847ea343e4fad9baed624e938bf8fc2286ec06"
REFERENCES = (
    ("vs_empty", "Strong empty"), ("vs_static", "Law-only static"),
    ("vs_native_claim_own_B1_45", "Own frozen B1"),
    ("vs_native_claim45", "Original B8"), ("vs_ACE45", "ACE native"),
    ("vs_ACE_common45", "ACE common"), ("vs_text45", "Text-only"),
    ("vs_joint_consolidated45", "Joint teaching"),
)
DOMAIN = (-6.0, 46.0)
PANELS = (("EC", 180, COLORS["skills"]), ("EV", 810, COLORS["frozen_after_B1"]))
WIDTH = 380


def plot_data():
    if digest(COMPLETION) != COMPLETION_SHA:
        raise ValueError("The original completed comparison changed")
    result = json.loads(COMPLETION.read_text())
    stats = result["paired_source_statistics"]
    assert result["status"] == "completed_frozen_comparison"
    assert result["actual_native_calls"] == 1836 and result["teacher_calls"] == 0
    assert len(result["exact_wire_reuses_not_independent_draws"]) == 468
    assert stats["sources"] == 128 and stats["primary_family_comparisons"] == 16
    assert set(stats["contrasts"]) == {name for name, _ in REFERENCES}
    rows = []
    for name, label in REFERENCES:
        contrast = stats["contrasts"][name]
        assert contrast["after"] == ["task_consolidated45"] and len(contrast["before"]) == 1
        endpoints = contrast["endpoints"]
        for family in ("EC", "EV"):
            expected = 100 * (result["metrics"]["task_consolidated45"][family]["f1"]
                              - result["metrics"][contrast["before"][0]][family]["f1"])
            assert abs(expected - endpoints[family]["difference_pp"]) < 1e-10
            assert all(DOMAIN[0] <= value <= DOMAIN[1] for value in
                       endpoints[family]["conditional_Bonferroni_interval_pp"])
        rows.append({"contrast": name, "reference": contrast["before"][0],
                     "label": label, "endpoints": endpoints})
    return {"rendered_at": datetime.now(timezone.utc).isoformat(), "rows": rows,
            "source_completion": str(COMPLETION.relative_to(ROOT)),
            "source_completion_sha256": COMPLETION_SHA,
            "target_bank_sha256": result["bank_sha256"]["task_consolidated45"],
            "absolute_native_F1": {name: {f: heads[f]["f1"] for f in ("EC", "EV")}
                                   for name, heads in result["metrics"].items()},
            "uncertainty": "Source-paired conditional Bonferroni intervals; one16-endpoint family",
            "sources": 128, "bootstrap_draws": stats["bootstrap_draws"],
            "bootstrap_seed": stats["bootstrap_seed"],
            "no_independent_learning_repeat_variance_invented": True,
            "all_failed_outputs_retained": True,
            "B8_EC": "Identical-request retention check, exact zero",
            "ACE_native_and_common_share_one_build": True,
            "font": "DejaVu Serif; Georgia unavailable, matching existing project figures",
            "physical_size_inches": [7.2, 3.2], "png_pixels": [4320, 1920],
            "render_script_sha256": digest(Path(__file__)),
            "reused_palette_and_digest_source": "paper/figures/render_run03_prequential.py",
            "reused_renderer_sha256": digest(Path(__file__).with_name("render_run03_prequential.py")),
            "new_model_teacher_or_grading_calls": 0}


def px(value, left):
    return left + (value - DOMAIN[0]) * WIDTH / (DOMAIN[1] - DOMAIN[0])


def svg_document(data):
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="7.2in" height="3.2in" viewBox="0 0 1260 560">',
             '<rect width="1260" height="560" fill="white"/>',
             '<style>text{font-family:"DejaVu Serif",serif;fill:#252525}</style>',
             '<title>Source-disjoint utility of the predeclared learned skill library</title>',
             '<desc>All eight paired references and both EC/EV endpoints, including the identical B8 EC contrast and joint teaching control.</desc>',
             '<metadata>' + escape(json.dumps(data, ensure_ascii=False, separators=(",", ":"))) + '</metadata>']

    def text(x, y, value, size=19, anchor="start"):
        parts.append(f'<text x="{x:.6f}" y="{y:.6f}" font-size="{size}" text-anchor="{anchor}">{escape(value)}</text>')

    def line(x1, y1, x2, y2, color="#555555", width=1.5, extra=""):
        parts.append(f'<line x1="{x1:.6f}" y1="{y1:.6f}" x2="{x2:.6f}" y2="{y2:.6f}" stroke="{color}" stroke-width="{width}" {extra}/>')

    for family, left, color in PANELS:
        title = "(a) Exemption classification" if family == "EC" else "(b) Exemption valuation"
        text(left, 48, title, 23)
        text(left + WIDTH + 60, 81, "Δ pp", 18, "end")
        for tick in (-5, 0, 10, 20, 30, 40):
            x = px(tick, left)
            line(x, 88, x, 430, "#b6b6b6" if tick == 0 else "#e4e4e4",
                 1.5 if tick == 0 else 1, 'stroke-dasharray="4 4"' if tick == 0 else "")
            text(x, 461, str(tick), 18, "middle")
        line(left, 438, left + WIDTH, 438)
        for index, row in enumerate(data["rows"]):
            y = 110 + 42 * index
            effect = row["endpoints"][family]
            value = effect["difference_pp"]
            lower, upper = effect["conditional_Bonferroni_interval_pp"]
            text(left - 12, y + 6, row["label"], 19, "end")
            tags = f'data-family="{family}" data-contrast="{row["contrast"]}"'
            line(px(lower, left), y, px(upper, left), y, color, 2.2,
                 tags + ' data-interval="family-adjusted"')
            for edge in (lower, upper):
                line(px(edge, left), y - 5, px(edge, left), y + 5, color, 2)
            parts.append(f'<circle cx="{px(value, left):.6f}" cy="{y}" r="4.5" fill="{color}" {tags}/>')
            text(left + WIDTH + 60, y + 6, f"{value:+.2f}", 18, "end")
        text(left + WIDTH / 2, 490, "Target − reference native F1 (pp)", 19, "middle")
    text(30, 528, "128 paired sources; intervals adjusted across all 16 EC/EV comparisons; one frozen bank per learner.", 17)
    text(30, 551, "Original B8 EC is an identical-request retention check. ACE native/common share one learned library.", 17)
    parts.append("</svg>")
    return "\n".join(parts)


def verify_coordinates(svg, data):
    root = ElementTree.fromstring(svg)
    errors = []
    for family, left, _ in PANELS:
        for row in data["rows"]:
            wanted = {"data-family": family, "data-contrast": row["contrast"]}
            point = next(e for e in root.iter() if e.tag.endswith("circle")
                         and all(e.get(k) == v for k, v in wanted.items()))
            interval = next(e for e in root.iter() if e.tag.endswith("line")
                            and e.get("data-interval") == "family-adjusted"
                            and all(e.get(k) == v for k, v in wanted.items()))
            decoded = lambda value: DOMAIN[0] + (float(value) - left) * (DOMAIN[1] - DOMAIN[0]) / WIDTH
            effect = row["endpoints"][family]
            expected = [effect["difference_pp"], *effect["conditional_Bonferroni_interval_pp"]]
            actual = [decoded(point.get("cx")), decoded(interval.get("x1")), decoded(interval.get("x2"))]
            errors.extend(abs(a - b) for a, b in zip(actual, expected))
    assert len(errors) == 48 and max(errors) < 1e-6
    return max(errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "paper/figures/source_disjoint_effects_20261029_v01")
    args = parser.parse_args()
    data = plot_data()
    svg = svg_document(data)
    data["maximum_coordinate_roundtrip_error_pp"] = verify_coordinates(svg, data)
    import gi
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg
    import cairo
    from PIL import Image
    args.output.mkdir(parents=True, exist_ok=False)
    svg_path = args.output / "paired_effects.svg"
    with svg_path.open("x", encoding="utf-8") as stream:
        stream.write(svg)
    handle = Rsvg.Handle.new_from_file(str(svg_path))
    viewport = Rsvg.Rectangle()
    viewport.x, viewport.y, viewport.width, viewport.height = 0, 0, 1260, 560
    image = cairo.ImageSurface(cairo.FORMAT_ARGB32, 4320, 1920)
    context = cairo.Context(image)
    context.scale(4320 / 1260, 1920 / 560)
    handle.render_document(context, viewport)
    png = args.output / "paired_effects_600dpi.png"
    image.write_to_png(str(png))
    image.finish()
    with Image.open(png) as bitmap:
        bitmap.save(png, dpi=(600, 600))
    pdf = cairo.PDFSurface(str(args.output / "paired_effects.pdf"), 7.2 * 72, 3.2 * 72)
    context = cairo.Context(pdf)
    context.scale(7.2 * 72 / 1260, 3.2 * 72 / 560)
    handle.render_document(context, viewport)
    pdf.finish()
    data["output_sha256"] = {p.name: digest(p) for p in args.output.iterdir()}
    with (args.output / "source_data_and_provenance.json").open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"output": str(args.output), "plotted_effects": 16,
                      "verified_coordinates": 48,
                      "maximum_coordinate_roundtrip_error_pp": data["maximum_coordinate_roundtrip_error_pp"],
                      "new_model_teacher_or_grading_calls": 0}))


if __name__ == "__main__":
    main()
