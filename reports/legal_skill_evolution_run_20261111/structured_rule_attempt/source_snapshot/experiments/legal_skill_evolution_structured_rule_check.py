"""Two already-fixed TRAIN source reads: records versus retained flat outputs."""
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

RUN = 'legal_skill_evolution_structured_rule_check_20261112'
FIELD = {'type': 'array',
    'question': 'One record per expressly stated disclosure permission or disclosure exception. Keep its actor, named recipients, context and attached conditions together. Do not infer a permission merely by reversing an obligation or prohibition.',
    'item_fields': [
        {'name': 'actor_terms', 'type': 'array', 'question': 'Literal actor or party terms to which this permission/exception applies. Do not invent an unstated organization or map a protected object to an actor.'},
        {'name': 'recipient_classes', 'type': 'array', 'question': 'Only classes of persons/entities explicitly allowed as recipients in this clause, expanding an explicitly defined group from its source definition. Exclude information categories, activities, and persons merely mentioned elsewhere. An empty list means no recipient classes are explicitly named here, not that disclosure is prohibited.'},
        {'name': 'conditions', 'type': 'array', 'question': 'The conditions and qualifications attached to this same permission, including purpose, need-to-know and safeguards where stated. Preserve the literal condition phrases; do not assert that any condition is satisfied.'},
        {'name': 'permission_context', 'type': 'string', 'question': 'The literal context of this permission or exception. An empty string means no separate context is stated, not unconditional permission.'},
        {'name': 'scope', 'type': 'string', 'question': 'The exact source heading or numbered clause containing this permission/exception.'}]}


def read(path):return json.loads(path.read_text())


def prepare(root, original):
    prior = root / 'artifacts/legal_skill_evolution_contract_updates_20261112/protocol.json'
    original_keys = read(prior)['previously_fixed_source_order']
    keys = original_keys[1:3]
    public_path = original / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    records = {s['key']: s for s in read(public_path)}
    if len(keys) != 2 or not all(k in records for k in keys):raise ValueError('Keep the already-fixed TRAIN parents')
    profile = read(original / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += list((root / 'tests').glob('test_skill_evolution_*.py')) + [Path(__file__).resolve()]
    folder = root / 'artifacts' / RUN
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'question': 'Can an explicit record shape prevent the observed conflation of recipient classes, protected objects and attached conditions in the two fixed source materials?',
        'source_selection': 'The d50 and 354 update parents of the already-fixed four-contract original TRAIN cohort; no additional source or seed.',
        'original_TRAIN_parents': keys, 'previous_fixed_cohort': original_keys,
        'field_specification': FIELD,
        'workload': 'One source-only READ for each of the two fixed materials, using one declared record-array field. Compare to already-retained flat READ values; do not regenerate the old condition. No teacher or native evaluation in this diagnostic.',
        'semantic_review': 'Inspect whether recipient classes are actors rather than protected information, definitions and clause qualifiers stay attached, and unsupported roles remain unstated. Current-source support IDs are evidence locations, not independent legal gold.',
        'decision': 'If source records are still semantically wrong, preserve them and diagnose before more generation. If usable, proceed to the necessary changed original-TRAIN program update with equal common support for strong controls; record-read success itself is not a method contribution.',
        'old_outputs_not_semantically_adapted': True, 'no_TEST_or_DEV_labels_read': True,
        'no_new_full_training_matrix_or_paper': True, 'automatic_retries': 0,
        'executor_profile': profile['executor'], 'offline_regressions_passed': 111,
        'public_TRAIN_sha256': hashlib.sha256(public_path.read_bytes()).hexdigest(),
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
    immutable_json(folder / 'protocol.json', protocol)
    return folder, protocol, profile, {k: records[k] for k in keys}


def run(root, original):
    folder, protocol, profile, sources = prepare(root, original)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (folder / 'completed.json').exists():return read(folder / 'completed.json')
        for name, sha in protocol['code_sha256'].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha:raise ValueError('Bound code changed: ' + name)
        ledger_path = original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        before_path = folder / 'ledger_before.json'
        before = read(before_path) if before_path.exists() else physical_snapshot(ledger_path)
        if any(x.get('reserved', 0) for x in physical_snapshot(ledger_path).values()):raise ValueError('Resolve pending physical calls first')
        immutable_json(before_path, before)
        ledger = EvolutionLedger(ledger_path, run_id=RUN, sources={'train': list(sources), 'dev': [], 'test': []}, binding=digest(protocol))
        executor = FrozenExecutor(ledger, folder, profile['executor'])
        reads = FrozenReads(executor)
        outcomes = {}
        for key, source in sources.items():
            path = folder / 'source_results' / (digest(key) + '.json')
            if path.exists():outcomes[key] = read(path);continue
            status = {'utc': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(),
                      'phase': 'source_rule_read', 'source': key, 'goal_complete': False}
            (folder / 'status.json').write_text(json.dumps(status, indent=2) + '\n')
            try:
                values, event = reads.read(source, source['views'][0], question=FIELD['question'],
                    fields={'disclosure_permissions': FIELD}, locator='Full supplied source; express disclosure permissions and their definitions/qualifiers.',
                    purpose='skill_replay', require_rule_support=True, allow_unresolved=True)
                outcome = {'source': key, 'values': values, 'event': event, 'semantic_review_pending': True}
            except Exception as error:
                outcome = {'source': key, 'error': type(error).__name__ + ': ' + str(error),
                           'event': getattr(error, 'event', None), 'semantic_review_pending': True}
            immutable_json(path, outcome);outcomes[key] = outcome
        after = physical_snapshot(ledger_path)
        if after['teacher']['total'] != before['teacher']['total']:raise ValueError('Unexpected teacher call')
        result = {'completed_utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
                  'protocol_hash': digest(protocol), 'outcomes': outcomes,
                  'ledger_before': before, 'ledger_after': after, 'new_teacher_calls': 0,
                  'semantic_review_pending': True}
        immutable_json(folder / 'completed.json', result)
        (folder / 'status.json').write_text(json.dumps({'phase': 'terminal_review_pending', 'pid': os.getpid(),
            'goal_complete': False, 'ledger_after': after}, indent=2) + '\n')
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('action', choices=['prepare', 'run'])
    args = parser.parse_args();root = Path(__file__).resolve().parents[1]
    original = Path('/home/yndx/hhy/legal-skill-redesign-20261109')
    if args.action == 'prepare':
        folder, protocol, _, _ = prepare(root, original)
        print(json.dumps({'protocol': str(folder / 'protocol.json'), 'hash': digest(protocol), 'planned_source_reads': 2}))
    else:
        result = run(root, original);print(json.dumps({'completed': True, 'goal_complete': False, 'ledger': result['ledger_after']}))
