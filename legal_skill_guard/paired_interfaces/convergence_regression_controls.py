"""Candidate validation controls on the same audited original/edit reads."""

import math


def compare_audited_updates(candidates, references, *, verify_read):
    """Compare native selection, absolute regression and fixed metamorphic checks.

    References are independently audited TRAIN pairs with an exact original and
    edited native integer outcome. A group with unresolved absolute semantics
    cannot act as absolute native feedback in these controls.
    """
    if 'incumbent' not in candidates or len(candidates) < 2 or not references:
        raise ValueError('Compare an incumbent and at least one candidate on fixed audited pairs')
    expected_keys = set(references)
    results = {}
    incumbent = candidates['incumbent']
    for name, rows in candidates.items():
        if set(rows) != expected_keys:
            raise ValueError('All comparison rules require identical audited pairs')
        audit = {}
        for source, row in rows.items():
            reference = references[source]
            expected = (reference['original'], reference['edited'])
            if any(type(value) is not int for value in expected):
                raise ValueError('An audited absolute regression pair needs two exact integer outcomes')
            observed = (row['original'], row['edited'])
            if verify_read(name, source, row) is not True:
                raise ValueError('A candidate lost actual paired execution provenance')
            original = (incumbent[source]['original'], incumbent[source]['edited'])
            correct = tuple(type(a) is int and a == b for a, b in zip(observed, expected, strict=True))
            old_correct = tuple(type(a) is int and a == b for a, b in zip(original, expected, strict=True))
            changes = tuple(a != b or type(a) is not type(b) for a, b in zip(observed, original, strict=True))
            audit[source] = {'absolute_native': list(correct), 'incumbent_absolute_native': list(old_correct),
                             'changed_outcome': list(changes),
                             'no_absolute_regression': all(not before or after
                                                           for before, after in zip(old_correct, correct, strict=True)),
                             'new_correctness_on_edited_pair': any(after and not before
                                                                  for before, after in zip(old_correct, correct, strict=True)),
                             'metamorphic_pass': (all(type(x) is int for x in observed)
                                                  and observed[1] - observed[0] == expected[1] - expected[0])}
        results[name] = {'pairs': audit,
                         'original_mean': math.fsum(row['absolute_native'][0] for row in audit.values()) / len(audit),
                         'regression_gate': all(row['no_absolute_regression'] for row in audit.values()),
                         'metamorphic_passes': sum(row['metamorphic_pass'] for row in audit.values())}
    base = results['incumbent']
    ordered = sorted((name for name in candidates if name != 'incumbent'),
                     key=lambda name: (-results[name]['original_mean'], name))
    improved = [name for name in ordered if results[name]['original_mean'] > base['original_mean']]
    return {'native_only_choice': next(iter(improved), 'incumbent'),
            'SkillEvoReg_style_candidate_validation': next((name for name in improved
                 if results[name]['regression_gate'] and any(row['new_correctness_on_edited_pair']
                                                            for row in results[name]['pairs'].values())), 'incumbent'),
            'Synedrion_style_HMT': next((name for name in improved
                 if results[name]['metamorphic_passes'] == len(references)), 'incumbent'),
            'candidates': results, 'identical_measured_pairs': True,
            'eligible_audited_mothers': len(references)}
