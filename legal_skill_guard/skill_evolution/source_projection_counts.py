"""Exact counts of named structural patterns in an acquired source output.

Zero means no match in this finite supplied representation. It is NEVER a
source-world absence judgment. Legal absence still requires its independently
acquired explicit full-source reading and the existing source checks.
"""
from copy import deepcopy

from .objects import digest
from .source_observations import fact


def add_counts(observation,projections):
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
    return value
