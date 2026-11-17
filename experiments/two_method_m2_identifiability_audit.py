"""Audit primary M2 identifiability using frozen real pilot constraints.

No graph repair, native scoring, new calibration, target labels or generation.
The all-unknown witness is an analytic property of the declared unrestricted
model, not a small-sample performance estimate. Conditional mode is separate.
"""
from collections import defaultdict
from pathlib import Path
import ast
import json

import numpy as np

from experiments.two_method_graph_corpus import BASE, ROOT, read, restore_pair, sha
from experiments.two_method_native_selection import restore_channel
from legal_skill_guard.paired_interfaces.native_channel_selection import choose_risks
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


SNAPSHOT = BASE / ('observed_abstention_channel_v3/'
    '8ab84a2860a622bcecbd94b2b340fbc3d38b5e22c420f0c8dfa8eb9b104cd44d/snapshots/'
    'ca524c1fe10e6024e17a5a693eebcf43e64eede1a5dd5eb863417eb5224d5385')


def channel_witness(channel):
    """Check an explicit simplex witness independently of solving an LP."""
    n = len(channel.edits)
    if channel.A.ndim != 2 or channel.A.shape != (len(channel.b), n + 1):
        raise ValueError('The original channel constraint dimensions changed')
    witness = np.zeros(n + 1); witness[-1] = 1.
    violation = float(np.max(channel.A @ witness - channel.b))
    feasible = bool(violation <= 1e-10)
    # The unrestricted fit contributes [certain,0] <= U and
    # [-possible,-1] <= -L, where 0 <= L <= U <= 1.
    template = (channel.A.shape[0] % 2 == 0
                and np.allclose(channel.A[0::2, -1], 0., atol=1e-14)
                and np.allclose(channel.A[1::2, -1], -1., atol=1e-14)
                and np.all((channel.b[0::2] >= 0.) & (channel.b[0::2] <= 1.))
                and np.all((channel.b[1::2] >= -1.) & (channel.b[1::2] <= 0.)))
    objectives = {'all_modeled_losses_zero': [0.] * n,
                  'heterogeneous_modeled_losses': [(i + 1.) / (n + 1.) for i in range(n)],
                  'all_modeled_losses_one': [1.] * n}
    intervals = {name: channel.bounds(values, values) for name, values in objectives.items()}
    # The last coefficient of every native-risk upper objective is 1.
    # Feasibility of this unit vector proves the max is >=1; normalized
    # nonnegative weights and bounded losses prove it is <=1.
    return {'unknown_mode': channel.unknown_mode, 'modeled_edits': n,
            'calibration_mothers': len(channel.sources), 'unknown_mass_one_feasible': feasible,
            'explicit_witness': witness.tolist(), 'witness_sum': float(witness.sum()),
            'maximum_inequality_violation': violation,
            'unrestricted_constraint_template_verified': bool(template),
            'bounded_loss_objective_checks': intervals,
            'all_checked_upper_bounds_one': all(abs(v[1] - 1.) <= 1e-10 for v in intervals.values()),
            'arbitrary_bounded_upper_loss_one_proved_by_witness': feasible,
            'objective_vectors_are_algebra_checks_not_new_native_trials': True}


def selector_contract(path):
    tree = ast.parse(Path(path).read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'select')
    primary = costs_zero = False
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign): continue
        names = {n.id for n in node.targets if isinstance(n, ast.Name)}
        value = node.value
        if ('choice' in names and isinstance(value, ast.Subscript)
                and isinstance(value.value, ast.Name) and value.value.id == 'm2'
                and isinstance(value.slice, ast.Constant) and value.slice.value == 'unrestricted'):
            primary = True
        if ('costs' in names and isinstance(value, ast.DictComp)
                and isinstance(value.value, ast.Constant) and value.value.value == 0.):
            costs_zero = True
    return {'primary_selects_unrestricted_mode': primary,
            'all_candidate_costs_fixed_zero': costs_zero,
            'source_contract_check_not_a_general_static_program_proof': True}


def prepare(*, selector_source=None):
    corpus_path = SNAPSHOT / 'corpus.json'; fitted_path = SNAPSHOT / 'fitted_channels.json'
    corpus, fitted = read(corpus_path), read(fitted_path)
    original_protocol_path = SNAPSHOT.parent.parent / 'protocol.json'
    original_protocol = read(original_protocol_path)
    if digest(corpus) != SNAPSHOT.name:
        raise ValueError('The immutable real pilot corpus changed')
    channel_source = 'legal_skill_guard/paired_interfaces/structural_channel.py'
    if original_protocol['source_sha256'][channel_source] != sha(ROOT / channel_source):
        raise ValueError('Use the same fitted constraints and original channel implementation')
    records = defaultdict(list)
    for row in corpus['pairs']:
        if row['role'] == 'calibration':
            records[row['context'], row['version']].append(restore_pair(row['pair']))
    actual = []
    for group in fitted['groups']:
        if not group.get('fitted'): continue
        modes = {}
        for mode in ('unrestricted', 'detectable_residual'):
            channel = restore_channel(group, mode, records[group['context'], group['version']])
            modes[mode] = channel_witness(channel)
        actual.append({k: group[k] for k in ('dataset', 'context', 'plan', 'version')} | {'modes': modes})
    formal_source = (Path(selector_source).resolve() if selector_source is not None else
                     ROOT / 'legal_skill_guard/paired_interfaces/formal_learning.py')
    if not formal_source.is_relative_to(ROOT):
        raise ValueError('Use an explicitly preserved project source snapshot')
    contract = selector_contract(formal_source)
    pilot = read(BASE / 'pilot_lock.json')
    orders = {d: [r['name'] for r in rows] for d, rows in pilot['plans'].items()}
    equivalence = {}
    for dataset, plans in orders.items():
        for arm in ('M2_fixed_interfaces', 'M1_M2'):
            pool = [p for p in plans if arm != 'M2_fixed_interfaces' or p in ('columns', 'records')]
            # Lower endpoints need not agree. Only the maximum is used by
            # the current primary selector; q_unknown=1 fixes each upper=1.
            predictions = {plan: {'supported': True, 'interval': [i / len(pool), 1.]}
                           for i, plan in enumerate(pool)}
            choice = choose_risks(predictions, baseline=pool[0], costs={p: 0. for p in pool})
            equivalence[dataset + ':' + arm] = {
                'baseline': pool[0], 'selected': choice['plan'],
                'risk_informed_ranking': choice['risk_informed_ranking'],
                'fixed_candidate_pool': pool, 'same_as_baseline': choice['plan'] == pool[0],
                'constructed_bounded_risks_not_actual_native_test_results': True}
    unrestricted = [r['modes']['unrestricted'] for r in actual]
    conditional = [r['modes']['detectable_residual'] for r in actual]
    proved = (bool(actual) and all(contract[k] for k in ('primary_selects_unrestricted_mode', 'all_candidate_costs_fixed_zero'))
              and all(r['unknown_mass_one_feasible'] and r['unrestricted_constraint_template_verified']
                      and r['all_checked_upper_bounds_one'] for r in unrestricted)
              and all(r['same_as_baseline'] and not r['risk_informed_ranking'] for r in equivalence.values()))
    binding_paths = [Path(__file__).resolve(), corpus_path, fitted_path, original_protocol_path,
                     ROOT / channel_source, formal_source, BASE / 'pilot_lock.json',
                     ROOT / 'legal_skill_guard/paired_interfaces/native_channel_selection.py',
                     ROOT / 'legal_skill_guard/paired_interfaces/partial_native_loss.py',
                     ROOT / 'experiments/two_method_native_selection.py']
    protocol = {'experiment': 'primary_M2_unrestricted_identifiability_audit_v2_explicit_contract',
        'explicit_historical_selector_source': str(formal_source.relative_to(ROOT)) if selector_source is not None else None,
        'sha256': {str(p.relative_to(ROOT)): sha(p) for p in binding_paths},
        'real_fitted_channel_constraints_reused_without_refitting': True,
        'source_reference_graphs_and_production_methods_not_modified': True,
        'no_native_grading_DEV_TEST_or_new_weak_reads': True,
        'new_model_requests': 0, 'new_independent_trials': 0}
    out = BASE / 'M2_identifiability_audit_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    for name, expected in protocol['sha256'].items():
        p = out / 'source_snapshot' / name;p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            if sha(p) != expected: raise ValueError('Immutable audit snapshot changed')
        else:p.write_bytes((ROOT / name).read_bytes())
    report = {'primary_M2_fixed_columns_equivalence_proved_for_current_contract': proved,
        'audited_selector_source': str(formal_source.relative_to(ROOT)),
        'historical_selector_explicitly_selected': selector_source is not None,
        'revised_observable_selector_refuted_by_this_audit': False,
        'selector_contract': contract, 'candidate_orders': orders,
        'real_pilot_fitted_groups': len(actual),
        'real_unrestricted_channels_with_full_unknown_witness': sum(r['unknown_mass_one_feasible'] for r in unrestricted),
        'real_conditional_channels_with_full_unknown_witness': sum(r['unknown_mass_one_feasible'] for r in conditional),
        'conditional_mode_not_universally_equated_with_primary_mode': True,
        'real_channel_checks': actual, 'production_selector_zero_cost_tie_checks': equivalence,
        'scope': 'current unrestricted primary minimax selector with zero costs and original columns-first pools;not all possible structural error-transfer methods',
        'arbitrary_training_size_same_unrestricted_constraint_form_still_admits_full_unknown': True,
        'more_training_cannot_remove_this_particular_nonidentifiability': True,
        'applicability_or_missing_family_refusal_also_keeps_declared_baseline': True,
        'floating_point_differences_around_one_not_substantive_risk_information': True,
        'does_not_depend_on_missing_source_annotations_or_heldout_labels': True,
        'conditional_mode_needs_its_own_assumption_validation_and_native_domain_support': True,
        'explicit_goal_stop_condition_evidence': ('The audited unrestricted selector is equivalent to fixed columns; this does not refute or authorize the revised observable model'
            if proved else 'The current selector differs from the unrestricted contract; historical latent-mixture obstruction remains preserved, and the revised method needs its own validation'),
        'formal_train_DEV_TEST_completed': False, 'goal_completed': False,
        'new_model_requests': 0, 'new_independent_trials': 0}
    immutable_json(out / 'report.json', report)
    proof = '''# Current primary M2 identifiability obstruction

For every calibration moment, unrestricted unknown errors contribute an
interval [0,1]. The fitted constraints have rows

    c_certain . q_modeled + 0 q_unknown <= U
    -c_possible . q_modeled - q_unknown <= -L

with 0 <= L <= U <= 1. Set every modeled mass to zero and q_unknown=1.
The inequalities reduce to 0<=U and -1<=-L; the simplex constraint also holds.
This witness exists for every sample size under the same unrestricted model.

Every upper-risk objective appends coefficient 1 for unknown errors, while
all modeled failure losses lie in [0,1]. The witness attains objective 1,
and the simplex bounds the objective above by 1. The upper risk is therefore
exactly 1, regardless of the observed error distribution or target consumer,
provided the risk computation is otherwise supported.

The current formal select function chooses the unrestricted mode, sets all
candidate costs to zero, and minimizes that upper risk with a name tie-break.
The original pools start with columns, also the lexicographically first name.
Both primary M2 arms therefore choose columns; unsupported families retain
that same baseline. A numerical difference near 1 cannot establish risk
information. Complete references or additional calibration do not repair
this obstruction. It is distinct from the separate conditional detectable-
residual model, which restricts unknown errors and needs validation.

The report checks the explicit witness in all original real fitted pilot
groups, restores their exact calibration provenance, and runs the production
bound solver and risk selector. Bounded objective vectors are algebra checks,
not new legal experiments. No native accuracy, transfer gain, or completed
formal study is claimed. The original Goal requires stopping expansion when
a method is deployably equivalent to a same-information simple comparator;
this evidence applies to the current primary selector. It does not refute
every possible structural error model and does not authorize changing the
primary assumption, dropping unknown mass, or changing the evaluation scope.
'''
    if selector_source is not None:
        proof = ('Audited source: ' + str(formal_source.relative_to(ROOT)) +
                 '\nThis is a historical selector contract, not the revised deployed selector.\n\n' + proof)
    elif not proved:
        proof = ('# Historical latent-mixture obstruction\n\nThe saved unrestricted constraints still admit full unknown mass. '
                 'The current source no longer selects that primary model; fixed-columns equivalence is not proved for it. '
                 'Use the original sealed audit to reproduce the historical deployment conclusion.\n')
    p=out/'PROOF.md'
    if p.exists():
        if p.read_text()!=proof:raise ValueError('Immutable proof changed')
    else:p.write_text(proof)
    return out, report


if __name__=='__main__':
    out, report = prepare()
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)),
        **{k: report[k] for k in ('primary_M2_fixed_columns_equivalence_proved_for_current_contract',
             'real_pilot_fitted_groups', 'real_unrestricted_channels_with_full_unknown_witness',
             'real_conditional_channels_with_full_unknown_witness','new_model_requests','goal_completed')}}, ensure_ascii=False))
