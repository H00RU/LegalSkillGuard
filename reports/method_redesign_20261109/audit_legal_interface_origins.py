"""Distinguish actual source-induced interfaces, shared API controls and author contracts."""
import hashlib,json,sqlite3
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'artifacts/rr_method_redesign_20261109'
STAGE=BASE/'legal_native_scope_completion_v1_20261110'


def read(p):return json.loads(p.read_text())


def main():
    roles=read(BASE/'redesign_source_roles_v1_20261109/seal.json')
    assert roles['initial_roles_or_case_facts_provided'] is False
    scalar=[]
    for name in ['teacher_sara151_percentage.json','teacher_sara63_basic_deduction.json']:
        p=BASE/'redesign_source_roles_v1_20261109'/name;r=read(p)
        scalar.append({'artifact':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
            'model_proposed_inputs':r['module']['inputs'],'input_names_types_meanings_not_enumerated_in_initial_schema':True,
            'generic_scalar_types_and_target_module_were_given':True})
    p=BASE/'legal_relations_exceptions_native_v1_20261109/seal.json';rel=read(p)
    raw=read(p.parent/'teacher_program.json');preds=raw['value']['predicates']
    assert 'Declare a neutral case_subject_year(person,year)' in rel['system_prompt']
    prior=read(BASE/'legal_independent_cache_v1_20261110/seal.json')
    out={'scalar_acquisition':scalar,'relation_initial_prompt_sha256':hashlib.sha256(rel['system_prompt'].encode()).hexdigest(),
        'relation_initial_prompt':rel['system_prompt'],'relation_model_predicates':preds,
        'relation_schema_does_not_enumerate_legal_predicate_names_or_roles':rel['program_schema']['properties']['predicates']['items'],
        'neutral_roster_predicate_given':{'name':'case_subject_year','roles':['person','year']},
        'substantive_role_and_connection_hints_given':True,
        'predicate_names_and_argument_roles_proposed_within_these_hints':True,
        'not_a_zero_hint_experiment_and_zero_hint_not_an_acceptance_requirement':True,
        'ordinary_independent_cache_was_given_this_learned_API':prior['shared_API_given_not_independently_rediscovered'],
        'API_acquisition_exists_but_equal_initial_source_cost_comparison_missing':True,
        'source13_six_scalar_inputs_and_annual_relation_columns_are_later_shared_author_contracts_not_this_API_acquisition':True,
        'do_not_repeat_the_existing_acquisition_under_a_new_name':True,
        'new_model_calls':0,'new_oracle_views':0,'goal_complete':False}
    immutable_json(STAGE/'interface_origin_audit.json',out)
    print(json.dumps({'scalar_interfaces_model_proposed':len(scalar),'legal_predicate_signatures_model_proposed':sum(p['name']!='case_subject_year' for p in preds),
        'neutral_roster_given':True,'semantic_role_hints_given':True,'same_initial_source_cost_comparison_missing':True,'new_model_calls':0}))


if __name__=='__main__':main()
