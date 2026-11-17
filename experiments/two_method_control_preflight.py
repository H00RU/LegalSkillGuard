"""Read-only native bundle/tokenizer preflight; cannot generate model text."""
import argparse
import hashlib
import json
from pathlib import Path

from legal_skill_guard.paired_interfaces.control_answers import source_bundle, wire_schema
from legal_skill_guard.paired_interfaces.control_learning import direct_program
from legal_skill_guard.rr.client import ExecutorClient
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/two_method_followthrough_20261116'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tokenize', action='store_true')
    args = parser.parse_args()
    lock = json.loads((BASE / 'pilot_lock.json').read_text())
    source_lock = json.loads((BASE / 'prepared/source_lock.json').read_text())
    path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    if hashlib.sha256(path.read_bytes()).hexdigest() != source_lock['prepared_sha256']['train']['public']:
        raise ValueError('The fixed original TRAIN public bytes changed')
    train = {s['key']: s for s in json.loads(path.read_text())}
    program, requests = direct_program(), []
    for row in lock['rows']:
        source = train[row['key']]
        if digest(source) != row['public_sha256']:
            raise ValueError('A fixed source changed')
        bundle = source_bundle(source)
        schema = record_schema({'value': wire_schema(source['dataset'], bundle)})
        messages = [{'role': 'system', 'content': program['predicates'][0]['prompt']
            + '\nReturn compact JSON matching this exact schema: '
            + json.dumps(schema, ensure_ascii=False, separators=(',', ':'))},
            {'role': 'user', 'content': json.dumps({'public': bundle['public'],
                'answer_schema': bundle['answer_schema']}, ensure_ascii=False, sort_keys=True)}]
        requests.append({'source': row['key'], 'dataset': row['dataset'], 'schema': schema,
                         'messages': messages, 'thinking': False})
    binding = {'executor': lock['executor'], 'direct_program': program, 'requests': requests}
    target = BASE / 'control_native_preflight_v1' / digest(binding)
    immutable_json(target / 'requests.json', binding)
    report = {'sources': len(requests), 'schemas': len(requests), 'generation_requests': 0,
              'grading_or_reference_graphs_opened': False}
    if args.tokenize:
        client = ExecutorClient(None, target, lock['executor'])
        readiness = client.readiness()
        tokens = []
        for request in requests:
            result = client.tokenize(request['messages'], thinking=False)
            tokens.append({'source': request['source'], 'dataset': request['dataset'],
                'input_tokens': result['count'],
                'input_plus_reserved_output': result['count'] + lock['executor']['max_tokens'],
                'within_original_context': result['count'] + lock['executor']['max_tokens'] <= lock['executor']['context_tokens'],
                'serving_template_token_sha256': digest(result['tokens'])})
        report.update(readiness=readiness, sources_tokenized=tokens,
                      all_within_original_context=all(t['within_original_context'] for t in tokens))
        immutable_json(target / 'tokenization.json', report)
    print(json.dumps({'artifact_root': str(target.relative_to(ROOT)),
                      'sources': len(requests), 'generation_requests': 0,
                      'all_within_original_context': report.get('all_within_original_context')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
