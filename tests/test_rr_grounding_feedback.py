"""Actual source32 overflow: encode diagnostics, preserving every source/value."""
import ast
from copy import deepcopy
import json
from pathlib import Path

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.program_inference import predict_source
from legal_skill_guard.rr.source_validation import encode_grounding_failure_feedback

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v7_20261109'


def actual_failure():
    seal=json.loads((STAGE/'seal.json').read_text());source=seal['sources']['train'][31]
    journal=STAGE/'build/journals'/digest(source)
    state=json.loads(json.loads((journal/'state0.json').read_text())['state_json'])
    root={k:state['feedback'][k] for k in ('error_type','error','field_path') if k in state['feedback']}
    return seal,source,state,root


def test_actual_14_grounding_failures_round_trip_without_omitting_fields_or_values():
    _,_,_,root=actual_failure();before=deepcopy(root)
    value=encode_grounding_failure_feedback(root);table=value['grounding_failures']
    assert table['columns']==['binding','sources','pass','basis_index']
    restored=[{'binding':r[0],'sources':r[1],'pass':r[2],'basis':table['basis_vocabulary'][r[3]]}
        for r in table['rows']]
    assert len(restored)==14 and value['error']+repr(restored)==root['error']
    assert root==before
    table['rows'][0][1].append('changed')
    assert root==before
    assert encode_grounding_failure_feedback({'error':'Other failure'}) is None
    assert encode_grounding_failure_feedback({'error':'Public literal grounding failed: __import__("os")'}) is None
    malformed=ast.literal_eval(root['error'].split(': ',1)[1]);malformed[0]['unexpected']='must not vanish'
    assert encode_grounding_failure_feedback({**root,'error':'Public literal grounding failed: '+repr(malformed)}) is None


def test_actual_source32_repair_fits_after_lossless_error_encoding_without_semantic_acceptance():
    seal,key,state,root=actual_failure();library=SkillLibrary(stage='formal_train')
    for previous in seal['sources']['train'][:31]:
        row=json.loads((STAGE/'build/sources'/(digest(previous)+'.json')).read_text())
        if row['learning'].get('learned_pattern'):library.add(row['learning']['learned_pattern'],source=previous)
        for template in row.get('compiler_learning',{}).get('templates',[]):library.add_compiler_template(template)
    source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources'] if s['key']==key)
    witness=json.loads((ROOT/'reports/rr_method_runtime_20261107/reference_grounding_feedback32_lossless_capacity_v24.json').read_text())
    original=state['calls'][0];seen=[]
    def tokenizer(messages,thinking):
        feedback=json.loads(messages[1]['content'])['source_only_feedback']
        if feedback is None:return {'count':original['usage']['prompt_tokens']}
        kind='full' if 'source_validation' in feedback else 'lossless_grounding_table' if 'grounding_failures' in feedback else 'root_only'
        return {'count':witness['input_token_counts'][kind]}
    def generate(messages,*,purpose,step,schema):
        payload=json.loads(messages[1]['content']);seen.append(payload)
        if step:
            assert payload['CURRENT']==seen[0]['CURRENT']
            assert payload['earlier_TRAIN_examples']==seen[0]['earlier_TRAIN_examples']
            assert payload['runtime_contract']==seen[0]['runtime_contract']
            encoded=payload['source_only_feedback'];table=encoded['grounding_failures']
            restored=[{'binding':r[0],'sources':r[1],'pass':r[2],'basis':table['basis_vocabulary'][r[3]]} for r in table['rows']]
            assert encoded['error']+repr(restored)==root['error']
        return {'content':original['raw_content'],'finish_reason':'stop','request_hash':original['request_hash'],
            'usage':original['usage'],'elapsed_seconds':0}
    out=predict_source(source,arm='M11',library=library.export(),generate=generate,tokenize=tokenizer,
        request_config=seal['config']['executor'],thinking=False,partition='train',controlled_shortcut=False)
    assert len(seen)==out['model_calls']==2
    assert out['result']['answer'] is None and not out['result']['A_main_path_executed']
    action=next(x for x in out['translation_actions'] if x.get('root_error_lossless_encoding'))
    assert action['full_input_tokens']==26691 and action['dispatched_input_tokens']==24347
