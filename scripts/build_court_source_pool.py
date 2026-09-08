"""Collect and segment authoritative SPC typical-case pages for corpus annotation."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import time
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "configs/data/main_training_sources.json"
DEFAULT_OUTPUT_ROOT = ROOT / "data/source_pool"


class ZoomTextParser(HTMLParser):
    """Extract visible text from the court.gov.cn article body with line boundaries."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        if attrs_map.get("id") == "zoom":
            self.depth = 1
            return
        if self.depth:
            self.depth += 1
            if tag in {"br", "p", "div", "li", "h1", "h2", "h3", "strong"}:
                self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.depth and tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.depth:
            if tag in {"p", "div", "li", "h1", "h2", "h3", "strong"}:
                self.parts.append("\n")
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.depth:
            self.parts.append(data)


def normalize_text(value: str) -> str:
    value = html.unescape(value).replace("\u3000", " ").replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


CASE_MARKER = re.compile(
    r"(?:^|\n)\s*(?:案例\s*)?(?:[一二三四五六七八九十百]+|\d{1,3})[、：.:]?\s*", re.M
)
BASIC_MARKER = re.compile(
    r"[【\[（(]?\s*(?:[一二三四五六七八九十]|\d)?\s*[】\]）)]?[、.:：]?\s*(?:基本|简要)案情\s*[】\]]?"
)
RESULT_MARKER = re.compile(
    r"[【\[（(]?\s*(?:[一二三四五六七八九十]|\d)?\s*[】\]）)]?[、.:：]?\s*(?:(?:裁判|处理|调解)结果|协同协作履职情况)\s*[】\]]?"
)
END_MARKER = re.compile(
    r"[【\[（(]?\s*(?:[一二三四五六七八九十]|\d)?\s*[】\]）)]?[、.:：]?\s*(?:典型意义|案例分析|专家点评)\s*[】\]]?"
)


def _clean_heading(value: str) -> str:
    lines = [line.strip(" —-\t") for line in value.splitlines() if line.strip()]
    if not lines:
        return ""
    # Directory entries can precede the real heading. The nearest two concise lines are enough.
    lines = [line for line in lines if len(line) <= 180]
    return " —— ".join(lines[-2:])[-300:]


def segment_cases(text: str) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    basics = list(BASIC_MARKER.finditer(text))
    for index, basic in enumerate(basics):
        next_basic_start = basics[index + 1].start() if index + 1 < len(basics) else len(text)
        result = RESULT_MARKER.search(text, basic.end(), next_basic_start)
        following_end = END_MARKER.search(text, basic.end(), next_basic_start)
        previous_boundary = basics[index - 1].end() if index else 0
        prior_markers = list(CASE_MARKER.finditer(text, previous_boundary, basic.start()))
        heading_start = (
            prior_markers[-1].end()
            if prior_markers
            else max(previous_boundary, basic.start() - 400)
        )
        heading = _clean_heading(text[heading_start : basic.start()])
        if result is not None:
            facts = normalize_text(text[basic.end() : result.start()])
            adjudication_end = following_end.start() if following_end else next_basic_start
            adjudication = normalize_text(text[result.end() : adjudication_end])
            source_structure = "separate_adjudication"
        else:
            # Some SPC compilations narrate both the dispute and disposition under
            # “基本案情”.  Keep the authoritative paragraph intact rather than
            # inventing an arbitrary split; downstream annotation must cite spans.
            narrative_end = following_end.start() if following_end else next_basic_start
            facts = normalize_text(text[basic.end() : narrative_end])
            adjudication = facts
            source_structure = "outcome_embedded_in_narrative"
        if len(facts) < 80 or len(adjudication) < 50:
            continue
        cases.append(
            {
                "source_case_index": str(len(cases) + 1),
                "source_case_heading": heading or f"case_{len(cases) + 1}",
                "basic_facts": facts,
                "adjudication": adjudication,
                "source_structure": source_structure,
            }
        )
    return cases


def segment_reference_case(text: str) -> list[dict[str, str]]:
    """Segment the SPC 入库参考案例 layout without folding the outcome into facts."""

    basic_marker = "基本案情"
    result_marker = "陕西省西安市阎良区人民法院于"
    reason_marker = "裁判理由"
    essence_marker = "裁判要旨"
    starts = {
        "basic": text.find(basic_marker),
        "result": text.find(result_marker),
        "reason": text.find(reason_marker),
        "essence": text.find(essence_marker),
    }
    if not (
        0 <= starts["basic"] < starts["result"] < starts["reason"] < starts["essence"]
    ):
        raise ValueError(f"reference-case markers are missing or out of order: {starts}")
    return [
        {
            "source_case_index": "1",
            "source_case_heading": normalize_text(text[: starts["basic"]]),
            "basic_facts": normalize_text(
                text[starts["basic"] + len(basic_marker) : starts["result"]]
            ),
            "adjudication": normalize_text(
                text[starts["reason"] + len(reason_marker) : starts["essence"]]
            ),
            "source_structure": "separate_adjudication",
        }
    ]


def segment_hrss_labor_cases(text: str) -> list[dict[str, str]]:
    """Segment the MOHRSS-SPC labor-case layout.

    These jointly issued cases use ``基本案情 / 申请人请求 / 处理结果 /
    案例分析`` rather than the SPC typical-case ``基本案情 / 裁判结果 /
    典型意义`` layout.  Keep the party request in the factual section and the
    disposition plus analysis in the adjudication section; this avoids both
    dropping short dispositions and treating legal analysis as client facts.
    """

    headings = list(re.finditer(r"(?:^|\n)\s*案例\s*(\d+)\s*[.．、：:]\s*([^\n]+)", text))
    cases: list[dict[str, str]] = []
    for index, heading in enumerate(headings):
        block_end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = text[heading.end() : block_end]
        basic = re.search(r"(?:^|\n)\s*基本案情\s*(?:\n|$)", block)
        request = re.search(r"(?:^|\n)\s*(?:申请人|原告)请求\s*(?:\n|$)", block)
        result = re.search(r"(?:^|\n)\s*处理结果\s*(?:\n|$)", block)
        analysis = re.search(r"(?:^|\n)\s*案例分析\s*(?:\n|$)", block)
        if not basic or not request or not result or not analysis:
            continue
        if not (basic.end() <= request.start() < result.start() < analysis.start()):
            continue
        facts = normalize_text(block[basic.end() : result.start()])
        adjudication = normalize_text(block[result.end() :])
        if len(facts) < 80 or len(adjudication) < 80:
            continue
        cases.append(
            {
                "source_case_index": str(len(cases) + 1),
                "source_case_heading": normalize_text(heading.group(2)),
                "basic_facts": facts,
                "adjudication": adjudication,
                "source_structure": "hrss_request_result_analysis",
            }
        )
    return cases


def fetch(url: str, cache_path: Path) -> bytes:
    if cache_path.exists() and cache_path.stat().st_size > 1000:
        return cache_path.read_bytes()
    failures: list[str] = []
    for attempt in range(1, 6):
        result = subprocess.run(
            [
                "curl",
                "-L",
                "--fail",
                "--silent",
                "--show-error",
                "--connect-timeout",
                "10",
                "--max-time",
                "25",
                url,
            ],
            check=False,
            capture_output=True,
        )
        if result.returncode == 0 and result.stdout:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(result.stdout)
            return result.stdout
        failures.append(
            f"attempt={attempt},code={result.returncode},stderr="
            + result.stderr.decode("utf-8", errors="replace")[-300:]
        )
        time.sleep(attempt)
    raise RuntimeError(f"source fetch failed for {url}: {' | '.join(failures)}")


def extract_page(raw: bytes) -> tuple[str, str, str | None]:
    decoded = raw.decode("utf-8", errors="replace")
    title_match = re.search(r'<div class="title">(.*?)</div>', decoded, flags=re.S)
    title = normalize_text(re.sub(r"<[^>]+>", "", title_match.group(1))) if title_match else ""
    date_match = re.search(r"发布时间：\s*([0-9-]{10}(?:\s+[0-9:]{8})?)", decoded)
    published_at = date_match.group(1) if date_match else None
    parser = ZoomTextParser()
    parser.feed(decoded)
    return title, normalize_text("".join(parser.parts)), published_at


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="rebuild in memory and require every declared pool to match byte-for-byte",
    )
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    args.output_root.mkdir(parents=True, exist_ok=True)
    records_by_pool: dict[str, list[dict[str, object]]] = {}
    source_ids: set[str] = set()
    urls: set[str] = set()
    for source in catalog["sources"]:
        source_id = str(source["source_id"])
        source_url = str(source["url"])
        if source_id in source_ids or source_url in urls:
            raise SystemExit(f"duplicate source id or URL in catalog: {source_id}")
        source_ids.add(source_id)
        urls.add(source_url)
        pool_file = str(source.get("pool_file") or "")
        if Path(pool_file).name != pool_file or not pool_file.endswith(".jsonl"):
            raise SystemExit(f"unsafe or missing pool_file for {source_id}: {pool_file!r}")
        retrieved_at = str(source.get("retrieved_at") or "")
        if not retrieved_at:
            raise SystemExit(f"catalog must freeze retrieved_at for {source_id}")
        print(f"fetching {source['source_id']}...", flush=True)
        raw = fetch(
            source_url,
            ROOT / "data/source_pool/raw_pages" / f"{source_id}.html",
        )
        title, body, published_at = extract_page(raw)
        layout = str(source.get("layout") or "typical_cases")
        if layout == "typical_cases":
            cases = segment_cases(body)
        elif layout == "reference_case":
            cases = segment_reference_case(body)
        elif layout == "hrss_labor_cases":
            cases = segment_hrss_labor_cases(body)
        else:
            raise SystemExit(f"{source_id}: unsupported source layout {layout!r}")
        expected_count = int(source["expected_page_case_count"])
        if len(cases) != expected_count:
            raise SystemExit(
                f"{source_id}: parser produced {len(cases)} cases, expected {expected_count}"
            )
        declared_indices = source.get("case_indices")
        if declared_indices == "all":
            selected_indices = list(range(1, len(cases) + 1))
        elif (
            isinstance(declared_indices, list)
            and declared_indices
            and all(isinstance(index, int) for index in declared_indices)
            and len(declared_indices) == len(set(declared_indices))
        ):
            selected_indices = list(declared_indices)
        else:
            raise SystemExit(f"{source_id}: case_indices must be 'all' or unique integers")
        if any(index < 1 or index > len(cases) for index in selected_indices):
            raise SystemExit(f"{source_id}: case_indices fall outside parsed page")
        heading_overrides = {
            int(index): str(heading)
            for index, heading in (source.get("case_heading_overrides") or {}).items()
        }
        if set(heading_overrides) - set(range(1, len(cases) + 1)):
            raise SystemExit(f"{source_id}: heading override index falls outside parsed page")
        for index in selected_indices:
            case = dict(cases[index - 1])
            if index in heading_overrides:
                case["source_case_heading"] = heading_overrides[index]
            payload = {
                "source_id": source_id,
                "domain": source["domain"],
                "publisher": "Supreme People's Court of the People's Republic of China",
                "source_url": source_url,
                "source_page_title": title,
                "source_published_at": published_at,
                "retrieved_at": retrieved_at,
                "source_page_sha256": hashlib.sha256(raw).hexdigest(),
                **case,
            }
            payload["source_case_sha256"] = hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            records_by_pool.setdefault(pool_file, []).append(payload)

    mismatches: list[str] = []
    for pool_file, records in records_by_pool.items():
        output = args.output_root / pool_file
        serialized = "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records
        )
        if args.verify_only:
            if not output.is_file() or output.read_text(encoding="utf-8") != serialized:
                mismatches.append(pool_file)
        else:
            temporary = output.with_suffix(".jsonl.tmp")
            temporary.write_text(serialized, encoding="utf-8")
            temporary.replace(output)
    counts: dict[str, int] = {}
    all_records = [record for records in records_by_pool.values() for record in records]
    for record in all_records:
        counts[str(record["domain"])] = counts.get(str(record["domain"]), 0) + 1
    report = {
        "status": "passed" if not mismatches else "failed",
        "mode": "verify_only" if args.verify_only else "write",
        "cases": len(all_records),
        "pools": {name: len(records) for name, records in records_by_pool.items()},
        "domains": counts,
        "mismatched_pools": mismatches,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if mismatches:
        raise SystemExit("frozen source pools are not reproducible from catalog and raw pages")


if __name__ == "__main__":
    main()
