"""Recover lost cost references by replaying original TRAIN inputs, offline.

The frozen runtime is unchanged. A recording executor observes settled physical
IDs before a truncated response or later exception discards the runtime trace.
No predictions, grades or ledger entries are rewritten.
"""
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
from legal_skill_guard.skill_evolution.native import public_task
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime
from reports.legal_skill_evolution_run_20261111.formal_cost_footprints import used_physical_ids

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent
RUN = 'offline_TRAIN_cost_references_20261112'


def read(path):return json.loads(path.read_text())


class ReadOnlyLedger:
    run_id = RUN

    def __init__(self, sources):self.sources = set(sources)

    def permit(self, source, purpose, role):
        if source not in self.sources or purpose != 'skill_actor' or role != 'executor':
            raise AssertionError('Offline replay left the original TRAIN scope')

    @contextmanager
    def transaction(self):
        with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
            yield db


class RecordingExecutor(FrozenExecutor):
    def generate(self, *args, **kwargs):
        result = super().generate(*args, **kwargs)
        self.observed.add(result.get('reused_physical_call_id', args[0]))
        return result


class NoNetwork:
    def open(self, *args, **kwargs):raise AssertionError('Offline cost evidence cannot dispatch')


def main():
    profile_path = ROOT / 'configs/legal_skill_evolution_formal_v5_20261111.json'
    profile = read(profile_path)
    formal = ROOT / profile['artifacts']
    old_costs = read(REPORT / 'formal_cost_footprints.json')
    receipt_path = REPORT / 'recovered_TRAIN_cost_references.json'
    missing = set(read(receipt_path)['recovered_physical_ids'] if receipt_path.exists()
                  else old_costs['formal_dispatches_not_yet_associated_with_settled_arm_evidence'])
    if not missing:raise ValueError('No untraced TRAIN cost remains to recover')
    ledger = ReadOnlyLedger([])
    with ledger.transaction() as db:
        records = {identity: {'source': source, 'result': json.loads(raw)}
                   for identity, source, raw in db.execute('select id,source,result from calls where status=\'completed\'')}
    sources = {records[i]['source'] for i in missing}
    ledger.sources = sources
    bank = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    if not sources <= set(bank):raise AssertionError('An untraced response is outside fixed TRAIN')
    folder = ROOT / 'artifacts/legal_skill_evolution_20261111/offline_TRAIN_cost_references'
    roots = [ROOT / read(ROOT / p)['artifacts'] for p in profile['exact_replay_profiles']] + [formal]
    client = RecordingExecutor(ledger, folder, profile['executor'], opener=NoNetwork())
    client.exact_replay_roots = roots
    runtime = SkillRuntime(FrozenReads(client))
    rows, evidence = [], {}
    def cite(path):evidence[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    cite(profile_path);cite(formal / 'execution_manifest.json')
    with patch.object(ExecutorClient, 'generate', side_effect=AssertionError('Offline cache miss; physical generation forbidden')) as dispatch:
        for arm in profile['arms']:
            for path in sorted((formal / arm).glob('initial_B[1-8].json')):
                point = read(path)
                batch = point['binding']['batch']
                for parent in point['results']:
                    if parent['source'] not in sources:continue
                    source = bank[parent['source']]
                    library_path = formal / arm / f'B{batch - 1}.json'
                    library = Library.load(library_path)
                    if library.hash != parent['library_hash']:
                        raise AssertionError('Replay library is not the original first-attempt library')
                    cite(path);cite(library_path)
                    for old_view in parent['views']:
                        if old_view['controlled']:continue
                        view = next(v for v in source['views'] if v['id'] == old_view['view'])
                        identity = digest({'source': source['key'], 'task': public_task(source, view),
                                           'frozen_executor': client.config})
                        direct = formal / 'native_direct_baselines' / (identity + '.json')
                        if direct.exists():
                            target = folder / 'native_direct_baselines' / direct.name
                            target.parent.mkdir(parents=True, exist_ok=True)
                            if target.exists() and target.read_bytes() != direct.read_bytes():
                                raise AssertionError('Preserved direct baseline changed')
                            shutil.copyfile(direct, target)
                        client.observed = set()
                        try:actual = runtime.run(source, view, library, purpose='skill_actor')
                        except (ValueError, KeyError, TypeError) as error:
                            actual = {'answer': None, 'core_executed': False, 'fallback': False,
                                      'error': type(error).__name__ + ': ' + str(error)}
                        expected = old_view['execution']
                        keys = ('answer', 'core_executed', 'fallback', 'error', 'terminal_skill')
                        if {k: actual.get(k) for k in keys} != {k: expected.get(k) for k in keys}:
                            raise AssertionError('An offline replay changed the original result')
                        original_ids = used_physical_ids(expected, records)
                        recovered = (client.observed - original_ids) & missing
                        rows.append({'arm': arm, 'batch': batch, 'source': source['key'], 'view': view['id'],
                            'original_result_equal': True, 'recovered_physical_ids': sorted(recovered),
                            'initial_evidence_path': str(path.relative_to(ROOT)),
                            'original_library_hash': library.hash})
        if dispatch.call_count:raise AssertionError('Offline recovery attempted dispatch')
    recovered = {i for row in rows for i in row['recovered_physical_ids']}
    if recovered != missing:raise AssertionError('The original first attempts do not explain every missing reference')
    with ledger.transaction() as db:
        if db.execute('select 1 from calls where id like ?', (RUN + ':%',)).fetchone():
            raise AssertionError('Offline evidence created a physical ledger entry')
    result = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'network_disabled': True, 'ledger_read_only': True, 'original_predictions_and_scores_unchanged': True,
        'recovered_physical_ids': sorted(recovered), 'rows': rows, 'evidence_sha256': evidence,
        'physical_responses': {i: {'source': records[i]['source'],
            'finish_reason': records[i]['result']['finish_reason'], 'usage': records[i]['result']['usage'],
            'settled_result_sha256': digest(records[i]['result'])} for i in sorted(recovered)},
        'interpretation': 'These physical requests were already charged once in total costs. Exact-cache replay recovers arm/batch references lost when the original runtime discarded an exception trace; it adds no model result or method benefit.'}
    receipt_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'new_model_calls': 0, 'replayed_native_views': len(rows),
        'recovered_physical_requests': len(recovered),
        'arm_response_references': sum(len(r['recovered_physical_ids']) for r in rows)}))


if __name__ == '__main__':main()
