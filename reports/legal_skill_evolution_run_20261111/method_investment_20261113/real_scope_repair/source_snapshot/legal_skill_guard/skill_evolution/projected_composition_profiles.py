"""Exact reachable G outputs using clingo's projection over output atoms.

All rule subsets remain selectable. Derived and recursive dependencies execute
unchanged; projection only coalesces subsets with identical deployed outputs.
No partial enumeration is accepted as complete supervision.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import time

from .relational_rules import (PREFIX, canonical, context_identity, decode_outputs,
    language_identity, observation_program, output_projection, rule_text, validate_context)
from .source_composition import render_composition, validate_renderers


def admissible_projected_compositions(library, observation, check_native, *, timeout_seconds=30):
    language = library['language']
    context = observation['context']
    validate_context(context, language)
    validate_renderers(language, library['renderers'])
    if context['unknown_groups']:
        raise ValueError('Projection requires fully observed inputs; do not fill unknown readings')
    if timeout_seconds <= 0:
        raise ValueError('Positive finite search time required')
    started = time.monotonic()
    base = {'language_sha256': language_identity(language), 'context_sha256': context_identity(context),
        'enumeration_scope': 'outputs_reachable_by_subsets_of_current_rules',
        'not_a_complete_relaxed_representation_diagnostic': True, 'new_model_requests': 0,
        'algorithm': 'clingo_explicit_output_projection', 'all_rule_subsets_remain_selectable': True}
    lines = ['{' + PREFIX + 'take(' + str(i) + ')}.' for i in range(len(language['rules']))]
    lines.extend(rule_text(r, i, selectable=True) for i, r in enumerate(language['rules']))
    lines.append(observation_program(context, 0))
    lines.append(output_projection(language))
    lines.extend('#project ' + name + '/' + str(len(s['arguments']) + 1) + '.'
        for name, s in language['signatures'].items() if s['kind'] == 'output')
    worker = Path(__file__).with_name('projected_composition_worker.py')
    try:
        result = subprocess.run([sys.executable, '-I', str(worker)],
            input=json.dumps({'program': '\n'.join(lines), 'timeout_seconds': timeout_seconds}),
            capture_output=True, text=True, timeout=timeout_seconds + 2, cwd='/tmp', close_fds=True)
    except subprocess.TimeoutExpired:
        return {**base, 'status': 'timeout', 'allowed_theories': None, 'evaluations': []}
    if result.returncode:
        raise ValueError('Projected solver failed: ' + result.stderr[-1200:])
    enumeration = json.loads(result.stdout)
    if enumeration['status'] != 'complete':
        return {**base, 'status': 'timeout', 'allowed_theories': None, 'evaluations': [],
            'partial_model_count': len(enumeration['models'])}
    required = {canonical(a) for a in context['required']}
    forbidden = {canonical(a) for a in context['forbidden']}
    vocabulary = {}
    evaluations = []
    allowed = []
    seen = set()
    for model in enumeration['models']:
        if time.monotonic() - started >= timeout_seconds:
            return {**base, 'status': 'timeout', 'allowed_theories': None, 'evaluations': evaluations}
        theory = [{k: v for k, v in a.items() if k != 'context_index'} for a in decode_outputs(model, language)]
        key = canonical(theory)
        if key in seen:
            raise ValueError('Explicit output projection returned a duplicate theory')
        seen.add(key)
        witness = []
        import clingo
        for symbol in model:
            a = clingo.parse_term(symbol)
            if a.name == PREFIX + 'take':
                witness.append(language['rules'][a.arguments[0].number]['id'])
        keys = {canonical(a) for a in theory}
        vocabulary.update({canonical(a): a for a in theory})
        hard = required <= keys and not forbidden.intersection(keys)
        record = {'theory_index': len(evaluations), 'theory': theory, 'witness_rule_ids': witness,
            'partial_source_constraints_satisfied': hard}
        if not hard:
            record.update(admissible=False, reason='explicit_partial_source_constraint')
        else:
            candidate = {'status': 'sat', 'complete': True,
                'certain_outputs': [{**a, 'context_index': 0} for a in theory],
                'possible_outputs': [{**a, 'context_index': 0} for a in theory],
                'unknown_observations_preserved': deepcopy(context['unknown_groups'])}
            try:
                output = render_composition(language, library['renderers'], observation, candidate, library['spec'])
                feedback = check_native(output)
                if type(feedback['accepted']) is not bool or not isinstance(feedback['reason'], str):
                    raise ValueError('Explicit actual native feedback required')
                record.update(native_feedback=feedback, admissible=feedback['accepted'], reason=feedback['reason'])
                if feedback['accepted']:
                    allowed.append(theory)
            except (ValueError, KeyError, TypeError) as error:
                record.update(admissible=False, reason='type_or_provenance_failure', error=str(error))
        evaluations.append(record)
    return {**base, 'status': 'complete', 'vocabulary': [vocabulary[k] for k in sorted(vocabulary)],
        'evaluations': evaluations, 'allowed_theories': allowed, 'finite_theory_count': len(evaluations),
        'accepted_theory_count': len(allowed), 'rule_subset_count': 1 << len(language['rules']),
        'elapsed_seconds': time.monotonic() - started}
