"""Connector interventions and ordinary example constraints for current source IR.

Only data structures and type/graph operations live here. Grading and oracle
access stay in source_interface_learning. Candidate agreement is never Omega.
"""
from copy import deepcopy

from .coverage import digest
from .interfaces import Relation
from .learning import parameterize_graph
from .scoped_program import expression_reads,value_type
from .typed_learning import candidates


def query_nodes(compiled):
    query=compiled['query'];by_name={n['name']:n for n in query.nodes}
    pending=list(expression_reads(query.query));reached=set()
    while pending:
        name=pending.pop()
        if name in reached:continue
        reached.add(name)
        if name in by_name:pending.extend(query.node_reads(by_name[name]))
    return reached&set(by_name)


def connector_identity(compiled,node_name,graph):
    """Mask values/identifiers, retaining the full source program's typed shape.

    The same local graph can mean different things under two legal wrappers.
    Neither a source ID, native label, numeric value nor entity is a family key.
    All extracted primitive types/column relationships are available to MB.
    """
    program=compiled['program'];slots=compiled['slots'];columns={}
    inputs=[b['name'] for b in program['bindings']]+[o['name'] for o in program['observations']]+\
        [r['name'] for r in program['rule_residuals']]
    declarations=[n['name'] for n in program['nodes']]+[s['name'] for s in compiled['effective_scopes']]+\
        [c['name'] for c in program['clauses']]
    names={name:'slot'+str(i) for i,name in enumerate(inputs)}
    names.update({name:'node'+str(i) for i,name in enumerate(declarations)})
    def column(name):
        if name not in columns:columns[name]='column'+str(len(columns))
        return columns[name]
    types=[]
    for name in inputs:
        if name in slots:
            value=slots[name];kind={'type':value_type(value)}
            if isinstance(value,Relation):kind.update(columns=[column(c) for c in value.columns],closed=value.closed)
        else:kind={'type':'boolean'}
        types.append(kind)
    def normalize_graph(node):
        if 'slot' in node:return {'slot':names[node['slot']]}
        result={'op':node['op'],'inputs':[normalize_graph(c) for c in node['inputs']]}
        params={}
        for key,value in node.get('params',{}).items():
            if key.endswith('_slot'):params[key]=names[value]
            elif key in {'keys','from','to'}:
                params[key]=list(value) if node['op']=='group_by' and set(value)<={'owner','period','unit'} else [column(c) for c in value]
            else:params[key]=value
        if params:result['params']=params
        return result
    def shape(expression):
        if isinstance(expression,dict):
            if set(expression)=={'var'}:return {'var':names[expression['var']]}
            return {'op':expression['op'],'args':[shape(a) for a in expression['args']]}
        return {'literal_type':type(expression).__name__}
    by_name={n['name']:n for n in compiled['query'].nodes};reached=query_nodes(compiled)
    normalized=[]
    for name in declarations:
        if name not in reached:continue
        node=by_name[name]
        body=shape(node['body']) if node['kind']=='expression' else {
            'graph':'selected_candidate' if name==node_name else normalize_graph(node['body']['graph']),
            'project':node['body']['project']}
        normalized.append({'name':names[name],'kind':node['kind'],'body':body})
    parameterize_graph(graph)
    normalized_graph=normalize_graph(graph)
    signature=digest({'input_types':types,'nodes':normalized,'query':shape(compiled['query'].query)})
    return signature,digest(normalized_graph)


def connector_cases(compiled):
    """At most32 single-connector interventions in the accepted full program."""
    reached=query_nodes(compiled);by_name={n['name']:n for n in compiled['query'].nodes}
    cases=[];seen=set()
    for raw in compiled['program']['nodes']:
        if raw['kind']!='connector' or raw['name'] not in reached:continue
        selected=by_name[raw['name']]['body']['graph']
        for graph in candidates(compiled['slots'],[selected]):
            # The current strict wire shape makes the empty parameter object
            # explicit. The shared executor/enumerator permits its omission;
            # adding {} supplies no parameter value or missing semantics.
            def wire_graph(node):
                result=deepcopy(node)
                if 'op' in result:
                    result.setdefault('params',{})
                    result['inputs']=[wire_graph(c) for c in result['inputs']]
                return result
            graph=wire_graph(graph)
            try:signature,key=connector_identity(compiled,raw['name'],graph)
            except (KeyError,ValueError,TypeError):continue
            identity=digest({'node':raw['name'],'graph':graph})
            if identity in seen:continue
            seen.add(identity)
            origins=[u['pattern_hash'] for u in by_name[raw['name']].get('pattern_uses',[])]
            cases.append({'node':raw['name'],'graph':deepcopy(graph),'signature':signature,
                          'normalized_graph_hash':key,'case_hash':identity,
                          'selected_node_explicit_library_calls':origins,
                          'generator':'current model node and bounded typed enumeration; not proof of independent rediscovery'})
            if len(cases)==32:return cases
    return cases


def replace_connector(program,case):
    result=deepcopy(program)
    node=next(n for n in result['nodes'] if n['name']==case['node'])
    if node['kind']!='connector':raise ValueError('Connector intervention target changed')
    node['body']['graph']=deepcopy(case['graph'])
    return result


def fit_source_examples(records,*,horn_families=()):
    """Fit the common32-candidate/4-view material without collision selection.

    Frozen families contain only masked compatibility and graph hashes/counts;
    native answers and source-specific examples remain in the training records.
    """
    groups={}
    for record in records:
        for case in record.get('learning',{}).get('candidate_checks',[]):
            group=groups.setdefault(case['signature'],{})
            counts=group.setdefault(case['normalized_graph_hash'],{'matched':0,'failed':0,'unbound':0})
            for check in case['checks']:
                key='unbound' if check['status']!='executed' else 'matched' if check['matches_reference'] else 'failed'
                counts[key]+=1
    families=[]
    for signature,graphs in sorted(groups.items()):
        accepted=[key for key,c in sorted(graphs.items()) if c['matched'] and not c['failed'] and not c['unbound']]
        rejected=[key for key,c in sorted(graphs.items()) if c['failed']]
        families.append({'signature':signature,'accepted_graph_hashes':accepted,'rejected_graph_hashes':rejected,
            'candidate_counts':graphs})
    content={'schema':1,'frozen':True,'policy':'ordinary_same_source_program_examples',
        'metadata_policy':'all_same_budget_extracted_typed_values','families':families,
        'horn_families':list(horn_families),'source_count':len(records),'extra_model_calls':0,
        'source_answers_stored_as_patterns':False,'finite_candidate_pool_is_Omega':False}
    return {'content':content,'sha256':digest(content)}


def check_source_examples(compiled,frozen):
    if not frozen['content']['frozen'] or digest(frozen['content'])!=frozen['sha256']:
        raise ValueError('Frozen ordinary source example model changed')
    families={f['signature']:f for f in frozen['content']['families']}
    rejected=[];untested=[];checked=[];reached=query_nodes(compiled)
    for node in compiled['query'].nodes:
        if node['kind']!='connector' or node['name'] not in reached:continue
        signature,key=connector_identity(compiled,node['name'],node['body']['graph'])
        family=families.get(signature)
        checked.append({'node':node['name'],'signature':signature,'graph_hash':key})
        if family and key in family['rejected_graph_hashes']:rejected.append(node['name'])
        elif not family or key not in family['accepted_graph_hashes']:untested.append(node['name'])
    return {'accepted':not rejected,'rejected_nodes':rejected,'untested_nodes':untested,
        'checked':checked,'ordinary_example_synthesis_applied':True,'finite_candidate_pool_is_Omega':False}
