"""Fixed-cohort PARSE adaptation with original native-schema recovery."""

import argparse
from collections import Counter
import json
import math
import sqlite3

import jsonschema

from experiments.convergence_native_teacher_pilot import INSTRUCTIONS, POINTER as ORDINARY
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.control_answers import decode_native, source_bundle, wire_schema
from legal_skill_guard.paired_interfaces.convergence_actors import common_cells
from legal_skill_guard.paired_interfaces.convergence_schema_control import (
    ReversibleWire, measure_schema, public_field_types, schema_proposal, validate_proposal,
)
from legal_skill_guard.paired_interfaces.scope_learning import strict_json
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'parse_pilot_current.json'
FAMILY = 'PARSE_style_interface_optimization'
SYSTEM = (
    'Propose a general reversible output schema transformation for this public legal task family. '
    'You may rename declared fields, prioritize field order, and add up to 90 words of domain-specific reader guidance. '
    'Output on every current source must decode to its complete original native wire, including all evidence, '
    'constraints and original task answers. Do not remove fields, combine outputs, change values or insert answers. '
    'The same frozen weak reader gets the complete public source information and at most one call per bundle. '
    'Keep uncertainty and the exact sentence IDs. Do not use access to case answers or identities.'
)
CHECK_PROPOSAL = {
    'field_aliases': [{'original': 'answer', 'alias': 'native_result'},
                      {'original': 'evidence_sentence_ids', 'alias': 'source_evidence'}],
    'fields_first': ['evidence_sentence_ids'], 'reader_guidance': '',
}


def audit_original_reads(ordinary, sources, binding):
    """Verify and translate settled original outputs without opening grading files."""
    originals = {}
    for name in binding['common_terminal_receipts']:
        path = ROOT / name
        for artifact in (path / 'program_executions').glob('*/result.json'):
            result = read(artifact)
            task = read(artifact.with_name('input.json'))['inputs']
            original_id = (result['source'], digest(task['public']))
            if original_id in originals:
                raise ValueError('The baseline has two observations with the same public identity')
            originals[original_id] = result
    observations = []
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for source in sources:
            for cell in common_cells(source):
                bundle = source_bundle(cell)
                result = originals[source['key'], digest(bundle['public'])]
                trace, = result['traces']
                physical, = db.execute(
                    'select status,source,purpose,result from calls where id=?', (trace['physical_call_id'],),
                ).fetchall()
                response = json.loads(physical[3])
                if (tuple(physical[:3]) != ('completed', source['key'], 'skill_actor')
                        or response['content'] != trace['raw_content'] or response['usage'] != trace['usage']):
                    raise ValueError('The original baseline evidence lost its physical source binding')
                original_schema = wire_schema(source['dataset'], bundle)
                if original_schema != trace['schema']['properties']['value']:
                    raise ValueError('The new comparator does not share the original native schema')
                codec = ReversibleWire(original_schema, CHECK_PROPOSAL)
                row = {'dataset': source['dataset'], 'source_sha256': digest(source),
                       'cell_sha256': digest(cell), 'native_tasks': len(cell['views']),
                       'original_physical_call_id': trace['physical_call_id'],
                       'production_roundtrip': False, 'original_response_status': trace['status']}
                if trace['status'] == 'validated':
                    wire, _ = restore_enum_transport(strict_json(response['content']), trace['schema'])
                    original = wire['value']
                    restored = codec.restore(codec.encode(original))
                    native, evidence = decode_native(source['dataset'], bundle, restored)
                    if restored != original or native != result['answer'] or evidence != trace['native_evidence']:
                        raise ValueError('The reversible treatment changed a measured native answer or evidence')
                    row['production_roundtrip'] = True
                observations.append(row)
    return {'native_cells': len(observations), 'schema_roundtrips_on_actual_valid_responses':
            sum(row['production_roundtrip'] for row in observations), 'native_tasks':
            sum(row['native_tasks'] for row in observations), 'new_requests': 0,
            'source_roster_sha256': binding['pilot_source_sha256'], 'rows': observations,
            'ordinary_pilot_root': str(ordinary.relative_to(ROOT))}


def cohort_contract(ordinary_binding, sources, protocol):
    return {
        'sources_sha256': digest(sources), 'native_tasks_sha256': digest({
            source['key']: [view['id'] for view in source['views']] for source in sources}),
        'executor': ordinary_binding['executor'], 'teacher': ordinary_binding['teacher_profile'],
        'comparison_protocol_sha256': sha(protocol), 'teacher_proposals_per_library': 1,
        'neural_callbacks_per_native_bundle': 1, 'openexempt_separate_EC_EV': True,
        'teacher_case_labels_or_inputs_visible': False,
    }


def prepare():
    ordinary = ROOT / read(ORDINARY)['artifact_root']
    prior = read(ordinary / 'binding.json')
    sources = read(ordinary / 'train_sources.json')
    feedback = read(ordinary / 'teacher_payloads.json')
    baseline = read(ordinary / 'incumbent_scores.json')
    if (digest(sources) != prior['pilot_source_sha256'] or digest(feedback) != prior['teacher_inputs_sha256']
            or digest(baseline) != prior['native_incumbent_sha256']
            or Counter(source['dataset'] for source in sources) != dict.fromkeys(INSTRUCTIONS, 4)
            or any(source['project_split'] != 'train' for source in sources)
            or any(sha(ROOT / stage / 'terminal.json') != value
                   for stage, value in prior['common_terminal_receipts'].items())):
        raise ValueError('The fixed original pilot or measured baseline changed')
    audit = audit_original_reads(ordinary, sources, prior)
    fields = {dataset: {} for dataset in INSTRUCTIONS}
    for source in sources:
        for cell in common_cells(source):
            bundle = source_bundle(cell)
            for name, kinds in public_field_types(wire_schema(source['dataset'], bundle)).items():
                observed = fields[source['dataset']].setdefault(name, [])
                observed.extend(kind for kind in kinds if kind not in observed)
    payloads = {dataset: {**value, 'public_wire_field_types': fields[dataset]}
                for dataset, value in feedback.items()}
    protocol = ROOT / 'reports/legal_skill_convergence_20261117/protocol.json'
    code = set(prior['source_sha256']) | {
        'experiments/convergence_parse_pilot.py', 'legal_skill_guard/paired_interfaces/convergence_schema_control.py',
        'legal_skill_guard/paired_interfaces/scope_learning.py', str(protocol.relative_to(ROOT)),
    }
    conditions = cohort_contract(prior, sources, protocol)
    binding = {'study_id': 'convergence_parse_style_fixed20_v1', 'family': FAMILY,
               'source_sha256': {name: sha(ROOT / name) for name in sorted(code)},
               'ordinary_root': str(ordinary.relative_to(ROOT)), 'ordinary_binding_sha256': digest(prior),
               'public_cohort_sha256': digest(sources), 'teacher_system_sha256': digest(SYSTEM),
               'teacher_payloads_sha256': digest(payloads), 'offline_recovery_audit_sha256': digest(audit),
               'matched_public_conditions': conditions, 'teacher_config': prior['teacher_config'],
               'teacher_profile': prior['teacher_profile'], 'executor': prior['executor']}
    out = BASE / 'parse_pilot' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'reference_recovery_audit.json', audit)
    immutable_json(out / 'teacher_payloads.json', payloads)
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    write_status(out, {'status': 'prepared', 'fixed_TRAIN_mothers': len(sources),
                       'native_cells': audit['native_cells'], 'verified_actual_roundtrips':
                       audit['schema_roundtrips_on_actual_valid_responses']}, POINTER)
    print(json.dumps(read(POINTER)), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    binding = read(out / 'binding.json')
    ordinary = ROOT / binding['ordinary_root']
    previous = read(ordinary / 'binding.json')
    sources = read(ordinary / 'train_sources.json')
    baseline = read(ordinary / 'incumbent_scores.json')
    payloads = read(out / 'teacher_payloads.json')
    if (read(ordinary / 'terminal.json')['status'] != 'completed'
            or digest(previous) != binding['ordinary_binding_sha256']
            or digest(sources) != binding['public_cohort_sha256']
            or digest(baseline) != previous['native_incumbent_sha256']
            or digest(payloads) != binding['teacher_payloads_sha256']
            or digest(SYSTEM) != binding['teacher_system_sha256']
            or any(sha(ROOT / name) != value for name, value in (
                binding['source_sha256'] | previous['grading_file_sha256']).items())):
        raise ValueError('The fixed PARSE pilot comparison changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved' limit 1").fetchone():
            raise ValueError('An existing physical request must settle first')
    keys = [source['key'] for source in sources]
    ledger = EvolutionLedger(LEDGER, run_id='convergence-parse-pilot-' + digest(binding)[:16],
                             sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    executor.readiness()
    teacher = FrozenTeacher(ledger, out, binding['teacher_config'], authorized_profile=binding['teacher_profile'])
    summaries = {}
    for dataset in sorted(INSTRUCTIONS):
        scoped = [source for source in sources if source['dataset'] == dataset]
        library_keys = [source['key'] for source in scoped]
        report = out / 'measured_libraries' / (dataset + '.json')
        if report.exists():
            summaries[dataset] = read(report)['summary']
            continue
        write_status(out, {'status': 'running', 'current_library': dataset, 'completed_libraries': len(summaries)}, POINTER)
        response = teacher.propose(ledger.run_id + ':teacher:' + dataset, source_ids=library_keys,
                                    system_prompt=SYSTEM, user_prompt=json.dumps(payloads[dataset], sort_keys=True),
                                    output_schema=schema_proposal())
        if response['model'] != binding['teacher_config']['model']:
            raise ValueError('Actual teacher differs from the matched model')
        proposal = response['value']
        base = math.fsum(math.fsum(baseline[key].values()) / len(baseline[key]) for key in library_keys) / len(library_keys)
        score_rows, predictions = [], {}
        try:
            validate_proposal(proposal, payloads[dataset]['public_wire_field_types'])
            for source in scoped:
                for cell in common_cells(source):
                    ReversibleWire(wire_schema(dataset, source_bundle(cell)), proposal)
        except (ValueError, jsonschema.ValidationError) as error:
            summary = {'incumbent_native': base, 'candidate_native': None, 'selected': 'incumbent',
                       'status': 'invalid_schema_proposal', 'error_type': type(error).__name__}
        else:
            for source in scoped:
                predictions[source['key']] = [measure_schema(executor, out, cell, proposal, 'skill_actor')
                                               for cell in common_cells(source)]
            immutable_json(out / 'prediction_seals' / (dataset + '.json'),
                           {'predictions_sha256': digest(predictions), 'source_keys': library_keys})
            golds = read(ROOT / previous['grading_paths'][dataset])
            for source in scoped:
                key = source['key']
                outputs = {name: value for item in predictions[key] for name, value in item['native'].items()}
                if outputs.keys() != golds[key].keys():
                    raise ValueError('Schema-optimized output changed the fixed native denominator')
                for view in source['views']:
                    name = view['id']
                    pred = outputs[name]
                    grade = grade_view(dataset, view, golds[key][name], pred['answer'],
                                       pred['evidence_sentence_ids']) if pred['handled'] else {'grade': 0.0}
                    score_rows.append({'source': key, 'view': name, 'dataset': dataset,
                                       'handled': pred['handled'], 'grade': grade['grade']})
            from legal_skill_guard.paired_interfaces.pilot_metrics import summarize
            expected = {(source['key'], view['id']) for source in scoped for view in source['views']}
            score = summarize(score_rows, expected)['mother_macro']
            summary = {'incumbent_native': base, 'candidate_native': score, 'status': 'completed',
                       'selected': 'candidate' if score > base else 'incumbent'}
        immutable_json(report, {'summary': summary, 'proposal': proposal, 'candidate_score_rows': score_rows,
                                'actual_predictions_sha256': digest(predictions), 'teacher_usage': response.get('invocation', {}).get('usage')})
        summaries[dataset] = summary
    terminal = {'status': 'completed', 'family': FAMILY, 'libraries': summaries,
                'fixed_train_mothers': len(sources), 'strongest_external_family_selected': False}
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, terminal, POINTER)
    print(json.dumps(terminal), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
