"""Compile actual scope repairs and preserve source/program learning events.

No model client is available here. The other original six mothers are fixed
regressions with known historical exposure, not a fresh held-out experiment.
"""
import ast
import argparse
from copy import deepcopy
import json
import traceback

from experiments import legal_skill_evolution_source_gap_acquisition as e
from experiments import legal_skill_evolution_source_scope_repair as repair
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.scoped_grammar import constructors, term_sort


class NoCalls:
    def generate(self, *args, **kwargs):
        raise AssertionError('This offline semantic check cannot dispatch models')


def changed_functions(before, after):
    def functions(program):
        return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(program).body}
    old, new = functions(before), functions(after)
    return sorted(n for n in set(old) | set(new) if old.get(n) != new.get(n))


def run(*, free_schema_imports=False):
    protocol, _ = repair.setup()
    task = e.read(repair.OUT / 'teacher_task.json')
    old_protocol, _, public = e.setup()
    grading = e.read(e.previous.prior.prior.GRADING)
    contract_sources = {k: v for k, v in public.items() if k.startswith('ContractNLI:')}
    for arm in e.ARMS:
        path = repair.OUT / arm / 'teacher.json'
        if not path.exists():
            continue
        old = task['actual_current_libraries_both_available'][arm]
        raw = e.read(path)['value']
        target = repair.OUT / arm
        compiled = target / 'compiled.json'
        if free_schema_imports and arm == 'FreeUpdate':
            target = target / 'unbound_schema_imports'
            compiled = target / 'library.json'
            assert compiled.exists(), 'Create and verify explicit schema import evidence first'
        if compiled.exists():
            library = e.read(compiled)
        else:
            try:
                assert raw['decision_functions'] == [], 'Consumer was frozen for this repair'
                assert raw['operations'] == [] and raw['reading_contracts'] == [], 'No new neural reads planned'
                library, receipt, canonical = e.compile_raw(old, raw, arm, contract_sources)
                assert library['spec']['decision_program'] == old['spec']['decision_program']
                immutable_json(compiled, library)
                immutable_json(repair.OUT / arm / 'canonical_proposal.json', canonical)
                immutable_json(repair.OUT / arm / 'compilation_receipt.json', receipt)
            except Exception as error:
                immutable_json(repair.OUT / arm / 'unbound_original_compile_error.json',
                    {'exception_type': type(error).__name__, 'message': str(error),
                     'traceback': traceback.format_exc(), 'new_model_requests': 0})
                print(json.dumps({'arm': arm, 'compile_failed': str(error)}), flush=True)
                continue
        for key in old_protocol['acquisition_sources']:
            dst = target / 'execution' / e.name_for(key)
            if dst.exists():
                continue
            pub, units, _ = e.previous.prior.prior.source_material(e.previous.PARENT, public, key)
            upstream = e.read(e.OUT / 'upstream' / e.name_for(key))['source_output']
            observation = observe(NoCalls(), repair.RUN + ':offline:' + arm + ':' + key, key, library,
                source_text=pub['source_text'], units=units, source_output=upstream)
            if arm == 'ConstraintAcquire':
                original_norms = {digest(r['term']) for r in upstream['statements']}
                schema = constructors(library['spec'])
                assert all(term_sort(r['term'], schema) != 'Norm' or digest(r['term']) in original_norms
                    for r in observation['visible_inputs']['source_output']['statements'])
            direct = deepcopy(library)
            if arm == 'ConstraintAcquire':
                direct['selected_rule_ids'] = library['suggested_rule_ids']
            actual = e.previous.prior.prior.evaluate_source(direct, observation, public[key], grading[key])
            immutable_json(dst, {'source': key, 'observation': observation, 'actual': actual,
                'repair_acquisition': key in protocol['acquisition_sources'],
                'previously_exposed_original_TRAIN_not_new_blind_validation': True,
                'new_model_requests': 0})
            print(json.dumps({'arm': arm, 'source': key,
                'correct': sum(bool(v['score'] and v['score']['correct']) for v in actual['feedback']['views']),
                'core': sum(v['core_executed'] for v in actual['feedback']['views']),
                'new_model_requests': 0}), flush=True)
        components = ['source_program', 'language', 'renderers'] if arm == 'ConstraintAcquire' else ['source_program', 'composition_program']
        events = []
        for key in protocol['acquisition_sources']:
            before = e.read(e.OUT / 'unbound_pure_preview' / arm / e.name_for(key))
            after = e.read(target / 'execution' / e.name_for(key))
            events.append({'source': key, 'actual_source_facts_before_update': before['observation']['context']['facts'],
                'before_visible_inputs_sha256': before['observation']['visible_inputs_sha256'],
                'after_visible_inputs_sha256': after['observation']['visible_inputs_sha256'],
                'partial_review': repair.REVIEW,
                'actual_component_changes': {c: {'before': old[c], 'after': library[c]} for c in components if old[c] != library[c]},
                'source_functions_changed': changed_functions(old['source_program'], library['source_program']),
                'source_parameter_correspondences_acquired': False,
                'not_an_automatically_valid_U_training_example': True})
        immutable_json(target / 'actual_source_program_repair_events.json',
            {'events': events, 'U_learned': False, 'new_model_requests': 0})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--free-schema-imports', action='store_true')
    run(free_schema_imports=parser.parse_args().free_schema_imports)
