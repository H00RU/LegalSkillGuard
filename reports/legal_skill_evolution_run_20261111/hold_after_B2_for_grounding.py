"""Wait for the actual B2 update boundary; never kill an in-flight call."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v1'
ARMS = ('FreeEvolution', 'LiftOnly', 'CoRevOnly', 'Full', 'Lift+GenericJoint', 'AllPorts+CoRev')


def main():
    process = json.loads((FOLDER / 'live_process.json').read_text())
    while True:
        complete = all((FOLDER / arm / 'update_B2.json').exists() for arm in ARMS)
        if complete:
            reason = {'goal_status': 'active', 'reason': 'forward-only exact source quote transcription repair',
                'B2_all_six_updates_settled': True, 'past_results_preserved': True,
                'inflight_call_must_settle_before_code_changes': True,
                'created_utc': datetime.now(timezone.utc).isoformat()}
            (FOLDER / 'HOLD_GENERATION').write_text(json.dumps(reason, ensure_ascii=False, indent=2) + '\n')
            (FOLDER / 'B2_boundary_hold_requested.json').write_text(json.dumps(reason, ensure_ascii=False, indent=2) + '\n')
            print(json.dumps(reason), flush=True)
            return
        path = Path('/proc') / str(process['pid'])
        if not path.exists() or int((path / 'stat').read_text().rsplit(') ', 1)[1].split()[19]) != process['proc_start_ticks']:
            print(json.dumps({'goal_status': 'active', 'observation': 'original client is terminal before B2 boundary',
                              'no_restart_or_hold_performed': True}), flush=True)
            return
        time.sleep(1)


if __name__ == '__main__':main()
