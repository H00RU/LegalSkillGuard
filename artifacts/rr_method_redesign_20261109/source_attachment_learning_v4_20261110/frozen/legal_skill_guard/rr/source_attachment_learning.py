"""Partial-feedback learning over grounded alternative source attachments.

The meaning of elementary operators is common machinery. Learned parameters
rank attachment/binding alternatives; neither valid JSON nor an operator tree
is a source-faithfulness certificate. Ordinary log-linear parameterizations of
the same graph scores are equivalent, not an extra contribution.
"""
import ast
import itertools
import re
from copy import deepcopy
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp

from .contract_scope_learning import QUERIES, validate

OPERATORS={'P':'permission','O':'obligation','F':'prohibition','BREACH':'breach','POSSIBLE':'possibility','OTHER':'other','NOT':'not'}


def meaning(reading):
    """Preserve negation scope; no-breach/not-forbidden is not permission."""
    def parse(node):
        if isinstance(node,ast.Name) and node.id=='A':return 'action'
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in OPERATORS and len(node.args)==1 and not node.keywords:
            return [OPERATORS[node.func.id],parse(node.args[0])]
        raise ValueError('Only unary public semantic operators and A are allowed')
    tree=ast.parse(reading['program'],mode='eval')
    if sum(1 for _ in ast.walk(tree))>48:raise ValueError('Interpretation expression is too large')
    formula=parse(tree.body)
    effect=next((k for k in ['permission','obligation','prohibition'] if formula==[k,'action']),None)
    if formula==['obligation',['not','action']]:effect='prohibition'
    return {'formula':formula, 'effect':effect}


def validate_forest(forest, material):
    ids = {r['id'] for r in material['graph']['rules']}
    if len(forest['rules']) != len(ids) or {r['rule_id'] for r in forest['rules']} != ids:
        raise ValueError('Forest must cover exactly the existing claims')
    for record in forest['rules']:
        if not record['readings']:
            raise ValueError('An existing claim has no source-grounded reading')
        for reading in record['readings']:
            for key in ['head_quote','action_quote']:
                if not reading[key] or reading[key] not in material['document']:
                    raise ValueError('Head/action needs an exact source quote')
            for key in ['negation_quote','actor_quote','object_quote']:
                if reading[key] and reading[key] not in material['document']:
                    raise ValueError('Binding/polarity quote is outside this source')
            value=meaning(reading)
            if 'not' in str(value['formula']) and not reading['negation_quote']:
                raise ValueError('Do not invent negation without source support')
            for key in ['conditions','references']:
                if any(not x or x not in material['document'] for x in reading[key]):
                    raise ValueError('Qualification is outside its source')
            if reading['exception_target'] is not None and reading['exception_target'] not in ids-{record['rule_id']}:
                raise ValueError('An exception points to an undeclared/self claim')
    return forest


def selected(forest, choice):
    return {r['rule_id']: r['readings'][i] for r,i in zip(forest['rules'],choice)}


def features(material, forest, choice, *, joint=True):
    readings = selected(forest,choice)
    original = {r['id']:r for r in material['graph']['rules']}
    counts = {}
    def add(k,v=1.):
        counts[k] = counts.get(k,0.)+v
    for record,rank in zip(forest['rules'],choice):
        rid = record['rule_id'];r=readings[rid];base=original[rid]
        value=meaning(r);formula=value['formula'];root=formula[0] if isinstance(formula,list) else formula
        add('head:'+root);add('action_head:'+base['action']+':'+root)
        for word in set(re.findall(r'\w+',r['head_quote'].casefold())):
            add('head_lexeme:'+word+':'+root)
        branch=formula
        while isinstance(branch,list):
            child=branch[1][0] if isinstance(branch[1],list) else branch[1]
            add('compose:'+branch[0]+':'+child)
            branch=branch[1]
        add('actor_known',bool(r['actor_quote']));add('object_known',bool(r['object_quote']))
        head_at=material['document'].find(r['head_quote']);action_at=material['document'].find(r['action_quote'])
        add('head_precedes_action',head_at<action_at)
        add('head_action_distance',min(abs(head_at-action_at),1000)/1000.)
        add('qualified',bool(r['conditions']));add('reference',bool(r['references']))
        for role,key in [('condition','conditions'),('reference','references'),('context','context_quotes')]:
            for quote in r[key]:
                words=re.findall(r'\w+',quote.casefold())
                add('qualifier_role:'+role)
                if words:add('qualifier_prefix:'+words[0]+':'+role)
        add('seed_effect_agreement',meaning(r)['effect']==base['effect'])
        target=r['exception_target']
        if target is not None:
            add('exception_edge')
            other=readings[target]
            if joint:
                actor=bool(r['actor_quote']) and r['actor_quote'].casefold()==other['actor_quote'].casefold()
                obj=bool(r['object_quote']) and r['object_quote'].casefold()==other['object_quote'].casefold()
                add('exception_actor_agreement',actor);add('exception_object_agreement',obj)
                add('exception_joint_binding',actor and obj)
                add('exception_action_pair:'+base['action']+':'+original[target]['action'])
                add('exception_effect_pair:'+str(meaning(r)['effect'])+':'+str(meaning(other)['effect']))
    return counts


def project(material, forest, choice):
    readings=selected(forest,choice);graph=deepcopy(material['graph']);kept=[];residuals=[]
    for r in graph['rules']:
        reading=readings[r['id']];value=meaning(reading)
        if value['effect'] is None:
            residuals.append({'original':r,'reading':reading,'meaning':value})
            continue
        r['effect']=value['effect'];r['conditions']=reading['conditions']+reading['references']
        r['source_quotes']=list(dict.fromkeys(r['source_quotes']+[reading['head_quote'],reading['action_quote']]+reading['context_quotes']))
        r['overrides']=[] if reading['exception_target'] is None else [reading['exception_target']]
        kept.append(r)
    kept_ids={r['id'] for r in kept}
    for r in kept:
        r['overrides']=[k for k in r['overrides'] if k in kept_ids]
    graph['rules']=kept
    validate(graph,material['document'])
    return {'graph':graph,'residuals':residuals,'readings':readings}


def native_answers(state):
    """Existing native convention; residuals cannot prove acquired absence."""
    g=state['graph'];scopes={s['id']:s for s in g['scopes']};answers={}
    for q,(effect,action,domain,trigger) in QUERIES.items():
        def matches(r):
            return r['action']==action and domain in scopes[r['scope_id']]['domains'] and (trigger is None or trigger in r['triggers'])
        matching=[r for r in g['rules'] if matches(r)]
        suppressed={k for r in matching for k in r['overrides']}
        active=[r for r in matching if r['id'] not in suppressed]
        positive=any(r['effect']==effect for r in active);negative=any(r['effect']=='prohibition' for r in active)
        residual=any(matches(r['original']) for r in state['residuals'])
        answers[q]=None if positive and negative else ('Entailment' if positive else 'Contradiction' if negative else
            'NotMentioned' if q in g['complete_query_ids'] and not g['unresolved'] and not residual else None)
    return answers


def compatible(material,forest,choice,feedback):
    readings=selected(forest,choice)
    for f in feedback:
        r=readings[f['rule_id']]
        if f['kind']=='source_head':
            if 'meaning_formula' in f and meaning(r)['formula']!=f['meaning_formula']:return False
            if meaning(r)['effect'] in f.get('forbidden_derived_effects',[]):return False
            if any(r[k]!=v for k,v in f['equals'].items()):return False
            if any(v not in r[k] for k,v in f['contains'].items()):return False
            if any(not any(v in x for x in r[k]) for k,v in f['list_contains'].items()):return False
        elif f['kind']=='joint_exception_binding':
            target=readings[f['target_rule_id']]
            if r['exception_target']!=f['target_rule_id']:return False
            if not r['actor_quote'] or r['actor_quote'].casefold()!=target['actor_quote'].casefold():return False
            if not r['object_quote'] or r['object_quote'].casefold()!=target['object_quote'].casefold():return False
            if not any(f['qualification_contains'] in x for x in r['conditions']):return False
    try:
        state=project(material,forest,choice);answers=native_answers(state)
    except ValueError:return False
    return all(answers[e['id']]==e['answer'] for e in material.get('examples',[]))


def problem(material,forest,feedback,*,joint=True):
    validate_forest(forest,material)
    choices=list(itertools.product(*(range(len(r['readings'])) for r in forest['rules'])))
    values=[features(material,forest,c,joint=joint) for c in choices]
    legal=[]
    for c in choices:
        try:project(material,forest,c);legal.append(True)
        except ValueError:legal.append(False)
    return {'key':material['key'],'choices':choices,'feature_dicts':values,
            'prior':np.array([sum(r['readings'][i]['prior_logit'] for r,i in zip(forest['rules'],c)) for c in choices],dtype=float),
            'valid':np.array(legal,dtype=bool),
            'compatible':np.array([ok and compatible(material,forest,c,feedback) for c,ok in zip(choices,legal)],dtype=bool)}


def fit(problems,*,mode='marginal'):
    """Exact partial-supervision likelihood with fixed unit Gaussian shrinkage.

    Native supervision couples choices through actual query execution; explicit
    partial source constraints are applied only in TRAIN. All legal choices
    remain available at inference. No source-ID or document-specific features.
    """
    if mode not in ['marginal','hard_em']:raise ValueError(mode)
    if any(not p['compatible'].any() for p in problems):
        return {'accepted':False,'reason':'No compatible source-grounded interpretation in the actual proposal forest',
                'uncovered':[p['key'] for p in problems if not p['compatible'].any()]}
    names=sorted({k for p in problems for f in p['feature_dicts'] for k in f});idx={k:i for i,k in enumerate(names)}
    prepared=[]
    for p in problems:
        x=np.zeros((len(p['choices']),len(names)))
        for i,f in enumerate(p['feature_dicts']):
            for k,v in f.items():x[i,idx[k]]=v
        prepared.append((p,x))
    history=[]
    def objective(w):
        loss=.5*w@w;grad=w.copy()
        for p,x in prepared:
            score=p['prior']+x@w;valid=p['valid'];good=p['compatible'];z=logsumexp(score[valid])
            pv=np.exp(score[valid]-z);expected=pv@x[valid]
            if mode=='hard_em':
                best=np.flatnonzero(good)[np.argmax(score[good])];loss+=z-score[best];grad+=expected-x[best]
            else:
                zg=logsumexp(score[good]);pg=np.exp(score[good]-zg);loss+=z-zg;grad+=expected-pg@x[good]
        return float(loss),grad
    initial=objective(np.zeros(len(names)))[0]
    result=minimize(objective,np.zeros(len(names)),jac=True,method='L-BFGS-B',options={'maxiter':200},callback=lambda w:history.append(objective(w)[0]))
    return {'accepted':bool(result.success),'mode':mode,'feature_names':names,'weights':result.x.tolist(),
            'initial_objective':initial,'final_objective':float(result.fun),'iterations':int(result.nit),
            'optimization_message':str(result.message),'history':history,'regularization':1.,
            'learner_is_an_ordinary_conditional_log_linear_model':True,'semantic_certificate':False}


def choose(model,p):
    if model is not None and not model['accepted']:return None
    weights={} if model is None else dict(zip(model['feature_names'],model['weights']))
    scores=[float(base)+sum(weights.get(k,0.)*v for k,v in f.items()) for base,f in zip(p['prior'],p['feature_dicts'])]
    legal=[i for i,x in enumerate(p['valid']) if x]
    if not legal:return None
    i=max(legal,key=lambda j:scores[j])
    return {'choice':list(p['choices'][i]),'score':scores[i],'training_compatible':bool(p['compatible'][i])}
