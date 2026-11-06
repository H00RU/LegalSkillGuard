"""Explicit bounded commands; this CLI has no formal training/test launch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from legal_skill_guard.rr.preflight import (
    Preflight,
    active_seal_path,
    create_seal,
    seal_parser_repair,
)
from legal_skill_guard.rr.repair import seal_native_contract_repair, seal_oracle_processing_repair

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["seal", "repair-parser", "repair-native-contract", "repair-oracle-processing", "thinking", "pilot", "status"])
    args = parser.parse_args()
    if args.command == "seal":
        seal = create_seal(ROOT)
        print(json.dumps({"sealed": True, "binding": seal["binding"], "formal_execution_enabled": False}, indent=2))
        return
    if args.command == "repair-parser":
        seal = seal_parser_repair(ROOT)
        print(json.dumps({"sealed_processing_repair": True, "binding": seal["binding"],
                          "generation_reruns": 0, "formal_execution_enabled": False}, indent=2))
        return
    if args.command == "repair-native-contract":
        seal = seal_native_contract_repair(ROOT)
        print(json.dumps({"sealed_native_contract_repair": True, "binding": seal["binding"],
                          "max_targeted_model_calls": 8, "formal_execution_enabled": False}, indent=2))
        return
    if args.command == "repair-oracle-processing":
        seal = seal_oracle_processing_repair(ROOT)
        print(json.dumps({"sealed_oracle_processing_repair": True, "binding": seal["binding"],
                          "additional_model_reruns": 0, "formal_execution_enabled": False}, indent=2))
        return
    if args.command == "status":
        config = json.loads((ROOT / "configs/rr_v2_preflight.json").read_text())
        directory = ROOT / config["artifact_directory"]
        seal_path = active_seal_path(directory)
        seal = json.loads(seal_path.read_text()) if seal_path.exists() else {}
        directory = directory / seal.get("processing_continuation", {}).get("artifact_subdirectory", "")
        print(json.dumps({"seal_exists": seal_path.exists(),
                          "thinking_complete": (directory / seal.get("wire_repair", {}).get("selection_file", "thinking_selection.json")).exists(),
                          "pilot_complete": (directory / "pilot_completion.json").exists(),
                          "formal_execution_enabled": False}, indent=2))
        return
    run = Preflight(ROOT)
    result = run.thinking() if args.command == "thinking" else run.pilot()
    print(json.dumps({k: v for k, v in result.items() if k != "ledger"}, indent=2))


if __name__ == "__main__":
    main()
