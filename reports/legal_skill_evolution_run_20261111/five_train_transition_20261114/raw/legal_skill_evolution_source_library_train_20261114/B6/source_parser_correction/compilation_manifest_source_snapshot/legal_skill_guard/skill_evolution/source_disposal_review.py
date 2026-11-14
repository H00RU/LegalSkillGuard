"""Shared partial source checks for two actually reviewed TRAIN OR clauses.

These checks assert no native answer and add no norm. A learned output must
retain the reviewed alternative; splitting its full-material branches into
separate mandatory obligations is not equivalent. Unreviewed sources are not
negatives. The same check is applied to both source-learning arms.
"""
import ast
from .span_compiler import execute_json
from .objects import digest


def validate_reviewed_disposal(output, reviews, consumer_program, *, cache=None):
    cache = {} if cache is None else cache
    definitions = [ast.get_source_segment(consumer_program, n)
        for n in ast.parse(consumer_program).body if n.name != 'apply']
    probe = '\n\n'.join(definitions) + '\n\ndef apply(inputs,premises):\n    return {"full":d_full_disposal(inputs["action"])}\n'
    def checked_action(action, leaf=False):
        key = digest([consumer_program, action, leaf])
        if key not in cache:
            code = probe.replace('d_full_disposal(inputs["action"])', 'd_full_disposal_leaf(inputs["action"])') if leaf else probe
            cache[key] = execute_json(code, {'action': action}, {}, allow_helpers=True)['full']
        return cache[key]
    issues = []
    for review in reviews:
        units = set(review['source_unit_ids'])
        relevant = [r for r in output['statements'] if set(r['support_ids']) & units
            and r['term'][0] == 'disposal_obligation']
        alternative = False
        for row in relevant:
            action = row['term'][2]
            is_alternative = action[0] in ('action_alternative', 'acquired_action_alternative_v3')
            # Use exactly the current shared consumer's typed material semantics,
            # not a lexical guess from quoted source text or a target label.
            full = checked_action(action)
            if is_alternative and full:
                alternative = True
            if not is_alternative and action[0] in ('return_to', 'destroy'):
                if checked_action(action, leaf=True):
                    issues.append({'source': review['source'], 'violation': 'Reviewed OR strengthened to an atomic full-material obligation', 'term': row['term']})
        if not alternative:
            issues.append({'source': review['source'], 'violation': 'Reviewed full-material disposal alternative omitted'})
    return issues


def with_disposal_review(check, source_id, reviews, consumer_program):
    selected = [r for r in reviews if r['source'] == source_id]
    if not selected:
        return check
    cache = {}
    def checked(output):
        feedback = check(output)
        issues = validate_reviewed_disposal(output, selected, consumer_program, cache=cache)
        feedback['reviewed_disposal_scope_passed'] = not issues
        feedback['reviewed_disposal_scope_violations'] = issues
        feedback['source_review_passed'] = feedback.get('source_review_passed', True) and not issues
        if issues:
            feedback.update(accepted=False, reason='explicit_reviewed_source_scope_violation')
        return feedback
    return checked
