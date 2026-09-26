from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_formal_service_wrapper_rejects_runtime_overrides_before_gpu_checks() -> None:
    environment = dict(os.environ)
    environment["LSG_VLLM_MAX_MODEL_LEN"] = "1"

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/start_main_model_services.sh"), "--check"],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=10,
    )

    assert completed.returncode == 1
    assert "Refusing frozen main-service start with LSG runtime overrides" in (
        completed.stdout
    )
    assert "LSG_VLLM_MAX_MODEL_LEN" in completed.stdout


def test_service_children_close_the_startup_lock_descriptor(tmp_path: Path) -> None:
    script = (ROOT / "scripts/start_main_model_services.sh").read_text(
        encoding="utf-8"
    )
    assert script.count("9>&- &") == 2

    lock_path = tmp_path / "service.lock"
    holder = subprocess.run(
        [
            "bash",
            "-c",
            'exec 9>"$1"; flock -n 9; sleep 30 >/dev/null 2>&1 9>&- & echo "$!"',
            "lock-test",
            str(lock_path),
        ],
        text=True,
        capture_output=True,
        check=True,
        timeout=5,
    )
    child_pid = int(holder.stdout.strip())
    try:
        os.kill(child_pid, 0)
        reacquired = subprocess.run(
            ["flock", "-n", str(lock_path), "true"],
            check=False,
            timeout=5,
        )
        assert reacquired.returncode == 0
    finally:
        os.kill(child_pid, signal.SIGTERM)
