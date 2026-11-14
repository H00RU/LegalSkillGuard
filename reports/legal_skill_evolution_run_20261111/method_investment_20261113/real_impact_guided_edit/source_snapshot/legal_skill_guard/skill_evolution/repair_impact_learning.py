"""Learn partial repair footprints over evidenced legal/program relations.

The DNF/set-cover learner is shared infrastructure, not a new induction
algorithm. Only explicitly reviewed judgments train a policy. A path witnesses
an acquired dependency; it does not establish its legal truth. Missing edges,
unseen feature configurations and conflicting effects stay unresolved.
"""
from copy import deepcopy

from .binding_learning import accepts, fit_dnf
from .objects import digest


EFFECTS = ('must_change', 'preserve', 'recheck')


def validate(event):
    graph = event['graph']; nodes = {n['id']: n for n in graph['nodes']}
    if len(nodes) != len(graph['nodes']) or not nodes:
        raise ValueError('Distinct actual dependency nodes required')
    for node in nodes.values():
        if not all(isinstance(node.get(k), str) and node[k] for k in ('id', 'kind', 'role')):
            raise ValueError('Explicit nominal node kinds and roles required')
        if not node.get('evidence_refs'):
            raise ValueError('A legal/program node needs actual evidence')
    if not graph['seeds'] or not set(graph['seeds']) <= nodes.keys():
        raise ValueError('Current evidenced repair seeds required')
    for edge in graph['edges']:
        if edge['from'] not in nodes or edge['to'] not in nodes:
            raise ValueError('Dependency endpoint missing')
        if not edge.get('relation') or not edge.get('evidence_refs'):
            raise ValueError('Dependencies require a named relation and evidence')
    for item in event.get('judgments', []):
        if item['node'] not in nodes or item['effect'] not in EFFECTS:
            raise ValueError('Unknown reviewed effect or target')
        if type(item['holds']) is not bool or not item.get('evidence_refs'):
            raise ValueError('Unknown is not a negative repair-impact label')
    return nodes


def observations(event, *, max_path):
    """Structural predicates without source IDs, quotes, values or native labels.

    Both directions are explicit in a path, and each path keeps a concrete
    witness. Same-file/quote co-occurrence supplies no graph edge.
    """
    nodes = validate(event)
    if not isinstance(max_path, int) or isinstance(max_path, bool) or max_path < 0:
        raise ValueError('Nonnegative fixed path bias required')
    adjacent = {key: [] for key in nodes}
    for index, edge in enumerate(event['graph']['edges']):
        adjacent[edge['from']].append((edge['to'], '>' + edge['relation'], index))
        adjacent[edge['to']].append((edge['from'], '<' + edge['relation'], index))
    found = {key: {} for key in nodes}
    for seed in event['graph']['seeds']:
        todo = [(seed, (), (seed,), ())]
        while todo:
            current, path, visited, edges = todo.pop()
            origin = nodes[seed]['kind'] + ':' + nodes[seed]['role']
            key = 'seed:' + origin if not path else 'path:' + origin + '/' + '/'.join(path)
            found[current].setdefault(key, []).append({'seed': seed,
                'nodes': list(visited), 'edges': list(edges)})
            if len(path) >= max_path:
                continue
            for target, relation, index in adjacent[current]:
                if target not in visited:
                    typed = relation + '(' + nodes[target]['kind'] + ':' + nodes[target]['role'] + ')'
                    todo.append((target, path + (typed,), visited + (target,), edges + (index,)))
    out = {}
    for key, node in nodes.items():
        features = {'kind:' + node['kind']: True, 'role:' + node['role']: True}
        features.update({name: True for name in found[key]})
        out[key] = {'features': features, 'path_witnesses': found[key]}
    return out


def learn(events, *, max_path=3, max_literals=2):
    """Fit explicit positive/negative effects; preserve parent-update identity."""
    if not events or len({e['id'] for e in events}) != len(events):
        raise ValueError('Distinct actual repair events required')
    parents = {e['parent_revision'] for e in events}
    observed = {e['id']: observations(e, max_path=max_path) for e in events}
    # Event-only features are never created. The vocabulary is fixed before
    # predicting a future repair. An unseen kind/role/path cannot mean False.
    vocabulary = sorted({k for rows in observed.values() for row in rows.values() for k in row['features']})
    policies = {}; feedback = []
    for effect in EFFECTS:
        rows = []
        for event in events:
            for item in event.get('judgments', []):
                if item['effect'] != effect:
                    continue
                features = observed[event['id']][item['node']]['features']
                rows.append({'features': {k: features.get(k, False) for k in vocabulary},
                    'positive': item['holds']})
                feedback.append({'event': event['id'], 'parent_revision': event['parent_revision'], **deepcopy(item)})
        positive = sum(r['positive'] for r in rows)
        if not positive or positive == len(rows):
            policies[effect] = {'status': 'not_identified', 'positive': positive,
                'negative': len(rows) - positive, 'reason': 'both_explicit_verdicts_required'}
            continue
        try:
            policies[effect] = {'status': 'learned', **fit_dnf(rows, max_literals=max_literals,
                positive_literals_only=True)}
        except ValueError as exc:
            policies[effect] = {'status': 'not_identified', 'reason': str(exc)}
    return {'policies': policies, 'feature_vocabulary': vocabulary,
        'max_path': max_path, 'max_literals': max_literals,
        'training_event_hashes': {e['id']: digest(e) for e in events},
        'independent_parent_revisions': len(parents), 'feedback': feedback,
        'unknowns_not_negative': True, 'legal_values_or_answers_not_features': True,
        'only_positive_witnessed_predicates': True}


def predict(model, event):
    observed = observations(event, max_path=model['max_path']); result = []
    known = set(model['feature_vocabulary'])
    for key, row in observed.items():
        unexpected = sorted(set(row['features']) - known)
        features = {k: row['features'].get(k, False) for k in model['feature_vocabulary']}
        effects = []; matched = {}
        # New relations/roles may alter an impact boundary. Do not classify them
        # by treating their absent training features as an all-False default.
        if not unexpected:
            for effect, policy in model['policies'].items():
                if policy['status'] == 'learned' and accepts(policy, features):
                    effects.append(effect)
                    matched[effect] = [c for c in policy['clauses'] if all(features[k] == v for k, v in c)]
        conflict = 'must_change' in effects and 'preserve' in effects
        result.append({'node': key, 'effects': [] if conflict else effects,
            'status': 'conflicting' if conflict else 'unseen_structure' if unexpected else 'predicted' if effects else 'unresolved',
            'unseen_features': unexpected, 'matched_clauses': matched,
            'path_witnesses': row['path_witnesses']})
    return {'model_sha256': digest(model), 'event_sha256': digest(event), 'nodes': result,
        'not_a_source_truth_or_edit_success_certificate': True}


def generation_scope(model, event):
    """Materialize learned semantic targets before an editor request is made.

    A preserve prediction alone cannot certify an old value. Supply a current
    source-backed validity judgment, or ask for review instead. Counterevidence
    releases the old value and always requires a new source check.
    """
    prediction = predict(model, event); nodes = validate(event)
    instructions = {'must_resolve': [], 'preserve_supported': [], 'recheck': [], 'unresolved': [],
        'model_sha256': prediction['model_sha256'], 'prediction': prediction,
        'protect_semantics_not_old_code': True}
    for row in prediction['nodes']:
        node = nodes[row['node']]
        target = {'node': row['node'], 'kind': node['kind'], 'role': node['role'],
            'evidence_refs': deepcopy(node['evidence_refs'])}
        if node.get('counterevidence'):
            if not node['counterevidence'].get('evidence_ref'):
                raise ValueError('Counterevidence needs an actual source reference')
            instructions['recheck'].append({**target, 'counterevidence': deepcopy(node['counterevidence'])})
            continue
        if 'must_change' in row['effects']:
            instructions['must_resolve'].append(target)
        if 'recheck' in row['effects']:
            instructions['recheck'].append(target)
        if 'preserve' in row['effects']:
            validity = node.get('current_validity', {})
            if validity.get('status') == 'supported' and validity.get('evidence_ref') and 'value' in validity:
                instructions['preserve_supported'].append({**target, 'value': deepcopy(validity['value']),
                    'validity_evidence_ref': validity['evidence_ref']})
            else:
                instructions['unresolved'].append({**target, 'reason': 'current_validity_not_established'})
        if not row['effects']:
            instructions['unresolved'].append({**target, 'reason': row['status']})
    return instructions
