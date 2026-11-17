"""Matched fixed and synthesized receiver-binding reads on four TRAIN NDAs."""

import argparse
import json

from experiments.convergence_maud_clause_probe import BASE, HANDOFF, ROOT, read, run, sha
from legal_skill_guard.paired_interfaces import cni_disclosure_relational as disclosure
from legal_skill_guard.paired_interfaces import indexed_relational_read as indexed
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.paired_interfaces.residual import encode
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

POINTER = HANDOFF / 'cni_disclosure_relational_probe_current.json'
# These are independent clause readings for the four fixed sources. They go
# through the exact production decoder and never enter the reader input.
SOURCE_REVIEWS = {
    'b6fc9bc6': ('n25_26', 'own_employees'),
    'adf7d954': ('n7_7', 'own_employees'),
    '9ec972e7': ('n25_25', 'own_employees'),
    'fc43b1c9': ('n10_10', None),
}


def prepare():
    baseline = ROOT / read(HANDOFF / 'pilot_b0_current.json')['artifact_root']
    common = ROOT / read(HANDOFF / 'cni_indexed_evidence_current.json')['artifact_root']
    baseline_input = read(baseline / 'public_TRAIN_pilot.json')
    baseline_binding = read(baseline / 'binding.json')
    if (digest(baseline_input) != baseline_binding['sources_digest']
            or read(common / 'terminal.json')['status'] != 'completed'):
        raise ValueError('The same four fixed pilot sources and settled indexed baseline are required')
    grade_path = ROOT / baseline_binding['grading_paths']['ContractNLI']
    if sha(grade_path) != baseline_binding['grading_file_sha256'][str(grade_path.relative_to(ROOT))]:
        raise ValueError('The original native grading changed')
    grades = read(grade_path)
    cases, reference = [], []
    for source in (row for row in baseline_input if row['dataset'] == 'ContractNLI'):
        selected, view = disclosure.build(source)
        anchor, group = SOURCE_REVIEWS[selected['key'][-8:]]
        span = view['relational_public_source']['indexed_ranges'][anchor]
        state = {'disclosure_actor': 'receiver', 'recipient_group': group, 'permission_force': 'allow'}
        expected = 'Entailment' if group == 'own_employees' else None
        for plan in view['plans']:
            unit = plan['relational_program']['units'][disclosure.UNIT]
            keys, _ = indexed.encoded_relations(unit['asset'])
            encoded = encode(unit['asset']['features'], state)
            symbol = '|'.join([anchor, *(indexed.symbol(encoded[key]) for key in keys)])
            result = decode_response(selected, view, plan, {'content': json.dumps(symbol), 'finish_reason': 'stop'})
            native = result['native'][disclosure.TASK]
            ids = disclosure.native_evidence(selected['views'][0]['public'], anchor, span)
            if (result['production_errors'] or native['answer'] != expected
                    or native['evidence_sentence_ids'] != (ids if expected else [])):
                raise ValueError('The reference clause reading lost its production answer or native evidence IDs')
            reference.append({'source': source['key'], 'plan': plan['name'], 'anchor': anchor,
                              'source_supports_answer': expected is not None, 'reference_production_passed': True})
        target = grades[source['key']][disclosure.TASK]['answer']
        cases.append({'public_source': selected, 'view': view,
                      'expected_local_projection': {disclosure.TASK: target}})
    if len(cases) != 4:
        raise ValueError('All fixed TRAIN documents must remain in the denominator')
    paths = [
        'experiments/convergence_cni_disclosure_probe.py',
        'experiments/convergence_maud_clause_probe.py',
        'legal_skill_guard/paired_interfaces/cni_disclosure_relational.py',
        'legal_skill_guard/paired_interfaces/indexed_relational_read.py',
        'legal_skill_guard/paired_interfaces/relational_program.py',
        'legal_skill_guard/paired_interfaces/residual.py',
        'legal_skill_guard/paired_interfaces/production_decode.py',
        'legal_skill_guard/paired_interfaces/formal_actors.py',
        'legal_skill_guard/skill_evolution/clients.py',
        'legal_skill_guard/skill_evolution/ledger.py',
        'legal_skill_guard/rr/client.py',
    ]
    binding = {
        'study_id': 'convergence_CNI_employee_disclosure_bindings_v1',
        'cases_sha256': digest(cases), 'source_sha256': {name: sha(ROOT / name) for name in paths},
        'source_gold_sha256': sha(grade_path), 'common_indexed_baseline_sha256': sha(common / 'terminal.json'),
        'executor': baseline_binding['executor'],
        'full_native_question_scored': True,
        'scope': 'one native employee-disclosure hypothesis in four fixed TRAIN documents',
        'both_arms_receive_identical_raw_document_and_clause_windows': True,
        'nominal_clause_reviews_do_not_supply_native_answers_or_evidence_labels_to_the_reader': True,
    }
    out = BASE / 'cni_disclosure_m1_probe' / digest(binding)
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'cases.json', cases)
    immutable_json(out / 'reference_check.json', reference)
    status = {'artifact_root': str(out.relative_to(ROOT)), 'status': 'prepared', 'reader_cells': 8}
    tmp = POINTER.with_suffix('.tmp')
    tmp.write_text(json.dumps(status, indent=2) + '\n')
    tmp.replace(POINTER)
    print(json.dumps(status), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else lambda: run(POINTER))()
