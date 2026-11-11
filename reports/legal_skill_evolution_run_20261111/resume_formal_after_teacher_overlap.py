"""Continue the same eight-batch pass after the verified B3 request boundary."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
ARMS = ('NoSkill', 'FreeEvolution', 'LiftOnly', 'CoRevOnly', 'Full', 'Lift+GenericJoint', 'AllPorts+CoRev')


def load(path):return json.loads(path.read_text())


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old = ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v2'
    new = ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v3'
    if not (old / 'B3_boundary_hold_requested.json').exists():raise ValueError('The verified B3 boundary has not been reached')
    process = load(old / 'live_process.json')
    path = Path('/proc') / str(process['pid'])
    if path.exists():
        fields = (path / 'stat').read_text().rsplit(') ', 1)[1].split()
        if int(fields[19]) == process['proc_start_ticks'] and fields[0] != 'Z':
            raise ValueError('The original client is still live; wait for its request-boundary exit')
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():raise ValueError('A physical request is still in flight')
        before = db.execute('select role,status,count(*) from calls group by role,status').fetchall()
    first = load(ROOT / 'configs/legal_skill_evolution_formal_v2_20261111.json')
    second = load(ROOT / 'configs/legal_skill_evolution_formal_v3_20261111.json')
    for field in ('executor', 'teacher', 'schedule', 'arms', 'curve_arms', 'selection_grade'):
        if first[field] != second[field]:raise ValueError('Forward formatting repair changed fixed protocol: ' + field)
    for arm in ARMS:
        if not (old / arm / 'B3.json').exists():raise ValueError('B3 prefix library is incomplete: ' + arm)
        if arm != 'NoSkill' and not (old / arm / 'update_B3.json').exists():
            raise ValueError('An original B3 update remains unfinished')
    paths = []
    for arm in ARMS:paths.extend((old / arm).rglob('*.json'))
    for folder in ('dev', 'view_results', 'native_direct_baselines'):
        paths.extend((old / folder).rglob('*.json'))
    paths.append(old / 'preflight.json')
    files = []
    for source in sorted(set(paths)):
        target = new / source.relative_to(old)
        if target.exists() and sha(target) != sha(source):raise ValueError('Existing resumed state differs: ' + str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files.append({'source': str(source.relative_to(ROOT)), 'destination': str(target.relative_to(ROOT)),
                      'sha256': sha(source)})
    for arm in ARMS:
        if sha(old / arm / 'B3.json') != sha(new / arm / 'B3.json'):raise ValueError('B3 library was not preserved exactly')
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        if db.execute('select role,status,count(*) from calls group by role,status').fetchall() != before:
            raise ValueError('Physical ledger changed during offline state import')
    receipt = {'imported_utc': datetime.now(timezone.utc).isoformat(), 'same_goal_and_training_pass': True,
        'new_model_calls': 0, 'completed_batch_prefix': 3,
        'B3_library_files_identical': True, 'native_inputs_model_configs_and_schedule_unchanged': True,
        'completed_sources_and_partial_DEV_or_next_batch_view_cache_preserved': True,
        'preflight_reused_because_native_payload_context_and_model_configuration_unchanged': True,
        'teacher_model_configuration_unchanged': True, 'teacher_proposal_workers': 2, 'executor_workers': 1,
        'teacher_adapter_cache_not_copied': True, 'original_calls_remain_in_original_physical_ledger': True,
        'ledger_counts_unchanged': before, 'copied_files': files}
    (new / 'state_import.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    (Path(__file__).with_name('formal_teacher_overlap_state_import.json')).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'completed_batch_prefix': 3, 'files_preserved': len(files), 'new_model_calls': 0,
                      'same_goal_and_training_pass': True}))


if __name__ == '__main__':main()
