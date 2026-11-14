"""Preserve a cited source term's joint evidence in learned output renderers.

This changes evidence transport only. Rule bodies, costs, legal templates and
selected rules remain unchanged. It cannot acquire a missing legal condition or
find evidence that the source program did not cite.
"""
from copy import deepcopy

from .source_composition import validate_renderers


def preserve_joint_support(language, renderers):
    """Replace a single root_support unit coordinate by its actual source term.

    Only explicit, unambiguous root_support links can be lifted. Reject partial
    transformations: every production of the same output must carry the term.
    Each term occurrence retains its own evidence; identical terms with distinct
    evidence sets are not merged or interpreted as conjunctive witnesses.
    """
    validate_renderers(language, renderers)
    updated = deepcopy(language)
    output_renderers = deepcopy(renderers)
    changes = []
    for renderer in output_renderers:
        name = renderer['predicate']
        rules = [r for r in updated['rules'] if r['head']['predicate'] == name]
        for position in list(renderer['support_arguments']):
            # The output coordinate must be solely provenance. validate_renderers
            # permits a provenance scalar in a legal template; changing it would
            # change semantics, so explicitly reject that case.
            def used_in_template(value):
                if isinstance(value, dict):
                    return value.get('scalar_argument') == position or value.get('term_argument') == position
                return isinstance(value, list) and any(used_in_template(v) for v in value[1:])
            if used_in_template(renderer['term']):
                raise ValueError('A legal template coordinate is not evidence-only')
            replacements = []
            for rule in rules:
                unit = rule['head']['arguments'][position]
                candidates = [a['arguments'][0] for a in rule['body']
                    if a['predicate'] == 'root_support' and a.get('sign', 'positive') == 'positive'
                    and len(a['arguments']) == 2 and a['arguments'][1] == unit]
                distinct = []
                for candidate in candidates:
                    if candidate not in distinct:
                        distinct.append(candidate)
                if len(distinct) != 1 or not isinstance(distinct[0], dict) or set(distinct[0]) != {'var'}:
                    raise ValueError('Output support needs one explicit source term binding')
                replacements.append((rule, deepcopy(distinct[0])))
            if not replacements:
                raise ValueError('No actual production for the cited output')
            for rule, term in replacements:
                rule['head']['arguments'][position] = term
            updated['signatures'][name]['arguments'][position] = 'term'
            renderer['support_arguments'].remove(position)
            renderer['support_from_terms'].append(position)
            changes.append({'predicate': name, 'position': position,
                'producing_rule_ids': [r['id'] for r, _ in replacements]})
    validate_renderers(updated, output_renderers)
    return updated, output_renderers, changes
