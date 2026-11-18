"""Compare complete paired ContractNLI readers on the same four TRAIN mothers."""

import argparse
import json
import sqlite3

import jsonschema

from experiments.convergence_cni_disclosure_probe import SOURCE_REVIEWS
from experiments.convergence_pilot_b0 import BASE, CNI_INDEXED_POINTER, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_disclosure_relational as disclosure
from legal_skill_guard.paired_interfaces import indexed_relational_read as indexed
from legal_skill_guard.paired_interfaces.convergence_cni_bundle import build_bundle, decode_bundle
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.residual import encode
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest

POINTER = HANDOFF / 'cni_hybrid_native_current.json'


def prepare():
    common = ROOT / read(CNI_INDEXED_POINTER)['artifact_root']
    original = read(common / 'binding.json')
    sources = read(common / 'public_TRAIN_pilot.json')
    if (read(common / 'terminal.json')['status'] != 'completed' or digest(sources) != original['sources_digest']
            or len(sources) != 4 or any(s['project_split'] != 'train' for s in sources)):
        raise ValueError('Bind the same four completed indexed TRAIN documents')
    previous = ROOT / read(HANDOFF / 'cni_disclosure_mentions_current.json')['artifact_root']
    prior = read(previous / 'terminal_provenance_and_scope_check.json')
    if prior['status'] != 'completed' or prior['source_bound_correct'] != {'fixed': 1, 'synthesized': 1}:
        raise ValueError('Target the actual earlier event and role attachment failures')
    actual = {record['source']: record for path in (common / 'program_executions').glob('*/result.json')
              for record in [read(path)]}
    checks, cases = [], []
    for source in sources:
        key = source['key']
        trace, = actual[key]['traces']
        if trace['finish_reason'] != 'stop' or trace['status'] != 'validated':
            raise ValueError('Require complete original native wire evidence for the reference transfer')
        original_wire, _ = restore_enum_transport(json.loads(trace['raw_content']), trace['schema'])
        remaining = {task: output for task, output in original_wire['value'].items() if task != disclosure.TASK}
        bundle = build_bundle(source)
        anchor, group = SOURCE_REVIEWS[key[-8:]]
        for plan in bundle['plans']:
            lookup = plan['local_plan']['relational_program']['units'][disclosure.UNIT]
            fields, _ = indexed.encoded_relations(lookup['asset'])
            encoded = encode(lookup['asset']['features'], {
                'disclosure_actor': 'receiver', 'recipient_group': group, 'permission_force': 'allow',
            })
            wire = '|'.join([anchor, *(indexed.symbol(encoded[name]) for name in fields)])
            result = decode_bundle(source, bundle, plan, {'finish_reason': 'stop',
                'content': json.dumps({'native_answers': remaining, 'disclosure': wire})})
            if (result['local_production_errors'] or len(result['native']) != 17
                    or any(result['native'][task]['answer'] != output['answer']
                           or result['native'][task]['evidence_sentence_ids'] != output['evidence_sentence_ids']
                           for task, output in remaining.items())
                    or result['native'][disclosure.TASK]['answer'] != ('Entailment' if group is not None else None)):
                raise ValueError('The paired full native layout must preserve every task and original evidence')
            local_input = json.loads(plan['messages'][1]['content'])['employee_disclosure_subtask']
            exact = bundle['selected_source']['views'][0]['public']['source_text']
            if any(exact[phrase['start']:phrase['end']] != phrase['text']
                   for window in local_input['event_coordinates'] for phrase in window['event_wording']):
                raise ValueError('A shared event coordinate does not have exact public source wording')
            checks.append({'source_sha256': digest(source), 'plan_sha256': plan['version'],
                           'original_physical_call_id': trace['physical_call_id'], 'native_tasks': 17})
        if bundle['plans'][0]['messages'][1] != bundle['plans'][1]['messages'][1]:
            raise ValueError('Fixed and synthesized reads must get byte-identical public evidence')
        cases.append({'source': source, 'bundle': bundle})
    paths = set(original['source_sha256']) | set(read(previous / 'binding.json')['source_sha256']) | {
        'experiments/convergence_cni_bundle_probe.py', 'legal_skill_guard/paired_interfaces/convergence_cni_bundle.py',
        'legal_skill_guard/paired_interfaces/scope_learning.py',
    }
    grade = original['grading_paths']['ContractNLI']
    binding = {'study_id': 'convergence_cni_complete_native_employee_interface',
               'source_sha256': {path: sha(ROOT / path) for path in sorted(paths)}, 'cases_sha256': digest(cases),
               'evidence_previous_root': str(previous.relative_to(ROOT)),
               'previous_attach_failure_sha256': sha(previous / 'terminal_provenance_and_scope_check.json'),
               'grading_path': grade, 'grading_sha256': original['grading_file_sha256'][grade],
               'executor': original['executor'], 'original_full_native_wire_preserved': True,
               'shared_public_participant_and_event_coordinates': True, 'paired_cells': len(checks)}
    out = BASE / 'cni_hybrid_native' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'cases.json', cases)
    immutable_json(out / 'reference_replay.json', {'rows': checks, 'native_tasks': 17 * len(checks), 'new_calls': 0})
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    write_status(out, {'status': 'prepared', 'paired_cells': len(checks), 'native_tasks': 17 * len(checks)}, POINTER)
    print(json.dumps(read(POINTER)), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps({'status': 'completed', 'new_calls': 0}), flush=True)
        return
    binding = read(out / 'binding.json')
    cases = read(out / 'cases.json')
    if (digest(cases) != binding['cases_sha256'] or sha(ROOT / binding['grading_path']) != binding['grading_sha256']
            or any(sha(ROOT / name) != version for name, version in binding['source_sha256'].items())):
        raise ValueError('A bound native reader condition changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved' limit 1").fetchone():
            raise ValueError('A current physical request must settle before this comparison')
    keys = [case['source']['key'] for case in cases]
    ledger = EvolutionLedger(LEDGER, run_id='convergence-cni-native-hybrid-' + digest(binding)[:16],
                             sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['executor'])
    ready = executor.readiness()
    immutable_json(out / 'executor_preflight.json', ready)
    predictions = []
    write_status(out, {'status': 'running', 'completed_cells': 0}, POINTER)
    try:
        for case in cases:
            source, bundle = case['source'], case['bundle']
            for plan in bundle['plans']:
                name = 'fixed' if plan['local_plan']['is_correct_fixed_raw_control'] else 'synthesized'
                logical_id = ledger.run_id + ':' + digest([source['key'], plan['version']])
                physical = executor.generate(logical_id, source=source['key'], purpose='skill_actor', thinking=False,
                                             schema=plan['schema'], messages=plan['messages'])
                row_id = physical.get('reused_physical_call_id', logical_id)
                verify_physical_response(executor, identity=row_id, source=source['key'], purpose='skill_actor',
                    content_sha256=digest(physical['content']), usage=physical['usage'], finish_reason=physical['finish_reason'])
                try:
                    result = decode_bundle(source, bundle, plan, physical)
                except (ValueError, jsonschema.ValidationError) as exc:
                    result = {'native': dict.fromkeys((task['id'] for task in source['views']),
                                {'handled': False, 'answer': None, 'evidence_sentence_ids': []}),
                              'local_production_errors': [type(exc).__name__], 'fallback_executed': False}
                row = {'source': source['key'], 'plan': name, 'plan_version': plan['version'],
                       'result': result, 'physical_call_id': row_id, 'usage': physical['usage']}
                immutable_json(out / 'predictions' / (digest([source['key'], name]) + '.json'), row)
                predictions.append(row)
        immutable_json(out / 'prediction_seal.json', {'predictions_sha256': digest(predictions)})
        grade = read(ROOT / binding['grading_path'])
        scores = {'fixed': [], 'synthesized': []}
        public = {case['source']['key']: case['source'] for case in cases}
        for row in predictions:
            source = public[row['source']]
            output = row['result']['native']
            tasks = {view['id']: grade_view(source['dataset'], view, grade[source['key']][view['id']],
                output[view['id']]['answer'], output[view['id']]['evidence_sentence_ids']) for view in source['views']}
            scores[row['plan']].append({'source': source['key'], 'tasks': tasks, 'raw_read': row['physical_call_id']})
        immutable_json(out / 'measured_scores.json', scores)
        summary = {name: {'full_17_native_correct': sum(v['grade'] for row in vals for v in row['tasks'].values()),
                          'local_native_correct': sum(row['tasks'][disclosure.TASK]['grade'] for row in vals)}
                   for name, vals in scores.items()}
        terminal = {'status': 'completed', 'mothers': len(cases), 'scores': summary,
                    'cost_tokens': sum(row['usage']['total_tokens'] for row in predictions),
                    'production_rejections': sum(bool(row['result']['local_production_errors']) for row in predictions),
                    'independent_source_grounding_requires_review': True}
        immutable_json(out / 'terminal.json', terminal)
        write_status(out, terminal, POINTER)
        print(json.dumps(terminal), flush=True)
    except Exception as error:
        write_status(out, {'status': 'interrupted_or_failed', 'completed_cells': len(predictions),
                           'error_type': type(error).__name__}, POINTER)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
