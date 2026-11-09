"""Update the finite reader channels from actually observed answer slots.

None is unobserved; the integer2 is an observed unknown answer. Marginalization
and EM are ordinary shared machinery, not an independent method contribution.
The original frozen learner and its artifacts remain unchanged.
"""
import math
import numpy as np

from .semantic_learning import OPS, PRIMITIVES, Y, features, softmax, transform, forecasts


def validate_rows(rows):
    if not rows:
        raise ValueError('Need real TRAIN observations')
    for r in rows:
        if len(r['h']) != 2 or any(type(x) is not int or x not in (0, 1, 2) for x in r['h']):
            raise ValueError('Truth roles must be explicit three-valued labels')
        if len(r['y']) != 4 or any(x is not None and (type(x) is not int or x not in (0, 1, 2)) for x in r['y']):
            raise ValueError('Use None only for unobserved slots and2 for observed unknown')
        if all(x is None for x in r['y']):
            raise ValueError('An unasked trajectory provides no reader observation')
        if not math.isfinite(r['weight']) or r['weight'] <= 0:
            raise ValueError('Source weights must be finite and positive')


def compatible_answers(observed):
    return np.array([all(v is None or y[i] == v for i, v in enumerate(observed)) for y in Y])


def operator_likelihood(rows):
    """Sum the old full-answer likelihood over all unobserved slots exactly."""
    result = []
    for r in rows:
        count = sum(v is not None for v in r['y'])
        result.append([.95 * all(v is None or transform(r['h'], op)[i] == v
                                 for i, v in enumerate(r['y'])) + .05 / (3 ** count) for op in OPS])
    return np.array(result)


def fit_observed_mixture(rows):
    like = operator_likelihood(rows)
    row_weights = np.array([r['weight'] for r in rows])
    edits = np.array([sum(v != 'self' for v in op) for op in OPS])
    prior = np.exp(-.5 * edits); prior /= prior.sum()
    mixture = prior.copy()
    for _ in range(100):
        posterior = like * mixture[None, :]
        posterior /= posterior.sum(axis=1, keepdims=True)
        mixture = (posterior * row_weights[:, None]).sum(axis=0) + prior
        mixture /= mixture.sum()
    return mixture.tolist()


def fit_observed_factors(rows):
    result = []
    prior = np.array([math.exp(-.5 * (v != 'self')) for v in PRIMITIVES]); prior /= prior.sum()
    for field in range(4):
        actual = [r for r in rows if r['y'][field] is not None]
        if not actual:
            result.append(prior.tolist()); continue
        like = np.array([[.95 * int(transform(r['h'], tuple(v if i == field else 'self' for i in range(4)))[field]
                                    == r['y'][field]) + .05 / 3 for v in PRIMITIVES] for r in actual])
        row_weights = np.array([r['weight'] for r in actual]); mixture = prior.copy()
        for _ in range(100):
            posterior = like * mixture[None, :]; posterior /= posterior.sum(axis=1, keepdims=True)
            mixture = (posterior * row_weights[:, None]).sum(axis=0) + prior
            mixture /= mixture.sum()
        result.append(mixture.tolist())
    return result


def joint_counts(rows):
    """Original Laplace counts; incomplete vectors contribute conditional mass."""
    masks = np.array([compatible_answers(r['y']) for r in rows])
    weight = np.array([r['weight'] for r in rows]); counts = np.ones(81)
    for _ in range(100):
        mass = masks * counts[None, :]
        mass /= mass.sum(axis=1, keepdims=True)
        counts = np.ones(81) + (mass * weight[:, None]).sum(axis=0)
    return counts.tolist()


def fit_observed_channels(rows):
    validate_rows(rows)
    contexts = sorted({tuple(r['context']) for r in rows})
    groups = {''.join(map(str, c)): [r for r in rows if r['context'] == list(c)] for c in contexts}
    field_counts = np.ones((4, 3, 3))
    for r in rows:
        for i, value in enumerate(r['y']):
            if value is not None:
                field_counts[i, r['h'][i % 2], value] += r['weight']
    bins = {}
    for r in rows:
        k = ''.join(map(str, r['h'])) + ':' + ''.join(map(str, r['context']))
        bins.setdefault(k, []).append(r)
    x = np.array([features(r['h'], r['context']) for r in rows])
    masks = np.array([compatible_answers(r['y']) for r in rows])
    row_weights = np.array([r['weight'] for r in rows]); w = np.zeros((x.shape[1], 81))
    for _ in range(200):
        p = softmax(x @ w)
        conditional = p * masks; conditional /= conditional.sum(axis=1, keepdims=True)
        gradient = x.T @ ((p - conditional) * row_weights[:, None]) / row_weights.sum() + w
        w -= .2 * gradient
    return {'structured': {'global': fit_observed_mixture(rows),
                'contexts': {k: fit_observed_mixture(v) for k, v in groups.items()},
                'iterations': 100, 'residual_mass': .05, 'prior_pseudocount_total': 1, 'complexity_rate': .5},
            'independent': field_counts.tolist(), 'joint_global': joint_counts(rows),
            'joint_empirical': {k: joint_counts(v) for k, v in bins.items()},
            'unstructured_softmax': w.tolist(), 'softmax_steps': 200, 'softmax_lr': .2, 'softmax_L2': 1,
            'primitive_vocabulary': list(PRIMITIVES), 'number_joint_operators': len(OPS),
            'training_mothers': sorted({r['mother'] for r in rows}), 'training_rows': len(rows),
            'factorized_same_grammar': {'global': fit_observed_factors(rows),
                                      'contexts': {k: fit_observed_factors(v) for k, v in groups.items()}},
            'observed_slots': sum(v is not None for r in rows for v in r['y']),
            'unobserved_slots': sum(v is None for r in rows for v in r['y']),
            'unobserved_is_not_unknown_class': True, 'new_hyperparameters': False}


def observed_forecasts(models, h, c):
    result = forecasts(models, h, c)
    factors = models['factorized_same_grammar']
    weights = factors['contexts'].get(''.join(map(str, c)), factors['global'])
    marginal = []
    for field in range(4):
        p = np.full(3, .05 / 3)
        for v, w in zip(PRIMITIVES, weights[field]):
            predicted = transform(h, tuple(v if i == field else 'self' for i in range(4)))[field]
            p[predicted] += .95 * w
        marginal.append(p)
    result['factorized_same_grammar'] = [math.prod(marginal[i][y[i]] for i in range(4)) for y in Y]
    return result
