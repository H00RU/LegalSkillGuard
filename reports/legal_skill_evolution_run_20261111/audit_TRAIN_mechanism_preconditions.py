"""Locate missing mechanism prerequisites using original TRAIN records only.

No new candidate execution, teacher/executor access, DEV or TEST reading.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.skill_evolution.objects import Library, coupled_blocks, digest

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent
ARMS = ('FreeEvolution', 'LiftOnly', 'CoRevOnly', 'Full', 'Lift+GenericJoint', 'AllPorts+CoRev')


def read(path):return json.loads(path.read_text())


def main():
    folder = ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v5'
    counts, packages, evidence = defaultdict(Counter), [], {}
    def cite(path):evidence[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for arm in ARMS:
        for path in sorted((folder / arm).glob('teacher_B[1-8].json')):
            reply = read(path);batch = int(path.stem.split('B')[1]);cite(path)
            old_path = folder / arm / f'B{batch - 1}.json';old = Library.load(old_path);cite(old_path)
            old_ports = sum(p['mode'] == 'skill' for s in old.skills.values() for p in s.inputs.values())
            blocks = sum(bool([b for b in coupled_blocks(s)
                if all(s.premises[n]['mode'] == 'constant' for n in b)]) for s in old.skills.values())
            counts[arm]['teacher_requests'] += 1
            counts[arm]['requests_with_old_dependency_ports'] += old_ports > 0
            counts[arm]['requests_with_constant_block_opportunities'] += blocks > 0
            for index, block in enumerate(reply['value']['blocks']):
                counts[arm]['raw_blocks'] += 1
                has_dependencies = False
                for revision in block['revisions']:
                    counts[arm]['raw_' + revision['operation']] += 1
                    ports = [p for p in revision['skill']['inputs'] if p['mode'] == 'skill']
                    counts[arm]['raw_dependency_ports'] += len(ports)
                    counts[arm]['raw_skills_with_dependency_ports'] += bool(ports)
                    has_dependencies |= bool(ports)
                if not has_dependencies:continue
                candidate_path = folder / arm / f'B{batch}_candidates/{index}.json'
                candidate = read(candidate_path);cite(candidate_path)
                if digest(candidate['raw_block']) != digest(block):
                    raise AssertionError('Raw dependency block is not its actual compiled candidate')
                if candidate.get('error') or len(candidate['revisions']) != len(block['revisions']):
                    raise AssertionError('Inspect a dependency proposal that failed compilation')
                compiled = {r['new']['id']: r['new'] for r in candidate['revisions']}
                for revision in block['revisions']:
                    for port in revision['skill']['inputs']:
                        if port['mode'] != 'skill':continue
                        actual = compiled[revision['skill']['id']]['inputs'][port['name']]
                        if any(actual[k] != port[k] for k in ('mode', 'skill_id', 'field', 'type')):
                            raise AssertionError('Compiler changed a declared dependency')
                table = candidate['table']
                if not table['complete']:raise AssertionError('Dependency package lacks its complete actual version table')
                all_new = (1 << len(candidate['revisions'])) - 1
                cells = {(c['mask'], c['source']): c for c in table['mixed_version_table']}
                trigger = table['trigger'];history = table['history']
                def gain(mask, source):return cells[mask, source]['native_parent_grade'] - cells[0, source]['native_parent_grade']
                uses = Counter()
                for source in trigger + history:
                    for view in cells[all_new, source]['trace']['views']:
                        for event in view['execution']['events']:
                            if event.get('kind') == 'USE':uses['trigger' if source in trigger else 'history'] += 1
                packages.append({'arm': arm, 'batch': batch, 'block': index,
                    'raw_operations': [r['operation'] for r in block['revisions']],
                    'skill_ids': [r['skill_id'] for r in candidate['revisions']],
                    'old_dependency_ports': old_ports, 'compiler_preserved_all_dependency_bindings': True,
                    'complete_version_table': True, 'classification': table['classification'],
                    'selected_mask': candidate['selected_mask'],
                    'all_new_trigger_mean_gain': sum(gain(all_new, s) for s in trigger) / len(trigger),
                    'all_new_minimum_history_change': min(gain(all_new, s) for s in history),
                    'all_new_USE_events_by_cohort': dict(uses),
                    'candidate_evidence': str(candidate_path.relative_to(ROOT))})
    for name in ('objects.py', 'patterns.py', 'revisions.py', 'study.py', 'teacher.py'):
        cite(ROOT / 'legal_skill_guard/skill_evolution' / name)
    for name in ('PLAN.md', 'METHOD_ACQUISITION.md', 'METHOD_EVOLUTION.md'):
        cite(ROOT / 'reports/legal_skill_evolution_plan_20261111' / name)
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        ledger = {role: db.execute('select count(*) from calls where role=?', (role,)).fetchone()[0]
                  for role in ('executor', 'teacher')}
        pending = db.execute("select count(*) from calls where status='reserved'").fetchone()[0]
    totals = Counter()
    for arm in ARMS:totals.update(counts[arm])
    result = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'new_candidate_executions': 0, 'DEV_files_opened': False, 'TEST_files_opened': False,
        'ledger_read_only': True, 'cumulative_physical_requests': ledger, 'pending': pending,
        'raw_counts_by_arm': {k: dict(v) for k, v in counts.items()}, 'totals': dict(totals),
        'dependency_packages': packages, 'evidence_sha256': evidence,
        'conclusions': [
            'Full generated no dependency-input skills; this is not evidence that the schema cannot represent dependencies.',
            'Other arms generated four dependency packages. The actual compiler preserved their bindings and the fixed runtime produced complete version tables.',
            'All four are creation packages. Even successful creation would not provide an old-skill co-revision witness.',
            'Every teacher request saw an old library without dependency ports. The required existing producer-consumer update object never entered the formal sequence.',
            'Twenty-five old-library snapshots had constant-block opportunities, but no dedicated Lift was proposed. An opportunity is not proof of useful semantic variation.',
            'No existing package is relabelled as a mechanism success, no missing semantics are fabricated, and the fixed study is not replayed.'],
        'goal_complete': False}
    assert totals['teacher_requests'] == 48 and totals['raw_create'] == 103 and totals['raw_revise'] == 6
    assert totals['raw_lift'] == 0 and totals['requests_with_constant_block_opportunities'] == 25
    assert totals['raw_dependency_ports'] == 20 and len(packages) == 4
    assert totals['requests_with_old_dependency_ports'] == 0
    assert all(set(p['raw_operations']) == {'create'} and p['selected_mask'] is None for p in packages)
    target = REPORT / 'TRAIN_mechanism_preconditions.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'teacher_requests': 48, 'raw_skill_proposals': 109,
        'dependency_packages': len(packages), 'dependency_ports': 20,
        'existing_dependency_update_opportunities': 0, 'new_model_calls': 0,
        'packages': [{k: v for k, v in p.items() if k not in ('skill_ids', 'candidate_evidence')} for p in packages]}))


if __name__ == '__main__':main()
