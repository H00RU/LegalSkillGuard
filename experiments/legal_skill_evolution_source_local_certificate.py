"""Check a local C objective certificate using its actual positive rule closure.

This certifies the fixed eight-source native objective under the declared bias,
not source truth, transfer, or the full five-dataset training objective.
"""
import ast
from copy import deepcopy
import json

from experiments import legal_skill_evolution_source_local_preview as preview
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.open_acquisition import execute
from legal_skill_guard.skill_evolution.span_compiler import execute_json
from legal_skill_guard.skill_evolution.objects import digest


current = preview.current
OUT = current.OUT / 'unbound_local_objective_certificate'


def run():
    folder = current.OUT / 'unbound_proposed_execution/ConstraintAcquire'
    library = current.read(folder / 'library.json')
    before = current.read(current.OUT / 'teacher_task.json')['current_libraries']['ConstraintAcquire']
    old_rules = {r['id']: r for r in before['language']['rules']}
    new_rules = {r['id']: r for r in library['language']['rules']}
    assert all(new_rules[k] == v for k, v in old_rules.items())
    added = set(new_rules) - set(old_rules)
    selected_delta = set(library['selected_rule_ids']) ^ set(before['selected_rule_ids'])
    expected = {'read_complete_source_absence_v4', 'compose_complete_no_disposal_v4', 'compose_complete_no_retention_v4'}
    assert selected_delta == expected and selected_delta <= added
    assert all(a['sign'] == 'positive' for r in new_rules.values() for a in [r['head'], *r['body']])
    assert all(r['head']['predicate'] != a['predicate'] or r['head'] != a for r in new_rules.values() for a in r['body'])
    renderers = {r['predicate']: r for r in library['renderers']}
    absence_heads = {}
    for predicate, renderer in renderers.items():
        if renderer['term'][0] in ('complete_source_no_disposal_obligation', 'complete_source_no_retention_effect'):
            absence_heads[predicate] = renderer['term'][0]
    assert absence_heads == {'emit_complete_no_disposal_v4': 'complete_source_no_disposal_obligation',
                             'emit_complete_no_retention_v4': 'complete_source_no_retention_effect'}
    producers = {h: [r for r in new_rules.values() if r['head']['predicate'] == h] for h in absence_heads}
    assert all(all(any(a['predicate'] == 'd_complete_source_absence_v4' for a in r['body']) for r in rs) for rs in producers.values())
    assert [r['id'] for r in new_rules.values() if r['head']['predicate'] == 'd_complete_source_absence_v4'] == ['read_complete_source_absence_v4']
    maximum = deepcopy(library)
    maximum['selected_rule_ids'] = list(new_rules)
    closures = {}
    for prefix in ('8fb38', 'a5b036'):
        path = next(folder.glob('ContractNLI_' + prefix + '*.json'))
        row = current.read(path)
        observation = row['observation']
        assert observation['context']['unknown_groups'] == []
        result = execute(maximum, observation)
        immutable_json(OUT / (prefix + '_maximum_closure.json'), result)
        output = result['source_output']
        source_norms = [r['term'] for r in observation['visible_inputs']['source_output']['statements']]
        consumer = library['spec']['decision_program']
        tree = ast.parse(consumer)
        functions = [ast.get_source_segment(consumer, n) for n in tree.body if n.name != 'apply']
        probe = '\n\n'.join(functions) + '''\n\ndef apply(inputs,premises):
    endpoints=[]
    for row in inputs['statements']:
        t=row['term']
        if t[0]=='disposal_obligation' and d_endpoint_trigger(t[3]):
            endpoints.append(t)
    return {'endpoints':endpoints}
'''
        check = execute_json(probe, output, {}, allow_helpers=True)
        assert not check['endpoints']
        closures[prefix] = {'source': row['source'], 'source_output_root_constructors': sorted({t[0] for t in source_norms}),
            'maximum_output_root_constructors': sorted({r['term'][0] for r in output['statements']}),
            'native_endpoint_in_maximum_positive_closure': False}
        if prefix == 'a5b036':
            assert not any(t[0] in ('complete_source_no_disposal_obligation', 'complete_source_no_retention_effect',
                'disposal_obligation', 'retention_permission', 'retention_prohibition') for t in source_norms)
    # Frozen consumer's nda16 Entailment branch requires a disposal endpoint.
    apply = next(n for n in tree.body if n.name == 'apply')
    nda16 = next(n for n in ast.walk(apply) if isinstance(n, ast.If) and ast.unparse(n.test) == "task == 'nda-16'")
    entailment_returns = [n for n in ast.walk(nda16) if isinstance(n, ast.Return)
        and isinstance(n.value, ast.Dict) and any(isinstance(v, ast.Constant) and v.value == 'Entailment' for v in n.value.values)]
    assert len(entailment_returns) == 1
    endpoint_guard = next(n for n in nda16.body if isinstance(n, ast.If) and ast.unparse(n.test) == 'endpoint')
    assert entailment_returns[0] in list(ast.walk(endpoint_guard))
    new_complexity = sum(new_rules[k]['cost'] for k in expected)
    assert new_complexity == 5
    assert all(min(r['cost'] for r in rs) == 2 for rs in producers.values())
    observed = current.read(folder / 'result.json')
    assert observed['correct'] == 31 and observed['total_views'] == 32
    certificate = {'scope': 'fixed_eight_original_TRAIN_mothers_only', 'same_goal': True,
        'library_sha256': digest(library), 'all24_old_candidate_rule_definitions_equal': True,
        'all_rules_positive_and_no_unknown_groups_in_witnesses': True, 'checked_maximum_closures': closures,
        'native_loss_lower_bound': 1, 'observed_native_loss': 1,
        'lower_bound_reason': '8fb nda16 requires an endpoint for Entailment; even all positive rules derive none. Every subset has a subset of these outputs.',
        'selection_edit_lower_bound': 3, 'observed_selection_edits': 3,
        'edit_bound_reason': 'a5b has neither disposal/retention rules nor direct absence roots. Both required distinct absence outputs need separate emitters, and each requires the uniquely produced new read relation. All three were absent from the old selected set.',
        'new_complexity_lower_bound_given_three_edits': 5, 'observed_added_complexity': new_complexity,
        'lexicographic_objective_certified': 'native_loss, selection_edits, complexity',
        'exhaustive_solver_fit_run': False, 'no_new_model_calls': True,
        'source_semantics_or_independent_contribution_certified': False, 'goal_complete': False}
    immutable_json(OUT / 'certificate.json', certificate)
    print(json.dumps({k: certificate[k] for k in ('native_loss_lower_bound', 'observed_native_loss',
        'selection_edit_lower_bound', 'observed_selection_edits', 'exhaustive_solver_fit_run')}), flush=True)


if __name__ == '__main__':
    run()
