"""Resume the unchanged DEV calculation after a recorded transport failure.

Terminal failed requests stay charged and remain failed main-path outputs. They
are never submitted again. Only previously unstarted requests are dispatched;
the original frozen request/configuration identities remain in force. A separate
receipt binds this recovery controller and its reduced HTTP concurrency.
"""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legal_skill_guard.lsl.data import load_json, write_json, sha
from legal_skill_guard.lsl.streaming_physical import dispatch_stream
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.ledger import BudgetError


def resume_stream(ledger, requests, directory, *, endpoint='http://127.0.0.1:8000/v1/chat/completions',
                  concurrency=8, on_result=None):
    cached = {}
    fresh = []
    with ledger.transaction() as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise BudgetError('Reconcile actual pending requests before DEV recovery')
        for request in requests:
            prior = db.execute('select role,purpose,source,request_hash,status,result from calls where id=?',
                               (request['call_id'],)).fetchone()
            if prior is None:
                fresh.append(request)
                continue
            expected = ('executor', request['purpose'], request['source'],
                        digest({'request': request['request'], 'origin_spec': ledger.spec, 'policy': ledger.policy}))
            if prior[:4] != expected or prior[4] not in ('completed', 'failed') or not prior[5]:
                raise BudgetError('DEV recovery identity or terminal status differs')
            cached[request['call_id']] = json.loads(prior[5])
    if on_result:
        for call_id, result in cached.items():
            on_result(call_id, result)
    # Four is within the original maximum of eight. Lower in-flight demand
    # prevents long scalar programs from exhausting the fixed KV budget.
    if fresh:
        generated = dispatch_stream(ledger, fresh, directory, endpoint=endpoint,
                                    concurrency=min(4, concurrency), on_result=on_result)
        cached.update((request['call_id'], result) for request, result in zip(fresh, generated))
    return [cached[request['call_id']] for request in requests]


def main(epoch):
    import experiments.lsl_mix_dev as dev
    import experiments.lsl_mix_candidate_generation as generation

    out = ROOT / 'artifacts/lsl_mixed256_20261110'
    location = out / 'dev' / ('epoch%d' % epoch)
    frozen = load_json(location / 'config.json')
    for file, expected in frozen['code'].items():
        if sha(ROOT / file) != expected:
            raise ValueError('Frozen DEV file changed before recovery: ' + file)
    # The original in-memory mapping uses tuples; JSON persists them as lists.
    # Canonicalize that representation before the existing equality check.
    # The seven system dependencies must remain exactly identical on disk.
    canonical_systems = json.loads(json.dumps(dev.SYSTEMS))
    if canonical_systems != frozen['systems']:
        raise ValueError('Scientific system dependencies changed')
    dev.SYSTEMS = canonical_systems
    import httpx
    metrics = httpx.get('http://127.0.0.1:8000/metrics', trust_env=False, timeout=10).text
    states = [line for line in metrics.splitlines()
              if line.startswith(('vllm:num_requests_running', 'vllm:num_requests_waiting'))]
    if not states or any(float(line.rsplit(' ', 1)[1]) for line in states):
        raise RuntimeError('Wait for real serving requests to finish before recovering')
    write_json(location / 'transport_recovery.json', {
        'controller_sha256': sha(Path(__file__)), 'frozen_config_sha256': sha(location / 'config.json'),
        'time': time.time(), 'serving_states': states, 'maximum_HTTP_concurrency': 4,
        'model_generation_configuration_changed': False, 'terminal_requests_retried': 0,
        'system_mapping': 'identical JSON value; tuple/list persistence mismatch normalized',
        'failed_outputs': 'preserved as failed main paths; only the separately marked original fallback protocol may apply',
        'TEST_loaded': False})
    # Explicit recovery injection; both original scientific modules and their
    # bound files remain unchanged. This overlay is recorded in the receipt.
    generation.dispatch_stream = resume_stream
    dev.dispatch_stream = resume_stream
    dev.main(epoch)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--epoch', type=int, choices=(1, 2, 3), required=True)
    main(parser.parse_args().epoch)
