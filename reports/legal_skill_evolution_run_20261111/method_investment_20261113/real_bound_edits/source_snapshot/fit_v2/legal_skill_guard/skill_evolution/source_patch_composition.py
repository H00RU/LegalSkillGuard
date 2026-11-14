"""Compose actual learned source programs and G without aliasing their types.

The host supplies pure code composition and exact-field source bindings. The
dictionary of retirements is an acquired asset, not a host legal rule. A retired
source term must have current evidence and a bound successor in the new program.
"""
import ast
from copy import deepcopy

from .objects import digest
from .relational_rules import validate_language
from .source_composition import validate_renderers, validate_template_constructors
from .scoped_grammar import constructors
from .span_compiler import validate_procedure, execute_json


def compose_programs(before, proposed, retirements):
    old = ast.parse(before); new = ast.parse(proposed)
    old_names = {n.name for n in old.body}; new_names = {n.name for n in new.body}
    if old_names & new_names != {'apply'}:
        raise ValueError('Actual source helper namespaces must be disjoint')
    if any(n.name.startswith('_joint_patch_') for n in [*old.body, *new.body]):
        raise ValueError('Patch entry names collide with supplied code')
    for tree, name in [(old, '_joint_patch_before'), (new, '_joint_patch_proposed')]:
        next(n for n in tree.body if n.name == 'apply').name = name
    # This generic effect interpreter neither fills legal fields nor substitutes
    # source values between different current units. New facts come solely from
    # the actual supplied programs, and removals require a declared binding.
    wrapper = '''
def _joint_patch_anchor(row, position, units):
    term = row.get('term', [])
    found = []
    if position < len(term):
        value = term[position]
        for unit in units:
            if unit.get('id') in row.get('support_ids', []) and value == unit.get('text'):
                found.append(unit.get('id'))
    return found

def _joint_patch_at(value, path):
    for index in path:
        if not isinstance(value, list) or index >= len(value):
            return None
        value = value[index]
    return value

def _joint_patch_matches(old, current, policy, units):
    if old['term'][0] != policy['old_constructor']:
        return False
    for check in policy.get('old_checks', []):
        if _joint_patch_at(old['term'], check['path']) != check['value']:
            return False
    old_units = _joint_patch_anchor(old, policy['old_quote_position'], units)
    if len(old_units) != 1:
        return False
    for new in current:
        if new['term'][0] != policy['new_constructor']:
            continue
        new_units = _joint_patch_anchor(new, policy['new_quote_position'], units)
        if len(new_units) != 1 or old_units != new_units:
            continue
        guards_ok = True
        for guard in policy.get('guards', []):
            matched = False
            for witness in current:
                if witness['term'][0] != guard['constructor']:
                    continue
                left = _joint_patch_at(new['term'], guard['anchor_path'])
                right = _joint_patch_at(witness['term'], guard['witness_path'])
                if left is None or right is None or left != right:
                    continue
                all_checks = True
                for check in guard.get('checks', []):
                    if _joint_patch_at(witness['term'], check['path']) != check['value']:
                        all_checks = False
                if all_checks:
                    matched = True
            if not matched:
                guards_ok = False
        if guards_ok:
            return True
    return False

def apply(inputs, premises):
    before = _joint_patch_before(inputs, premises)
    amended = dict(inputs)
    amended['source_output'] = before
    proposed = _joint_patch_proposed(amended, premises)
    policies = POLICY_LITERAL
    units = inputs.get('source_spans', [])
    current = proposed.get('statements', [])
    old_rows = before.get('statements', [])
    rows = []
    for row in current:
        retire = False
        if row in old_rows:
            for policy in policies:
                if _joint_patch_matches(row, current, policy, units):
                    retire = True
        if not retire:
            rows.append(row)
    return {'statements': rows, 'complete': proposed['complete'], 'unresolved': proposed['unresolved']}
'''.replace('POLICY_LITERAL', repr(retirements))
    program = ast.unparse(old) + '\n\n' + ast.unparse(new) + '\n\n' + wrapper
    validate_procedure(program, allow_helpers=True)
    return program


def compose_libraries(before, proposed, retirements=()):
    if before['operations'] or proposed['operations']:
        raise ValueError('This actual source-only composition requires no neural reads')
    if before['spec']['decision_program'] != proposed['spec']['decision_program']:
        raise ValueError('Consumer changes must be evaluated separately')
    result = deepcopy(proposed)
    result['source_program'] = compose_programs(before['source_program'], proposed['source_program'], list(retirements))
    by_name = {c['name']: c for c in before['spec']['constructors']}
    for ctor in proposed['spec']['constructors']:
        if ctor['name'] in by_name and by_name[ctor['name']] != ctor:
            raise ValueError('Constructor meanings cannot be aliased or overwritten')
        by_name[ctor['name']] = deepcopy(ctor)
    result['spec']['constructors'] = list(by_name.values()); constructors(result['spec'])
    language = deepcopy(before['language'])
    for name, signature in proposed['language']['signatures'].items():
        if name in language['signatures'] and language['signatures'][name] != signature:
            raise ValueError('Conflicting relation signatures')
        language['signatures'][name] = deepcopy(signature)
    for sort, values in proposed['language']['constants'].items():
        target = language['constants'].setdefault(sort, [])
        target.extend(deepcopy(v) for v in values if v not in target)
    rules = {r['id']: r for r in language['rules']}
    for rule in proposed['language']['rules']:
        if rule['id'] in rules:
            raise ValueError('Actual source G rule names must be disjoint')
        rules[rule['id']] = deepcopy(rule)
    language['rules'] = list(rules.values())
    result['language'] = language
    result['renderers'] = deepcopy(before['renderers'] + proposed['renderers'])
    selected = list(before['selected_rule_ids']) + list(proposed['suggested_rule_ids'])
    if len(set(selected)) != len(selected):
        raise ValueError('Duplicated rule identity in source patch')
    result['selected_rule_ids'] = selected; result['suggested_rule_ids'] = selected
    validate_language(language); validate_renderers(language, result['renderers'])
    validate_template_constructors(result['renderers'], result['spec'])
    result['source_patch_composition'] = {'before_sha256': digest(before), 'proposed_sha256': digest(proposed),
        'retirements': deepcopy(list(retirements)), 'automatic_semantic_certification': False,
        'no_whole_program_fallback_or_native_answer_selection': True}
    return result


def retirement_effects(before_rows, current_rows, units, policies):
    """Use exactly the compiled effect interpreter, not an approximate matcher."""
    identity = 'def apply(inputs,premises):\n    return inputs["source_output"]\n'
    program = compose_programs(identity, identity, [])
    tree = ast.parse(program)
    helpers = '\n\n'.join(ast.get_source_segment(program, n) for n in tree.body
        if n.name in {'_joint_patch_anchor', '_joint_patch_at', '_joint_patch_matches'})
    evaluate = '''
def apply(inputs,premises):
    effects = []
    for policy in inputs['policies']:
        indices = []
        index = 0
        for row in inputs['before']:
            if _joint_patch_matches(row, inputs['current'], policy, inputs['units']):
                indices.append(index)
            index += 1
        effects.append(indices)
    return {'effects': effects}
'''
    return execute_json(helpers + '\n\n' + evaluate,
        {'before': before_rows, 'current': current_rows, 'units': units, 'policies': policies}, {},
        allow_helpers=True)['effects']
