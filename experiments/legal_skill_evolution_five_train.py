"""Current five-dataset TRAIN continuation: fixed data, explicit method routing.

Preparation never generates, opens TEST or launches the retired Lift/CoRev
study. The source pass extends the actually acquired C/control programs to all
24 original ContractNLI TRAIN mothers; the previously executed eight are reused.
It is one part of the full mixed run, not a claim that all five have trained.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import tarfile
import traceback

from experiments import legal_skill_evolution_native_execution_reuse as native
from experiments import legal_skill_evolution_source_local_preview as source
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.scoped_source_program import run_source
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units


ROOT = Path(__file__).resolve().parents[1]
RUN = 'legal_skill_evolution_five_train_20261114'
OUT = ROOT / 'artifacts' / RUN
PREPARED = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train'
MANIFEST = ROOT / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json'
read = lambda p: json.loads(Path(p).read_text())


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    if (OUT / 'protocol.json').exists():
        protocol = read(OUT / 'protocol.json')
        for name, expected in protocol['fixed_input_hashes'].items():
            assert file_hash(ROOT / name) == expected, name
        return protocol
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        before = db.execute('select * from calls order by id').fetchall()
    assert not any(r[6] == 'reserved' for r in before)
    public = read(PREPARED / 'public.json')
    grading = read(PREPARED / 'grading.json')
    manifest = read(MANIFEST)
    batches = [[r['source_key'] for r in b['sources']] for b in manifest['source_sequence']]
    order = [key for batch in batches for key in batch]
    assert len(batches) == 8 and all(len(batch) == 16 for batch in batches)
    assert len(order) == len(set(order)) == len(public) == 128
    assert set(order) == {s['key'] for s in public} == set(grading)
    assert all(s['split'] == 'train' for s in public)
    expected = {'OpenExempt': 32, 'SARA_v2_Binary': 24, 'ContractNLI': 24, 'RuleArena_Airline': 24, 'MAUD': 24}
    assert dict(Counter(s['dataset'] for s in public)) == expected
    assert sum(len(s['views']) for s in public) == 280
    for batch in batches:
        assert dict(Counter(k.split(':')[0] for k in batch)) == {
            'OpenExempt': 4, 'SARA_v2_Binary': 3, 'ContractNLI': 3, 'RuleArena_Airline': 3, 'MAUD': 3}
    old_native = read(native.OUT / 'protocol.json')
    kernels, corrected, receipts = [], [], []
    # Only original TRAIN query directives are retained; formal case facts and
    # expected polarity are not copied to any actor-facing record.
    template = read(native.OUT / 'kernel_bank.json')[0]
    with tarfile.open('/tmp/lsg_sara_v2_native_archive_20261114.tar.gz') as archive:
        for record in public:
            if record['dataset'] != 'SARA_v2_Binary':
                continue
            original_id = grading[record['key']]['native']['original_id']
            body = archive.extractfile('sara_v2/cases/' + original_id + '.pl').read()
            query = native.parse_query(body.decode().split('% Test', 1)[1])
            kernel = deepcopy(template)
            family = '+'.join(call['predicate'] for call in query)
            kernel.update(name=family, query_clause=family, native_query=query)
            kernels.append({'source': record['key'], 'kernel': kernel})
            from legal_skill_guard.skill_evolution.sara_statute_kernel import query_term
            display = ', '.join(query_term(call) for call in query)
            view = deepcopy(record)
            view['views'][0]['public']['question'] += '\nNative query constraints from this same original TRAIN task (truth value not supplied): ' + display + '.'
            corrected.append(view)
            receipts.append({'source': record['key'], 'original_member_sha256': hashlib.sha256(body).hexdigest(),
                'native_query_without_polarity': query, 'formal_case_facts_copied': False, 'native_answer_copied': False})
    assert len(kernels) == len(corrected) == 24
    immutable_json(OUT / 'TRAIN_source_sequence.json', batches)
    immutable_json(OUT / 'SARA_native_kernel_bank.json', kernels)
    immutable_json(OUT / 'SARA_corrected_TRAIN_views.json', corrected)
    immutable_json(OUT / 'SARA_query_restoration_receipts.json', receipts)
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'user_authorized_full_five_TRAIN_20261114': True,
        'stage': 'integration_and_initial_source_pass', 'full_training_finished': False,
        'train_sources': order, 'batches': batches, 'dataset_mothers': expected, 'views': 280,
        'batch_size_mothers': 16, 'batches_count': 8,
        'new_sources_seeds_or_model_configuration': False,
        'fixed_input_hashes': {str(p.relative_to(ROOT)): file_hash(p) for p in (MANIFEST, PREPARED / 'public.json', PREPARED / 'grading.json')},
        'SARA_kernel_bank_sha256': digest(kernels), 'executor_profile': old_native['executor_profile'],
        'teacher_profile': old_native['teacher_profile'], 'thinking': False,
        'TEST_opened': False, 'DEV_labels_used_to_update': False,
        'prior_TRAIN_exposure_preserved_and_not_a_new_blind_experiment': True,
        'required_comparisons': {
            'C': 'Learned source representation and shared composition, with independent strong acquisition and source/G interventions.',
            'observation_learning': 'Error-updated observation representation/conversion versus generic representation AND ordinary same-information teacher; subsequent cases are logged separately from development.',
            'residual_reading': 'Same frozen observation contract, kernel, initial observation and request opportunity; actual residual-guided read versus ordinary reread; no outcome-guided eligibility.',
            'novelty': 'Track concrete learned/update mechanism and actual reusable code paths against prior work; winning the two comparisons is not by itself novelty.'},
        'remaining_integration': ['batchwise C update/selection', 'all-family observation contract learning and replay',
            'same-contract residual/ordinary read dispatch', 'shared remaining three dataset routes and common exposure/cost audit'],
        'ledger_before': len(before), 'new_model_requests_for_preparation': 0}
    immutable_json(OUT / 'protocol.json', protocol)
    print(json.dumps({'prepared': RUN, 'mothers': 128, 'views': 280, 'batches': 8,
        'SARA_native_interfaces': 24, 'new_model_calls': 0, 'full_training_finished': False}), flush=True)
    return protocol


def source_pass(protocol):
    public = {s['key']: s for s in read(PREPARED / 'public.json')}
    grading = read(PREPARED / 'grading.json')
    current = source.current
    libraries = {
        'ConstraintAcquire': read(current.OUT / 'unbound_proposed_execution/ConstraintAcquire/library.json'),
        'FreeUpdate': read(current.OUT / 'unbound_control_reference_recovery/execution/library.json')}
    previous = {
        'ConstraintAcquire': current.OUT / 'unbound_proposed_execution/ConstraintAcquire',
        'FreeUpdate': current.OUT / 'unbound_control_reference_recovery/execution'}
    parent = current.old.previous.PARENT
    base, grammar = read(parent / 'base.json'), read(parent / 'grammar.json')
    summaries = []
    for batch_index, batch in enumerate(protocol['batches'], 1):
        for key in batch:
            if public[key]['dataset'] != 'ContractNLI':
                continue
            source_record = public[key]
            pub = source_record['views'][0]['public']
            units, _ = execution_source_units(pub['source_text'], source_spans(material_public(pub)))
            upstream_file = OUT / 'source_pass/upstream' / current.old.name_for(key)
            if upstream_file.exists():
                upstream = read(upstream_file)['source_output']
            else:
                old_upstream = current.old.OUT / 'upstream' / current.old.name_for(key)
                if old_upstream.exists():
                    upstream = read(old_upstream)['source_output']
                else:
                    interpretation, event = run_source(base['source_program'], base['grammar'], grammar, source_record)
                    upstream = interpretation['source_program_output']
                immutable_json(upstream_file, {'source_output': upstream, 'new_model_calls': 0})
            for arm, library in libraries.items():
                target = OUT / 'source_pass' / arm / current.old.name_for(key)
                if target.exists():
                    row = read(target)
                else:
                    old_result = previous[arm] / current.old.name_for(key)
                    if old_result.exists():
                        actual = read(old_result)
                        row = {**actual, 'reused_exact_prior_execution': str(old_result.relative_to(ROOT)),
                               'same_library_sha256': digest(library)}
                    else:
                        try:
                            observation = current.old.observe(source.NoModel(), RUN + ':' + arm + ':' + key, key, library,
                                source_text=pub['source_text'], units=units, source_output=upstream)
                            assert observation['new_model_requests'] == 0
                            # Preserve the primary execution before touching lawful TRAIN scores.
                            unscored = current.old.previous.prior.prior.evaluate_source(library, observation, source_record, None)
                            immutable_json(target.with_name(target.stem + '_primary.json'), {
                                'source': key, 'arm': arm, 'observation': observation, 'unscored': unscored})
                            actual = current.old.previous.prior.prior.evaluate_source(library, observation, source_record, grading[key])
                            row = {'source': key, 'arm': arm, 'observation': observation, 'actual': actual,
                                'correct': sum(bool(v['score'] and v['score']['correct']) for v in actual['feedback']['views']),
                                'unresolved': len(source_record['views']) - sum(v['core_executed'] for v in actual['feedback']['views'])}
                        except Exception as error:
                            row = {'source': key, 'arm': arm, 'correct': 0, 'unresolved': len(source_record['views']),
                                   'error': type(error).__name__ + ': ' + str(error), 'traceback': traceback.format_exc()}
                    row.update(batch=batch_index, new_model_calls=0, fallback=False,
                        proposed_C_selection_not_new_fit=arm == 'ConstraintAcquire')
                    immutable_json(target, row)
                summaries.append({k: row[k] for k in ('source', 'arm', 'batch', 'correct', 'unresolved')})
                print(json.dumps(summaries[-1]), flush=True)
    result = {'rows': summaries, 'mother_count': 24, 'views_per_arm': 96,
        'correct_by_arm': {a: sum(r['correct'] for r in summaries if r['arm'] == a) for a in libraries},
        'unresolved_by_arm': {a: sum(r['unresolved'] for r in summaries if r['arm'] == a) for a in libraries},
        'new_model_calls': 0, 'additional_mothers': 0, 'not_five_dataset_training_completion': True,
        'same_frozen_candidate_library_across_batches_not_a_learning_curve': True, 'goal_complete': False}
    immutable_json(OUT / 'source_pass/result.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['prepare', 'source-pass'])
    args = parser.parse_args()
    protocol = prepare()
    if args.phase == 'source-pass':
        source_pass(protocol)
