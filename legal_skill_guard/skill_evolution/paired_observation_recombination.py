"""Coordinate proposals over actual paired observation/conversion versions.

Whole teacher proposals and the retained library remain candidates. Additional
neighbors transfer ONE complete acquired component version between them. The
host generates no schema field, conversion rule, observation or source fact.
This finite coordinate operator is not, by itself, a claim of novelty.
"""
from copy import deepcopy

from .objects import digest


def _behavior(component):
    if component is None:
        return None
    return {k: sorted(component[k]) if k == 'complete_native_families' else component[k]
        for k in ('id', 'meaning', 'prompt', 'schema_json', 'conversion_program', 'complete_native_families')}


def _library_key(library):
    return digest({'shared_helpers': library['shared_helpers'],
        'components': [_behavior(c) for c in sorted(library['components'], key=lambda c: c['id'])]})


def coordinate_candidates(libraries):
    result = dict(libraries)
    seen = {_library_key(value) for value in result.values()}
    for receiver_name, receiver in libraries.items():
        for donor_name, donor in libraries.items():
            if receiver_name == donor_name:
                continue
            if receiver['shared_helpers'] != donor['shared_helpers']:
                raise ValueError('Component versions require their actual unchanged shared helpers')
            current = {c['id']: c for c in receiver['components']}
            offered = {c['id']: c for c in donor['components']}
            for cid in sorted(set(current) | set(offered)):
                if _behavior(current.get(cid)) == _behavior(offered.get(cid)):
                    continue
                index = deepcopy(current)
                if cid in offered:
                    index[cid] = deepcopy(offered[cid])
                else:
                    index.pop(cid)
                value = {**deepcopy(receiver), 'components': [index[k] for k in sorted(index)]}
                key = _library_key(value)
                if key in seen:
                    continue
                seen.add(key)
                name = 'coordinate/' + receiver_name + '/from/' + donor_name + '/' + cid
                result[name] = value
    return result
