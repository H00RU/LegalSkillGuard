from pathlib import Path

from legal_skill_guard.evaluation.qualification import (
    client_simulator_qualification_sha256,
)
from legal_skill_guard.utils.hashing import canonical_json_sha256


def test_canonical_json_hash_is_key_order_invariant() -> None:
    assert canonical_json_sha256({"a": 1, "b": 2}) == canonical_json_sha256({"b": 2, "a": 1})


def test_client_qualification_contract_is_bound_to_current_corpus(tmp_path: Path) -> None:
    contract_paths = (
        "configs/prompts/client_fact_selector_zh.txt",
        "configs/prompts/client_fact_disclosure_zh.txt",
        "configs/qualification/client_simulator_cases.json",
        "data/training/legal_skill_guard_dlawbench_style_cn.jsonl",
        "third_party/DLawBench/config/personas.json",
        "legal_skill_guard/environment/client_response.py",
        "legal_skill_guard/evaluation/qualification.py",
        "legal_skill_guard/inference/openai_client.py",
        "legal_skill_guard/schemas/state.py",
        "legal_skill_guard/text_normalization.py",
        "legal_skill_guard/utils/hashing.py",
        "scripts/qualify_client_simulator.py",
    )
    for relative in contract_paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")

    experiment = tmp_path / "configs/experiments/main_experiment.yaml"
    experiment.parent.mkdir(parents=True, exist_ok=True)
    experiment.write_text("execution:\n  client_selection_attempts: 2\n", encoding="utf-8")
    for relative in ("data/manifests/client.json", "data/manifests/qwen.json"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")

    selector = {"model_id": "frozen-client", "manifest": "data/manifests/client.json"}
    disclosure = {
        "model_id": "qwen",
        "revision": "d1",
        "manifest": "data/manifests/qwen.json",
    }
    before = client_simulator_qualification_sha256(tmp_path, selector, disclosure)
    (tmp_path / contract_paths[3]).write_text("changed corpus", encoding="utf-8")
    after = client_simulator_qualification_sha256(tmp_path, selector, disclosure)

    assert before != after

    unrelated = tmp_path / "legal_skill_guard/schemas/experiment.py"
    unrelated.parent.mkdir(parents=True, exist_ok=True)
    unrelated.write_text("trajectory schema 26", encoding="utf-8")
    scoped_before = client_simulator_qualification_sha256(tmp_path, selector, disclosure)
    unrelated.write_text("trajectory schema 27", encoding="utf-8")
    assert client_simulator_qualification_sha256(tmp_path, selector, disclosure) == scoped_before

    state_schema = tmp_path / "legal_skill_guard/schemas/state.py"
    state_schema.write_text("changed client state", encoding="utf-8")
    assert client_simulator_qualification_sha256(tmp_path, selector, disclosure) != scoped_before
