"""Lossless native evidence-set serialization, bounded by public span count.

Bit i refers to public sentence span i. This removes repeated-index generation
without adding, dropping or inferring any semantic evidence. Runtime decoding
accepts only the current format; old records are migrated explicitly offline.
"""


def encode_evidence(indices,count):
    if type(count)is not int or count<0:raise ValueError('Invalid public span count')
    if not isinstance(indices,list) or any(type(i)is not int or not 0<=i<count for i in indices):raise ValueError('Native evidence index outside public source')
    observed=set(indices)
    return ''.join('1' if i in observed else '0' for i in range(count))


def decode_evidence(bits,count):
    if not isinstance(bits,str) or len(bits)!=count or any(c not in '01' for c in bits):raise ValueError('Evidence bitmap must contain exactly one 0/1 per public span')
    return [i for i,c in enumerate(bits) if c=='1']
