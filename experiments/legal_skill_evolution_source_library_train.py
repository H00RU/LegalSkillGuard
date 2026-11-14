"""C's source-learning branch of the existing mixed TRAIN continuation.

Reuse the completed source pass and inherited warm-start costs. The original
batch order is retained. A zero-loss first batch commits an unchanged library;
the first actual residual drives a normal paired source update. This entry does
not launch a new study, open TEST, or redefine source correctness as native score.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from experiments import legal_skill_evolution_five_train as parent
from experiments import legal_skill_evolution_source_local_update as previous
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs, unpack_programs, INSTRUCTION, PROGRAM_INSTRUCTION
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues, render_structured_codex_prompt, CODEX_TURN_INPUT_CHARACTER_LIMIT


ROOT = parent.ROOT
RUN = 'legal_skill_evolution_source_library_train_20261114'
OUT = ROOT / 'artifacts' / RUN
ARMS = previous.ARMS
read = parent.read
SYSTEM = '''Continue the actual cumulative legal source-acquisition libraries in
the original five-dataset TRAIN order. This branch handles the original
ContractNLI mothers. It is normal full-TRAIN learning, not a new task, synthetic
pilot or a claim of cold-start exposure. The prior paid8-mother libraries and
costs are inherited. Both arms see identical full current/past TRAIN sources,
lawful native supervision, both actual libraries, failures and partial review.

Learn useful source semantic distinctions/relations and executable composition;
do not memorize source IDs, company names, values or native answers. Use local
source_function_edits:[{name,code}] on YOUR actual current module, preserving
untouched functions. All helpers must exist in your current library or be
explicitly supplied as edits. Other-arm code is available but is not silently
imported: if reused, supply exact helpers and any missing unchanged types.

The common native consumer is frozen for the primary acquisition comparison.
decision_functions must be[]. All old constructors retain their meanings. The
teacher may acquire truly new source primitives, semantic reading operations,
their explicit scope contracts and planner functions when necessary; [] is
valid when pure source code suffices. A failed lexical match is not source
absence. Unread/unknown stays unresolved, not False, zero or a default answer.
Every actual semantic read is charged with the unchanged thinking-OFF executor.

For C, source functions acquire primitive source atoms. New complete legal
Norms must come through actual G composition, with typed source/role/action/
condition/exception scope and real joint source evidence. Retain valid prior
source-specific claims; do not turn a different contract into global law.
composition contains the complete relational language JSON, with every old rule
definition preserved unless a supplied actual error justifies its revision.
suggested_rule_ids is a proposal, not proof of a fitted G. Ordinary FreeUpdate
may use arbitrary pure source/composition code, direct Norms, every shared
concept/ontology, cached correct repair and the same raw-source capabilities.
Do not deliberately weaken it. Independent acquisition costs are retained.

Native labels are lawful training feedback but not source factual concepts.
Native accuracy does not certify source truth; source reviews are partial and
unreviewed fields are not negatives. In the current second-batch residual,
the source says 'employees OR contractors OF THE RECIPIENT' within its actual
permission. Current C gets only contractors; information ABOUT employees in a
different definition clause is not employee disclosure permission. Learn the
source-conditioned recipient distinction, not a company-specific string fix.
The same error and full material are supplied to the unrestricted control.

Keep old valid source abilities and uncertainty. Do not invent termination
where a source says only if requested, or invent a confidentiality qualification
to match a hypothesis. Keep current role, direction, material and event scopes.
Partial source reviews and all prior failed replacements remain supplied.
Do not rewrite the whole unrelated module. No imports, IO, nested functions,
lambdas, source/company-ID branches or native answer lookups. Return compact
valid pure function edits and the supplied architecture's normal schema.'''


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    original = parent.prepare()
    libraries = {
        'ConstraintAcquire': read(previous.OUT / 'unbound_proposed_execution/ConstraintAcquire/library.json'),
        'FreeUpdate': read(previous.OUT / 'unbound_control_reference_recovery/execution/library.json')}
    for arm, library in libraries.items():
        immutable_json(OUT / 'B0' / arm / 'library.json', library)
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/source_function_patch.py',
        ROOT / 'legal_skill_guard/skill_evolution/acquisition_proposal.py',
        ROOT / 'legal_skill_guard/skill_evolution/open_acquisition.py',
        ROOT / 'legal_skill_guard/skill_evolution/relational_learning.py']
    protocol = {'run_id': RUN, 'parent_five_dataset_run': parent.RUN, 'same_goal': True,
        'sources': [s for s in original['train_sources'] if s.startswith('ContractNLI:')],
        'mixed_batches': original['batches'], 'executor_profile': original['executor_profile'],
        'teacher_profile': original['teacher_profile'], 'source_sha256': {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'inherited_warmstart_sources': [t['source_id'] for t in read(previous.OUT / 'teacher_task.json')['tasks']],
        'same_information_unrestricted_control': True, 'thinking': False, 'TEST_opened': False,
        'cold_start_or_blind_claim': False, 'goal_complete': False}
    immutable_json(OUT / 'protocol.json', protocol)
    for path in files:
        target = OUT / 'source_snapshot' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    return protocol


def initial_from_current_pass(protocol, batch):
    """Reuse an exact already executed state; never relabel a fixed pass as evolution."""
    assert batch in (1, 2), 'Later batches need actual new libraries executed by the continuation'
    results = []
    for arm in ARMS:
        library = read(OUT / f'B{batch-1}' / arm / 'library.json')
        original = read(OUT / 'B0' / arm / 'library.json')
        assert digest(library) == digest(original), 'The old fixed pass cannot represent a changed library'
        for sid in protocol['mixed_batches'][batch-1]:
            if sid not in protocol['sources']:
                continue
            path = parent.OUT / 'source_pass' / arm / previous.old.name_for(sid)
            row = read(path)
            result = {'source': sid, 'arm': arm, 'batch': batch,
                'library_sha256': digest(library), 'actual': row,
                'reused_exact_execution_path': str(path.relative_to(ROOT)),
                'new_model_calls': 0, 'cold_start_or_blind_claim': False}
            immutable_json(OUT / f'B{batch}' / arm / 'initial' / previous.old.name_for(sid), result)
            results.append(result)
    immutable_json(OUT / f'B{batch}/initial.json', {'rows': results, 'new_model_calls': 0,
        'correct': {a: sum(r['actual']['correct'] for r in results if r['arm'] == a) for a in ARMS}})
    if batch == 1:
        assert all(r['actual']['correct'] == 4 and r['actual']['unresolved'] == 0 for r in results)
        for arm in ARMS:
            library = read(OUT / 'B0' / arm / 'library.json')
            immutable_json(OUT / 'B1' / arm / 'library.json', library)
        immutable_json(OUT / 'B1/update_receipt.json', {
            'operation': 'unchanged_library_no_observed_native_residual', 'new_teacher_calls': 0,
            'source_truth_not_certified_by_zero_native_loss': True,
            'C_selection_native_loss_lower_bound': 0, 'C_observed_native_loss': 0,
            'C_selection_edit_lower_bound': 0, 'C_observed_selection_edits': 0,
            'no_claim_of_new_source_or_G_update': True, 'goal_complete': False})
    return results


def make_task(protocol, batch=2):
    path = OUT / f'B{batch}/teacher_task.json'
    if path.exists():
        return read(path)
    assert batch == 2
    initial_from_current_pass(protocol, 1)
    initial_from_current_pass(protocol, 2)
    public = {s['key']: s for s in read(parent.PREPARED / 'public.json') if s['dataset'] == 'ContractNLI'}
    grading = read(parent.PREPARED / 'grading.json')
    current_ids = [k for k in protocol['mixed_batches'][batch-1] if k in public]
    history = list(dict.fromkeys(protocol['inherited_warmstart_sources'] + [
        k for b in protocol['mixed_batches'][:batch] for k in b if k in public]))
    libraries = {a: read(OUT / f'B{batch-1}' / a / 'library.json') for a in ARMS}
    tasks = []
    for sid in history:
        source = public[sid]
        upstream = read(parent.OUT / 'source_pass/upstream' / previous.old.name_for(sid))['source_output']
        actual = {}
        for arm in ARMS:
            row = read(parent.OUT / 'source_pass' / arm / previous.old.name_for(sid))
            if 'actual' not in row:
                actual[arm] = {'error': row.get('error'), 'correct': row['correct'], 'unresolved': row['unresolved']}
                continue
            value = row['actual']
            output = value['execution']['source_output']
            actual[arm] = {'statements': [r for r in output['statements'] if 'residual' not in r['term'][0]],
                'unresolved': output['unresolved'], 'native_feedback': value['feedback'],
                'correct': row['correct'], 'unresolved_views': row['unresolved']}
        units = read(parent.OUT / 'source_pass/ConstraintAcquire' / previous.old.name_for(sid))['observation']['visible_inputs']['units']
        tasks.append({'source_id': sid, 'current_batch': sid in current_ids,
            'full_source_text': source['views'][0]['public']['source_text'], 'source_units': units,
            'incoming_source_output': upstream, 'native_TRAIN_supervision': grading[sid], 'actual_current': actual})
    old_task = read(previous.OUT / 'teacher_task.json')
    task = {'batch': batch, 'current_sources': current_ids, 'tasks': tasks,
        'current_libraries': libraries, 'common_frozen_consumer': libraries['ConstraintAcquire']['spec']['decision_program'],
        'common_observed_signatures': old_task['common_observed_signatures'],
        'source_function_patch_code': old_task['source_function_patch_code'],
        'encoder_code': old_task['encoder_code'], 'observer_code': old_task['observer_code'],
        'prior_partial_source_reviews_and_failed_replacements': read(previous.old.OUT / 'teacher_task.json')['partial_source_diagnosis']
            if 'partial_source_diagnosis' in read(previous.old.OUT / 'teacher_task.json') else
            {'kept_in_existing_history': True, 'not_an_exhaustive_source_annotation': True},
        'actual_second_batch_diagnosis': {
            'source': next(k for k in current_ids if '78adf3' in k),
            'classification': 'source_recipient_concept_omission_not_unresolved_execution',
            'finding': 'Source clause5 permits employees OR contractors of the Recipient, with need-to-know and written confidentiality; current C emits only the contractor permission. Earlier employee words concern protected information, not permitted recipients.',
            'current_C_correct': 11, 'current_Free_correct': 10, 'views_per_arm': 12,
            'current_candidate_reachability_not_yet_a_full_representation_certificate': True},
        'source_function_updates_allowed_to_fix_actual_errors_not_only_this_phrase': True,
        'new_sources_or_synthetic_cases': 0, 'inherited_exposure_not_a_blind_new_split': True}
    assert unpack_programs(pack_programs(task)) == task
    immutable_json(path, task)
    return task


def acquire(protocol, arm=None):
    task = make_task(protocol)
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
    for selected in ARMS:
        if arm is not None and selected != arm:
            continue
        output = OUT / 'B2' / selected / 'teacher.json'
        if output.exists():
            continue
        system = SYSTEM + '\n' + (previous.old.C_PART + '\n' + previous.old.previous.prior.prior.C_SPEC
            if selected == 'ConstraintAcquire' else previous.old.FREE_PART)
        system += '\n' + INSTRUCTION + '\n' + PROGRAM_INSTRUCTION
        system += '\nAllowed attributes: ' + ','.join(sorted(previous.old.METHODS)) + '\nAllowed calls: ' + ','.join(sorted(previous.old.CALLS))
        schema = previous.schema_for(selected)
        assert not strict_output_schema_issues(schema)
        user = json.dumps(pack_programs(task), ensure_ascii=False, separators=(',', ':'))
        size = len(render_structured_codex_prompt(system, user))
        assert size <= CODEX_TURN_INPUT_CHARACTER_LIMIT
        immutable_json(output.with_name('preflight.json'), {'task_sha256': digest(task), 'characters': size,
            'schema_issues': [], 'source_only_serialized_duplication_omitted': True})
        result = FrozenTeacher(ledger, OUT, protocol['teacher_profile']).propose(RUN + ':B2:' + selected + ':update',
            source_ids=[t['source_id'] for t in task['tasks']], system_prompt=system, user_prompt=user, output_schema=schema)
        immutable_json(output, result)
        print(json.dumps({'batch': 2, 'arm': selected, 'source_library_update_saved': True}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['prepare', 'acquire'])
    parser.add_argument('--arm', choices=ARMS)
    args = parser.parse_args()
    protocol = prepare()
    for name, expected in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    if args.phase == 'prepare':
        task = make_task(protocol)
        print(json.dumps({'prepared_current_batch': 2, 'current_mothers': len(task['current_sources']),
            'inherited_or_seen_mothers': len(task['tasks']), 'B1_teacher_calls': 0, 'new_model_calls': 0}), flush=True)
    else:
        with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquire(protocol, args.arm)
