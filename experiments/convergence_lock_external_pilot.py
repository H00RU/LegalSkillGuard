"""Verify the four matched external adaptations and lock the ranking once."""

from copy import deepcopy
import json
import math

from experiments.convergence_compact_teacher_pilot import pointer
from experiments.convergence_parse_pilot import POINTER as PARSE
from experiments.convergence_pilot_b0 import HANDOFF, ROOT, read, sha
from experiments.convergence_scope_legal_edits import POINTER as SCOPE_EDITS
from experiments.convergence_shared_dev_checkpoint import ReadOnlyLedger
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.control_programs import ControlProgramRuntime
from legal_skill_guard.paired_interfaces.convergence_actors import common_cells
from legal_skill_guard.paired_interfaces.convergence_compact_proposal import (
    compact_native_passthrough, compile_proposal,
)
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_tools import legal_tools
from legal_skill_guard.paired_interfaces.pilot_metrics import rank_external_pilot, summarize
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


LOCK = HANDOFF / 'locked_external_baseline_20261118.json'


def _baseline_rows(sources, binding, baseline):
    results = []
    for source in sources:
        dataset, key = source['dataset'], source['key']
        origin = 'cni_indexed_evidence_current.json' if dataset == 'ContractNLI' else 'pilot_b0_current.json'
        directory = ROOT / read(HANDOFF / origin)['artifact_root']
        if sha(directory / 'terminal.json') != binding['common_terminal_receipts'][str(directory.relative_to(ROOT))]:
            raise ValueError('The common incumbent physical predictions changed')
        record = read(directory / 'source_results' / (digest(key) + '.json'))
        for task in source['views']:
            view = task['id']
            grade, handled = baseline[key][view], record['native'][view]['handled']
            if grade != record['grades'][view]['grade']:
                if dataset != 'RuleArena_Airline' or grade != 1:
                    raise ValueError('Only the validated common Airline payment correction is permitted')
                handled = True
            results.append({'source': key, 'dataset': dataset, 'view': view, 'grade': grade, 'handled': handled})
    return results


def _paid_usage(ledger, teacher, executor):
    totals = {role: {'calls': len(ids), 'tokens': 0} for role, ids in [('teacher', teacher), ('executor', executor)]}
    with ledger.transaction() as db:
        for role, identities in [('teacher', teacher), ('executor', executor)]:
            for identity in identities:
                saved = db.execute('select role,status,result from calls where id=?', (identity,)).fetchone()
                if saved is None or saved[:2] != (role, 'completed'):
                    raise ValueError('The comparison must bind actual completed physical observations')
                result = json.loads(saved[2])
                usage = result['usage'] if role == 'executor' else result['invocation']['usage']
                totals[role]['tokens'] += (usage['total_tokens'] if role == 'executor'
                                           else usage['input_tokens'] + usage['output_tokens'])
    return totals


def _compact_rows(style, common, sources, baseline_rows, ledger):
    root = ROOT / read(pointer(style))['artifact_root']
    binding, terminal = read(root / 'binding.json'), read(root / 'terminal.json')
    if (root.name != digest(binding) or digest(common) != binding['parent_binding_sha256']
            or terminal['status'] != 'completed' or terminal['style'] != style):
        raise ValueError('Use the completed proposal and same five-library pilot for every adaptation')
    recovery = binding.get('recovery', {})
    baseline = {(row['source'], row['view']): row for row in baseline_rows}
    by_library, selected, teachers, executors = {}, {}, set(), set()
    keys = [source['key'] for source in sources]
    for dataset, summary in terminal['libraries'].items():
        prior = recovery.get('measured_libraries', {}).get(dataset)
        directory = ROOT / recovery['root'] if prior else root
        path = directory / 'measured_libraries' / (dataset + '.json')
        record = read(path)
        if (summary != record['summary'] or summary['status'] != 'completed' or (prior and sha(path) != prior)):
            raise ValueError('The compact ranking must preserve each actual candidate measurement')
        teacher = record['teacher_physical_call']
        with ledger.transaction() as db:
            row = db.execute('select role,status,result from calls where id=?', (teacher,)).fetchone()
        if row is None or row[:2] != ('teacher', 'completed') or json.loads(row[2])['value'] != record['proposal']:
            raise ValueError('The measured proposal lost its exact teacher provenance')
        teachers.add(teacher)
        program = compile_proposal(record['proposal'], keys)
        if dataset == 'OpenExempt':
            program = compact_native_passthrough(program)
        grade_path = common['grading_paths'][dataset]
        if sha(ROOT / grade_path) != common['grading_file_sha256'][grade_path]:
            raise ValueError('Ranking uses the original native TRAIN grade file')
        grades = read(ROOT / grade_path)
        proof = record['measurement']
        if proof['program_sha256'] != digest(program):
            raise ValueError('The declared candidate differs from the executed program')
        region = [source for source in sources if source['dataset'] == dataset]
        expected = {(source['key'], view['id']) for source in region for view in source['views']}
        executor = FrozenExecutor(ledger, directory, binding['executor'])
        actor = ProgramActor(executor, directory, max_calls=1)
        rows = []
        for source, receipt in zip(region, proof['source_rows'], strict=True):
            if dataset == 'RuleArena_Airline':
                source = {**source, 'enable_public_airline_fee_tool': True}
            key = source['key']
            if key != receipt['source'] or digest(source) != receipt['public_sha256']:
                raise ValueError('The source was re-bound after measurement')
            native, physicals = {}, []
            for cell in common_cells(source):
                bundle = source_bundle(cell)
                tools, assets = legal_tools(cell, bundle)
                runtime = ControlProgramRuntime(executor, directory, max_calls=1, shared_assets=assets, legal_tools=tools)
                execution = read(runtime.execution_path(program, cell, bundle, purpose='skill_actor'))
                answers = actor._native(cell, execution)
                actor.verify_program_result(cell, program, 'skill_actor', {'execution': execution, 'native': answers})
                native.update(answers)
                physicals.extend(trace['physical_call_id'] for trace in execution['traces']
                                 if 'finish_reason' in trace and 'physical_call_id' in trace)
            if digest(native) != receipt['actual_prediction_sha256'] or physicals != receipt['physical_call_ids']:
                raise ValueError('The original physical model responses must produce the reported outcomes')
            executors.update(physicals)
            for view in source['views']:
                task = view['id']
                answer = native[task]
                grade = (grade_view(dataset, view, grades[key][task], answer['answer'],
                                    answer.get('evidence_sentence_ids', []))['grade'] if answer['handled'] else 0.0)
                if grade != receipt['native_task_utilities'][task]:
                    raise ValueError('The recorded per-task grade differs from the original benchmark scorer')
                rows.append({'source': key, 'dataset': dataset, 'view': task, 'grade': grade, 'handled': answer['handled']})
        comparable = [row for pair, row in baseline.items() if pair in expected]
        prior_utility = summarize(comparable, expected)['mother_macro']
        after_utility = summarize(rows, expected)['mother_macro']
        if prior_utility != summary['incumbent_native'] or after_utility != summary['candidate_native']:
            raise ValueError('The native report changed from the physically verified candidate pool')
        selected[dataset] = after_utility > prior_utility
        by_library[dataset] = {'incumbent': comparable, 'candidate': rows}
    if len(teachers) != 5 or len(executors) != 24:
        raise ValueError('Keep five actual teacher programs and 24 distinct original neural responses per comparison')
    return {'by_library': by_library, 'native_positive': selected, 'teacher_ids': teachers, 'executor_ids': executors,
            'conditions': digest(binding['matched_public_conditions']), 'terminal_sha256': sha(root / 'terminal.json')}


def lock_external():
    if LOCK.exists():
        print(json.dumps(read(LOCK)['ranking'], sort_keys=True))
        return
    parse_root = ROOT / read(PARSE)['artifact_root']
    parse_binding = read(parse_root / 'binding.json')
    receipt = read(HANDOFF / 'parse_complete_fixed20_ranking_receipt_20261118.json')
    parse = read(parse_root / 'external_ranking_input.json')
    if (digest(parse) != receipt['ranking_input_sha256']
            or parse['paired_terminal_sha256'] != sha(parse_root / 'terminal.json')):
        raise ValueError('The measured reversible-schema ranking input changed')
    ordinary = ROOT / parse_binding['ordinary_root']
    common, sources = read(ordinary / 'binding.json'), read(ordinary / 'train_sources.json')
    baseline = read(ordinary / 'incumbent_scores.json')
    if (digest(common) != parse_binding['ordinary_binding_sha256'] or digest(sources) != common['pilot_source_sha256']
            or digest(baseline) != common['native_incumbent_sha256']
            or any(source['project_split'] != 'train' for source in sources)):
        raise ValueError('Lock only on the original fixed TRAIN sources and common incumbent')
    roster_receipt = read(HANDOFF / 'sealed_source_roster_current.json')
    roster = read(ROOT / roster_receipt['artifact_root'] / 'binding.json')
    if digest(roster) != roster_receipt['roster_sha256'] or {source['key'] for source in sources} != {
            row['source'] for row in roster['fixed_pilot']}:
        raise ValueError('The comparison must use every original pilot mother')
    paths = ROOT / 'reports/legal_skill_convergence_20261117/protocol.json'
    protocol = read(paths)
    cohort = [{'source': source['key'], 'dataset': source['dataset']} for source in sources]
    views = {source['key']: [task['id'] for task in source['views']] for source in sources}
    ledger = ReadOnlyLedger()
    baseline_rows = _baseline_rows(sources, common, baseline)
    native = _compact_rows('ordinary', common, sources, baseline_rows, ledger)
    scope = _compact_rows('scope', common, sources, baseline_rows, ledger)
    attribution = ROOT / read(HANDOFF / 'compact_SCOPE_composition_attribution_20261118.json')['artifact_root']
    if read(attribution / 'binding.json')['SCOPE_terminal_sha256'] != scope['terminal_sha256']:
        raise ValueError('The scope attribution evidence must match the same measured programs')
    edits = ROOT / read(SCOPE_EDITS)['artifact_root']
    edit_binding, edit_terminal = read(edits / 'binding.json'), read(edits / 'terminal.json')
    if (edits.name != digest(edit_binding) or edit_terminal['status'] != 'completed'
            or edit_binding['scope_terminal_sha256'] != scope['terminal_sha256'] or edit_terminal['edited_tasks'] != 12):
        raise ValueError('The SCOPE contender requires completed matched source-edit validation')
    for candidate in ('incumbent', 'candidate'):
        measurement = read(edits / (candidate + '_measurement.json'))
        if measurement['program_sha256'] != digest(edit_binding['programs'][candidate]):
            raise ValueError('The legal edit validation must measure the same competing programs')
        scope['executor_ids'].update(call for row in measurement['source_rows'] for call in row['physical_call_ids'])
    if len(scope['executor_ids']) != 32:
        raise ValueError('Require both actual programs on all four edited variants')
    regressions = HANDOFF / 'external_same_read_pair_checks_20261118.json'
    if (any(native['native_positive'].values()) or read(regressions)['evidence']['eligible_audited_mothers'] != 2):
        raise ValueError('These matched validation controls require an independent audit for any positive update')
    scope_choices = {name: 'incumbent' for name in scope['by_library']}
    if {name for name, keep in scope['native_positive'].items() if keep} != {'MAUD'}:
        raise ValueError('Confirm the fixed positive shortlist before applying MAUD role regressions')
    scope_choices['MAUD'] = edit_terminal['MAUD_selection_after_edit']

    def candidate(name, measured, rows, gate):
        totals = _paid_usage(ledger, measured['teacher_ids'], measured['executor_ids'])
        return {'family': name, 'rows': deepcopy(rows), 'matched_public_conditions_sha256': measured['conditions'],
                'comparison_logical_tokens': sum(role['tokens'] for role in totals.values()),
                'actual_calls_and_tokens': totals, 'gate': gate}

    scope_rows = [row for dataset, choice in scope_choices.items() for row in scope['by_library'][dataset][choice]]
    candidates = [parse, candidate('SCOPE_style_skill_learning', scope, scope_rows,
                                  'retain a positive proposal if it passes matched role-name regression')]
    for family in ('SkillEvoReg_style_candidate_validation', 'Synedrion_style_HMT'):
        candidates.append(candidate(family, native, baseline_rows,
                                    'strict native-positive shortlist is empty on the matched candidate bank'))
    ranking = rank_external_pilot(candidates, cohort, views, protocol['study_scope']['external_eligible_families'])
    result = {'ranking': ranking, 'candidate_receipts_sha256': {r['family']: digest(r) for r in candidates},
              'pilot_source_sha256': digest(sources), 'protocol_sha256': sha(paths),
              'scope_legal_edit_terminal_sha256': sha(edits / 'terminal.json'),
              'scope_attribution_terminal_sha256': sha(attribution / 'terminal.json'),
              'audited_airline_selector_receipt_sha256': sha(regressions),
              'native_supervised_teacher_bank_sha256': native['terminal_sha256'],
              'same_bank_reused_for_candidate_validation_and_HMT': True,
              'conditional_validation_dispatched_for_native_positive_updates_only': True,
              'published_baseline_reproduction': False, 'formal_pilot_skills_preloaded': False, 'TEST_opened': False}
    immutable_json(LOCK, result)
    print(json.dumps(ranking, sort_keys=True), flush=True)


if __name__ == '__main__':
    lock_external()
