"""Verify one real correct-subrule grounding failure, without a model call.

The original paid response and legal procedure stay unchanged. The two child
values are an overapproximation of an unresolved input view, not new cases or
asserted genders. This is a source-reviewed counterfactual replay, not fresh
model success, a complete parent-clause proof, or a learned-method gain.
"""
from copy import deepcopy
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.runtime import execute_helper


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/legal_skill_evolution_run_20261111/correct_skill_execution_20261114'


def read(path):
    return json.loads(path.read_text())


def main():
    original_path = ROOT / 'artifacts/legal_skill_evolution_named_role_check_20261112/completed.json'
    library_path = ROOT / 'artifacts/legal_skill_evolution_case_support_check_20261112/generated_library.json'
    original = read(original_path)
    event, = [e for e in original['execution']['events'] if e.get('kind') == 'APPLY']
    library = Library.load(library_path); skill = library.skills[event['skill_id']]
    assert skill.hash == event['skill_hash']
    source = next(s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json') if s['key'] == event['source'])
    assert source['split'] == 'train'
    view, = [v for v in source['views'] if v['id'] == event['view']]
    literal = literal_bindings(view)
    assert literal['values']['employer'] == 'Alice' and literal['values']['employee'] == 'Bob'
    assert ['Alice', 'father', 'Bob'] in literal['values']['case_family_relations']
    assert event['inputs']['employer_relationship_to_employee'] == 'father'
    assert 'service performed by an individual in the employ of his son, daughter, or spouse;' in view['public']['source_text']
    assert event['premises']['excluded_employer_relationships'] == ['son', 'daughter', 'spouse']
    actual = execute_helper(skill, event['inputs'], event['premises'])
    assert actual == event['outputs']
    alternatives = []
    for child in ('son', 'daughter'):
        inputs = deepcopy(event['inputs']); inputs['employer_relationship_to_employee'] = child
        result = execute_helper(skill, inputs, event['premises'])
        alternatives.append({'input_view': inputs, 'same_legal_procedure_result': result,
            'not_asserted_as_a_gender_fact': True})
    assert all(a['same_legal_procedure_result']['answer'] == 'Entailment' for a in alternatives)
    result = {'source': source['key'], 'view': view['id'], 'facts': view['public']['facts'],
        'question': view['public']['question'], 'literal_role_and_relation_record': literal,
        'actual_paid_execution': original['execution'], 'actual_paid_native_score': original['score'],
        'same_skill_hash': skill.hash, 'same_legal_procedure': skill.procedure,
        'source_legal_subrule': skill.premises['excluded_employer_relationships'],
        'actual_binding_error': 'Bob is the father OF Alice; the requested port is the relation Alice bears TO Bob. Copying father reverses the argument frame.',
        'source_reviewed_input_projection': 'The employer is a child of the employee; the relation-only view need not resolve the child gender because both source-listed child alternatives satisfy the unchanged A rule.',
        'counterfactual_input_views': alternatives,
        'child_alternatives_are_an_overapproximation_not_two_new_sources': True,
        'no_corrected_native_answer_in_input_or_program': True,
        'subrule_correctness_not_full_parent_clause_completeness': 'The A rule is faithful. The native question asks parent c(5): A true suffices for this case; A false alone cannot certify the parent false because B also exists.',
        'ordinary_relational_projection_can_recover_this_case': True,
        'new_model_requests': 0, 'not_independent_method_effect_or_new_model_success': True,
        'original_artifacts_sha256': {str(p.relative_to(ROOT)): digest(read(p)) for p in (original_path, library_path)},
        'goal_complete': False}
    immutable_json(OUT / 'verified_source_frame_error.json', result)
    print(json.dumps({'real_wrong_binding': event['inputs']['employer_relationship_to_employee'],
        'unchanged_program_actual_answer': actual['answer'],
        'source_supported_child_view_results': [a['same_legal_procedure_result']['answer'] for a in alternatives],
        'ordinary_relation_control_also_recovers': True, 'new_model_requests': 0}), flush=True)


if __name__ == '__main__':
    main()
