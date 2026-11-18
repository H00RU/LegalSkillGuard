"""Replay exact and metamorphic validation on matched, actually read fee pairs."""

import json
import sqlite3

from experiments.convergence_airline_joint_relation import BAG
from experiments.convergence_airline_structured_update import LITERALS, compose_public_rules
from experiments.convergence_pilot_b0 import HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces.airline_public_fees import compile_rule
from legal_skill_guard.paired_interfaces.convergence_regression_controls import compare_audited_updates
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def replay():
    previous = ROOT / read(LITERALS)['artifact_root']
    bound = read(previous / 'binding.json')
    terminal = read(previous / 'terminal.json')
    pairs = read(previous / 'cases.json')
    if (terminal['status'] != 'completed' or digest(pairs) != bound['pairs_sha256']
            or not read(previous / 'reference_check.json')['source_compiled_matches_independent_case_reference']):
        raise ValueError('The common physical cases and independent reference audit must remain bound')
    measures = {value['source_sha256']: value for path in (previous / 'measurements').glob('*.json')
                for value in [read(path)]}
    references, verified = {}, {}
    candidates = {name: {} for name in ('incumbent', 'match_bag_max', 'unpaired_marginals')}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for pair in pairs:
            key = pair['original']['key']
            reads, physical_ids = [], []
            for side in ('original', 'edited'):
                source = pair[side]
                public = source['views'][0]['public']
                saved = measures[digest(source)]
                identity = saved['physical_call_id']
                status, physical_source, purpose, raw = db.execute(
                    'select status,source,purpose,result from calls where id=?', (identity,),
                ).fetchone()
                physical = json.loads(raw)
                rule = compile_rule(public['source_text'])
                prediction = compose_public_rules(json.loads(physical['content']), len(BAG.findall(public['facts'])), rule)
                if ((status, physical_source, purpose) != ('completed', key, 'skill_actor')
                        or physical['finish_reason'] != 'stop' or saved['production_error'] is not None
                        or prediction != saved['predictions'] or physical['usage'] != saved['usage']
                        or digest(rule) != bound['compiled_rule_sha256'][digest(source)]):
                    raise ValueError('Missing or inconsistent production execution for a paired observation')
                reads.append(prediction)
                physical_ids.append(identity)
            references[key] = dict(zip(('original', 'edited'), (
                pair['unchanged_fees'] + charge for charge in pair['allowed_surcharges']), strict=True))
            for name in candidates:
                mode = 'add_charges' if name == 'incumbent' else name
                row = {'original': reads[0][mode], 'edited': reads[1][mode], 'physical_call_ids': physical_ids}
                reported = next(item for item in terminal['evidence'][mode] if item['source'] == key)
                if [row['original'] - pair['unchanged_fees'], row['edited'] - pair['unchanged_fees']] != reported['actual_surcharge_signature']:
                    raise ValueError('Replayed projection lost its original terminal comparison')
                candidates[name][key] = row
                verified[name, key] = digest(row)
    results = compare_audited_updates(candidates, references, verify_read=lambda name, source, row:
                                      verified.get((name, source)) == digest(row))
    result = {'evidence': results, 'source_pair_binding_sha256': bound['pairs_sha256'],
              'original_terminal_sha256': sha(previous / 'terminal.json'),
              'scope': 'two audited Airline TRAIN pairs and one shared coordinate response per input',
              'relative_and_absolute_controls_share_actual_reads': True,
              'new_requests': 0, 'complete_20_source_external_selection': False}
    immutable_json(HANDOFF / 'external_same_read_pair_checks_20261118.json', result)
    print(json.dumps({k: v for k, v in results.items() if k != 'candidates'}, sort_keys=True))


if __name__ == '__main__':
    replay()
