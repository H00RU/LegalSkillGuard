"""Actual Qwen tokenizer/xgrammar checks, with no generation or weight loading."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
import socket
from unittest.mock import patch

from legal_skill_guard.rr.client import ExecutorClient, request_payload
from legal_skill_guard.rr.compiler_prompt import format_examples
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.engine import proposal_schema, wire_messages
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.readiness import current_binding
from legal_skill_guard.rr.routing import route_prediction

ROOT = Path(__file__).resolve().parents[1]


def main(root=ROOT):
    import xgrammar
    from transformers import AutoTokenizer
    cfg = json.loads((root / 'configs/rr_v2_preflight.json').read_text())
    data = PreflightData(root, root / cfg['source_manifest'])
    profile = cfg['executor']
    assert profile['enable_thinking'] is False
    def deny(*args, **kwargs):
        raise RuntimeError('Decoder/tokenizer offline checks forbid network')
    cases, grammar_cache = [], {}
    with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny):
        model = Path(profile['model_root'])
        tok = AutoTokenizer.from_pretrained(str(model), local_files_only=True, trust_remote_code=False)
        compiler = xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(tok,
            vocab_size=json.loads((model / 'config.json').read_text())['vocab_size']), max_threads=1)
        def matches(schema, value):
            key = digest(schema)
            if key not in grammar_cache:
                grammar_cache[key] = compiler.compile_json_schema(schema, strict_mode=True, any_whitespace=False)
            matcher = xgrammar.GrammarMatcher(grammar_cache[key])
            tokens = tok.encode(json.dumps(value, ensure_ascii=False), add_special_tokens=False)
            return all(matcher.accept_token(t) for t in tokens) and matcher.accept_token(tok.eos_token_id) and matcher.is_terminated()
        def count(prompt):
            tokens = tok.apply_chat_template(prompt, tokenize=True, add_generation_prompt=True, enable_thinking=False)
            return {'count': len(tokens), 'tokens': tokens}
        old = json.loads((root / 'reports/rr_v2_evidence/semantic_preflight/source_status.json').read_text())
        examples = format_examples()
        for index, sid in enumerate(data.order):
            source = data.public(sid)
            schema = proposal_schema(source['dataset'], source=source)
            if source['dataset'] in {'RuleArena_Airline', 'SARA_v2_Binary', 'OpenExempt'}:
                sample = deepcopy(examples[{'RuleArena_Airline':0,'SARA_v2_Binary':1,'OpenExempt':2}[source['dataset']]]['proposal'])
                if source['dataset'] == 'OpenExempt':
                    sample['answer'] = {'EC':{}, 'EV':{}}
                variants = [(True, sample)]
                for bad in [{'op':'and','args':['s157']}, {'op':'if','args':['s0',1,0]},
                            {'op':'add','args':['5',0]}, {'op':'if','args':[True]}]:
                    v = deepcopy(sample); v['program']['body']['query'] = bad
                    variants.append((False, v))
            else:
                sample = {'answer':'Unknown' if source['dataset'].startswith('ProofWriter') else 'NotMentioned',
                    'program':{'kind':'unsupported','body':{}}, 'compiled_units':[], 'unsupported_units':[], 'interfaces':[]}
                variants = [(True, sample)]
                if source['dataset'].startswith('ProofWriter'):
                    v = deepcopy(sample); v['program'] = {'kind':'public_horn','body':{}}
                    variants.append((True, v))
                if index in (4, 9, 14):
                    original = json.loads((root / old[index]['source_record']).read_text())
                    variants.append((False, json.loads(original['calls'][-1]['raw_content'])))
            for expected, value in variants:
                actual = matches(schema, value)
                if actual != expected:
                    raise AssertionError((sid, expected, actual, value))
            prompt = wire_messages(source)
            tokens = count(prompt)
            assert tokens['count'] + profile['max_tokens'] <= profile['context_tokens']
            cases.append({'source':sid, 'schema_sha256':digest(schema), 'messages_sha256':digest(prompt),
                'decode_cases':len(variants), 'input_tokens':tokens['count'], 'context_fits':True})
        # The actual inference route derives the residual state and planner from
        # the existing artificial raw proposals. No theory/plan is injected.
        fixture = json.loads((root / 'tests/fixtures/rr_existing_xor_request.json').read_text())
        source, proposals, requests = fixture['source'], fixture['proposals'], []
        def generate(prompt, **kwargs):
            value = proposals[kwargs['step']]
            assert matches(kwargs['schema'], value)
            requests.append({'messages':prompt, 'schema':kwargs['schema']})
            return {'content':json.dumps(value)}
        generate.is_offline_mock = True
        route = route_prediction(source, arm='M11', library=SkillLibrary(frozen=True).export(), generate=generate,
            protocol={}, partition='train', offline_mock=True, tokenize=count, request_config=profile, thinking=False)
        action = route['translation_actions'][0]
        assert action['selected'] == ['s1','s2'] and action['joint_separation_complete']
        assert route['result']['answer'] == 80 and route['result']['certificate_status'] == 'completion_stable'
        assert requests[1]['messages'][1]['content'].count('General rule:') == 1
        assert requests[1]['messages'][1]['content'].count('Base is 80.') == 1
        assert 'Boolean b_unrelated' not in requests[1]['messages'][1]['content']
        wire = request_payload(profile, **requests[1], thinking=False)
        assert hashlib.sha256(json.dumps(wire, ensure_ascii=False).encode()).hexdigest() == action['request_cost']['wire_body_sha256']
        local_tokens = count(requests[1]['messages'])
    # Read-only loopback /tokenize verifies the actual serving chat template;
    # this is not a model generation or a token-cost estimate from byte length.
    server = ExecutorClient(None, root / cfg['artifact_directory'], profile)
    card = server.readiness()
    serving = server.tokenize(requests[1]['messages'], thinking=False)
    assert local_tokens['tokens'] == serving['tokens']
    result = {'binding':current_binding(root), 'all_checks_passed':True,
        'cpu_decoder_network_blocked':True, 'serving_read_only_tokenization':True,
        'generation_requests':0, 'weights_loaded':False, 'labels_used_for_generation':False,
        'sources':cases, 'decode_cases':sum(c['decode_cases'] for c in cases)+2,
        'A_business_route':route, 'measured_request_cost':action['request_cost'],
        'serving_tokens_sha256':digest(serving['tokens']), 'local_serving_tokens_exact':True,
        'model_card':card, 'executor_thinking':False}
    path = root / 'reports/rr_v2_evidence/method_gap_repair/backend.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'sources','A_business_route','model_card'}},ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
