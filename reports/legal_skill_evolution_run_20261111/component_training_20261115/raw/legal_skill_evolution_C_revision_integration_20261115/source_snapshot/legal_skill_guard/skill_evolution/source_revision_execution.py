"""Run both frozen learned producers on current input, then apply learned guards.

No source bank, prior per-source output, native question or gold label is loaded.
This is the inference path for a single selected two-version revision, not a
recursive library framework or a semantic fallback after observing an answer.
"""
import jsonschema

from .objects import digest
from .scoped_grammar import constructors, term_sort
from .scoped_source_program import OUTPUT
from .source_concept_execution import convert
from .source_frame_revision import merge
from .source_revision_guards import mask_for
from .span_compiler import execute_json


def execute(library, raw, *, timeout_seconds=30):
    revision = library['source_revision']; outputs = {}; receipts = {}
    v = raw['visible_inputs']
    for label in ('previous', 'proposed'):
        child = revision[label]
        if 'source_revision' in child:
            raise ValueError('Current revision execution has exactly two direct producers')
        if child['spec'] != library['spec']:
            raise ValueError('A source revision cannot silently change the shared consumer')
        if 'language' in child:
            from .open_acquisition import execute as execute_composition
            observation = convert(child, raw)
            result = execute_composition(child, observation, timeout_seconds=timeout_seconds)
            output = result['source_output']
            receipts[label] = {'library_sha256': digest(child), 'actual_phi_G_execution': True,
                'source_concept_sha256': observation['source_concept_execution']['program_sha256'],
                'selected_rule_ids': child['selected_rule_ids'], 'composition': result['composition']}
        else:
            output = execute_json(child['composition_program'], {'source_text': v['source_text'],
                'source_spans': v['units'], 'source_output': v['source_output'], 'semantic_answers': v['answers']},
                {}, allow_helpers=True)
            jsonschema.validate(output, OUTPUT)
            for row in output['statements']:
                term_sort(row['term'], constructors(child['spec']))
            receipts[label] = {'library_sha256': digest(child), 'actual_ordinary_program_execution': True,
                               'program_sha256': digest(child['composition_program'])}
        outputs[label] = output
    mask = mask_for(revision['policy'], v['source_text'])
    output, receipt = merge(outputs['previous'], outputs['proposed'], mask)
    return {'source_output': output, 'source_revision_execution': {
        'policy_sha256': digest(revision['policy']), 'updated_families': mask,
        'producer_executions': receipts, 'revision_receipt': receipt,
        'no_cached_per_source_output_or_answer_used': True, 'not_a_source_truth_certificate': True},
        'library_sha256': digest(library), 'observation_sha256': raw['visible_inputs_sha256'],
        'new_model_requests': 0}
