from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest
import yaml

from legal_skill_guard.data_visibility import Audience, assert_lawyer_view_safe, project_case

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs/data/main_corpus.yaml"
CORE = ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.jsonl"
PROVENANCE = ROOT / "data/training/legal_skill_guard_dlawbench_style_cn.provenance.jsonl"
SELECTION = ROOT / "data/manifests/main_corpus_selection.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_main_corpus_config_count_split_and_current_hashes() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    core = read_jsonl(CORE)
    provenance = read_jsonl(PROVENANCE)

    assert config["status"] == "frozen_128_cpu_audited_runtime_requalification_required"
    assert config["formal_cases"] == len(core) == len(provenance) == 128
    assert sum(item["split"] == "train" for item in provenance) == 128
    assert not [item for item in provenance if item["split"] != "train"]
    assert sha256(CORE) == config["hashes"]["core_sha256"]
    assert sha256(PROVENANCE) == config["hashes"]["provenance_sha256"]
    assert sha256(SELECTION) == config["hashes"]["selection_sha256"]
    assert config["source_pool_cases"] == 179
    assert config["selected_source_pages"] == 35
    assert config["fact_pairs"] == 852
    assert config["disputed_fact_pairs"] == 266
    assert config["undisputed_fact_pairs"] == 586
    assert config["expected_inquiries"] == 699
    assert config["memo_expectations"] == 683
    assert all(item["id"].startswith("lsg_cn_") for item in core)


def test_main_corpus_sources_partition_the_full_ordered_pool_without_overlap() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    exclusions = json.loads(
        (ROOT / config["exclusion_manifest"]).read_text(encoding="utf-8")
    )
    source_count = sum(len(read_jsonl(ROOT / path)) for path in config["source_pools"])
    selected = {item["source_line"] for item in selection["records"]}
    excluded_rows = [
        source_line
        for category in exclusions["categories"]
        for source_line in category["source_lines"]
    ]
    excluded = set(excluded_rows)

    assert source_count == exclusions["source_pool_cases"] == 179
    assert len(selected) == 128
    assert len(excluded_rows) == len(excluded) == exclusions["excluded_cases"] == 51
    assert selected.isdisjoint(excluded)
    assert selected | excluded == set(range(1, source_count + 1))


def test_main_corpus_split_is_grouped_by_official_page_and_covers_all_domains() -> None:
    provenance = read_jsonl(PROVENANCE)
    page_splits: dict[str, set[str]] = defaultdict(set)
    split_domains: dict[str, set[str]] = defaultdict(set)
    for item in provenance:
        page_splits[item["source"]["page_sha256"]].add(item["split"])
        split_domains[item["split"]].add(item["annotation"]["legal_domain"])

    assert len(page_splits) == 35
    assert not [page for page, splits in page_splits.items() if len(splits) > 1]
    assert len(split_domains["train"]) == 14
    assert "validation" not in split_domains


def test_main_corpus_lawyer_projection_excludes_all_hidden_labels() -> None:
    for case in read_jsonl(CORE):
        lawyer_view = project_case(case, Audience.LAWYER_AGENT)
        assert_lawyer_view_safe(lawyer_view)
        assert set(lawyer_view) == {"id", "jurisdiction", "language", "opening"}


def test_main_corpus_provenance_records_reconstruction_and_claim_boundary() -> None:
    for item in read_jsonl(PROVENANCE):
        pipeline = item["annotation_pipeline"]
        assert pipeline["authoring_model"] == "gpt-5.6-sol"
        assert pipeline["reasoning_effort"] == "high"
        assert pipeline["prior_rejected_draft_used_as_annotation_input"] is False
        assert pipeline["prior_rejected_draft_authoring_model"] == "gpt-5.4-mini"
        assert item["expert_validated"] is False


def test_casewise_and_contamination_reports_are_bound_to_current_corpus() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    casewise_path = ROOT / config["casewise_quality_report"]
    contamination_path = ROOT / config["contamination_report"]
    casewise = json.loads(casewise_path.read_text(encoding="utf-8"))
    contamination = json.loads(contamination_path.read_text(encoding="utf-8"))

    assert casewise["status"] == "passed"
    assert casewise["counts"]["cases"] == 128
    assert casewise["counts"]["evidence_quotes_verified"] == 1128
    assert casewise["splits"]["train_pages"] == 35
    assert len(casewise["splits"]["train_domains"]) == 14
    assert casewise["core_sha256"] == sha256(CORE)
    assert casewise["provenance_sha256"] == sha256(PROVENANCE)
    assert config["hashes"]["casewise_quality_report_sha256"] == sha256(casewise_path)

    assert contamination["status"] == "passed"
    assert contamination["selected_source_cases"] == 128
    assert contamination["formal_core_sha256"] == sha256(CORE)
    assert contamination["selection_sha256"] == sha256(SELECTION)
    assert config["hashes"]["contamination_report_sha256"] == sha256(contamination_path)

def test_source_catalog_freezes_pool_membership_and_retrieval_identity() -> None:
    catalog = json.loads(
        (ROOT / "configs/data/main_training_sources.json").read_text(encoding="utf-8")
    )
    assert len(catalog["sources"]) == 36
    assert len({item["source_id"] for item in catalog["sources"]}) == 36
    assert len({item["url"] for item in catalog["sources"]}) == 36
    for item in catalog["sources"]:
        assert item["pool_file"].endswith(".jsonl")
        assert item["case_indices"] == "all" or item["case_indices"]
        assert item["expected_page_case_count"] > 0
        assert item["retrieved_at"]


@pytest.mark.integration
def test_frozen_source_pools_rebuild_byte_for_byte() -> None:
    raw_pages = ROOT / "data/source_pool/raw_pages"
    if not raw_pages.is_dir() or len(list(raw_pages.glob("*.html"))) != 36:
        pytest.skip("Frozen court source pages are intentionally not included in the repository")
    result = subprocess.run(
        [sys.executable, "scripts/build_court_source_pool.py", "--verify-only"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
