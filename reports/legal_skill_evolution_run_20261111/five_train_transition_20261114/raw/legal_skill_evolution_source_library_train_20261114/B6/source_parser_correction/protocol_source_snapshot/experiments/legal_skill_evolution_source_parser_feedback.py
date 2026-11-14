"""Targeted acquisition repair from actual B6 parser/source contradictions.

Same TRAIN parents, models, costs and independent strong-control freedoms. No
labels or source facts are invented; raw B6 proposals and failed fits remain.
This client only acquires two proposals and exits at a clean boundary.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_source_library_train as train
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs, INSTRUCTION, PROGRAM_INSTRUCTION


ROOT = train.ROOT
RUN = 'legal_skill_evolution_source_parser_feedback_20261115'
OUT = train.OUT / 'B6/source_parser_correction'


def prepare():
    original = train.read(train.OUT / 'B6/teacher_task.json')
    task = deepcopy(original)
    task['current_libraries'] = {a: train.read(train.OUT / 'B6' / a / 'compiled_candidate.json') for a in train.ARMS}
    target_sources = [t['source_id'] for t in task['tasks'] if 'e82b951' in t['source_id'] or '4607c94' in t['source_id']]
    for entry in task['tasks']:
        sid = entry['source_id']
        entry['actual_current'] = {}
        for arm in train.ARMS:
            row = train.read(train.OUT / 'B6' / arm / 'candidate_results' / train.previous.old.name_for(sid))
            entry['actual_current'][arm] = {'statements': row['actual']['execution']['source_output']['statements'],
                'native_feedback': row['actual']['feedback'], 'correct': row['correct'], 'unresolved': row['unresolved']}
        if sid not in target_sources:
            # Their original full sources are preserved, and are replayed by the
            # host. This repair needs exact text of the two diagnosed documents.
            entry.pop('full_source_text')
            entry.pop('source_units')
            entry.pop('incoming_source_output')
    task['targeted_actual_parser_feedback'] = {
        'C_real_e82_missing_negation_frame': 'Unit17 literally says not to disclose it to anyone. The paid C6 rationale claimed this was fixed, but the actual prohibited matcher only has shall not disclose / not disclose / will not without / not without, so it emits no prohibition source atom. All32 reachable G outputs were completely checked and cannot repair this native residual. Fix the reusable infinitival negated-disclosure frame, preserving the expressly-permitted cross-reference and prior-written-consent exceptions; do not infer a new rule from the label.',
        'Free_real_e82_missing_fragmented_permission': 'The actual Free6 output has the bounded third-party prohibition, but no employee permission from3.1.1 only to such employees of the receiving Party as are strictly necessary for the Permitted Purpose. Read its actual preceding permitted-disclosure heading/context, not a requirement that may disclose and employees appear in one sentence. It also emits complete_source_no_disclosure_permission contrary to the explicit source permission; the shared existing source check rejects that claim. A lexical miss is not complete absence.',
        'C_real_4607_missing_branch_authorization': 'Source2.1.7 permits return or, only where expressly authorized in writing by OSCE, destruction/deletion. Current C6 keeps an ordinary OR with both joint exception slots no_acquired_exception. Preserve authorization only on the destruction branch. The existing Free library demonstrates authorized_action_alternative; the acquired C joint exception/action language is also available if it can faithfully preserve branch attachment. Do not attach authorization to unconditional return, drop it, or turn OR into AND.',
        'do_not_fix_faithful_native_residuals': '8fb says only if requested, not agreement termination; reviewed de42 full-information/copies OR remains source-faithful despite its native NotMentioned. Do not remove or strengthen those source norms for a label.',
        'all_existing_shared_source_type_scope_and_native_checks_unchanged': True,
        'past_failed_G_search_not_a_source_semantic_pass': True}
    task['same_actual_feedback_for_both_independent_teachers'] = True
    task['two_full_sources_this_targeted_repair'] = target_sources
    immutable_json(OUT / 'teacher_task.json', task)
    profile = train.prepare()
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/clients.py',
        ROOT / 'legal_skill_guard/skill_evolution/ledger.py',
        ROOT / 'legal_skill_guard/skill_evolution/teacher_transport.py', Path(train.__file__)]
    protocol = {'run_id': RUN, 'same_goal': True, 'acquisition_only_no_candidate_execution': True,
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'task_sha256': digest(task), 'teacher_profile': profile['teacher_profile'],
        'sources': train.parent.prepare()['train_sources'], 'teacher_concurrency': 2,
        'old_calls_proposals_results_fits_and_libraries_preserved': True,
        'new_sources_seeds_model_configuration': False, 'TEST_opened': False}
    immutable_json(OUT / 'protocol.json', protocol)
    return protocol, task


def run():
    protocol, task = prepare()
    for path, sha in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN, sources={'train': protocol['sources'], 'dev': [], 'test': []},
        binding=digest(protocol), teacher_concurrency=2)
    system = train.SYSTEM
    first = system.index('In the current second-batch residual,')
    last = system.index('Keep old valid source abilities', first)
    system = system[:first] + 'Repair the concrete B6 parser/source failures documented in targeted_actual_parser_feedback. Change the smallest relevant functions and retain all other correct source behavior. Native scores alone do not authorize a factual or scope change.\n' + system[last:]
    user = json.dumps(pack_programs(task), ensure_ascii=False, separators=(',', ':'))

    def acquire(arm):
        path = OUT / arm / 'teacher.json'
        if path.exists():
            return
        prompt = system + '\n' + (train.previous.old.C_PART + '\n' + train.previous.old.previous.prior.prior.C_SPEC
            if arm == 'ConstraintAcquire' else train.previous.old.FREE_PART)
        prompt += '\n' + INSTRUCTION + '\n' + PROGRAM_INSTRUCTION
        prompt += '\nAllowed attributes: ' + ','.join(sorted(train.previous.old.METHODS))
        prompt += '\nAllowed calls: ' + ','.join(sorted(train.previous.old.CALLS))
        result = FrozenTeacher(ledger, OUT, protocol['teacher_profile']).propose(
            RUN + ':' + arm + ':parser_repair', source_ids=[t['source_id'] for t in task['tasks']],
            system_prompt=prompt, user_prompt=user, output_schema=train.previous.schema_for(arm))
        immutable_json(path, result)
        print(json.dumps({'actual_parser_repair_teacher_saved': arm}), flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(acquire, arm) for arm in train.ARMS]
        errors = []
        for job in jobs:
            try:
                job.result()
            except Exception as error:
                errors.append(error)
        if errors:
            raise errors[0]


if __name__ == '__main__':
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()
