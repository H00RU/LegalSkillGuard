"""Inspect grammar choices at real source77 boundaries; never complete an IR."""
from datetime import datetime, timezone
import base64
import hashlib
import importlib.metadata
import json
from pathlib import Path
import socket
import sqlite3

import xgrammar as xgr
from transformers import AutoTokenizer


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate object key')
        result[key] = value
    return result


def complete_node_boundaries(raw):
    decoder = json.JSONDecoder(object_pairs_hook=unique_object)
    at = 1
    while True:
        at += len(raw[at:]) - len(raw[at:].lstrip())
        key, end = decoder.raw_decode(raw, at)
        at = end + len(raw[end:]) - len(raw[end:].lstrip())
        assert raw[at] == ':'
        at += 1
        at += len(raw[at:]) - len(raw[at:].lstrip())
        if key == 'nodes':
            assert raw[at] == '['
            rows = []
            at += 1
            while True:
                at += len(raw[at:]) - len(raw[at:].lstrip())
                try:
                    value, end = decoder.raw_decode(raw, at)
                except (ValueError, TypeError):
                    return rows
                assert isinstance(value, dict)
                rows.append(end)
                at = end + len(raw[end:]) - len(raw[end:].lstrip())
                if raw[at:at + 1] != ',':
                    return rows
                at += 1
        _, end = decoder.raw_decode(raw, at)
        at = end + len(raw[end:]) - len(raw[end:].lstrip())
        assert raw[at] == ','
        at += 1


def main():
    def denied(*args, **kwargs):
        raise AssertionError('This audit cannot use the network')
    socket.socket.connect = denied
    socket.create_connection = denied
    root = Path(__file__).resolve().parents[2]
    stage = root / 'artifacts/rr_method_runtime_20261107/method_runtime_ast_v1_20261107'
    seal = json.loads((stage / 'seal.json').read_text())
    source = seal['sources']['train'][76]
    source_key = hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    record = json.loads((stage / 'build/sources' / (source_key + '.json')).read_text())
    cfg = json.loads((root / 'configs/rr_v2_preflight.json').read_text())['executor']
    tokenizer = AutoTokenizer.from_pretrained(cfg['model_root'], local_files_only=True)
    vocab = json.loads((Path(cfg['model_root']) / 'config.json').read_text())['vocab_size']
    info = xgr.TokenizerInfo.from_huggingface(tokenizer, vocab_size=vocab)
    compiler = xgr.GrammarCompiler(info, max_threads=1, cache_enabled=False)
    byte_info = xgr.TokenizerInfo([bytes([i]) for i in range(256)] + [b''],
        vocab_size=257, stop_token_ids=[256])
    byte_compiler = xgr.GrammarCompiler(byte_info, max_threads=1, cache_enabled=False)
    rows = []
    with sqlite3.connect('file:' + str(root / seal['ledger_path']) + '?mode=ro', uri=True) as db:
        for call in record['prediction']['calls']:
            cid = seal['run_id'] + ':build:' + source_key + ':' + str(call['step'])
            status, saved = db.execute('select status,result from calls where id=?', (cid,)).fetchone()
            saved = json.loads(saved)
            raw = call['raw_content']
            assert status == 'completed' and saved['content'] == raw and saved['usage'] == call['usage']
            wire_path = Path(saved['artifact_directory']) / 'wire_request.json'
            wire_bytes = wire_path.read_bytes()
            wire = json.loads(wire_bytes)
            body = base64.b64decode(wire['body_b64'])
            assert hashlib.sha256(body).hexdigest() == wire['body_sha256']
            schema = json.loads(body)['response_format']['json_schema']['schema']
            dispatch = json.loads(json.loads((stage / 'build/journals' / source_key /
                ('request' + str(call['step']) + '.json')).read_text())['dispatch_json'])
            assert schema == dispatch['schema']
            contexts = [('byte_grammar', byte_compiler.compile_json_schema(json.dumps(schema), any_whitespace=True)),
                ('Qwen3_tokenizer', compiler.compile_json_schema(json.dumps(schema), any_whitespace=True))]
            boundaries = complete_node_boundaries(raw)
            assert boundaries
            for index in sorted({0, len(boundaries) - 1}):
                prefix = raw[:boundaries[index]]
                checks = []
                for label, ctx in contexts:
                    for continuation, expected in [(']', True), (',', True), ('}', False)]:
                        matcher = xgr.GrammarMatcher(ctx)
                        prefix_ok = matcher.accept_string(prefix)
                        assert prefix_ok
                        mask_allowed = None
                        if label == 'Qwen3_tokenizer':
                            tokens = tokenizer.encode(continuation, add_special_tokens=False)
                            assert len(tokens) == 1
                            token = tokens[0]
                            mask = xgr.allocate_token_bitmask(1, info.vocab_size)
                            matcher.fill_next_token_bitmask(mask)
                            mask_allowed = bool((int(mask[0, token // 32].item()) >> (token % 32)) & 1)
                        accepted = matcher.accept_string(continuation)
                        checks.append({'backend': label, 'continuation': continuation,
                            'prefix_accepted': prefix_ok, 'continuation_accepted': accepted,
                            'standalone_token_mask_allowed': mask_allowed, 'expected': expected})
                        assert accepted == expected and (mask_allowed is None or mask_allowed == expected)
                rows.append({'call_id': cid, 'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                    'wire_body_sha256': wire['body_sha256'], 'complete_nodes_in_actual_prefix': len(boundaries),
                    'boundary_after_node_index': index, 'prefix_characters': len(prefix),
                    'prefix_sha256': hashlib.sha256(prefix.encode()).hexdigest(), 'choices': checks})
            assert wire_path.read_bytes() == wire_bytes
    result = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'run_id': seal['run_id'],
        'source_position': 77, 'source': source, 'xgrammar_version': importlib.metadata.version('xgrammar'),
        'any_whitespace': True, 'rows': rows, 'network_blocked': True, 'model_weights_loaded': False,
        'new_model_or_oracle_or_grading_calls': 0, 'original_outputs_or_ledger_modified': False,
        'candidate_program_reconstructed': False, 'core_semantic_success_claimed': False,
        'interpretation': 'At these exact real character-prefix boundaries, both ending the nodes array and '
            'continuing it are admitted by the captured schema in the pinned backend. This is a narrow '
            'syntactic choice check, not a replay of unavailable sampled token IDs, model logits, all '
            'generation positions, or successful complete IR. Missing clauses/scopes/query remain missing.'}
    path = Path(__file__).with_name(seal['run_id'] + '_source77_array_choices_audit.json')
    path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'path': str(path.relative_to(root)), 'boundaries_checked': len(rows),
        'closure_and_continuation_allowed': True, 'invalid_object_closure_rejected': True,
        'new_model_calls': 0, 'core_success': False}))


if __name__ == '__main__':
    main()
