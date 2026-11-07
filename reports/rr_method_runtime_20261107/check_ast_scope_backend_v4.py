"""Installed-backend syntax and ordered token checks for the input-first AST contract."""
from copy import deepcopy
from datetime import datetime,timezone
import importlib.metadata
import json
from pathlib import Path
import socket
import time

import xgrammar as xgr
from transformers import AutoTokenizer

from legal_skill_guard.rr.compiler_contract import compiler_response_schema as candidate_schema, encode_compiler_program as encode
from verify_compiler_contract_backend_v1 import ordered


def main():
    def denied(*a,**k):raise AssertionError('No network or model call in backend feasibility')
    socket.socket.connect=denied;socket.create_connection=denied
    root=Path(__file__).resolve().parents[2];folder=Path(__file__).parent
    cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text())['executor']
    tokenizer=AutoTokenizer.from_pretrained(cfg['model_root'],local_files_only=True)
    size=json.loads((Path(cfg['model_root'])/'config.json').read_text())['vocab_size']
    byte_info=xgr.TokenizerInfo([bytes([i]) for i in range(256)]+[b''],vocab_size=257,stop_token_ids=[256])
    info=xgr.TokenizerInfo.from_huggingface(tokenizer,vocab_size=size)
    byte_compiler=xgr.GrammarCompiler(byte_info,max_threads=1,cache_enabled=False)
    token_compiler=xgr.GrammarCompiler(info,max_threads=1,cache_enabled=False)
    case=json.loads((root/'tests/fixtures/rr_scope_v5_binding_projection.json').read_text())
    packet=json.loads((root/'data/packets/rr_v2/public_train.json').read_text())
    sources={s['key']:s for s in packet['sources']};shapes=json.loads((folder/'structured_scope_candidate_offline.json').read_text())['schema_shapes']
    cases=[('actual_paid_SARA_IR',case['source'],case['canonical_program'],True)]
    for row in shapes:
        source=sources[row['source']]
        # This deliberately unbound root exercises syntax only. It is neither
        # an execution result nor a fabricated positive example.
        program={key:[] for key in ('bindings','observations','rule_residuals','nodes','scopes','clauses')}
        program['query']={'var':'unbound_no_semantic_success'}
        cases.append((row['dataset']+'_syntax_only',source,program,True))
    raw=json.loads((root/'tests/fixtures/rr_actual_ast_scope_v1.json').read_text())['raw_content']
    at=raw.index(':',raw.index('"scopes"'))+1
    at+=len(raw[at:])-len(raw[at:].lstrip())
    scopes,_=json.JSONDecoder().raw_decode(raw,at)
    raw=json.loads((root/'tests/fixtures/rr_actual_ast_input_first_v1.json').read_text())['raw_content']
    at=raw.index('[',raw.index('"nodes"'))+1
    at+=len(raw[at:])-len(raw[at:].lstrip())
    node,_=json.JSONDecoder().raw_decode(raw,at)
    for label,expression in [('paid_scope_string_vector_rejected',scopes['s0']['condition']),
                              ('paid_node_nested_pair_rejected',node['body'])]:
        program=deepcopy(case['canonical_program'])
        assert program['nodes'][0]['kind']=='expression'
        program['nodes'][0]['body']=expression
        cases.append((label,case['source'],program,False))
    results=[]
    with (folder/'ast_scope_backend_v4_progress.jsonl').open('w') as progress:
        for label,source,program,expected in cases:
            schema=candidate_schema(source);value=ordered(encode(program,source),schema,schema['$defs'])
            if not expected:
                # Invalid expression unions cannot choose a valid serializer
                # arm. Keep the enclosing node's metadata order canonical so
                # rejection is attributed to its operand, not its field order.
                row=value['nodes'][0]
                value['nodes'][0]={key:row[key] for key in ('name','kind','body')}
            text=json.dumps(value,ensure_ascii=False);spec=json.dumps(schema,ensure_ascii=False)
            started=time.monotonic()
            print(json.dumps({'phase':'compiling','case':label}),flush=True)
            byte_grammar=byte_compiler.compile_json_schema(spec,any_whitespace=False)
            token_grammar=token_compiler.compile_json_schema(spec,any_whitespace=False)
            compilation=time.monotonic()-started
            byte_ok=xgr.GrammarMatcher(byte_grammar).accept_string(text)
            matcher=xgr.GrammarMatcher(token_grammar);mask=xgr.allocate_token_bitmask(1,info.vocab_size)
            first=None
            for index,token in enumerate(tokenizer.encode(text,add_special_tokens=False)):
                matcher.fill_next_token_bitmask(mask)
                allowed=bool((int(mask[0,token//32].item())>>(token%32))&1)
                if not allowed or not matcher.accept_token(token):first={'index':index,'token_id':token};break
            row={'case':label,'expected_accepted':expected,'byte_accepted':byte_ok,'Qwen_tokens_accepted':first is None,
                'first_rejection':first,'compilation_seconds':compilation,'elapsed_seconds':time.monotonic()-started,
                'serialized_tokens':len(tokenizer.encode(text,add_special_tokens=False))}
            progress.write(json.dumps(row)+'\n');progress.flush();print(json.dumps(row),flush=True)
            if not expected:
                prefix=tokenizer.decode(tokenizer.encode(text,add_special_tokens=False)[:first['index']+1])
                body_at=text.index('"body":',text.index('"nodes":'))+len('"body":')
                row['rejected_after_node_body_started']=len(prefix)>body_at
                row['rejection_prefix_tail']=prefix[-150:]
                assert row['rejected_after_node_body_started'],row
            assert byte_ok==expected and (first is None)==expected,row
            results.append(row)
    receipt={'checked_utc':datetime.now(timezone.utc).isoformat(),'wired_but_real_model_validation_not_yet_run':True,
        'cases':results,'xgrammar_version':importlib.metadata.version('xgrammar'),
        'any_whitespace':False,'matches_live_disable_any_whitespace':True,'all_5_original_banks_syntax_only':True,'model_weights_loaded':False,'new_model_calls':0,
        'test_or_grading_packets_opened':False,'real_primary_success_claimed':False}
    (folder/'ast_scope_backend_v4.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
