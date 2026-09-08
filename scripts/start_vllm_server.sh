#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
vllm_bin="${project_root}/.venv/bin/vllm"
python_bin="${project_root}/.venv/bin/python"
roles_file="${project_root}/configs/models/roles.yaml"

mapfile -t model_values < <(
    "${python_bin}" - "${roles_file}" <<'PY'
from pathlib import Path
import sys
import yaml

root = Path(sys.argv[1]).resolve().parents[2]
role = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))["roles"]["lawyer_policy"]
print(root / role["local_snapshot"])
print(role["model_id"])
print(role["runtime_limits"]["kv_cache_memory_bytes"])
print(role["runtime_limits"]["startup_gpu_memory_utilization"])
print(role["runtime_limits"]["max_model_len"])
print(role["runtime_limits"]["max_num_seqs"])
print(role["runtime_limits"]["guided_decoding_backend"])
print(str(role["runtime_limits"]["guided_decoding_disable_any_whitespace"]).lower())
PY
)
if [[ "${#model_values[@]}" -ne 8 ]]; then
    echo "Could not resolve lawyer model contract from ${roles_file}" >&2
    exit 1
fi
model_path="${model_values[0]}"
served_model="${model_values[1]}"
configured_kv_bytes="${model_values[2]}"
configured_startup_utilization="${model_values[3]}"
configured_max_model_len="${model_values[4]}"
configured_max_num_seqs="${model_values[5]}"
configured_guided_backend="${model_values[6]}"
configured_disable_any_whitespace="${model_values[7]}"

if [[ ! -x "${vllm_bin}" ]]; then
    echo "vLLM executable not found: ${vllm_bin}" >&2
    exit 1
fi
if [[ ! -f "${model_path}/model.safetensors.index.json" ]]; then
    echo "Pinned lawyer-model snapshot is incomplete: ${model_path}" >&2
    exit 1
fi
"${python_bin}" - "${model_path}" <<'PY'
import json
from pathlib import Path
import sys

snapshot = Path(sys.argv[1])
index = json.loads((snapshot / "model.safetensors.index.json").read_text())
shards = sorted(set(index.get("weight_map", {}).values()))
missing = [name for name in shards if not (snapshot / name).is_file()]
if not shards or missing:
    raise SystemExit(f"Pinned lawyer-model weight shards are incomplete: {missing}")
PY

args=(
    serve "${model_path}"
    --served-model-name "${served_model}"
    --host "${LSG_VLLM_HOST:-127.0.0.1}"
    --port "${LSG_VLLM_PORT:-8000}"
    --dtype bfloat16
    --max-model-len "${LSG_VLLM_MAX_MODEL_LEN:-${configured_max_model_len}}"
    --max-num-seqs "${LSG_VLLM_MAX_NUM_SEQS:-${configured_max_num_seqs}}"
    --seed 42
    --generation-config vllm
    --reasoning-parser qwen3
    --gpu-memory-utilization "${LSG_VLLM_STARTUP_GPU_MEMORY_UTILIZATION:-${configured_startup_utilization}}"
    --enable-prefix-caching
    --disable-uvicorn-access-log
    --guided-decoding-backend "${configured_guided_backend}"
)
if [[ "${configured_disable_any_whitespace}" == "true" ]]; then
    args+=(--guided-decoding-disable-any-whitespace)
elif [[ "${configured_disable_any_whitespace}" != "false" ]]; then
    echo "Invalid guided_decoding_disable_any_whitespace value: ${configured_disable_any_whitespace}" >&2
    exit 1
fi
args+=(
    --kv-cache-memory-bytes "${LSG_VLLM_KV_CACHE_MEMORY_BYTES:-${configured_kv_bytes}}"
)

exec "${vllm_bin}" "${args[@]}"
