"""Replay the settled TRAIN decoder language without generation or labels.

Counterfactual array values test grammar freedom only. They are never bound,
executed, scored as answers, or substituted for the acquired records.
"""
import base64
import copy
import hashlib
import json
from pathlib import Path
import time

import jsonschema

from legal_skill_guard.skill_evolution.runtime import decoder_schema


def run(root):
    import torch
    import xgrammar
    from transformers import AutoTokenizer

    folder = root / 'artifacts/legal_skill_evolution_relational_acquisition_v2_20261113'
    read = lambda p: json.loads(p.read_text())
    completed = read(folder / 'completed.json')
    profile = read(root / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    model = Path(profile['executor']['model_root'])
    tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=True)
    vocab_size = read(model / 'config.json')['vocab_size']
    torch.set_num_threads(1)
    compiler = xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(
        tokenizer, vocab_size=vocab_size), max_threads=1)
    calls = {read(p).get('id'): p.parent for p in (folder / 'calls').glob('*/request.json')}
    arrays, replays, variants = [], [], []

    def replay(compiled, content):
        matcher = xgrammar.GrammarMatcher(compiled)
        tokens = tokenizer.encode(content, add_special_tokens=False)
        start = time.monotonic()
        for index, token in enumerate(tokens):
            if not matcher.accept_token(token):
                return {'accepted': False, 'tokens': len(tokens), 'failed_token_index': index,
                    'failed_token': tokenizer.decode([token]), 'seconds': time.monotonic() - start}
        return {'accepted': True, 'tokens': len(tokens), 'EOS_accepted': matcher.accept_token(
            tokenizer.eos_token_id), 'seconds': time.monotonic() - start}

    for arm in ('ScopedAcquisition', 'FreeAcquisition'):
        spec = read(folder / arm / 'frozen_candidate.json')['spec']
        for result in completed['results'][arm]:
            event = result.get('source_event')
            if not event:
                continue  # The actual truncated response is preserved, not repaired here.
            call = calls[event['call_id']]
            request, response = read(call / 'request.json'), read(call / 'result.json')
            schema = request['payload']['response_format']['json_schema']['schema']
            expected, checks = decoder_schema(schema)
            wire = read(call / 'wire_request.json')
            payload = json.loads(base64.b64decode(wire['body_b64']))
            actual = payload['response_format']['json_schema']['schema']
            assert actual == expected
            compiled = compiler.compile_json_schema(json.dumps(actual))
            baseline = replay(compiled, response['content'])
            assert baseline['accepted'] and baseline['EOS_accepted'], result['source']
            replays.append({'arm': arm, 'source': result['source'], 'call_id': event['call_id'],
                'actual_content_sha256': hashlib.sha256(response['content'].encode()).hexdigest(),
                'wire_equals_existing_decoder_adapter': True, 'actual_response': baseline})
            value = json.loads(response['content'])
            selected = None
            for frame in spec['frames']:
                for index, instance in enumerate(value[frame['name']]):
                    for field in frame['fields']:
                        observed = instance['fields'][field['name']]['value']
                        if field['type'] != 'array' or observed is None:
                            continue
                        arrays.append({'arm': arm, 'source': result['source'],
                            'frame': frame['name'], 'instance_index': index, 'field': field['name'],
                            'observed_count': len(observed), 'domain_count': len(field['domain']),
                            'equals_entire_domain': set(observed) == set(field['domain'])})
                        if selected is None and len(observed) > 1:
                            selected = (frame['name'], index, field['name'], observed)
            # Both real failure contexts are fixed before running this audit.
            if arm == 'ScopedAcquisition' and result['source'].split(':')[1].startswith(('354623', '5cad3f')):
                assert selected is not None
                frame, index, field, observed = selected
                for label, replacement in [('singleton', observed[:1]), ('empty', []), ('unknown', None)]:
                    candidate = copy.deepcopy(value)
                    candidate[frame][index]['fields'][field]['value'] = replacement
                    jsonschema.validate(candidate, schema)
                    outcome = replay(compiled, json.dumps(candidate, ensure_ascii=False))
                    assert outcome['accepted'] and outcome['EOS_accepted'], (result['source'], label)
                    variants.append({'source': result['source'], 'frame': frame, 'instance_index': index,
                        'field': field, 'counterfactual': label, 'original_host_schema_valid': True,
                        'decoder': outcome, 'is_legal_semantic_repair': False})
    assert len(replays) == 19 and len(variants) == 6
    by_arm = {arm: {'known_arrays': sum(r['arm'] == arm for r in arrays),
        'entire_domain_arrays': sum(r['arm'] == arm and r['equals_entire_domain'] for r in arrays)}
        for arm in ('ScopedAcquisition', 'FreeAcquisition')}
    output = {'new_model_calls': 0, 'labels_loaded': False, 'model_weights_loaded': False,
        'actual_schema_response_replays': replays, 'array_observations': arrays,
        'array_counts_by_arm': by_arm, 'counterfactual_grammar_only_checks': variants,
        'finding': 'The actual wire grammars accept singleton, empty and null alternatives in the two real failure contexts. Copying the complete role domain is not forced by the accepted language. This does not rule out softer model/grammar probability or prompt interactions.',
        'no_outputs_repaired_or_semantics_invented': True, 'goal_complete': False}
    target = folder / 'postrun_audit' / 'decoder_array_audit.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('Preserve the prior audit; do not overwrite it')
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    return output


if __name__ == '__main__':
    result = run(Path(__file__).resolve().parents[1])
    print(json.dumps({'arrays': result['array_counts_by_arm'],
        'actual_replays': len(result['actual_schema_response_replays']),
        'counterfactuals': len(result['counterfactual_grammar_only_checks']),
        'new_model_calls': 0}, ensure_ascii=False))
