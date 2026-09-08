from __future__ import annotations

from pathlib import Path

import pytest

from scripts.audit_dlawbench import audit

ROOT = Path(__file__).resolve().parents[2]
REVISION = "9f6325f29f07b296fac110a6e1880bdd5d9ca538"
SNAPSHOT = ROOT / "data/raw/dlawbench" / REVISION


@pytest.mark.integration
def test_public_release_counts_and_hashes() -> None:
    if not SNAPSHOT.is_dir():
        pytest.skip("Run scripts/prepare_dlawbench.py first")
    result = audit(SNAPSHOT)
    assert result["jurisdictions"]["CN"]["cases"] == 30
    assert result["jurisdictions"]["US"]["cases"] == 30
    assert result["jurisdictions"]["CN"]["facts"] == 319
    assert result["integrity"]["record_hashes_valid"] is True
    assert result["domains"]["case_level_metadata_available"] is False
    assert result["release_gap"]["full_corpus_present"] is False
