"""Learn source-structural binding policies, without learning legal meanings.

Acquired, source-grounded fragments supply all semantic terms and open slots.
The learned object is a DNF over whole typed binding assignments. Repeated
attributes can share a provider; distinct slots need not occupy disjoint text.
No source identity, native label or default legal fact is a feature.
"""
from copy import deepcopy
import heapq
from itertools import combinations, product

from .objects import digest
from .scoped_grammar import term_sort


def slots(term):
    found = {}
    def visit(t):
        if isinstance(t, dict):
            if set(t) != {'slot', 'sort'} or not all(isinstance(t[k],str) and t[k] for k in t):
                raise ValueError('An open term needs a named, typed slot')
            if t['slot'] in found and found[t['slot']] != t['sort']:
                raise ValueError('Repeated slot has conflicting types')
            found[t['slot']] = t['sort']
        elif isinstance(t,list):
            for child in t[1:]:visit(child)
    visit(term)
    return found


def substitute(term, values):
    if isinstance(term,dict):return deepcopy(values[term['slot']])
    if isinstance(term,list):return [term[0],*(substitute(t,values) for t in term[1:])]
    return term


def required_slots(claim):
    found=slots(claim['term'])
    for req in claim['requires']:
        if set(req)!={'slot','sort','equals'}:raise ValueError('Malformed acquired source requirement')
        if req['slot'] in found and found[req['slot']]!=req['sort']:
            raise ValueError('Conflicting source requirement type')
        found[req['slot']]=req['sort']
    return dict(sorted(found.items()))


def validate_fragments(fragments,schema):
    if len({f['id'] for f in fragments})!=len(fragments):raise ValueError('Duplicate fragment identity')
    for fragment in fragments:
        if fragment['kind'] not in ('value','claim'):raise ValueError('Unknown fragment kind')
        found=required_slots(fragment);names=list(found)
        def replace(t):
            if isinstance(t,dict):return {'$':names.index(t['slot'])}
            if isinstance(t,list):return [t[0],*(replace(c) for c in t[1:])]
            return t
        term_sort(replace(fragment['term']),schema,list(found.values()))
        if fragment['kind']=='value' and found:raise ValueError('A provider must have an acquired closed value')
        for req in fragment['requires']:
            if term_sort(req['equals'],schema)!=req['sort']:raise ValueError('Source requirement has wrong acquired type')


def family(claim):
    return digest({'term':claim['term'],'requires':claim['requires']})


def alpha_claim(claim):
    """Rename bound variables only, preserving repeated-variable identity."""
    names={}
    def name(old):
        if old not in names:names[old]='v'+str(len(names))
        return names[old]
    def replace(t):
        if isinstance(t,dict):return {'slot':name(t['slot']),'sort':t['sort']}
        if isinstance(t,list):return [t[0],*(replace(c) for c in t[1:])]
        return t
    value=deepcopy(claim);value['term']=replace(claim['term'])
    value['requires']=[{**r,'slot':name(r['slot'])} for r in claim['requires']]
    return value,names


def assignments(claim, fragments, schema, *, capacity=12000):
    names=list(required_slots(claim));choices=[]
    for name,sort in required_slots(claim).items():
        required=[r['equals'] for r in claim['requires'] if r['slot']==name]
        choices.append([f for f in fragments if f['kind']=='value' and not slots(f['term'])
            and term_sort(f['term'],schema)==sort and all(f['term']==v for v in required)])
    if not names:return [{}]
    size=1
    for c in choices:size*=len(c)
    if size>capacity:raise ValueError('Binding search capacity exceeded; no partial selection')
    return [dict(zip(names,values)) for values in product(*choices)]


def features(claim, assignment):
    out={}
    for name,provider in sorted(assignment.items()):
        a,b=claim['unit'],provider['unit'];key=name+':'
        out.update({key+'same_unit':a==b,key+'before':b<a,key+'after':b>a,
            key+'previous_unit':b==a-1,key+'next_unit':b==a+1,
            key+'current_header':b==claim['header'],
            key+'same_header':claim['header'] is not None and claim['header']==provider['header']})
    for a,b in combinations(sorted(assignment),2):
        x,y=assignment[a],assignment[b];key=a+'~'+b+':'
        out.update({key+'same_unit':x['unit']==y['unit'],
            key+'same_header':x['header'] is not None and x['header']==y['header'],
            key+'same_provider':x['id']==y['id']})
    return out


def fit_dnf(examples, *, max_literals=3):
    """Exact finite set cover of positive assignments, excluding all negatives.

    Literal count then clause count determine description length. If the
    acquired observations cannot be separated, report it instead of inventing
    identity features or accepting some known false assignment.
    """
    if not examples or not any(e['positive'] for e in examples):
        raise ValueError('Actual positive binding observations required')
    keys=sorted(examples[0]['features'])
    if any(set(e['features'])!=set(keys) for e in examples):raise ValueError('Different assignment feature vocabularies')
    positives=[e['features'] for e in examples if e['positive']]
    negatives=[e['features'] for e in examples if not e['positive']]
    clauses={}
    for n in range(min(max_literals,len(keys))+1):
        for chosen in combinations(keys,n):
            for values in product((False,True),repeat=n):
                clause=list(zip(chosen,values))
                match=lambda row:all(row[k]==v for k,v in clause)
                if any(match(row) for row in negatives):continue
                mask=sum(1<<i for i,row in enumerate(positives) if match(row))
                if not mask:continue
                old=clauses.get(mask)
                if old is None or (len(clause),clause)<(len(old),old):clauses[mask]=clause
    target=(1<<len(positives))-1
    covered_all=0
    for mask in clauses:covered_all|=mask
    if covered_all!=target:
        raise ValueError('No consistent structural binding policy in the declared language')
    # Solve only masks reachable by useful clauses, preserving an exact result.
    best={0:(0,0,[])};queue=[(0,0,[],0)]
    while queue:
        cost,count,chosen,mask=heapq.heappop(queue)
        if best.get(mask)!=(cost,count,chosen):continue
        if mask==target:break
        for covered,clause in clauses.items():
            nxt=mask|covered
            if nxt==mask:continue
            candidate=(cost+len(clause),count+1,chosen+[clause])
            if nxt not in best or candidate<best[nxt]:
                best[nxt]=candidate;heapq.heappush(queue,(*candidate,nxt))
        if len(best)>262144:raise ValueError('Exact binding-policy search capacity exceeded')
    result=best[target]
    return {'clauses':result[2],'description_literals':result[0],
        'positive_assignments':len(positives),'negative_assignments':len(negatives),
        'native_labels_as_features':False,'source_identity_as_feature':False}


def accepts(policy, observed):
    return any(all(observed[k]==v for k,v in c) for c in policy['clauses'])


def learn(cases, schema, *, cross_slot=True):
    grouped={}
    for case in cases:
        fragments=case['fragments'];byid={f['id']:f for f in fragments}
        validate_fragments(fragments,schema)
        for demo in case['bindings']:
            claim,names=alpha_claim(byid[demo['claim']])
            expected={names[k]:v for k,v in demo['providers'].items()}
            if set(expected)!=set(required_slots(claim)):
                raise ValueError('Binding demonstration must ground all acquired slots')
            candidates=assignments(claim,fragments,schema)
            if not any({k:v['id'] for k,v in x.items()}==expected for x in candidates):
                raise ValueError('Demonstration is not an actual typed current-source assignment')
            if type(demo.get('positive')) is not bool:raise ValueError('Explicit source-reviewed binding verdict required')
            actual={k:byid[v] for k,v in expected.items()}
            observed=features(claim,actual)
            if not cross_slot:observed={k:v for k,v in observed.items() if '~' not in k}
            item={'features':observed,'positive':demo['positive']}
            rows=grouped.setdefault(family(claim),[])
            # Unlisted assignments are unknown, not invented negative labels.
            if item not in rows:rows.append(item)
    policies={};rejected=[]
    for key,rows in grouped.items():
        try:policies[key]=fit_dnf(rows)
        except ValueError as exc:
            if str(exc) not in ('No consistent structural binding policy in the declared language','Actual positive binding observations required'):raise
            rejected.append({'family':key,'reason':str(exc)})
    return {'policies':policies,'rejected_families':rejected,
        'cross_slot_features':cross_slot,'training_cases':len(cases),
        'no_legal_terms_or_native_answers_created':True}


def resolve(model, fragments, schema, *, nearest=False):
    validate_fragments(fragments,schema)
    roots=[];unresolved=[];uses=[]
    for original in fragments:
        if original['kind']!='claim':continue
        claim,names=alpha_claim(original)
        candidates=assignments(claim,fragments,schema)
        if required_slots(claim):
            if nearest:
                # A strong structural baseline: prefer same unit, then current
                # header, then distance. Keep ties instead of arbitrary IDs.
                costs=[(sum(v['unit']!=claim['unit'] for v in x.values()),
                        sum(v['unit']!=claim['header'] for v in x.values()),
                        sum(abs(v['unit']-claim['unit']) for v in x.values())) for x in candidates]
                candidates=[x for x,c in zip(candidates,costs) if c==min(costs)] if costs else []
            else:
                policy=model['policies'].get(family(claim))
                selected=[]
                for x in candidates:
                    observed=features(claim,x)
                    if not model['cross_slot_features']:observed={k:v for k,v in observed.items() if '~' not in k}
                    if policy and accepts(policy,observed):selected.append(x)
                candidates=selected
        outputs={}
        for assignment in candidates:
            term=substitute(claim['term'],{name:v['term'] for name,v in assignment.items()})
            term_sort(term,schema)
            ids=sorted({s for f in [claim,*assignment.values()] for s in f['support_ids']})
            outputs.setdefault(digest(term),{'term':term,'supports':[],'assignments':[]})
            outputs[digest(term)]['supports'].append(ids)
            outputs[digest(term)]['assignments'].append({name:v['id'] for name,v in assignment.items()})
        if len(outputs)!=1:
            unresolved.append({'claim':claim['id'],'candidate_terms':len(outputs),'reason':'No unique supported binding'})
            continue
        output=next(iter(outputs.values()))
        # Multiple witnesses of the same value are retained as alternatives;
        # they are not silently merged into a larger purported proof.
        roots.append({'term':output['term'],'support_ids':output['supports'][0]})
        uses.append({'claim':claim['id'],'alternative_supports':output['supports'],'assignments':output['assignments'],
                     'slot_alpha_map':names,
                     'learned_binding_policy_used':bool(required_slots(claim)) and not nearest})
    return {'statements':roots,'unresolved':unresolved,'binding_uses':uses}
