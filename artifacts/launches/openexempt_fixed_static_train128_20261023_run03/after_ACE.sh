#!/usr/bin/env bash
set -euo pipefail

# Timing only. The existing Python guard requires actual full completion and
# preservation before using the canonical lock or making any model request.
while systemctl --user is-active --quiet legal-openexempt-ace-public-assets128-20261023-run04.service; do
    sleep 45
done

exec /media/sangfor/vdb/legal-skill-evolve/.venv/bin/python -u \
    -m experiments.openexempt_fixed_train_control run \
    /media/sangfor/vdb/legal-skill-evolve/configs/openexempt_fixed_static_train128_20261023_run03.json
