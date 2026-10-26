"""Exact, prospective execution-version provenance; no arbitrary hash waiver.

Only the four recorded learning drivers/shared teacher module may have a prior
version. The current bundle is bound byte-for-byte. Original actor, grader and
gate functions must also match their preserved, hash-bound source. No run data,
prediction, label, publication, transport or scorer has a version exception.
"""
from __future__ import annotations

import ast
from pathlib import Path

from legal_skill_guard.learning.experiment import sha

SCHEDULE = 'seed45_serial_seed145245_phase_dispatch_v1'
PROTOCOL = 'docs/research/OPENEXEMPT_PROSPECTIVE_PHASE_DISPATCH_20261023.md'
CONTROL_SCHEDULE = 'original45_serial_uniform45_controls_phase_dispatch_v2'
CONTROL_PROTOCOL = 'docs/research/OPENEXEMPT_UNIFORM_ABLATION_ACCELERATION_20261025.md'
DECLARATION = {'policy': 'ordered_independent_phases_v1', 'native_workers': 4,
               'teacher_workers': 2, 'required_max_num_seqs': 4}
SERIAL_RECEIPT = {**DECLARATION, 'native_workers': 1, 'teacher_workers': 1,
                  'required_max_num_seqs': 1}
SNAPSHOTS = ('artifacts/research/openexempt_legal_scope_20261020/'
             'source_snapshots/runtime_versions_20261023')
CURRENT = {
    'experiments/openexempt_online.py':
        'e8a2d2e4eff63d2d1cda876e3de545db60459bbf69a7573e2fc098ff94773705',
    'experiments/openexempt_ace_online.py':
        '9e31e3e38be8a06f483ba3efa9a25ce2f541d5e317c31f0f56c1df872d6be598',
    'experiments/openexempt_trace2skill.py':
        'e9ecb72ae4ca1c0f867d94944366e73b08797d679a68777bd939e9798c61ecfc',
    'legal_skill_guard/learning/experiment.py':
        '3c583be8b82c16955cb175a477b716fa68a2c6a3e7fb32f2a302d8a010e2f35b',
    'legal_skill_guard/learning/phase_dispatch.py':
        '7ac30f501954ef12753bf7eb91673f4cf036a2a03ffc7345691fa8cdefafa16f',
}
HISTORICAL = {
    'experiments/openexempt_online.py': {
        '732f1a924d0e49333de0384b5d6a63a25d990eb9d187874a9b1e54d114032c1c':
            'openexempt_online'},
    'experiments/openexempt_ace_online.py': {
        '9321cb95d4374467484e34d46170a59e1911ba299f3a922ebd566fb7169c3fc0':
            'openexempt_ace_online'},
    'experiments/openexempt_trace2skill.py': {
        'b7277fb9d6e94abac4ffd92e1c74e66f477ccbcab7523f886b993346ab5dc5b7':
            'openexempt_trace2skill'},
    'legal_skill_guard/learning/experiment.py': {
        '07a4f9599d72da83be97eac54c04e4601ebae8645506b06615f0830a14bfca88':
            'experiment',
        '7f598092149e21d0bfec923e682d19a046ae61a88c112a4768669e9d81369e17':
            'experiment_before_teacher_timeout_logs_20261023'},
}
PROTECTED = {
    'experiments/openexempt_online.py': (
        'Online.answer', 'Online.grade', 'actor_payload', 'direct_case_input', 'acceptance',
        'task_admission', 'legal_scope_admission'),
    'experiments/openexempt_ace_online.py': ('ACEOnline.answer', 'ACEOnline.train_solved'),
    'experiments/openexempt_trace2skill.py': ('validate_profile',),
    'legal_skill_guard/learning/experiment.py': ('Comparison.call', 'Comparison.check'),
}


def checked_path(root, name):
    path = root / name
    if Path(name).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Execution source must remain inside the project: ' + name)
    return path


def validate_bundle(root):
    files = {checked_path(root, name) for name in CURRENT}
    if any(not (root / name).is_file() or sha(root / name) != digest
           for name, digest in CURRENT.items()):
        raise ValueError('The prospective phase-dispatch source bundle changed')
    return files | {checked_path(root, 'legal_skill_guard/learning/runtime_sources.py')}


def function_ast(path, qualified):
    body = ast.parse(path.read_text()).body
    for name in qualified.split('.'):
        matches = [n for n in body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                   and n.name == name]
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous protected function: ' + qualified)
        node = matches[0]
        body = node.body
    return ast.dump(node, include_attributes=False)


def verify_revision(root, name, expected):
    """Resolve only an approved runtime version, retaining its actual source."""
    if name not in HISTORICAL:
        raise ValueError('No execution-version exception for: ' + name)
    extras = validate_bundle(root)
    if expected == CURRENT[name]:
        return extras
    stem = HISTORICAL[name].get(expected)
    if stem is None:
        raise ValueError('Unknown historical execution-source hash: ' + name)
    original = checked_path(root, f'{SNAPSHOTS}/{stem}__{expected}.py')
    if not original.is_file() or sha(original) != expected:
        raise ValueError('The exact original execution source is missing or changed: ' + name)
    if any(function_ast(original, function) != function_ast(root / name, function)
           for function in PROTECTED[name]):
        raise ValueError('A protected actor, grader or gate changed: ' + name)
    return extras | {original}


def uniform_control(source):
    """Only the explicitly amended two seed45 ablations, never a main repeat."""
    variant = source.get('ablation_variant')
    return (source.get('ablation_execution_schedule') == CONTROL_SCHEDULE
            and source.get('execution_order_addendum') == CONTROL_PROTOCOL
            and source.get('generation', {}).get('seed') == 45
            and variant in ('whole_bank', 'task_local')
            and source.get('skill_commit_policy') == variant
            and source.get('candidate_feedback_policy') == 'carry_partial_and_refine')


def validate_learning_receipt(root, source, frozen, initial, complete, *,
                              allow_uniform_control=False):
    """Bind explicit scheduling, captured service and the actual learner receipts."""
    seed = source['generation']['seed']
    amended = allow_uniform_control and uniform_control(source)
    if source.get('ablation_execution_schedule') is not None and not amended:
        raise ValueError('Only the explicitly amended ablation may change its execution profile')
    expected = DECLARATION if seed != 45 or amended else None
    if seed not in (45, 145, 245) or source.get('phase_dispatch') != expected:
        raise ValueError('Keep seed45 serial and declare the matched145/245 dispatch')
    if seed != 45 or amended:
        if any(frozen['files'].get(name) != digest for name, digest in CURRENT.items()):
            raise ValueError('New learning must freeze the exact prospective runtime bundle')
        if any(record.get('execution_dispatch') != DECLARATION for record in (initial, complete)):
            raise ValueError('New learning receipts disagree with the declared execution schedule')
    else:
        names = ['experiments/openexempt_online.py',
                 'legal_skill_guard/learning/experiment.py']
        if source.get('learner') == 'ace_native_online_v4':
            names.append('experiments/openexempt_ace_online.py')
        if source.get('learner') == 'trace2skill_text_offline_v1':
            names.append('experiments/openexempt_trace2skill.py')
        if any(frozen['files'].get(name) not in HISTORICAL[name] for name in names):
            raise ValueError('Seed45 must retain its original serial learning-source version')
        if any(record.get('execution_dispatch') not in (None, SERIAL_RECEIPT)
               for record in (initial, complete)):
            raise ValueError('The seed45 learning runtime must remain serial')
    environment = checked_path(root, source['inference_environment'])
    if frozen['files'].get(source['inference_environment']) != sha(environment):
        raise ValueError('Bind the actual learning environment, not a rewritten capture')
    return environment
