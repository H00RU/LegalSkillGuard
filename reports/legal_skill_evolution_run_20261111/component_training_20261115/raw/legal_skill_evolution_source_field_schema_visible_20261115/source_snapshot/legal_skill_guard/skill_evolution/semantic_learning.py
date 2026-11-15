"""Source-semantic evidence and joint compiler candidates for acquisition.

Evidence is supplied by an explicit source review, never inferred from native
answer correctness. Missing observations stay open. This is the constraint and
execution part of the proposed learner; it does not invent productions or
claim to implement the complete induction algorithm.
"""
from copy import deepcopy
import ast

import jsonschema

from .objects import digest
from .relational_compiler import (
    SCHEMA as RELATION_SCHEMA, apply, bind_records, compile_skill, spans_for)
from .source_schema import LABELS
from .span_compiler import execute_json, validate_procedure


def contract(spec):
    """Bind a review to meanings/types, not to a consumer's spelling alone."""
    return digest(spec['frames'])


def compile_bundle(bundle, materials):
    if set(bundle) != {'spec', 'source_program'}:
        raise ValueError('Acquire complete relation contract, consumer and source program')
    jsonschema.validate(bundle['spec'], RELATION_SCHEMA)
    compile_skill(bundle['spec'], materials, restricted=True, allow_helpers=True)
    validate_procedure(bundle['source_program'], allow_helpers=True)
    if any(isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in LABELS
           for n in ast.walk(ast.parse(bundle['source_program']))):
        raise ValueError('Source recognition must not emit native answer labels')
    return deepcopy(bundle)


def run_bundle(bundle, source, *, trace=False):
    """Use only a current public source; no native labels enter either program."""
    spans = spans_for(source)
    result = execute_json(bundle['source_program'], {'source_spans': spans}, {},
                          allow_helpers=True, trace=trace)
    raw = result['result'] if trace else result
    records = bind_records(bundle['spec'], spans, raw)
    views = {}
    for view in source['views']:
        try:
            value = apply(bundle['spec'], source, view, records, allow_helpers=True)
            views[view['id']] = {'value': value, 'error': None}
        except (ValueError, TypeError, KeyError) as exc:
            views[view['id']] = {'value': None, 'error': type(exc).__name__ + ': ' + str(exc)}
    return {'source': source['key'], 'contract': contract(bundle['spec']),
            'records': records, 'views': views,
            **({'source_trace': result} if trace else {})}


def producing_calls(trace, record):
    """Find actual functions returning the disputed instance, not a causal proof.

    The source compiler alone is traced. Generic constructors and their legal
    callers are both retained; this function never declares a semantic repair.
    """
    instance = {'support_ids': record['support_ids'], 'fields': {
        name: {'value': record['values'].get(name), 'support_ids': ids}
        for name, ids in record['field_support_ids'].items()}}
    def contains(value):
        if value == instance:
            return True
        if isinstance(value, dict):
            return any(contains(v) for v in value.values())
        if isinstance(value, list):
            return any(contains(v) for v in value)
        return False
    calls = {c['id']: c for c in trace['calls']}
    selected = [c for c in trace['calls'] if contains(c.get('returned'))]
    return {'call_ids': [c['id'] for c in selected],
            'functions': sorted({c['function'] for c in selected}),
            'trace_truncated': trace['trace_truncated'],
            'semantic_fault_proved': False,
            'lineages': [[p['function'] for p in _lineage(c, calls)] for c in selected]}


def _lineage(call, calls):
    out = [call]
    while out[-1]['parent'] is not None:
        out.append(calls[out[-1]['parent']])
    return list(reversed(out))


def review_binding(source, spec, *, kind, field, value, support_ids, polarity,
                   reason, review_origin):
    """Register an already reviewed binding, with its exact evidence scope.

    Supported values are complete field assertions. Rejections forbid only the
    stated value/scope; they do not supply a replacement legal interpretation.
    A review_origin identifies a real acquired/audited observation, not a label.
    """
    if polarity not in {'supported', 'rejected'}:
        raise ValueError('Explicit source review polarity required')
    if not reason.strip() or not review_origin.strip():
        raise ValueError('A semantic review needs its reason and actual origin')
    frames = {f['name']: f for f in spec['frames']}
    if kind not in frames:
        raise ValueError('Review of an unacquired relation')
    fields = {f['name']: f for f in frames[kind]['fields']}
    if field not in fields:
        raise ValueError('Review of an unacquired field')
    f = fields[field]
    if f['type'] == 'string':
        valid = isinstance(value, str) and value in f['domain']
    else:
        valid = (isinstance(value, list)
                 and all(isinstance(v, str) and v in f['domain'] for v in value)
                 and len(set(value)) == len(value))
    if not valid:
        raise ValueError('Explicit, typed known value required; unknown is not a review')
    spans = spans_for(source)
    if not support_ids or any(type(i) is not int or i < 0 or i >= len(spans) for i in support_ids):
        raise ValueError('Review must cite current-source spans')
    ids = sorted(set(support_ids))
    if f['type'] == 'array':
        value = sorted(value)
    observation = {'source': source['key'], 'source_digest': digest(spans),
                   'contract': contract(spec), 'kind': kind, 'field': field,
                   'value': deepcopy(value), 'support_ids': ids,
                   'polarity': polarity, 'reason': reason, 'review_origin': review_origin}
    return {'id': digest(observation), **observation}


def check_binding(observation, source, spec, records):
    """Check a specific reviewed assertion, without completing missing meaning."""
    if source['key'] != observation['source'] or digest(spans_for(source)) != observation['source_digest']:
        raise ValueError('Semantic observation belongs to different source bytes')
    if contract(spec) != observation['contract']:
        return {'status': 'open', 'reason': 'Changed semantic contract requires a new explicit review'}
    matches = [r for r in records if r['kind'] == observation['kind']
               and sorted(r['support_ids']) == observation['support_ids']]
    field = observation['field']
    known = [r['values'][field] for r in matches
             if field not in r['unresolved_fields'] and field in r['values']]
    unresolved = any(field in r['unresolved_fields'] or field not in r['values'] for r in matches)
    expected = observation['value']
    if isinstance(expected, list):
        known = [sorted(v) for v in known]
    same = any(v == expected for v in known)
    if observation['polarity'] == 'rejected':
        if same:
            return {'status': 'violated', 'reason': 'Reproduces the source-rejected binding'}
        if unresolved:
            return {'status': 'open', 'reason': 'Field remains unresolved'}
        return {'status': 'not_reproduced', 'reason': 'Rejected binding absent; replacement semantics unverified'}
    if same and not unresolved and all(v == expected for v in known):
        return {'status': 'supported', 'reason': 'Reproduces this reviewed binding only'}
    if known and not same:
        return {'status': 'violated', 'reason': 'Contradicts the source-supported field assertion'}
    return {'status': 'open', 'reason': 'Missing or conflicting binding; no negative fact inferred'}


def assess_candidate(bundle, sources, observations, *, native_feedback=None):
    """Keep source-semantic evidence separate from native training feedback."""
    sources = {s['key']: s for s in sources}
    if any(o['source'] not in sources for o in observations):
        raise ValueError('A pending review source cannot silently disappear')
    runs, errors = {}, {}
    for key, source in sources.items():
        try:
            runs[key] = run_bundle(bundle, source)
        except (ValueError, TypeError, KeyError, jsonschema.ValidationError) as exc:
            errors[key] = type(exc).__name__ + ': ' + str(exc)
    checks = []
    for o in observations:
        result = ({'status': 'open', 'reason': 'Source execution failed: ' + errors[o['source']]}
                  if o['source'] in errors else check_binding(
                      o, sources[o['source']], bundle['spec'], runs[o['source']]['records']))
        checks.append({'observation': o['id'], **result})
    return {'candidate': digest(bundle), 'runs': runs, 'execution_errors': errors,
            'evidence_set': digest({'sources': sources, 'observations': sorted(o['id'] for o in observations)}),
            'observation_ids': sorted(o['id'] for o in observations),
            'checks': checks, 'source_violations': sum(c['status'] == 'violated' for c in checks),
            'source_supported': sum(c['status'] == 'supported' for c in checks),
            'source_open': sum(c['status'] == 'open' for c in checks),
            'source_rejections_not_reproduced': sum(c['status'] == 'not_reproduced' for c in checks),
            'native_feedback': deepcopy(native_feedback),
            'complete_source_semantics_verified': False}


def update_frontier(state, bundle, assessment, *, acquisition_receipt):
    """Retain reviewed versions and rejected attempts; never promote native fit
    into source supervision. This manages candidates, not production synthesis.
    """
    if assessment['candidate'] != digest(bundle):
        raise ValueError('Assessment belongs to another candidate')
    if not acquisition_receipt:
        raise ValueError('Retain the actual acquisition receipt')
    state = deepcopy(state)
    state.setdefault('versions', {})
    state.setdefault('attempts', [])
    if not set(state.get('observation_ids', [])) <= set(assessment['observation_ids']):
        raise ValueError('Previously reviewed semantic observations cannot silently disappear')
    if state.get('evidence_set') != assessment['evidence_set']:
        for version in state['versions'].values():
            version['feasible'] = False
            version['assessment_stale'] = True
    state['evidence_set'] = assessment['evidence_set']
    state['observation_ids'] = assessment['observation_ids']
    key = digest(bundle)
    feasible = not assessment['execution_errors'] and not assessment['source_violations']
    state['versions'][key] = {'bundle': deepcopy(bundle), 'assessment': deepcopy(assessment),
                              'feasible': feasible, 'assessment_stale': False,
                              'acquisition_receipt': acquisition_receipt}
    state['attempts'].append({'candidate': key, 'feasible': feasible,
                              'assessment': deepcopy(assessment),
                              'acquisition_receipt': acquisition_receipt})
    state['feasible_versions'] = sorted(k for k, v in state['versions'].items() if v['feasible'])
    state['production_induction_implemented'] = False
    state['core_learning_success_claimed'] = False
    return state
