"""Replay real complete outputs and one preserved real-source IR, CPU only.

The positive control is a historical teacher compilation, never a new executor
success. No candidate is repaired and no control is supplied to a live model.
"""
from copy import deepcopy
from datetime import datetime, timezone
import base64
import hashlib
import importlib.metadata
import json
from pathlib import Path
import socket
import sqlite3

import xgrammar as xgr
from jsonschema import Draft202012Validator, ValidationError
from transformers import AutoTokenizer

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.compiler_contract import encode_compiler_program, decode_compiler_response
from legal_skill_guard.rr.source_execution import assess_source
from legal_skill_guard.rr.source_inference import _decode
from legal_skill_guard.rr.wire_validation import validate_wire


def order_for_schema(value, schema, root):
    """Reorder object keys only; preserve every decoded JSON value exactly."""
    if '$ref' in schema:
        target = root
        for part in schema['$ref'].removeprefix('#/').split('/'):
            target = target[part]
        return order_for_schema(value, {**target, **{k: v for k, v in schema.items() if k != '$ref'}}, root)
    for union in ('anyOf', 'oneOf'):
        if union in schema:
            for branch in schema[union]:
                if Draft202012Validator({'$defs': root['$defs'], **branch}).is_valid(value):
                    return order_for_schema(value, branch, root)
            raise AssertionError('No schema branch accepts the unchanged value')
    if isinstance(value, dict):
        properties = schema.get('properties', {})
        assert set(value) <= set(properties)
        return {key: order_for_schema(value[key], child, root)
                for key, child in properties.items() if key in value}
    if isinstance(value, list):
        prefix = schema.get('prefixItems', [])
        return [order_for_schema(item, prefix[i] if i < len(prefix) else schema['items'], root)
                for i, item in enumerate(value)]
    return value


def main():
    def denied(*args, **kwargs):
        raise AssertionError('No network or model calls in this audit')
    socket.socket.connect = denied
    socket.create_connection = denied
    root = Path(__file__).resolve().parents[2]
    folder = Path(__file__).parent
    stage = root / 'artifacts/rr_method_runtime_20261107/method_runtime_ast_v1_20261107'
    seal = json.loads((stage / 'seal.json').read_text())
    assert science_files(root) == seal['files']
    state = json.loads((stage / 'build/state.json').read_text())
    count = state['complete_sources']
    public = {s['key']: s for s in json.loads((root / 'data/packets/rr_v2/public_train.json').read_text())['sources']}
    library = SkillLibrary(stage='formal_train')
    rows = []
    with sqlite3.connect('file:' + str(root / seal['ledger_path']) + '?mode=ro', uri=True) as db:
        for index, sid in enumerate(seal['sources']['train'][:count]):
            record = json.loads((stage / 'build/sources' / (digest(sid) + '.json')).read_text())
            assert digest(record) == state['source_hashes'][index]
            assert record['library_before_hash'] == digest(library.export())
            for call in record['prediction']['calls']:
                raw = call['raw_content']
                try:
                    json.loads(raw)
                except (ValueError, TypeError):
                    continue
                cid = seal['run_id'] + ':build:' + digest(sid) + ':' + str(call['step'])
                status, saved = db.execute('select status,result from calls where id=?', (cid,)).fetchone()
                saved = json.loads(saved)
                assert status == 'completed' and saved['content'] == raw and saved['usage'] == call['usage']
                dispatch = json.loads(json.loads((stage / 'build/journals' / digest(sid) /
                    ('request' + str(call['step']) + '.json')).read_text())['dispatch_json'])
                wire = json.loads((Path(saved['artifact_directory']) / 'wire_request.json').read_text())
                body = base64.b64decode(wire['body_b64'])
                assert hashlib.sha256(body).hexdigest() == wire['body_sha256']
                assert json.loads(body)['response_format']['json_schema']['schema'] == dispatch['schema']
                schema_valid, reproduced = False, None
                try:
                    parsed = _decode(raw)
                    validate_wire(parsed, dispatch['schema'])
                    schema_valid = True
                    program = decode_compiler_response(parsed, public[sid], library.export())
                    candidate = compile_source(public[sid], program, library=library.export())
                    assess_source(candidate)
                except Exception as exc:
                    reproduced = {'type': type(exc).__name__,
                        'message': exc.message if isinstance(exc, ValidationError) else str(exc)}
                    if isinstance(exc, ValidationError):
                        reproduced['field_path'] = list(exc.path)
                recorded = deepcopy(call['analysis'].get('error'))
                assert reproduced == recorded, (cid, reproduced, recorded)
                rows.append({'call_id': cid, 'source': sid, 'source_position': index + 1,
                    'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                    'wire_body_sha256': wire['body_sha256'], 'finish_reason': saved['finish_reason'],
                    'usage': saved['usage'], 'wire_schema_valid': schema_valid,
                    'recorded_error_reproduced': True, 'error': reproduced,
                    'current_model_IR_accepted': reproduced is None})
            if record['learning'].get('learned_pattern'):
                library.add(record['learning']['learned_pattern'], source=sid)
        fixture_path = root / 'tests/fixtures/rr_scope_v5_binding_projection.json'
        fixture = json.loads(fixture_path.read_text())
        sid = fixture['source']['key']
        assert fixture['source']['public'] == public[sid]['public']
        assert fixture['source']['content_hash'] == public[sid]['content_hash']
        canonical = fixture['canonical_program']
        compiled = compile_source(public[sid], canonical)
        program = encode_compiler_program(canonical, public[sid])
        request_path = stage / 'build/journals' / digest(sid) / 'request0.json'
        schema = json.loads(json.loads(request_path.read_text())['dispatch_json'])['schema']
        validate_wire(program, schema)
        assert decode_compiler_response(program, public[sid]) == canonical
        ordered = order_for_schema(program, schema, schema)
        assert ordered == program and digest(ordered) == digest(program)
        before = assess_source(compiled)
        text = json.dumps(ordered, ensure_ascii=False, separators=(',', ':'))
        cfg = seal['config']['executor']
        tokenizer = AutoTokenizer.from_pretrained(cfg['model_root'], local_files_only=True)
        vocab = json.loads((Path(cfg['model_root']) / 'config.json').read_text())['vocab_size']
        info = xgr.TokenizerInfo.from_huggingface(tokenizer, vocab_size=vocab)
        compiler = xgr.GrammarCompiler(info, max_threads=1, cache_enabled=False)
        context = compiler.compile_json_schema(json.dumps(schema), any_whitespace=True)
        matcher = xgr.GrammarMatcher(context)
        mask = xgr.allocate_token_bitmask(1, info.vocab_size)
        tokens = tokenizer.encode(text, add_special_tokens=False)
        first_rejection = None
        for position, token in enumerate(tokens):
            matcher.fill_next_token_bitmask(mask)
            allowed = bool((int(mask[0, token // 32].item()) >> (token % 32)) & 1)
            accepted = matcher.accept_token(token)
            if not allowed or not accepted:
                first_rejection = {'position': position, 'token_id': token,
                    'mask_allowed': allowed, 'matcher_accepted': accepted}
                break
        eos_allowed = False
        if first_rejection is None:
            matcher.fill_next_token_bitmask(mask)
            eos = tokenizer.eos_token_id
            eos_allowed = bool((int(mask[0, eos // 32].item()) >> (eos % 32)) & 1)
        result = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'run_id': seal['run_id'],
            'committed_sources': count, 'complete_actual_response_count': len(rows),
            'complete_actual_responses': rows, 'all_recorded_complete_response_errors_reproduced': True,
            'positive_control': {'source': sid, 'public_packet_equal_to_historical_fixture': True,
                'fixture_file_sha256': hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
                'paid_program_origin': fixture['paid_program_origin'],
                'origin_role': 'historical_teacher_compilation_not_current_executor_generation',
                'canonical_program_hash': digest(canonical), 'current_compiler_accepts': True,
                'current_captured_wire_schema_accepts': True, 'scope_codec_preserves_exact_program': True,
                'before_status': before['status'], 'before_reason': before['reason'],
                'wire_object_keys_reordered_only': True, 'wire_sha256': hashlib.sha256(text.encode()).hexdigest(),
                'wire_characters': len(text), 'Qwen_tokenizer_tokens': len(tokens),
                'configured_output_tokens': cfg['max_tokens'],
                'all_tokens_admitted_by_captured_schema_in_pinned_backend': first_rejection is None,
                'first_token_rejection': first_rejection, 'EOS_allowed_after_complete_IR': eos_allowed,
                'natural_language_faithfulness_newly_proven': False,
                'control_counts_as_new_executor_or_core_success': False},
            'xgrammar_version': importlib.metadata.version('xgrammar'), 'any_whitespace': True,
            'new_model_or_oracle_or_grading_calls': 0, 'network_blocked': True,
            'model_weights_loaded': False, 'grading_packets_opened': False,
            'original_candidates_modified': False, 'control_supplied_to_live_model': False,
            'frozen_scientific_files_unchanged': science_files(root) == seal['files'], 'full_goal_complete': False}
        out = folder / (seal['run_id'] + '_ir_entry_contract_audit.json')
        out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
        print(json.dumps({'path': str(out.relative_to(root)), 'sources': count,
            'complete_outputs_replayed': len(rows), 'control_tokens': len(tokens),
            'control_tokens_all_admitted': first_rejection is None, 'control_EOS_allowed': eos_allowed,
            'new_model_calls': 0, 'new_core_success': False}))
        assert first_rejection is None and eos_allowed and len(tokens) < cfg['max_tokens']


if __name__ == '__main__':
    main()
