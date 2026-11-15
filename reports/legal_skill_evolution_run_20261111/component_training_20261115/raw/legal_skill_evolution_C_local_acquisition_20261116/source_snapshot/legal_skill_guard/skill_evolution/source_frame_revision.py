"""Select whole acquired effect families without mixing a frame's operands.

Both φ/G compilation and an ordinary source program can use this same update
operator. Family names refer to the already declared consumer interface. It
supplies no legal interpretation, correct answer, source-specific gate or fact.
"""
from copy import deepcopy
from itertools import combinations

from .source_composition import statement_fingerprint


FAMILIES = {
    'disclosure': {'permission', 'prohibition', 'define_representative',
                   'complete_source_no_disclosure_permission'},
    'disposal': {'disposal_obligation', 'complete_source_no_disposal_obligation'},
    'retention': {'retention_permission', 'retention_prohibition',
                  'absolute_retention_prohibition', 'retention_exception',
                  'complete_source_no_retention_effect'},
}


def family(row):
    name = row['term'][0]
    matches = [f for f, names in FAMILIES.items() if name in names]
    if len(matches) != 1:
        raise ValueError('No declared revision family for source statement: ' + name)
    return matches[0]


def candidate_masks():
    names = sorted(FAMILIES)
    return [list(part) for size in range(len(names) + 1) for part in combinations(names, size)]


def merge(previous, proposed, updated_families):
    """A learned global mask chooses complete statements from their producers.

    A return/destroy alternative and its attached trigger/exception remain one
    statement. Complete-source audits travel only from the chosen producer for
    that effect family. Unresolved and unknown metadata are never closed by a
    partial update. The unchanged branches still execute on the current source.
    """
    selected = set(updated_families)
    if not selected <= set(FAMILIES):
        raise ValueError('Revision mask contains an undeclared effect family')
    for output in (previous, proposed):
        for row in output['statements']:
            family(row)
    if not selected:
        return deepcopy(previous), {'updated_families': [], 'whole_previous_output': True}
    if selected == set(FAMILIES):
        return deepcopy(proposed), {'updated_families': sorted(selected), 'whole_proposed_output': True}
    statements, origins, seen = [], [], {}
    for label, output in [('previous', previous), ('proposed', proposed)]:
        for row in output['statements']:
            belongs = family(row)
            if (belongs in selected) != (label == 'proposed'):
                continue
            key = statement_fingerprint(row)
            if key not in seen:
                seen[key] = len(statements); statements.append(deepcopy(row))
                origins.append({'statement_index': seen[key], 'family': belongs,
                                'producer': label, 'statement_fingerprint': key})
    result = {'statements': statements, 'complete': bool(previous['complete'] and proposed['complete']),
              'source_semantics_verified': False}
    for key in ('unresolved', 'unknown_observations_preserved'):
        result[key] = []
        for output in (previous, proposed):
            for value in output.get(key, []):
                if value not in result[key]:
                    result[key].append(deepcopy(value))
    return result, {'updated_families': sorted(selected), 'origins': origins,
        'whole_frames_preserved': True, 'no_source_or_answer_dispatch': True,
        'not_a_source_truth_certificate': True}
