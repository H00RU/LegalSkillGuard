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
        "legal_skill_guard/experiment/storage.py",
        "legal_skill_guard/schemas/experiment.py",
        "legal_skill_guard/inference/openai_client.py",
        "scripts/qualify_client_simulator.py",
    )
    for relative in contract_paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")

    selector = {"model_id": "frozen-client"}
    disclosure = {"model_id": "qwen", "revision": "d1"}
    before = client_simulator_qualification_sha256(tmp_path, selector, disclosure)
    (tmp_path / contract_paths[3]).write_text("changed corpus", encoding="utf-8")
    after = client_simulator_qualification_sha256(tmp_path, selector, disclosure)

    assert before != after
