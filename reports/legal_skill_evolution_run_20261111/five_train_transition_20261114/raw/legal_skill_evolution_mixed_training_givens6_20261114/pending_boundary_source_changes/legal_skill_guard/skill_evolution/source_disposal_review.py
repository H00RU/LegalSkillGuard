"""Partial checks of two actually reviewed TRAIN disposal-OR links.

No native answer or norm is added. Preserve the source's alternative instead
of omitting it or strengthening its children into independent obligations.
Material/trigger refinements are not restricted to a consumer's current codec.
The same partial checks are applied to both source-learning arms.
"""

def validate_reviewed_disposal(output, reviews):
    issues = []
    for review in reviews:
        units = set(review['source_unit_ids'])
        relevant = [r for r in output['statements'] if set(r['support_ids']) & units
            and r['term'][0] == 'disposal_obligation']
        alternatives = [r['term'][2] for r in relevant
            if r['term'][2][0] in ('action_alternative', 'acquired_action_alternative_v3')]
        alternatives = [a for a in alternatives if len(a) >= 3
            and {a[1][0], a[2][0]} == {'return_to', 'destroy'}]
        if not alternatives:
            issues.append({'source': review['source'], 'violation': 'Reviewed disposal alternative omitted'})
        children = [a[i] for a in alternatives for i in (1, 2)]
        for row in relevant:
            action = row['term'][2]
            if action[0] in ('return_to', 'destroy') and action in children:
                issues.append({'source': review['source'], 'violation': 'Reviewed OR strengthened to an independent child obligation', 'term': row['term']})
    return issues


def with_disposal_review(check, source_id, reviews):
    selected = [r for r in reviews if r['source'] == source_id]
    if not selected:
        return check
    def checked(output):
        feedback = check(output)
        issues = validate_reviewed_disposal(output, selected)
        feedback['reviewed_disposal_link_passed'] = not issues
        feedback['reviewed_disposal_scope_violations'] = issues
        feedback['source_review_passed'] = feedback.get('source_review_passed', True) and not issues
        if issues:
            feedback.update(accepted=False, reason='explicit_reviewed_source_link_violation')
        return feedback
    return checked
