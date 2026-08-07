#!/usr/bin/env python3
"""Collect machine-readable host, Python, CUDA, and framework evidence."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> dict[str, Any]:
    executable = shutil.which(command[0])
    if executable is None and Path(command[0]).is_absolute() and Path(command[0]).is_file():
        executable = command[0]
    if executable is None:
        return {"command": command, "available": False, "returncode": None, "output": ""}
    completed = subprocess.run(
        [executable, *command[1:]],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    return {
        "command": command,
        "available": True,
        "returncode": completed.returncode,
        "output": completed.stdout.strip(),
    }


def package_versions() -> dict[str, str | None]:
    names = (
        "torch",
        "transformers",
        "vllm",
        "accelerate",
        "datasets",
        "pydantic",
        "PyYAML",
        "jsonschema",
        "numpy",
        "scipy",
        "scikit-learn",
        "pytest",
    )
    versions: dict[str, str | None] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def disk_record(path: Path) -> dict[str, int | str]:
    usage = shutil.disk_usage(path)
    return {
        "path": str(path),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


def collect(workspace: Path = ROOT) -> dict[str, Any]:
    """Collect evidence as a value so the Phase 0 orchestrator can reuse it."""

    nvcc = shutil.which("nvcc")
    if nvcc is None and Path("/usr/local/cuda/bin/nvcc").is_file():
        nvcc = "/usr/local/cuda/bin/nvcc"

    evidence = {
        "captured_at": datetime.now(UTC).isoformat(),
        "host": {
            "platform": platform.platform(),
            "kernel": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
        },
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
        },
        "disk": disk_record(workspace),
        "memory": run(["free", "-b"]),
        "gpu": {
            "nvidia_smi": run(["nvidia-smi"]),
            "pci_devices": run(["lspci"]),
            "loaded_kernel_modules": run(["lsmod"]),
            "nvidia_module_info": run(["modinfo", "nvidia"]),
            "proc_driver_version": (
                Path("/proc/driver/nvidia/version").read_text(encoding="utf-8").strip()
                if Path("/proc/driver/nvidia/version").is_file()
                else None
            ),
            "device_nodes": sorted(str(path) for path in Path("/dev").glob("nvidia*")),
        },
        "cuda": {
            "nvcc": run([nvcc or "nvcc", "--version"]),
            "cuda_home": str(Path("/usr/local/cuda").resolve())
            if Path("/usr/local/cuda").exists()
            else None,
        },
        "tools": {name: run([name, "--version"]) for name in ("git", "uv")},
        "packages": package_versions(),
    }
    pci_output = evidence["gpu"]["pci_devices"]["output"]
    evidence["gpu"]["nvidia_pci_detected"] = "NVIDIA" in pci_output
    evidence["gpu"]["runtime_usable"] = evidence["gpu"]["nvidia_smi"]["returncode"] == 0
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/artifacts/environment.json")
    args = parser.parse_args()

    evidence = collect(args.workspace)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "gpu_runtime_usable": evidence["gpu"]["runtime_usable"],
            }
        )
    )


if __name__ == "__main__":
    main()
