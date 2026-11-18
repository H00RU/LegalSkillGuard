"""Compare two M1 routing rules on settled, chronological TRAIN folds."""

import argparse
import json
import math
import sqlite3
from types import SimpleNamespace

from experiments.convergence_formal_b1_observe import POINTER as FIRST_OBSERVATION, load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_train_observe import pointer as observation_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces import diversity_claim_groups
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_training import RelationalInterfaceLibrary
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


DATASET = 'LegalBench_Diversity'
ORDINARY = 'common_teacher_skill_learning'
M1 = 'method_one_only'


def _profile(plan):
    return tuple(sorted(plan['choices'].items()))


def choose_against_incumbent(view, observations, native_controls, reader_condition, *, source_key):
    """Use the actual native fallback utility on the same paired TRAIN mothers."""
    by_profile = {_profile(plan): {} for plan in view['plans']}
    conditions = {_profile(plan): reader_condition(plan) for plan in view['plans']}
    for row in observations:
        profile = tuple(map(tuple, row['profile']))
        key = row['source']
        if (row['dataset'] != DATASET or key == source_key or key not in native_controls or profile not in conditions
                or row.get('reader_condition_sha256') != conditions[profile]):
            continue
        if key in by_profile[profile]:
            raise ValueError('A TRAIN mother cannot enter the matched cohort twice')
        by_profile[profile][key] = row
    paired = sorted(set.intersection(*(set(rows) for rows in by_profile.values()))) if by_profile else []
    if not paired:
        return None, {'paired_mothers': [], 'candidates': []}
    incumbent = math.fsum(native_controls[key] for key in paired) / len(paired)
    candidates = []
    for plan in view['plans']:
        profile = _profile(plan)
        rows = [by_profile[profile][key] for key in paired]
        score = math.fsum(row['native_utility'] for row in rows
                          if row['source_fidelity']['all_local_relations_source_faithful']) / len(rows)
        average_tokens = math.fsum(row['usage']['total_tokens'] for row in rows) / len(rows)
        candidates.append({'profile': profile, 'grounded_native': score, 'average_tokens': average_tokens,
                           'fixed_raw_reference': plan['is_correct_fixed_raw_control']})
    eligible = [r for r in candidates if not r['fixed_raw_reference'] and r['grounded_native'] > incumbent]
    best = min(eligible, key=lambda r: (-r['grounded_native'], r['average_tokens'], r['profile']), default=None)
    return (best['profile'] if best else None), {'paired_mothers': paired, 'candidates': candidates,
                                               'common_native': incumbent}


def _control(journal, batch):
    pointer = FIRST_OBSERVATION if batch == 1 else observation_pointer(batch)
    out = ROOT / read(pointer)['artifact_root']
    end = read(out / 'terminal.json')
    file = out / ('native_scores.json' if batch == 1 else 'native_scores/' + ORDINARY + '.json')
    rows = read(file)
    checksum = end['native_scores_sha256'] if batch == 1 else end['native_scores_sha256'][ORDINARY]
    if end['TEST_opened'] or digest(rows) != checksum:
        raise ValueError('Use only verified chronological TRAIN native scores')
    return {r['source']: r['native_utility'] for r in rows if r['dataset'] == DATASET}, {
        'terminal_sha256': sha(out / 'terminal.json'),
        'observations_sha256': journal._observations(ORDINARY, batch)['train_observation_sha256'],
        'program_sha256': digest(journal.library(ORDINARY, batch - 1)['programs'][DATASET]),
    }


def _verify_reads(rows):
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for observation in rows:
            saved = db.execute('select status,source,purpose,result from calls where id=?',
                               (observation['physical_call_id'],)).fetchone()
            if saved is None or saved[:3] != ('completed', observation['source'], 'skill_actor'):
                raise ValueError('Expected the exact completed TRAIN interface reading')
            response = json.loads(saved[3])
            if (digest(response['content']) != observation['response_content_sha256']
                    or response['usage'] != observation['usage']):
                raise ValueError('The recorded interface observation differs from the physical response')


def run(through):
    root = ROOT / read(BOOTSTRAP)['artifact_root']
    study = read(root / 'binding.json')
    batches = load_roster(study)
    journal = TrainingJournal(root, study, batches)
    provider = diversity_claim_groups.Provider()
    model = SimpleNamespace(executor=SimpleNamespace(config=study['executor']))
    controls = {n: _control(journal, n) for n in range(1, through + 1)}
    receipts = {n: journal._completed_batch(M1, n)['completed_batch_sha256'] for n in controls}
    final = journal.library(M1, through)['interface_library']['observations']
    _verify_reads(final)
    roster = [row['key'] for batch in batches for row in batch]
    folds = []
    for batch in range(2, through + 1):
        training = journal.library(M1, batch - 1)['interface_library']
        learner = RelationalInterfaceLibrary.restore(root, actor=model, train_sources=roster, snapshot=training)
        current_program = controls[batch][1]['program_sha256']
        history = {key: utility for n, (scores, proof) in controls.items() if n < batch
                   and proof['program_sha256'] == current_program for key, utility in scores.items()}
        for mother in batches[batch - 1]:
            if mother['dataset'] != DATASET:
                continue
            key = mother['key']
            view, = provider.views(mother)
            plan, _ = learner.choose(mother, view)
            current = None if plan['is_correct_fixed_raw_control'] else _profile(plan)
            proposed, support = choose_against_incumbent(view, learner.records, history, learner.reader_condition,
                                                        source_key=key)
            paid = {tuple(map(tuple, row['profile'])): row for row in final if row['source'] == key}
            if any(paid[_profile(p)]['plan_version'] != p['version'] for p in view['plans']):
                raise ValueError('The fold must score the originally executed candidate wire')

            def score(profile):
                if profile is None:
                    return {'native': controls[batch][0][key], 'source_faithful': None}
                row = paid[profile]
                return {'native': row['native_utility'], 'physical_call_id': row['physical_call_id'],
                        'source_faithful': row['source_fidelity']['all_local_relations_source_faithful']}

            folds.append({'batch': batch, 'source': key, 'source_sha256': digest(mother), 'current': score(current),
                          'incumbent_paired': score(proposed), 'common': score(None), 'current_profile': current,
                          'incumbent_paired_profile': proposed, 'prior_TRAIN_support': support})
    summary = {arm: {'native_correct': sum(row[arm]['native'] for row in folds),
                     'synthesized': sum(row[arm]['source_faithful'] is not None for row in folds),
                     'source_faithful': sum(row[arm]['source_faithful'] is True for row in folds)}
               for arm in ('common', 'current', 'incumbent_paired')}
    record = {'through_batch': through, 'study_binding_sha256': digest(study), 'update_receipts': receipts,
              'baseline_receipts': {n: entry[1] for n, entry in controls.items()},
              'summary': summary, 'folds': folds, 'TRAIN_targets_count': len(folds), 'new_model_calls': 0,
              'current_route_rule_edited': False, 'TEST_opened': False, 'DEV_opened': False}
    path = BASE / 'm1_incumbent_audit' / digest(record) / 'terminal.json'
    immutable_json(path, record)
    pointer = HANDOFF / f'M1_incumbent_through_B{through}_20261118.json'
    immutable_json(pointer, {'receipt': str(path.relative_to(ROOT)), 'summary': summary, 'TRAIN_targets_count': len(folds)})
    print(json.dumps(read(pointer), sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--through', type=int, choices=range(2, 9), required=True)
    run(parser.parse_args().through)
