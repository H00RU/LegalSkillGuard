"""Facts-only reads of acquired relations through the frozen executor transport."""
import json
import jsonschema
from legal_skill_guard.rr.checkpoint import immutable_json
from .decoder_constraints import decoding_schema
from .objects import digest
from .relational_observation_contract import constrained_read_schema,source_copy_schema,schema
from .runtime import render_messages
from .clients import GenerationHold


def read(path):
    return json.loads(path.read_text())


def read_relation(client,p,sid,component,relation,public,prior):
    contract=component['relation_contract'];group=next(r for r in contract['relations']if r['name']==relation)
    task={'current_facts':public['facts'],'actual_prior_source_records':prior,
          'requested_relation':relation,'shared_key_domain':contract['key_domain']}
    domain_receipt={'used':False}
    if contract.get('read_constraint_program'):
        original,domain_receipt=constrained_read_schema(contract,relation,public,prior)
    else:
        original=(source_copy_schema(contract,[relation],public['facts'])
                  if p.get('compile_finite_copy_obligations') else schema(contract,[relation]))
    wire,_=decoding_schema(original)
    copy_receipt={'used':False}
    if p.get('compile_literal_copy_and_shared_keys'):
        from legal_skill_guard.skill_evolution.observation_copy_grammar import compile_wire
        wire,copy_receipt=compile_wire(wire,contract,relation,public['facts'],prior)
    messages=render_messages(group['prompt']+'\nRead facts only. Preserve current source keys. Do not infer missing dates, people or places. '
        'Complete scans enumerate every relevant source record. Ambiguity is unread. Return the named relation wrapper.',task,original)
    key=digest({'source':sid,'messages':messages,'schema':wire})
    output=client.artifacts
    target=output/'relation_reads'/(key+'.json')
    if target.exists():
        saved=read(target)
        if saved.get('error'):raise ValueError(saved['error'])
        value=json.loads(saved['raw_content'])
        assert value==saved['value'],'Raw response and saved parsed value disagree'
        return value,{**saved['receipt'],'cache_hit':True}
    saved={'source':sid,'component':component['id'],'relation':relation,'messages':messages,
           'schema':original,'learned_domain_receipt':domain_receipt,'copy_grammar_receipt':copy_receipt}
    try:
        size=client.tokenize(messages,thinking=False)['count']
        assert size+p['executor_profile']['max_tokens']<=p['executor_profile']['context_tokens']
        raw=client.generate(p['run_id']+':relation:'+key,source=sid,purpose='skill_actor',messages=messages,thinking=False,schema=wire)
        immutable_json(output/'raw_relation_responses'/(key+'.json'),raw)
        saved['receipt']={k:raw.get(k)for k in ('usage','elapsed_seconds','finish_reason','cache_hit')}
        assert raw['finish_reason']=='stop','Incomplete relation generation'
        value=json.loads(raw['content']);jsonschema.validate(value,original)
        saved['raw_content']=raw['content']
        saved['value']=value
    except GenerationHold:
        raise
    except Exception as error:
        saved['error']=type(error).__name__+': '+str(error)
    immutable_json(target,saved)
    if saved.get('error'):raise ValueError(saved['error'])
    return saved['value'],saved['receipt']

