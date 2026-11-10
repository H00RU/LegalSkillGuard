"""Compile actual source fragments to a finite latent attachment forest.

Literal adaptation never changes a logical operator. Qualification roles are
explicit hypotheses for learning, not declared semantic repairs of the model.
"""
from copy import deepcopy
import itertools
import json
import re

from .source_attachment_learning import meaning, validate_forest


def literal(value, document):
    if not value or value in document:return value,False
    parts=re.split(r'\s+',value.strip())
    pattern=r'\s+'.join(re.escape(p) for p in parts)
    candidates={m.group() for m in re.finditer(pattern,document,re.I)}
    if len(candidates)!=1:raise ValueError('No unique case/whitespace-only source rendering: '+value)
    return next(iter(candidates)),True


def bind_action(program, rule, scope, reading):
    """Lower only an explicit, uniquely verified operand to the public A.

    The real response used share(third_parties, Confidential Information).
    Both arguments are already explicitly carried by this source claim. No
    missing subject/object/domain or different outer operator is supplied.
    """
    try:
        meaning({'program':program})
        return program,None
    except (ValueError,SyntaxError):pass
    candidates=[]
    for domain in scope['domains']:
        pattern=(r'\b'+re.escape(rule['action'])+r'\(\s*'+re.escape(domain)+r'\s*,\s*'
                 +re.escape(reading['object_quote'])+r'\s*\)')
        for match in re.finditer(pattern,program):
            lowered=program[:match.start()]+'A'+program[match.end():]
            try:meaning({'program':lowered})
            except (ValueError,SyntaxError):continue
            candidates.append((lowered,match.group(),domain))
    if len(candidates)!=1:raise ValueError('Expanded action is not uniquely bound to the explicit source fields')
    lowered,operand,domain=candidates[0]
    return lowered,{'original':program,'lowered':lowered,'bound_operand':operand,
                    'action':rule['action'],'receiver_domain':domain,'object_quote':reading['object_quote'],
                    'outer_semantic_operators_unchanged':True}


def compile_forest(material, raw, *, expand_roles=True):
    rules={r['id']:r for r in material['graph']['rules']};scopes={s['id']:s for s in material['graph']['scopes']}
    if set(raw)!=set(rules):raise ValueError('Do not manufacture missing source claims')
    forest={'rules':[]};adaptations=[];rejected=[]
    for rid,rule in rules.items():
        readings=[];seen=set()
        for rank,original in enumerate(raw[rid]):
            r=deepcopy(original)
            try:
                # Bind before literal rendering so the literal operand in the
                # program can be checked against the exact model's object field.
                r['program'],binding=bind_action(r['program'],rule,scopes[rule['scope_id']],r)
                if binding:adaptations.append({'rule_id':rid,'reading':rank,'field':'program','binding':binding})
                for key in ['head_quote','action_quote','negation_quote','actor_quote','object_quote']:
                    value,changed=literal(r[key],material['document'])
                    if changed:adaptations.append({'rule_id':rid,'reading':rank,'field':key,'original':r[key],'literal':value})
                    r[key]=value
                for key in ['conditions','references']:
                    for i,q in enumerate(r[key]):
                        value,changed=literal(q,material['document'])
                        if changed:adaptations.append({'rule_id':rid,'reading':rank,'field':key+'.'+str(i),'original':q,'literal':value})
                        r[key][i]=value
            except ValueError as e:
                rejected.append({'rule_id':rid,'reading':rank,'error':str(e),'original':original});continue
            qualifiers=list(dict.fromkeys(r['conditions']+r['references']))
            original_roles=['condition' if q in r['conditions'] else 'reference' for q in qualifiers]
            # Preserve the model's role assignment as highest prior, then
            # enumerate generic type-legal attachments of observed fragments.
            role_sets=itertools.product(['condition','reference','context'],repeat=len(qualifiers)) if expand_roles else [tuple(original_roles)]
            for roles in role_sets:
                c={**r,'conditions':[],'references':[],'context_quotes':[]}
                for q,role in zip(qualifiers,roles):c[{'condition':'conditions','reference':'references','context':'context_quotes'}[role]].append(q)
                identity=json.dumps(c,sort_keys=True)
                if identity in seen:continue
                seen.add(identity)
                c['prior_logit']=-float(rank)-.5*sum(a!=b for a,b in zip(roles,original_roles))
                c['proposal_rank']=rank
                readings.append(c)
        if not readings:raise ValueError('No source-grounded interpretation remains for '+rid)
        readings.sort(key=lambda r:-r['prior_logit'])
        forest['rules'].append({'rule_id':rid,'readings':readings})
    validate_forest(forest,material)
    return {'forest':forest,'literal_or_operand_adaptations':adaptations,'rejected_readings':rejected,
            'qualification_role_variants_are_latent_hypotheses_not_semantic_certificates':True,
            'missing_source_claims_or_semantic_operators_supplied':False}
