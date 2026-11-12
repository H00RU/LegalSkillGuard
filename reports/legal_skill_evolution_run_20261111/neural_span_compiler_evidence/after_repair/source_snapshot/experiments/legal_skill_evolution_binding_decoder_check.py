"""Exact current-source quote codec regression on the installed Qwen backend.

No generation or model weights loaded. Original host schema remains strict;
the actual acquired quoted clause is reused without labels or invented facts.
"""
import json
from pathlib import Path
import time

import jsonschema

from legal_skill_guard.skill_evolution.runtime import decoder_schema


def run(root):
    import torch
    import xgrammar
    from transformers import AutoTokenizer
    old = root / 'artifacts/legal_skill_evolution_neural_span_compiler_20261112'
    request = json.loads(next((old / 'calls').glob('*/request.json')).read_text())
    schema = request['payload']['response_format']['json_schema']['schema']
    asset = json.loads((old / 'shared_asset.json').read_text())
    frame = next(f for f in asset['frames'] if '"' in f['example']['quote'])
    value = {'records': [{'frame_id': frame['id'], **frame['example']}]}
    jsonschema.validate(value, schema)
    profile = json.loads((root / 'configs/legal_skill_evolution_formal_v5_20261111.json').read_text())
    model = Path(profile['executor']['model_root'])
    tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=True)
    vocab_size = json.loads((model / 'config.json').read_text())['vocab_size']
    torch.set_num_threads(1)
    compiler = xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(tokenizer,
        vocab_size=vocab_size), max_threads=1)
    wire, checks = decoder_schema(schema)
    tokens = tokenizer.encode(json.dumps(value, ensure_ascii=False), add_special_tokens=False)
    results = {}
    for name, candidate in [('original', schema), ('repaired_decoder', wire)]:
        start = time.monotonic();compiled = compiler.compile_json_schema(json.dumps(candidate))
        compile_seconds = time.monotonic() - start
        matcher = xgrammar.GrammarMatcher(compiled)
        mask = xgrammar.allocate_token_bitmask(1, vocab_size);fill = 0;accept = 0;accepted = True;failed = None
        for index, token in enumerate(tokens):
            start = time.monotonic();matcher.fill_next_token_bitmask(mask);fill += time.monotonic() - start
            start = time.monotonic();accepted = matcher.accept_token(token);accept += time.monotonic() - start
            if not accepted:
                failed = {'token_index': index, 'token': tokenizer.decode([token]),
                    'context': tokenizer.decode(tokens[max(0,index-8):index+8])}
                break
        eos = matcher.accept_token(tokenizer.eos_token_id) if accepted else False
        results[name] = {'all_content_tokens_accepted': accepted, 'EOS_accepted': eos,
            'content_tokens': len(tokens), 'processed_tokens': index + 1,
            'compile_seconds': compile_seconds, 'fill_seconds': fill, 'accept_seconds': accept,
            'failed_at': failed}
    assert not results['original']['all_content_tokens_accepted']
    assert results['repaired_decoder']['all_content_tokens_accepted'] and results['repaired_decoder']['EOS_accepted']
    for bad in ['', 'x' * 1801]:
        corrupt = json.loads(json.dumps(value));corrupt['records'][0]['quote'] = bad
        try:jsonschema.validate(corrupt, schema)
        except jsonschema.ValidationError:pass
        else:raise AssertionError('Original host length checks were relaxed')
    result = {'actual_acquired_frame_id': frame['id'], 'actual_value': value,
        'original_host_schema_valid': True, 'original_host_length_checks_retained': True,
        'prompt_schema_unchanged': True, 'deferred_host_checks': checks,
        'new_model_calls': 0, 'results': results}
    (old / 'exact_decoder_repair_evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__ == '__main__':
    x = run(Path(__file__).resolve().parents[1]);print(json.dumps(x['results'],ensure_ascii=False))
