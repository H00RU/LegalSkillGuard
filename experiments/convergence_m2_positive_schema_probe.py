"""Test M2 on the already measured native-positive OpenExempt pilot candidate."""

import argparse
import json
import math
import sqlite3

from experiments.convergence_formal_b1_primary import _eligible
from experiments.convergence_lock_external_pilot import LOCK, _baseline_rows
from experiments.convergence_m2_update_probe import POINTER as PRIOR_NATURAL, measure_natural_projection
from experiments.convergence_parse_pilot import POINTER as PARSE
from experiments.convergence_parse_runtime import EXTERNAL_ARM, ParseControlActor
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_shared_dev_checkpoint import ReadOnlyLedger
from legal_skill_guard.paired_interfaces.convergence_actors import common_cells
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.paired_interfaces.shared_semantics_validation import validate_patch
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


DATASET = 'OpenExempt'
POINTER = HANDOFF / 'm2_positive_schema_probe_current.json'


def _bank(parse_root, pilot_root):
    previous = read(parse_root / 'binding.json')
    ordinary = ROOT / previous['ordinary_root']
    common = read(ordinary / 'binding.json')
    sources = read(ordinary / 'train_sources.json')
    baseline_scores = read(ordinary / 'incumbent_scores.json')
    if (digest(sources) != common['pilot_source_sha256'] or digest(common) != previous['ordinary_binding_sha256']
            or digest(baseline_scores) != common['native_incumbent_sha256']
            or any(source['project_split'] != 'train' for source in sources)):
        raise ValueError('Reuse exactly the fixed pilot TRAIN cohort and verified original grades')
    cohort = [source for source in sources if source['dataset'] == DATASET]
    if len(cohort) != 4:
        raise ValueError('The locked OpenExempt pilot must contain four mothers')
    original = _baseline_rows(sources, common, baseline_scores)
    report = read(parse_root / 'measured_libraries' / (DATASET + '.json'))
    proposal = report['compiled_proposal']
    library = sealed({'arm': EXTERNAL_ARM, 'batch': 1, 'schema_proposals': {DATASET: proposal}}, 'snapshot_sha256')
    reader = FrozenExecutor(ReadOnlyLedger(), parse_root, previous['executor'])
    actor = ParseControlActor(None, reader, parse_root)
    saved = {}
    for path in (parse_root / 'schema_control_reads').glob('*/result.json'):
        row = read(path)
        if row['proposal_sha256'] == digest(proposal):
            if row['source_sha256'] in saved:
                raise ValueError('The candidate bank contains more than one response for a fixed wire')
            saved[row['source_sha256']] = row
    path = common['grading_paths'][DATASET]
    if sha(ROOT / path) != common['grading_file_sha256'][path]:
        raise ValueError('The original native TRAIN scoring changed')
    grades = read(ROOT / path)
    native_pairs, predictions = [], {}
    for source in cohort:
        key = source['key']
        selected = [saved[digest(cell)] for cell in common_cells(source)]
        native = {view: value for row in selected for view, value in row['native'].items()}
        actor.verify_saved(source, library, 'skill_actor', {'native': native, 'schema_reads': selected,
            'schema_library_sha256': library['snapshot_sha256'], 'fallback_executed': False})
        predictions[key] = selected
        before = [row['grade'] for row in original if row['source'] == key]
        after = [grade_view(DATASET, task, grades[key][task['id']], native[task['id']]['answer'])['grade']
                 if native[task['id']]['handled'] else 0.0 for task in source['views']]
        native_pairs.append({'source': key, 'baseline_utility': math.fsum(before) / len(before),
                             'patch_utility': math.fsum(after) / len(after)})
    if (digest(predictions) != report['actual_predictions_sha256']
            or math.fsum(pair['patch_utility'] - pair['baseline_utility'] for pair in native_pairs) <= 0):
        raise ValueError('This follow-up needs a physically verified native-positive candidate')
    incumbent = read(pilot_root / 'binding.json')['program']
    return cohort, native_pairs, incumbent, proposal


def prepare():
    parse_root = ROOT / read(PARSE)['artifact_root']
    binding = read(parse_root / 'binding.json')
    if (read(parse_root / 'terminal.json')['status'] != 'completed'
            or read(LOCK)['ranking']['selected_family'] != binding['family'] or read(LOCK)['TEST_opened']):
        raise ValueError('Use the single settled ranking and the already measured positive candidate')
    pilot = ROOT / read(HANDOFF / 'pilot_b0_current.json')['artifact_root']
    old = ROOT / read(PRIOR_NATURAL)['artifact_root']
    cohort, rows, incumbent, proposal = _bank(parse_root, pilot)
    mother, group = _eligible({source['key'] for source in cohort})
    if group is None or read(old / 'terminal.json')['status'] != 'completed':
        raise ValueError('Use the independently audited natural group from this same fixed pilot')
    files = set(binding['source_sha256']) | set(read(old / 'binding.json')['source_sha256']) | {
        'experiments/convergence_m2_positive_schema_probe.py', 'experiments/convergence_parse_runtime.py',
        'experiments/convergence_formal_b1_primary.py', 'experiments/convergence_lock_external_pilot.py'}
    spec = {'study': 'M2_natural_ownership_same_native_positive_fixed20_subcohort',
            'parse_root': str(parse_root.relative_to(ROOT)), 'pilot_root': str(pilot.relative_to(ROOT)),
            'group_mother': mother['key'], 'group_public_sha256': digest([case.public for case in group['cases']]),
            'frozen_profile': binding['executor'], 'lock_sha256': sha(LOCK),
            'native_pairs_sha256': digest(rows), 'incumbent_sha256': digest(incumbent), 'candidate_sha256': digest(proposal),
            'previous_evidence': {str(stage.relative_to(ROOT)): sha(stage / 'terminal.json') for stage in (parse_root, pilot, old)},
            'source_sha256': {path: sha(ROOT / path) for path in sorted(files)},
            'native_wire_unchanged_for_scoring': True, 'relay_existing_reader_guidance_only': True}
    out = BASE / 'm2_positive_schema_probe' / digest(spec)
    immutable_json(out / 'binding.json', spec)
    immutable_json(out / 'native_pairs.json', rows)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'fixed_TRAIN_mothers': len(cohort),
                           'new_teacher_requests': 0, 'max_new_projection_reads': 4}, POINTER)
    print(json.dumps(read(POINTER), sort_keys=True), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(POINTER), sort_keys=True), flush=True)
        return
    binding = read(out / 'binding.json')
    cohort, native, incumbent, proposal = _bank(ROOT / binding['parse_root'], ROOT / binding['pilot_root'])
    keys = [source['key'] for source in cohort]
    mother, group = _eligible(set(keys))
    cases = group['cases']
    if (out.name != digest(binding) or sha(LOCK) != binding['lock_sha256']
            or mother['key'] != binding['group_mother'] or digest([case.public for case in cases]) != binding['group_public_sha256']
            or digest(native) != binding['native_pairs_sha256'] or digest(incumbent) != binding['incumbent_sha256']
            or digest(proposal) != binding['candidate_sha256']
            or any(sha(ROOT / file) != expected for file, expected in binding['source_sha256'].items())
            or any(sha(ROOT / path / 'terminal.json') != expected for path, expected in binding['previous_evidence'].items())):
        raise ValueError('The fixed paired native scoring evidence, source group or reader changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Settle the other study job first')
    run_id = 'convergence-M2-positive-PARSE-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    executor = FrozenExecutor(ledger, out, binding['frozen_profile'])
    executor.exact_replay_roots = [ROOT / path for path in binding['previous_evidence']]
    executor.readiness()
    programs = {'incumbent': incumbent, 'candidate': {'predicates': [{'prompt': proposal['reader_guidance']}]}}
    measurements = {}
    for name, program in programs.items():
        write_status(out, {'status': 'running', 'reader': name}, POINTER)
        measurements[name] = [measure_natural_projection(executor, out, program, case) for case in cases]
    patch = digest(proposal)
    paired = measurements['candidate']
    rows = {case.source_id: row for case, row in zip(cases, paired, strict=True)}
    audit = validate_patch(group['theory'], patch, [{
        'cases': cases, 'outputs': [row[0] for row in paired], 'physical_call_ids': [row[1] for row in paired],
        'literal_assertion_fields': ('ownership', 'stated_value'),
    }], native, visible_train=keys,
        verify_projection=lambda version, physical, case, output: version == patch and rows.get(case.source_id) == (output, physical),
        verify_native_pair=lambda version, row: version == patch and row in native)
    gate, = audit['matched_controls']
    supported = gate['asserted_outputs_present'] and not gate['unsupported_literal_assertions']
    choices = {'native_only': 'candidate',
               'single_witness': 'candidate' if supported and gate['single_witness_compatible'] else 'incumbent',
               'independent': 'candidate' if supported and gate['independent_per_case_compatible'] else 'incumbent',
               'shared': 'candidate' if audit['status'] == 'eligible_train_update' else 'incumbent'}
    with ledger.transaction() as db:
        physical = db.execute('select status,result from calls where id like ?', (run_id + ':%',)).fetchall()
    if any(status != 'completed' for status, _ in physical):
        raise ValueError('The natural projection reads have not settled')
    result = {'status': 'completed_M2_native_positive_candidate_probe', 'choices': choices, 'validation': audit,
              'paired_projections': measurements, 'physical_executor_calls': len(physical),
              'executor_tokens': sum(json.loads(raw)['usage']['total_tokens'] for _, raw in physical),
              'new_native_requests': 0, 'new_teacher_requests': 0, 'formal_B2_update_mutated': False, 'TEST_opened': False}
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'choices': choices, 'new_projection_reads': len(physical)}, POINTER)
    print(json.dumps(read(POINTER), sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
