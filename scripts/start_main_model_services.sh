#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${project_root}/.venv/bin/python"
roles_file="${project_root}/configs/models/roles.yaml"
mode="${1:-start}"

if [[ "${mode}" != "start" && "${mode}" != "--check" ]]; then
    echo "Usage: bash scripts/start_main_model_services.sh [--check]" >&2
    exit 2
fi
if [[ ! -x "${python_bin}" ]]; then
    echo "Project Python executable not found: ${python_bin}" >&2
    exit 1
fi
if [[ ! -f "${roles_file}" ]]; then
    echo "Model role configuration not found: ${roles_file}" >&2
    exit 1
fi

# The formal wrapper must realize the frozen roles.yaml runtime, not an inherited
# debugging configuration.  Timeout is operational and may vary; parameters that
# change model identity, context capacity, concurrency, or memory allocation may not.
frozen_runtime_override_names=(
    LSG_JUDGE_VLLM_HOST
    LSG_JUDGE_VLLM_PORT
    LSG_JUDGE_VLLM_MAX_MODEL_LEN
    LSG_JUDGE_VLLM_MAX_NUM_SEQS
    LSG_JUDGE_VLLM_KV_CACHE_MEMORY_BYTES
    LSG_JUDGE_VLLM_STARTUP_GPU_MEMORY_UTILIZATION
    LSG_VLLM_HOST
    LSG_VLLM_PORT
    LSG_VLLM_MAX_MODEL_LEN
    LSG_VLLM_MAX_NUM_SEQS
    LSG_VLLM_KV_CACHE_MEMORY_BYTES
    LSG_VLLM_STARTUP_GPU_MEMORY_UTILIZATION
    LSG_VLLM_RUNTIME_RESERVE_BYTES
    LSG_VLLM_SAFETY_FREE_BYTES
)
active_runtime_overrides=()
for variable_name in "${frozen_runtime_override_names[@]}"; do
    if [[ -v "${variable_name}" ]]; then
        active_runtime_overrides+=("${variable_name}")
    fi
done
if (( ${#active_runtime_overrides[@]} )); then
    echo "Refusing frozen main-service start with LSG runtime overrides: ${active_runtime_overrides[*]}" >&2
    exit 1
fi

# Serialize the complete check -> cold start -> readiness transition.  This does
# not claim the GPU from unrelated projects; it prevents two invocations of this
# project's wrapper from both passing the same empty-card check.
service_lock_dir="${project_root}/runs/.locks"
service_lock_path="${service_lock_dir}/main_model_services.lock"
mkdir -p "${service_lock_dir}"
exec 9>"${service_lock_path}"
if ! flock -n 9; then
    echo "Another LegalSkillEvolve model-service check/start is already in progress." >&2
    exit 1
fi

mapfile -t role_values < <(
    "${python_bin}" - "${roles_file}" <<'PY'
from pathlib import Path
import sys
import yaml

roles_path = Path(sys.argv[1]).resolve()
root = roles_path.parents[2]
roles = yaml.safe_load(roles_path.read_text(encoding="utf-8"))["roles"]
for role_name in ("semantic_judge", "lawyer_policy"):
    role = roles[role_name]
    print(role["base_url"].rstrip("/"))
    print(role["model_id"])
    print(root / role["local_snapshot"])
    print(role["runtime_limits"]["kv_cache_memory_bytes"])
    print(role["runtime_limits"]["max_model_len"])
budget = yaml.safe_load(roles_path.read_text(encoding="utf-8"))["gpu_service_budget"]
print(budget["runtime_reserve_bytes"])
print(budget["post_start_free_floor_bytes"])
PY
)

if [[ "${#role_values[@]}" -ne 12 ]]; then
    echo "Could not resolve both model service contracts from ${roles_file}" >&2
    exit 1
fi

judge_base_url="${role_values[0]}"
judge_model="${role_values[1]}"
judge_snapshot="${role_values[2]}"
configured_judge_kv_bytes="${role_values[3]}"
judge_max_model_len="${role_values[4]}"
qwen_base_url="${role_values[5]}"
qwen_model="${role_values[6]}"
qwen_snapshot="${role_values[7]}"
configured_qwen_kv_bytes="${role_values[8]}"
qwen_max_model_len="${role_values[9]}"
configured_runtime_reserve_bytes="${role_values[10]}"
configured_safety_free_bytes="${role_values[11]}"
startup_timeout="${LSG_SERVICE_START_TIMEOUT_SECONDS:-300}"
judge_kv_bytes="${configured_judge_kv_bytes}"
qwen_kv_bytes="${configured_qwen_kv_bytes}"
runtime_reserve_bytes="${configured_runtime_reserve_bytes}"
safety_free_bytes="${configured_safety_free_bytes}"

verify_total_memory_budget() {
    local total_mib
    total_mib="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n 1 | tr -d ' ')"
    "${python_bin}" - \
        "${judge_snapshot}/model.safetensors.index.json" \
        "${qwen_snapshot}/model.safetensors.index.json" \
        "${judge_kv_bytes}" "${qwen_kv_bytes}" \
        "${runtime_reserve_bytes}" "${safety_free_bytes}" "${total_mib}" <<'PY'
import json
from pathlib import Path
import sys

judge_index, qwen_index = (Path(value) for value in sys.argv[1:3])
missing = [str(path) for path in (judge_index, qwen_index) if not path.is_file()]
if missing:
    raise SystemExit(f"Missing model weight index required for memory budgeting: {missing}")

judge_value = json.loads(judge_index.read_text())
qwen_value = json.loads(qwen_index.read_text())
missing_shards = [
    str(index.parent / name)
    for index, value in ((judge_index, judge_value), (qwen_index, qwen_value))
    for name in sorted(set(value.get("weight_map", {}).values()))
    if not (index.parent / name).is_file()
]
if missing_shards:
    raise SystemExit(f"Model snapshots are missing indexed weight shards: {missing_shards}")
judge_weights = int(judge_value["metadata"]["total_size"])
qwen_weights = int(qwen_value["metadata"]["total_size"])
judge_kv, qwen_kv, runtime_reserve, safety_free = map(int, sys.argv[3:7])
total = int(sys.argv[7]) * 1024 * 1024
required = judge_weights + qwen_weights + judge_kv + qwen_kv + runtime_reserve + safety_free
gib = 1024**3
print(
    "GPU memory budget: "
    f"weights={(judge_weights + qwen_weights) / gib:.2f} GiB, "
    f"KV={(judge_kv + qwen_kv) / gib:.2f} GiB, "
    f"runtime_reserve={runtime_reserve / gib:.2f} GiB, "
    f"post-start_free_floor={safety_free / gib:.2f} GiB, "
    f"required={required / gib:.2f} GiB, device={total / gib:.2f} GiB"
)
if required > total:
    raise SystemExit("Configured model services do not fit the total GPU memory budget")
PY
}

verify_post_start_free_memory() {
    local free_mib
    free_mib="$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -n 1 | tr -d ' ')"
    "${python_bin}" - "${free_mib}" "${safety_free_bytes}" <<'PY'
import sys

free_bytes = int(sys.argv[1]) * 1024 * 1024
floor = int(sys.argv[2])
if free_bytes < floor:
    raise SystemExit(
        f"Post-start GPU free memory {free_bytes / 1024**3:.2f} GiB is below "
        f"the configured safety floor {floor / 1024**3:.2f} GiB"
    )
print(f"Post-start GPU free memory: {free_bytes / 1024**3:.2f} GiB")
PY
}

verify_qwen_start_free_budget() {
    local free_mib
    free_mib="$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -n 1 | tr -d ' ')"
    "${python_bin}" - \
        "${qwen_snapshot}/model.safetensors.index.json" \
        "${qwen_kv_bytes}" "${runtime_reserve_bytes}" "${safety_free_bytes}" \
        "${free_mib}" <<'PY'
import json
from pathlib import Path
import sys

index = Path(sys.argv[1])
value = json.loads(index.read_text())
weights = int(value["metadata"]["total_size"])
kv, runtime_reserve, safety_free = map(int, sys.argv[2:5])
free = int(sys.argv[5]) * 1024 * 1024
required = weights + kv + runtime_reserve + safety_free
if free < required:
    raise SystemExit(
        "Refusing Qwen start: free GPU memory changed after judge readiness "
        f"({free / 1024**3:.2f} GiB free, {required / 1024**3:.2f} GiB required). "
        "An unrelated workload may have appeared."
    )
print(
    "Pre-Qwen free-memory check: "
    f"{free / 1024**3:.2f} GiB free, {required / 1024**3:.2f} GiB required"
)
PY
}

endpoint_has_model() {
    local base_url="$1"
    local expected_model="$2"
    local expected_root="$3"
    local expected_max_model_len="$4"
    "${python_bin}" - "${base_url}" "${expected_model}" \
        "${expected_root}" "${expected_max_model_len}" <<'PY' >/dev/null 2>&1
import json
from pathlib import Path
import sys
from urllib.request import ProxyHandler, build_opener

# Both services are bound to loopback.  Do not let workstation-wide proxy
# variables route readiness probes away from the local process.
opener = build_opener(ProxyHandler({}))
with opener.open(sys.argv[1].rstrip("/") + "/models", timeout=2) as response:
    payload = json.load(response)
cards = [item for item in payload.get("data", []) if str(item.get("id")) == sys.argv[2]]
if len(cards) != 1:
    raise SystemExit(1)
card = cards[0]
root_matches = Path(str(card.get("root"))).resolve() == Path(sys.argv[3]).resolve()
length_matches = card.get("max_model_len") == int(sys.argv[4])
raise SystemExit(0 if root_matches and length_matches else 1)
PY
}

wait_for_model() {
    local name="$1"
    local base_url="$2"
    local expected_model="$3"
    local expected_root="$4"
    local expected_max_model_len="$5"
    local pid="$6"
    local deadline=$((SECONDS + startup_timeout))

    while (( SECONDS < deadline )); do
        if endpoint_has_model "${base_url}" "${expected_model}" \
            "${expected_root}" "${expected_max_model_len}"; then
            echo "${name} ready: ${expected_model} at ${base_url}"
            return 0
        fi
        if ! kill -0 "${pid}" 2>/dev/null; then
            echo "${name} exited before its endpoint became ready (pid=${pid})." >&2
            return 1
        fi
        sleep 2
    done
    echo "Timed out after ${startup_timeout}s waiting for ${name} at ${base_url}." >&2
    return 1
}

judge_ready=false
qwen_ready=false
if endpoint_has_model "${judge_base_url}" "${judge_model}" \
    "${judge_snapshot}" "${judge_max_model_len}"; then
    judge_ready=true
fi
if endpoint_has_model "${qwen_base_url}" "${qwen_model}" \
    "${qwen_snapshot}" "${qwen_max_model_len}"; then
    qwen_ready=true
fi

echo "judge_ready=${judge_ready} model=${judge_model} endpoint=${judge_base_url}"
echo "qwen_ready=${qwen_ready} model=${qwen_model} endpoint=${qwen_base_url}"

if [[ "${mode}" == "--check" ]]; then
    [[ "${judge_ready}" == true && "${qwen_ready}" == true ]]
    exit
fi
if [[ "${judge_ready}" == true && "${qwen_ready}" == true ]]; then
    echo "Both configured services are already ready; no process was started."
    exit 0
fi
if [[ "${judge_ready}" != "${qwen_ready}" ]]; then
    echo "Refusing a partial model-service state (judge=${judge_ready}, Qwen=${qwen_ready})." >&2
    echo "Stop the lone configured service cleanly, then rerun from an empty card." >&2
    exit 1
fi

if [[ "${judge_ready}" != true || "${qwen_ready}" != true ]]; then
    if ! command -v nvidia-smi >/dev/null 2>&1; then
        echo "nvidia-smi is unavailable; refusing an unverified GPU service start." >&2
        exit 1
    fi
    verify_total_memory_budget
fi

gpu_processes="$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader 2>/dev/null || true)"
if [[ -n "${gpu_processes//[[:space:]]/}" ]]; then
    echo "Refusing to cold-start while unrelated GPU compute processes are active:" >&2
    echo "${gpu_processes}" >&2
    exit 1
fi

session_id="$(date '+%Y%m%d_%H%M%S_%N')_pid_$$"
session_dir="${project_root}/runs/service_logs/session_${session_id}"
mkdir -p "${project_root}/runs/service_logs"
if ! mkdir "${session_dir}"; then
    echo "Could not create a unique service-log session: ${session_dir}" >&2
    exit 1
fi
judge_pid=""
qwen_pid=""
started_judge=false

cleanup_owned_services() {
    local exit_code=$?
    trap - EXIT INT TERM
    if [[ -n "${qwen_pid}" ]] && kill -0 "${qwen_pid}" 2>/dev/null; then
        kill -TERM -- "-${qwen_pid}" 2>/dev/null || kill -TERM "${qwen_pid}" 2>/dev/null || true
    fi
    if [[ "${started_judge}" == true ]] && [[ -n "${judge_pid}" ]] && kill -0 "${judge_pid}" 2>/dev/null; then
        kill -TERM -- "-${judge_pid}" 2>/dev/null || kill -TERM "${judge_pid}" 2>/dev/null || true
    fi
    exit "${exit_code}"
}
trap cleanup_owned_services EXIT INT TERM

if [[ "${judge_ready}" != true ]]; then
    nohup setsid bash "${project_root}/scripts/start_judge_vllm_server.sh" \
        >"${session_dir}/judge_vllm.log" 2>&1 </dev/null 9>&- &
    judge_pid=$!
    started_judge=true
    printf '%s\n' "${judge_pid}" >"${session_dir}/judge.pid"
    wait_for_model "judge" "${judge_base_url}" "${judge_model}" \
        "${judge_snapshot}" "${judge_max_model_len}" "${judge_pid}"
fi

# An external service can be restarted after the initial empty-card check even
# though it does not honor this project's lock.  Rechecking the exact remaining
# memory budget catches that race before Qwen allocation begins.
verify_qwen_start_free_budget

nohup setsid env LSG_VLLM_KV_CACHE_MEMORY_BYTES="${qwen_kv_bytes}" \
    bash "${project_root}/scripts/start_vllm_server.sh" \
    >"${session_dir}/qwen_vllm.log" 2>&1 </dev/null 9>&- &
qwen_pid=$!
printf '%s\n' "${qwen_pid}" >"${session_dir}/qwen.pid"
wait_for_model "Qwen" "${qwen_base_url}" "${qwen_model}" \
    "${qwen_snapshot}" "${qwen_max_model_len}" "${qwen_pid}"
verify_post_start_free_memory

trap - EXIT INT TERM
printf '%s\n' "ready" >"${session_dir}/status"
echo "Both services are ready. Logs and owned PIDs: ${session_dir}"
