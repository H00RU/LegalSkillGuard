"""Postprocess actual v3 port responses with shared unique-quote binding.

Original v3 outcomes remain untouched. This is deterministic evaluation of the
same paid responses under a documented decoder correction, not new independent
model trials. Native TRAIN labels enter only after predictions are serialized.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments.two_method_annotate import inputs
from legal_skill_guard.paired_interfaces import airline_interfaces, graph_interface as gi
from legal_skill_guard.paired_interfaces.graph_prompt import schema_visible_plan
from legal_skill_guard.paired_interfaces.native_adapters import run_airline
from legal_skill_guard.paired_interfaces.port_evidence import bind_port_evidence
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/two_method_followthrough_20261116'
OUT = BASE / 'pilot_program_port_postprocessing_v1'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    lock = read(BASE / 'pilot_lock.json')
    plans = {p['version']: p for p in map(schema_visible_plan,
        airline_interfaces.compile_plans(lock['plans']['RuleArena_Airline']))}
    train_root = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train'
    train = {s['key']: s for s in read(train_root / 'public.json')}
    files = ['experiments/two_method_score_program_ports.py',
        'legal_skill_guard/paired_interfaces/port_evidence.py',
        'legal_skill_guard/paired_interfaces/airline_interfaces.py',
        'legal_skill_guard/paired_interfaces/native_adapters.py']
    immutable_json(OUT / 'protocol.json', {'source_sha256': {f: sha(ROOT / f) for f in files},
        'read_protocol_sha256': sha(BASE / 'pilot_reads_v3/protocol.json'),
        'original_v3_predictions_and_errors_preserved': True,
        'model_values_codes_or_statuses_not_repaired': True,
        'new_model_calls': 0, 'new_independent_trials': 0})
    predictions = []
    for path in sorted((BASE / 'pilot_reads_v3/reads').glob('*/decoded.json')):
        row = read(path)
        if not row['source'].startswith('RuleArena_Airline:'):
            continue
        source, plan = train[row['source']], plans[row['plan_version']]
        units = inputs(source)[0]['views'][0]['source_units']
        error, construction, binding, graph = None, None, None, None
        try:
            if any(x.startswith('Non-stop generation finish') for x in row['errors']):
                raise ValueError('Truncated model response is not a complete input')
            jsonschema.validate(row['raw_graph_encoding'], plan['schema'])
            fixed, binding = bind_port_evidence(plan, row['raw_graph_encoding'], units)
            graph, construction = airline_interfaces.decode(plan, fixed, units)
            gi.validate(graph, units)
            native = run_airline(graph, units, plan['fixed_library_sha256'])
        except (ValueError, KeyError, TypeError, jsonschema.ValidationError) as exc:
            error = type(exc).__name__ + ': ' + str(exc)
            native = {'handled': False, 'answer': None, 'reason': error}
        result = {'source': row['source'], 'plan': row['plan'], 'plan_version': row['plan_version'],
            'physical_call_id': row['physical_call_id'], 'actual_read_sha256': sha(path),
            'unique_quote_binding_receipt': binding, 'paired_decoder_receipt': construction,
            'native': native, 'error': error, 'graph': graph,
            'original_reader_errors': row['errors'], 'new_model_calls': 0,
            'same_physical_response_not_an_independent_trial': True}
        immutable_json(OUT / 'predictions' / path.parent.name / 'prediction.json', result)
        predictions.append(result)
    # The prediction files above exist before any label is loaded.
    labels = read(train_root / 'grading.json')
    scored = []
    for result in predictions:
        target = labels[result['source']]['native']['answer']
        scored.append({'source': result['source'], 'plan': result['plan'],
            'handled': result['native']['handled'], 'prediction': result['native']['answer'],
            'reference': target, 'correct': bool(result['native']['handled']) and result['native']['answer'] == target,
            'physical_call_id': result['physical_call_id']})
    snapshot = {'scored': scored, 'pilot_complete': False, 'new_independent_trials': 0}
    key = digest(snapshot)
    immutable_json(OUT / 'snapshots' / (key + '.json'), snapshot)
    print(json.dumps({'actual_paid_responses': len(predictions),
        'native_program_executions': sum(bool(p['native'].get('learned_native_main_path_executed')) for p in predictions),
        'native_correct': sum(p['correct'] for p in scored), 'rows': scored,
        'snapshot': key, 'new_model_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
