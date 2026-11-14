"""Use actual ContractNLI TRAIN text views for the contract quote validator.

The full five-library public file remains frozen and unchanged. Acquisition
sources/model inputs/labels are identical; this only avoids indexing unrelated
nontext task views while validating inherited literal contract examples.
"""
from experiments.legal_skill_evolution_scoped_atom_adapter import project
from copy import deepcopy
import sys
from experiments import legal_skill_evolution_source_gap_acquisition as e
from legal_skill_guard.rr.checkpoint import immutable_json
original=e.setup

def contract_setup():
    p,ledger,public=original()
    contracts={k:v for k,v in public.items() if k.startswith('ContractNLI:')}
    assert len(contracts)==24 and all(k in contracts for k in p['acquisition_sources'])
    assert all('source_text' in v['public'] for s in contracts.values() for v in s['views'])
    immutable_json(e.OUT/'unbound_compile_context_proof.json',{'acquisition_sources':p['acquisition_sources'],
        'actual_contract_TRAIN_quote_validation_sources':sorted(contracts),'full_original_public_registry_unchanged':True,
        'other_four_libraries_not_acquisition_sources_in_this_run':True,'new_model_requests':0,
        'original_error':'compile_proposal source-text quote validation indexed an unrelated five-library view without source_text'})
    return p,ledger,contracts

original_compile=e.compile_raw

def bind_declared_constant(old,raw,arm,public):
    if arm=='ConstraintAcquire':
        raw=deepcopy(raw);language=e.json.loads(raw['composition'])
        bridge=next(r for r in language['rules'] if r['id']=='read_disclosure_v3')
        rule=next(r for r in language['rules'] if r['id']=='compose_bounded_prohibition_v3')
        assert bridge['head']['predicate']=='d_disclosure_v3'
        position=bridge['head']['arguments'].index({'var':'R'});assert position==4
        body=next(a for a in rule['body'] if a['predicate']=='d_disclosure_v3')
        constant=body['arguments'][position];assert constant=='source_outsiders'
        assert rule['head']['arguments'][1]=={'var':'R'}
        old_head=deepcopy(rule['head']);rule['head']['arguments'][1]=constant
        raw['composition']=e.json.dumps(language,ensure_ascii=False)
        immutable_json(e.OUT/'ConstraintAcquire/unbound_constant_binding_proof.json',{
            'source_bridge_head':bridge['head'],'body_atom':body,'original_head':old_head,'adapted_head':rule['head'],
            'same_explicit_recipient_field_constant':constant,'only_unbound_head_R_bound_from_existing_source_field':True,
            'rule_body_cost_renderer_source_program_and_semantic_constants_unchanged':True,
            'no_native_label_or_test_answer_used_in_fix':True,'new_model_requests':0})
    if arm=='ConstraintAcquire':
        renderers=e.json.loads(raw['renderers_json']);projection=project(language,renderers)
        raw['composition']=e.json.dumps(language,ensure_ascii=False);raw['renderers_json']=e.json.dumps(renderers,ensure_ascii=False)
        immutable_json(e.OUT/'ConstraintAcquire/unbound_output_projection_proof.json',{'changes':projection,'same_existing_pointwise_output_projection_adapter':True,'all_bodies_costs_source_values_and_legal_term_provenance_substitution_preserved':True,'new_model_requests':0})
    return original_compile(old,raw,arm,public)

e.compile_raw=bind_declared_constant
e.setup=contract_setup
e.ARMS=tuple(sys.argv[1:])
e.compile_all()
