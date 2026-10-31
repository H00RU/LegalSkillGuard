#!/usr/bin/python3
"""Export the current bilingual working manuscript without changing its sources.

Pandoc preserves native Word mathematics; an isolated LibreOffice profile renders
PDF. The original v0.23 renderer and outputs are deliberately untouched. Output
directories must be new. This is a review export, not a journal submission.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PANDOC = Path("/home/yndx/hhy/.paper-tools/pandoc-3.13/bin/pandoc")
SOURCES = {
    "en": ROOT / "paper/utility_skill_manuscript_working_20261030.md",
    "zh": ROOT / "paper/sections-zh/utility_skill_manuscript_working_20261030.md",
}
BIB = ROOT / "paper/utility_skill_references_20261030.bib"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, **kwargs):
    return subprocess.run([str(x) for x in argv], check=True, capture_output=True, **kwargs)


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def visible(inlines, *, split_math=False):
    result = []
    for node in inlines:
        kind, value = node.get("t"), node.get("c")
        if kind == "Str":
            result.append(value)
        elif kind in ("Space", "SoftBreak", "LineBreak"):
            result.append(" ")
        elif kind == "Math":
            result.append("\0" if split_math else "")
        elif kind in ("Code", "Link", "Span"):
            result.append(value[-1] if kind == "Code" else visible(value[1], split_math=split_math))
        elif kind in ("Emph", "Strong", "Strikeout", "Superscript", "Subscript", "SmallCaps"):
            result.append(visible(value, split_math=split_math))
        elif kind == "Quoted":
            # None of the current scientific paragraphs depends on smart-quote style.
            result.append(visible(value[1], split_math=split_math))
        elif kind not in ("Image", "RawInline", "Note"):
            raise ValueError("Unreviewed inline type: " + str(kind))
    return "".join(result)


def paragraph_text(ast, *, split_math=False):
    result = []
    for node in walk(ast["blocks"]):
        if node.get("t") in ("Para", "Plain", "Header"):
            values = node["c"][2] if node["t"] == "Header" else node["c"]
            text = visible(values, split_math=split_math)
            if text.strip():
                result.append(text)
    return result


def norm(text):
    return "".join(unicodedata.normalize("NFKC", text).replace("\u00ad", "").split())


def make_reference(path):
    """Generate one A4 review template; do not mutate existing document styles."""
    payload = run([PANDOC, "--print-default-data-file=reference.docx"]).stdout
    with zipfile.ZipFile(io.BytesIO(payload)) as original, zipfile.ZipFile(path, "x") as dest:
        for item in original.infolist():
            data = original.read(item.filename)
            if item.filename in ("word/styles.xml", "word/document.xml"):
                doc = minidom.parseString(data)
                if item.filename == "word/document.xml":
                    body = doc.getElementsByTagName("w:body")[0]
                    sections = body.getElementsByTagName("w:sectPr")
                    section = sections[-1] if sections else doc.createElementNS(W, "w:sectPr")
                    if not sections:
                        body.appendChild(section)
                    for tag in ("pgSz", "pgMar"):
                        if not section.getElementsByTagName("w:" + tag):
                            section.appendChild(doc.createElementNS(W, "w:" + tag))
                for fonts in doc.getElementsByTagName("w:rFonts"):
                    if fonts.getAttribute("w:ascii") in ("Consolas", "Courier New", "Source Code Pro"):
                        continue
                    for name in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
                        if fonts.hasAttribute(name):
                            fonts.removeAttribute(name)
                    for name, value in (("w:ascii", "Liberation Serif"), ("w:hAnsi", "Liberation Serif"),
                                        ("w:eastAsia", "Noto Serif CJK SC")):
                        fonts.setAttribute(name, value)
                for page in doc.getElementsByTagName("w:pgSz"):
                    page.setAttribute("w:w", "11906")
                    page.setAttribute("w:h", "16838")
                for margin in doc.getElementsByTagName("w:pgMar"):
                    for side in ("top", "bottom", "left", "right"):
                        margin.setAttribute("w:" + side, "1134")
                data = doc.toxml(encoding="UTF-8")
            dest.writestr(item, data)


def stabilize_review_layout(path):
    """Keep review rows/captions intact without changing scientific content."""
    with zipfile.ZipFile(path) as package:
        members = [(item, package.read(item.filename)) for item in package.infolist()]
    payload = next(data for item, data in members if item.filename == "word/document.xml")
    doc = minidom.parseString(payload)

    def child(parent, name):
        return next((n for n in parent.childNodes if n.nodeType == n.ELEMENT_NODE
                     and n.tagName == "w:" + name), None)

    def flag(parent, properties, name):
        props = child(parent, properties)
        if props is None:
            props = doc.createElementNS(W, "w:" + properties)
            parent.insertBefore(props, parent.firstChild)
        prop = child(props, name)
        if prop is None:
            prop = doc.createElementNS(W, "w:" + name)
            props.appendChild(prop)
        prop.setAttribute("w:val", "1")

    def text(node):
        return "".join(t.firstChild.data for t in node.getElementsByTagName("w:t")
                       if t.firstChild is not None)

    stats = {"unsplit_rows": 0, "image_caption_links": 0,
             "table_caption_links": 0, "whole_short_table_groups": 0,
             "targeted_column_width_tables": 0}
    for row in doc.getElementsByTagName("w:tr"):
        flag(row, "trPr", "cantSplit")
        stats["unsplit_rows"] += 1
    for para in doc.getElementsByTagName("w:p"):
        if para.getElementsByTagName("w:drawing"):
            flag(para, "pPr", "keepNext")
            flag(para, "pPr", "keepLines")
            stats["image_caption_links"] += 1
        if re.match(r"^(?:Table\s*(?:[A-Z]?\d+)\.|表\s*(?:[A-Z]?\d+)\.)", text(para)):
            flag(para, "pPr", "keepNext")
            flag(para, "pPr", "keepLines")
            stats["table_caption_links"] += 1
    for table in doc.getElementsByTagName("w:tbl"):
        table_rows = [n for n in table.childNodes if n.nodeType == n.ELEMENT_NODE
                      and n.tagName == "w:tr"]
        cells = [n for n in table_rows[0].childNodes if n.nodeType == n.ELEMENT_NODE
                 and n.tagName == "w:tc"]
        header = [norm(text(cell)) for cell in cells]
        main = len(header) == 4 and header[0] in ("Frozenlibrary", "冻结技能库") and header[-1] == "Avg."
        control = len(header) == 5 and len(table_rows) == 4 and header[0] in ("Learningcondition", "学习条件")
        if main or control:
            for row in table_rows[:-1]:
                for para in row.getElementsByTagName("w:p"):
                    flag(para, "pPr", "keepNext")
            stats["whole_short_table_groups"] += 1
        formation = len(header) == 4 and header[-1] in ("Teacherresponses", "教师响应")
        ratios = (0.49, 0.17, 0.17, 0.17) if main else ((0.22, 0.36, 0.16, 0.26) if formation else None)
        if ratios is not None:
            columns = table.getElementsByTagName("w:gridCol")
            if len(columns) != len(ratios):
                raise ValueError("Unexpected column grid in a targeted review table")
            total = sum(int(c.getAttribute("w:w")) for c in columns)
            widths = [round(total * ratio) for ratio in ratios[:-1]]
            widths.append(total - sum(widths))
            for column, width in zip(columns, widths):
                column.setAttribute("w:w", str(width))
            for row in table_rows:
                row_cells = [n for n in row.childNodes if n.nodeType == n.ELEMENT_NODE
                             and n.tagName == "w:tc"]
                if len(row_cells) != len(widths):
                    raise ValueError("Unexpected merged cell in a targeted review table")
                for cell, width in zip(row_cells, widths):
                    properties = child(cell, "tcPr")
                    if properties is None:
                        properties = doc.createElementNS(W, "w:tcPr")
                        cell.insertBefore(properties, cell.firstChild)
                    cell_width = child(properties, "tcW")
                    if cell_width is None:
                        cell_width = doc.createElementNS(W, "w:tcW")
                        properties.appendChild(cell_width)
                    cell_width.setAttribute("w:w", str(width))
                    cell_width.setAttribute("w:type", "dxa")
            stats["targeted_column_width_tables"] += 1
    with tempfile.TemporaryDirectory(prefix="legal-docx-layout-", dir=path.parent) as temp:
        revised = Path(temp) / path.name
        with zipfile.ZipFile(revised, "w") as dest:
            for item, data in members:
                dest.writestr(item, doc.toxml(encoding="UTF-8")
                              if item.filename == "word/document.xml" else data)
        revised.replace(path)
    return stats


def export(source, lang, out, reference):
    ast = json.loads(run([PANDOC, "--from=markdown-implicit_figures", "--to=json", source]).stdout)
    original = copy.deepcopy(ast)
    # JSON readers do not parse CLI metadata strings as Markdown citations.
    # Let Pandoc itself construct the canonical wildcard citation metadata.
    metadata = json.loads(run([PANDOC, "--from=markdown", "--to=json"],
                              input=b"---\nnocite: '@*'\n---\n").stdout)["meta"]
    ast["meta"].update(metadata)
    assets = []
    for node in walk(ast["blocks"]):
        if node.get("t") == "Image":
            target = node["c"][2][0]
            image = (source.parent / target).resolve()
            if image.suffix.lower() == ".svg":
                image = image.with_name(image.stem + "_600dpi.png")
            elif image.name.endswith("_preview.png"):
                image = image.with_name(image.name.replace("_preview.png", "_600dpi.png"))
            if not image.is_file():
                raise FileNotFoundError(image)
            node["c"][2][0] = str(image)
            assets.append({"original_target": target, "rendered_path": str(image.relative_to(ROOT)), "sha256": sha(image)})
        elif node.get("t") == "Link" and node["c"][2][0].endswith(".bib"):
            node["c"][2][0] = BIB.name
    note = ("INITIAL DRAFT REVIEW — completed source-isolated IID comparison; independent learning repeats deferred."
            if lang == "en" else "完整初稿审阅版：来源隔离IID比较已完成；额外独立学习重复暂缓。")
    ast["blocks"].insert(0, {"t": "Para", "c": [{"t": "Strong", "c": [{"t": "Str", "c": note}]}]})
    stem = "utility_v6_working_" + lang
    docx = out / (stem + ".docx")
    result = run([PANDOC, "--from=json", "--to=docx", "--standalone", "--citeproc",
                  "--bibliography=" + str(BIB),
                  "--metadata=reference-section-title=" + ("References" if lang == "en" else "参考文献"),
                  "--metadata=lang=" + ("en-US" if lang == "en" else "zh-CN"),
                  "--reference-doc=" + str(reference), "--output=" + str(docx)],
                 input=json.dumps(ast, ensure_ascii=False).encode())
    layout = stabilize_review_layout(docx)
    with tempfile.TemporaryDirectory(prefix="legal-paper-lo-") as profile:
        converted = run(["/usr/bin/libreoffice", "-env:UserInstallation=" + Path(profile).as_uri(),
                         "--headless", "--convert-to", "pdf", "--outdir", out, docx])
    pdf = docx.with_suffix(".pdf")
    if not pdf.is_file():
        raise RuntimeError("LibreOffice did not produce the requested PDF")
    with zipfile.ZipFile(docx) as package:
        xml = ET.fromstring(package.read("word/document.xml"))
        word_text = "".join(node.text or "" for node in xml.iter("{" + W + "}t"))
        math_count = sum(1 for _ in xml.iter("{" + M + "}oMath"))
        table_count = sum(1 for _ in xml.iter("{" + W + "}tbl"))
        media = {n: hashlib.sha256(package.read(n)).hexdigest() for n in package.namelist() if n.startswith("word/media/")}
    expected_math = [n["c"] for n in walk(original["blocks"]) if n.get("t") == "Math"]
    expected_tables = sum(n.get("t") == "Table" for n in walk(original["blocks"]))
    missing_docx = [text for text in paragraph_text(original) if norm(text) not in norm(word_text)]
    plain = run(["/usr/bin/pdftotext", "-layout", pdf, "-"]).stdout.decode()
    raw_plain = run(["/usr/bin/pdftotext", "-raw", pdf, "-"]).stdout.decode()
    segments = [segment for text in paragraph_text(original, split_math=True) for segment in text.split("\0") if len(norm(segment)) >= 8]
    missing_pdf = [text for text in segments if norm(text) not in norm(plain) and norm(text) not in norm(raw_plain)]
    if len(assets) != 2 or any(asset["sha256"] not in media.values() for asset in assets):
        raise ValueError("A source figure was omitted or changed before embedding")
    if math_count != len(expected_math) or table_count != expected_tables:
        raise ValueError("Native mathematics or table count changed in DOCX")
    for title in ("Diagnostic Benchmark for Legal Reasoning", "Experiential Learners",
                  "Agentic Context Engineering", "Trajectory-Local Lessons",
                  "Scaling Agent Self-Evolving", "Behaviorally Validated Scope Expansion"):
        if norm(title).casefold() not in norm(word_text).casefold():
            raise ValueError("A cited bibliography entry was not rendered: " + title)
    shutil.copy2(source, out / (stem + ".source.md"))
    return {"source": str(source.relative_to(ROOT)), "source_sha256": sha(source),
        "docx": {"path": str(docx.relative_to(ROOT)), "sha256": sha(docx)},
        "pdf": {"path": str(pdf.relative_to(ROOT)), "sha256": sha(pdf)},
        "source_paragraphs_and_cells": len(paragraph_text(original)), "docx_missing_source_text": missing_docx,
        "pdf_source_segments": len(segments), "pdf_missing_segments": missing_pdf,
        "PDF_text_checked_in_layout_and_raw_cell_reading_order": True,
        "all_six_cited_primary_bibliography_entries_rendered": True,
        "source_math": expected_math, "native_OMML_math_count": math_count, "table_count": table_count,
        "figures": assets, "embedded_media_sha256": media, "layout_adjustments": layout,
        "pandoc_stderr": result.stderr.decode(), "libreoffice_stdout": converted.stdout.decode(),
        "libreoffice_stderr": converted.stderr.decode(),
        "status": "text_checked_pending_visual_review" if not missing_docx and not missing_pdf else "needs_text_review"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    out = args.output_directory.resolve()
    out.relative_to(ROOT / "artifacts/research/manuscript_review_20261030")
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in (*SOURCES.values(), BIB)}
    version = run([PANDOC, "--version"]).stdout.decode()
    if not version.startswith("pandoc 3.13\n"):
        raise ValueError("Use the isolated pinned document tool, not the training environment")
    out.mkdir(parents=True, exist_ok=False)
    reference = out / "review_reference.docx"
    make_reference(reference)
    shutil.copy2(BIB, out / BIB.name)
    shutil.copy2(Path(__file__), out / "render_source_snapshot.py")
    outputs = {lang: export(source, lang, out, reference) for lang, source in SOURCES.items()}
    if hashes != {str(p.relative_to(ROOT)): sha(p) for p in (*SOURCES.values(), BIB)}:
        raise ValueError("Scientific manuscript sources changed during export")
    manifest = {"at": datetime.now(timezone.utc).isoformat(), "classification": "Bilingual utility-method initial draft with completed source-isolated frozen comparison; extra independent learning builds deferred; not a submission.",
        "source_sha256": hashes, "renderer_sha256": sha(Path(__file__)), "pandoc_version": version,
        "pandoc_binary_sha256": sha(PANDOC), "reference_docx_sha256": sha(reference), "outputs": outputs,
        "new_prose_or_scores_written_to_source": False, "old_v023_renderer_and_paper_untouched": True,
        "no_training_model_teacher_TEST_access": True, "review_wrapper_and_bibliography_added_only_to_export": True}
    (out / "render_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({lang: {k: value[k] for k in ("pdf", "docx", "native_OMML_math_count", "table_count", "status", "docx_missing_source_text", "pdf_missing_segments")} for lang, value in outputs.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
