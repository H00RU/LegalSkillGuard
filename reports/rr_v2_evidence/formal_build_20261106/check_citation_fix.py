"""Offline old/new citation decoder regression on original TRAIN public text.

Never modifies or completes a real response. A next-token probe is not a new IR
or a semantic success. No model, new label, or oracle call is available here.
"""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import base64
import hashlib
import json
import re
import socket

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.engine import source_text
from legal_skill_guard.rr.strict_contract import CITATION_PATTERN

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'artifacts/rr_v2_formal_build_20261106'
OUT=ROOT/'reports/rr_v2_evidence/formal_build_20261106'


def read(path):return json.loads(Path(path).read_text())
def deny(*a,**kw):raise RuntimeError('Citation decoder checks forbid network/model calls')


def main():
    import xgrammar
    from transformers import AutoTokenizer
    cfg=read(ROOT/'configs/rr_v2_preflight.json');manifest=read(ROOT/cfg['source_manifest'])
    public={s['key']:s for s in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    headers=read(OUT/'citation_public_header_audit.json')
    old_pattern=headers['old_pattern']
    all_headers=sorted({line.strip() for sid in manifest['formal_train_order'] if public[sid]['dataset']=='OpenExempt'
        for line in source_text(public[sid]).splitlines()
        if re.match(r'^(?:11 U\.S\.C\.|Ariz\. Rev\. Stat\.|735 Ill\. Comp\. Stat\.|Or\. Rev\. Stat\.|42 Pa\. Cons\. Stat\.|Wis\. Stat\.) ',line.strip())})
    cases=[];probes=[]
    with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny):
        model=Path(cfg['executor']['model_root'])
        tok=AutoTokenizer.from_pretrained(str(model),local_files_only=True,trust_remote_code=False)
        compiler=xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(tok,
            vocab_size=read(model/'config.json')['vocab_size']),max_threads=1)
        def accepts(compiled,text,complete):
            matcher=xgrammar.GrammarMatcher(compiled)
            okay=all(matcher.accept_token(t) for t in tok.encode(text,add_special_tokens=False))
            return okay and (not complete or matcher.accept_token(tok.eos_token_id))
        old_string=compiler.compile_json_schema({'type':'string','pattern':old_pattern},strict_mode=True,any_whitespace=False)
        new_string=compiler.compile_json_schema({'type':'string','pattern':CITATION_PATTERN},strict_mode=True,any_whitespace=False)
        for citation in all_headers:
            text=json.dumps(citation,ensure_ascii=False)
            before=accepts(old_string,text,True);after=accepts(new_string,text,True)
            if not after:raise ValueError('Public citation remains blocked: '+citation)
            cases.append({'public_citation':citation,'old_accepts_complete_string':before,'new_accepts_complete_string':after})
        malformed=['invented citation','735 Ill. Comp. Stat. fake','A§B" } trailing§invalid',
                   '735 Ill. Comp. Stat. 5/12-1001(a)\\tail', '735 Ill. Comp. Stat. 5/12-1001(a)\ncontrol']
        for value in malformed:
            if accepts(new_string,json.dumps(value,ensure_ascii=False),True):
                raise ValueError('Malformed/noncitation value admitted by corrected format')
        for index,citation in [(29,'735 Ill. Comp. Stat. 5/12-1001(a)'),(30,'735 Ill. Comp. Stat. 5/12-1001(d)')]:
            sid=manifest['formal_train_order'][index-1]
            record=read(BASE/'run/sources'/(digest(sid)+'.json'))
            call=record['calls'][0];cid='rr_v2_formal_build_20261106:'+sid+':0'
            directory=BASE/'run/calls'/digest(cid)
            wire=read(directory/'wire_request.json');literal=base64.b64decode(wire['body_b64'])
            if hashlib.sha256(literal).hexdigest()!=wire['body_sha256']:raise ValueError('Wire request changed')
            old_schema=json.loads(literal)['response_format']['json_schema']['schema']
            new_schema=deepcopy(old_schema)
            def replace_pattern(node):
                if isinstance(node,dict):
                    if node.get('type')=='string' and node.get('pattern')==old_pattern:node['pattern']=CITATION_PATTERN
                    for value in node.values():replace_pattern(value)
                elif isinstance(node,list):
                    for value in node:replace_pattern(value)
            replace_pattern(new_schema)
            start=call['raw_content'].find(citation)
            if start<0 or citation not in source_text(public[sid]):raise ValueError('Probe citation is not in actual output and public input')
            prefix=call['raw_content'][:start+len(citation)]
            before=compiler.compile_json_schema(old_schema,strict_mode=True,any_whitespace=False)
            after=compiler.compile_json_schema(new_schema,strict_mode=True,any_whitespace=False)
            def can_close(compiled):
                matcher=xgrammar.GrammarMatcher(compiled)
                if not all(matcher.accept_token(t) for t in tok.encode(prefix,add_special_tokens=False)):
                    raise ValueError('Actual canonical-citation prefix rejected')
                return all(matcher.accept_token(t) for t in tok.encode('"',add_special_tokens=False))
            old_close,new_close=can_close(before),can_close(after)
            if old_close or not new_close:raise ValueError('Canonical citation closure regression not resolved')
            probes.append({'index':index,'source':sid,'step':0,'public_citation':citation,
                'original_request_hash':call['request_hash'],'raw_response_sha256':hashlib.sha256(call['raw_content'].encode()).hexdigest(),
                'actual_prefix_characters':len(prefix),'old_closing_quote_allowed':old_close,'new_closing_quote_allowed':new_close,
                'actual_response_modified':False,'completed_response_or_IR_created':False})
    value={'captured_utc':datetime.now(timezone.utc).isoformat(),'old_generation_binding':read(BASE/'run/seal.json')['binding'],
        'corrected_strict_contract_sha256':hashlib.sha256((ROOT/'legal_skill_guard/rr/strict_contract.py').read_bytes()).hexdigest(),
        'old_pattern':old_pattern,'corrected_pattern':CITATION_PATTERN,'public_train_sources':32,
        'public_header_cases':cases,'old_rejected_public_headers':sum(not r['old_accepts_complete_string'] for r in cases),
        'new_rejected_public_headers':0,'malformed_cases_rejected':len(malformed),'actual_prefix_closure_probes':probes,
        'network_blocked':True,'new_model_calls':0,'new_oracle_views':0,'weights_loaded':False,
        'real_output_repaired_or_regraded':False,'research_scope_changed':False,
        'limitation':'Offline decoder acceptance does not prove new model outputs or native task semantics succeed.'}
    (OUT/'citation_fix_decoder.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k not in {'public_header_cases'}}),flush=True)


if __name__=='__main__':main()
