"""Apply explicit function edits to the current learned source program.

Untouched functions retain their exact bytes. This prevents an acquisition
update from silently replacing unrelated learned code; actual source/nativity
checks still decide whether the candidate is useful. It is shared to controls.
"""
import ast

from .objects import digest
from .span_compiler import validate_procedure


def function_bytes(program):
    lines = program.splitlines(keepends=True)
    return {node.name: ''.join(lines[node.lineno - 1:node.end_lineno])
            for node in ast.parse(program).body}


def apply_function_edits(program, edits):
    validate_procedure(program, allow_helpers=True)
    tree = ast.parse(program)
    old_nodes = {node.name: node for node in tree.body}
    replacements = {}
    for edit in edits:
        if set(edit) != {'name', 'code'} or edit['name'] in replacements:
            raise ValueError('One explicit source-function definition per edited name')
        nodes = ast.parse(edit['code']).body
        if len(nodes) != 1 or not isinstance(nodes[0], ast.FunctionDef) or nodes[0].name != edit['name']:
            raise ValueError('An edit must define exactly its declared source function')
        replacements[edit['name']] = edit['code'].rstrip() + '\n'
    lines = program.splitlines(keepends=True)
    result, cursor = [], 0
    for node in tree.body:
        result.extend(lines[cursor:node.lineno - 1])
        result.append(replacements.get(node.name, ''.join(lines[node.lineno - 1:node.end_lineno])))
        cursor = node.end_lineno
    result.extend(lines[cursor:])
    for name, code in replacements.items():
        if name not in old_nodes:
            result.extend(['\n', code])
    updated = ''.join(result)
    validate_procedure(updated, allow_helpers=True)
    before, after = function_bytes(program), function_bytes(updated)
    unchanged = set(before) - set(replacements)
    assert all(before[name] == after[name] for name in unchanged)
    return updated, {'before_program_sha256': digest(program), 'after_program_sha256': digest(updated),
        'edited_functions': sorted(set(before) & set(replacements)),
        'added_functions': sorted(set(replacements) - set(before)),
        'untouched_functions_byte_equal': sorted(unchanged),
        'does_not_certify_no_semantic_regression': True}
