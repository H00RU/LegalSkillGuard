"""Receiver and recipient binding for the ContractNLI employee-disclosure task."""

from functools import lru_cache
import hashlib
import inspect
import re
from textwrap import dedent

from legal_skill_guard.paired_interfaces import indexed_relational_read, relational_program, residual
from legal_skill_guard.skill_evolution.objects import digest

TASK = 'nda-5'
UNIT = 'employee_disclosure_scope'
ACTION = re.compile(r'\b(?:disclos\w*|shar\w*|divulg\w*|access|confidential\s+information)\b', re.I)
RECIPIENT = re.compile(r'\b(?:employees?|agents?|advisers?|advisors?|representatives?|personnel|staff)\b', re.I)


def consume(values, context):
    if values['disclosure_actor'] == 'receiver' and values['recipient_group'] == 'own_employees':
        if values['permission_force'] == 'allow':
            return {'classification': 'Entailment'}
        if values['permission_force'] == 'deny_all':
            return {'classification': 'Contradiction'}
    return {'classification': None}


@lru_cache(maxsize=1)
def module():
    code = dedent(inspect.getsource(consume))
    return residual.FiniteModule.build(
        UNIT, {'disclosure_actor': ['receiver', 'other_party', None],
               'recipient_group': ['own_employees', 'other_recipients', None],
               'permission_force': ['allow', 'deny_all', 'no_bound_permission', None]},
        [{}], consume, consumer_sha256=hashlib.sha256(code.encode()).hexdigest(), program_source=code,
        source_scope={
            'source_fields': ['source_text'],
            'local_unit': 'the disclosure permission or prohibition and the receiving party’s employees',
            'field_meanings': {
                'disclosure_actor': 'the source binds the actor of the disclosure or internal sharing to '
                                     'the party receiving this same confidential information. Named parties can '
                                     'be bound by their role in the quoted provision',
                'recipient_group': 'the permission or prohibition covers at least some employees '
                                                 'of that receiver. Do not transfer an employee of the discloser '
                                                 'to the receiver. Do not assume agents or advisers are employees',
                'permission_force': 'allow for an operative permission, including limited sharing on a need-to-know '
                                    'basis. Use deny_all only for an explicit ban covering all such sharing. '
                                    'A general confidentiality duty does not alone establish that ban',
            },
        },
    )


@lru_cache(maxsize=1)
def assets():
    pair = residual.propose(module(), max_new=64, relational=True)
    dependencies = {'disclosure_actor', 'recipient_group'}
    for candidate in pair['candidates']:
        if any(feature.get('expression', {}).get('op') == 'and'
               and dependencies == set(feature['consumer_dependencies']) for feature in candidate['features']):
            return pair['baseline'], candidate
    raise ValueError('No certified same-receiver relation was generated')


def clause_ranges(public):
    """Keep every eligible individual or consecutive pair of native spans."""
    text = public['source_text']
    spans = public['sentence_spans']
    ranges = {}
    for i in range(len(spans)):
        for j in range(i, min(i + 2, len(spans))):
            start, end = spans[i][0], spans[j][1]
            unit = text[start:end]
            if ACTION.search(unit) and RECIPIENT.search(unit):
                ranges[f'n{i}_{j}'] = [start, end]
    return ranges


def native_evidence(public, anchor, expected_range):
    match = re.fullmatch(r'n([0-9]+)_([0-9]+)', anchor)
    if not match:
        raise ValueError('Contract evidence needs declared native span coordinates')
    first, last = map(int, match.groups())
    spans = public['sentence_spans']
    if not 0 <= first <= last < len(spans) or last - first > 1:
        raise ValueError('Contract evidence index is outside the selected public span group')
    if expected_range != [spans[first][0], spans[last][1]]:
        raise ValueError('Contract evidence span lost its exact native text binding')
    return list(range(first, last + 1))


def build(source):
    native = next(view for view in source['views'] if view['id'] == TASK)
    selected = {**source, 'views': [native]}
    public = native['public']
    ranges = clause_ranges(public)
    if not ranges:
        raise ValueError('No source-localized disclosure group is available')
    plans = []
    for index, asset in enumerate(assets()):
        program = relational_program.sealed({
            'units': {UNIT: {
                'asset': asset, 'asset_sha256': digest(asset), 'module_binding': asset['module_binding'],
                'context': {}, 'template_key': f'cni_employee_disclosure:{asset["version"]}',
                'entity_context': {'action': 'disclosure or internal sharing', 'receiver_role': 'receiving party'},
            }},
            'outputs': {TASK: {'local': [UNIT, 'classification']}},
        })
        system = relational_program.prompt(program)
        plan = {
            'name': f'cni_disclosure_{index}', 'choices': {'employee_disclosure_scope': index},
            'is_correct_fixed_raw_control': index == 0, 'native_evidence_codec': 'cni_clause_ranges_v1',
            'reader_kind': 'consumer_relational_program', 'relational_program': program,
            'source_public_sha256': digest(selected), 'system': system,
            'reader_template_sha256': relational_program.template_version(
                program, system=system, public_rules='employee disclosure permission', protocol='cni_disclosure_v1'),
        }
        plans.append(plan)
    view = indexed_relational_read.reformat({
        'source': source['key'], 'dataset': 'ContractNLI', 'view': 'employee_disclosure_scope',
        'source_units': [], 'native_tasks': [TASK], 'plans': plans,
        'relational_public_source': {'source_text': public['source_text'], 'indexed_ranges': ranges},
        'read_input': {'source_text': public['source_text'], 'hypothesis': public['question']},
    }, factorized=True)
    return selected, view
