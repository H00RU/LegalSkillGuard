"""Resolve explicit references to code/types already present in the teacher task.

The Free teacher referenced the supplied C helpers without redeclaring them.
Only exact, uniquely named definitions are imported, transitively. No aliases,
new legal logic, model call or label-guided correction is permitted.
"""
import ast
from copy import deepcopy
import json

from experiments import legal_skill_evolution_source_local_preview as preview
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.source_function_patch import apply_function_edits, function_bytes
from legal_skill_guard.skill_evolution.span_compiler import CALLS
from legal_skill_guard.skill_evolution.objects import digest


current = preview.current
OUT = current.OUT / 'unbound_control_reference_recovery'


def recover():
    task = current.read(current.OUT / 'teacher_task.json')
    original = current.read(current.OUT / 'FreeUpdate/teacher.json')['value']
    packet = deepcopy(original)
    prior = deepcopy(task['current_libraries']['FreeUpdate'])
    shared = task['current_libraries']['ConstraintAcquire']
    existing = function_bytes(prior['source_program'])
    provided = function_bytes(shared['source_program'])
    edits = {e['name']: e['code'] for e in packet.pop('source_function_edits')}
    imported = {}
    while True:
        definitions = {**existing, **imported, **edits}
        calls = {n.func.id for code in definitions.values() for n in ast.walk(ast.parse(code))
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        missing = calls - set(definitions) - CALLS
        if not missing:
            break
        for name in sorted(missing):
            if name not in provided or name == 'apply':
                raise ValueError('No unique existing supplied definition for ' + name)
            imported[name] = provided[name]
    final_edits = [{'name': n, 'code': code} for n, code in {**imported, **edits}.items()]
    packet['source_program'], preservation = apply_function_edits(prior['source_program'], final_edits)
    # These are the exact five already supplied atom definitions. They are
    # schema dependencies of the explicitly referenced helper modules.
    known = {c['name']: c for c in prior['spec']['constructors']}
    new = {c['name']: c for c in packet['new_constructors']}
    required = {c['name']: c for c in shared['spec']['constructors'] if c['name'].startswith('acq_')}
    for name, constructor in required.items():
        if name in known:
            assert known[name] == constructor
        elif name in new:
            assert new[name] == constructor
        else:
            packet['new_constructors'].append(deepcopy(constructor))
    immutable_json(OUT / 'original_rejection.json', {'error': 'Unsupported call: sp_retention',
        'original_response_sha256': digest(original), 'physical_response_unchanged': True})
    immutable_json(OUT / 'canonical_proposal.json', packet)
    immutable_json(OUT / 'exact_reference_receipt.json', {
        'supplied_library_sha256': digest(shared), 'imported_helpers': {n: digest(c) for n, c in imported.items()},
        'imported_existing_atom_types': sorted(set(required) - set(known) - set(new)),
        'native_labels_consulted_by_recovery': False, 'new_code_or_semantics_invented': False,
        'function_patch_preservation': preservation, 'new_model_calls': 0})
    return packet


def run():
    packet = recover()
    # Reuse the actual producer/consumer driver with an explicit proposal.
    preview.run('FreeUpdate', proposal=packet, output_folder=OUT / 'execution', complete_program=True)


if __name__ == '__main__':
    run()
