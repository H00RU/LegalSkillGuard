"""Measure shared amount validation on the same teacher patches and paid native controls."""

import argparse
import json
import sqlite3

import jsonschema

from experiments.convergence_diversity_grouped_probe import POINTER as CALIBRATION
from experiments.convergence_diversity_grouped_reuse import POINTER as REUSE
from experiments.convergence_m2_update_probe import TEACHER_SCHEMA, frozen_paths
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_source_audit import study_teacher_configuration
from legal_skill_guard.paired_interfaces import diversity_claim_groups
from legal_skill_guard.paired_interfaces.convergence_regression_controls import compare_shared_selectors
from legal_skill_guard.paired_interfaces.diversity_amount_supervision import controlled_amount_relation
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor, verify_physical_response
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.paired_interfaces.shared_semantics_validation import validate_patch
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'm2_amount_update_current.json'
PROFILE = {'citizenship': 0, 'same_pair_claims': 1}
SYSTEM = (
    'Return two distinct additions to the legal reader skill, each at most 90 words. Both additions must '
    'be reusable on the original jurisdiction task and its local amount projection. Keep the existing '
    'evidence scope, legal rule and output types. Focus one on accurate amount binding and arithmetic, '
    'and the other on a lower or upper bound proof from stated amounts. Do not use source names, '
    'made-up facts, solved examples, native labels, or executable code.'
)


def prepare():
    cal, reuse = (ROOT / read(pointer)['artifact_root'] for pointer in (CALIBRATION, REUSE))
    cal_report, reuse_report = read(cal / 'terminal.json'), read(reuse / 'terminal.json')
    if (cal_report['status'] != 'completed' or reuse_report['status'] != 'completed'
            or any(row['native_utility'] != [1.0, 0.0] for row in reuse_report['paired_fixed_then_learned'])):
        raise ValueError('Use the measured below-threshold failure and all its actual native controls')
    initial, later = read(cal / 'sources.json'), read(reuse / 'targets.json')['sources']
    sources = initial + later
    if len({source['key'] for source in sources}) != 4 or any(s['project_split'] != 'train' for s in sources):
        raise ValueError('Bind both calibration and both independent TRAIN reuse mothers')
    measured = [row['physical_call_id'] for row in cal_report['paired_scores'] if dict(row['profile']) == PROFILE]
    measured += [row['physical_call_ids'][1] for row in reuse_report['paired_fixed_then_learned']]
    preflight = read(HANDOFF / 'M2_diversity_amount_relation_preflight_20261118.json')
    source, = (item for item in initial if item['key'] == preflight['native_mother'])
    fields = preflight['groups'][0]['shared_primitives']
    group = controlled_amount_relation(source, fields, entailed_anchor=True)
    if len(group['shared']['signatures']) != 3 or len(group['independent']['signatures']) != 4:
        raise ValueError('The high-amount anchor must preserve the nontrivial shared relation')
    profile, teacher = study_teacher_configuration()
    previous = read(cal / 'binding.json')
    files = set(frozen_paths()) | set(previous['source_sha256']) | {
        'experiments/convergence_m2_amount_update.py',
        'legal_skill_guard/paired_interfaces/diversity_amount_supervision.py',
        'legal_skill_guard/paired_interfaces/convergence_regression_controls.py'}
    feedback = {'observed_TRAIN_error': 'Explicitly below-threshold grouped claim sums were read as exceeding the threshold.',
                'public_rule': 'The amount for the specified plaintiff and defendant must strictly exceed 75000 dollars.',
                'format': 'Keep fixed citizenship coordinates and local Boolean amount relations. None means unresolved.',
                'relation_scope': 'For a mask with a shared nonnegative unknown amount, isolated facts may not establish a '
                                  'comparison. The lower bound alone can establish it if it is strictly above the threshold.'}
    binding = {'study': 'convergence_amount_same_pool_actual_update', 'executor': previous['executor'],
               'teacher_profile': profile, 'teacher_config': teacher, 'sources_sha256': digest(sources),
               'source_sha256': {name: sha(ROOT / name) for name in sorted(files)}, 'feedback_sha256': digest(feedback),
               'group_mother': source['key'], 'group_fields': fields,
               'edited_public_sha256': [digest(case.public) for case in group['cases']],
               'native_incumbent_physical_ids': measured,
               'prior_roots': {str(root.relative_to(ROOT)): sha(root / 'terminal.json') for root in (cal, reuse)},
               'grading_path': previous['grading_path'], 'grading_sha256': previous['grading_sha256'],
               'new_teacher_cells': 1, 'new_native_executor_cells': 8, 'new_projection_executor_cells': 9}
    out = BASE / 'm2_amount_update' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'sources.json', sources)
    immutable_json(out / 'teacher_input.json', feedback)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'native_mothers': len(sources), 'edited_cases': 3}, POINTER)
    print(json.dumps(read(POINTER)), flush=True)


def _base_plan(provider, source):
    view, = provider.views(source)
    plan, = (plan for plan in view['plans'] if plan['choices'] == PROFILE)
    return view, plan


def _projection(executor, out, name, directive, case, parties):
    schema = record_schema({'exceeds_threshold': {'type': ['boolean', 'null']}})
    messages = [{'role': 'system', 'content': (
        'Answer the local amount question from the named parties’ stated claims. Exceeding the threshold requires '
        'strictly more than 75000 dollars. Use null if the public information leaves the comparison undecided. '
        'Do not infer an unstated number. Report only the specified local field.\n' + directive)},
        {'role': 'user', 'content': json.dumps({**case.public, 'plaintiff': parties[0], 'defendant': parties[1]},
                                             ensure_ascii=False, sort_keys=True)}]
    call_id = executor.ledger.run_id + ':projection:' + digest([name, case.source_id, messages, schema])
    response = executor.generate(call_id, source=case.root_id, purpose='skill_actor', messages=messages,
                                 thinking=False, schema=schema)
    physical = response.get('reused_physical_call_id', call_id)
    verify_physical_response(executor, identity=physical, source=case.root_id, purpose='skill_actor',
                             content_sha256=digest(response['content']), usage=response['usage'],
                             finish_reason=response['finish_reason'])
    try:
        if response['finish_reason'] != 'stop':
            raise ValueError('Non-stop reader output')
        decoded = json.loads(response['content'])
        jsonschema.validate(decoded, schema)
        value = decoded['exceeds_threshold']
        error = None
    except (ValueError, jsonschema.ValidationError) as exc:
        value, error = None, str(exc)
    row = {'case': case.source_id, 'case_sha256': digest(case.public), 'projection': value,
           'physical_call_id': physical, 'decode_error': error, 'request_sha256': digest(messages)}
    immutable_json(out / 'projection_reads' / (digest(call_id) + '.json'), row)
    return row


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')['decisions']), flush=True)
        return
    binding, sources, feedback = (read(out / (name + '.json')) for name in ('binding', 'sources', 'teacher_input'))
    if (out.name != digest(binding) or digest(sources) != binding['sources_sha256']
            or digest(feedback) != binding['feedback_sha256'] or any(sha(ROOT / name) != expected
                       for name, expected in binding['source_sha256'].items())):
        raise ValueError('The fixed TRAIN source, teacher feedback or production code changed')
    keys = [source['key'] for source in sources]
    group_source, = (source for source in sources if source['key'] == binding['group_mother'])
    group = controlled_amount_relation(group_source, binding['group_fields'], entailed_anchor=True)
    cases = group['cases']
    if [digest(case.public) for case in cases] != binding['edited_public_sha256']:
        raise ValueError('The rendered source variants changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Settle the prior physical request first')
    ledger = EvolutionLedger(LEDGER, run_id='convergence-m2-amount-' + out.name[:16],
                             sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.readiness()
    provider = diversity_claim_groups.Provider()
    actor = InterfaceActor(reader, out, plan_assets={}, source_inputs=None, relational_provider=provider,
                           pipeline_binding=binding['source_sha256'])
    paid = {}
    for directory, checksum in binding['prior_roots'].items():
        root = ROOT / directory
        if sha(root / 'terminal.json') != checksum:
            raise ValueError('The actual incumbent terminal evidence changed')
        for path in (root / 'interface_reads').glob('*/decoded.json'):
            row = read(path)
            if row['physical_call_id'] in binding['native_incumbent_physical_ids']:
                task = read(path.with_name('task.json'))
                if row['task_sha256'] != digest(task) or task['purpose'] != 'skill_actor':
                    raise ValueError('A paid read lost its original input identity')
                paid[row['physical_call_id']] = (row, task)
    if set(paid) != set(binding['native_incumbent_physical_ids']):
        raise ValueError('Every original native incumbent must be reused, with full physical provenance')
    stage = 'teacher'
    try:
        write_status(out, {'status': 'running', 'stage': stage}, POINTER)
        teacher = FrozenTeacher(ledger, out, binding['teacher_config'], authorized_profile=binding['teacher_profile'])
        result = teacher.propose(ledger.run_id + ':teacher', source_ids=keys, system_prompt=SYSTEM,
                                 user_prompt=json.dumps(feedback, sort_keys=True), output_schema=TEACHER_SCHEMA)
        directives = result['value']
        if (result['model'] != binding['teacher_config']['model'] or len(set(directives.values())) != 2
                or any(not s.strip() or len(s.split()) > 90 for s in directives.values())):
            raise ValueError('Use exactly the two bounded proposals from the frozen teacher')
        programs = {'incumbent': '', **directives}
        immutable_json(out / 'programs.json', programs)
        stage = 'paired_reads'
        write_status(out, {'status': 'running', 'stage': stage}, POINTER)
        grade_path = ROOT / binding['grading_path']
        if sha(grade_path) != binding['grading_sha256']:
            raise ValueError('The independent native TRAIN scorer inputs changed')
        gold = read(grade_path)
        reports = {}
        for name, directive in programs.items():
            program = digest({'layout': PROFILE, 'directive': directive, 'native_production_binding': binding['source_sha256']})
            native = {}
            for source, old_id in zip(sources, binding['native_incumbent_physical_ids'], strict=True):
                view, plan = _base_plan(provider, source)
                original, task = paid[old_id]
                if (original['source'] != source['key'] or original['raw_read_version'] != plan['version']
                        or task['source_public_sha256'] != digest(source)):
                    raise ValueError('Incumbent replay must use the exact paid layout and source')
                verify_physical_response(reader, identity=old_id, source=source['key'], purpose='skill_actor',
                                         content_sha256=original['response_content_sha256'], usage=original['usage'],
                                         finish_reason=original['response_finish_reason'])
                if directive:
                    plan = {**plan, 'system': plan['system'] + '\nAdditional reader guidance: ' + directive,
                            'reader_template_sha256': digest([plan['reader_template_sha256'], directive])}
                    plan['version'] = digest({k: v for k, v in plan.items() if k != 'version'})
                    measured = actor.measure(source, {**view, 'plans': [plan]}, plan, 'skill_actor')
                else:
                    measured = original
                task_view, = source['views']
                answer = measured['native'][task_view['id']]
                value = (grade_view(source['dataset'], task_view, gold[source['key']][task_view['id']], answer['answer'])['grade']
                         if answer['handled'] else 0.0)
                native[source['key']] = {'grade': value, 'physical_call_id': measured['physical_call_id']}
            projected = [_projection(reader, out, name, directive, case, min(group['covered_pairs'])) for case in cases]
            reports[name] = {'program_sha256': program, 'native': native, 'projected': projected}
            immutable_json(out / 'measurements' / (name + '.json'), reports[name])
        base = reports['incumbent']['native']
        checks = {}
        for name, measured in reports.items():
            proof = measured['projected']
            native_rows = [{'source': key, 'baseline_utility': base[key]['grade'],
                            'patch_utility': measured['native'][key]['grade']} for key in keys]
            checks[name] = validate_patch(
                group['theory'], measured['program_sha256'], [{'cases': cases, 'outputs': [r['projection'] for r in proof],
                    'physical_call_ids': [r['physical_call_id'] for r in proof]}], native_rows, visible_train=keys,
                verify_projection=lambda patch, physical, case, value: patch == measured['program_sha256'] and any(
                    physical == row['physical_call_id'] and case.source_id == row['case']
                    and digest(case.public) == row['case_sha256'] and value == row['projection'] for row in proof),
                verify_native_pair=lambda patch, row: patch == measured['program_sha256'] and row in native_rows,
            )
        decisions = compare_shared_selectors('incumbent', checks)
        terminal = sealed({'status': 'completed', 'decisions': decisions, 'measurements': reports,
                           'validation': checks, 'controlled_missingness': True, 'TEST_opened': False}, 'terminal_sha256')
        verify(terminal, 'terminal_sha256')
        immutable_json(out / 'terminal.json', terminal)
        write_status(out, {'status': 'completed', 'decisions': decisions}, POINTER)
        print(json.dumps({'decisions': decisions, 'native_correct': {n: sum(r['grade'] for r in v['native'].values())
                                                                  for n, v in reports.items()}}), flush=True)
    except Exception as error:
        write_status(out, {'status': 'interrupted_or_failed', 'stage': stage, 'error_type': type(error).__name__}, POINTER)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
