"""Build/check exact OE public-context residual interfaces, without model calls.

All frozen legal premises bind their original TRAIN text. Output comparison is
an offline program check, not a native data score or independent trial.
"""
import itertools
import json
from pathlib import Path
import subprocess
import sys

from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.paired_interfaces.asset_interfaces import compile_plans, frozen_skill, regimes
from legal_skill_guard.paired_interfaces.graph_prompt import schema_visible_plan
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def execute(procedure, premises, calls):
    result = subprocess.run([sys.executable, '-I', '-S',
        str(ROOT / 'legal_skill_guard/paired_interfaces/consumer_worker.py')],
        input=json.dumps({'procedure': procedure, 'premises': premises, 'calls': calls}),
        text=True, capture_output=True, timeout=30, cwd='/tmp', env={'LANG': 'C.UTF-8'})
    if result.returncode:
        raise ValueError('Frozen/residual consumer failed: ' + result.stderr[-1600:])
    values = json.loads(result.stdout)
    if len(values) != len(calls):
        raise ValueError('A program equivalence check returned an incomplete output table')
    return values


def build():
    skill = frozen_skill()
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    source_lock = read(BASE / 'prepared/source_lock.json')
    if sha(public_path) != source_lock['prepared_sha256']['train']['public']:
        raise ValueError('The fixed TRAIN public source changed')
    train = {source['key']: source for source in read(public_path)}
    anchors = []
    for field, premise in skill['premises'].items():
        if premise['mode'] != 'constant':
            raise ValueError('The frozen legal premise requires a real new acquisition')
        origin = premise['origin']
        view = next(view for view in train[origin['source_id']]['views'] if view['id'] == origin['view_id'])
        text = view['public']['original_input'].partition('\nFacts:\n')[0]
        quote = origin['quote']
        if ' '.join(quote.split()) not in ' '.join(text.split()):
            raise ValueError('A frozen legal premise lost its TRAIN source quote: ' + field)
        anchors.append({'premise': field, 'origin': origin, 'exact_quote': quote in text,
                        'whitespace_folded_quote': True})
    locked = read(BASE / 'pilot_lock.json')['plans']['OpenExempt']
    plans = {regime: [schema_visible_plan(plan) for plan in compile_plans(locked, regime)]
             for regime in regimes(skill)}
    booleans = sorted(name for name in skill['inputs'] if name.startswith('asset_is_'))
    if len(booleans) > 12:
        raise ValueError('The declared finite Boolean equivalence check needs an explicit new bound')
    premises = {name: value['value'] for name, value in skill['premises'].items()}
    reports = []
    for regime, candidates in plans.items():
        local = next(plan for plan in candidates if plan['name'] == 'local_records')
        full_calls, residual_calls = [], []
        for flags, debtors, family in itertools.product(itertools.product([False, True], repeat=len(booleans)),
                                                       (1, 2), ('EC', 'EV')):
            values = {'asset_descriptions': ['example zero-valued item', 'example fractional-valued item'],
                'asset_values': [0, 23717.5], 'governing_regime': regime,
                'number_of_debtors': debtors, 'output_family': family,
                **{name: [value, not value] for name, value in zip(booleans, flags)}}
            full_calls.append({'inputs': values})
            # Omitted facts are actually absent, not assigned arbitrary false
            # representatives. The generated D never reads them in this context.
            residual_calls.append({'inputs': {key: value for key, value in values.items()
                                              if key in local['residual_required_fields']}})
        full = execute(skill['procedure'], premises, full_calls)
        reduced = execute(local['residual_program']['procedure'], premises, residual_calls)
        if full != reduced:
            raise ValueError('A generated residual changed the original EC/EV outputs')
        reports.append({'regime': regime, 'full_calls': len(full_calls),
            'both_native_output_families_preserved': True, 'debtors_checked': [1, 2],
            'numeric_values_checked': [0, 23717.5], 'two_assets_have_opposite_category_states': True,
            'required_array_ports': local['array_fields'],
            'omitted_factual_ports': local['residual_program']['removed_noncontext_fields'],
            'need_debtor_count': 'number_of_debtors' in local['residual_required_fields'],
            'syntactic_context_certificate_covers_other_numeric_values_and_lengths': True,
            'this_finite_check_does_not_certify_source_meaning_or_reader_accuracy': True})
    paths = [Path(__file__).relative_to(ROOT), 'legal_skill_guard/paired_interfaces/asset_interfaces.py',
             'legal_skill_guard/paired_interfaces/program_residual.py',
             'legal_skill_guard/paired_interfaces/consumer_worker.py',
             'legal_skill_guard/paired_interfaces/native_graph_consumers.py',
             'legal_skill_guard/paired_interfaces/partial_consumer_worker.py',
             'legal_skill_guard/paired_interfaces/control_tools.py',
             'legal_skill_guard/paired_interfaces/graph_prompt.py',
             'legal_skill_guard/paired_interfaces/graph_interface.py',
             'legal_skill_guard/skill_evolution/span_compiler.py']
    library = ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v5/Full/B8.json'
    protocol = {'experiment': 'frozen_OE_program_public_context_residual_ports_v1',
        'source_sha256': {str(path): sha(ROOT / path) for path in paths},
        'frozen_library_sha256': sha(library), 'fixed_skill_sha256': digest(skill),
        'TRAIN_public_sha256': sha(public_path), 'source_lock_sha256': sha(BASE / 'prepared/source_lock.json'),
        'original_pilot_lock_sha256': sha(BASE / 'pilot_lock.json'),
        'existing_candidate_names_and_families_unchanged': True,
        'legal_F_and_premises_unchanged': True,
        'new_adapter_does_not_rewrite_old_pilot_reads_scores_or_channels': True,
        'formal_reader_integration_and_real_calibration_not_yet_executed': True,
        'native_labels_or_DEV_TEST_inputs_used': False, 'new_model_requests': 0}
    out = BASE / 'offline_asset_module_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    immutable_json(out / 'frozen_skill.json', skill)
    immutable_json(out / 'generated_interfaces.json', plans)
    immutable_json(out / 'checks.json', {'source_anchors': anchors, 'residual_checks': reports,
        'original_outputs_compared': sum(row['full_calls'] for row in reports),
        'new_model_requests': 0, 'new_native_scores_or_independent_trials': 0})
    for path in paths:
        destination = out / 'source_snapshot' / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / path).read_bytes()
        if destination.exists() and destination.read_bytes() != raw:
            raise ValueError('An immutable source snapshot changed')
        if not destination.exists():
            destination.write_bytes(raw)
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)),
        'original_outputs_compared': sum(row['full_calls'] for row in reports),
        'per_regime': [{key: row[key] for key in ('regime', 'required_array_ports', 'omitted_factual_ports', 'need_debtor_count')}
                       for row in reports], 'new_model_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    build()
