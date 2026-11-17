"""Fixed, explicit local contract consumers; unsupported scope stays unresolved.

These consumers act on source-grounded graphs, not benchmark labels supplied
as features. Reading errors do not change their rules during interface search.
The public hypotheses define which clause consequences each query requests.
"""
from __future__ import annotations


def index(graph):
    nodes = {n['id']: n for n in graph['nodes']}
    outgoing = {}
    for edge in graph['relations']:
        if edge['status'] != 'stated' or len(edge['arguments']) < 2:
            continue
        outgoing.setdefault((edge['arguments'][0], edge['predicate']), []).extend(edge['arguments'][1:])
    def tags(identity, predicate):
        return {nodes[target]['concept'] for target in outgoing.get((identity, predicate), []) if target in nodes}
    return nodes, outgoing, tags


def contract(graph, task):
    if task not in ('nda-5', 'nda-7', 'nda-16', 'nda-20'):
        return {'handled': False, 'answer': None, 'reason': 'unsupported contract query'}
    nodes, outgoing, tags = index(graph)
    if not graph['scope_complete'] or graph['unresolved'] or any(
            edge['status'] in ('unknown', 'unread') for edge in graph['relations']):
        return {'handled': False, 'answer': None, 'reason': 'outside the complete local consumer domain'}
    evidence, prohibits, disposal_all = [], [], []
    unresolved = bool(graph['unresolved']) or any(
        edge['status'] in ('unknown', 'unread') for edge in graph['relations'])
    for identity, node in nodes.items():
        modality = node['concept']
        if modality not in ('permission', 'prohibition', 'obligation', 'retention'):
            if node['kind'] == 'effect' and modality == 'unspecified':
                unresolved = True
            continue
        actors = tags(identity, 'actor')
        actions, recipients = tags(identity, 'action'), tags(identity, 'recipient')
        materials, triggers = tags(identity, 'information'), tags(identity, 'trigger')
        if not actors or not actions or 'unspecified' in actors | actions:
            unresolved = True
            continue
        if not actors & {'receiving_party', 'either_party'}:
            continue
        if task in ('nda-5', 'nda-7') and 'disclosure' in actions:
            if not materials & {'confidential_information', 'all_confidential_information_and_copies', 'some_confidential_information'}:
                if not materials or 'unspecified' in materials:
                    unresolved = True
                continue
            wanted = {'own_employees'} if task == 'nda-5' else {
                'affiliate_employees', 'legal_advisors', 'financial_advisors', 'consultants',
                'agents', 'contractors', 'other_third_parties'}
            if recipients & wanted:
                (evidence if modality == 'permission' else prohibits if modality == 'prohibition' else []).append(identity)
        if task == 'nda-16' and modality == 'obligation' and actions & {'return', 'destruction'}:
            if triggers & {'termination', 'termination_or_request'}:
                evidence.append(identity)
        if task == 'nda-20':
            if 'retention' in actions:
                if modality in ('permission', 'retention'):
                    evidence.append(identity)
                elif modality == 'prohibition':
                    prohibits.append(identity)
            if modality == 'obligation' and actions & {'return', 'destruction'} and 'all_confidential_information_and_copies' in materials:
                disposal_all.append(identity)
    if evidence and prohibits:
        return {'handled': False, 'answer': None, 'reason': 'unresolved conflict between operative effects'}
    if evidence:
        return {'handled': True, 'answer': 'Entailment', 'used_nodes': evidence}
    if prohibits or task == 'nda-20' and disposal_all:
        return {'handled': True, 'answer': 'Contradiction', 'used_nodes': prohibits + disposal_all}
    if graph['scope_complete'] and not unresolved:
        return {'handled': True, 'answer': 'NotMentioned', 'used_nodes': []}
    return {'handled': False, 'answer': None, 'reason': 'incomplete operative contract scope'}


def maud(graph, task):
    nodes, outgoing, tags = index(graph)
    if not graph['scope_complete'] or graph['unresolved'] or any(
            edge['status'] in ('unknown', 'unread') for edge in graph['relations']):
        return {'handled': False, 'answer': None, 'reason': 'outside the complete local consumer domain'}
    if task == 'Knowledge Definition-Answer':
        classifications = set()
        for identity, node in nodes.items():
            if node['concept'] != 'knowledge_definition':
                continue
            standards = tags(identity, 'standard')
            inquiry = bool(standards & {'reasonable_inquiry_required', 'due_inquiry_required', 'constructive_imputation'})
            actual = bool(standards & {'explicit_actual_wording', 'no_inquiry_required'})
            if inquiry:
                classifications.add('Constructive knowledge')
            elif actual:
                classifications.add('Actual knowledge')
        if len(classifications) == 1:
            return {'handled': True, 'answer': next(iter(classifications))}
        return {'handled': False, 'answer': None, 'reason': 'knowledge standard unestablished'}
    wanted = ('ordinary_course_covenant' if task.startswith('Ordinary Course Covenant')
              else 'negative_interim_covenant' if task.startswith('Negative Interim Covenant') else None)
    if wanted is None:
        return {'handled': False, 'answer': None, 'reason': 'unsupported covenant query'}
    pandemic = {'pandemic', 'epidemic', 'covid_19'}
    unresolved = bool(graph['unresolved']) or any(
        edge['status'] in ('unknown', 'unread') for edge in graph['relations'])
    for identity, node in nodes.items():
        if node['kind'] == 'exception' and node['concept'] in pandemic:
            if tags(identity, 'exception_for') & {wanted}:
                return {'handled': True, 'answer': 'Yes', 'used_nodes': [identity]}
            if not tags(identity, 'exception_for'):
                unresolved = True
    if graph['scope_complete'] and not unresolved:
        return {'handled': True, 'answer': 'No', 'used_nodes': []}
    return {'handled': False, 'answer': None, 'reason': 'exception attachment scope incomplete'}
