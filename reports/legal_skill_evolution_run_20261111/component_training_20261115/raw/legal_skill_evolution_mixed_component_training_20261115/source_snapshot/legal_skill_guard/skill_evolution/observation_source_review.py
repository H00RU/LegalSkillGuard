"""Existing real TRAIN counterevidence, shared by both acquisition arms.

These are partial source annotations, not a complete semantic oracle, a new
benchmark or a replacement for native scoring. No expected native answer is
used. Absence from this short review is not certification of a different case.
"""


def review(source, grounded):
    rows = [b['inputs'] for b in grounded.get('bindings', [])]
    checks = []
    if source.startswith('SARA_v2_Binary:1ff7d9'):
        for row in rows:
            facts = row['facts']
            forbidden = {'father_', 'mother_', 'son_', 'daughter_', 'service_', 'payment_', 'joint_return_'}
            checks.append({'check': 'No invented kinship, service, payment episode or joint filing from annual income and marriage',
                'passed': not any(f['predicate'] in forbidden for f in facts)})
            checks.append({'check': 'General negative151 entitlement and income are not exact positive or negative151b/c givens',
                'passed': not any(f['predicate'] in {'s151_b', 's151_b_applies', 's151_c_applies'}
                    for f in facts + row['negative_givens'])})
    if source.startswith('SARA_v2_Binary:30b162'):
        for row in rows:
            facts = row['facts']
            checks.append({'check': 'Explicit personal151b exemption remains151b, not63d deduction',
                'passed': {'predicate': 's151_b', 'arguments': ['Alice', 2000, 2017]} in facts
                    and not any(f['predicate'] == 'deduction_' for f in facts)})
    if source.startswith('SARA_v2_Binary:d5e113'):
        for row in rows:
            facts = row['facts']
            def has(predicate, arguments):
                return {'predicate': predicate, 'arguments': arguments} in facts
            payment_ids = [f['arguments'][0] for f in facts if f['predicate'] == 'payment_']
            checks.append({'check': 'Stated hay wage has coherent payer, payee, amount and means on its payment event',
                'passed': any(has('agent_', [p, 'Alice']) and has('patient_', [p, 'Bob'])
                    and has('amount_', [p, 2325]) and has('means_', [p, 'hay']) for p in payment_ids)})
            checks.append({'check': 'Ordinary agricultural wage does not establish termination, disability or death',
                'passed': not any(f['predicate'] in {'termination_', 'disability_', 'death_'} for f in facts)})
    return {'checks': checks, 'reviewed': bool(checks), 'failures': sum(not c['passed'] for c in checks),
        'partial_source_review_not_full_semantic_certification': True,
        'source_annotations_shared_both_arms': True, 'native_answer_used': False}
