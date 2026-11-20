"""Attribute the locked DEV errors using the archived operative-edge wire responses."""

import json
import sqlite3
from collections import Counter

from experiments import convergence_revision6_maud_anchor_idempotence as idempotence
from experiments import convergence_revision6_maud_locked_operative_dev as locked
from experiments.convergence_pilot_b0 import HANDOFF, LEDGER, read, sha
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def run():
    root, spec, cases, wires, _, grade, proofs, formal = locked.prepare()
    pointer = read(locked.POINTER)
    terminal = verify(read(root / 'terminal.json'), 'terminal_sha256')
    file = root / 'sealed_predictions.json'
    if (pointer['terminal_sha256'] != terminal['terminal_sha256'] or sha(file) != terminal['predictions_sha256']
            or root.name != terminal['binding_sha256'] or sha(grade) != spec['DEV_grade_sha256']
            or terminal['TEST_opened']):
        raise ValueError('Use the completed locked DEV comparison and its original grade')
    bank = read(file)
    variant, groups, counts = {}, {}, Counter()
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for key, case in cases.items():
            identity = f'{locked.STAGE}-{root.name[:12]}:{digest(key)}:synthesized'
            encoded, = db.execute(
                "select result from calls where id=? and source=? and purpose='skill_dev' and status='completed'",
                (identity, key),
            ).fetchone()
            outcome = json.loads(encoded)
            raw, folded, _, error = idempotence.decode(case, wires[key]['synthesized'][1], 'synthesized', outcome)
            if raw != bank['raw']['synthesized'][key] or error:
                raise ValueError('The original decoder and actual physical reading must reproduce')
            variant[key] = folded
            anchors = case['public']['candidate_clause_anchors']
            old = locked.comparator.governors.anchors.inventory(case['public']['original_excerpts'])
            groups[key] = 'supplemented_anchors' if old != anchors else 'original_anchors'
            for row in json.loads(outcome['content'])['observations'].values():
                left, right = row['first'], row['second']
                exclusions = locked.measured.edges.EXCLUDED
                families = [anchors[value]['candidate_family'] if value in anchors else exclusions.get(value)
                            for value in (left, right)]
                counts.update({
                    'marker_pairs': 1,
                    'both_families_excluded': int({left, right} == set(exclusions)),
                    'repeated_family': int(families[0] is not None and families[0] == families[1]),
                    'identical_positive_anchor': int(left in anchors and left == right),
                    'unknown_slots': (left, right).count(None),
                })
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger != terminal['ledger']:
        raise ValueError('Keep this diagnostic in the unchanged continuous ledger')
    raw = {**bank['raw'], 'synthesized': variant}
    scope = locked.visible.common_scope(raw, {key: row['scope'] for key, row in proofs.items()})
    revised = locked.visible.common_scope(
        locked.visible.revise(scope, {key: row['visibility'] for key, row in proofs.items()}),
        {key: row['preamble'] for key, row in proofs.items()},
    )
    labels = read(grade)
    subgroup = {}
    for name in sorted(set(groups.values())):
        subset = {key: case for key, case in cases.items() if groups[key] == name}
        subgroup[name] = {
            'positions': [case['position'][0] for case in subset.values()],
            'correct_on_both_tasks': {
                role: sum(cell['answer'] == labels[key][locked.fit.TASKS[family]]['answer']
                          for key in subset for family, cell in rows[key].items())
                for role, rows in bank['same_information'].items()
            },
        }
    stats = locked.evaluate(cases, revised, labels, formal)
    record = {'fixed_DEV_terminal': terminal['terminal_sha256'], 'counts': dict(counts),
              'subgroup_original_native_results': subgroup,
              'duplicate_positive_anchor_replay': stats['paired_readers'],
              'new_requests': 0, 'TEST_opened': False}
    receipt = HANDOFF / 'revision6_maud_locked_operative_dev_readouts_20261120.json'
    tag = immutable_json(receipt, record)
    print(tag, dict(counts), subgroup)
    print('same-information correct after exact repeat collapse', stats['paired_readers']['correct'])


if __name__ == '__main__':
    run()
