#!/usr/bin/env bash
# Complete the NVIDIA 570 compute stack and verify the persistence daemon.
set -euo pipefail
export LC_ALL=C

expected_version="570.133.20"
package_name="libnvidia-cfg1-570-server"

if [[ "$EUID" -ne 0 ]]; then
    echo "Root privileges are required; requesting sudo once." >&2
    exec sudo -- "$0"
fi

if [[ "$(cat /sys/module/nvidia/version 2>/dev/null || true)" != "$expected_version" ]]; then
    echo "Expected loaded NVIDIA module ${expected_version}; refusing a cross-version repair." >&2
    exit 70
fi

candidate="$(apt-cache policy "$package_name" | awk '/Candidate:/{print $2}')"
if [[ "$candidate" != "${expected_version}-0ubuntu0.20.04.1" ]]; then
    echo "Unexpected ${package_name} candidate: ${candidate:-none}" >&2
    exit 71
fi

DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$package_name"
ldconfig

cfg_target="$(readlink -f /usr/lib/x86_64-linux-gnu/libnvidia-cfg.so.1)"
if [[ "$cfg_target" != *"libnvidia-cfg.so.${expected_version}" ]]; then
    echo "libnvidia-cfg still has an unexpected target: $cfg_target" >&2
    exit 72
fi

systemctl reset-failed nvidia-persistenced.service || true
systemctl restart nvidia-persistenced.service
systemctl is-active --quiet nvidia-persistenced.service

nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv,noheader
echo "libnvidia-cfg: $cfg_target"
echo "nvidia-persistenced: $(systemctl is-active nvidia-persistenced.service)"
