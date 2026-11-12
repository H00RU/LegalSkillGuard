"""Two fixed original-TRAIN source selections; no semantic-value generation."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot

RUN = 'legal_skill_evolution_fragment_preflight_20261112'
QUESTION = 'Locate the source text governing confidentiality/nondisclosure, its express disclosure permissions or exceptions, and the definitions needed to interpret those clauses. Select source spans only; do not decide any native hypothesis.'
FIELDS = {
    'nondisclosure_clauses': {'type': 'array', 'representation': 'source_spans',
        'question': 'Select the literal nondisclosure obligations and any expressly stated disclosure permissions/exceptions, preserving their attached qualifications and references. Select a governing clause even when it does not name Representatives. Do not select unrelated protected-information lists or notification duties as permissions.'},
    'party_and_recipient_definitions': {'type': 'array', 'representation': 'source_spans',
        'question': 'Select literal source definitions identifying the parties/roles and recipient groups used by the nondisclosure clauses. Definitions may be embedded in the operative clause. Select text, not a legal role-equivalence conclusion or an invented list. Use unknown if no relevant defining text can be located.'}}


def read(path):return json.loads(path.read_text())


def prepare(root, original):
    fixed = read(root / 'artifacts/legal_skill_evolution_contract_updates_20261112/protocol.json')['previously_fixed_source_order']
    keys = fixed[1:3]
    public = original / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    records = {s['key']: s for s in read(public)}
    if len(keys) != 2 or not all(k in records for k in keys):raise ValueError('Keep the same fixed original TRAIN parents')
    profile = read(original / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += list((root / 'tests').glob('test_skill_evolution_*.py')) + [Path(__file__).resolve()]
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'question': 'Can the frozen executor locate the relevant literal clauses/definitions when it does not have to synthesize legal role/permission values?',
        'original_fixed_TRAIN_parents': keys, 'previous_fixed_cohort': fixed,
        'fields': FIELDS, 'read_question': QUESTION,
        'workload': 'One two-field source-only selection for d50 and one for 354, the same two previously fixed original TRAIN materials. No new teacher, native evaluation, source or seed in this preflight. Previous semantic responses are retained rather than regenerated.',
        'host_binding': 'Only current-source span IDs are generated. Known selections bind exact full source text in source order. Unknown remains unresolved. No rule, class atom, role equivalence or absence is inferred by the binding code.',
        'decision': 'Inspect actual selected text and completeness before learned-program integration. Selection/type success is not legal correctness or Lift/CoRev success. If the required clauses cannot be selected, preserve the failure and diagnose before additional generation.',
        'all_controls_get_same_interface': True, 'native_admission_unchanged': True,
        'no_DEV_TEST_labels_training_matrix_or_paper': True, 'automatic_retries': 0,
        'offline_regressions_passed': 115, 'executor_profile': profile['executor'],
        'public_TRAIN_sha256': hashlib.sha256(public.read_bytes()).hexdigest(),
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
    folder = root / 'artifacts' / RUN;immutable_json(folder / 'protocol.json', protocol)
    return folder, protocol, profile, {k: records[k] for k in keys}


def run(root, original):
    folder, protocol, profile, records = prepare(root, original)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (folder / 'completed.json').exists():return read(folder / 'completed.json')
        for name, sha in protocol['code_sha256'].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha:raise ValueError('Bound code changed: ' + name)
        ledger_path = original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        if any(v.get('reserved', 0) for v in physical_snapshot(ledger_path).values()):raise ValueError('Reconcile pending calls first')
        before = folder / 'ledger_before.json'
        if not before.exists():immutable_json(before, physical_snapshot(ledger_path))
        ledger = EvolutionLedger(ledger_path, run_id=RUN, sources={'train': list(records), 'dev': [], 'test': []}, binding=digest(protocol))
        reads = FrozenReads(FrozenExecutor(ledger, folder, profile['executor']))
        outcomes = {}
        for key, source in records.items():
            path = folder / 'source_results' / (digest(key) + '.json')
            if path.exists():outcomes[key] = read(path);continue
            (folder / 'status.json').write_text(json.dumps({'pid': os.getpid(), 'utc': datetime.now(timezone.utc).isoformat(),
                'phase': 'source_fragment_selection', 'source': key, 'goal_complete': False}, indent=2) + '\n')
            try:
                values, event = reads.read(source, source['views'][0], question=QUESTION, fields=FIELDS,
                    locator='Complete supplied current source, including operative clauses, attached qualifications and definitions.',
                    purpose='skill_replay', require_rule_support=True, allow_unresolved=True)
                result = {'source': key, 'values': values, 'event': event, 'semantic_review_pending': True}
            except Exception as error:
                result = {'source': key, 'error': type(error).__name__ + ': ' + str(error),
                          'event': getattr(error, 'event', None), 'semantic_review_pending': True}
            immutable_json(path, result);outcomes[key] = result
        after = physical_snapshot(ledger_path)
        if after['teacher']['total'] != read(before)['teacher']['total']:raise ValueError('Unexpected teacher dispatch')
        result = {'completed_utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
            'outcomes': outcomes, 'ledger_before': read(before), 'ledger_after': after,
            'semantic_review_pending': True, 'protocol_hash': digest(protocol)}
        immutable_json(folder / 'completed.json', result)
        (folder / 'status.json').write_text(json.dumps({'pid': os.getpid(), 'phase': 'terminal_review_pending',
            'goal_complete': False, 'ledger_after': after}, indent=2) + '\n')
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('action', choices=['prepare', 'run']);args = parser.parse_args()
    root = Path(__file__).resolve().parents[1];original = root / 'history/fixed_study_20261111'
    completed = root / 'artifacts' / RUN / 'completed.json'
    if completed.exists():
        result = read(completed);protocol = read(completed.with_name('protocol.json'))
        if digest(protocol) != result['protocol_hash'] or set(result['outcomes']) != set(protocol['original_fixed_TRAIN_parents']):
            raise ValueError('Preserved completed preflight/protocol binding differs')
        print(json.dumps({'restored_completed_run': True, 'goal_complete': False,
            'tested_code_binding_sha256': digest(protocol['code_sha256']),
            'tested_code_files': len(protocol['code_sha256']), 'new_model_calls': 0,
            'recorded_ledger_after': result['ledger_after']}))
    elif args.action == 'prepare':
        folder, protocol, _, _ = prepare(root, original)
        print(json.dumps({'protocol': str(folder / 'protocol.json'), 'hash': digest(protocol), 'planned_source_selections': 2}))
    else:
        result = run(root, original);print(json.dumps({'completed': True, 'goal_complete': False, 'ledger': result['ledger_after']}))
