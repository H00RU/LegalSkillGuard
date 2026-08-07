from __future__ import annotations

from pathlib import Path

import pytest

from scripts.prepare_lecode import EXPECTED_REVISION, prepare

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "third_party" / "LeCoDe"


@pytest.mark.integration
def test_lecode_public_checkout_records_gated_data_boundary(tmp_path: Path) -> None:
    if not SOURCE.is_dir():
        pytest.skip("Clone the official LeCoDe repository first")
    snapshot, manifest = prepare(SOURCE, tmp_path, EXPECTED_REVISION)
    assert manifest["revision"] == EXPECTED_REVISION
    assert manifest["access"]["status"] == "application_required"
    assert manifest["access"]["dataset_files_present"] is False
    assert manifest["access"]["redistribution_allowed"] is False
    assert (snapshot / "README.md").is_file()
    assert any((snapshot / "app_agreement").glob("*.pdf"))
