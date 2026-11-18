"""Compare a sealed B4 candidate and incumbent on the same natural title edits."""

import argparse
import json
import math
import sqlite3

import jsonschema

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import M2, OE, ORDINARY, _group, pointer as fit_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_oe_title_value import (
    LITERAL_FIELDS, SCHEMA, SYSTEM, compile_title_value, decode_observation, selections,
)
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.shared_semantics_validation import validate_patch
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'm2_oe_title_value_current.json'
FAILURE = HANDOFF / 'B4_OE_projection_contract_audit_20261118.json'


def _materials():
    stage = ROOT / read(fit_pointer(4))['artifact_root']
    binding, terminal = (read(stage / name) for name in ('binding.json', 'terminal.json'))
    checkpoint = ROOT / binding['checkpoint_root']
    study = read(checkpoint / 'binding.json')
    failure = read(FAILURE)
    if (digest(binding) != stage.name or digest(study) != binding['study_binding_sha256']
            or terminal['status'] != 'completed_all_five_TRAIN_updates' or terminal['batch'] != 4
            or terminal['TEST_opened'] or failure['stage'] != stage.name
            or failure['terminal_sha256'] != sha(stage / 'terminal.json')
            or failure['observed_false_ownership_and_missing_visible_amount_count'] != 2):
        raise ValueError('Use the sealed B4 update and the two observed transport failures')
    batches = load_roster(study)
    visible = [source for batch in batches[:4] for source in batch]
    natural, _ = _group(visible)
    group = compile_title_value(natural)
    pilot_file = ROOT / read(HANDOFF / 'source_audit_current.json')['artifact_root'] / 'pilot20.json'
    pilot = read(pilot_file)
    root, = {case.root_id for case in group['cases']}
    if len(pilot) != 20 or root not in {row['source'] for row in pilot if row['dataset'] == OE}:
        raise ValueError('Projection reads are restricted to the original fixed pilot and its lawful edits')
    journal = TrainingJournal(checkpoint, study, batches)
    entering = journal._completed_batch(M2, 3)
    finished = journal._completed_batch(M2, 4)
    decisions = read(stage / 'matched_decisions.json')
    old_decision = decisions['relation'][OE]
    candidate = read(stage / 'candidates' / ORDINARY / OE / 'measurements.json')['candidate']
    incumbent = journal.library(M2, 3)['programs'][OE]
    native = old_decision['native_comparisons']
    if (entering != read(ROOT / binding['observations_root'] / 'binding.json')['entering_history'][M2]
            or terminal['arm_receipts'][M2] != finished['completed_batch_sha256']
            or digest(decisions) != terminal['matched_decisions_sha256']
            or digest(candidate) != old_decision['patch_sha256'] or digest(candidate) != failure['candidate_sha256']
            or [case.source_id for case in group['cases']] != old_decision['matched_controls'][0]['source_ids']
            or {row['source'] for row in native} != {source['key'] for source in batches[3] if source['dataset'] == OE}
            or math.fsum(row['patch_utility'] - row['baseline_utility'] for row in native) <= 0):
        raise ValueError('Use the previously measured native-positive pair and the same two source variants')
    return stage, binding, root, group, {'incumbent': incumbent, 'candidate': candidate}, native, visible, sha(pilot_file)


def _spec(materials):
    stage, binding, root, group, programs, native, visible, pilot = materials
    paths = set(binding['source_sha256']) | {
        'experiments/convergence_oe_title_value_probe.py',
        'legal_skill_guard/paired_interfaces/convergence_oe_title_value.py',
        'experiments/convergence_oe_natural_relation.py',
        'legal_skill_guard/paired_interfaces/shared_semantics.py',
        'legal_skill_guard/paired_interfaces/shared_semantics_validation.py',
    }
    return {'study': 'B4_existing_native_pair_natural_OE_title_filtered_value', 'stage': str(stage.relative_to(ROOT)),
            'B4_terminal_sha256': sha(stage / 'terminal.json'), 'prior_failure_sha256': sha(FAILURE),
            'executor': binding['executor'], 'pilot_sha256': pilot, 'pilot_root_source': root,
            'visible_TRAIN_hash': digest([row['key'] for row in visible]), 'B4_native_comparisons_sha256': digest(native),
            'programs_sha256': {name: digest(program) for name, program in programs.items()},
            'group_sha256': digest({'sources': [case.public for case in group['cases']], 'anchors': group['anchors'],
                                    'reference': group['theory'].reference_sha256,
                                    'shared': group['shared']['signatures'], 'independent': group['independent']['signatures']}),
            'reader_sha256': digest({'system': SYSTEM, 'schema': SCHEMA}),
            'source_sha256': {path: sha(ROOT / path) for path in sorted(paths)}}


def prepare():
    materials = _materials()
    spec = _spec(materials)
    out = BASE / 'm2_oe_title_value' / digest(spec)
    immutable_json(out / 'binding.json', spec)
    immutable_json(out / 'B4_native_comparisons.json', {'pairs': materials[5]})
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'projection_reads': 4, 'new_TRAIN_native_requests': 0,
                           'original_shared_signatures': 2, 'independent_signatures': 4}, POINTER)
    print(json.dumps(read(POINTER), sort_keys=True), flush=True)


def _measure(reader, out, program, group, arm):
    policy = '\n'.join(predicate['prompt'] for predicate in program['predicates'])
    rows = []
    for case, anchor in zip(group['cases'], group['anchors'], strict=True):
        messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': json.dumps(
            {'source': case.public['text'], 'named_asset': case.public['asset'], 'quoted_reader_policy': policy},
            ensure_ascii=False, sort_keys=True)}]
        identity = reader.ledger.run_id + ':title-value:' + digest([case.source_id, messages, SCHEMA])
        raw = reader.generate(identity, source=case.root_id, purpose='skill_actor', messages=messages,
                              schema=SCHEMA, thinking=False)
        verify_physical_response(reader, identity=identity, source=case.root_id, purpose='skill_actor',
                                 content_sha256=digest(raw['content']), usage=raw['usage'], finish_reason=raw['finish_reason'])
        try:
            value, anchored = decode_observation(raw, case, anchor)
            failure = None
        except (ValueError, jsonschema.ValidationError) as error:
            value, anchored, failure = None, False, type(error).__name__
        row = {'case': case.source_id, 'source_sha256': digest(case.public), 'arm': arm,
               'physical_call_id': identity, 'value': value, 'anchored': anchored, 'failure': failure}
        immutable_json(out / 'projection_reads' / (digest([arm, identity]) + '.json'), row)
        rows.append(row)
    return rows


def _validate(program, group, rows, native, visible):
    version = digest(program)
    indexed = {row['case']: row for row in rows}
    return validate_patch(group['theory'], version, [{
        'cases': group['cases'], 'outputs': [row['value'] for row in rows],
        'physical_call_ids': [row['physical_call_id'] for row in rows], 'literal_assertion_fields': LITERAL_FIELDS,
    }], native, visible_train=[row['key'] for row in visible], verify_projection=lambda patch, physical, case, value:
        patch == version and indexed[case.source_id]['source_sha256'] == digest(case.public)
        and (indexed[case.source_id]['physical_call_id'], indexed[case.source_id]['value']) == (physical, value),
        verify_native_pair=lambda patch, row: patch == version and row in native)


def run():
    materials = _materials()
    _, _, root, group, programs, native, visible, _ = materials
    binding = _spec(materials)
    out = ROOT / read(POINTER)['artifact_root']
    if out.name != digest(binding) or read(out / 'binding.json') != binding:
        raise ValueError('The exact B4 evidence, new projection or source binding changed')
    if (out / 'terminal.json').exists():
        print(json.dumps(read(POINTER), sort_keys=True), flush=True)
        return
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Settle the active research request before dispatching')
    run_id = 'convergence-M2-OE-title-value-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={'train': [root], 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.readiness()
    measured = {}
    for arm, program in programs.items():
        write_status(out, {'status': 'running', 'arm': arm}, POINTER)
        measured[arm] = _measure(reader, out, program, group, arm)
    neutral_native = [{**pair, 'patch_utility': pair['baseline_utility']} for pair in native]
    evaluations = {arm: _validate(program, group, measured[arm], native if arm == 'candidate' else neutral_native, visible)
                   for arm, program in programs.items()}
    diagnostics = {arm: selections(group, rows, evaluations[arm]['native_utility_sum_delta'] > 0, evaluations[arm])
                   for arm, rows in measured.items()}
    with ledger.transaction() as db:
        physical = db.execute('select status,result from calls where id like ?', (run_id + ':%',)).fetchall()
    if len(physical) != 4 or any(status != 'completed' for status, _ in physical):
        raise ValueError('The paired probe requires four distinct settled physical responses')
    terminal = {'status': 'completed_M2_natural_title_value_probe', 'measured': measured,
                'relation_validation': evaluations, 'diagnostics': diagnostics, 'executor_calls': len(physical),
                'executor_tokens': sum(json.loads(raw)['usage']['total_tokens'] for _, raw in physical),
                'new_native_requests': 0, 'new_teacher_requests': 0, 'formal_updates_changed': False,
                'TEST_opened': False, 'prior_B4_native_results_reused': True}
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'executor_calls': len(physical), 'diagnostics': diagnostics}, POINTER)
    print(json.dumps(read(POINTER), sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
