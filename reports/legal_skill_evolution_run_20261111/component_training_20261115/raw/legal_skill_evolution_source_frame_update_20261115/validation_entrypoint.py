"""Run the frozen validator with its already authorized two-teacher ledger policy."""
import fcntl
from functools import partial
from experiments import legal_skill_evolution_source_frame_update as stage
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger

# Acquisition stored concurrency=2 in the immutable ledger policy. The frozen
# validator omitted the argument, whose default=1 correctly raised BudgetError.
# Restore that identical policy; do not change a cap, source, binding or row.
stage.EvolutionLedger = partial(EvolutionLedger, teacher_concurrency=2)
with (stage.ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    stage.protocol()
    stage.validate()
