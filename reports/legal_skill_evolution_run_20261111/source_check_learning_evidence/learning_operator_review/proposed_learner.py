import copy
import json
import math
import re
import sys

CONTRACT = {
    'config': {
        'choice_factors': 'nonempty mapping choice -> nonempty list of semantic factors',
        'focus_only_factors': 'list of factors whose direct evidence must occur in focus_text'
    },
    'observation': {
        'focus_text': 'string containing the reviewed focus unit',
        'context_text': 'optional string containing the rest of the supplied window',
        'allowed': 'list of explicitly supported/admissible choices; may be empty',
        'forbidden': 'list of explicitly rejected choices; may be empty'
    },
    'entry_points': ['init_state(config)', 'update(state, observations)',
                     'predict(state, focus_text, context_text="")']
}

_WORD = re.compile(r'[A-Za-z]+|[0-9]+')


def _tokens(text):
    out = []
    for token in _WORD.findall(text or ''):
        token = token.casefold()
        if token.isdigit():
            token = '<num>'
        if len(token) > 32:
            token = '<long>'
        out.append(token)
    return out


def _channel(prefix, text):
    tokens = _tokens(text)
    counts = {}
    for width in (1, 2, 3):
        for i in range(0, len(tokens) - width + 1):
            key = prefix + str(width) + ':' + '_'.join(tokens[i:i + width])
            counts[key] = counts.get(key, 0.0) + 1.0
    norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
    return {key: value / norm for key, value in counts.items()}


def _features(focus_text, context_text):
    result = _channel('F:', focus_text)
    result.update(_channel('C:', context_text))
    return result


def _validate_config(config):
    choices = config.get('choice_factors')
    if not isinstance(choices, dict) or not choices:
        raise ValueError('choice_factors must be a nonempty mapping')
    signatures = set()
    factors = set()
    for choice, values in choices.items():
        if not isinstance(choice, str) or not choice:
            raise ValueError('choice names must be nonempty strings')
        if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v for v in values):
            raise ValueError('each choice needs semantic factors')
        signature = tuple(sorted(set(values)))
        if signature in signatures:
            raise ValueError('choices must have distinct factor signatures')
        signatures.add(signature)
        factors.update(signature)
    focus_only = config.get('focus_only_factors', [])
    if not isinstance(focus_only, list) or any(v not in factors for v in focus_only):
        raise ValueError('unknown focus-only factor')


def init_state(config):
    _validate_config(config)
    choices = {key: sorted(set(value)) for key, value in config['choice_factors'].items()}
    factors = sorted({factor for values in choices.values() for factor in values})
    return {
        'version': 1,
        'choice_factors': choices,
        'focus_only_factors': sorted(set(config.get('focus_only_factors', []))),
        'weights': {factor: {} for factor in factors},
        'updates': 0,
        'paired_constraints': 0,
        'open_rejections': 0,
        'accept_margin': 0.0
    }


def _usable(state, factor, feature):
    return not (factor in state['focus_only_factors'] and feature.startswith('C:'))


def _score(state, choice, features):
    total = 0.0
    for factor in state['choice_factors'][choice]:
        weights = state['weights'][factor]
        for feature, value in features.items():
            if _usable(state, factor, feature):
                total += weights.get(feature, 0.0) * value
    return total


def _delta(state, preferred, rejected, features):
    delta = {}
    for sign, choice in ((1.0, preferred), (-1.0, rejected)):
        for factor in state['choice_factors'][choice]:
            for feature, value in features.items():
                if _usable(state, factor, feature):
                    key = (factor, feature)
                    delta[key] = delta.get(key, 0.0) + sign * value
    return {key: value for key, value in delta.items() if value}


def _apply_delta(state, delta, scale):
    for (factor, feature), value in delta.items():
        weights = state['weights'][factor]
        weights[feature] = weights.get(feature, 0.0) + scale * value
        if abs(weights[feature]) < 1e-12:
            del weights[feature]


def _validate_observation(state, observation):
    if not isinstance(observation.get('focus_text'), str):
        raise ValueError('focus_text must be a string')
    if not isinstance(observation.get('context_text', ''), str):
        raise ValueError('context_text must be a string')
    allowed = observation.get('allowed', [])
    forbidden = observation.get('forbidden', [])
    if not isinstance(allowed, list) or not isinstance(forbidden, list):
        raise ValueError('allowed and forbidden must be lists')
    known = set(state['choice_factors'])
    if any(value not in known for value in allowed + forbidden):
        raise ValueError('observation contains an unknown choice')
    if set(allowed).intersection(forbidden):
        raise ValueError('a choice cannot be both allowed and forbidden')
    return sorted(set(allowed)), sorted(set(forbidden))


def update(state, observations):
    state = copy.deepcopy(state)
    if not isinstance(observations, list):
        raise ValueError('observations must be a list')
    prepared = []
    for observation in observations:
        allowed, forbidden = _validate_observation(state, observation)
        features = _features(observation['focus_text'], observation.get('context_text', ''))
        prepared.append((features, allowed, forbidden))
        if forbidden and not allowed:
            state['open_rejections'] += 1
        if allowed:
            common = None
            for choice in allowed:
                factors = set(state['choice_factors'][choice])
                common = factors if common is None else common.intersection(factors)
            rate = 0.25 / math.sqrt(1.0 + state['updates'])
            for factor in sorted(common or ()):
                for feature, value in features.items():
                    if _usable(state, factor, feature):
                        weights = state['weights'][factor]
                        weights[feature] = weights.get(feature, 0.0) + rate * value
            state['updates'] += 1
    for _ in range(8):
        for features, allowed, forbidden in prepared:
            if not allowed or not forbidden:
                continue
            preferred = max(allowed, key=lambda c: (_score(state, c, features), c))
            rejected = max(forbidden, key=lambda c: (_score(state, c, features), c))
            margin = _score(state, preferred, features) - _score(state, rejected, features)
            if margin < 1.0:
                delta = _delta(state, preferred, rejected, features)
                norm = sum(value * value for value in delta.values())
                if norm:
                    step = min(1.0, (1.0 - margin) / norm)
                    _apply_delta(state, delta, step)
                    state['updates'] += 1
            state['paired_constraints'] += 1
    margins = []
    for features, allowed, forbidden in prepared:
        if allowed and forbidden:
            good = max(_score(state, choice, features) for choice in allowed)
            bad = max(_score(state, choice, features) for choice in forbidden)
            margins.append(good - bad)
    if margins:
        learned = max(0.0, min(margins) / 2.0)
        state['accept_margin'] = max(state['accept_margin'], learned)
    return state


def predict(state, focus_text, context_text=''):
    features = _features(focus_text, context_text)
    ranked = sorted(((choice, _score(state, choice, features))
                     for choice in state['choice_factors']),
                    key=lambda item: (-item[1], item[0]))
    top_choice, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top_score - second_score
    if top_score <= 0.0 or margin < state['accept_margin']:
        return {'choice': 'unknown', 'margin': margin, 'evidence': []}
    contributions = []
    for factor in state['choice_factors'][top_choice]:
        for feature, value in features.items():
            if _usable(state, factor, feature):
                contribution = state['weights'][factor].get(feature, 0.0) * value
                if contribution > 0.0:
                    contributions.append((contribution, factor, feature))
    contributions.sort(reverse=True)
    return {'choice': top_choice, 'margin': margin,
            'evidence': [{'factor': factor, 'feature': feature, 'weight': value}
                         for value, factor, feature in contributions[:8]]}


def main(request):
    operation = request.get('op')
    if operation == 'init':
        return {'contract': CONTRACT, 'state': init_state(request['config'])}
    if operation == 'update':
        return {'state': update(request['state'], request['observations'])}
    if operation == 'predict':
        return predict(request['state'], request['focus_text'], request.get('context_text', ''))
    raise ValueError('op must be init, update, or predict')


if __name__ == '__main__':
    print(json.dumps(main(json.load(sys.stdin)), sort_keys=True))
