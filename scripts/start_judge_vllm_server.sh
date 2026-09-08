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

roles_path = Path(sys.argv[1]).resolve()
root = roles_path.parents[2]
role = yaml.safe_load(roles_path.read_text(encoding="utf-8"))["roles"]["semantic_judge"]
print(root / role["local_snapshot"])
print(role["model_id"])
print(role["runtime_limits"]["kv_cache_memory_bytes"])
print(role["runtime_limits"]["startup_gpu_memory_utilization"])
print(role["runtime_limits"]["max_model_len"])
print(role["runtime_limits"]["max_num_seqs"])
PY
)
if [[ "${#model_values[@]}" -ne 6 ]]; then
    echo "Could not resolve judge model contract from ${roles_file}" >&2
    exit 1
fi
model_path="${model_values[0]}"
served_model="${model_values[1]}"
configured_kv_bytes="${model_values[2]}"
configured_startup_utilization="${model_values[3]}"
configured_max_model_len="${model_values[4]}"
configured_max_num_seqs="${model_values[5]}"

if [[ ! -x "${vllm_bin}" ]]; then
    echo "vLLM executable not found: ${vllm_bin}" >&2
    exit 1
fi
if [[ ! -f "${model_path}/model.safetensors.index.json" ]]; then
    echo "Pinned gpt-oss-20b snapshot is incomplete: ${model_path}" >&2
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
    raise SystemExit(f"Pinned judge-model weight shards are incomplete: {missing}")
PY

exec "${vllm_bin}" serve "${model_path}" \
    --served-model-name "${served_model}" \
    --host "${LSG_JUDGE_VLLM_HOST:-127.0.0.1}" \
    --port "${LSG_JUDGE_VLLM_PORT:-8002}" \
    --dtype bfloat16 \
    --max-model-len "${LSG_JUDGE_VLLM_MAX_MODEL_LEN:-${configured_max_model_len}}" \
    --max-num-seqs "${LSG_JUDGE_VLLM_MAX_NUM_SEQS:-${configured_max_num_seqs}}" \
    --kv-cache-memory-bytes "${LSG_JUDGE_VLLM_KV_CACHE_MEMORY_BYTES:-${configured_kv_bytes}}" \
    --gpu-memory-utilization "${LSG_JUDGE_VLLM_STARTUP_GPU_MEMORY_UTILIZATION:-${configured_startup_utilization}}" \
    --seed 0 \
    --generation-config vllm \
    --reasoning-parser openai_gptoss \
    --enable-prefix-caching \
    --disable-uvicorn-access-log
