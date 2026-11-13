"""Complete never-dispatched controls after the verified revision boundary.

Equal information covers source, cases, feedback, traces and common fixes.
The proposed update recipe is the treatment, not an extra data entitlement.
"""
import ast
import fcntl
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments.legal_skill_evolution_refutation_learning import ROOT, read, sha
from experiments.legal_skill_evolution_teacher_proof_skills import RUN, OUT, RESULT
from experiments.legal_skill_evolution_teacher_proof_revision import REVISED_COMMON, FREE, DIRECTED
from experiments.legal_skill_evolution_teacher_proof_execute import PLAN, validate, execute
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.teacher_transport import pack


def run():
    p = read(OUT/'protocol.json')
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        assert not db.execute("select id from calls where status='reserved'").fetchall()
    assert (OUT/'revision/Full/teacher.json').exists(), 'Preserve and observe the original live Full first'
    tasks, changes = {}, {}
    for arm in ('ProofFree', 'CacheFree'):
        original = read(OUT/'revision'/arm/'input.json')
        current = dict(original)
        assert current.pop('directed_revision_algorithm_also_available_to_free_controls') == DIRECTED
        assert current == {k: v for k, v in original.items()
                           if k != 'directed_revision_algorithm_also_available_to_free_controls'}
        tasks[arm] = current
        changes[arm] = {'original_unsubmitted_input_sha256': digest(original),
                       'actual_input_sha256': digest(current),
                       'all_empirical_data_supervision_own_history_and_common_fixes_unchanged': True}
        immutable_json(OUT/'revision'/arm/'actual_input_data_only.json', current)
    amendment = {'reason': 'Do not inject candidate update algorithm into its ablation. Equal empirical information is preserved; free controls remain free to discover/use any organization.',
        'same_goal': True, 'goal_complete': False,
        'no_new_sources_cases_labels_or_seed': True,
        'Full_request_and_result_unchanged': True,
        'controls_not_previously_physically_dispatched': True,
        'not_a_physical_retry': True, 'tasks': changes,
        'implementation_sha256': sha(Path(__file__))}
    immutable_json(OUT/'revision'/'control_comparison_amendment.json', amendment)
    ledger = EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['source_ids'], 'dev': [], 'test': []}, binding=digest(p))
    for arm in ('ProofFree', 'CacheFree'):
        folder = OUT/'revision'/arm
        if (folder/'teacher.json').exists():
            print(json.dumps({'preserved_existing_result': arm}), flush=True); continue
        with ledger.transaction() as db:
            assert not db.execute('select id from calls where id=?', (RUN+':revision:'+arm,)).fetchall()
        # The previous wrapper has relinquished this exact lock before removal.
        (folder/'HOLD_GENERATION').unlink(missing_ok=True)
        response = FrozenTeacher(ledger, folder, p['teacher_profile']).propose(
            RUN+':revision:'+arm, source_ids=p['acquisition_and_feedback_sources'],
            system_prompt=REVISED_COMMON+FREE,
            user_prompt=json.dumps(pack(tasks[arm]), ensure_ascii=False), output_schema=RESULT)
        immutable_json(folder/'teacher.json', response)
        bundle = response['value']
        try:
            validate(bundle['program']); names = {n.name for n in ast.parse(bundle['program']).body}
            for rule in bundle['source_rules']:
                assert rule['quote'] and rule['quote'] in tasks[arm]['law_material'][rule['source_field']]
                assert rule['function'] in names
            plans = [execute(bundle['program'], {'phase': 'plan', 'question': r['question']})
                     for r in tasks[arm]['actual_acquisition_TRAIN_cases']]
            for plan in plans: jsonschema.validate(plan, PLAN)
            immutable_json(folder/'offline_check.json', {'pure_python_exact_quotes_and_plan_types': True,
                'plans': plans, 'native_and_source_semantic_validation_pending': True,
                'actual_input': 'actual_input_data_only.json'})
            print(json.dumps({'arm': arm, 'program_chars': len(bundle['program']),
                              'seconds': response['elapsed_seconds'], 'plans': plans}, ensure_ascii=False), flush=True)
        except Exception as error:
            immutable_json(folder/'offline_check.json', {'validation_error': type(error).__name__+': '+str(error)})
            print(json.dumps({'arm': arm, 'validation_error': str(error)}), flush=True)


if __name__ == '__main__':
    with (ROOT/'artifacts/rr_v2_preflight/current_teacher_proof_revision.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()
