# GPU 驱动诊断与修复记录

诊断日期：2026-08-07（Asia/Shanghai）

## 根因

- PCI 设备 `0000:00:1a.0` 可见，ID 为 `10de:2235`（NVIDIA A40 系列）。
- 修复前设备没有 `Kernel driver in use`。
- 运行内核为 `5.15.0-139-generic`，对应 headers 已安装。
- `/lib/modules/5.15.0-139-generic` 不存在 `nvidia*.ko`，`modinfo nvidia` 失败。
- DKMS 未安装，也没有任何由 dpkg 管理的 NVIDIA 驱动包。
- `/usr/bin/nvidia-smi` 与 NVML 是手工注入的 535.230.02 用户态文件；没有配套内核模块。
- 首次补齐 570 compute stack 后，未被包管理的 `libnvidia-cfg.so.1` 仍指向
  535.230.02；`nvidia-persistenced` 因此无法用 570 内核驱动枚举设备。
- Secure Boot kernel lockdown 为 `none`；nouveau 未加载，不是本次故障原因。

结论：故障是“仅有 NVIDIA 用户态工具，缺少内核驱动”，不是 CUDA Toolkit 故障。

## 选定方案

安装 Ubuntu archive 中的 570-server 计算栈：

- 当前硬件探测将 570 列为推荐分支；
- 使用 Canonical 为当前 kernel ABI 提供的预编译、签名模块，避免临时 DKMS 编译；
- 只安装 compute/NVML/nvidia-smi，不安装桌面和 32 位图形依赖；
- CUDA 12.2 要求 Linux driver >=525.60.13，570 对 CUDA 12.2 向后兼容。

APT dry-run：新增 9 个包、删除 0、升级 0。

## 唯一需要管理员权限的操作

```bash
bash /home/yndx/hhy/legal-skill-guard/scripts/admin_install_nvidia_driver.sh
```

脚本会请求一次 sudo，安装后立即加载模块，不自动重启。完整日志写入
`/var/log/legalskillguard-nvidia-driver-install.log`。

安装后以普通用户运行：

```bash
/home/yndx/hhy/legal-skill-guard/.venv/bin/python \
  /home/yndx/hhy/legal-skill-guard/scripts/verify_gpu_runtime.py
```

只有 `nvidia-smi`、CUDA Driver API 初始化和设备计数同时通过，才视为修复完成。

## 修复结果

修复完成时间：2026-08-07 22:22（Asia/Shanghai）。无需重启。

| 验证层 | 结果 |
|---|---|
| GPU / 显存 | NVIDIA A40，49140 MiB |
| 驱动 | 570.133.20 |
| NVIDIA cfg library | 570.133.20，由 `libnvidia-cfg1-570-server` 管理 |
| PCI 绑定 | `Kernel driver in use: nvidia` |
| 内核模块 | `nvidia`、`nvidia_modeset`、`nvidia_drm`、`nvidia_uvm` 已加载 |
| 设备节点 | `/dev/nvidia0`、`/dev/nvidiactl`、`/dev/nvidia-uvm*` 已创建 |
| CUDA Driver API | `cuInit=0`，设备数 1，Driver API 12.8 |
| CUDA Runtime 实算 | CUDA 12.2，1,048,576 元素向量加法及逐项结果校验通过 |
| NVIDIA daemon | `nvidia-persistenced.service` active，GPU 已注册，RPC 已初始化 |

机器可读证据保存在 `reports/artifacts/gpu_verification.json`。验证脚本会现场编译
`scripts/cuda_smoke_test.cu`，因此不仅检查设备枚举，还覆盖显存分配、主机与设备间拷贝、
kernel launch、同步和结果回传。

Ubuntu 提供的 unit 使用 `--no-persistence-mode`，因此服务正常运行时 `nvidia-smi` 的
Persistence Mode 仍显示 Disabled。这是发行版默认策略而不是故障，不影响 CUDA 计算；
本阶段不擅自更改服务器的长期功耗与持久化策略。

结论：原故障已解决，GPU 驱动不再阻塞项目后续基线实验。PyTorch、Transformers 和
vLLM 仍按模型与推理后端的兼容矩阵统一冻结，不以临时安装包代替可复现实验环境。
