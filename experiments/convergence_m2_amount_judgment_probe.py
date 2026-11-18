"""Assess judgment compatibility of the paid native-positive pilot layout."""

import argparse
import json
import sqlite3

from experiments.convergence_m2_amount_judgment import group_binding, measure, validate_update
from experiments.convergence_m2_amount_update import CALIBRATION, PROFILE, _base_plan
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_shared_dev_checkpoint import ReadOnlyLedger
from legal_skill_guard.paired_interfaces import diversity_claim_groups
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.control_programs import ControlProgramRuntime
from legal_skill_guard.paired_interfaces.diversity_amount_judgment_supervision import controlled_amount_judgment_relation
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor, verify_physical_response
from legal_skill_guard.paired_interfaces.formal_tools import legal_tools
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'm2_amount_judgment_probe_current.json'


def _bank(calibration, baseline):
    stored, common = read(calibration / 'binding.json'), read(baseline / 'binding.json')
    terminal = read(calibration / 'terminal.json')
    sources = read(calibration / 'sources.json')
    pilot = {s['key']: s for s in read(baseline / 'public_TRAIN_pilot.json')}
    if (terminal['status'] != 'completed' or read(baseline / 'terminal.json')['status'] != 'completed'
            or digest(sources) != stored['original_sources_sha256'] or len(sources) != 2
            or any(s['project_split'] != 'train' or pilot.get(s['key']) != s for s in sources)
            or stored['executor'] != common['executor']):
        raise ValueError('Bind the two preselected fixed-pilot mothers and the same frozen runtime')
    gold_path = ROOT / stored['grading_path']
    if sha(gold_path) != stored['grading_sha256']:
        raise ValueError('The settled TRAIN scorer changed')
    gold = read(gold_path)
    expected = {r['physical_call_id']: r for r in terminal['paired_scores'] if dict(r['profile']) == PROFILE}
    measured = {}
    for path in (calibration / 'interface_reads').glob('*/decoded.json'):
        row = read(path)
        if row['physical_call_id'] in expected:
            measured[row['source']] = (row, read(path.with_name('task.json')))
    reader = FrozenExecutor(ReadOnlyLedger(), baseline, common['executor'])
    actor = ProgramActor(reader, baseline, max_calls=1)
    provider = diversity_claim_groups.Provider()
    comparisons, plans = [], {}
    for source in sources:
        key = source['key']
        task, = source['views']
        row, saved = measured[key]
        _, plan = _base_plan(provider, source)
        if (row['task_sha256'] != digest(saved) or saved['source_public_sha256'] != digest(source)
                or saved['raw_read_version'] != plan['version'] or saved['purpose'] != 'skill_actor'):
            raise ValueError('The calibrated candidate lost its exact source or layout')
        verify_physical_response(reader, identity=row['physical_call_id'], source=key, purpose='skill_actor',
                                 content_sha256=row['response_content_sha256'], usage=row['usage'],
                                 finish_reason=row['response_finish_reason'])
        audit = read(baseline / 'source_results' / (digest(key) + '.json'))
        bundle = source_bundle(source)
        tools, assets = legal_tools(source, bundle)
        runtime = ControlProgramRuntime(reader, baseline, max_calls=1, shared_assets=assets, legal_tools=tools)
        execution = read(runtime.execution_path(common['program'], source, bundle, purpose='skill_actor'))
        actor.verify_program_result(source, common['program'], 'skill_actor', {'execution': execution, 'native': audit['native']})
        before = grade_view(source['dataset'], task, gold[key][task['id']], audit['native'][task['id']]['answer'])['grade']
        after = grade_view(source['dataset'], task, gold[key][task['id']], row['native'][task['id']]['answer'])['grade']
        if before != audit['grades'][task['id']]['grade'] or after != expected[row['physical_call_id']]['native']:
            raise ValueError('The physical native result no longer agrees with the preserved scores')
        comparisons.append({'source': key, 'baseline_utility': before, 'patch_utility': after})
        plans[key] = plan
    if sum(r['patch_utility'] - r['baseline_utility'] for r in comparisons) <= 0:
        raise ValueError('The existing native support must be positive before any projection calls')
    anchor = read(HANDOFF / 'M2_diversity_amount_relation_preflight_20261118.json')
    mother, = (source for source in sources if source['key'] == anchor['native_mother'])
    group = controlled_amount_judgment_relation(mother, anchor['groups'][0]['shared_primitives'])
    # In the local diagnostic the layout guidance is adapted to the same projection
    # codec for both readers. Original native executions and scores remain immutable.
    diagnostic = {'predicates': [{'prompt': plans[mother['key']]['system']}],
                  'bound_native_layouts': {key: plan['version'] for key, plan in plans.items()}}
    return stored, comparisons, group, common['program'], diagnostic


def prepare():
    calibration = ROOT / read(CALIBRATION)['artifact_root']
    baseline = ROOT / read(HANDOFF / 'pilot_b0_current.json')['artifact_root']
    stored, native, group, original, candidate = _bank(calibration, baseline)
    paths = set(stored['source_sha256']) | set(read(baseline / 'binding.json')['source_sha256']) | {
        'experiments/convergence_m2_amount_judgment_probe.py', 'experiments/convergence_m2_amount_judgment.py',
        'experiments/convergence_m2_amount_update.py',
        'legal_skill_guard/paired_interfaces/diversity_amount_judgment_supervision.py',
        'legal_skill_guard/paired_interfaces/diversity_amount_supervision.py'}
    binding = {'data_scope': 'fixed_pilot_calibration_mothers_only', 'executor': stored['executor'],
               'calibration': str(calibration.relative_to(ROOT)), 'baseline': str(baseline.relative_to(ROOT)),
               'prior_terminals': {str(r.relative_to(ROOT)): sha(r / 'terminal.json') for r in (calibration, baseline)},
               'source_sha256': {path: sha(ROOT / path) for path in sorted(paths)},
               'native_sha256': digest(native), 'group_sha256': group_binding(group),
               'programs_sha256': digest([original, candidate]), 'adapted_projection_codec': True}
    out = BASE / 'm2_amount_judgment_probe' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'native_pairs.json', native)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'native_mothers': len(native), 'new_teacher_requests': 0,
                           'new_native_requests': 0, 'projection_cells': len(group['cases']) * 2}, POINTER)
    print(json.dumps(read(POINTER), sort_keys=True), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(POINTER), sort_keys=True), flush=True)
        return
    binding = read(out / 'binding.json')
    if (out.name != digest(binding) or any(sha(ROOT / f) != v for f, v in binding['source_sha256'].items())
            or any(sha(ROOT / f / 'terminal.json') != v for f, v in binding['prior_terminals'].items())):
        raise ValueError('The settled native bank or projection runtime changed')
    _, native, group, original, candidate = _bank(ROOT / binding['calibration'], ROOT / binding['baseline'])
    if (native != read(out / 'native_pairs.json') or digest(native) != binding['native_sha256']
            or group_binding(group) != binding['group_sha256'] or digest([original, candidate]) != binding['programs_sha256']):
        raise ValueError('Use the identical native evidence and audited legal projection')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Settle the other study job first')
    keys = [r['source'] for r in native]
    run_id = 'convergence-M2-judgment-pilot-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.readiness()
    write_status(out, {'status': 'running', 'phase': 'projected_reads'}, POINTER)
    projections = {name: measure(reader, out, program, group)
                   for name, program in (('incumbent', original), ('candidate', candidate))}
    audit = validate_update(candidate, group, projections['candidate'], native, keys)
    with ledger.transaction() as db:
        physical = db.execute('select status,result from calls where id like ?', (run_id + ':%',)).fetchall()
    if any(status != 'completed' for status, _ in physical):
        raise ValueError('All projection calls must settle before publication')
    result = {'status': 'completed_paid_native_positive_quantity_probe', 'candidate_validation': audit,
              'projections': projections, 'new_executor_requests': len(physical),
              'executor_tokens': sum(json.loads(result)['usage']['total_tokens'] for _, result in physical),
              'new_native_requests': 0, 'new_teacher_requests': 0, 'controlled_missingness': True,
              'formal_update_committed': False, 'TEST_opened': False}
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'candidate_selected_by': audit['candidate_selected_by'],
                       'judgment_gate': audit['judgment_gate'], 'external_tokens': result['executor_tokens']}, POINTER)
    print(json.dumps(read(POINTER), sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
