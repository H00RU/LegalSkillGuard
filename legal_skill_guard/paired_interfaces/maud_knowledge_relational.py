"""M1 interface for the MAUD knowledge-definition native task."""
from functools import lru_cache
import hashlib
import inspect
from textwrap import dedent

from legal_skill_guard.paired_interfaces import relational_program, residual
from legal_skill_guard.skill_evolution.objects import digest

TASK = 'Knowledge Definition-Answer'


def consume(values, context):
    if values['qualification_target'] == 'target_definition' and values['inquiry_effect'] == 'required':
        return {'classification': 'Constructive knowledge'}
    if values['qualification_target'] is None or values['inquiry_effect'] is None:
        return {'classification': None}
    if values['explicit_actual_restriction'] is True:
        return {'classification': 'Actual knowledge'}
    return {'classification': None}


@lru_cache(maxsize=1)
def module():
    code = dedent(inspect.getsource(consume))
    return residual.FiniteModule.build(
        'maud_operative_knowledge_qualification',
        {
            'qualification_target': ['target_definition', 'different_definition_or_clause', 'absent', None],
            'inquiry_effect': ['required', 'not_required', 'absent', None],
            'explicit_actual_restriction': [True, False, None],
        },
        [{}],
        consume,
        consumer_sha256=hashlib.sha256(code.encode()).hexdigest(),
        program_source=code,
        source_scope={
            'source_fields': ['source_text'],
            'local_unit': 'the operative definition of knowledge in the requested agreement excerpt',
            'field_meanings': {
                'qualification_target': 'the definition that an inquiry phrase modifies. '
                                        'Resolve attachment before treating an inquiry as operative. '
                                        'Ignore unrelated definitions and preserve unresolved attachment',
                'inquiry_effect': 'the force of the inquiry wording, including knowledge a definition '
                                  'imputes after a reasonable inquiry. A limitation on the types '
                                  'of inquiry does not revoke an otherwise operative inquiry requirement',
                'explicit_actual_restriction': 'an express restriction to actual knowledge in the target definition. '
                                               'A reference to actual knowledge alone can coexist with '
                                               'an additional inquiry qualification',
            },
        },
    )


@lru_cache(maxsize=1)
def assets():
    pair = residual.propose(module(), relational=True, max_new=64)
    required = {'qualification_target', 'inquiry_effect'}
    for candidate in pair['candidates']:
        if any(feature.get('expression', {}).get('op') == 'and'
               and required <= set(feature['consumer_dependencies']) for feature in candidate['features']):
            return pair['baseline'], candidate
    raise ValueError('No certified scope-and-inquiry relation was synthesized')


def build(source):
    native = next(view for view in source['views'] if view['id'] == TASK)
    selected_source = {**source, 'views': [native]}
    public = native['public']
    plans = []
    for index, asset in enumerate(assets()):
        unit = 'operative_knowledge_definition'
        program = relational_program.sealed({
            'units': {unit: {'asset': asset, 'asset_sha256': digest(asset),
                             'module_binding': asset['module_binding'], 'context': {},
                             'template_key': 'knowledge_scope:' + asset['version'],
                             'entity_context': {'task': TASK}}},
            'outputs': {TASK: {'local': [unit, 'classification']}},
        })
        plan = {
            'name': f'knowledge_scope_{index}', 'reader_kind': 'consumer_relational_program',
            'relational_program': program, 'source_public_sha256': digest(selected_source),
            'schema': relational_program.schema(program, maximum_evidence=1, exact_finite_values=True),
            'system': relational_program.prompt(program)
                      + '\nUse one exact quote from the operative definition. Return compact JSON.',
            'choices': {'knowledge_scope': index}, 'is_correct_fixed_raw_control': index == 0,
        }
        plan['reader_template_sha256'] = relational_program.template_version(
            program, system=plan['system'], public_rules='operative inquiry qualification',
            protocol='maud_knowledge_definition_reader_v1')
        plan['version'] = digest(plan)
        plans.append(plan)
    return selected_source, {
        'source': source['key'], 'view': 'knowledge_definition',
        'native_tasks': [TASK], 'plans': plans, 'source_units': [],
        'relational_public_source': {'source_text': public['source_text']},
        'read_input': {**public, 'unit_requests': relational_program.unit_requests(plans[0]['relational_program'])},
    }
