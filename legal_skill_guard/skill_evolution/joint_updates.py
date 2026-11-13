"""Learn local AST edits with shared, typed current-source parameters.

The examples are actual before/after edits plus explicit source/code
correspondences. Source meanings and correspondences are acquired inputs, not
inferred here from matching strings. This PBE core neither supplies legal rules
nor certifies the truth of its source observations.
"""
import ast
from copy import deepcopy
from itertools import combinations
import math
import json

from .objects import digest


def _tree(value):
    if isinstance(value, ast.AST):
        return {'ast': type(value).__name__, 'fields': {k: _tree(v) for k, v in ast.iter_fields(value)}}
    if isinstance(value, list):
        return [_tree(v) for v in value]
    return value


def _ast(value):
    if isinstance(value, dict) and set(value) == {'ast', 'fields'}:
        return getattr(ast, value['ast'])(**{k: _ast(v) for k, v in value['fields'].items()})
    if isinstance(value, list):
        return [_ast(v) for v in value]
    return value


def _get(value, path):
    for key in path:
        value = value[key]
    return value


def _put(value, path, replacement):
    if not path:
        return deepcopy(replacement)
    _get(value, path[:-1])[path[-1]] = deepcopy(replacement)
    return value


def _same(a, b):
    return type(a) is type(b) and a == b


def _shape(value):
    if isinstance(value, dict) and 'ast' in value:
        return 'ast:' + value['ast']
    return type(value).__name__


def _fragment(code):
    module = ast.parse(code)
    if len(module.body) != 1:
        raise ValueError('One actual local AST subtree is required per edit example')
    return _tree(module.body[0])


def _retained_literal(before, after, path):
    """Retain the same occurrence only under unchanged syntactic roles."""
    try:
        if not _same(_get(before, path), _get(after, path)):return False
        for length in range(len(path)):
            old = _get(before, path[:length]); new = _get(after, path[:length])
            if not isinstance(new, dict) or 'ast' not in new:continue
            if not isinstance(old, dict) or old.get('ast') != new['ast']:return False
            kind = new['ast'];a = old['fields'];b = new['fields']
            selectors = {'Call': ['func'], 'Subscript': ['value'], 'BinOp': ['op'],
                         'UnaryOp': ['op'], 'BoolOp': ['op'], 'Compare': ['ops']}.get(kind, [])
            if any(not _same(a[key], b[key]) for key in selectors):return False
            tail = path[length:]
            if kind == 'Dict' and len(tail) >= 3 and tail[:2] == ('fields', 'values'):
                index = tail[2]
                if not _same(a['keys'][index], b['keys'][index]):return False
        return True
    except (KeyError, IndexError, TypeError):
        return False


def _source_bindings(example, signatures):
    values = {}; occupied = {}
    for name, slot in example['source_slots'].items():
        positions = slot['positions']
        if not positions:
            raise ValueError('A source parameter needs actual witnessed argument positions')
        for row, column in positions:
            fact = example['source_facts'][row]
            if fact.get('sign', 'positive') != 'positive':
                raise ValueError('Source patterns use explicit positive observations')
            sorts = signatures[fact['predicate']]
            if len(fact['arguments']) != len(sorts) or sorts[column] != slot['sort']:
                raise ValueError('The source/code parameter has inconsistent nominal types')
            value = fact['arguments'][column]
            if not isinstance(value, (str, int, float, bool)) or isinstance(value, float) and not math.isfinite(value):
                raise ValueError('A witnessed parameter must be an explicit finite scalar')
            if name in values and not _same(values[name], value):
                raise ValueError('One source role cannot bind different current objects')
            if (row, column) in occupied:
                raise ValueError('Annotate one source identity at an argument position')
            values[name] = value; occupied[row, column] = name
    return values, occupied


def _annotate(example, signatures, source_constants):
    values, positions = _source_bindings(example, signatures)
    query = []
    for i, fact in enumerate(example['source_facts']):
        if fact.get('sign', 'positive') != 'positive':
            raise ValueError('A negative or unknown relation is not a positive source witness')
        sorts = signatures[fact['predicate']]
        if len(sorts) != len(fact['arguments']):
            raise ValueError('Source witness arity differs from its declared signature')
        arguments = []
        for j, value in enumerate(fact['arguments']):
            if (i, j) in positions:
                arguments.append({'source': positions[i, j]})
            elif any(_same(value, c) for c in source_constants.get(sorts[j], [])):
                arguments.append(deepcopy(value))
            else:
                raise ValueError('Current source identities/values cannot become static query constants')
        query.append({'predicate': fact['predicate'], 'arguments': arguments})
    before, after = _fragment(example['before']), _fragment(example['after'])
    originals = deepcopy(before), deepcopy(after)
    for name, slot in example['source_slots'].items():
        for side, tree in [('before', before), ('after', after)]:
            for path in slot.get(side + '_paths', []):
                if not _same(_get(tree, path), values[name]):
                    raise ValueError('A source/code correspondence does not equal its actual witnessed value')
                _put(tree, path, {'source': name})
    for name, capture in example.get('copies', {}).items():
        before_paths = capture['before_paths']; after_paths = capture['after_paths']
        if not before_paths:
            raise ValueError('An edit copy must be bound in the old code')
        value = _get(originals[0], before_paths[0])
        for side, paths, raw, tree in [('before', before_paths, originals[0], before),
                                       ('after', after_paths, originals[1], after)]:
            for path in paths:
                if not _same(_get(raw, path), value):
                    raise ValueError('An edit copy must preserve the actual old subtree')
                # An annotated source role must not disappear into a code copy.
                current = _get(tree, path)
                if _contains_marker(current):
                    raise ValueError('Overlapping source and code annotations obscure their binding')
                _put(tree, path, {'copy': name, 'shape': _shape(value)})
    old_names = {n.id for n in ast.walk(ast.parse(example['before'])) if isinstance(n, ast.Name)}
    fresh = {}
    for path, node in _walk(originals[1]):
        if node['ast'] == 'Name' and node['fields']['ctx']['ast'] == 'Store':
            name = node['fields']['id']
            if name not in old_names and name not in fresh:fresh[name] = 'local_' + str(len(fresh))
    for path, node in _walk(originals[1]):
        if node['ast'] == 'Name' and node['fields']['id'] in fresh:
            target = (*path, 'fields', 'id')
            # A new local may be inside an unchanged ancestor only if it was
            # already present before, which is excluded above.
            if isinstance(_get(after, target), dict):
                raise ValueError('A new local cannot also be a legal source parameter')
            _put(after, target, {'fresh': fresh[node['fields']['id']]})
    return query, before, after


def _contains_marker(value):
    if isinstance(value, dict):
        return ('source' in value and len(value) == 1 or 'copy' in value
                or any(_contains_marker(v) for v in value.values()))
    return isinstance(value, list) and any(_contains_marker(v) for v in value)


def _unify_examples(values, captures, *, left):
    if all(_same(values[0], v) for v in values[1:]):
        return deepcopy(values[0])
    first = values[0]
    if all(isinstance(v, dict) and set(v) == set(first) for v in values) and isinstance(first, dict):
        return {k: _unify_examples([v[k] for v in values], captures, left=left) for k in first}
    if isinstance(first, list) and all(isinstance(v, list) and len(v) == len(first) for v in values):
        return [_unify_examples([v[i] for v in values], captures, left=left) for i in range(len(first))]
    if len({_shape(v) for v in values}) != 1:
        raise ValueError('Edit examples need an explicit common AST context')
    key = digest(values)
    if key not in captures:
        if not left:
            raise ValueError('A new varying value needs a witnessed source parameter or an old-code copy')
        captures[key] = 'code_' + str(len(captures))
    return {'copy': captures[key], 'shape': _shape(first)}


def learn(examples, signatures, *, source_constants=None, program_constants=()):
    """Jointly generalize witnessed Q, local B and replacement A.

    A teacher may supply the correspondences/copy context. Equal words do not
    establish correspondence. New legal literals require source bindings;
    fixed API constants must be explicitly declared by the calling language.
    """
    if not examples:
        raise ValueError('Actual source-backed before/after examples required')
    source_constants = {} if source_constants is None else source_constants
    slots = {n: v['sort'] for n, v in examples[0]['source_slots'].items()}
    annotated = []
    for example in examples:
        if slots != {n: v['sort'] for n, v in example['source_slots'].items()}:
            raise ValueError('Corresponded source roles/types must agree between examples')
        annotated_example = _annotate(example, signatures, source_constants)
        old_tree = _fragment(example['before']); after_tree = _fragment(example['after'])
        for path, node in _walk(after_tree):
            if node['ast'] != 'Constant':continue
            literal = node['fields']['value']
            if any(_same(literal, v) for v in program_constants):continue
            # Retention is occurrence-specific. A value used elsewhere in the
            # old code is not a source for a new legal parameter at this site.
            if _retained_literal(old_tree, after_tree, path):continue
            marked = annotated_example[2]; copied = False
            for key in (*path, 'fields', 'value'):
                if isinstance(marked, dict) and set(marked) == {'copy', 'shape'}:
                    copied = True;break
                marked = marked[key]
            copied = copied or isinstance(marked, dict) and set(marked) == {'copy', 'shape'}
            if not copied and (not isinstance(marked, dict) or set(marked) != {'source'}):
                raise ValueError('Every new legal literal occurrence needs its actual source binding')
        annotated.append(annotated_example)
    query = annotated[0][0]
    if any(q != query for q, _, _ in annotated):
        raise ValueError('Examples require explicit relation-role alignment, not positional guessing')
    captures = {}
    before = _unify_examples([x[1] for x in annotated], captures, left=True)
    after = _unify_examples([x[2] for x in annotated], captures, left=False)
    update = {'source_query': query, 'source_sorts': slots, 'before_pattern': before,
        'after_template': after, 'guard': [], 'signatures': deepcopy(signatures),
        'source_constants': deepcopy(source_constants),
        'supporting_events': [e['event_id'] for e in examples],
        'meaning_or_generalization_certified': False}
    update['id'] = digest(update)
    for example in examples:
        # A real local Return subtree is legal inside its owning function,
        # although compiling it as a top-level module is not. Validate learning
        # in an explicit function context; applications still compile the whole
        # actual target program before installation.
        def local_context(code):
            return 'def _joint_update_learning_context():\n' + '\n'.join('    ' + line for line in code.splitlines()) + '\n'
        result = apply(update, example['source_facts'], local_context(example['before']))
        expected = ast.parse(local_context(example['after']))
        old_names = {n.id for n in ast.walk(ast.parse(example['before'])) if isinstance(n, ast.Name)}
        new_names = {}
        for _, node in _walk(_fragment(example['after'])):
            if node['ast'] == 'Name' and node['fields']['ctx']['ast'] == 'Store':
                name = node['fields']['id']
                if name not in old_names and name not in new_names:
                    new_names[name] = result.get('fresh_names', {}).get('local_' + str(len(new_names)))
        for node in ast.walk(expected):
            if isinstance(node, ast.Name) and node.id in new_names and new_names[node.id] is not None:
                node.id = new_names[node.id]
        if result['status'] != 'applied' or _tree(ast.parse(result['program'])) != _tree(expected):
            raise ValueError('Learned update does not uniquely reproduce a supplied real edit')
    return update


def _source_matches(patterns, facts, signatures, initial=None):
    states = [{} if initial is None else deepcopy(initial)]
    sorts = {}
    for pattern in patterns:
        if pattern['predicate'] not in signatures or len(pattern['arguments']) != len(signatures[pattern['predicate']]):
            raise ValueError('Source query/guard signature changed')
        for expected, sort in zip(pattern['arguments'], signatures[pattern['predicate']]):
            if isinstance(expected, dict):
                if set(expected) != {'source'}:raise ValueError('An explicit source role is required')
                name = expected['source']
                if name in sorts and sorts[name] != sort:
                    raise ValueError('Shared source roles have inconsistent nominal types')
                sorts[name] = sort
    for pattern in patterns:
        next_states = []
        for binding in states:
            for fact in facts:
                if fact.get('sign', 'positive') != 'positive' or fact['predicate'] != pattern['predicate']:
                    continue
                if len(fact['arguments']) != len(signatures[fact['predicate']]):
                    raise ValueError('Actual source relation arity changed')
                candidate = deepcopy(binding)
                for expected, actual in zip(pattern['arguments'], fact['arguments']):
                    if isinstance(expected, dict) and set(expected) == {'source'}:
                        name = expected['source']
                        if name in candidate and not _same(candidate[name], actual):break
                        candidate[name] = actual
                    elif not _same(expected, actual):break
                else:
                    if candidate not in next_states:next_states.append(candidate)
        states = next_states
    return states


def _match(pattern, current, source, copies):
    if isinstance(pattern, dict) and set(pattern) == {'source'}:
        return pattern['source'] in source and _same(source[pattern['source']], current)
    if isinstance(pattern, dict) and set(pattern) == {'copy', 'shape'}:
        if _shape(current) != pattern['shape']:return False
        name = pattern['copy']
        if name in copies:return _same(copies[name], current)
        copies[name] = deepcopy(current);return True
    if type(pattern) is not type(current):return False
    if isinstance(pattern, dict):
        return set(pattern) == set(current) and all(_match(v, current[k], source, copies) for k, v in pattern.items())
    if isinstance(pattern, list):
        return len(pattern) == len(current) and all(_match(a, b, source, copies) for a, b in zip(pattern, current))
    return pattern == current


def _build(template, source, copies, fresh):
    if isinstance(template, dict) and set(template) == {'source'}:
        if template['source'] not in source:raise ValueError('Unbound current-source edit parameter')
        return deepcopy(source[template['source']])
    if isinstance(template, dict) and set(template) == {'copy', 'shape'}:
        if template['copy'] not in copies:raise ValueError('Unbound old-code copy')
        return deepcopy(copies[template['copy']])
    if isinstance(template, dict) and set(template) == {'fresh'}:
        return fresh[template['fresh']]
    if isinstance(template, dict):return {k: _build(v, source, copies, fresh) for k, v in template.items()}
    if isinstance(template, list):return [_build(v, source, copies, fresh) for v in template]
    return deepcopy(template)


def _walk(tree, path=()):
    if isinstance(tree, dict):
        if 'ast' in tree:yield path, tree
        for k, v in tree.items():yield from _walk(v, (*path, k))
    elif isinstance(tree, list):
        for i, v in enumerate(tree):yield from _walk(v, (*path, i))


def _fresh_names(template, occupied):
    found = set()
    def visit(value):
        if isinstance(value, dict):
            if set(value) == {'fresh'}:found.add(value['fresh'])
            else:
                for child in value.values():visit(child)
        elif isinstance(value, list):
            for child in value:visit(child)
    visit(template);result = {};index = 0
    for name in sorted(found):
        while '_u_local_' + str(index) in occupied:index += 1
        result[name] = '_u_local_' + str(index);occupied.add(result[name]);index += 1
    return result


def applications(update, source_facts, program, *, source_binding=None):
    """Enumerate matches without discarding source bindings for equal code.

    Multi-component edits must join on the shared binding before deduplication.
    Equal generated code can have different legal witnesses, one of which may
    be the only witness consistent with another component.
    """
    if source_binding is not None and not set(source_binding) <= set(update['source_sorts']):
        raise ValueError('Initial bindings must name the actual learned source roles')
    parsed = ast.parse(program);module = _tree(parsed); outcomes = []
    fresh = _fresh_names(update['after_template'], {n.id for n in ast.walk(parsed) if isinstance(n, ast.Name)})
    bindings = _source_matches(update['source_query'] + update['guard'], source_facts,
                               update['signatures'], initial=source_binding)
    for source in bindings:
        for path, node in _walk(module):
            copies = {}
            if not _match(update['before_pattern'], node, source, copies):continue
            result = _put(deepcopy(module), path, _build(update['after_template'], source, copies, fresh))
            if result == module:continue
            ast_result = ast.fix_missing_locations(_ast(result));compile(ast_result, '<learned_joint_update>', 'exec')
            code = ast.unparse(ast_result) + '\n'
            outcomes.append({'program': code, 'source_binding': source,
                'code_path': list(path), 'code_copies_sha256': digest(copies), 'fresh_names': fresh})
    return outcomes


def apply(update, source_facts, program):
    """Use one shared substitution; preserve ambiguity between distinct edits."""
    outcomes = {}
    for application in applications(update, source_facts, program):
        outcomes.setdefault(digest(_tree(ast.parse(application['program']))), application)
    result = {'status': 'applied' if len(outcomes) == 1 else 'ambiguous' if outcomes else 'not_applicable',
        'update_id': update['id'], 'distinct_candidate_edits': len(outcomes), 'new_model_requests': 0}
    if len(outcomes) == 1:result.update(next(iter(outcomes.values())))
    return result


def learn_guard(update, positive, negative, candidates):
    """Select a smallest positive relational guard from explicit applications.

    Negative examples must be actual, explicitly supported non-applications;
    missing observations and unchanged historical scores are not negatives.
    """
    if not positive:raise ValueError('Guard learning needs supported applicable examples')
    for candidate in candidates:
        sorts = update['signatures'].get(candidate['predicate'])
        if sorts is None or len(sorts) != len(candidate['arguments']):
            raise ValueError('Guard candidates need declared source signatures')
        for argument, sort in zip(candidate['arguments'], sorts):
            if not isinstance(argument, dict) and not any(_same(argument, v)
                    for v in update['source_constants'].get(sort, [])):
                raise ValueError('A current source identity/value cannot become a static guard')
    for size in range(len(candidates) + 1):
        for selected in combinations(range(len(candidates)), size):
            proposal = deepcopy(update);proposal['guard'] = [deepcopy(candidates[i]) for i in selected]
            if not all(apply(proposal, e['source_facts'], e['before'])['status'] == 'applied' for e in positive):continue
            if any(apply(proposal, e['source_facts'], e['before'])['status'] != 'not_applicable' for e in negative):continue
            proposal['guard_evidence'] = {'positive_events': [e['event_id'] for e in positive],
                'negative_events': [e['event_id'] for e in negative], 'selected_candidate_indices': list(selected)}
            proposal['id'] = digest({k: v for k, v in proposal.items() if k != 'id'})
            return proposal
    raise ValueError('No candidate guard satisfies the explicit application evidence')


def _delta(before, after, path=()):
    """An exact structural edit, without charging unchanged surrounding code."""
    if _same(before, after):return []
    if isinstance(before, dict) and isinstance(after, dict) and set(before) == set(after):
        return [e for key in before for e in _delta(before[key], after[key], (*path, key))]
    if isinstance(before, list) and isinstance(after, list):
        if len(before) == len(after):
            return [e for i, (a, b) in enumerate(zip(before, after)) for e in _delta(a, b, (*path, i))]
        start = 0
        while start < min(len(before), len(after)) and _same(before[start], after[start]):start += 1
        suffix = 0
        while suffix < min(len(before), len(after)) - start and _same(before[-1-suffix], after[-1-suffix]):suffix += 1
        return [{'splice': list(path), 'start': start, 'stop': len(before)-suffix,
            'values': deepcopy(after[start:len(after)-suffix if suffix else len(after)])}]
    return [{'replace': list(path), 'value': deepcopy(after)}]


def replay_delta(program, edits):
    tree = _tree(ast.parse(program))
    for edit in edits:
        if 'replace' in edit:tree = _put(tree, edit['replace'], edit['value'])
        else:
            values = _get(tree, edit['splice'])
            values[edit['start']:edit['stop']] = deepcopy(edit['values'])
    return ast.unparse(ast.fix_missing_locations(_ast(tree))) + '\n'


def candidates(updates, source_facts, program):
    """Construct actual edits and a frozen two-part conditional coding prior.

    The dictionary/order must be fixed before subsequent data. Dictionary
    acquisition/storage is a separate cost; source values are current inputs.
    These byte lengths are a program prior, not model tokens or billing. Native
    and explicit source correctness still govern a caller's final selection.
    """
    def size(value):
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
    def written(value):
        if isinstance(value, dict):
            if set(value) == {'source'}:return {value['source']}
            return set().union(*(written(v) for v in value.values())) if value else set()
        return set().union(*(written(v) for v in value)) if isinstance(value, list) and value else set()
    result = []
    for index, update in enumerate(updates):
        application = apply(update, source_facts, program)
        if application['status'] != 'applied':continue
        edits = _delta(_tree(ast.parse(program)), _tree(ast.parse(application['program'])))
        if _tree(ast.parse(replay_delta(program, edits))) != _tree(ast.parse(application['program'])):
            raise ValueError('The raw edit coding must exactly reconstruct the actual candidate')
        macro = {'update_index': index, 'code_path': application['code_path'],
            'current_source_parameters': {k: application['source_binding'][k]
                for k in sorted(written(update['after_template']))}}
        raw_bytes, macro_bytes = size({'raw_edit': edits}), size({'macro_edit': macro})
        result.append({**application, 'raw_edit': edits, 'macro_edit': macro,
            'raw_edit_bytes': raw_bytes, 'macro_edit_bytes': macro_bytes,
            'conditional_edit_bytes': min(raw_bytes, macro_bytes),
            'coding': 'frozen_canonical_JSON_utf8_raw_delta_or_template_and_current_parameters_v1',
            'dictionary_sha256': digest(updates), 'dictionary_bytes': size(updates)})
    return sorted(result, key=lambda r: (r['conditional_edit_bytes'], r['update_id']))
