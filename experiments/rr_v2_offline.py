"""Reproduce only RR-v2 offline acceptance; never dispatch model requests."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import platform
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from legal_skill_guard.rr.coverage import digest

ROOT = Path(__file__).resolve().parents[1]
TESTS = ["tests/test_rr_coverage.py", "tests/test_rr_interfaces.py",
         "tests/test_rr_ledger.py", "tests/test_rr_state_and_partitions.py",
         "tests/test_rr_adapters.py", "tests/test_rr_controls_and_scoring.py",
         "tests/test_rr_client_and_learning.py", "tests/test_rr_engine.py", "tests/test_rr_pipeline.py",
         "tests/test_rr_method_gaps.py", "tests/test_rr_formal_build.py"]


def main() -> int:
    os.chdir(ROOT)
    protocol = json.loads((ROOT / "reports/legalskillguard_rule_reasoning_protocol_v2.json").read_text())
    if protocol["execution_request"]["frozen_test_enabled"] or protocol['execution_request'].get('formal_eval_enabled',False):
        raise RuntimeError("Formal evaluation/test switches must remain disabled")
    if protocol['run_enabled'] and not protocol['execution_request']['full_build_enabled']:
        raise RuntimeError('Only the explicitly authorized build may be enabled')
    files = [*sorted((ROOT / "legal_skill_guard/rr").glob("*.py")),
             *sorted((ROOT / "experiments").glob("rr_v2*.py")),
             *sorted((ROOT / "tests/fixtures").glob("rr_*.json")),
             *(ROOT / t for t in TESTS), ROOT / "reports/legalskillguard_rule_reasoning_protocol_v2.json"]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    output = io.StringIO()
    # Network is disabled in the test process itself, not asserted from a mock
    # client result. Actual data acquisition runs in a separate explicit step.
    def deny_network(*args, **kwargs):
        raise RuntimeError("Network forbidden during offline semantic acceptance")
    with patch.object(socket.socket, "connect", deny_network), \
            patch.object(socket.socket, "connect_ex", deny_network), \
            contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        status = pytest.main(["-q", *TESTS])
    evidence = ROOT / "reports/rr_v2_evidence"
    evidence.mkdir(exist_ok=True)
    (evidence / "offline_latest.txt").write_text(output.getvalue())
    receipt = {"kind": "offline_implementation_acceptance_not_model_results",
               "exit_code": int(status), "python": platform.python_version(),
               "network_blocked": True, "executor_requests": 0, "teacher_requests": 0,
               "formal_run_enabled": False, "frozen_test_enabled": False,
               "files": hashes, "manifest_hash": digest(hashes),
               "log_sha256": hashlib.sha256(output.getvalue().encode()).hexdigest()}
    (evidence / "offline_latest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(output.getvalue(), end="")
    print("Receipt:", evidence / "offline_latest.json")
    return int(status)


if __name__ == "__main__":
    raise SystemExit(main())
