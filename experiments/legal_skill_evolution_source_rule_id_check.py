"""One real retry for one changed evidence-ID interface; no teacher or labels."""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads
from legal_skill_guard.skill_evolution.teacher import reader_from_wire
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot


def read(p):return json.loads(p.read_text())


def main():
    root = Path(__file__).resolve().parents[1]
    original = Path('/home/yndx/hhy/legal-skill-redesign-20261109')
    previous = root / 'artifacts/legal_skill_evolution_source_rule_check_20261112'
    if not (previous / 'completed.json').exists():raise ValueError('Original controller must be terminal')
    keys = read(previous / 'protocol.json')['already_fixed_original_TRAIN_parents']
    run = 'legal_skill_evolution_source_rule_id_check_20261112';folder = root / 'artifacts' / run
    profile = read(original / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    raw = read(previous / 'FreeEvolution/teacher_B3.json')['value']['blocks'][0]['revisions'][1]['skill']
    reader = reader_from_wire(raw['reads'][0])
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py')) + [Path(__file__).resolve()]
    protocol = {'run_id': run, 'same_goal': True, 'goal_complete': False,
        'source': keys[0], 'previous_table': str(previous.relative_to(root) / 'FreeEvolution/B3_candidates/0.json'),
        'failure': 'The seed root READ returned support ID 149 although the local namespace maximum was 146; native sentence indices were also visible.',
        'change': 'Present only local support IDs to the model. Keep public native sentence mapping host-side. No value, program, bound or correctness check relaxed.',
        'workload': 'One existing source/root reader request, once; no teacher, new source or whole-table rerun.',
        'offline_regressions_passed': 91, 'executor_profile': profile['executor'], 'automatic_retries': 0,
        'no_native_labels_used': True,
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    immutable_json(folder / 'protocol.json', protocol)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (folder / 'completed.json').exists():return read(folder / 'completed.json')
        ledger_path = original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        before = physical_snapshot(ledger_path)
        if any(x.get('reserved', 0) for x in before.values()):raise ValueError('Reconcile pending requests first')
        ledger = EvolutionLedger(ledger_path, run_id=run, sources={'train': keys, 'dev': [], 'test': []}, binding=digest(protocol))
        executor = FrozenExecutor(ledger, folder, profile['executor'])
        source = next(s for s in read(original / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json') if s['key'] == keys[0])
        view = next(v for v in source['views'] if v['id'] == 'nda-5')
        try:
            values, event = FrozenReads(executor).read(source, view, question=reader['question'],
                fields=reader['fields'], locator=reader['source_locator'], purpose='skill_replay',
                require_rule_support=True, allow_unresolved=True,
                invocation_arguments={'current_question': view['public']['question']})
            result = {'values': values, 'event': event, 'interface_validation_passed': True}
        except Exception as e:
            result = {'error': type(e).__name__ + ': ' + str(e), 'interface_validation_passed': False}
        result.update(utc=datetime.now(timezone.utc).isoformat(), goal_complete=False,
                      ledger_before=before, ledger_after=physical_snapshot(ledger_path), new_teacher_calls=0,
                      not_a_replacement_for_the_previous_version_table=True)
        immutable_json(folder / 'completed.json', result)
        return result


if __name__ == '__main__':
    result = main();print(json.dumps({'completed': True, 'interface_validation_passed': result['interface_validation_passed'],
                                    'ledger': result['ledger_after'], 'goal_complete': False}))
