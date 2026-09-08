#!/usr/bin/env python3
"""Verify NVIDIA kernel, NVML, CUDA Driver API, and real CUDA execution."""

from __future__ import annotations

import argparse
import ctypes
import json
import shutil
import subprocess
import tempfile
from ctypes import util as ctypes_util
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "reports" / "artifacts" / "gpu_verification.json"


def run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "output": completed.stdout.strip(),
    }


def cuda_driver_probe() -> dict[str, Any]:
    library_name = ctypes_util.find_library("cuda") or "libcuda.so.1"
    try:
        library = ctypes.CDLL(library_name)
    except OSError as exc:
        return {"library": library_name, "loaded": False, "error": str(exc)}

    init_code = int(library.cuInit(0))
    device_count = ctypes.c_int(-1)
    count_code = (
        int(library.cuDeviceGetCount(ctypes.byref(device_count))) if init_code == 0 else None
    )
    driver_version = ctypes.c_int(-1)
    version_code = (
        int(library.cuDriverGetVersion(ctypes.byref(driver_version))) if init_code == 0 else None
    )
    return {
        "library": library_name,
        "loaded": True,
        "cuInit_returncode": init_code,
        "cuDeviceGetCount_returncode": count_code,
        "device_count": device_count.value,
        "cuDriverGetVersion_returncode": version_code,
        "driver_api_version": driver_version.value,
    }


def cuda_runtime_smoke() -> dict[str, Any]:
    """Compile and execute a small CUDA kernel without adding Python GPU packages."""

    nvcc = shutil.which("nvcc")
    fallback = Path("/usr/local/cuda/bin/nvcc")
    if nvcc is None and fallback.is_file():
        nvcc = str(fallback)
    source = ROOT / "scripts" / "cuda_smoke_test.cu"
    if nvcc is None:
        return {"available": False, "error": "nvcc not found"}
    if not source.is_file():
        return {"available": False, "error": f"source not found: {source}"}

    with tempfile.TemporaryDirectory(prefix="legal-skill-guard-cuda-") as directory:
        binary = Path(directory) / "cuda_smoke"
        compile_result = run([nvcc, "-O2", "-o", str(binary), str(source)])
        execution = run([str(binary)]) if compile_result["returncode"] == 0 else None
    return {
        "available": True,
        "compile": compile_result,
        "execution": execution,
        "passed": bool(execution is not None and execution["returncode"] == 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    nvidia_smi = run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,uuid,driver_version,memory.total,persistence_mode",
            "--format=csv,noheader",
        ]
    )
    cuda = cuda_driver_probe()
    cuda_smoke = cuda_runtime_smoke()
    evidence = {
        "verified_at": datetime.now(UTC).isoformat(),
        "nvidia_smi": nvidia_smi,
        "kernel_modules": run(["bash", "-lc", "lsmod | grep '^nvidia'"]),
        "nvidia_persistenced": run(["systemctl", "is-active", "nvidia-persistenced.service"]),
        "pci_binding": run(["lspci", "-nnk", "-s", "00:1a.0"]),
        "device_nodes": sorted(str(path) for path in Path("/dev").glob("nvidia*")),
        "proc_driver_version": (
            Path("/proc/driver/nvidia/version").read_text(encoding="utf-8").strip()
            if Path("/proc/driver/nvidia/version").is_file()
            else None
        ),
        "cuda_driver_api": cuda,
        "cuda_runtime_smoke": cuda_smoke,
    }
    evidence["passed"] = bool(
        nvidia_smi["returncode"] == 0
        and cuda.get("cuInit_returncode") == 0
        and cuda.get("cuDeviceGetCount_returncode") == 0
        and cuda.get("device_count", 0) > 0
        and cuda_smoke.get("passed") is True
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    raise SystemExit(0 if evidence["passed"] else 1)


if __name__ == "__main__":
    main()
