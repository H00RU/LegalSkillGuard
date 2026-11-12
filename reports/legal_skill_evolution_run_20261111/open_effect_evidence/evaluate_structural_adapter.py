"""Replay actual proposals after lossless top-level function-array splitting.

The teacher emitted several complete definitions in each array item. This
adapter changes array grouping only; executable ASTs and legal terms stay fixed.
Original frozen acquisition and recovery scripts are not edited.
"""
import ast
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('open_effect_recovery', Path(__file__).with_name('recover_and_validate.py'))
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
recovery.ROOT = ROOT
study = recovery.study


def structural_only(base, proposal, materials):
    adapted = deepcopy(proposal)
    checks = {}
    for key in ('source_functions', 'decision_functions'):
        parts = []
        before = []
        for body in proposal[key]:
            tree = ast.parse(body)
            if not tree.body or any(not isinstance(n, ast.FunctionDef) for n in tree.body):
                raise ValueError('Only complete acquired function definitions may be regrouped')
            before.extend(tree.body)
            parts.extend(ast.get_source_segment(body, n) for n in tree.body)
        if len({n.name for n in before}) != len(before):
            raise ValueError('Duplicate names require a semantic decision, not grouping adaptation')
        original_ast = ast.dump(ast.Module(body=before, type_ignores=[]), include_attributes=False)
        regrouped_ast = ast.dump(ast.parse('\n\n'.join(parts)), include_attributes=False)
        if original_ast != regrouped_ast:
            raise ValueError('Function regrouping changed executable AST')
        adapted[key] = parts
        checks[key] = {'items_before': len(proposal[key]), 'items_after': len(parts),
                       'function_names': [n.name for n in before], 'executable_AST_identical': True}
    if adapted != proposal:
        folder = ROOT / 'artifacts' / study.RUN / 'SourceEffect'
        immutable_json(folder / 'structural_recovery.json', {
            'raw_proposal_digest': digest(proposal), 'adapted_digest': digest(adapted),
            'checks': checks, 'constructors_examples_and_all_function_bodies_unchanged': True,
            'native_labels_used': False, 'host_created_legal_rules': False,
            'new_physical_requests': 0})
        immutable_json(folder / 'adapted_proposal.json', adapted)
    return recovery.metadata_only(base, adapted, materials)


if __name__ == '__main__':
    folder, protocol, ledger, public = study.setup(ROOT)
    old = study.read(folder / 'recovery_execution_manifest.json')
    recovery_path = ROOT / old['recovery_source']
    assert hashlib.sha256(recovery_path.read_bytes()).hexdigest() == old['recovery_sha256']
    immutable_json(folder / 'structural_execution_manifest.json', {
        'protocol_sha256': hashlib.sha256((folder / 'protocol.json').read_bytes()).hexdigest(),
        'previous_recovery_manifest_sha256': hashlib.sha256((folder / 'recovery_execution_manifest.json').read_bytes()).hexdigest(),
        'adapter_source': str(Path(__file__).relative_to(ROOT)),
        'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'all_original_bound_source_unchanged': True, 'no_new_model_requests': True,
        'no_reuse_source_or_label_used_by_adapter': True, 'goal_complete': False})
    study.materialize = structural_only
    # Materialize both before grading or opening the fixed reuse sources.
    for arm in study.ARMS:
        study.compiled(folder, protocol, public, arm)
    study.evaluate(ROOT)
    study.evaluate(ROOT, reuse=True)
    study.parse = recovery.policy_bank(ROOT, folder, public)
    study.evaluate(ROOT, cache=True)
    study.evaluate(ROOT, reuse=True, cache=True)
