"""Audit real learned programs and pattern credit without permitting dispatch."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.patterns import learn, candidates, compatible_dependency_versions
from legal_skill_guard.skill_evolution.revisions import VersionTable
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime
from experiments.legal_skill_evolution_fragment_program_update import RUN
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot


def read(p):return json.loads(p.read_text())


class ExactOnly(FrozenExecutor):
    def generate(self, *args, **kwargs):
        self.validate_scope(kwargs['source'], kwargs['purpose'], kwargs['thinking'])
        payload = self.payload(messages=kwargs['messages'], thinking=kwargs['thinking'], schema=kwargs['schema'])
        wire = json.dumps(payload, ensure_ascii=False).encode()
        key = (kwargs['source'], kwargs['purpose'], hashlib.sha256(wire).hexdigest())
        if not any(m[2] == wire for m in self.replay_index(self.exact_replay_roots).get(key, ())):
            raise AssertionError('Offline audit forbids a model dispatch; no exact response exists')
        return super().generate(*args, **kwargs)


def main():
    root = Path(__file__).resolve().parents[1]
    folder = root / 'artifacts' / RUN
    protocol, result = read(folder / 'protocol.json'), read(folder / 'completed.json')
    if digest(protocol) != result['protocol_hash']:raise ValueError('Actual run binding changed')
    for name, sha in protocol['code_sha256'].items():
        if hashlib.sha256((folder / 'tested_code_snapshot' / name).read_bytes()).hexdigest() != sha:
            raise ValueError('Tested source snapshot differs: ' + name)
    keys = protocol['already_fixed_original_TRAIN_parents']
    records = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json') if s['key'] in keys}
    seed = Library.load(root / protocol['shared_seed'])
    profile = read(root / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    ledger = object.__new__(EvolutionLedger)
    ledger.path, ledger.run_id, ledger.freeze = root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', RUN + '_offline_audit', None
    ledger.sources = {'train': tuple(keys), 'dev': (), 'test': ()}
    before = physical_snapshot(ledger.path)
    executor = ExactOnly(ledger, folder / 'postrun_audit', profile['executor'])
    executor.exact_replay_roots = [folder]
    runtime = SkillRuntime(FrozenReads(executor))
    arms = {}
    producer, consumer, field = 'nda_representative_exception_applicability', 'nda_disclosure_permission_consequence', 'exception_applies'
    for arm, update in result['updates'].items():
        saved = Library.load(folder / arm / 'B3.json')
        corrected = deepcopy(saved);corrected.revision_patterns = []
        exported = update['table']
        table = VersionTable(tuple(exported['revision_hashes']), tuple(exported['trigger']), tuple(exported['history']))
        for c in exported['mixed_version_table']:table.observe(c['mask'], c['source'], c['native_parent_grade'], c['trace'])
        learned = learn(corrected, seed, update['revisions'], table, update['selected_mask'],
            generic=arm == 'Lift+GenericJoint', source_records=records)
        compatible = compatible_dependency_versions(seed.skills[producer], corrected.skills[producer],
            seed.skills[consumer], corrected.skills[consumer], field)
        corrected.save(folder / 'postrun_audit' / (arm + '_library.json'))
        assert {k: v.hash for k, v in corrected.skills.items()} == {k: v.hash for k, v in saved.skills.items()}
        replays = []
        for key in keys:
            original = (result['frozen_TRAIN_reuse'][arm] if key == protocol['frozen_TRAIN_reuse'] else
                table.traces[update['selected_mask'], key])
            for expected in original['views']:
                if expected['view'] not in ('nda-5', 'nda-7'):continue
                view = next(v for v in records[key]['views'] if v['id'] == expected['view'])
                actual = runtime.run(records[key], view, corrected, purpose='skill_actor', fallback=False)
                assert actual['core_executed'] and not actual['fallback']
                assert actual['answer'] == expected['execution']['answer']
                assert expected['score']['correct']
                replays.append({'source': key, 'view': view['id'], 'answer': actual['answer'],
                    'same_as_recorded_real_execution': True, 'core_correct_by_existing_native_TRAIN_annotation': True,
                    'read_physical_origins': sorted({e['physical_call_id'] for e in actual['events'] if e.get('kind') == 'READ_LOCAL'})})
        reuse_candidates = candidates(corrected, [result['frozen_TRAIN_reuse'][arm]],
            generic=arm == 'Lift+GenericJoint', source_records=records)
        arms[arm] = {'admitted_native_program_update_preserved': update['accepted'],
            'raw_table_classification': table.classify(), 'all_companion_dependency_versions_compatible': compatible,
            'raw_pipeline_pattern_count': len(saved.revision_patterns), 'postreview_eligible_pattern_count': len(corrected.revision_patterns),
            'postreview_learned_pattern_ids': learned, 'offline_actual_program_replays': replays,
            'patterns_used_in_real_frozen_reuse': 0, 'offline_pattern_candidates_on_that_recorded_reuse': len(reuse_candidates),
            'reuse_was_updated_program_execution_not_pattern_transfer': True}
    after = physical_snapshot(ledger.path);assert before == after
    calls, teacher_usage = [], {}
    for path in sorted((folder / 'calls').glob('*/request.json')):
        request = read(path);response = read(path.with_name('result.json'))
        purpose = request['purpose']
        identity = (RUN + ':teacher:' + digest({'system': request['system_prompt'],
            'user': request['user_prompt'], 'schema': request['output_schema']})
            if purpose == 'skill_teacher' else request['id'])
        assert digest(identity) == path.parent.name
        calls.append({'physical_call_id': identity, 'source': request.get('source'), 'purpose': purpose,
            'elapsed_seconds': response['elapsed_seconds'], 'finish_reason': response.get('finish_reason'),
            'usage': response.get('usage') or response.get('invocation', {}).get('usage'),
            **({'thinking_requested': False, 'reasoning_empty': not bool(response.get('reasoning_content'))} if purpose != 'skill_teacher' else {})})
    for arm in result['updates']:
        teacher_usage[arm] = read(folder / arm / 'teacher_B3.json')['invocation']['usage']
    executor_calls = [c for c in calls if c['purpose'] != 'skill_teacher']
    receipt = {'actual_run_protocol_hash': result['protocol_hash'], 'actual_implementation_commit': 'abd539c9664c763e405df0ba3293d54eba3c0d8b',
        'original_tested_code_files_preserved': len(protocol['code_sha256']), 'arms': arms,
        'new_physical_requests_in_actual_run': {'executor': len(executor_calls), 'teacher': len(teacher_usage)},
        'executor_tokens': sum(c['usage']['total_tokens'] for c in executor_calls),
        'executor_elapsed_seconds': sum(c['elapsed_seconds'] for c in executor_calls),
        'teacher_usage': teacher_usage, 'physical_request_ledger': calls,
        'cumulative_physical_requests': {k: v['total'] for k, v in after.items()}, 'pending': 0,
        'offline_audit_new_physical_requests': 0, 'offline_replays_are_not_new_model_validation': True,
        'same_program_results_after_pattern_credit_fix': True,
        'metadata_order_cache_miss': 'Pilot and teacher-generated fragment tasks were equal as JSON values; field metadata key order differed, preventing exact-wire reuse and causing two additional source selections. All four charged calls are retained. Pure selector metadata is now canonical in teacher field order, with exact zero-dispatch replay of all sixteen actual core paths; ordinary semantic wire remains unchanged.',
        'Full_pattern_credit_fix': 'The old check examined only exception_applies and missed the new companion output general_third_party_prohibition, absent in the old producer. Check every producer-linked consumer input across both versions. Native program admission and scores are unchanged; the Full legal pattern is excluded offline.',
        'method_interpretation': 'Actual literal-source program acquisition/update and fixed TRAIN reuse are supported; the same-information Generic control achieves the same scores. Generic old-consumer/new-producer joint table includes unresolved old READs, so native joint-needed alone does not prove legal semantic co-revision. No real pattern-guided later update and no dedicated Lift success are established.',
        'Lift_independently_established': False, 'CoRev_independently_established': False,
        'actual_cash_invoice_available': False, 'cash_cost_usd': None,
        'billing_basis': 'Existing local executor GPU and authorized Codex CLI; tokens/time measured, no invented dollar conversion.',
        'no_new_DEV_TEST_full_training_or_paper': True, 'goal_status': 'active', 'goal_complete': False}
    immutable_json(folder / 'postrun_audit' / 'receipt.json', receipt)
    print(json.dumps({'new_model_calls_offline': 0, 'actual_run_calls': receipt['new_physical_requests_in_actual_run'],
        'actual_executor_tokens': receipt['executor_tokens'], 'postreview_patterns': {a: v['postreview_eligible_pattern_count'] for a, v in arms.items()},
        'exact_real_core_replays': sum(len(v['offline_actual_program_replays']) for v in arms.values()), 'ledger': after}))


if __name__ == '__main__':main()
