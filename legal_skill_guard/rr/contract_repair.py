"""Pilot: infer a source-literal postcomposition from a real correction pair.

This finite synthesizer and SMT equivalence are standard components. The
source-parametric applicability learner is still missing; no transfer claim.
"""
import re
from .semantic_contracts import compare_modules


def infer_postcomposition(candidate, reference, signature, domain, rule_text):
    # Only constants literally in the supplied policy. Never add native answers
    # or case amounts to this grammar. Evidence retains every span for audit.
    occurrences = {}
    for match in re.finditer(r'(?<![A-Za-z0-9_])\d[\d,]*(?![A-Za-z0-9_])', rule_text):
        value = int(match.group().replace(',', ''))
        occurrences.setdefault(value, []).append([match.start(), match.end()])
    grammar = [('identity', None, candidate)]
    grammar += [(op, value, f'{op}({value}, ({candidate}))')
                for op in ('min', 'max') for value in sorted(occurrences)]
    attempts, valid = [], []
    for op, value, expression in grammar:
        comparison = compare_modules(expression, reference, signature, domain)
        row = dict(operator=op, source_literal=value, expression=expression,
                   comparison=comparison)
        attempts.append(row)
        if comparison['equivalent_over_supplied_domain']:
            valid.append(row)
    if not valid:
        return dict(status='no_verified_patch_in_declared_grammar', attempts=attempts,
                    selected=None, broader_search_authorized_by_this_function=False)
    selected = min(valid, key=lambda r: (r['operator'] != 'identity', len(r['expression']), r['expression']))
    return dict(status='verified_postcomposition_found', selected=selected,
                source_literal_spans=occurrences.get(selected['source_literal'], []),
                alternatives_verified=len(valid), attempts=attempts,
                proof_scope='Equivalence to supplied reference on supplied domain',
                source_truth_or_cross_source_applicability_proved=False,
                reference_is_already_correct_strong_control=True,
                learned_new_primitive_operator=False)
