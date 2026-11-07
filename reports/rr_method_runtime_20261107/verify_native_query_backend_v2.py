"""Pinned backend query/type-order checks; tokenizers only, no model weights."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import socket

import xgrammar as xgr
from transformers import AutoTokenizer

from legal_skill_guard.rr.source_program import program_schema


def main():
    def denied(*args, **kwargs):
        raise AssertionError('No network in backend grammar verification')
    socket.socket.connect = denied
    socket.create_connection = denied
    root = Path(__file__).resolve().parents[2]
    sources = {s['key']: s for s in json.loads((root / 'data/packets/rr_v2/public_train.json').read_text())['sources']}
    fixture = json.loads((root / 'tests/fixtures/rr_actual_method_c6_native_queries.json').read_text())
    byte_info = xgr.TokenizerInfo([bytes([i]) for i in range(256)] + [b''], vocab_size=257, stop_token_ids=[256])
    compiler = xgr.GrammarCompiler(byte_info, max_threads=1, cache_enabled=False)
    cfg = json.loads((root / 'configs/rr_v2_preflight.json').read_text())['executor']
    tokenizer = AutoTokenizer.from_pretrained(cfg['model_root'], local_files_only=True)
    vocab = json.loads((Path(cfg['model_root']) / 'config.json').read_text())['vocab_size']
    info = xgr.TokenizerInfo.from_huggingface(tokenizer, vocab_size=vocab)
    token_compiler = xgr.GrammarCompiler(info, max_threads=1, cache_enabled=False)
    checks = []; byte_cache = {}; token_cache = {}
    def check(label, schema, value, expected, actual_tokens=True):
        raw = json.dumps(value, ensure_ascii=False)
        key = json.dumps(schema)
        if key not in byte_cache:byte_cache[key] = compiler.compile_json_schema(key, any_whitespace=True)
        compiled = byte_cache[key]
        accepted = xgr.GrammarMatcher(compiled).accept_string(raw)
        item = {'case': label, 'expected': expected, 'byte_grammar_accepts': accepted,
                'value_sha256': hashlib.sha256(raw.encode()).hexdigest()}
        assert accepted == expected, item
        if actual_tokens:
            if key not in token_cache:token_cache[key] = token_compiler.compile_json_schema(key, any_whitespace=True)
            compiled = token_cache[key]
            matcher = xgr.GrammarMatcher(compiled)
            mask = xgr.allocate_token_bitmask(1, info.vocab_size)
            first = None
            for index, token in enumerate(tokenizer.encode(raw, add_special_tokens=False)):
                matcher.fill_next_token_bitmask(mask)
                allowed = bool((int(mask[0, token // 32].item()) >> (token % 32)) & 1)
                accepted_token = matcher.accept_token(token)
                if not allowed or not accepted_token:
                    first = {'index': index, 'token_id': token, 'mask_allowed': allowed,
                             'matcher_accepted': accepted_token}
                    break
            item.update(all_actual_Qwen_tokens_accepted=first is None, first_token_rejection=first)
            assert (first is None) == expected, item
        checks.append(item)
    for record in fixture['records']:
        query = json.loads(record['content'])['query']
        schema = program_schema(sources[record['source']])
        current = {'$defs': schema['$defs'], **schema['properties']['query']}
        check(record['call_id'] + ':old_query', fixture['old_query_schema'], query, True)
        check(record['call_id'] + ':current_query', current, query, False)
    cases = [('SARA_v2_Binary', 'Entailment', 'Contradiction', 'Unknown'),
             ('ProofWriter_OWA_depth5', 'True', 'Unknown', 'Entailment'),
             ('ContractNLI', 'Entailment', 'NotMentioned', 'True'),
             ('RuleArena_Airline', 0, 1, 'Entailment'),
             ('OpenExempt', {'op': 'object', 'args': []}, None, 'Entailment')]
    for dataset, yes, no, wrong in cases:
        source = next(s for s in sources.values() if s['dataset'] == dataset)
        schema = program_schema(source)
        current = {'$defs': schema['$defs'], **schema['properties']['query']}
        query = {'op': 'if', 'args': [{'op': 'eq', 'args': ['public string', 'Entailment']}, yes, no]}
        check(dataset + ':valid_native_syntax', current, query, True)
        check(dataset + ':wrong_native_label', current, wrong, False)
        if dataset in {'SARA_v2_Binary', 'RuleArena_Airline'}:
            for depth in (16, 17):
                value = yes
                for _ in range(depth):
                    value = {'op': 'if', 'args': [True, value, no]}
                check(dataset + ':result_depth_' + str(depth), current, value, depth == 16)
    source = sources[fixture['records'][0]['source']]
    schema = program_schema(source)
    binding = {'$defs': schema['$defs'], **schema['$defs']['binding']}
    # Identical mapping values, different serialization order; syntax only.
    check('binding:type_then_evidence_then_value', binding,
          {'name': 'n_literal', 'type': 'integer', 'sources': ['s3'], 'value': 3}, True)
    check('binding:old_value_first_order', binding,
          {'name': 'n_literal', 'value': 3, 'type': 'integer', 'sources': ['s3']}, False)
    actual = json.loads((root / 'tests/fixtures/rr_actual_probe_v4_expressions.json').read_text())
    source = sources[actual['source']]; full = program_schema(source)
    expr_schema = {'$defs': full['$defs'], **full['$defs']['expr']}
    bad = [c['value'] for c in json.loads(actual['raw_content'])['clauses'] if c['value'].get('op') == 'if' and len(c['value']['args']) != 3]
    for size in sorted({len(e['args']) for e in bad}):
        value = next(e for e in bad if len(e['args']) == size)
        check('actual_v4_if_arity_' + str(size) + ':old', actual['old_expression_schema'], value, True)
        check('actual_v4_if_arity_' + str(size) + ':new', expr_schema, value, False)
    operators = {'if': [True, 1, 0], 'not': [True], 'xor': [True, False], 'eq': [1, 1], 'ne': [1, 2],
        'lt': [1, 2], 'le': [1, 2], 'sub': [2, 1], 'scale': [2, 1], 'divide_constant': [2, 1],
        'ceil_divide_constant': [2, 1], 'number_at': [{'op': 'array', 'args': [1]}, 0],
        'min': [1], 'max': [1], 'and': [], 'or': [], 'add': [], 'array': [], 'pair': ['key', 1], 'object': [], 'concat': []}
    for op, args in operators.items():check('operator_' + op, expr_schema, {'op': op, 'args': args}, True)
    for op, args in [('divide_constant', [1, 0]), ('ceil_divide_constant', [1, -1]),
        ('scale', [{'var': 'n_scale'}, 1]), ('number_at', [{'op': 'array', 'args': [1]}, {'var': 'n_index'}])]:
        check('invalid_literal_operand_' + op, expr_schema, {'op': op, 'args': args}, False)
    result = {'checked_utc': datetime.now(timezone.utc).isoformat(),
              'xgrammar_version': importlib.metadata.version('xgrammar'), 'checks': checks,
              'network_blocked': True, 'new_model_calls': 0, 'new_oracle_views': 0,
              'model_weights_loaded': False, 'service_environment_modified': False,
              'old_responses_modified': False,
              'interpretation': 'Actual wrong-query rejection and syntax/mask checks only; not benchmark or A/B semantic success.'}
    (root / 'reports/rr_method_runtime_20261107/native_query_backend_v2.json').write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'checks'}, ensure_ascii=False))
    print(json.dumps({'checked_cases': len(checks), 'all_expected_memberships_and_masks_match': True}))


if __name__ == '__main__':
    main()
