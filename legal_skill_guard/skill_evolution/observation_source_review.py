"""Existing real TRAIN counterevidence, shared by both acquisition arms.

These are partial source annotations, not a complete semantic oracle, a new
benchmark or a replacement for native scoring. No expected native answer is
used. Absence from this short review is not certification of a different case.
"""


def review(source, grounded, *, complete_families=None):
    rows = [b['inputs'] for b in grounded.get('bindings', [])]
    checks = []
    if source.startswith('SARA_v2_Binary:1ff7d9'):
        for row in rows:
            facts = row['facts']
            forbidden = {'father_', 'mother_', 'son_', 'daughter_', 'brother_', 'sister_',
                         'sibling_', 'service_', 'joint_return_'}
            checks.append({'check': 'No invented kinship, labor service or joint filing from annual income and marriage; a source-stated payment is allowed',
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
                    and has('amount_', [p, 2325]) and any(f['predicate'] == 'means_'
                        and f['arguments'][0] == p and 'hay' in str(f['arguments'][1]).lower()
                        for f in facts) for p in payment_ids)})
            checks.append({'check': 'Ordinary agricultural wage does not establish termination, disability or death',
                'passed': not any(f['predicate'] in {'termination_', 'disability_', 'death_'} for f in facts)})
    if source.startswith('SARA_v2_Binary:d9d6b2'):
        # Actual TRAIN facts state agricultural wages and service intervals.
        # The paid education reader quoted those wages as evidence of school,
        # enrollment and attendance; an interval end also became termination.
        # Record the source contradiction even when another component already
        # leaves the whole case unresolved. Do not remove or replace its facts.
        for row in rows:
            facts = row['facts']
            checks.append({'check': 'Agricultural wage and service intervals do not state an educational institution, enrollment or attendance',
                'passed': not any(f['predicate'] in {'educational_institution_', 'enrollment_', 'attending_classes_'}
                    for f in facts)})
            checks.append({'check': 'A source service interval end does not state employment termination',
                'passed': not any(f['predicate'] == 'termination_' for f in facts)})
    if source.startswith('SARA_v2_Binary:250fc5'):
        from .sara_statute_kernel import literal_date
        for row in rows:
            facts = row['facts']
            services = [f['arguments'][0] for f in facts if f['predicate']=='service_']
            observed = set(complete_families or ())
            def has(p,args):return {'predicate':p,'arguments':args} in facts
            if 'service_' in observed or services:
                checks.append({'check':'Source-stated service keeps Alice as worker and the named university as employer',
                    'native_families':['service_'],
                    'passed':bool(services) and all(has('agent_',[e,'Alice']) and
                        has('patient_',[e,'Johns Hopkins University']) for e in services)})
                checks.append({'check':'Enrollment/class periods and query workday are not source-stated service dates',
                    'native_families':['service_'],
                    'passed':not any(f['predicate'] in {'start_','end_','location_','country_'} and
                        f['arguments'][0] in services for f in facts)})
                checks.append({'check':'University services do not establish agricultural or domestic service',
                    'native_families':['service_'],
                    'passed':not any(f['predicate']=='purpose_' and f['arguments'][0] in services and
                        f['arguments'][1] in {'agricultural labor','domestic service'} for f in facts)})
            for family,place in [('educational_institution_','agent_'),('enrollment_','patient_'),('attending_classes_','location_')]:
                if family not in observed:continue
                ids=[f['arguments'][0] for f in facts if f['predicate']==family]
                def timed(e,p,d):return any(f['predicate']==p and f['arguments'][0]==e and
                    literal_date(f['arguments'][1])==d for f in facts)
                checks.append({'check':'A complete '+family+' scan retains the actual institution and source-stated period',
                    'native_families':[family],
                    'passed':any(has(place,[e,'Johns Hopkins University']) and
                        (family=='educational_institution_' or has('agent_',[e,'Alice']) and
                            timed(e,'start_','2015-08-29') and timed(e,'end_','2019-05-30')) for e in ids)})
    return {'checks': checks, 'reviewed': bool(checks), 'failures': sum(not c['passed'] for c in checks),
        'partial_source_review_not_full_semantic_certification': True,
        'source_annotations_shared_both_arms': True, 'native_answer_used': False}
