"""Check six observed long responses against their actual frozen wire schemas.

This checks prefixes only. It never closes, repairs, executes, or scores the
truncated response and does not turn any failed response into a successful IR.
"""
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
import hashlib
import json
import socket
import base64

ROOT=Path(__file__).resolve().parents[3]
RUN=ROOT/'artifacts/rr_v2_formal_build_20261106/run'
OUT=ROOT/'reports/rr_v2_evidence/formal_build_20261106'


def read(path):return json.loads(Path(path).read_text())
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def deny(*args,**kwargs):raise RuntimeError('Truncation checks forbid network/model calls')


def main():
    import xgrammar
    from transformers import AutoTokenizer
    cfg=read(ROOT/'configs/rr_v2_preflight.json')
    order=read(ROOT/cfg['source_manifest'])['formal_train_order']
    cache={};rows=[]
    with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny):
        model=Path(cfg['executor']['model_root'])
        tokenizer=AutoTokenizer.from_pretrained(str(model),local_files_only=True,trust_remote_code=False)
        compiler=xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(tokenizer,
            vocab_size=read(model/'config.json')['vocab_size']),max_threads=1)
        for index in (26,29,30):
            sid=order[index-1]
            record=read(RUN/'sources'/(digest(sid)+'.json'))
            for call in record['calls']:
                cid='rr_v2_formal_build_20261106:'+sid+':'+str(call['step'])
                directory=RUN/'calls'/digest(cid)
                saved_req=read(directory/'request.json')
                # Immutable request.json sorts keys for archival. xgrammar uses
                # schema property order, so replay the literal transmitted body.
                wire=read(directory/'wire_request.json')
                literal=base64.b64decode(wire['body_b64'])
                if hashlib.sha256(literal).hexdigest()!=wire['body_sha256']:
                    raise ValueError('Literal wire request hash differs')
                payload=json.loads(literal)
                if payload!=saved_req['payload']:
                    raise ValueError('Archived request values differ from actual wire')
                result=read(directory/'result.json')
                raw=call['raw_content']
                if raw!=result['content'] or result['finish_reason']!='length' or result['usage']['completion_tokens']!=8192:
                    raise ValueError('The selected observed truncation record differs')
                schema=payload['response_format']['json_schema']['schema']
                key=digest(schema)
                if key not in cache:
                    cache[key]=compiler.compile_json_schema(schema,strict_mode=True,any_whitespace=False)
                matcher=xgrammar.GrammarMatcher(cache[key])
                # The original serving token IDs are not returned by the API.
                # Retokenize the preserved literal output with the same tokenizer.
                tokens=tokenizer.encode(raw,add_special_tokens=False)
                first_rejected=next((i for i,t in enumerate(tokens) if not matcher.accept_token(t)),None)
                eos_accepted=False if first_rejected is not None else matcher.accept_token(tokenizer.eos_token_id)
                try:
                    json.loads(raw)
                    raise ValueError('Selected length-limited response unexpectedly has complete JSON')
                except json.JSONDecodeError as exc:
                    error={'message':exc.msg,'pos':exc.pos,'line':exc.lineno,'column':exc.colno}
                preceding=raw[:error['pos']].rstrip()[-1:]
                quote_probe=None
                if first_rejected is None and preceding in ('[',':'):
                    probe=xgrammar.GrammarMatcher(cache[key])
                    if not all(probe.accept_token(t) for t in tokens):
                        raise ValueError('Repeated prefix check differs')
                    # Check only whether a closing quote is allowed next. This
                    # does not produce a completed JSON response or an IR.
                    quote_probe=all(probe.accept_token(t) for t in tokenizer.encode('"',add_special_tokens=False))
                rows.append({'index':index,'source':sid,'step':call['step'],'request_hash':call['request_hash'],
                    'schema_sha256':key,'raw_response_sha256':hashlib.sha256(raw.encode()).hexdigest(),
                    'schema_root_property_order':list(schema['properties']),
                    'schema_source':'literal_wire_request_body',
                    'model_reported_output_tokens':result['usage']['completion_tokens'],
                    'retokenized_tokens':len(tokens),'all_prefix_tokens_accepted':first_rejected is None,
                    'first_rejected_token_index':first_rejected,'EOS_accepted':eos_accepted,
                    'last_open_string_is_value':preceding in ('[',':'),
                    'closing_quote_can_be_generated':quote_probe,
                    'JSON_error':error,'quotes_after_unclosed_string':raw[error['pos']+1:].count('"'),
                    'existing_IR_status':call['analysis']['program_status'],
                    'response_modified_or_repaired':False})
    value={'captured_utc':datetime.now(timezone.utc).isoformat(),'binding':read(RUN/'seal.json')['binding'],
        'scope':'observed source26/29/30, both attempts; not an all-source decoder claim',
        'checks':rows,'all_selected_prefixes_accepted':all(r['all_prefix_tokens_accepted'] for r in rows),
        'all_selected_EOS_rejected':all(not r['EOS_accepted'] for r in rows),
        'value_string_close_cases':sum(r['last_open_string_is_value'] for r in rows),
        'all_selected_value_strings_can_close':all(r['closing_quote_can_be_generated'] is True for r in rows if r['last_open_string_is_value']),
        'original_token_ids_available':False,'same_local_tokenizer_used':True,
        'initial_sorted_request_diagnostic_preserved':'truncation_evidence.sorted_request_check.json',
        'no_response_completion_or_semantic_repair':True,'new_model_calls':0,'new_oracle_views':0,
        'network_blocked':True,'weights_loaded':False}
    (OUT/'truncation_evidence.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(value,ensure_ascii=False),flush=True)
    if not value['all_selected_prefixes_accepted'] or not value['all_selected_EOS_rejected'] or not value['all_selected_value_strings_can_close']:
        raise RuntimeError('Actual prefix constraints need investigation; do not label all cases ordinary truncation')


if __name__=='__main__':main()
