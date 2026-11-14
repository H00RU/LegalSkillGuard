"""Strict wire types for the existing executable constructor-array terms.

No object wrapper, legal ontology or new method is introduced here.
"""
from copy import deepcopy
import jsonschema

from .native import record_schema
from .scoped_grammar import constructors,term_sort


def term_schema(spec,root_sort):
    bank=constructors(spec);by_sort={}
    for c in bank.values():by_sort.setdefault(c['sort'],[]).append(c)
    definitions={};pending=[root_sort]
    while pending:
        sort=pending.pop()
        if sort in definitions:continue
        if sort=='text':definitions[sort]={'type':'string'};continue
        if sort not in by_sort:raise ValueError('Unknown acquired sort: '+sort)
        variants=[];definitions[sort]={'anyOf':variants}
        for c in by_sort[sort]:
            args=c['arguments'];pending.extend(args)
            variants.append({'type':'array','minItems':1+len(args),'maxItems':1+len(args),
                'prefixItems':[{'type':'string','enum':[c['name']]},*[{'$ref':'#/$defs/'+a} for a in args]],
                'items':False})
    return {'$defs':definitions,'$ref':'#/$defs/'+root_sort}


def validate_value(spec,sort,value):
    jsonschema.validate(value,term_schema(spec,sort))
    if term_sort(value,constructors(spec))!=sort:raise ValueError('Wrong acquired result sort')
    return deepcopy(value)
