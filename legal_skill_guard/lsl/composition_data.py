"""Branch-blind local nodes and evaluator-only native edge labels."""
from collections import defaultdict, deque
from copy import deepcopy

from .projection import compact, native_projection, neutral, support
from .data import nonspace


def head_key(h, units):
    return compact([units[h['u']],h['a'],h['k'],h['e']])


def inventory_nodes(state, source, item_id):
    nodes=[];counts=defaultdict(int)
    def add(n):
        identity=compact(n);ordinal=counts[identity];counts[identity]+=1
        n={**n,'id':neutral(item_id,identity,ordinal)};nodes.append(n)
    for h in state['h']:
        add({'kind':'branch','text':compact([h['a'],h['k'],h['e']]),
             'unit':state['u'][h['u']],'head':deepcopy(h), 'support':support(source,state['u'][h['u']],h['a'])})
    for p,tag,u in state['v']:
        add({'kind':'leaf','text':state['p'][p],'tag':tag,'unit':state['u'][u],
             'support':support(source,state['u'][u],state['p'][p])})
    for op,u in state['o']:
        # No descendant-derived span, depth or gold root/branch label.
        add({'kind':op,'text':op,'unit':state['u'][u], 'support':{'kind':'unresolved','candidates':[]}})
    return sorted(nodes,key=lambda n:n['id'])


def gold_graph(record):
    state=native_projection(record);source=record['input']['rule_text']
    nodes=inventory_nodes(state,source,record['item_id']);queues=defaultdict(deque)
    for i,n in enumerate(nodes):
        if n['kind']=='branch':key=('branch',head_key(n['head'],state['u']))
        elif n['kind']=='leaf':key=('leaf',n['unit'],n['tag'],n['text'])
        else:key=(n['kind'],n['unit'])
        queues[key].append(i)
    parents=[-1]*len(nodes)
    for unit in record['gold']['units']:
        ut=unit['unit_text']
        for b in unit['branches']:
            h={'u':state['u'].index(ut),'a':b['anchor']['text'],'k':b['norm_kind'],
               'e':[e['effect_text'] for e in b['effects']]}
            branch=queues[('branch',head_key(h,state['u']))].popleft()
            def visit(tree,parent):
                if tree is None:return
                key=(tree['op'],ut) if 'op' in tree else ('leaf',ut,tree['tag'],tree['text'])
                index=queues[key].popleft();parents[index]=parent
                if 'op' in tree:
                    for child in tree['items']:visit(child,index)
            visit(b.get('conditions'),branch)
    if any(queues.values()):raise ValueError('Native records lost by local projection')
    graph={'item_id':record['item_id'],'source':source,'context':record['input']['full_article_text'],
           'family_id':record['family_id'],'nodes':nodes,'parents':parents}
    valid_graph(graph,raise_error=True)
    return graph


def valid_graph(graph,raise_error=False):
    nodes=graph['nodes'];parents=graph['parents'];errors=[];children=defaultdict(list)
    if len(parents)!=len(nodes):errors.append('Parent vector length')
    else:
        for i,n in enumerate(nodes):
            p=parents[i]
            if n['kind']=='branch':
                if p!=-1:errors.append('Branch cannot have parent')
                continue
            if type(p) is not int or not 0<=p<len(nodes) or nodes[p]['kind'] not in ('branch','AND','OR') or p==i:
                errors.append('Illegal parent');continue
            children[p].append(i);seen={i};j=p
            while j!=-1:
                if j in seen:errors.append('Cycle');break
                seen.add(j);j=parents[j]
                if not -1<=j<len(nodes):break
        for i,n in enumerate(nodes):
            if n['kind']=='branch' and len(children[i])>1:errors.append('Multiple branch roots')
            # The native schema contains empty AND/OR nodes. Preserve them:
            # AND([])=true, OR([])=false, with no invented children.
    if errors and raise_error:raise ValueError('Invalid forest: '+','.join(sorted(set(errors))))
    return not errors


def branch_of(graph,index):
    seen=set();nodes=graph['nodes'];parents=graph['parents']
    while nodes[index]['kind']!='branch':
        if index in seen or parents[index]<0:return -1
        seen.add(index);index=parents[index]
    return index


def children_of(graph):
    out=defaultdict(list)
    for i,p in enumerate(graph['parents']):
        if p>=0:out[p].append(i)
    return out


def atom_keys(graph):
    keys={}
    for i,n in enumerate(graph['nodes']):
        if n['kind']!='leaf':continue
        spans=n['support']['candidates']
        # Sharing requires the same uniquely grounded occurrence and role.
        # Ambiguous/inferred native instances retain separate truth variables.
        keys[i]=compact([n['tag'],n['text'],spans[0]]) if len(spans)==1 else n['id']
    return keys


def canonical_tree(graph,index,*,semantic=False):
    n=graph['nodes'][index];children=children_of(graph)
    if n['kind']=='leaf':
        return ['leaf',atom_keys(graph)[index]] if semantic else ['leaf',n['tag'],nonspace(n['text'])]
    items=[canonical_tree(graph,c,semantic=semantic) for c in children[index]]
    return [n['kind'],sorted(items,key=compact)]


def canonical_graph(graph):
    if not valid_graph(graph):return None
    nodes=graph['nodes'];children=children_of(graph);result=[]
    for i,n in enumerate(nodes):
        if n['kind']=='branch':
            import json
            anchor,kind,effects=json.loads(n['text'])
            head=[nonspace(anchor),kind,sorted(nonspace(e) for e in effects)]
            result.append([nonspace(n['unit']),head,[canonical_tree(graph,c) for c in children[i]]])
    return sorted(result,key=compact)


def node_text(node):
    if node['kind']=='branch':return '规范分支 '+node['text']
    if node['kind']=='leaf':return '条件 '+node['tag']+' '+node['text']
    return '逻辑算子 '+node['kind']


def strip_labels(graph):
    return {k:deepcopy(v) for k,v in graph.items() if k!='parents'}


def b0_to_graph(result,source,item_id,family_id):
    if set(result)!={'units'} or not isinstance(result['units'],list):raise ValueError('Invalid whole-graph root')
    # This adapter validates generated semantic records; it adds no rules.
    from .projection import unit_span, KINDS, TAGS
    units=result['units'];nodes=[];parents=[];counters=defaultdict(int)
    def add(n,parent=-1):
        ordinal=counters[compact(n)];counters[compact(n)]+=1
        nodes.append({**n,'id':neutral(item_id,n,ordinal)});parents.append(parent);return len(nodes)-1
    for u in units:
        if set(u)!={'text','b'} or not isinstance(u['text'],str) or not unit_span(source,u['text']) or not isinstance(u['b'],list):raise ValueError('Invalid generated unit')
        for b in u['b']:
            if set(b)!={'a','k','e','c'} or not isinstance(b['a'],str) or b['k'] not in KINDS or not isinstance(b['e'],list) or not all(isinstance(s,str) for s in b['e']):raise ValueError('Invalid generated branch')
            bi=add({'kind':'branch','text':compact([b['a'],b['k'],b['e']]),'unit':u['text'],
                    'head':{'a':b['a'],'k':b['k'],'e':b['e']},'support':support(source,u['text'],b['a'])})
            def visit(t,parent):
                if t is None:return
                if not isinstance(t,dict):raise ValueError('Invalid condition')
                if 'op' in t:
                    if set(t)!={'op','items'} or t['op'] not in ('AND','OR') or not isinstance(t['items'],list):raise ValueError('Invalid operator')
                    i=add({'kind':t['op'],'text':t['op'],'unit':u['text'],'support':{'kind':'unresolved','candidates':[]}},parent)
                    for child in t['items']:visit(child,i)
                else:
                    if set(t)!={'tag','text'} or t['tag'] not in TAGS or not isinstance(t['text'],str):raise ValueError('Invalid leaf')
                    add({'kind':'leaf','text':t['text'],'tag':t['tag'],'unit':u['text'],'support':support(source,u['text'],t['text'])},parent)
            visit(b['c'],bi)
    graph={'item_id':item_id,'family_id':family_id,'source':source,'nodes':nodes,'parents':parents}
    valid_graph(graph,raise_error=True);return graph
