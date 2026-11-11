"""The fixed seven-system native TEST, only after a verified B8 freeze."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import jsonschema

from experiments.legal_skill_evolution_formal import ARMS, PROFILE as FORMAL_PROFILE
from experiments.legal_skill_evolution_freeze_data import materialize, require_B8
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import WireError
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, GenerationHold
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime, render_messages
from legal_skill_guard.skill_evolution.native import grade_view, public_task, answer_wire_schema, DIRECT_SYSTEM
from reports.legal_skill_evolution_run_20261111.native_statistics import (
    average, summarize, nli_metrics, paired_source_bootstrap, CONTRASTS)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'configs/legal_skill_evolution_frozen_v1_20261111.json'
FOLDER = ROOT / 'artifacts/legal_skill_evolution_20261111/frozen_test_v1'


def load(path):return json.loads(path.read_text())


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    require_B8(ROOT)  # Reconcile all TRAIN/DEV work before qualification or TEST reads.
    from reports.legal_skill_evolution_run_20261111.qualify_TEST_identity import main as qualify
    qualify()  # Includes the now-complete TRAIN teacher prefix; no TEST labels.
    materialize(ROOT)  # Its B8 gate precedes all TEST annotation access.
    formal_profile = load(FORMAL_PROFILE)
    formal = ROOT / formal_profile['artifacts']
    original = load(formal / 'execution_manifest.json')
    from experiments.legal_skill_evolution_transfer import prepare_masks
    source_manifest = load(ROOT / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    source_datasets = {r['key']: dataset for dataset, splits in source_manifest['datasets'].items()
                       for r in splits['train']}
    transfer_paths, ancestry_paths = prepare_masks(formal, FOLDER,
        Library.load(FOLDER / 'libraries/Full_B8.json'), source_datasets)
    code = {p: sha(ROOT / p) for p in original['code']}
    for relative in ('experiments/legal_skill_evolution_frozen.py',
                     'experiments/legal_skill_evolution_freeze_data.py',
                     'experiments/legal_skill_evolution_transfer.py',
                     'reports/legal_skill_evolution_run_20261111/native_statistics.py',
                     'reports/legal_skill_evolution_run_20261111/skill_lineage.py',
                     'reports/legal_skill_evolution_run_20261111/qualify_TEST_identity.py',
                     'reports/legal_skill_evolution_run_20261111/test_skill_lineage.py',
                     'reports/legal_skill_evolution_run_20261111/test_frozen_native_preparation.py',
                     'legal_skill_guard/rr/adapters.py', 'legal_skill_guard/rr/partitions.py',
                     'legal_skill_guard/rr/coverage.py'):
        code[relative] = sha(ROOT / relative)
    data = {p: sha(ROOT / p) for p in original['data']}
    data.update({str(path.relative_to(ROOT)): expected for path, expected in ancestry_paths.items()})
    for path in [ROOT / 'reports/legal_skill_evolution_run_20261111/qualified_TEST_identity_plan.json',
                 FOLDER / 'native_materialization.json', FOLDER / 'prepared_test/public.json',
                 FOLDER / 'prepared_test/grading.json'] + list((FOLDER / 'libraries').glob('*_B8.json')) + transfer_paths:
        data[str(path.relative_to(ROOT))] = sha(path)
    manifest = load(ROOT / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json')
    sources = {p: [r['key'] for dataset in manifest['datasets'].values() for r in dataset[p]]
               for p in ('train', 'dev')}
    sources['test'] = [r['key'] for r in load(FOLDER / 'prepared_test/public.json')]
    payload = {'code': code, 'data': data, 'batch': 8,
        'B8_hashes': load(FOLDER / 'native_materialization.json')['original_B8_hashes'],
        'model_hash_receipt': load(ROOT / 'artifacts/legal_skill_evolution_20261111/base_model_verified.json'),
        'teacher_TEST_access': False, 'library_updates': False, 'TEST_source_count': 160, 'native_views': 352}
    profile = {'run_id': 'legal_skill_evolution_frozen_v1_20261111',
        'artifacts': str(FOLDER.relative_to(ROOT)), 'executor': formal_profile['executor'],
        'source_ids': sources, 'freeze': {'batch': 8, 'artifact_sha256': digest(payload)},
        'generation_binding': {'code_hash': digest(code), 'data_hash': digest(data),
            'executor_hash': digest(formal_profile['executor']), 'B8_libraries_hash': digest(payload['B8_hashes'])},
        'exact_replay_profiles': formal_profile['exact_replay_profiles'] + [str(FORMAL_PROFILE.relative_to(ROOT))],
        'systems': list(ARMS), 'teacher_enabled': False, 'model_parameter_updates': False,
        'library_updates': False, 'thinking': False}
    immutable_json(PROFILE, profile)
    immutable_json(FOLDER / 'freeze_manifest.json', {**payload, 'profile_sha256': sha(PROFILE)})
    for relative in code:
        path = FOLDER / 'source_snapshot' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and sha(path) != sha(ROOT / relative):raise ValueError('Frozen TEST source snapshot changed')
        shutil.copyfile(ROOT / relative, path)
    print(json.dumps({'B8_freeze_prepared': True, 'source_count': 160, 'native_views': 352,
                      'systems': 7, 'teacher_enabled': False, 'new_model_calls': 0}), flush=True)


class FrozenStudy:
    def __init__(self):
        self.profile = load(PROFILE)
        manifest = load(FOLDER / 'freeze_manifest.json')
        if sha(PROFILE) != manifest['profile_sha256']:raise ValueError('Frozen TEST profile changed')
        if digest({k: v for k, v in manifest.items() if k != 'profile_sha256'}) != self.profile['freeze']['artifact_sha256']:
            raise ValueError('Frozen artifact fingerprint differs from its bound profile')
        for path, expected in {**manifest['code'], **manifest['data']}.items():
            if sha(ROOT / path) != expected:raise ValueError('Frozen TEST dependency changed: ' + path)
        self.folder = FOLDER
        self.records = {r['key']: r for r in load(FOLDER / 'prepared_test/public.json')}
        self.grading = load(FOLDER / 'prepared_test/grading.json')
        if set(self.records) != set(self.profile['source_ids']['test']) or set(self.records) != set(self.grading):
            raise ValueError('The qualified frozen source/grading sets differ')
        self.ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
            run_id=self.profile['run_id'], sources=self.profile['source_ids'],
            binding=self.profile['generation_binding'], freeze=self.profile['freeze'])
        self.executor = FrozenExecutor(self.ledger, self.folder, self.profile['executor'])
        self.executor.exact_replay_roots = []
        for relative in self.profile['exact_replay_profiles']:
            prior = load(ROOT / relative)
            if prior['executor'] != self.profile['executor']:raise ValueError('Frozen executor profile changed across reuse')
            self.executor.exact_replay_roots.append(ROOT / prior['artifacts'])
        self.runtime = SkillRuntime(FrozenReads(self.executor))
        self.libraries = {a: Library.load(FOLDER / 'libraries' / (a + '_B8.json')) for a in ARMS}
        for arm, library in self.libraries.items():
            if library.hash != manifest['B8_hashes'][arm]:raise ValueError('A B8 frozen library changed')

    def parent(self, source, library, arm):
        path = self.folder / 'predictions' / arm / (digest(source['key']) + '.json')
        if path.exists():
            saved = load(path)
            if saved['source'] != source['key'] or saved['library_hash'] != library.hash:
                raise ValueError('Frozen parent checkpoint identity changed')
            return saved
        original_hash, results = library.hash, []
        for view in source['views']:
            cache = self.folder / 'view_results' / (digest({'source': source['key'], 'view': view,
                'library_hash': library.hash, 'purpose': 'skill_test'}) + '.json')
            if cache.exists():results.append(load(cache));continue
            try:
                execution = self.runtime.run(source, view, library, purpose='skill_test')
            except (GenerationHold, BudgetError):
                raise
            except (ValueError, WireError, jsonschema.ValidationError, subprocess.TimeoutExpired) as error:
                with self.ledger.transaction() as db:
                    if db.execute("select 1 from calls where status='reserved'").fetchone():raise
                execution = {'answer': None, 'evidence_sentence_ids': [], 'events': [],
                    'core_executed': False, 'fallback': False, 'error': type(error).__name__ + ': ' + str(error)}
            score = grade_view(source['dataset'], view, self.grading[source['key']][view['id']],
                               execution['answer'], execution['evidence_sentence_ids'])
            result = {'view': view['id'], 'controlled': False, 'execution': execution, 'score': score}
            immutable_json(cache, result)
            results.append(result)
        if library.hash != original_hash:raise ValueError('Frozen inference changed a library')
        result = {'source': source['key'], 'dataset': source['dataset'], 'library_hash': library.hash,
            'views': results, 'native_grade': average([r['score']['grade'] for r in results]),
            'native_core_correct': sum(r['score']['correct'] and r['execution']['core_executed'] for r in results),
            'native_fallback_views': sum(r['execution']['fallback'] for r in results)}
        immutable_json(path, result)
        return result

    def preflight(self):
        card = self.executor.readiness()
        rows = []
        for source in self.records.values():
            for view in source['views']:
                count = self.executor.tokenize(render_messages(DIRECT_SYSTEM, public_task(source, view),
                    answer_wire_schema(source['dataset'], view)), thinking=False)['count']
                if count + self.profile['executor']['max_tokens'] > self.profile['executor']['context_tokens']:
                    raise ValueError('A frozen TEST input exceeds capacity; no clipping or query replacement')
                rows.append({'source': source['key'], 'view': view['id'], 'input_tokens': count})
        immutable_json(self.folder / 'preflight.json', {'card': card, 'native_views': rows,
            'new_model_generation_calls': 0, 'teacher_enabled': False, 'thinking': False})
        print(json.dumps({'frozen_TEST_preflight_passed': True, 'views': len(rows), 'new_model_calls': 0}), flush=True)

    def run(self):
        if not (self.folder / 'preflight.json').exists():raise ValueError('Frozen input preflight must precede model generation')
        complete_path = self.folder / 'TEST_completed.json'
        if complete_path.exists():
            complete = load(complete_path)
            if complete['freeze_artifact_sha256'] != self.profile['freeze']['artifact_sha256']:
                raise ValueError('Completed TEST belongs to another freeze')
            for path, expected in complete['result_file_sha256'].items():
                if sha(self.folder / path) != expected:raise ValueError('Completed frozen result changed')
            print(json.dumps({'frozen_TEST_already_complete': True, 'new_model_calls': 0}), flush=True)
            return
        all_results = {}
        for arm in ARMS:
            library = self.libraries[arm]
            rows = []
            for source in self.records.values():
                rows.append(self.parent(source, library, arm))
                print(json.dumps({'stage': 'frozen_TEST', 'arm': arm, 'source': source['key'],
                    'native_grade': rows[-1]['native_grade'], 'core_correct': rows[-1]['native_core_correct']}), flush=True)
            all_results[arm] = rows
            immutable_json(self.folder / (arm + '_native_summary.json'), {'arm': arm, 'B8_library_hash': library.hash,
                'metrics': summarize(rows), 'ContractNLI_secondary': nli_metrics(rows, self.grading),
                'teacher_used': False, 'skill_updated': False, 'model_parameter_updates': False})
        comparison = {arm: paired_source_bootstrap(all_results['Full'], all_results[arm]) for arm in CONTRASTS}
        immutable_json(self.folder / 'primary_four_contrasts.json', comparison)
        with self.ledger.transaction() as db:
            if db.execute("select 1 from calls where id like ? and role='teacher'", (self.profile['run_id'] + ':%',)).fetchone():
                raise ValueError('Teacher access occurred during frozen evaluation')
        immutable_json(self.folder / 'TEST_completed.json', {'completed_utc': datetime.now(timezone.utc).isoformat(),
            'systems': 7, 'independent_parents_per_dataset': 32, 'native_views_per_system': 352,
            'freeze_artifact_sha256': self.profile['freeze']['artifact_sha256'],
            'result_file_sha256': {p.name: sha(p) for p in list(self.folder.glob('*_native_summary.json')) +
                                  [self.folder / 'primary_four_contrasts.json']},
            'teacher_calls': 0, 'library_updates': False, 'goal_complete': False,
            'next': 'registered frozen transfer masks, independent mechanism evidence and completion audit'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'preflight', 'run'])
    args = parser.parse_args()
    try:
        if args.action == 'prepare':prepare()
        else:
            study = FrozenStudy()
            study.preflight() if args.action == 'preflight' else study.run()
    except GenerationHold as error:
        print(json.dumps({'state': 'held_at_request_boundary', 'goal_status': 'active', 'reason': str(error)}), flush=True)
        raise SystemExit(75)
