#!/usr/bin/env bash
set -euo pipefail

# Only execution timing: the frozen Python entry verifies full eight-batch
# completion, preservation, source identity and the canonical lock itself.
while systemctl --user is-active --quiet legal-openexempt-ace-public-assets128-20261022-run02.service; do
    sleep 45
done

exec /media/sangfor/vdb/legal-skill-evolve/.venv/bin/python -u \
    -m experiments.openexempt_fixed_train_control run \
    /media/sangfor/vdb/legal-skill-evolve/configs/openexempt_fixed_static_train128_20261022_run01.json
