#!/usr/bin/env bash
# Install the minimal Ubuntu-packaged NVIDIA compute stack for this host.
set -euo pipefail

driver_branch="${1:-570}"
expected_device="10de:2235"
install_log="/var/log/legalskillguard-nvidia-driver-install.log"

if [[ "$EUID" -ne 0 ]]; then
    echo "Root privileges are required; requesting sudo once." >&2
    exec sudo -- "$0" "$driver_branch"
fi

exec > >(tee -a "$install_log") 2>&1

echo "[$(date --iso-8601=seconds)] LegalSkillGuard NVIDIA driver repair started"

if [[ "$driver_branch" != "570" ]]; then
    echo "Refusing unreviewed branch '$driver_branch'; this host was audited for branch 570." >&2
    exit 64
fi

source /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "20.04" ]]; then
    echo "Expected Ubuntu 20.04, observed ${ID:-unknown} ${VERSION_ID:-unknown}." >&2
    exit 65
fi

kernel_release="$(uname -r)"
if [[ ! -d "/usr/src/linux-headers-${kernel_release}" ]]; then
    echo "Running-kernel headers are missing: ${kernel_release}" >&2
    exit 66
fi

if ! lspci -Dnns 00:1a.0 | grep -qi "$expected_device"; then
    echo "Expected NVIDIA PCI device ${expected_device} at 00:1a.0 was not found." >&2
    lspci -Dnn | grep -i nvidia || true
    exit 67
fi

exact_modules="linux-modules-nvidia-${driver_branch}-server-${kernel_release}"
tracking_modules="linux-modules-nvidia-${driver_branch}-server-generic-hwe-20.04"
packages=(
    "$exact_modules"
    "$tracking_modules"
    "libnvidia-cfg1-${driver_branch}-server"
    "libnvidia-compute-${driver_branch}-server"
    "nvidia-compute-utils-${driver_branch}-server"
    "nvidia-utils-${driver_branch}-server"
)

echo "OS: ${PRETTY_NAME}"
echo "Kernel: ${kernel_release}"
echo "GPU: $(lspci -Dnns 00:1a.0)"
echo "Installing: ${packages[*]}"

apt-get update
for package_name in "${packages[@]}"; do
    if ! apt-cache show "$package_name" >/dev/null 2>&1; then
        echo "Required package is unavailable: ${package_name}" >&2
        exit 68
    fi
done

DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${packages[@]}"

depmod -a "$kernel_release"
modprobe nvidia
modprobe nvidia_uvm

# Create device nodes if udev has not done so yet.
udevadm trigger --subsystem-match=pci --action=change || true
udevadm settle || true
nvidia-modprobe -u -c=0 || true

echo "Loaded modules:"
lsmod | grep '^nvidia' || true
echo "PCI binding:"
lspci -nnk -s 00:1a.0
echo "Driver version:"
cat /proc/driver/nvidia/version
echo "nvidia-smi:"
nvidia-smi

# The package's udev rule may try to start the daemon before /dev/nvidia* is
# ready. Retry only after nvidia-smi has proved that device initialization is
# complete, and do not hide a persistent service failure.
if systemctl list-unit-files nvidia-persistenced.service | grep -q '^nvidia-persistenced.service'; then
    systemctl reset-failed nvidia-persistenced.service || true
    systemctl restart nvidia-persistenced.service
    systemctl is-active --quiet nvidia-persistenced.service
fi

echo "[$(date --iso-8601=seconds)] NVIDIA driver repair completed successfully"
echo "Log: ${install_log}"
