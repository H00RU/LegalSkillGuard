"""Factor acquired fields without inventing observations or semantic literals.

This is a shared execution compiler, not a learned method by itself. Acquired
source-domain programs keep their declared input units. Calendar fields stay
together because the existing literal-date converter can require both endpoints.
"""
from copy import deepcopy
import json

from .native import record_schema
from .objects import digest
from .relational_observation_contract import schema, split


def compile_library(library):
    result=deepcopy(library);receipts=[]
    for component in result['components']:
        contract=component.get('relation_contract')
        if not contract:continue
        before=digest(contract)
        if contract.get('read_constraint_program'):
            receipts.append({'component':component['id'],'changed':False,
                'reason':'Preserve acquired program input relations and fields'})
            continue
        changes=[]
        for original in list(contract['relations']):
            fields=[f for f in original['fields']if f['name']!=original['key']]
            temporal=[f['name']for f in fields if f.get('normalizer')=='literal_date']
            partitions=[]
            for field in fields:
                names=temporal if field['name']in temporal else [field['name']]
                if any(p['fields']==names for p in partitions):continue
                partitions.append({'name':original['name']+'__'+'_'.join(names),'fields':names,
                    'prompt':original['prompt']+'\nRead only the declared fields '+', '.join(names)+
                        '. Keep other attributes unread; do not supply their values.'})
            if len(partitions)<=1:continue
            contract=split(contract,original['name'],partitions)
            changes.append({'relation':original['name'],'partitions':partitions})
        if changes:
            component['relation_contract']=contract
            shape=schema(contract);shape['required']=[]
            component['schema_json']=json.dumps(record_schema({'views':{
                'type':'array','minItems':1,'items':shape}}))
        receipts.append({'component':component['id'],'changed':bool(changes),
            'parent_sha256':before,'compiled_sha256':digest(contract),'partitions':changes,
            'semantic_literals_added':False,'calendar_dependencies_preserved':True})
    return result,receipts
