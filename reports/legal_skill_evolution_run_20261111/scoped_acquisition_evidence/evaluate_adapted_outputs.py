"""Reproduce the terminal v5 acquisition with one explicit singleton adapter.

The original proposals and acquisition source remain byte-identical. This
launcher changes no learned program or source interpretation. Both methods
then use the original evaluator and its fixed development/reuse/ablation order.
"""
from copy import deepcopy
import ast
import hashlib
import json
from pathlib import Path

import jsonschema
from experiments import legal_skill_evolution_scoped_acquisition as original
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.scoped_grammar import constructors, induce, term_sort
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure


def adapted_proposal(folder, phase, arm, public, protocol):
    if arm != 'ScopedGrammar':
        return RAW_COMPILE(folder, phase, arm, public, protocol)
    raw = original.read(folder / f'phase{phase}' / arm / 'teacher.json')
    value = deepcopy(raw['value'])
    seed = value['grammar']['seeds'][9]
    tree = json.loads(seed['term_json'])
    schema = constructors(value['grammar'])
    assert tree[0] == 'prohibition'
    assert term_sort(tree[4], schema) == 'Exception'
    assert schema['prohibition']['arguments'][3] == 'ExceptionSet'
    injections = [c for c in schema.values()
                  if c['sort'] == 'ExceptionSet' and c['arguments'] == ['Exception']]
    assert len(injections) == 1 and injections[0]['name'] == 'exception_set'
    assert injections[0]['meaning'] == 'A singleton exception set.'
    tree[4] = ['exception_set', tree[4]]
    seed['term_json'] = json.dumps(tree, ensure_ascii=False)
    jsonschema.validate(value, original.PROPOSAL)
    keys = protocol['initial_sources'] + protocol['update_sources']
    grammar = induce(value['grammar'], {k: public[k]['views'][0]['public'] for k in keys})
    validate_procedure(value['source_program'], allow_helpers=True)
    assert not any(isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and n.value in original.LABELS
                   for n in ast.walk(ast.parse(value['source_program'])))
    assert value['source_program'] == raw['value']['source_program']
    assert value['grammar']['decision_program'] == raw['value']['grammar']['decision_program']
    immutable_json(folder / f'phase{phase}' / arm / 'adapted_proposal.json', value)
    immutable_json(folder / f'phase{phase}' / arm / 'induced_grammar.json', grammar)
    return value, grammar


RAW_COMPILE = original.compiled_proposal


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[3]
    folder, protocol, ledger, public = original.setup(root)
    assert (folder / 'PRESERVED_AFTER_TEACHERS.json').exists()
    assert not original.read(folder / 'phase2/teachers_settled.json')['errors']
    paths = {**protocol['source_snapshot'], str(Path(__file__).relative_to(root)):
             hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    immutable_json(folder / 'postgeneration_execution_manifest.json', {
        'base_protocol_sha256': hashlib.sha256((folder / 'protocol.json').read_bytes()).hexdigest(),
        'source_snapshot': paths,
        'adaptation': original.read(folder / 'postgeneration_type_adaptation.json'),
        'same_two_frozen_reuse_sources': protocol['reuse_sources'],
        'new_physical_requests': 0, 'learned_programs_changed': False,
        'no_new_sources_DEV_TEST_or_tuning': True})
    # Dependency substitution is confined to this receipt-bearing reproduction;
    # the raw acquisition runner and teacher outputs remain unchanged.
    original.compiled_proposal = adapted_proposal
    for arm in original.ARMS:
        adapted_proposal(folder, 2, arm, public, protocol)
    original.evaluate(root, 2)
    original.evaluate(root, 2, reuse=True)
    original.evaluate(root, 2, reuse=True, nofactor=True)
