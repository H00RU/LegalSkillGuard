"""Source-acquired overapproximations of legal claimant support.

The lattice bounds positive witnesses, never grants an entitlement. TOP means
an open support range. Source summaries and extensional anchor completeness are
explicit semantic assumptions, not inferred from names or quote membership.
"""
import ast
from copy import deepcopy
from .semantic_frames import obj
from .legal_predicate_skills import evaluate_guard

NODES=('deduction151','exemptions151','dependent152','children152','relatives152')
INPUTS=('known_deduction151','known_exemptions151','known_dependent152','known_children152','known_relatives152','relationship_c2','relationship_d2','spouses','family','household','all_actors')
SEEDS=dict(zip(NODES,INPUTS[:5]))
BLOCKS=('151a','151b','151c','151d','152a','152b','152c','152d')
S={'type':'string'}
QUOTES={'type':'array','items':{'type':'string','minLength':1,'maxLength':600},'minItems':1,'maxItems':3}
ROW=obj({'effect':{'enum':['supports','forwards','removes_only','amount_only','unknown']},
         'output':{'enum':[*NODES,'none','unknown']},'support_expression':S,'quotes':QUOTES,'reason':S})
PROFILE_SCHEMA=obj({'sections':obj({k:ROW for k in BLOCKS})})
PAL_SCHEMA=obj({'expression':S,'quotes':QUOTES,'unresolved':{'type':'array','items':S,'maxItems':8}})


def union(*values):
    if any(v is None for v in values):return None
    return frozenset().union(*values)


def intersection(*values):
    finite=[v for v in values if v is not None]
    if not finite:return None
    out=finite[0]
    for v in finite[1:]:out=out&v
    return out


def support_expression(code,env):
    """Pure set expressions; no generated Python execution or fact constants."""
    tree=ast.parse(code,mode='eval')
    def visit(n):
        if isinstance(n,ast.Name):
            if n.id not in env:raise ValueError('Undeclared support name '+n.id)
            return env[n.id]
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and not n.keywords:
            name=n.func.id
            if name in ('empty','top') and not n.args:return frozenset() if name=='empty' else None
            if name=='singleton' and len(n.args)==1:
                v=visit(n.args[0])
                if not isinstance(v,str):raise ValueError('singleton requires the actual focus role')
                return frozenset([v])
            if name in ('union','intersect') and n.args:
                values=[visit(a) for a in n.args]
                if any(v is not None and not isinstance(v,frozenset) for v in values):raise ValueError('Set operands required')
                return union(*values) if name=='union' else intersection(*values)
        if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.BitOr,ast.BitAnd)):
            a,b=visit(n.left),visit(n.right)
            if any(v is not None and not isinstance(v,frozenset) for v in (a,b)):raise ValueError('Set operands required')
            return union(a,b) if isinstance(n.op,ast.BitOr) else intersection(a,b)
        raise ValueError('Unsupported support expression '+ast.dump(n,include_attributes=False))
    value=visit(tree.body)
    if value is not None and not isinstance(value,frozenset):raise ValueError('A support expression must return a set or TOP')
    return value


def reads(code):return {n.id for n in ast.walk(ast.parse(code,mode='eval')) if isinstance(n,ast.Name)}-{'union','intersect','singleton','empty','top'}


def validate_profile(profile,blocks):
    if set(profile)!= {'sections'} or set(profile['sections'])!=set(BLOCKS) or set(blocks)!=set(BLOCKS):raise ValueError('All source blocks must be represented')
    graph={n:set() for n in NODES};example={n:frozenset() for n in (*NODES,*INPUTS)}|{'focus':'A'}
    for key,row in profile['sections'].items():
        if row['effect'] not in ROW['properties']['effect']['enum'] or row['output'] not in ROW['properties']['output']['enum']:raise ValueError('Unknown support effect/output')
        if not row['quotes'] or any(not q or q not in blocks[key] for q in row['quotes']):raise ValueError('Source quote missing at '+key)
        support_expression(row['support_expression'],example)
        if row['effect'] in ('supports','forwards'):
            if row['output'] not in NODES:raise ValueError('Positive support needs a declared relation')
            graph[row['output']]|=reads(row['support_expression'])&set(NODES)
        elif row['effect'] in ('removes_only','amount_only') and row['output']!='none':raise ValueError('Noncreating effect cannot declare positive output')
    def dfs(n,path):
        if n in path:raise ValueError('Unresolved cyclic support must not become an empty proof')
        for child in graph[n]:dfs(child,path|{n})
    for n in NODES:dfs(n,set())
    return {'syntax_source_membership_and_acyclicity':True,'NL_summary_soundness_proved':False}


def normalize_inputs(frame):
    if set(frame)!=set(INPUTS):raise ValueError('Every factual support family needs a value or explicit TOP')
    out={}
    for k,v in frame.items():
        if v is None:out[k]=None
        elif isinstance(v,(list,tuple,set,frozenset)) and all(isinstance(x,str) and x for x in v):out[k]=frozenset(v)
        else:raise ValueError('Support family is a finite set of role values or TOP')
    return out


def evaluate_profile(profile,frame,focus,*,erase_effect_distinctions=False):
    inputs=normalize_inputs(frame);state={node:inputs[seed] for node,seed in SEEDS.items()};unknown=False
    for row in profile['sections'].values():
        if row['effect']=='unknown' or row['output']=='unknown':unknown=True
        if erase_effect_distinctions and row['effect'] in ('removes_only','amount_only'):unknown=True
    if unknown:return {'range':None,'status':'open_source_effect','nodes':{},'source_semantics_assumed':True}
    for _ in range(len(NODES)+1):
        after=dict(state);env=inputs|state|{'focus':focus}
        for row in profile['sections'].values():
            if row['effect'] in ('supports','forwards'):
                node=row['output'];after[node]=union(after[node],support_expression(row['support_expression'],env))
        if after==state:break
        state=after
    else:raise ValueError('Support graph did not reach its finite acyclic bound')
    result=state['deduction151']
    return {'range':None if result is None else sorted(result),'status':'open_anchor_support' if result is None else 'finite_positive_support',
            'nodes':{k:None if v is None else sorted(v) for k,v in state.items()},'source_semantics_assumed':True,
            'range_is_not_the_set_of_all_people':True}


def evaluate_pal(value,frame,focus):
    if value['unresolved']:return {'range':None,'status':'unresolved_source'}
    env=normalize_inputs(frame)|{'focus':focus}
    result=support_expression(value['expression'],env)
    return {'range':None if result is None else sorted(result),'status':'open' if result is None else 'finite_positive_support'}


def apply_support_bound(program,case,rule_id,support,*,source_review_accepted,anchor_review_accepted):
    """Compose a positive-support guarantee with the actual negative guard.

    A finite result is useful only under admitted source and anchor semantics.
    This proves that positive witnesses are inside the supplied bound, not that
    all taxpayers are inside it. It never turns a failed source read into false.
    """
    original=evaluate_guard(program,case,rule_id)
    if original['condition_value'] is True:return {'condition_value':True,'basis':'actual_positive_witness','original':original}
    if not source_review_accepted or not anchor_review_accepted or support['range'] is None:
        return {'condition_value':None,'basis':'support_or_source_open','original':original}
    if case['query']['arguments'].count(None)!=1 or case['query']['arguments'][0] is not None:raise ValueError('This acquired interface projects its claimant role at index0')
    bounded=evaluate_guard(program,case,rule_id,domains={0:support['range']})
    return {'condition_value':bounded['condition_value'],'basis':'positive_support_bound_plus_guard_calls','original':original,'bounded_calls':bounded,
            'positive_support':deepcopy(support),'source_and_anchor_review_are_assumptions':True,
            'no_population_domain_closure_assumed':True}


def compare_support_functions(profile,pal):
    """Exact extensional comparison for every abstract input set/focus member.

    This checks range-function equivalence, not whether either function is
    faithful to the natural-language law. No observed case label is used.
    """
    import z3
    symbols={n:z3.Bool('contains_'+n) for n in INPUTS};is_focus=z3.Bool('member_is_focus')
    def expression(code,env):
        def visit(n):
            if isinstance(n,ast.Name) and n.id in env:return env[n.id]
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and not n.keywords:
                k=n.func.id
                if k in ('empty','top') and not n.args:return z3.BoolVal(k=='top')
                if k=='singleton' and len(n.args)==1 and isinstance(n.args[0],ast.Name) and n.args[0].id=='focus':return is_focus
                if k in ('union','intersect') and n.args:return (z3.Or if k=='union' else z3.And)(*[visit(x) for x in n.args])
            if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.BitOr,ast.BitAnd)):
                return (z3.Or if isinstance(n.op,ast.BitOr) else z3.And)(visit(n.left),visit(n.right))
            raise ValueError('Unsupported symbolic support expression')
        return visit(ast.parse(code,mode='eval').body)
    state={n:symbols[k] for n,k in SEEDS.items()}
    unknown=any(r['effect']=='unknown' or r['output']=='unknown' for r in profile['sections'].values())
    if unknown:left=z3.BoolVal(True)
    else:
        for _ in range(len(NODES)+1):
            env=symbols|state;after=dict(state)
            for r in profile['sections'].values():
                if r['effect'] in ('supports','forwards'):
                    n=r['output'];after[n]=z3.simplify(z3.Or(after[n],expression(r['support_expression'],env)))
            state=after
        left=state['deduction151']
    right=z3.BoolVal(True) if pal['unresolved'] else expression(pal['expression'],symbols)
    solver=z3.Solver();solver.set(timeout=5000);solver.add(left!=right);status=solver.check()
    out={'status':str(status),'equivalent_for_all_abstract_input_sets':status==z3.unsat,'source_soundness_established':False}
    if status==z3.sat:
        m=solver.model();out['counterexample_membership']={n:z3.is_true(m.eval(v,model_completion=True)) for n,v in symbols.items()}|{'member_is_focus':z3.is_true(m.eval(is_focus,model_completion=True)),'profile_contains':z3.is_true(m.eval(left,model_completion=True)),'pal_contains':z3.is_true(m.eval(right,model_completion=True))}
    return out
