"""Request a clean B3 boundary; never interrupt a model or pause the Goal."""
import json
from pathlib import Path
import time

from legal_skill_guard.rr.checkpoint import immutable_json

ROOT = Path(__file__).resolve().parents[2]
folder = ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v2'
identity = json.loads((folder / 'live_process.json').read_text())
arms = ('FreeEvolution', 'LiftOnly', 'CoRevOnly', 'Full', 'Lift+GenericJoint', 'AllPorts+CoRev')
while True:
    process = Path('/proc') / str(identity['pid'])
    if not process.exists() or int(process.joinpath('stat').read_text().split()[21]) != identity['proc_start_ticks']:
        raise SystemExit('Original client is terminal; inspect its result rather than launching another run')
    if all((folder / arm / 'update_B3.json').exists() for arm in arms):
        receipt = {'requested_unix': time.time(), 'completed_update_prefix': 3, 'goal_status': 'active',
            'reason': 'Install offline-verified two-teacher prefetch at a request boundary; preserve B0-B3.',
            'observer_does_not_terminate_inflight_calls': True, 'restart_old_client': False}
        immutable_json(folder / 'B3_boundary_hold_requested.json', receipt)
        (folder / 'HOLD_GENERATION').write_text('B3 source/teacher/library prefix is complete. Exit at next request boundary.\n')
        print(json.dumps(receipt), flush=True)
        break
    time.sleep(10)
