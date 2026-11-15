"""Existing real TRAIN counterevidence, shared by both acquisition arms.

These are partial source annotations, not a complete semantic oracle, a new
benchmark or a replacement for native scoring. No expected native answer is
used. Absence from this short review is not certification of a different case.
"""


def review(source, grounded, *, complete_families=None, scope_contract=None):
    rows = [b['inputs'] for b in grounded.get('bindings', [])]
    checks = []
    pending = []
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
            observed=set(complete_families or ())
            if scope_contract is not None:observed.update(scope_contract['family_scans'])
            check={'check': 'Stated hay wage has coherent payer, payee, amount and means on its payment event',
                'native_families':['payment_'],
                'passed': any(has('agent_', [p, 'Alice']) and has('patient_', [p, 'Bob'])
                    and has('amount_', [p, 2325]) and any(f['predicate'] == 'means_'
                        and f['arguments'][0] == p and 'hay' in str(f['arguments'][1]).lower()
                        for f in facts) for p in payment_ids)}
            properties=set()if scope_contract is None else {
                (s['event'],s['predicate'])for s in scope_contract['event_properties']}
            active='payment_'in observed and not payment_ids or any(
                scope_contract is None or 'payment_'in set(complete_families or ())or
                all((p,predicate)in properties for predicate in ('agent_','patient_','amount_','means_'))
                for p in payment_ids)
            if active:checks.append(check)
            else:pending.append({'check':check['check'],'native_families':['payment_'],
                'unread_predicates':['agent_','patient_','amount_','means_'],'status':'unread_not_certified'})
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
                role_check={'check':'Source-stated service keeps Alice as worker and the named university as employer',
                    'native_families':['service_'],
                    'passed':bool(services) and all(has('agent_',[e,'Alice']) and
                        has('patient_',[e,'Johns Hopkins University']) for e in services)}
                bad_role=any(f['predicate']in ('agent_','patient_')and f['arguments'][0]in services and
                    f['arguments'][1]!=('Alice'if f['predicate']=='agent_'else 'Johns Hopkins University')for f in facts)
                roles_closed=scope_contract is None or 'service_'in observed or bool(services)and all(
                    {'event':e,'predicate':p}in scope_contract['event_properties']
                    for e in services for p in ('agent_','patient_'))
                if bad_role or roles_closed:checks.append({**role_check,'passed':role_check['passed']and not bad_role})
                else:pending.append({'check':role_check['check'],'native_families':['service_'],
                    'unread_predicates':['agent_','patient_'],'status':'unread_not_certified'})
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
    service_sources={
        'bb6b0bc1':('domestic service','USA',True),
        'ed3f34d3':('domestic service','Venezuela',False),
        '3e22604a':(None,'USA',False)}
    annotation=next((v for k,v in service_sources.items()if source.startswith('SARA_v2_Binary:'+k)),None)
    if annotation:
        from .sara_statute_kernel import literal_date
        kind,country,home=annotation
        for row in rows:
            facts=row['facts'];observed=set(complete_families or ())
            services=[f['arguments'][0]for f in facts if f['predicate']=='service_']
            def has(p,args):return {'predicate':p,'arguments':args}in facts
            if scope_contract is not None and 'service_'in scope_contract['family_scans']:
                checks.append({'check':'The source-stated service is retained by the declared complete scan',
                    'native_families':['service_'],'passed':len(services)==1})
            payment_ids=[f['arguments'][0]for f in facts if f['predicate']=='payment_']
            if source.startswith(('SARA_v2_Binary:bb6b0bc1','SARA_v2_Binary:3e22604a')):
                payment_closed='payment_'in observed or (scope_contract is not None and 'payment_'in scope_contract['family_scans'])
                if payment_closed:
                    checks.append({'check':'The source-stated payment remains in a declared complete payment scan',
                        'native_families':['payment_'],'passed':bool(payment_ids)})
                if payment_ids:
                    checks.append({'check':'The service period does not become an unstated payment date',
                        'native_families':['payment_'],
                        'passed':not any(f['predicate']in ('start_','end_')and f['arguments'][0]in payment_ids for f in facts)})
                purpose_closed=scope_contract is None or 'payment_'in observed or any(
                    s['predicate']=='purpose_'and s['event']in payment_ids
                    for s in scope_contract['event_properties'])
                service_closed=scope_contract is None or 'service_'in observed or 'service_'in scope_contract['family_scans']
                if payment_ids and purpose_closed and service_closed:
                    checks.append({'check':'The source-stated payment for this service keeps the actual event connection',
                        'native_families':['payment_','service_'],
                        'passed':any(has('agent_',[p,'Alice'])and has('patient_',[p,'Bob'])and
                            any(has('purpose_',[p,e])for e in services)for p in payment_ids)})
            def scoped(check,ports,*,bad_observed=False,events=None,family='service_'):
                explicit=set(ports)
                selected=services if events is None else events
                closed=scope_contract is None or family in observed or bool(selected)and all(
                    {'event':e,'predicate':p}in scope_contract['event_properties']for e in selected for p in explicit)
                if bad_observed or closed:checks.append({**check,'passed':check['passed']and not bad_observed})
                else:pending.append({'check':check['check'],'native_families':[family],
                    'unread_predicates':sorted(explicit),'status':'unread_not_certified'})
            if services or 'service_'in observed:
                scoped({'check':'Stated worker Bob and employer Alice remain on the same service',
                    'native_families':['service_'],'passed':len(services)==1 and all(
                        has('agent_',[e,'Bob'])and has('patient_',[e,'Alice'])for e in services)},('agent_','patient_'),
                    bad_observed=any(f['predicate']in ('agent_','patient_')and f['arguments'][0]in services and
                        f['arguments'][1]!=('Bob'if f['predicate']=='agent_'else 'Alice')for f in facts))
                scoped({'check':'Service period is source-stated February 1 through September 2, 2017',
                    'native_families':['service_'],'passed':all(any(f['predicate']=='start_'and
                        f['arguments'][0]==e and literal_date(f['arguments'][1])=='2017-02-01'for f in facts)
                        and any(f['predicate']=='end_'and f['arguments'][0]==e and
                            literal_date(f['arguments'][1])=='2017-09-02'for f in facts)for e in services)},('start_','end_'),
                    bad_observed=any(f['predicate']in ('start_','end_')and f['arguments'][0]in services and
                        literal_date(f['arguments'][1])!=('2017-02-01'if f['predicate']=='start_'else '2017-09-02')for f in facts))
                scoped({'check':'Restricted service kind follows the current source clause',
                    'native_families':['service_'],'passed':all(has('purpose_',[e,kind])if kind else
                        not any(f['predicate']in ('purpose_','type_')and f['arguments'][0]==e and
                            f['arguments'][1]in ('agricultural labor','domestic service')for f in facts)for e in services)},('purpose_','type_'),
                    bad_observed=any(f['predicate']in ('purpose_','type_')and f['arguments'][0]in services and
                        (f['arguments'][1]!=kind if kind else f['arguments'][1]in ('agricultural labor','domestic service'))for f in facts))
                locations=[f['arguments'][1]for f in facts if f['predicate']=='location_'and f['arguments'][0]in services]
                scoped({'check':'Explicit home is retained; domestic work alone does not invent a private-home venue',
                    'native_families':['service_'],'passed':('private home'in locations)==home},('location_',),
                    bad_observed=not home and 'private home'in locations)
                checks.append({'check':'Geographic country is not inferred from the employer citizenship',
                    'native_families':['service_'],'passed':not any(f['predicate']=='country_'and
                        f['arguments'][0]in locations and f['arguments'][1]!=country for f in facts)})
            father_scan=scope_contract is not None and 'father_'in scope_contract['family_scans']
            if ':3e22604a'in source and ('father_'in observed or father_scan or any(f['predicate']=='father_' for f in facts)):
                fathers=[f['arguments'][0]for f in facts if f['predicate']=='father_']
                checks.append({'check':'Work dates and workplace do not assert a kinship interval or family residence',
                    'native_families':['father_','residence_'],
                    'passed':not any(f['predicate']=='residence_'or
                        f['predicate']in ('start_','end_')and f['arguments'][0]in fathers for f in facts)})
                check={'check':'Bob is the source-stated father of Alice, with parent/child direction preserved',
                    'native_families':['father_'],'passed':any(has('agent_',[e,'Bob'])and
                        has('patient_',[e,'Alice'])for e in fathers)}
                if father_scan and not fathers:checks.append(check)
                else:scoped(check,('agent_','patient_'),events=fathers,family='father_',
                    bad_observed=any(f['predicate']in ('agent_','patient_')and f['arguments'][0]in fathers and
                        f['arguments'][1]!=('Bob'if f['predicate']=='agent_'else 'Alice')for f in facts))
    return {'checks': checks, 'reviewed': bool(checks), 'failures': sum(not c['passed'] for c in checks),
        'pending_checks':pending,
        'partial_source_review_not_full_semantic_certification': True,
        'source_annotations_shared_both_arms': True, 'native_answer_used': False}
