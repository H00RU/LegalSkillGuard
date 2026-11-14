"""Exact rule selection using lazy, output-specific native feedback constraints.

For fully observed positive relational programs, executing all rules gives the
complete output vocabulary. Unknown native losses start at their lower bound0.
Each checked output set supplies a sound loss bound (or hard rejection) for all
rule selections producing it. An exhausted optimum whose actual losses attain
all optimistic bounds is an exact optimum of loss/edit/complexity, without
enumerating every output set first. Partial prior searches supply pointwise
samples only, never completeness or a restricted allowed-output universe.
"""
from copy import deepcopy
import time

from .objects import digest
from .relational_rules import (PREFIX, atom_text, canonical, context_identity,
    decode_outputs, language_identity, observation_program, output_projection,
    rule_text, validate_language, validate_context)
from .relational_learning import _solve, execute_composition
from .source_composition import render_composition
from .theory_supervision import native_loss


def select(library, rows, checker_for, prior_selected, *, samples=(), timeout_seconds=180):
    language = validate_language(library['language'])
    rules = language['rules']
    ids = {r['id'] for r in rules}
    if not set(prior_selected) <= ids:
        raise ValueError('Unacquired revision prior')
    if not rows or len({r['source'] for r in rows}) != len(rows):
        raise ValueError('Distinct actual source contexts required')
    started = time.monotonic()
    deadline = started + timeout_seconds
    vocabularies, cache, checks, solves = {}, {}, [], []
    contexts = [r['observation']['context'] for r in rows]
    for row, context in zip(rows, contexts):
        if 'library_sha256' in row:
            assert row['library_sha256'] == digest(library), 'Actual incumbent is from another library'
        validate_context(context, language)
        if context['unknown_groups'] or 'theory_constraints' in context:
            raise ValueError('Lazy native selection requires actual complete observations, without a pre-restricted theory universe')
        result = execute_composition(language, [r['id'] for r in rules], context,
            timeout_seconds=max(.001, deadline-time.monotonic()))
        if not result['complete']:
            return {'status': 'inconsistent_observations' if result['status'] == 'unsat' else 'timeout',
                'selected_rule_ids': None, 'exact_optimum': False, 'checks': checks}
        vocabulary = [{k: v for k, v in a.items() if k != 'context_index'} for a in result['possible_outputs']]
        vocabularies[row['source']] = sorted(vocabulary, key=canonical)

    def identity(theory):
        return canonical(sorted(theory, key=canonical))

    def remember(sid, theory, feedback, origin):
        key = (sid, identity(theory))
        loss = native_loss(feedback)
        if key in cache:
            if cache[key]['native_loss'] != loss:
                raise ValueError('Same fixed source/output produced conflicting native feedback')
            return cache[key]
        item = {'source': sid, 'theory': deepcopy(theory), 'native_loss': loss,
            'hard_valid': loss is not None, 'native_feedback_sha256': digest(feedback), 'origin': origin}
        cache[key] = item
        checks.append(item)
        return item

    # Reuse only individually completed evaluations under this exact language
    # and context. A timeout of the overall enumeration is not called complete.
    rows_by_id = {r['source']: r for r in rows}
    for sample in samples:
        sid, profile = sample['source'], sample['profile']
        assert profile['language_sha256'] == language_identity(language)
        assert profile['context_sha256'] == context_identity(rows_by_id[sid]['observation']['context'])
        for evaluation in profile['evaluations']:
            if evaluation['partial_source_constraints_satisfied'] and 'native_feedback' in evaluation:
                remember(sid, evaluation['theory'], evaluation['native_feedback'], 'prior_individually_checked_theory_not_complete_search')
    for row in rows:
        result = row['actual']['execution']['composition']
        theory = [{k: v for k, v in a.items() if k != 'context_index'} for a in result['certain_outputs']]
        feedback = checker_for(row['source'])(row['actual']['execution']['source_output'])
        remember(row['source'], theory, feedback, 'actual_paid_proposal_execution')

    def validated_candidate(selected, losses):
        return {'selected_rule_ids': sorted(selected), 'native_loss': sum(losses.values()),
            'native_loss_by_context': losses, 'selection_edits': len(set(selected)^set(prior_selected)),
            'complexity': sum(r['cost'] for r in rules if r['id'] in selected),
            'all_supplied_partial_source_type_and_execution_checks_passed': True,
            'source_truth_beyond_supplied_checks_not_certified': True}

    def objective(item):
        return tuple(item[k] for k in ('native_loss', 'selection_edits', 'complexity'))

    best = None
    current_losses = {}
    for row in rows:
        theory = [{k: v for k, v in a.items() if k != 'context_index'}
            for a in row['actual']['execution']['composition']['certain_outputs']]
        keys = {canonical(a) for a in theory}
        context = row['observation']['context']
        loss = cache[(row['source'], identity(theory))]['native_loss']
        if loss is None or not {canonical(a) for a in context['required']} <= keys or any(canonical(a) in keys for a in context['forbidden']):
            break
        current_losses[row['source']] = loss
    if len(current_losses) == len(rows):
        best = validated_candidate(library['selected_rule_ids'], current_losses)

    iteration = 0
    while time.monotonic() < deadline:
        iteration += 1
        lines = ['{' + PREFIX + 'take(' + str(i) + ')}.' for i in range(len(rules))]
        lines += [rule_text(r, i, selectable=True) for i, r in enumerate(rules)]
        lines.append('#minimize {N@2,C:' + PREFIX + 'loss(C,N)}.')
        lines.append('#minimize {' + ';'.join('1@1,' + str(i) + ':' +
            ('not ' if r['id'] in prior_selected else '') + PREFIX + 'take(' + str(i) + ')'
            for i, r in enumerate(rules)) + '}.')
        lines.append('#minimize {' + ';'.join(str(r['cost']) + '@0,' + str(i) + ':' +
            PREFIX + 'take(' + str(i) + ')' for i, r in enumerate(rules)) + '}.')
        for index, row in enumerate(rows):
            context = row['observation']['context']
            lines.append(observation_program(context, index))
            lines += [':- not ' + atom_text(a, index) + '.' for a in context['required']]
            lines += [':- ' + atom_text(a, index) + '.' for a in context['forbidden']]
            maximum = len(row['actual']['feedback']['views'])
            lines.append('1 {' + PREFIX + 'loss(' + str(index) + ',0..' + str(maximum) + ')} 1.')
            vocabulary = vocabularies[row['source']]
            keys = {canonical(a) for a in vocabulary}
            for item in checks:
                if item['source'] != row['source']:
                    continue
                present = {canonical(a) for a in item['theory']}
                if not present <= keys:
                    raise ValueError('Checked theory lies outside complete all-rules output vocabulary')
                match = [('' if canonical(a) in present else 'not ') + atom_text(a, index) for a in vocabulary]
                if item['native_loss'] == 0:
                    continue  # Already the universal optimistic lower bound.
                if item['native_loss'] is not None:
                    match += [PREFIX + 'loss(' + str(index) + ',N)', 'N<' + str(item['native_loss'])]
                lines.append(':- ' + ','.join(match) + '.' if match else ':-.')
        lines.append(output_projection(language))
        lines.append('#show ' + PREFIX + 'loss/2.')
        program = '\n'.join(lines)
        solved = _solve(program, 'optimize', deadline-time.monotonic())
        solves.append({'iteration': iteration, 'program_sha256': digest(program),
            'status': solved['status'], 'exhausted': solved.get('exhausted'), 'cost': solved.get('cost')})
        if solved['status'] != 'sat' or not solved['exhausted']:
            return {'status': 'complete_unsat' if solved['status'] == 'unsat' and solved['exhausted'] else 'timeout',
                'selected_rule_ids': None, 'exact_optimum': False, 'checks': checks, 'solver_runs': solves,
                'best_validated_selection': best}
        import clingo
        selected, bounds = [], {}
        for value in solved['last_model']:
            atom = clingo.parse_term(value)
            if atom.name == PREFIX + 'take':
                selected.append(rules[atom.arguments[0].number]['id'])
            elif atom.name == PREFIX + 'loss':
                bounds[atom.arguments[0].number] = atom.arguments[1].number
        outputs = decode_outputs(solved['last_model'], language)
        losses, refined, actual_losses = {}, False, {}
        for index, row in enumerate(rows):
            theory = [{k: v for k, v in a.items() if k != 'context_index'} for a in outputs if a['context_index'] == index]
            key = (row['source'], identity(theory))
            item = cache.get(key)
            if item is None:
                result = {'status': 'sat', 'complete': True,
                    'certain_outputs': [{**a, 'context_index': 0} for a in theory],
                    'possible_outputs': [{**a, 'context_index': 0} for a in theory], 'unknown_observations_preserved': []}
                try:
                    rendered = render_composition(language, library['renderers'], row['observation'], result, library['spec'])
                    feedback = checker_for(row['source'])(rendered)
                except (ValueError, KeyError, TypeError) as error:
                    feedback = {'accepted': False, 'reason': 'execution_error', 'error': str(error)}
                item = remember(row['source'], theory, feedback, 'actual_lazy_render_and_native_check')
            actual_losses[row['source']] = item['native_loss']
            if item['native_loss'] is None or item['native_loss'] > bounds[index]:
                refined = True
            else:
                assert item['native_loss'] == bounds[index], 'Optimistic cut overstates actual native loss'
                losses[row['source']] = item['native_loss']
        if all(loss is not None for loss in actual_losses.values()):
            checked = validated_candidate(selected, actual_losses)
            if best is None or objective(checked) < objective(best):
                best = checked
        if not refined:
            return {'status': 'sat', 'selected_rule_ids': sorted(selected), 'exact_optimum': True,
                'objective_order': ['native_loss', 'selection_edits', 'complexity'],
                'native_loss': sum(losses.values()), 'native_loss_by_context': losses,
                'selection_edits': len(set(selected) ^ set(prior_selected)),
                'complexity': sum(r['cost'] for r in rules if r['id'] in selected),
                'actual_loss_attains_exhausted_optimistic_global_bound': True,
                'language_sha256': language_identity(language),
                'context_sha256': [context_identity(c) for c in contexts],
                'checks': checks, 'solver_runs': solves,
                'elapsed_seconds': time.monotonic()-started, 'new_model_requests': 0,
                'source_truth_beyond_supplied_checks_not_certified': True}
    return {'status': 'timeout', 'selected_rule_ids': None, 'exact_optimum': False,
        'checks': checks, 'solver_runs': solves, 'new_model_requests': 0,
        'best_validated_selection': best}
