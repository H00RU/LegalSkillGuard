"""Obtain the missing source-only references for the original locked TRAIN128.

Reuse the32 original paid pilot annotations, including all failures/partial
scopes and their original role/provenance. Obtain one proposal per remaining
mother, in the already frozen eight-batch order. No candidate, executor or
DEV/TEST call occurs. Proposals require source review before scientific use.
"""
import argparse
import fcntl
import json
from pathlib import Path
import sqlite3

from experiments.two_method_annotate import SYSTEM, inputs, output_schema
from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from legal_skill_guard.inference.codex_cli_client import (
    CODEX_TURN_INPUT_CHARACTER_LIMIT, render_structured_codex_prompt, strict_output_schema_issues)
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.skill_evolution.clients import FrozenTeacher, GenerationHold
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.rr.checkpoint import immutable_json


LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
RUN_ID = 'two_method_train128_references_v1_20261117'


def ledger_connection():
    return sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True)


def prepare():
    source_path, pilot_path = BASE / 'prepared/source_lock.json', BASE / 'pilot_lock.json'
    sources, pilot = read(source_path), read(pilot_path)
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    public = read(public_path)
    train = {source['key']: source for source in public}
    batches = sources['training_batches']
    order = [key for batch in batches for key in batch]
    if (len(train) != 128 or len(batches) != 8 or len(order) != 128 or len(set(order)) != 128
            or set(order) != set(train) or set(order) != set(sources['sources']['train'])
            or sha(public_path) != sources['prepared_sha256']['train']['public']):
        raise ValueError('Reference acquisition must retain the original TRAIN128/eight batches')
    old_protocol_path = BASE / 'annotation_v1/protocol.json'
    old_protocol = read(old_protocol_path)
    if old_protocol['annotation_system'] != SYSTEM:
        raise ValueError('The source annotation system changed')
    if (pilot['executor'] != old_protocol['executor'] or pilot['teacher'] != old_protocol['teacher']
            or old_protocol['source_lock_sha256'] != sha(source_path)):
        raise ValueError('The original model/source binding changed')
    paths = [Path(__file__).relative_to(ROOT), 'experiments/two_method_annotate.py',
             'experiments/two_method_graph_corpus.py',
             'legal_skill_guard/paired_interfaces/graph_interface.py',
             'legal_skill_guard/inference/codex_cli_client.py',
             'legal_skill_guard/skill_evolution/clients.py',
             'legal_skill_guard/skill_evolution/ledger.py',
             'legal_skill_guard/skill_evolution/native.py',
             'legal_skill_guard/skill_evolution/objects.py',
             'legal_skill_guard/rr/ledger.py', 'legal_skill_guard/rr/checkpoint.py']
    bindings = {str(path): sha(ROOT / path) for path in paths}
    existing = {row['key']: row for row in pilot['rows']}
    inventory = []
    with ledger_connection() as db:
        for batch, keys in enumerate(batches, 1):
            for key in keys:
                source = train[key]
                task, mapping = inputs(source)
                schema = output_schema(task)
                if strict_output_schema_issues(schema):
                    raise ValueError('An annotation schema fails the original teacher contract')
                user = json.dumps(task, ensure_ascii=False, sort_keys=True)
                chars = len(render_structured_codex_prompt(SYSTEM, user))
                if chars > CODEX_TURN_INPUT_CHARACTER_LIMIT:
                    raise ValueError('A complete source exceeds the original teacher transport cap')
                row = {'source': key, 'dataset': source['dataset'], 'batch': batch,
                    'source_public_sha256': digest(source), 'task_sha256': digest(task),
                    'schema_sha256': digest(schema), 'teacher_prompt_characters': chars,
                    'views': len(task['views']), 'native_view_to_opaque_source_view': mapping,
                    'no_native_answers_or_questions_in_teacher_input': True}
                if key in existing:
                    folder = BASE / 'annotation_v1/proposed_references' / digest(key)
                    old_task, checks = read(folder / 'task.json'), read(folder / 'source_checks.json')
                    if old_task['task'] != task or not old_task['no_native_answers_or_questions']:
                        raise ValueError('An old paid annotation has a different source input')
                    identity = checks['physical_call_id']
                    physical = db.execute('select status,result from calls where id=?', (identity,)).fetchone()
                    if physical is None or physical[0] != 'completed':
                        raise ValueError('A cached pilot annotation is not physically settled')
                    result = json.loads(physical[1])
                    if digest(result['value']) != checks['proposed_value_sha256']:
                        raise ValueError('A cached annotation differs from its continuous ledger result')
                    row.update(acquisition='preserved_pilot_proposal', physical_call_id=identity,
                               original_pilot_role=existing[key]['role'],
                               original_task_path=str((folder / 'task.json').relative_to(ROOT)),
                               original_task_sha256=sha(folder / 'task.json'),
                               original_source_checks_path=str((folder / 'source_checks.json').relative_to(ROOT)),
                               original_source_checks_sha256=sha(folder / 'source_checks.json'))
                else:
                    row['acquisition'] = 'one_new_source_only_proposal'
                inventory.append(row)
    if sum(item['acquisition'] == 'preserved_pilot_proposal' for item in inventory) != 32:
        raise ValueError('All32 original pilot annotations must be preserved/reused')
    protocol = {'experiment': 'locked_TRAIN128_missing_source_reference_acquisition_v1',
        'run_id': RUN_ID, 'source_lock_sha256': sha(source_path), 'pilot_lock_sha256': sha(pilot_path),
        'public_TRAIN_sha256': sha(public_path), 'original_annotation_protocol_sha256': sha(old_protocol_path),
        'source_sha256': bindings, 'system_sha256': digest(SYSTEM), 'inventory': inventory,
        'teacher': old_protocol['teacher'], 'executor_not_called_profile': old_protocol['executor'],
        'teacher_executable_sha256': sha(Path(old_protocol['teacher']['executable'])),
        'fixed_total_train_mothers': 128, 'preserved_pilot_mothers': 32,
        'new_teacher_proposals_exactly_once_per_missing_mother': 96,
        'no_extra_sources_candidates_or_independent_trials': True,
        'outputs_are_unverified_source_proposals_not_gold': True,
        'all_arms_receive_the_same_source_reference_pool_after_review': True,
        'no_native_grading_input_or_DEV_TEST_teacher_access': True,
        'no_formal_training_or_evaluation_completion_claim': True,
        'no_implicit_retry_or_failed_identity_redispatch': True}
    out = BASE / 'train128_references_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    for path in paths:
        dest = out / 'source_snapshot' / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / path).read_bytes()
        if dest.exists() and dest.read_bytes() != raw:
            raise ValueError('An immutable source snapshot changed')
        if not dest.exists():
            dest.write_bytes(raw)
    for row in inventory:
        if row['acquisition'] != 'one_new_source_only_proposal':
            continue
        task, mapping = inputs(train[row['source']])
        metadata = {'source': row['source'], 'batch': row['batch'], 'role': 'formal_train_reference',
                    'task': task, 'native_view_to_opaque_source_view': mapping,
                    'no_native_answers_or_questions': True, 'reference_ready': False,
                    'source_public_sha256': row['source_public_sha256'],
                    'output_schema': output_schema(task), 'system_sha256': digest(SYSTEM)}
        immutable_json(out / 'proposed_references' / digest(row['source']) / 'task.json', metadata)
    return out, protocol, sources


def run(stop_after):
    out, protocol, sources = prepare()
    lock = (out / 'driver.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for name, expected in protocol['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('A bound reference acquisition source changed: ' + name)
    with ledger_connection() as db:
        if db.execute("select count(*) from calls where status='reserved'").fetchone()[0]:
            raise ValueError('An existing physical request must settle before dispatch')
    ledger = EvolutionLedger(LEDGER, run_id=RUN_ID, sources=sources['sources'],
        binding={'phase': 'missing_TRAIN128_source_reference_acquisition', 'protocol_sha256': sha(out / 'protocol.json')})
    teacher = FrozenTeacher(ledger, out, protocol['teacher'])
    attempted = 0
    for row in protocol['inventory']:
        if row['acquisition'] != 'one_new_source_only_proposal':
            continue
        folder = out / 'proposed_references' / digest(row['source'])
        checks_path = folder / 'source_checks.json'
        if checks_path.exists():
            continue
        metadata = read(folder / 'task.json')
        identity = RUN_ID + ':source:' + digest(metadata)
        with ledger_connection() as db:
            old = db.execute('select status from calls where id=?', (identity,)).fetchone()
        if old and old[0] == 'failed':
            immutable_json(checks_path, {'source': row['source'], 'physical_call_id': identity,
                'status': 'previous_physical_failure_retained', 'reference_ready': False,
                'source_semantic_truth_verified': False, 'failed_identity_not_redispatched': True})
            continue
        print(json.dumps({'event': 'teacher_dispatch', 'source': row['source'], 'batch': row['batch'],
                          'call_id': identity, 'artifact_root': str(out.relative_to(ROOT))}), flush=True)
        try:
            response = teacher.propose(identity, source_ids=[row['source']], system_prompt=SYSTEM,
                user_prompt=json.dumps(metadata['task'], ensure_ascii=False, sort_keys=True),
                output_schema=metadata['output_schema'])
        except GenerationHold:
            raise
        except Exception as error:
            immutable_json(checks_path, {'source': row['source'], 'physical_call_id': identity,
                'status': 'physical_failure', 'error': type(error).__name__ + ': ' + str(error),
                'reference_ready': False, 'source_semantic_truth_verified': False})
            raise  # A service/resource fault is not permission to repeat96 failing calls.
        value = response['value']
        expected = {view['view_id']: view['source_units'] for view in metadata['task']['views']}
        seen, checks, errors = set(), {}, []
        for view in value['views']:
            key = view['view_id']
            if key not in expected or key in seen:
                errors.append('Unexpected or duplicate opaque source view: ' + key)
                continue
            seen.add(key)
            try:
                checks[key] = gi.validate(view['graph'], expected[key])
            except (ValueError, KeyError) as error:
                errors.append(key + ': ' + str(error))
        if seen != set(expected):
            errors.append('Missing supplied source views')
        immutable_json(folder / 'proposal.json', {'physical_call_id': identity, 'value': value})
        immutable_json(checks_path, {'source': row['source'], 'batch': row['batch'],
            'role': 'formal_train_reference', 'physical_call_id': identity,
            'checks': checks, 'errors': errors, 'proposed_value_sha256': digest(value),
            'source_semantic_truth_verified': False, 'reference_ready': False,
            'requires_source_review_before_scientific_use': True,
            'independent_human_annotation_claimed': False})
        print(json.dumps({'event': 'teacher_settled', 'source': row['source'],
                          'batch': row['batch'], 'span_checks_passed': not errors,
                          'reference_ready': False, 'new_candidates': 0}), flush=True)
        attempted += 1
        if stop_after is not None and attempted >= stop_after:
            return
    with ledger_connection() as db:
        counts = db.execute('select status,count(*) from calls where id like ? group by status', (RUN_ID + ':%',)).fetchall()
    immutable_json(out / 'terminal.json', {'status': 'fixed_source_proposal_schedule_settled',
        'new_phase_physical_request_counts': counts, 'original_pilot_proposals_reused': 32,
        'reference_truth_certified': False, 'formal_training_DEV_TEST_or_goal_complete': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--stop-after', type=int)
    args = parser.parse_args()
    if args.stop_after is not None and args.stop_after < 1:
        parser.error('--stop-after must be positive')
    if args.prepare:
        out, protocol, _ = prepare()
        print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), 'fixed_train_mothers': 128,
            'reused_pilot_proposals': 32, 'new_source_proposals': 96,
            'max_teacher_prompt_characters': max(row['teacher_prompt_characters'] for row in protocol['inventory']),
            'reference_ready_from_span_checks_alone': False, 'model_requests': 0}))
    else:
        run(args.stop_after)
