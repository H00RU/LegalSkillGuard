"""Verify current code envelopes using the pinned decoder, without generation."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import socket

import xgrammar as xgr
from transformers import AutoTokenizer

from legal_skill_guard.rr.source_code import compiler_response_schema, render_source_code
from legal_skill_guard.rr.source_execution import prepare_followup
from legal_skill_guard.rr.source_program import compile_source


def main():
    def denied(*args, **kwargs):
        raise AssertionError('No network in code envelope backend checks')
    socket.socket.connect = denied
    socket.create_connection = denied
    root = Path(__file__).resolve().parents[2]
    record = json.loads((root / 'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())
    program = record['canonical_program']
    code = render_source_code(program)
    source_schema = compiler_response_schema()
    compiled = compile_source(record['source'], program)
    prepared = prepare_followup(compiled, compilation='full', thinking=False,
        tokenize=lambda messages, **kwargs: {'count': len(json.dumps(messages))},
        request_config={'context_tokens': 100000, 'max_tokens': 8192})
    rows = [{'name': name, 'value': None, 'evidence': ''} for name in prepared['names']]
    cases = [
        ('actual_scope_code', source_schema, {'code': code}, True),
        ('legacy_IR_rejected', source_schema, program, False),
        ('side_answer_rejected', source_schema, {'code': code, 'answer': 'Entailment'}, False),
        ('missing_code_rejected', source_schema, {}, False),
        ('nonstring_code_rejected', source_schema, {'code': 3}, False),
        ('unicode_and_escaped_string', source_schema, {'code': '# 条款\nquery = "quoted \\\"text\\\""\n'}, True),
        ('joint_accepted_translation_and_facts', prepared['schema'],
            {'program': {'code': code}, 'factual_observations': rows}, True),
        ('joint_legacy_IR_rejected', prepared['schema'],
            {'program': program, 'factual_observations': rows}, False),
        ('joint_side_answer_rejected', prepared['schema'],
            {'program': {'code': code}, 'factual_observations': rows, 'answer': 'Entailment'}, False),
    ]
    cfg = json.loads((root / 'configs/rr_v2_preflight.json').read_text())['executor']
    tokenizer = AutoTokenizer.from_pretrained(cfg['model_root'], local_files_only=True)
    size = json.loads((Path(cfg['model_root']) / 'config.json').read_text())['vocab_size']
    byte_info = xgr.TokenizerInfo([bytes([i]) for i in range(256)] + [b''], vocab_size=257, stop_token_ids=[256])
    info = xgr.TokenizerInfo.from_huggingface(tokenizer, vocab_size=size)
    byte_compiler = xgr.GrammarCompiler(byte_info, max_threads=1, cache_enabled=False)
    token_compiler = xgr.GrammarCompiler(info, max_threads=1, cache_enabled=False)
    byte_cache, token_cache, checks = {}, {}, []
    for name, schema, value, expected in cases:
        schema_text = json.dumps(schema, ensure_ascii=False)
        text = json.dumps(value, ensure_ascii=False)
        if schema_text not in byte_cache:
            byte_cache[schema_text] = byte_compiler.compile_json_schema(schema_text, any_whitespace=True)
            token_cache[schema_text] = token_compiler.compile_json_schema(schema_text, any_whitespace=True)
        byte_accepted = xgr.GrammarMatcher(byte_cache[schema_text]).accept_string(text)
        matcher = xgr.GrammarMatcher(token_cache[schema_text])
        mask = xgr.allocate_token_bitmask(1, info.vocab_size)
        first_rejection = None
        for index, token in enumerate(tokenizer.encode(text, add_special_tokens=False)):
            matcher.fill_next_token_bitmask(mask)
            allowed = bool((int(mask[0, token // 32].item()) >> (token % 32)) & 1)
            accepted = matcher.accept_token(token)
            if not allowed or not accepted:
                first_rejection = {'index': index, 'token_id': token, 'mask_allowed': allowed, 'accepted': accepted}
                break
        item = {'case': name, 'expected': expected, 'byte_accepted': byte_accepted,
            'all_actual_Qwen_tokens_accepted': first_rejection is None,
            'first_rejection': first_rejection, 'value_sha256': hashlib.sha256(text.encode()).hexdigest()}
        assert byte_accepted == expected and (first_rejection is None) == expected, item
        checks.append(item)
    receipt = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks,
        'xgrammar_version': importlib.metadata.version('xgrammar'),
        'model_weights_loaded': False, 'network_blocked': True, 'new_model_calls': 0,
        'new_oracle_views': 0, 'interpretation': 'Only code/joint wire syntax and token-mask evidence; internal SourceIR and all existing semantic checks still required.'}
    output = Path(__file__).with_name('source_code_wire_backend_v1.json')
    output.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'checks': len(checks), 'all_passed': True, 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
