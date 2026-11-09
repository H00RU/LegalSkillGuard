"""Finite TRAIN-only discrimination programs and joint reader channels.

The operator grammar, tree search and decoder are common machinery. Only fitted
programs/weights are learned artifacts; none certifies a source interpretation.
"""
import itertools
import math
import re
import numpy as np

H = list(itertools.product(range(3), repeat=2))
Y = list(itertools.product(range(3), repeat=4))
FEATURES = ('D.work', 'D.medium', 'R.work', 'R.medium')


def context(text):
    # Raw text only; no source ID, variant marker, annotation or reader answer.
    medium = bool(re.search(r'\b(?:paid|wages)\b[^.]*?\bin\s+(?:hay|cash|kind|agricultural products)\b', text, re.I))
    return [int(medium), int(len(re.findall(r'\bpaid\b', text, re.I)) > 1)]


def key(h, c):
    return ''.join(map(str, h)) + ':' + ''.join(map(str, c))


def semantic_loss(pred, truth):
    # Unknown is an explicit answer; unsupported confident exclusions cost twice.
    return sum(int(a != b) + int(a != 2 and a != b) for a, b in zip(pred, truth))


def compile_skill(rows, *, contrast=True):
    pairs = [(i, j) for i in range(len(rows)) for j in range(i)
             if rows[i]['mother'] == rows[j]['mother'] and rows[i]['h'] != rows[j]['h']]
    errors = [r['case_id'] for r in rows if r['y'][:2] != r['h'] or r['y'][2:] != r['h']]
    if not errors:
        return {'empty': True, 'reason': 'No actual verified confusion', 'training_errors': []}

    def apply(tree, y):
        if 'leaf' in tree: return tree['leaf']
        return apply(tree['branches'][str(y[tree['feature']])], y)

    def nodes(t):
        return 0 if 'leaf' in t else 1 + sum(nodes(x) for x in t['branches'].values())

    def groups(t, y):
        if 'leaf' in t: return set()
        f = t['feature']
        return {f // 2} | groups(t['branches'][str(y[f])], y)

    def score(t, ids):
        outputs = {i: apply(t, rows[i]['y']) for i in ids}
        loss = sum(rows[i]['weight'] * semantic_loss(outputs[i], rows[i]['h']) for i in ids)
        failed_pairs = sum(min(rows[i]['weight'], rows[j]['weight']) for i, j in pairs
                           if i in outputs and j in outputs and
                           (outputs[i] == outputs[j] or outputs[i] != rows[i]['h'] or outputs[j] != rows[j]['h'])) if contrast else 0
        cost = sum(rows[i]['weight'] * len(groups(t, rows[i]['y'])) for i in ids)
        return (loss, failed_pairs, cost, nodes(t))

    def search(ids, depth, used):
        leaves = [{'leaf': list(h)} for h in H]
        # Empty/unseen branch stays unknown, never inherits a confident default.
        if not ids: return {'leaf': [2, 2]}
        best = min(leaves, key=lambda t: (score(t, ids), str(t)))
        if depth:
            for f in range(4):
                if f in used: continue
                subsets = [[i for i in ids if rows[i]['y'][f] == v] for v in range(3)]
                if sum(bool(s) for s in subsets) < 2: continue
                tree = {'feature': f, 'question': FEATURES[f], 'branches': {
                    str(v): search(s, depth - 1, used | {f}) for v, s in enumerate(subsets)}}
                if (score(tree, ids), str(tree)) < (score(best, ids), str(best)): best = tree
        return best

    tree = search(list(range(len(rows))), 2, set())
    return {'empty': False, 'tree': tree, 'objective': list(score(tree, list(range(len(rows))))),
            'objective_order': ['source_weighted_semantic_and_false_exclusion_loss', 'confusion_pair_loss', 'physical_prompt_groups', 'nodes'],
            'training_errors': errors, 'confusion_pairs': [[rows[i]['case_id'], rows[j]['case_id']] for i, j in pairs],
            'contrast_pair_term': contrast, 'max_depth': 2, 'certifies_semantic_truth': False}


def run_skill(skill, y):
    if skill['empty']: return {'prediction': [2, 2], 'prompt_groups': [], 'trace': [], 'empty': True}
    t = skill['tree']; trace = []; groups = set()
    while 'leaf' not in t:
        f = t['feature']; groups.add('direct' if f < 2 else 'reader')
        trace.append({'question': FEATURES[f], 'answer': y[f]})
        t = t['branches'][str(y[f])]
    return {'prediction': t['leaf'], 'prompt_groups': sorted(groups), 'trace': trace, 'semantic_certificate': False}


# Each answer reads a typed semantic role, with one permitted corruption.
PRIMITIVES = ('self', 'other', 'negate_self', 'negate_other', 'unknown_as_false', 'unknown_as_true', 'erase')
OPS = list(itertools.product(PRIMITIVES, repeat=4))


def transform(h, op):
    out = []
    for i, p in enumerate(op):
        own = h[i % 2]; other = h[1 - i % 2]
        value = other if p in ('other', 'negate_other') else own
        if p.startswith('negate') and value != 2: value = 1 - value
        if p == 'unknown_as_false' and value == 2: value = 0
        if p == 'unknown_as_true' and value == 2: value = 1
        if p == 'erase': value = 2
        out.append(value)
    return out


def fit_mixture(rows):
    if not rows: raise ValueError('Need actual training trajectories')
    pred = np.array([[transform(r['h'], op) == r['y'] for op in OPS] for r in rows], dtype=float)
    like = .95 * pred + .05 / 81
    weights = np.array([r['weight'] for r in rows])
    edits = np.array([sum(p != 'self' for p in op) for op in OPS])
    prior = np.exp(-.5 * edits); prior /= prior.sum()
    mixture = prior.copy()
    for _ in range(100):
        posterior = like * mixture[None, :]; posterior /= posterior.sum(axis=1, keepdims=True)
        mixture = (posterior * weights[:, None]).sum(axis=0) + prior
        mixture /= mixture.sum()
    return mixture.tolist()


def features(h, c):
    a = [float(h[0] == i) for i in range(3)]
    b = [float(h[1] == i) for i in range(3)]
    # Shared features for all models, including all h/context interactions.
    return np.array([1.] + a + b + list(map(float, c)) +
                    [x * z for x in a + b for z in c] + [x * z for x in a for z in b])


def softmax(z):
    e = np.exp(z - np.max(z, axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


def fit_channels(rows):
    global_mix = fit_mixture(rows)
    contexts = sorted({tuple(r['context']) for r in rows})
    contextual = {''.join(map(str, c)): fit_mixture([r for r in rows if r['context'] == list(c)]) for c in contexts}
    field_counts = np.ones((4, 3, 3))
    global_counts = np.ones(81)
    joint = {}
    for r in rows:
        for i in range(4): field_counts[i, r['h'][i % 2], r['y'][i]] += r['weight']
        yi = Y.index(tuple(r['y'])); global_counts[yi] += r['weight']
        k = key(r['h'], r['context'])
        joint.setdefault(k, np.ones(81)); joint[k][yi] += r['weight']
    x = np.array([features(r['h'], r['context']) for r in rows])
    target = np.array([Y.index(tuple(r['y'])) for r in rows])
    weight = np.array([r['weight'] for r in rows]); w = np.zeros((x.shape[1], 81))
    for _ in range(200):
        error = softmax(x @ w); error[np.arange(len(rows)), target] -= 1
        gradient = x.T @ (error * weight[:, None]) / weight.sum() + w
        w -= .2 * gradient
    return {'structured': {'global': global_mix, 'contexts': contextual, 'iterations': 100,
            'residual_mass': .05, 'prior_pseudocount_total': 1, 'complexity_rate': .5},
            'independent': field_counts.tolist(), 'joint_empirical': {k: v.tolist() for k, v in joint.items()},
            'joint_global': global_counts.tolist(), 'unstructured_softmax': w.tolist(),
            'softmax_steps': 200, 'softmax_lr': .2, 'softmax_L2': 1,
            'primitive_vocabulary': list(PRIMITIVES), 'number_joint_operators': len(OPS),
            'training_mothers': sorted({r['mother'] for r in rows}), 'training_rows': len(rows)}


def forecasts(models, h, c):
    m = models['structured']; ck = ''.join(map(str, c)); mix = m['contexts'].get(ck, m['global'])
    structured = np.full(81, .05 / 81)
    for op, p in zip(OPS, mix): structured[Y.index(tuple(transform(h, op)))] += .95 * p
    independent = np.array(models['independent']); independent /= independent.sum(axis=2, keepdims=True)
    indep = np.array([math.prod(independent[i, h[i % 2], y[i]] for i in range(4)) for y in Y])
    j = np.array(models['joint_empirical'].get(key(h, c), models['joint_global'])); j /= j.sum()
    soft = softmax(features(h, c) @ np.array(models['unstructured_softmax']))
    return {'structured': structured.tolist(), 'independent': indep.tolist(), 'joint_empirical': j.tolist(),
            'unstructured_softmax': soft.tolist()}


def operator_summary(models, rows):
    result = {}
    for k, mixture in {'global': models['structured']['global'], **models['structured']['contexts']}.items():
        order = np.argsort(mixture)[::-1][:12]
        result[k] = [{'operator': list(OPS[i]), 'mass': mixture[i], 'edits': sum(p != 'self' for p in OPS[i]),
                       'exact_support_mothers': sorted({r['mother'] for r in rows if transform(r['h'], OPS[i]) == r['y']})} for i in order]
    return result


def decode_joint(all_h_forecasts, observed):
    yi = Y.index(tuple(observed))
    result = {}
    for model in ('structured', 'independent', 'joint_empirical', 'unstructured_softmax'):
        probs = [f[model][yi] for f in all_h_forecasts]
        best = max(probs); ties = [list(h) for h, p in zip(H, probs) if abs(p - best) < 1e-12]
        # Uniform residual makes every h possible. MAP is a prediction only.
        result[model] = {'MAP_h': ties[0] if len(ties) == 1 else [2, 2], 'MAP_ties': ties,
                         'compatible_h_with_residual': [list(h) for h in H],
                         'semantic_answer': None, 'unresolved': True,
                         'reason': 'No trusted relation anchor; full-support error remains possible'}
    return result
