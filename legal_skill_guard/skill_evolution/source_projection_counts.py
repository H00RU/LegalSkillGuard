"""Exact counts of named structural patterns in an acquired source output.

Zero means no match in this finite supplied representation. It is NEVER a
source-world absence judgment. Legal absence still requires its independently
acquired explicit full-source reading and the existing source checks.
"""
from copy import deepcopy

from .objects import digest
from .source_observations import fact


SIGNATURE = {'arguments': ['input_projection_name', 'representation_count'], 'kind': 'observed'}


def validate_projections(projections, constructor_table=None):
    names = set()
    for projection in projections:
        if set(projection) != {'name', 'constructor', 'arguments_equal'}:
            raise ValueError('A projection has exact identity, constructor and argument conditions')
        name, constructor = projection['name'], projection['constructor']
        if not isinstance(name, str) or not name or name in names or not isinstance(constructor, str) or not constructor:
            raise ValueError('Distinct projection names and a declared constructor required')
        names.add(name)
        if constructor_table is not None and constructor not in constructor_table:
            raise ValueError('Projection names an undeclared source constructor')
        positions = set()
        for condition in projection['arguments_equal']:
            if set(condition) != {'position', 'value'}:
                raise ValueError('An exact argument position and value are required')
            position = condition['position']
            if type(position) is not int or position < 0 or position in positions:
                raise ValueError('Projection positions are distinct nonnegative argument indices')
            positions.add(position)
            if constructor_table is not None and position >= len(constructor_table[constructor]['arguments']):
                raise ValueError('Projection argument is outside its declared constructor')
            if type(condition['value']) not in (str, int, float, bool):
                raise ValueError('Project an actual scalar source argument, not a missing value')
    return projections


def add_counts(observation,projections):
    validate_projections(projections)
    if 'structural_projection_receipt' in observation:
        raise ValueError('Do not append the same derived observation interface twice')
    value=deepcopy(observation)
    statements=value['visible_inputs']['source_output']['statements']
    receipts=[]
    names=set()
    for projection in projections:
        name=projection['name']
        if not isinstance(name,str) or not name or name in names:
            raise ValueError('Distinct structural projection names required')
        names.add(name)
        indices=[]
        for index,row in enumerate(statements):
            term=row['term']
            if not isinstance(term,list) or not term or term[0]!=projection['constructor']:
                continue
            matches=True
            for condition in projection['arguments_equal']:
                position=condition['position']
                if type(position)is not int or position<0:
                    raise ValueError('Projection arguments use actual nonnegative child indices')
                if position+1>=len(term) or term[position+1]!=condition['value']:
                    matches=False
            if matches:indices.append(index)
        value['context']['facts'].append(fact('input_projection_count',name,len(indices)))
        receipts.append({'projection':projection,'count':len(indices),'matched_statement_indices':indices})
    value['structural_projection_receipt']={'input_observation_sha256':digest(observation),
        'projections':receipts,'source_or_reader_judgments_changed':False,
        'zero_count_is_not_legal_absence':True,'new_model_calls':0}
    value['contract_sha256'] = digest({'base_contract_sha256': observation['contract_sha256'],
        'deterministic_input_projection_definitions': projections, 'signature': SIGNATURE})
    return value
