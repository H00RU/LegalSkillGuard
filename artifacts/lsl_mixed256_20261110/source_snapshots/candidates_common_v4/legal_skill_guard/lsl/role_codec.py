"""One-to-one native role serialization for the observed xgrammar Unicode bug.

Only the wire code changes. The native Chinese ontology and scoring stay the
same. Unknown codes raise; no field aliases or inferred semantic repairs.
"""
from copy import deepcopy
from .projection import TAGS

WIRE_ROLES=('SUBJECT','OBJECT','PRECONDITION','MANNER','CIRCUMSTANCE','ACTION',
            'REFERENCE','PURPOSE','EXCLUSION','RESULT','PROCEDURE','AMOUNT')
ENCODE=dict(zip(TAGS,WIRE_ROLES));DECODE={v:k for k,v in ENCODE.items()}


def _convert(value,mapping):
    if isinstance(value,list):return [_convert(v,mapping) for v in value]
    if not isinstance(value,dict):return value
    out={k:_convert(v,mapping) for k,v in value.items()}
    if 'tag' in out:
        if out['tag'] not in mapping:raise ValueError('Unknown role serialization code')
        out['tag']=mapping[out['tag']]
    return out


def encode_native(value):return _convert(value,ENCODE)
def decode_wire(value):return _convert(value,DECODE)
