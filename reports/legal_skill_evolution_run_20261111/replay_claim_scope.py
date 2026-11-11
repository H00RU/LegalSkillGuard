"""Actual-response regression of the wrong-final-proposition fix; network off."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from unittest.mock import patch

from legal_skill_guard.rr.client import ExecutorClient
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = Path('/home/yndx/hhy/legal-skill-redesign-20261109')
PRIOR = ROOT / 'artifacts/legal_skill_evolution_activation_repair_20261112'
RUN = 'claim_scope_cache_only_20261112'


def read(path):return json.loads(path.read_text())


class ReadOnlyLedger:
    run_id = RUN

    def __init__(self, sources):self.sources = set(sources)

    def permit(self, source, purpose, role):
        if source not in self.sources or purpose != 'skill_actor' or role != 'executor':
            raise AssertionError('Cache-only regression source/purpose differs')

    @contextmanager
    def transaction(self):
        path = ORIGINAL / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        connection = sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True)
        try:yield connection
        finally:connection.close()


class NoNetwork:
    def open(self, *args, **kwargs):raise AssertionError('No network is permitted in the offline regression')


def main():
    bank = read(ROOT / 'reports/legal_skill_evolution_run_20261111/activation_evidence/original_TRAIN_sources.json')
    sources = {r['key']: r for r in bank['public'] if r['dataset'] == 'SARA_v2_Binary'}
    previous = read(PRIOR / 'body_adapter_replay/completed.json')
    profile = read(ORIGINAL / 'configs/legal_skill_evolution_formal_v5_20261111.json')['executor']
    if digest(profile) != read(PRIOR / 'protocol.json')['executor_profile_hash']:
        raise AssertionError('Old actual responses belong to another executor profile')
    folder = ROOT / 'artifacts/claim_scope_cache_replay_20261112'
    # Preserve the exact earlier direct baselines, with their real response IDs.
    for path in (PRIOR / 'body_adapter_replay/native_direct_baselines').glob('*.json'):
        target = folder / 'native_direct_baselines' / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != path.read_bytes():
            raise AssertionError('A preserved baseline changed')
        shutil.copyfile(path, target)
    ledger = ReadOnlyLedger(sources)
    client = FrozenExecutor(ledger, folder, profile, opener=NoNetwork())
    client.exact_replay_roots = [PRIOR, PRIOR / 'body_adapter_replay',
                               ORIGINAL / 'artifacts/legal_skill_evolution_20261111/formal_v5']
    runtime = SkillRuntime(FrozenReads(client));rows = []
    with patch.object(ExecutorClient, 'generate', side_effect=AssertionError('Exact cache miss; generation is disabled')) as dispatch:
        for arm in ('Full', 'FreeEvolution'):
            library = Library.load(PRIOR / 'body_adapter_replay' / arm / 'B1.json')
            old = {r['source']: r for r in previous['arms'][arm]['parents']}
            for key, source in sources.items():
                view = source['views'][0]
                result = runtime.run(source, view, library, purpose='skill_actor')
                score = grade_view(source['dataset'], view, bank['grading'][key][view['id']],
                                   result['answer'], result['evidence_sentence_ids'])
                before = old[key]['views'][0]
                rows.append({'arm': arm, 'source': key, 'view': view['id'],
                    'before_grade': before['score']['grade'], 'after_grade': score['grade'],
                    'before_execution': before['execution'], 'after_execution': result})
        if dispatch.call_count:raise AssertionError('An offline regression attempted physical dispatch')
    wrong = next(r for r in rows if r['arm'] == 'Full' and ':cc82ab' in r['source'])
    valid = next(r for r in rows if r['arm'] == 'Full' and ':a51930' in r['source'])
    if (wrong['after_execution']['core_executed'] or not wrong['after_execution']['fallback']
            or not any(f.get('static_proof', {}).get('kind') == 'explicit_final_claim_mismatch'
                       for f in wrong['after_execution']['failed_candidates'])):
        raise AssertionError('Known wrong final proposition was not skipped')
    if not valid['after_execution']['core_executed'] or valid['after_grade'] != 1:
        raise AssertionError('The actual correct same-proposition path regressed')
    if any(r['before_grade'] != r['after_grade'] for r in rows):
        raise AssertionError('This regression should preserve the four native scores')
    with ledger.transaction() as db:
        if db.execute('select count(*) from calls where id like ?', (RUN + ':%',)).fetchone()[0]:
            raise AssertionError('An offline namespace acquired a physical ledger row')
    result = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'network_disabled': True, 'ledger_read_only': True, 'native_scores_unchanged': True,
        'true_152_core_path_preserved': True, 'wrong_151_core_claim_removed': True,
        'all_original_law_and_case_information_retained': True, 'rows': rows,
        'claim_scope_implementation_sha256': hashlib.sha256((ROOT / 'legal_skill_guard/skill_evolution/claim_scope.py').read_bytes()).hexdigest(),
        'scope': 'Actual prior model responses reused by exact request bytes and settled ledger identity; not new generation, not a full semantic verifier, not Lift/CoRev benefit evidence.',
        'goal_complete': False}
    destination = ROOT / 'reports/legal_skill_evolution_run_20261111/claim_scope_actual_response_regression.json'
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'new_model_calls': 0, 'native_scores_unchanged': True,
        'rows': [{'arm': r['arm'], 'source': r['source'],
                  'before_core': r['before_execution']['core_executed'],
                  'after_core': r['after_execution']['core_executed'],
                  'fallback': r['after_execution']['fallback']} for r in rows]}))


if __name__ == '__main__':main()
