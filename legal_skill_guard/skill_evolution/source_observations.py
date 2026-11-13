"""Lossless source inputs plus grounded, fallible learned observations for G.

This is an interface, not a legal extractor. Existing acquired source programs
remain upstream readers; all their supplied output and current text are retained.
The relational learner cannot execute arbitrary Python on text. Its search bias
must not be confused with an impossibility claim about an old raw-text reader.
"""
from copy import deepcopy

from .objects import digest
from .semantic_operations import ground_answers
from .span_compiler import occurrences


def fact(predicate,*arguments):
    return {'predicate':predicate,'arguments':list(arguments),'sign':'positive'}


SIGNATURES = {
    'source_text':(['text'],'observed'),
    'source_unit':(['unit'],'observed'),
    'unit_text':(['unit','text'],'observed'),
    'next_unit':(['unit','unit'],'observed'),
    'json_root':(['field','json_node'],'observed'),
    'json_kind':(['json_node','json_kind'],'observed'),
    'json_entry':(['json_node','field','json_node'],'observed'),
    'json_item':(['json_node','position','json_node'],'observed'),
    'json_scalar':(['json_node','scalar'],'observed'),
    'legacy_root':(['term'],'observed'),
    'term_constructor':(['term','constructor'],'observed'),
    'term_child':(['term','position','term'],'observed'),
    'term_scalar':(['term','scalar'],'observed'),
    'root_support':(['term','unit'],'observed'),
    'reader_query':(['query','operation'],'observed'),
    'query_window':(['query','unit'],'observed'),
    'query_focus':(['query','unit'],'observed'),
    'reader_observed_value':(['query','choice'],'observed'),
    'query_choice':(['query','choice'],'observed'),
    'query_unknown':(['query'],'observed'),
    'query_unread':(['query'],'observed'),
    'evidence_unit':(['query','unit'],'observed'),
    'evidence_quote':(['query','unit','text'],'observed'),
}


def signatures():
    return {p:{'arguments':list(args),'kind':kind} for p,(args,kind) in SIGNATURES.items()}


def encode_source_observations(source_id, *, source_text, units, source_output,
                               operations, queries, answers, scope):
    """Retain every G-visible value, including order, text and unknown/unread.

    Only the actual answered subset is quote-grounded. Completion branches are
    solver possibilities, not asserted readings; an empty branch preserves the
    possibility that no declared choice describes an unread meaning.
    Native labels/source review enter separate constraints, never these inputs.
    """
    if not isinstance(source_id,str) or not source_id or not isinstance(source_text,str):
        raise ValueError('A source identity and its actual text are required')
    if scope not in ('focus_last','window'):
        raise ValueError('Preserve the actual acquired focus/window contract')
    # Validate operation structure without interpreting demonstrations as current
    # facts. Their original-parent validation belongs to asset acquisition.
    import jsonschema
    from .semantic_operations import OPERATION
    jsonschema.validate(operations,{'type':'array','items':OPERATION})
    ops={o['name']:o for o in operations};by_unit={u['id']:u for u in units}
    if len(ops)!=len(operations) or len(by_unit)!=len(units):
        raise ValueError('Distinct acquired operations and actual source units required')
    for op in operations:
        choices=[c['name'] for c in op['choices']]
        if len(set(choices))!=len(choices) or 'unknown' in choices:
            raise ValueError('Declared distinct choices; unknown is reserved')
    for u in units:
        if type(u['id']) is not int or u['id']<0 or not occurrences(source_text,u['text']):
            raise ValueError('Units must quote the actual current source')
    by_query={q['id']:q for q in queries}
    if len(by_query)!=len(queries) or any(not isinstance(q['id'],str) or not q['id'] for q in queries):
        raise ValueError('Distinct current queries required')
    for q in queries:
        if q['operation'] not in ops or not q['unit_ids'] or len(set(q['unit_ids']))!=len(q['unit_ids']) \
                or not set(q['unit_ids'])<=set(by_unit):
            raise ValueError('Each actual query needs its declared operation and current window')
    ids=[a['id'] for a in answers]
    if len(set(ids))!=len(ids) or not set(ids)<=set(by_query):
        raise ValueError('At most one actual answer per planned query')
    raw={'answers':[{k:deepcopy(a[k]) for k in ('id','choice','evidence')} for a in answers]}
    for a in raw['answers']:
        a['evidence']=[{k:w[k] for k in ('unit_id','quote')} for w in a['evidence']]
    grounded=ground_answers(operations,[q for q in queries if q['id'] in set(ids)],units,raw)
    by_answer={a['id']:a for a in grounded}
    visible={'source_text':source_text,'units':deepcopy(units),'source_output':deepcopy(source_output),
        'operations':deepcopy(operations),'queries':deepcopy(queries),'answers':grounded,'scope':scope}
    facts=[fact('source_text',source_text)];unknown=[];nodes={};roots={};term_supports={};json_count=0

    def json_tree(value):
        nonlocal json_count
        name='j'+str(json_count);json_count+=1
        kind='object' if isinstance(value,dict) else 'array' if isinstance(value,list) else 'null' if value is None else 'scalar'
        facts.append(fact('json_kind',name,kind))
        if isinstance(value,dict):
            for k,v in sorted(value.items()):facts.append(fact('json_entry',name,k,json_tree(v)))
        elif isinstance(value,list):
            for i,v in enumerate(value):facts.append(fact('json_item',name,i,json_tree(v)))
        elif value is not None:facts.append(fact('json_scalar',name,value))
        return name

    for key,value in visible.items():facts.append(fact('json_root',key,json_tree(value)))
    for i,u in enumerate(units):
        facts.extend([fact('source_unit',u['id']),fact('unit_text',u['id'],u['text'])])
        if i:facts.append(fact('next_unit',units[i-1]['id'],u['id']))

    def term_tree(value,supports):
        name='t'+str(len(nodes));nodes[name]=deepcopy(value);term_supports[name]=list(supports)
        if isinstance(value,list):
            if not value or not isinstance(value[0],str):raise ValueError('An existing term needs its acquired constructor')
            facts.append(fact('term_constructor',name,value[0]))
            for i,v in enumerate(value[1:]):facts.append(fact('term_child',name,i,term_tree(v,supports)))
        elif type(value) in (str,int,float,bool):facts.append(fact('term_scalar',name,value))
        else:raise ValueError('Unexpected existing typed term; do not coerce or fill it')
        return name

    for row in source_output['statements']:
        if not set(row['support_ids'])<=set(by_unit):raise ValueError('Legacy root cites a noncurrent unit')
        name=term_tree(row['term'],row['support_ids']);roots[name]=deepcopy(row);facts.append(fact('legacy_root',name))
        facts.extend(fact('root_support',name,u) for u in row['support_ids'])
    for q in queries:
        qid=q['id'];facts.append(fact('reader_query',qid,q['operation']))
        facts.extend(fact('query_window',qid,u) for u in q['unit_ids'])
        if scope=='focus_last':facts.append(fact('query_focus',qid,q['unit_ids'][-1]))
        a=by_answer.get(qid)
        if a:
            facts.append(fact('reader_observed_value',qid,a['choice']))
            for w in a['evidence']:
                facts.extend([fact('evidence_unit',qid,w['unit_id']),fact('evidence_quote',qid,w['unit_id'],w['quote'])])
        if a and a['choice']!='unknown':facts.append(fact('query_choice',qid,a['choice']))
        else:
            facts.append(fact('query_unknown' if a else 'query_unread',qid))
            unknown.append([[fact('query_choice',qid,c['name'])] for c in ops[q['operation']]['choices']]+[[]])
    context={'id':source_id,'facts':facts,'unknown_groups':unknown,'required':[],'forbidden':[]}
    return {'context':context,'visible_inputs':visible,'visible_inputs_sha256':digest(visible),
        'contract_sha256':digest({'version':1,'signatures':SIGNATURES,'scope':scope,
            'raw_text_retained':True,'old_reader_is_upstream':True}),
        'legacy_roots':roots,'term_nodes':nodes,'term_supports':term_supports,
        'grounding_certifies_source_meaning':False,'new_model_requests':0}


def decode_visible_inputs(encoded):
    """Check that the generic relational view loses no supplied G input."""
    facts=encoded['context']['facts'];kind={};scalars={};entries={};items={};roots={}
    for a in facts:
        p=a['predicate'];args=a['arguments']
        if p=='json_kind':kind[args[0]]=args[1]
        elif p=='json_scalar':scalars[args[0]]=args[1]
        elif p=='json_entry':entries.setdefault(args[0],{})[args[1]]=args[2]
        elif p=='json_item':items.setdefault(args[0],{})[args[1]]=args[2]
        elif p=='json_root':roots[args[0]]=args[1]
    def read(node):
        k=kind[node]
        if k=='null':return None
        if k=='scalar':return scalars[node]
        if k=='object':return {key:read(child) for key,child in entries.get(node,{}).items()}
        return [read(child) for _,child in sorted(items.get(node,{}).items())]
    return {field:read(node) for field,node in roots.items()}


def retain_legacy_roots(encoded, outputs):
    """Render explicitly selected old roots; no default output on solver failure."""
    identities=[]
    for row in outputs:
        if row['predicate']!='keep_root':raise ValueError('Not a legacy-root selection output')
        identity,=row['arguments']
        if identity not in encoded['legacy_roots']:raise ValueError('Output names no actual current root')
        if identity not in identities:identities.append(identity)
    return [deepcopy(encoded['legacy_roots'][i]) for i in identities]
