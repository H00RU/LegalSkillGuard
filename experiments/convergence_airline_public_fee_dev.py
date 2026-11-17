"""Compare the compiled common fee consumer on its fixed, public DEV scope."""

import argparse
import json
import sqlite3

from experiments.convergence_airline_joint_relation import BAG
from experiments.convergence_airline_structured_update import LITERALS, measure
from experiments.convergence_dev_b0 import ARM, POINTER as B0
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.airline_public_fees import compile_rule, local_charges, public_domestic_scope
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

POINTER = HANDOFF / 'airline_shared_fee_dev_current.json'


def prepare():
    reference = ROOT / read(LITERALS)['artifact_root']
    measured = read(reference / 'terminal.json')
    if measured['native_scores']['match_bag_max'] != 1 or measured['native_mothers'] != 2:
        raise ValueError('Verified native TRAIN behavior is required for the scoped common consumer')
    baseline = ROOT / read(B0)['artifact_root']
    prior = read(baseline / 'binding.json')
    sources = read(baseline / 'public_DEV_sources.json')
    if digest(sources) != prior['DEV_public_sha256']:
        raise ValueError('The fixed DEV cohort changed')
    baseline_report_path = baseline / 'dev/B0' / ARM / 'scores.json'
    b0_report = read(baseline_report_path)
    before = {item['source']: item['grade'] for item in b0_report['source_scores']
              if item['dataset'] == 'RuleArena_Airline'}
    supported = []
    for source in (row for row in sources if row['dataset'] == 'RuleArena_Airline'):
        public = source['views'][0]['public']
        scope = public_domestic_scope(public)
        if scope is None:
            continue
        rule = compile_rule(public['source_text'], cabin=scope['cabin'])
        bag_list = [{'dimensions': [int(item[i]) for i in (2, 3, 4)], 'weight': int(item[5])}
                    for item in BAG.finditer(public['facts'])]
        try:
            local_charges(rule, bag_list)
        except ValueError:
            continue
        supported.append({'source': source, 'rule': rule, 'scope': scope})
    if len(before) != 16 or not supported:
        raise ValueError('Retain the complete fixed Airline DEV denominator')
    path = prior['grading_paths']['RuleArena_Airline']
    source_files = ('experiments/convergence_airline_public_fee_dev.py',
                    'experiments/convergence_airline_structured_update.py',
                    'experiments/convergence_airline_joint_relation.py',
                    'legal_skill_guard/paired_interfaces/airline_public_fees.py',
                    'legal_skill_guard/paired_interfaces/native_adapters.py',
                    'legal_skill_guard/paired_interfaces/formal_actors.py',
                    'legal_skill_guard/skill_evolution/native.py',
                    'legal_skill_guard/skill_evolution/clients.py',
                    'legal_skill_guard/skill_evolution/ledger.py', 'legal_skill_guard/rr/client.py')
    binding = {'study_id': 'convergence_shared_public_airline_rule_DEV',
               'source_sha256': {name: sha(ROOT / name) for name in source_files}, 'cases_sha256': digest(supported),
               'rule_scope_selection_uses_answers': False, 'reference_runtime_sha256': sha(reference / 'terminal.json'),
               'B0_score_artifact': str(baseline_report_path.relative_to(ROOT)),
               'B0_score_sha256': sha(baseline_report_path), 'executor': prior['executor'],
               'grading_file': path, 'grading_sha256': prior['grading_file_sha256'][path],
               'B0_source_utilities': before, 'primary_arm': 'shared_common_repairs_not_M1_or_M2'}
    out = BASE / 'airline_common_public_rule_dev' / digest(binding)
    if (out / 'terminal.json').is_file():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'cases.json', supported)
    write_status(out, {'status': 'prepared', 'eligible_DEV_cells': len(supported), 'all_sources': 16}, POINTER)
    print(json.dumps({'status': 'prepared', 'eligible_DEV_cells': len(supported), 'binding': digest(binding)}))


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').is_file():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    binding = read(out / 'binding.json')
    cases = read(out / 'cases.json')
    if (digest(cases) != binding['cases_sha256'] or sha(ROOT / binding['B0_score_artifact']) != binding['B0_score_sha256']
            or any(sha(ROOT / name) != v for name, v in binding['source_sha256'].items())):
        raise ValueError('The fixed common rule DEV comparison changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved' limit 1").fetchone():
            raise ValueError('An existing request must settle')
    keys = [case['source']['key'] for case in cases]
    ledger = EvolutionLedger(LEDGER, run_id='convergence-airline-compiled-DEV-' + digest(binding)[:16],
        sources={'train': [], 'dev': keys, 'test': []}, binding=binding)
    ex = FrozenExecutor(ledger, out, binding['executor'])
    ex.readiness()
    write_status(out, {'status': 'running', 'eligible_DEV_cells': len(cases)}, POINTER)
    try:
        predictions = [measure(ex, case['source'], out, compiled_rule=case['rule'], purpose='skill_dev') for case in cases]
        immutable_json(out / 'prediction_seal.json', {'predictions_sha256': digest(predictions), 'sources': keys})
        grade_file = ROOT / binding['grading_file']
        if sha(grade_file) != binding['grading_sha256']:
            raise ValueError('The frozen DEV grader changed')
        golds = read(grade_file)
        before = binding['B0_source_utilities']
        after = dict(before)
        for case, prediction in zip(cases, predictions, strict=True):
            source = case['source']
            after[source['key']] = grade_view(source['dataset'], source['views'][0], golds[source['key']]['native'],
                                              prediction['predictions']['match_bag_max'])['grade']
        terminal = {'status': 'completed', 'fixed_Airline_DEV_mothers': len(before),
                    'native_exact_counts_before_after': [sum(before.values()), sum(after.values())],
                    'eligible_counts_before_after': [sum(before[key] for key in keys), sum(after[key] for key in keys)],
                    'eligible_DEV_mothers': len(keys), 'unchanged_b0_mothers_reused': len(before) - len(keys),
                    'common_pipeline_improvement_only': True, 'new_executor_tokens': sum(
                        row['usage']['total_tokens'] for row in predictions), 'TEST_opened': False}
        immutable_json(out / 'terminal.json', terminal)
        write_status(out, terminal, POINTER)
        print(json.dumps(terminal), flush=True)
    except Exception as error:
        write_status(out, {'status': 'interrupted_or_failed', 'error_type': type(error).__name__}, POINTER)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
