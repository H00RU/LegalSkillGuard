"""Fit the unchanged ordinary evidence retriever with equal source-label access.

This is a future comparison artifact, never installed in the running method.
No query program, teacher, new encoder/model download or lawyer weight update.
No fitted-source correctness or held-out outcome is inspected by this command.
"""

# ruff: noqa: E402 -- Bind the authoritative project before importing its learner.
from __future__ import annotations

import pickle
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.evidence_programs import SCORER_PARAMETERS, fit_program_model
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


def main():
    config = read(ROOT / "artifacts/research/discriminative_evidence_skill_20261017/config_run03.json")
    manifest = read(ROOT / config["ordinary_manifest"])
    baseline_ids = manifest["seen_original_source_ids"]
    bank_ids = config["training_ids"]
    ids = baseline_ids + bank_ids
    assert len(ids) == len(set(ids)) == 44
    reserve = read(ROOT / "artifacts/research/discriminative_evidence_new_contracts_20261017/source_only_reserve32_selection.json")
    assert not set(ids) & set(reserve["selected_source_ids_in_fixed_order"])
    archive_path = ROOT / config["source_archive"]
    assert sha(archive_path) == config["source_archive_sha256"]
    import json

    with zipfile.ZipFile(archive_path) as archive:
        author = json.loads(archive.read("contract-nli/train.json"))
    originals = {r["id"]: r for r in author["documents"]}
    rows = [originals[d] for d in ids]
    implementation = {str(p.resolve()): sha(p) for p in (Path(__file__),
        ROOT / "legal_skill_guard/learning/evidence_programs.py", ROOT / "legal_skill_guard/_vendor/scienceclaw_contracts.py")}
    declaration = {"at": now(), "original_training_source_ids": ids,
        "fixed_ordinary_training_ids": baseline_ids, "additional_bank_training_ids": bank_ids,
        "parameters_unchanged_from_existing_retriever": SCORER_PARAMETERS,
        "source_rows_sha256": csha(rows), "source_archive_sha256": sha(archive_path),
        "implementation": implementation, "heldout_DEV_TEST_unopened": True,
        "no_new_generation_teacher_or_effect_based_selection": True,
        "not_a_replacement_for_running_fixed_M2": True,
        "future_comparison_matches_unique_source_label_access_not_compute_or_algorithm_capacity": True}
    RunStore.immutable_json(FOLDER / "declaration.json", declaration)
    start = time.monotonic()
    model = fit_program_model(rows, author["labels"], [])
    assert not model.programs and not model.queries
    assert len(model.scoring_pairs_) == 44 * 17
    path = FOLDER / "ordinary_equal_source_label44.pkl"
    with path.open("xb") as stream:
        pickle.dump(model, stream, protocol=pickle.HIGHEST_PROTOCOL)
    assert all(sha(p) == h for p, h in implementation.items())
    state = {"at": now(), "path": str(path.resolve()), "pickle_sha256": sha(path),
        "training_ids": ids, "original_training_rows_sha256": csha(rows),
        "parameters": SCORER_PARAMETERS, "programs": [], "queries": [],
        "original_scoring_pairs": len(model.scoring_pairs_), "fit_seconds": time.monotonic() - start,
        "no_current_or_reserved_source_native_effects_scored": True,
        "same_retriever_architecture_only_original_training_source_label_access_increased": True,
        "not_in_running_method_or_a_claim_of_improved_legal_metrics": True}
    RunStore.immutable_json(FOLDER / "ordinary_equal_source_label44.manifest.json", state)
    print(json.dumps(state, ensure_ascii=False))


if __name__ == "__main__":
    main()
