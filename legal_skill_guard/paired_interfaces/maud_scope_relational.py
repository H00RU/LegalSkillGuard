"""Certified local clause-scope interface for audited MAUD TRAIN passages.

The source-only audit locates the span for both arms. Only the span and the
public document are sent to the reader. The independently audited attachment
is available to the reference path. These local projections do not close the
scope of a full native MAUD question.
"""
from functools import lru_cache
import hashlib
import inspect
from textwrap import dedent

from legal_skill_guard.paired_interfaces import relational_program, residual
from legal_skill_guard.skill_evolution.objects import digest


COVENANTS = ('ordinary_course', 'negative_interim', 'other')
CONDITIONS = ('consent', 'law_required', 'pandemic', 'other')
PROJECTIONS = ('governs_ordinary_course', 'governs_negative_interim', 'is_pandemic_condition')


def local_consumer(values, context):
    # An expressly read target remains known even when the remainder of its
    # scope has not been resolved. A missing target alone proves no absence.
    ordinary = values['first_target'] == 'ordinary_course' or values['second_target'] == 'ordinary_course'
    negative = values['first_target'] == 'negative_interim' or values['second_target'] == 'negative_interim'
    unresolved = values['first_target'] is None or values['second_target'] is None
    return {
        'governs_ordinary_course': True if ordinary else None if unresolved else False,
        'governs_negative_interim': True if negative else None if unresolved else False,
        'is_pandemic_condition': values['condition'] == 'pandemic' if values['condition'] is not None else None,
    }


@lru_cache(maxsize=1)
def module():
    source = dedent(inspect.getsource(local_consumer))
    return residual.FiniteModule.build(
        'maud_local_operative_exception_scope',
        {
            'first_target': [*COVENANTS, None],
            'second_target': [*COVENANTS, 'no_additional_target_family', None],
            'condition': [*CONDITIONS, None],
        },
        [{}],
        local_consumer,
        consumer_sha256=hashlib.sha256(source.encode()).hexdigest(),
        program_source=source,
        source_scope={
            'local_unit': 'one cited exception and the covenant families it modifies',
            'source_fields': ['source_text'],
            'field_meanings': {
                'first_target': 'the first covenant family directly modified by the focused exception, '
                                'in the order of the governing language',
                'second_target': 'an additional directly modified family, if any. Use '
                                 'no_additional_target_family only when the attachment language is exhaustive',
                'condition': 'the type of the focused condition. Classify its stated trigger '
                             'as consent, law_required, pandemic or other',
            },
        },
    )


def has_scope_relation(asset):
    return any(feature['operation'] == 'relation'
               and {'first_target', 'second_target'} <= set(feature['consumer_dependencies'])
               for feature in asset['features'])


@lru_cache(maxsize=1)
def candidate_assets():
    pairing = residual.propose(module(), relational=True, max_new=8)
    generated = [asset for asset in pairing['candidates'] if has_scope_relation(asset)]
    if not generated:
        raise ValueError('The clause consumer did not generate a certified scope projection')
    return [pairing['baseline'], *generated]


def anchored_observations(source, audit, *, maximum=2):
    """Cover distinct audited target families in document and source order."""
    if source['dataset'] != 'MAUD' or source.get('project_split', source.get('split')) != 'train':
        raise ValueError('This reference anchor adapter requires a fixed MAUD TRAIN mother')
    documents = {f'document:{hashlib.sha256(doc.encode()).hexdigest()}': doc
                 for view in source['views'] for doc in [view['public']['source_text']]}
    effects = {record['effect_id']: record for record in audit['effects']}
    observations = []
    for exception in audit['exceptions']:
        if exception['scope_status'] != 'explicit' or len(exception['scope_options']) != 1:
            continue
        document = documents.get(exception['document_id'])
        condition = exception['condition_quote']
        attachment = exception['attachment_quote']
        if not document or document.count(condition) != 1 or attachment not in document:
            continue
        target_ids = set(exception['scope_options'][0])
        if not target_ids or not target_ids <= effects.keys():
            continue
        target_rows = [effects[target] for target in target_ids]
        if any(row['kind'] == 'unresolved' or row['document_id'] != exception['document_id']
               or row['operative_quote'] not in document for row in target_rows):
            continue
        targets = sorted(target_rows, key=lambda row: (document.index(row['operative_quote']), row['effect_id']))
        kinds = list(dict.fromkeys(
            row['kind'] if row['kind'] in COVENANTS else 'other' for row in targets))
        if not set(kinds).intersection(COVENANTS[:2]) or len(kinds) > 2:
            continue
        observation = {
            'anchor': {'document_id': exception['document_id'], 'condition_quote': condition,
                       'condition_offset': document.index(condition), 'attachment_quote': attachment},
            'state': {'first_target': kinds[0],
                      'second_target': kinds[1] if len(kinds) == 2 else 'no_additional_target_family',
                      'condition': exception['condition_kind'] if exception['condition_kind'] in CONDITIONS else None},
            'document': document,
            'target_families': tuple(kind for kind in COVENANTS[:2] if kind in kinds),
        }
        observations.append(observation)
    observations.sort(key=lambda row: (row['anchor']['document_id'], row['anchor']['condition_offset']))
    by_scope = {}
    remainder = []
    for observation in observations:
        scope = observation['target_families']
        if scope in by_scope:
            remainder.append(observation)
        else:
            by_scope[scope] = observation
    return [*by_scope.values(), *remainder][:maximum]


def case_view(mother, observation):
    """Instantiate the same local reader families on a real source anchor."""
    anchor = observation['anchor']
    text = observation['document']
    public = {'source_text': text, 'focused_exception': anchor['condition_quote'],
              'attachment_context': anchor['attachment_quote']}
    case_key = digest({'mother': mother['key'], 'anchor': anchor})
    local_tasks = [{'id': projection, 'public': public, 'answer_schema': {'type': 'boolean'}}
                   for projection in PROJECTIONS]
    diagnostic = {'key': mother['key'], 'dataset': 'MAUD', 'project_split': 'train',
                  'scope_diagnostic': case_key, 'views': local_tasks}
    plans = []
    unit_name = 'focused_exception'
    for index, asset in enumerate(candidate_assets()):
        program = relational_program.sealed({
            'units': {unit_name: {'asset': asset, 'asset_sha256': digest(asset),
                                  'module_binding': asset['module_binding'], 'context': {},
                                  'template_key': 'clause_scope:' + asset['version'],
                                  'entity_context': {'condition_offset': anchor['condition_offset']}}},
            'outputs': {projection: {'local': [unit_name, projection]} for projection in PROJECTIONS},
        })
        plan = {
            'name': f'clause_scope_{index}', 'reader_kind': 'consumer_relational_program',
            'relational_program': program, 'source_public_sha256': digest(diagnostic),
            'schema': relational_program.schema(program, exact_finite_values=True, maximum_evidence=1),
            'system': relational_program.prompt(program)
                      + '\nReturn a single compact JSON object. For a complete read, cite one exact source quote.',
            'choices': {'clause_scope': index},
            'is_correct_fixed_raw_control': index == 0,
        }
        plan['reader_template_sha256'] = relational_program.template_version(
            program, system=plan['system'], public_rules='focused operative exception scope',
            protocol='maud_local_clause_scope_v2_joint_support')
        plan['version'] = digest(plan)
        plans.append(plan)
    view = {
        'source': mother['key'], 'view': case_key, 'native_tasks': list(PROJECTIONS),
        'plans': plans, 'source_units': [],
        'relational_public_source': {'source_text': text},
        'read_input': {**public, 'unit_requests': relational_program.unit_requests(plans[0]['relational_program'])},
    }
    return diagnostic, view
