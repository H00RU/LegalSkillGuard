"""Fixed original-TRAIN legal module acquisition before any repair experiment.

The source supplies an actual general prohibition and a referenced permission
exception. Two independent acquisitions share information and resource rules.
Subsequent updates are not started automatically from an unreviewed seed.
"""
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.proposal_batch import prefetch_teachers
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime
from legal_skill_guard.skill_evolution.study import Study


def read(path):return json.loads(path.read_text())


def main():
    root = Path(__file__).resolve().parents[1]
    original = Path('/home/yndx/hhy/legal-skill-redesign-20261109')
    run_id = 'legal_skill_evolution_contract_acquisition_20261112'
    folder = root / 'artifacts' / run_id
    if (folder / 'completed.json').exists():return read(folder / 'completed.json')
    prepared = original / 'artifacts/legal_skill_evolution_20261111/prepared/train'
    records = {s['key']: s for s in read(prepared / 'public.json')}
    prefixes = ['8af247c6', 'd50f9bcd', '35462327', '62fda7e9']
    parents = []
    for prefix in prefixes:
        found = [k for k in records if k.startswith('ContractNLI:' + prefix)]
        if len(found) != 1:raise ValueError('Original TRAIN identity not unique')
        parents.append(found[0])
    key = parents[0]
    text = records[key]['views'][0]['public']['source_text']
    if 'except as expressly permitted under Paragraph 4' not in text or '4. Disclosure to Representatives' not in text:
        raise ValueError('The natural two-clause legal dependency is not in the supplied original source')
    contract = {
        'learning_object': 'Source-grounded exception judgment and the legal effect of a general prohibition, not an answer lookup or two fields of one record.',
        'source_structure': [
            'Paragraph 3(c) imposes a non-disclosure rule but expressly references Paragraph 4.',
            'Paragraph 4(a) supplies the recipient permission, with defined representatives and safeguards.'],
        'requested_granularity': 'Make the actual exception-applicability judgment a nonnative helper output and let the general-rule/native consequence consume it through mode skill. This cuts two actual normative provisions, not two JSON fields. Do not add formatting-only helpers or artificial predecessor errors.',
        'source_parameters': 'Declare source-specific recipient classes, exception type, restriction coverage and other used source values as grounded premises. Preserve their relationships; they may be passed to helper parameters with namespace premises.',
        'executor_reads': 'READ may extract source rule parameters with support. It must not directly decide the native label or decide the entire exception-applicability predicate that the learned procedure is supposed to compute.',
        'scope': 'This acquisition focuses on native disclosure views nda-5 and nda-7. Declare public_tasks accordingly. Other native views keep the unchanged direct fallback and remain in the parent score.',
        'native_query_input': 'current_question is already available as a literal argument. Use it directly rather than asking the executor to reread the same public query.',
        'unknowns': 'Do not invent consent, facts, absent definitions or source rules. Unknowns remain unresolved. Do not force a two-skill outcome when the source does not support two legal responsibilities.',
        'comparison': 'Full and FreeEvolution acquire independently from identical source/feedback and the same interface. Same original three-block/three-skill allowance; all costs retained.',
        'proof_boundary': 'A created legal graph is an acquisition asset, not an old-skill CoRev success or independent Lift evidence.'}
    profile = read(original / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py')) + [Path(__file__).resolve()]
    protocol = {'run_id': run_id, 'goal_complete': False, 'same_goal': True,
        'source_order_fixed_before_new_generation': parents,
        'source_selection': 'Original TRAIN legal clauses, known prior TRAIN initial scores and known teacher-receipt exposure; not DEV/TEST or new-output selection.',
        'already_seen_TRAIN_not_blind': True, 'active_phase': 'seed_acquisition_only',
        'seed': key, 'independent_arms': ['Full', 'FreeEvolution'],
        'prospective_shared_rule_controls_if_seed_is_valid': ['Full', 'FreeEvolution', 'AllPorts+CoRev', 'Lift+GenericJoint'],
        'prospective_update_parents': parents[1:3], 'prospective_reuse_parent': parents[3],
        'future_phase_requires': 'Review real generated procedures/source/USE and then freeze the exact update implementation and workload; no full training or automatic experiment expansion.',
        'acquisition_contract': contract, 'teacher_tasks_this_phase': 2,
        'admission': 'Unchanged strict native parent gain and history preservation; partial scope falls back, never receives false mechanism credit.',
        'offline_regressions_passed': 85, 'automatic_retries': 0,
        'no_new_sources_DEV_TEST_or_full_training': True,
        'executor_profile': profile['executor'], 'teacher_profile': profile['teacher'],
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    immutable_json(folder / 'protocol.json', protocol)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger_path = original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        with sqlite3.connect('file:' + str(ledger_path) + '?mode=ro', uri=True) as db:
            if db.execute("select 1 from calls where status='reserved'").fetchone():raise ValueError('Reconcile actual in-flight requests first')
        study = object.__new__(Study)
        study.root, study.folder, study.stage = root, folder, 'contract_acquisition'
        study.profile = {**deepcopy(profile), 'prior_logical_replay_executions': {}, 'acquisition_contract': contract}
        study.records = {key: records[key]}
        study.grading = {key: read(prepared / 'grading.json')[key]}
        study.source_ids = {'train': [key], 'dev': [], 'test': []}
        study.arms, study.batches, study.order = ('Full', 'FreeEvolution'), [[key]], [key]
        study.ledger = EvolutionLedger(ledger_path, run_id=run_id, sources=study.source_ids,
                                      binding=digest(protocol), teacher_concurrency=2)
        study.executor = FrozenExecutor(study.ledger, folder, profile['executor'])
        study.executor.exact_replay_roots = [original / profile['artifacts']]
        for rel in profile.get('exact_replay_profiles', []):
            prior = read(original / rel)
            if digest(prior['executor']) != digest(profile['executor']):raise ValueError('Frozen model profile differs')
            study.executor.exact_replay_roots.append(original / prior['artifacts'])
        study.reads = FrozenReads(study.executor);study.runtime = SkillRuntime(study.reads)
        study.teacher = FrozenTeacher(study.ledger, folder, profile['teacher'])
        study.initialize()
        for arm in study.arms:study.initial_batch(arm, 1)
        prefetch_teachers(study, 1)
        updates = {arm: study.update(arm, 1) for arm in study.arms}
        with study.ledger.transaction() as db:
            calls = [list(r) for r in db.execute('select id,role,status from calls where id like ? order by reserved_at', (run_id + ':%',))]
        result = {'completed_utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
            'updates': updates, 'physical_requests': calls,
            'source_and_mechanism_review_pending': True, 'no_update_or_reuse_phase_started': True}
        immutable_json(folder / 'completed.json', result)
        return result


if __name__ == '__main__':print(json.dumps(main()))
