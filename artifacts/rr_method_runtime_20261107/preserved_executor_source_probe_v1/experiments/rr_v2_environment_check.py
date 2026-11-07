"""Read-only service/CLI readiness and tokenizer templates; no generation calls."""
from __future__ import annotations

import hashlib
import json
import subprocess
from importlib import metadata
from pathlib import Path
from urllib import request

from legal_skill_guard.inference.codex_cli_client import CodexCLIClient
from legal_skill_guard.rr.client import ExecutorClient
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.engine import messages

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = json.loads((ROOT / "configs/rr_v2_preflight.json").read_text())
    if config["formal_run_enabled"] or config["frozen_test_enabled"]:
        raise ValueError("Formal execution must stay disabled")
    client = ExecutorClient(None, ROOT / config["artifact_directory"], config["executor"])
    profiles = {}
    fixture = [{"role": "user", "content": "Tokenizer-only environment audit."}]
    opener = request.build_opener(request.ProxyHandler({}))
    for thinking in (True, False):
        tokens = client.tokenize(fixture, thinking=thinking)
        req = request.Request("http://127.0.0.1:8000/detokenize",
                              data=json.dumps({"model": config["executor"]["model"],
                                               "tokens": tokens["tokens"][-32:]}).encode(),
                              headers={"Content-Type": "application/json"}, method="POST")
        with opener.open(req, timeout=30) as response:
            text = json.load(response)["prompt"]
        profiles[str(thinking).lower()] = {
            "count": tokens["count"], "tokens_sha256": digest(tokens["tokens"]),
            "suffix_tokens": tokens["tokens"][-32:], "suffix_text": text,
            # This installed Qwen template leaves an open assistant prefix when
            # enabled; it does not preinsert <think>. The disabled profile
            # inserts an explicitly closed empty thinking block.
            "template_profile_observed": text.endswith("<|im_start|>assistant\n") if thinking
            else text.rstrip().endswith("</think>")}
    teacher = config["teacher"]
    adapter = CodexCLIClient(model=teacher["model"], executable=teacher["executable"],
                             reasoning_effort=teacher["reasoning_effort"], retries=0,
                             cache_root=ROOT / "artifacts/rr_v2_preflight/teacher_adapter_cache")
    service = subprocess.check_output(["systemctl", "--user", "show", "legal-qwen3-8b-phase-dispatch.service",
                                       "-p", "ActiveState", "-p", "SubState", "-p", "MainPID"], text=True)
    pid = int(next(line.split("=", 1)[1] for line in service.splitlines() if line.startswith("MainPID=")))
    packages = {p.metadata["Name"]: p.version for p in metadata.distributions(path=[str(ROOT / ".local-tools/rr-v2-deps")])}
    data = PreflightData(ROOT, ROOT / config["source_manifest"])
    source_context_checks = []
    for source_id in data.order:
        source = data.public(source_id)
        counts = {str(thinking).lower(): client.tokenize(messages(source), thinking=thinking)["count"]
                  for thinking in (True, False)}
        source_context_checks.append({"source": source_id, "prompt_tokens": counts,
                                      "output_cap": config["executor"]["max_tokens"],
                                      "within_context_both_profiles": all(
                                          n + config["executor"]["max_tokens"] <= config["executor"]["context_tokens"]
                                          for n in counts.values())})
    value = {"executor": client.readiness(), "teacher_authentication": adapter.preflight(),
             "teacher_model": teacher["model"], "teacher_reasoning_effort": teacher["reasoning_effort"],
             "tokenizer_profiles": profiles, "service": service.splitlines(),
             "model_pid": pid, "model_proc_start_ticks": Path(f"/proc/{pid}/stat").read_text().split()[21],
             "isolated_reference_dependencies": packages,
             "fixed_source_context_checks": source_context_checks,
             "tokenizer_profile_difference_observed": profiles["true"]["tokens_sha256"] != profiles["false"]["tokens_sha256"],
             "actual_generation_thinking_switch_verified": False,
             "note": "Tokenizer and authentication checks only; real paired generation still required",
             "executor_generations": 0, "teacher_generations": 0,
             "config_sha256": hashlib.sha256((ROOT / "configs/rr_v2_preflight.json").read_bytes()).hexdigest()}
    destination = ROOT / "reports/rr_v2_evidence/environment_no_generation.json"
    destination.write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"executor_ready": value["executor"]["ready"],
                      "teacher_authenticated": value["teacher_authentication"]["ready"],
                      "template_profiles_differ": value["tokenizer_profile_difference_observed"],
                      "executor_generations": 0, "teacher_generations": 0,
                      "receipt": str(destination)}, indent=2))


if __name__ == "__main__":
    main()
