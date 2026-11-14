"""Fixed compact generic-observation control on the same original TRAIN stream."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_five_train as parent
from experiments import legal_skill_evolution_native_observation_read as native_encoding
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import execute_alternatives
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.generic_event_observation import PROMPT, schema_for, lower
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages


ROOT = parent.ROOT
RUN = 'legal_skill_evolution_generic_view_train_20261114'
OUT = ROOT / 'artifacts' / RUN
read = parent.read


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    p = parent.prepare()
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/generic_event_observation.py']
    protocol = {'run_id': RUN, 'parent_five_dataset_run': parent.RUN,
        'sources': p['train_sources'], 'batches': p['batches'],
        'executor_profile': p['executor_profile'], 'thinking': False,
        'representation_frozen_before_new_case_execution_and_scores': True,
        'representation_frozen_after_first_ProgramGuided_teacher_proposal': True,
        'timing_correction_preserves_zero_dispatch_preflight': True,
        'same_author_native_ontology_and_programs': True, 'new_legal_rules_supplied': False,
        'learned_representation_or_teacher_update': False,
        'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'TEST_opened': False, 'new_mothers': 0, 'goal_complete': False}
    immutable_json(OUT / 'protocol.json', protocol)
    return protocol


def execute(protocol, batch):
    for name, sha in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
    client = FrozenExecutor(ledger, OUT, protocol['executor_profile'])
    public = {s['key']: s for s in read(parent.OUT / 'SARA_corrected_TRAIN_views.json')}
    kernels = {s['source']: s['kernel'] for s in read(parent.OUT / 'SARA_native_kernel_bank.json')}
    for sid in [s for s in protocol['batches'][batch-1] if s in public]:
        path = OUT / f'B{batch}/results' / (digest(sid) + '.json')
        if path.exists():
            continue
        pub, kernel = public[sid]['views'][0]['public'], kernels[sid]
        schema = schema_for(kernel)
        prompt = PROMPT + '\nSame author event/argument meanings: ' + native_encoding.ONTOLOGY
        messages = render_messages(prompt, {'current_case': pub, 'unchanged_legal_program': kernel}, schema)
        count = client.tokenize(messages, thinking=False)['count']
        assert count + protocol['executor_profile']['max_tokens'] <= protocol['executor_profile']['context_tokens']
        row = {'source': sid, 'arm': 'GenericView', 'batch': batch, 'input_tokens': count,
            'fallback': False, 'fixed_representation_sha256': digest(schema)}
        try:
            result = client.generate(RUN + ':B' + str(batch) + ':' + sid, source=sid,
                purpose='skill_actor', thinking=False, messages=messages, schema=decoder_schema(schema)[0])
            row['read'] = {k: result[k] for k in ('usage', 'elapsed_seconds', 'finish_reason')}
            assert result['finish_reason'] == 'stop'
            observation = json.loads(result['content'])
            jsonschema.validate(observation, schema)
            row['observation'] = observation
            row['grounded'] = lower(observation, kernel, pub)
            row['execution'] = execute_alternatives(kernel, row['grounded'])
        except Exception as error:
            with ledger.transaction() as db:
                assert not db.execute("select 1 from calls where status='reserved'").fetchone(), 'Reconcile pending request'
            row.update(error=type(error).__name__ + ': ' + str(error), execution={'handled': False, 'answer': None})
        immutable_json(path, row)
        print(json.dumps({'batch': batch, 'source': sid, 'handled': row['execution']['handled'], 'error': row.get('error')}), flush=True)


def score(protocol, batch):
    public = {s['key']: s for s in read(parent.OUT / 'SARA_corrected_TRAIN_views.json')}
    grading = read(parent.PREPARED / 'grading.json')
    rows = []
    for sid in [s for s in protocol['batches'][batch-1] if s in public]:
        row = read(OUT / f'B{batch}/results' / (digest(sid) + '.json'))
        src = public[sid];view = src['views'][0]
        rows.append({**row, 'native_score': grade_view(src['dataset'], view, grading[sid][view['id']], row['execution']['answer'])})
    immutable_json(OUT / f'B{batch}/scored_results.json', {'rows': rows,
        'not_a_semantic_truth_certificate': True, 'goal_complete': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['prepare', 'execute', 'score'])
    parser.add_argument('--batch', type=int, choices=range(1, 9), default=1)
    args = parser.parse_args()
    protocol = prepare()
    if args.phase != 'prepare':
        with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            (execute if args.phase == 'execute' else score)(protocol, args.batch)
