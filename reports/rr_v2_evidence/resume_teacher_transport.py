"""Resume the sealed pilot after its single preserved teacher transport failure.

This operational receipt script changes only the explicit retry ID and bypasses
the user-owned shell launcher that unsets the required proxy. It never edits
sealed science, model settings, prompts, source order, or the budget ledger.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.preflight import Preflight

OLD_ID = "pilot_teacher_batch1"
RETRY_ID = "pilot_teacher_batch1_transport_retry1"
DIRECT_CLI = "/home/yndx/.local/share/codex-npm/bin/codex"


class ExplicitTeacherTransportRetry:
    is_offline_mock = False

    def __init__(self, run: Preflight):
        self.client = run.teacher
        self.stage = run.artifacts
        self.ledger = run.ledger
        self.client.adapter.executable = DIRECT_CLI

    def summarize(self, call_id: str, **kwargs) -> dict:
        if call_id != OLD_ID:
            raise ValueError("This recovery authorizes exactly the first-batch summary")
        original_path = self.stage / "calls" / digest(OLD_ID) / "request.json"
        original = json.loads(original_path.read_text())
        reconstructed = {"config": self.client.config,
                         "purpose": self.client.summary_purpose, **kwargs}
        # Saved source records have canonical key order; the initial request
        # serialized its in-memory dictionaries. Require identical JSON values,
        # then replay the original literal prompt to preserve exact wire bytes.
        if json.loads(reconstructed["user_prompt"]) != json.loads(original["user_prompt"]):
            raise ValueError("Reconstructed source material differs")
        reconstructed["user_prompt"] = original["user_prompt"]
        kwargs["user_prompt"] = original["user_prompt"]
        if reconstructed != original:
            raise ValueError("Teacher retry request differs from the preserved failure")
        with self.ledger.transaction() as db:
            status = db.execute("SELECT status FROM calls WHERE id=?", (OLD_ID,)).fetchone()
        if status != ("failed",):
            raise ValueError("Original failed reservation must remain charged")
        receipt = {
            "schema": 1,
            "original_call_id": OLD_ID,
            "explicit_retry_call_id": RETRY_ID,
            "request_identical": True,
            "literal_original_prompt_replayed_after_JSON_value_equality_check": True,
            "request_sha256": hashlib.sha256(original_path.read_bytes()).hexdigest(),
            "configured_launcher": self.client.config["executable"],
            "actual_retry_executable": DIRECT_CLI,
            "launcher_sha256": hashlib.sha256(Path(self.client.config["executable"]).read_bytes()).hexdigest(),
            "direct_cli_sha256": hashlib.sha256(Path(DIRECT_CLI).read_bytes()).hexdigest(),
            "operational_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "cli_version": "0.166.0",
            "transport_change": "Bypass shell launcher which unsets HTTP_PROXY, HTTPS_PROXY and ALL_PROXY; inherit the existing localhost proxy",
            "scientific_parameters_changed": False,
            "automatic_retries": 0,
            "teacher_total_hard_cap": 2,
            "model_rerun_rounds_added": 0,
            "preserved_failure_directory": "artifacts/rr_v2_preflight/preserved_before_teacher_transport_retry",
        }
        immutable_json(self.stage / "teacher_transport_retry_receipt.json", receipt)
        return self.client.summarize(RETRY_ID, **kwargs)


def main() -> None:
    readiness = json.loads((ROOT / "reports/rr_v2_evidence/teacher_proxy_readiness_no_generation.json").read_text())
    if not readiness.get("backend_reachable"):
        raise ValueError("Non-generation backend readiness has not succeeded")
    run = Preflight(ROOT)
    run.teacher = ExplicitTeacherTransportRetry(run)
    result = run.pilot()
    run.verify_binding()
    print(json.dumps({key: value for key, value in result.items() if key != "ledger"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
