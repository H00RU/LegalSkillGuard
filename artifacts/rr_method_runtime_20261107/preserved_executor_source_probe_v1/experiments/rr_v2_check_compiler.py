"""CPU-only serving-grammar and tokenizer regression; no weights or network."""
from __future__ import annotations

import hashlib
import json
import socket
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


def main():
    import xgrammar
    from transformers import AutoTokenizer

    from legal_skill_guard.rr.compiler_prompt import format_examples
    from legal_skill_guard.rr.coverage import digest
    from legal_skill_guard.rr.cumulative_repair import closed_inputs, inputs, prompts, schema_for
    from legal_skill_guard.rr.preflight import atomic_json
    from legal_skill_guard.rr.strict_contract import CITATION_PATTERN, TARGETS

    root = Path(__file__).resolve().parents[1]
    cfg, data = inputs(root)
    def deny(*args, **kwargs):
        raise RuntimeError('No network during actual decoder/tokenizer regression')
    records = []
    with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny):
        model = Path(cfg['executor']['model_root'])
        tok = AutoTokenizer.from_pretrained(str(model), local_files_only=True, trust_remote_code=False)
        vocab_size = json.loads((model / 'config.json').read_text())['vocab_size']
        compiler = xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(tok, vocab_size=vocab_size), max_threads=1)
        malformed = '"A§B" } trailing§invalid"'
        old_matcher = xgrammar.GrammarMatcher(compiler.compile_json_schema({'type': 'string', 'pattern': '^.+§.+$'}))
        new_matcher = xgrammar.GrammarMatcher(compiler.compile_json_schema({'type': 'string', 'pattern': CITATION_PATTERN}))
        if not old_matcher.accept_string(malformed) or new_matcher.accept_string(malformed):
            raise AssertionError('Exact quote-boundary backend regression was not reproduced/fixed')
        actual = json.loads((root / 'tests/fixtures/rr_strict_actual_failure.json').read_text())
        for source_id in data.order:
            source = data.public(source_id)
            if source['dataset'] not in TARGETS:
                continue
            schema = schema_for(root, source)
            grammar = compiler.compile_json_schema(schema, strict_mode=True)
            cases = []
            index = {'RuleArena_Airline': 0, 'SARA_v2_Binary': 1, 'OpenExempt': 2}[source['dataset']]
            for example in [format_examples()[index]]:
                p = deepcopy(example['proposal'])
                bindings = closed_inputs(root, source)
                if bindings:
                    p['program']['body']['bindings'] = bindings
                    p['program']['body']['query'] = {'op': 'object', 'args': [
                        {'op': 'pair', 'args': [family, {'op': 'object', 'args': [
                            {'op': 'pair', 'args': [{'var': b['name']}, {'op': 'array', 'args': []}]}
                            for b in bindings if b['name'].startswith('s_asset')]}]} for family in ['EC', 'EV']]}
                if source['dataset'] == 'OpenExempt':
                    p['answer'] = {'EC': {}, 'EV': {}}
                elif source['dataset'] == 'SARA_v2_Binary':
                    p['answer'] = 'Entailment'
                cases.append((True, p))
                if bindings:
                    nonempty = deepcopy(p)
                    for family_pair in nonempty['program']['body']['query']['args']:
                        family, mapping = family_pair['args']
                        for field in mapping['args']:
                            field['args'][1]['args'] = ['Toy Rule §1'] if family == 'EC' else [
                                {'op': 'object', 'args': [{'op': 'pair', 'args': ['citation', 'Toy Rule §1']},
                                    {'op': 'pair', 'args': ['claim_value', {'var': 'n_value1'}]}]}]
                    cases.append((True, nonempty))
                    actual95 = json.loads((root / 'tests/fixtures/rr_actual_failure_95.json').read_text())
                    cases.append((False, json.loads(actual95['content'])))
            for query in [ {'op': 'and', 'args': ['s157']}, {'op': 'if', 'args': ['s0', 1, 0]},
                           {'op': 'add', 'args': ['5', 0]}, {'op': 'if', 'args': [True]} ]:
                p = deepcopy(cases[0][1])
                p['program']['body']['query'] = query
                cases.append((False, p))
            p = deepcopy(cases[0][1])
            p['program']['body']['source_links'] = {'s0': ['s0']}
            cases.append((False, p))
            p = json.loads(actual['raw_response']['choices'][0]['message']['content'])
            cases.append((False, p))
            for expected, p in cases:
                matcher = xgrammar.GrammarMatcher(grammar)
                tokens = tok.encode(json.dumps(p, ensure_ascii=False), add_special_tokens=False)
                ok = True
                for i, token in enumerate(tokens):
                    if not matcher.accept_token(token):
                        ok = False
                        break
                ok = ok and matcher.accept_token(tok.eos_token_id) and matcher.is_terminated()
                if ok != expected:
                    raise AssertionError((source_id, expected, i, tok.decode(tokens[max(0, i-20):i+20])))
            messages = prompts(root, source)
            tokens = tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=True)
            fits = len(tokens) + cfg['executor']['max_tokens'] <= cfg['executor']['context_tokens']
            if not fits:
                raise ValueError('Full public input exceeds context; no truncation allowed')
            records.append({'source': source_id, 'schema_hash': digest(schema), 'messages_hash': digest(messages),
                            'schema_wire_sha256': hashlib.sha256(json.dumps(schema, ensure_ascii=False).encode()).hexdigest(),
                            'decoder_cases': len(cases), 'context_fits': fits,
                            'tokenization': {'tokens': tokens, 'count': len(tokens), 'max_model_len': cfg['executor']['context_tokens']}})
            print(json.dumps({'checked': source_id, 'cases': len(cases), 'prompt_tokens': len(tokens)}), flush=True)
    atomic_json(root / 'reports/rr_v2_evidence/cumulative_repair/backend_precheck.json',
        {'network_blocked': True, 'model_weights_loaded': False, 'labels_loaded': False,
         'executor_requests': 0, 'teacher_requests': 0, 'records': records,
         'regex_quote_boundary_regression': {'old_accepts_invalid_JSON': True, 'fixed_rejects_invalid_JSON': True}})


if __name__ == '__main__':
    main()
