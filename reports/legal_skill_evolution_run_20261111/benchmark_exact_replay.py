"""Compare indexed reuse with preserved production code; network is forbidden."""
from contextlib import contextmanager
import base64
import json
from pathlib import Path
import sqlite3
import time
from unittest.mock import patch

from legal_skill_guard.skill_evolution.clients import FrozenExecutor

ROOT = Path(__file__).resolve().parents[2]


def main():
    profile = json.loads((ROOT / 'configs/legal_skill_evolution_repair_v13_20261111.json').read_text())
    namespace = {'__name__': 'legal_skill_guard.skill_evolution._old_client', '__package__': 'legal_skill_guard.skill_evolution'}
    preserved = ROOT / 'artifacts/legal_skill_evolution_20261111/repair_v12/source_snapshot/legal_skill_guard/skill_evolution/clients.py'
    exec(compile(preserved.read_text(), str(preserved), 'exec'), namespace)
    class ReadOnlyLedger:
        @contextmanager
        def transaction(self):
            db = sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True)
            try:yield db
            finally:db.close()
        def permit(self, source, purpose, role):
            assert purpose == 'skill_actor' and role == 'executor'
    ledger = ReadOnlyLedger()
    roots = [ROOT / json.loads((ROOT / p).read_text())['artifacts'] for p in profile['exact_replay_profiles']]
    samples = []
    for path in sorted((ROOT / 'artifacts/legal_skill_evolution_20261111/repair_v12/calls').glob('*/request.json'))[:12]:
        request = json.loads(path.read_text())
        wire = json.loads(path.with_name('wire_request.json').read_text())
        payload = json.loads(base64.b64decode(wire['body_b64']))
        samples.append({'source': request['source'], 'purpose': request['purpose'], 'thinking': False,
            'messages': payload['messages'], 'schema': payload['response_format']['json_schema']['schema']})
    assert len(samples) == 12
    results, times = {}, {}
    with patch('legal_skill_guard.rr.client.ExecutorClient.generate', side_effect=AssertionError('Offline cache miss: dispatch forbidden')):
        for label, cls in [('old_scan', namespace['FrozenExecutor']), ('indexed', FrozenExecutor)]:
            client = object.__new__(cls)
            client.config, client.ledger, client.exact_replay_roots = profile['executor'], ledger, roots
            client.artifacts = ROOT / 'artifacts/legal_skill_evolution_20261111/cache_benchmark' / label
            start = time.perf_counter()
            results[label] = [client.generate('offline-cache-benchmark:' + str(i), **args) for i, args in enumerate(samples)]
            times[label] = time.perf_counter() - start
    assert results['old_scan'] == results['indexed']
    receipt = {'evidence_kind': 'offline actual-request cache lookup benchmark; not model generation latency',
        'new_model_calls': 0, 'requests_compared': len(samples), 'all_results_byte_content_and_physical_ids_equal': True,
        'seconds': times, 'lookup_speedup_including_index_build': times['old_scan'] / times['indexed'],
        'teacher_requests': 0, 'network_dispatch_forbidden': True}
    target = Path(__file__).with_name('exact_replay_performance_regression.json')
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':main()
