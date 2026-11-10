"""Native evidence sets and lossless, explicitly indexed public source views.

Sparse object keys are the original sentence-span IDs. Grammar can enforce
uniqueness without asking a language model to count a long evidence bitmap.
All source text, including unindexed gaps, stays in its original order.
"""


def encode_evidence(indices,count):
    if type(count)is not int or count<0:raise ValueError('Invalid public span count')
    if not isinstance(indices,list) or any(type(i)is not int or not 0<=i<count for i in indices):raise ValueError('Native evidence index outside public source')
    return {str(i):True for i in sorted(set(indices))}


def decode_evidence(selected,count):
    if not isinstance(selected,dict):raise ValueError('Native evidence must be a sparse span-ID set')
    ids=[]
    for key,value in selected.items():
        if not isinstance(key,str) or not key.isdigit() or str(int(key))!=key or not 0<=int(key)<count or value is not True:raise ValueError('Invalid native evidence span-ID set entry')
        ids.append(int(key))
    return sorted(ids)


def actor_public(public):
    document=public['document'];segments=[];position=0
    for i,(start,end) in enumerate(public['sentence_spans']):
        if not (position<=start<end<=len(document)):raise ValueError('Public sentence spans overlap or are out of order')
        if start>position:segments.append({'text':document[position:start]})
        segments.append({'span_id':i,'text':document[start:end]});position=end
    if position<len(document):segments.append({'text':document[position:]})
    if ''.join(s['text'] for s in segments)!=document:raise ValueError('Indexed view lost public source characters')
    return {**{k:v for k,v in public.items() if k not in ('document','sentence_spans')},'document_segments':segments}
