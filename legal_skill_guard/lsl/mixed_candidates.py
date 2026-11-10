"""Finite, source-aligned alternatives and real native execution tables.

The model proposes records. This module only checks alignment, applies exact
edits and executes them. It never repairs a candidate from an answer/reference.
"""
import ast
from copy import deepcopy
import itertools

from .projection import compact
from .native_schema import obj,array,STRING
from .native_semantics import norm_graph,norm_result,predict,horn_scope_squares,norm_loss_domain
from .safe_program import assignments,validate,local_choices
from .native_scope import local_execution_table,native_square
from .scalar_proposals import source_index
from .semantic_witness import square_candidates
from .local_credit import preference


def proposal_request(record,primary):
    """No grading fields consulted; source-order selection precedes execution."""
    d=record['dataset'];public=record['public'];meta={}
    if d=='ContractNLI':return None
    if d in ('SARA_v2_Binary','RuleArena_Airline'):
        source,index=source_index(record);tree=validate(primary['program'])
        nodes=assignments(tree);counts={n.targets[0].id:sum(v.targets[0].id==n.targets[0].id for v in nodes) for n in nodes}
        inventory=[{'name':n.targets[0].id,'statement':ast.unparse(n)} for n in nodes if counts[n.targets[0].id]==1]
        if not inventory:return None
        instruction='Attribute source-rule assignments to the PUBLIC_POLICY lines, excluding current-case factual assignments. In source order select at most the first four attributable rule assignments. For each propose ONE genuinely different, plausible local semantic alternative as an assignment to the SAME name, preserving its exact set of input variable names. Do not fix the whole program, edit facts, change other statements, enumerate arbitrary thresholds, or supply answers. Alternatives may express negation, exception, threshold or one competing interpretation of that same policy line. Use the public line index source_id. No answer key is available.'
        grammar=obj({'blocks':{**array(obj({'name':STRING,'source_id':{'type':'integer','minimum':0,'maximum':len(index)-1},'alternative':STRING})),'maxItems':4}})
        body={'current_program':primary['program'],'assignment_inventory':inventory,'PUBLIC_POLICY':index,
              'public_case':{k:v for k,v in public.items() if k not in ('rules','rules_context')}}
        meta={'source':source,'index':index}
    elif d=='NormBench':
        g=norm_graph(record,primary);source=public['rule_text'];available=[]
        for i,n in enumerate(g['nodes']):
            if n['kind']!='leaf':continue
            starts=[j for j in range(len(source)) if source.startswith(n['text'],j)]
            if len(starts)==1:available.append((starts[0],i,n))
        slots=[{'slot':i,'quote':n['text'],'source_start':start,'current':{'tag':n['tag'],'text':n['text']}} for start,i,n in sorted(available)[:4]]
        if not slots:return None
        # Native tag serialization stays ASCII throughout the wire protocol.
        from .role_codec import ENCODE
        for s in slots:s['current']['tag']=ENCODE[s['current']['tag']]
        from .native_schema import schema
        leaf=schema('NormBench')['$defs']['condition']['anyOf'][0]
        instruction='For each listed source-local condition record propose exactly one plausible competing semantic reading. Preserve source support, change only this record (its role/content, or null for omission); do not edit any other condition, parent, branch, or effect. Use only schema role codes, not Chinese tags. A competing reading is a proposal, not a known correction. Do not output an answer or full graph.'
        grammar=obj({'blocks':{**array(obj({'slot':{'type':'integer','enum':[s['slot'] for s in slots]},'alternative':{'anyOf':[leaf,{'type':'null'}]}})),'maxItems':len(slots)}})
        body={'rule_text':source,'context':public['full_article_text'],'slots':slots};meta={'slots':slots}
    elif d=='ProofWriter_OWA_depth5':
        # Source-order fact slots are an explicit generation contract; quote
        # attribution is checked, never silently inferred from a gold atom.
        facts=primary['program']['facts'];slots=[{'slot':i,'current':a} for i,a in enumerate(facts)]
        if not slots:return None
        atom={'type':'array','prefixItems':[STRING,array(STRING),{'type':'boolean'}],'minItems':3,'maxItems':3,'items':False}
        instruction='For each listed acquired fact, identify the exact supporting public fact sentence and propose one plausible competing local atom (or null for omission). Preserve a ground atom interface. Change only this fact, never the rules, other facts or query. Propose an actual competing reading, not an answer. Source sentence must be copied exactly. Select source-supported slots in public fact order, at most four.'
        grammar=obj({'blocks':{**array(obj({'slot':{'type':'integer','enum':[s['slot'] for s in slots]},'quote':STRING,'alternative':{'anyOf':[atom,{'type':'null'}]}})),'maxItems':min(4,len(slots))}})
        body={'public':public,'slots':slots};meta={'slots':slots}
    else:raise ValueError(d)
    return {'messages':[{'role':'system','content':'Return only the requested JSON; thinking is disabled. Propose local alternatives without a reference answer.'},
                         {'role':'user','content':instruction+'\n'+compact(body)}], 'schema':grammar,'metadata':meta}


def _norm_replace(g,index,value):
    g=deepcopy(g)
    if value is None:
        del g['nodes'][index];del g['parents'][index]
        g['parents']=[p-1 if p>index else p for p in g['parents']]
    else:
        from .role_codec import DECODE
        g['nodes'][index].update(tag=DECODE[value['tag']],text=value['text'])
        # Recompute grounding through the strict native adapter, without using
        # reference provenance or pretending a newly worded record is literal.
    return norm_result(g)


def _norm_native_constraints(record,g,index):
    """Full native annotations fix all other content and scope in this task.

    We do not call unconstrained permutations 'valid common contexts' when
    the independently supplied dense structure already excludes them.
    """
    from .composition_data import gold_graph,canonical_graph
    gold=gold_graph(record['native_record'])
    def signature(graph,skip):
        copy=deepcopy(graph);copy['nodes'][skip].update(tag='__LOCAL_SLOT__',text='__LOCAL_SLOT__')
        return canonical_graph(copy)
    slot=g['nodes'][index];possible=[i for i,n in enumerate(gold['nodes']) if n['kind']=='leaf' and n['unit']==slot['unit']]
    return any(signature(g,index)==signature(gold,i) for i in possible)


def build_tables(record,primary,alternatives=None):
    d=record['dataset'];result={'source':record['key'],'dataset':d,'blocks':[],'squares':[],
        'prediction':None,'valid':False,'fallback':False,'errors':[],
        'effective_supervision':{'native_task':1,'native_structure':int(d in ('NormBench','ProofWriter_OWA_depth5')),
            'native_evidence':int(d=='ContractNLI'),'directed_interaction_from_acquired_program':0,
            'official_reference_used_as_prediction_tool':False}}
    try:
        result['prediction']=predict(record,primary);result['valid']=result['prediction']['valid']
        if not result['valid']:return result
        # Graph objects are deterministic serializable prediction artifacts.
        if d=='ContractNLI':result['mask_reason']='no_independent_contract_execution_oracle';return result
        if d in ('SARA_v2_Binary','RuleArena_Airline'):
            proposal=deepcopy(primary);source,index=source_index(record);proposal['blocks']=[]
            for b in (alternatives or {}).get('blocks',[]):
                sid=b['source_id']
                if type(sid)is not int or not 0<=sid<len(index):continue
                proposal['blocks'].append({**b,'quote':index[sid]['text'],'source_start':index[sid]['start']})
            for b in local_choices(proposal,source):
                table=local_execution_table(proposal,b,record['public'],d,record['grade']['answer'],record['key']+':'+b['name'])
                # Keep the complete raw execution record, then constrain the
                # training completions by the known native QA observation.
                compatible=[c for c in table['contexts'] if min(c['losses'])==0]
                table['all_contexts']=table['contexts'];table['contexts']=compatible
                table['loss_table']=[c['losses'] for c in compatible]
                table['choices']=b['choices'];table['quote']=b['quote']
                table['credit']=preference(table['loss_table']) if compatible else {'status':'no_native_compatible_context','weight':0.,'preferred':None}
                result['blocks'].append(table)
            s=native_square(proposal,record['public'],d,record['grade']['answer'],record['key'])
            if s is not None:
                s['cells']=[{'program':p} for p in s['programs']];result['squares'].append(s)
        elif d=='ProofWriter_OWA_depth5':
            from .horn_codec import normalize as normalize_horn,atom as normalize_atom,rules_key,theory_key
            primary={**primary,'program':normalize_horn(primary['program'])}
            scopes=horn_scope_squares(primary['program'],record['key']);contexts=[primary]
            for s in scopes:
                for c in s['cells']:
                    if compact(c['program']) not in {compact(x['program']) for x in contexts}:contexts.append(c)
            unique={}
            for c in contexts:unique.setdefault(theory_key(c['program']),c)
            contexts=list(unique.values())[:8]
            used=set()
            local_blocks=sorted((alternatives or {}).get('blocks',[]),key=lambda b:record['public']['facts'].index(b['quote']) if b.get('quote') in record['public']['facts'] else len(record['public']['facts']))[:4]
            for b in local_blocks:
                i=b['slot'];quote=b['quote'];alt=normalize_atom(b['alternative']) if b['alternative']is not None else None
                if type(i)is not int or not 0<=i<len(primary['program']['facts']) or i in used or quote not in record['public']['facts']:continue
                used.add(i);rows=[]
                for c in contexts:
                    cells=[];predictions=[]
                    for choice in (primary['program']['facts'][i],alt):
                        v=deepcopy(c)
                        if choice is None:del v['program']['facts'][i]
                        else:v['program']['facts'][i]=choice
                        try:e=predict(record,v)
                        except Exception:break
                        if not e['valid']:break
                        cells.append(v);predictions.append(e['answer'])
                    if len(cells)==2:
                        losses=[int(a!=record['grade']['answer']) for a in predictions]
                        if min(losses)==0:rows.append({'cells':cells,'predictions':predictions,'losses':losses})
                # Known native Horn structure fixes the rule composition;
                # only an exactly matching reference context may pass here.
                reference=normalize_horn(record['grade']['horn'])
                from collections import Counter
                # Public and formal fact lists need not have the same order.
                # Align this already supplied TRAIN annotation by its exact
                # controlled-English source, never by a guessed list index.
                from legal_skill_guard.rr.public_horn import parse_atom
                annotated=parse_atom(quote)
                gold_fact=[annotated.predicate,list(annotated.arguments),annotated.positive]
                if gold_fact not in reference['facts']:
                    result['blocks'].append({'quote':quote,'slot':i,'choices':[primary['program']['facts'][i],alt],
                        'contexts':[],'loss_table':[],'credit':{'status':'native_fact_quote_alignment_unverified','weight':0.,'preferred':None}});continue
                known_facts=list(reference['facts']);known_facts.remove(gold_fact)
                def fixed_context(row):
                    p=row['cells'][0]['program']
                    return (rules_key(p['rules'])==rules_key(reference['rules']) and p['query']==reference['query'] and
                            Counter(map(compact,p['facts'][:i]+p['facts'][i+1:]))==Counter(map(compact,known_facts)))
                rows=[r for r in rows if fixed_context(r)]
                exhaustive=bool(rows) # annotated composition independently fixed
                table=[r['losses'] for r in rows]
                result['blocks'].append({'quote':quote,'slot':i,'choices':[primary['program']['facts'][i],alt],
                    'contexts':rows,'loss_table':table,'independently_fixed':exhaustive,'exhaustive':False,
                    'credit':preference(table,independently_fixed=exhaustive) if table else {'status':'no_native_compatible_context','weight':0.,'preferred':None}})
            for s in scopes:
                executions=[predict(record,c) for c in s['cells']]
                if all(e['valid'] for e in executions):
                    s['predictions']=[e['answer'] for e in executions];s['mean_errors']=[int(e['answer']!=record['grade']['answer']) for e in executions];result['squares'].append(s)
        elif d=='NormBench':
            from .composition_data import gold_graph
            g=norm_graph(record,primary);gold=gold_graph(record['native_record']);used=set()
            for b in (alternatives or {}).get('blocks',[]):
                i=b['slot']
                if type(i)is not int or not 0<=i<len(g['nodes']) or g['nodes'][i]['kind']!='leaf' or i in used:continue
                used.add(i)
                from .role_codec import encode_native
                choices=[encode_native({'tag':g['nodes'][i]['tag'],'text':g['nodes'][i]['text']}),b['alternative']]
                if not _norm_native_constraints(record,g,i):
                    result['blocks'].append({'slot':i,'quote':g['nodes'][i]['text'],'choices':choices,'credit':{'status':'other_dense_native_constraints_violated','weight':0.,'preferred':None},'contexts':[],'loss_table':[]});continue
                alt=_norm_replace(g,i,b['alternative']);cells=[primary,alt]
                gs=[norm_graph(record,c) for c in cells];domain=norm_loss_domain(gold,gs,record['key']+':'+str(i))
                if not domain['scorable']:
                    result['blocks'].append({'slot':i,'quote':g['nodes'][i]['text'],'choices':choices,'contexts':[],'loss_table':[],
                        'credit':{'status':domain['unscorable_reason'],'weight':0.,'preferred':None}});continue
                table=[domain['errors']]
                result['blocks'].append({'slot':i,'quote':g['nodes'][i]['text'],
                    'choices':choices,
                    'contexts':[{'cells':cells,'losses':domain['errors'],'predictions':domain['signatures']}],
                    'loss_table':table,'independently_fixed':True,'exhaustive':False,
                    'credit':preference(table,independently_fixed=True)})
            for s in square_candidates(g):
                gs=[{**g,'parents':p} for p in s['parents']]
                domain=norm_loss_domain(gold,gs,record['key']+':square')
                if not domain['scorable']:continue
                from .semantic_witness import assignments,evaluate
                keys,values,_=assignments(g,64)
                result['squares'].append({**s,'cells':gs,
                    'predictions':[evaluate(v,keys,values).tolist() for v in gs],
                    'mean_errors':domain['errors'],'abstract_not_case_gold':True})
        result['effective_supervision']['directed_interaction_from_acquired_program']=int(bool(result['squares']))
        return result
    except Exception as e:
        result['errors'].append(type(e).__name__+': '+str(e));return result
