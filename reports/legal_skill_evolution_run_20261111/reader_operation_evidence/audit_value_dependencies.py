"""Measure actual finisher dependence; synthetic interventions are not scores.

Only replay this on an already-executed source. No model or grading access.
Changing a declared answer here is a deliberately artificial program probe,
never a repaired source interpretation or a new training example.
"""
from collections import Counter
from copy import deepcopy
import json

from legal_skill_guard.skill_evolution.semantic_operations import finish


def term_counter(raw):
    return Counter(json.dumps(r['term'], ensure_ascii=False, sort_keys=True)
                   for r in raw['statements'])


def audit(bundle, text, units, actual_answers, actual_output):
    assert finish(bundle['program'], text, units, actual_answers) == actual_output
    operations = {o['name']: o for o in bundle['operations']}
    probes = []
    for i, answer in enumerate(actual_answers):
        for choice in ['unknown', *[c['name'] for c in operations[answer['operation']]['choices']]]:
            if choice == answer['choice']: continue
            altered = deepcopy(actual_answers); altered[i]['choice'] = choice
            row = {'query': answer['id'], 'operation': answer['operation'],
                   'actual_choice': answer['choice'], 'artificial_choice': choice}
            try:
                changed = finish(bundle['program'], text, units, altered)
                before, after = term_counter(actual_output), term_counter(changed)
                removed = before-after; added = after-before
                row.update({'source_term_multiset_changed': before != after,
                    'removed_terms': list(removed.elements()),
                    'added_terms': list(added.elements()),
                    'unresolved_changed': actual_output['unresolved'] != changed['unresolved']})
                # A gate can remove/add roots. Changing a field within an
                # emitted same-kind root is stronger constructive-dependence
                # evidence, but is still not source-semantic correctness.
                old_roots = {(s['term'][0],tuple(s['support_ids'])): [] for s in actual_output['statements']}
                new_roots = {(s['term'][0],tuple(s['support_ids'])): [] for s in changed['statements']}
                for s in actual_output['statements']: old_roots[s['term'][0],tuple(s['support_ids'])].append(s['term'])
                for s in changed['statements']: new_roots[s['term'][0],tuple(s['support_ids'])].append(s['term'])
                changed_values = []
                for key in old_roots.keys() & new_roots.keys():
                    a,b = old_roots[key],new_roots[key]
                    if len(a)==len(b)==1 and a!=b:
                        changed_values.append({'root_kind':key[0],'support_ids':list(key[1]),
                                               'actual_term':a[0],'artificial_term':b[0]})
                row['unique_same_kind_same_support_value_changes'] = changed_values
            except Exception as error:
                row['artificial_probe_error'] = type(error).__name__+': '+str(error)
            probes.append(row)
    return {'actual_output_reproduced_exactly':True, 'probes':probes,
        'new_model_requests':0,'native_labels_loaded':False,
        'artificial_probes_not_source_truth_or_repairs':True,
        'operation_used_is_not_by_itself_learning_or_contribution_success':True,
        'goal_complete':False}
