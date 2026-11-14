"""Finite context-dependent composition learning with a mature ASP solver.

Select learned candidate rules under partial source supervision. Unknown
observations are possible branches, never filled factual values. Countermodels
refine solver constraints, not the benchmark or the executor's raw responses.
The current rule bias is positive relational composition with explicit negative
observations; native legal default semantics remain in each dataset consumer.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import time

from .objects import digest
from .relational_rules import (PREFIX,atom_text,canonical,decode_outputs,
    language_identity,observation_program,output_projection,rule_text,validate_context)


def _solve(program,mode,seconds):
    if seconds<=0:return {'status':'timeout','exhausted':False,'last_model':[]}
    worker=Path(__file__).with_name('relational_solver_worker.py')
    started=time.monotonic()
    try:
        completed=subprocess.run([sys.executable,'-I',str(worker)],
            input=json.dumps({'program':program,'mode':mode,'timeout_seconds':seconds}),
            capture_output=True,text=True,timeout=seconds+2,cwd='/tmp',close_fds=True)
    except subprocess.TimeoutExpired:
        return {'status':'timeout','exhausted':False,'last_model':[],'seconds':time.monotonic()-started}
    if completed.returncode:
        raise ValueError('Finite solver failed: '+completed.stderr[-1200:])
    return json.loads(completed.stdout)


def _world(model,context_index,context):
    import clingo
    choices={}
    for value in model:
        atom=clingo.parse_term(value)
        if atom.name==PREFIX+'alternative' and atom.arguments[0].number==context_index:
            choices[atom.arguments[1].number]=atom.arguments[2].number
    if set(choices)!=set(range(len(context['unknown_groups']))):
        raise ValueError('Solver did not return a complete possible-observation assignment')
    return [choices[g] for g in range(len(context['unknown_groups']))]


def _groups(contexts):
    return {name:i for i,name in enumerate(dict.fromkeys(c['id'] for c in contexts))}


def _soft(context):
    return context.get('theory_constraints',{}).get('optimization')=='native_loss'


def _program(language,contexts,*,selected=None,worlds=None,supervise=False,blocked=(),deployed_losses=(),prior_rule_ids=None):
    selectable=selected is None;lines=[]
    groups=_groups(contexts)
    if selectable:
        lines.extend('{'+PREFIX+'take('+str(i)+')}.' for i,_ in enumerate(language['rules']))
        complexity_priority = '@-1' if prior_rule_ids is not None else ''
        lines.append('#minimize {'+';'.join(str(r['cost'])+complexity_priority+','+str(i)+':'+PREFIX+'take('+str(i)+')'
            for i,r in enumerate(language['rules']))+'}.')
        if prior_rule_ids is not None:
            # A branch absent from partial supervision is not a rejected branch.
            # Native loss and every hard constraint still outrank this prior.
            lines.append('#minimize {'+';'.join('1@0,'+str(i)+':' +
                ('not ' if r['id'] in prior_rule_ids else '')+PREFIX+'take('+str(i)+')'
                for i,r in enumerate(language['rules']))+'}.')
        for rejected in blocked:
            body=[('' if r['id'] in rejected else 'not ')+PREFIX+'take('+str(i)+')'
                  for i,r in enumerate(language['rules'])]
            lines.append(':- '+','.join(body)+'.' if body else ':-.')
        if supervise:
            seen=set()
            for context in contexts:
                if not _soft(context) or context['id'] in seen:continue
                seen.add(context['id']);g=groups[context['id']]
                maximum=max((r['native_loss'] for r in context['theory_constraints']['scored_theories']),default=0)
                lines.append('1 {'+PREFIX+'loss_bound('+str(g)+',0..'+str(maximum)+')} 1.')
            lines.append('#minimize {N@1,G:'+PREFIX+'loss_bound(G,N)}.')
            for hypothesis,name,loss in deployed_losses:
                body=[('' if r['id'] in hypothesis else 'not ')+PREFIX+'take('+str(i)+')'
                      for i,r in enumerate(language['rules'])]
                body.extend([PREFIX+'loss_bound('+str(groups[name])+',N)','N<'+str(loss)])
                lines.append(':- '+','.join(body)+'.')
    for i,rule in enumerate(language['rules']):
        if selectable or rule['id'] in selected:
            lines.append(rule_text(rule,i,selectable=selectable))
    for i,context in enumerate(contexts):
        lines.append(observation_program(context,i,world=None if worlds is None else worlds[i]))
        if supervise:
            lines.append(_supervision(context,i))
            if _soft(context):
                lines.append(':- '+PREFIX+'native_loss('+str(i)+',N),'+PREFIX+
                    'loss_bound('+str(groups[context['id']])+',B),N>B.')
    lines.append(output_projection(language))
    lines.append('#show '+PREFIX+'loss_bound/2.')
    return '\n'.join(lines)


def _supervision(context,index,*,violation=False,loss_limit=None):
    """Negation here constrains predicted theories, never absent source facts."""
    bad=PREFIX+'violated';lines=[]
    prefix=(bad+' :- ') if violation else ':- '
    lines.extend(prefix+'not '+atom_text(a,index)+'.' for a in context['required'])
    lines.extend(prefix+atom_text(a,index)+'.' for a in context['forbidden'])
    if 'theory_constraints' in context:
        theories=context['theory_constraints'];allowed=PREFIX+'allowed('+str(index)+')'
        rows=theories['scored_theories'] if _soft(context) else [{'theory':t} for t in theories['allowed_theories']]
        for number,row in enumerate(rows):
            theory=row['theory']
            included={canonical(a) for a in theory}
            body=[('' if canonical(a) in included else 'not ')+atom_text(a,index) for a in theories['vocabulary']]
            match=PREFIX+'theory('+str(index)+','+str(number)+')'
            lines.append(match+(' :- '+','.join(body) if body else '')+'.')
            lines.append(allowed+' :- '+match+'.')
            if _soft(context):
                lines.append(PREFIX+'native_loss('+str(index)+','+str(row['native_loss'])+') :- '+match+'.')
        lines.append(prefix+'not '+allowed+'.')
        if violation and _soft(context):
            lines.append(prefix+PREFIX+'native_loss('+str(index)+',N),N>'+str(loss_limit)+'.')
    if violation:lines.append(':- not '+bad+'.')
    return '\n'.join(lines)


def fit_composition(language,contexts,*,timeout_seconds=30,prior_rule_ids=None):
    identity=language_identity(language)
    for context in contexts:validate_context(context,language)
    if not contexts:raise ValueError('Actual training contexts required')
    if len({c['id'] for c in contexts})!=len(contexts):raise ValueError('Distinct current-source contexts required')
    if timeout_seconds<=0:raise ValueError('Positive finite solver time allowance required')
    if prior_rule_ids is not None:
        if (not isinstance(prior_rule_ids,list) or any(not isinstance(r,str) for r in prior_rule_ids)
                or len(set(prior_rule_ids)) != len(prior_rule_ids)
                or not set(prior_rule_ids) <= {r['id'] for r in language['rules']}):
            raise ValueError('Revision prior must name distinct actually acquired candidate rules')
    deadline=time.monotonic()+timeout_seconds;world_contexts=[];worlds=[];countermodels=[];solves=[];blocked=[];deployed_losses=[]
    # Start from one consistent completion per context. It is an assumption
    # inside the solver only; it never replaces an unknown observation.
    for context in contexts:
        text=observation_program(context,0)+'\n'+output_projection(language)
        result=_solve(text,'one',deadline-time.monotonic());solves.append({'phase':'observation_consistency',**result})
        if result['status']!='sat':
            return {'status':'timeout' if result['status']=='timeout' else 'inconsistent_observations',
                'context':context['id'],'language_sha256':identity,'selected_rule_ids':None,'solver_runs':solves}
        world_contexts.append(context);worlds.append(_world(result['last_model'],0,context))
    known={(c['id'],tuple(w)) for c,w in zip(world_contexts,worlds)}
    while True:
        text=_program(language,world_contexts,worlds=worlds,supervise=True,blocked=blocked,
            deployed_losses=deployed_losses,prior_rule_ids=prior_rule_ids)
        result=_solve(text,'optimize',deadline-time.monotonic());solves.append({'phase':'hypothesis_selection',**result})
        if result['status']!='sat' or not result['exhausted']:
            return {'status':'complete_unsat' if result['status']=='unsat' and result['exhausted'] else 'timeout',
                'language_sha256':identity,'selected_rule_ids':None,'countermodels':countermodels,'solver_runs':solves}
        import clingo
        selected=[];native_limits={};names={v:k for k,v in _groups(world_contexts).items()}
        for value in result['last_model']:
            atom=clingo.parse_term(value)
            if atom.name==PREFIX+'take':selected.append(language['rules'][atom.arguments[0].number]['id'])
            elif atom.name==PREFIX+'loss_bound':native_limits[names[atom.arguments[0].number]]=atom.arguments[1].number
        selected=sorted(selected);bad=False
        for context in contexts:
            text=_program(language,[context],selected=selected)+'\n'+_supervision(context,0,
                violation=True,loss_limit=native_limits.get(context['id']))
            check=_solve(text,'one',deadline-time.monotonic());solves.append({'phase':'possible_countermodel','context':context['id'],**check})
            if check['status']=='timeout':
                return {'status':'timeout','language_sha256':identity,'selected_rule_ids':None,
                    'partial_candidate_rule_ids':selected,'countermodels':countermodels,'solver_runs':solves}
            if check['status']=='sat':
                world=_world(check['last_model'],0,context);key=(context['id'],tuple(world))
                if key in known:raise ValueError('A constrained completion was violated again')
                known.add(key);world_contexts.append(context);worlds.append(world)
                countermodels.append({'context':context['id'],'possible_branch_indices':world,
                    'excluded_hypothesis':selected,'not_a_new_case_or_corrected_observation':True})
                bad=True
        if not bad:
            # Deployment renders the cautious intersection, not a guessed world.
            # Several individually acceptable worlds can have an unacceptable
            # empty intersection. Reject that *program*, not any valid world.
            for context in contexts:
                if 'theory_constraints' not in context:continue
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    return {'status':'timeout','language_sha256':identity,'selected_rule_ids':None,
                        'countermodels':countermodels,'solver_runs':solves}
                deployed=execute_composition(language,selected,context,timeout_seconds=remaining)
                solves.append({'phase':'deployed_cautious_theory','context':context['id'],**deployed['solver']})
                if not deployed['complete']:
                    return {'status':'timeout' if deployed['status']=='timeout' else 'inconsistent_observations',
                        'language_sha256':identity,'selected_rule_ids':None,'countermodels':countermodels,'solver_runs':solves}
                actual={canonical({k:v for k,v in a.items() if k!='context_index'}) for a in deployed['certain_outputs']}
                if _soft(context):
                    profiles=context['theory_constraints']['scored_theories']
                    losses=[r['native_loss'] for r in profiles if {canonical(a) for a in r['theory']}==actual]
                    if losses and losses[0]>native_limits[context['id']]:
                        deployed_losses.append((set(selected),context['id'],losses[0]))
                        countermodels.append({'context':context['id'],'hypothesis':selected,
                            'reason':'deployed_cautious_native_loss_exceeds_bound','native_loss':losses[0],
                            'not_a_new_case_or_corrected_observation':True});bad=True;break
                    allowed=[{canonical(a) for a in r['theory']} for r in profiles]
                else:
                    allowed=[{canonical(a) for a in t} for t in context['theory_constraints']['allowed_theories']]
                if actual not in allowed:
                    blocked.append(set(selected));countermodels.append({'context':context['id'],
                        'excluded_hypothesis':selected,'reason':'deployed_cautious_theory_not_admissible',
                        'not_a_new_case_or_corrected_observation':True});bad=True;break
        if not bad:
            return {'status':'sat','language_sha256':identity,'selected_rule_ids':selected,
                'cost':result['cost'],'countermodels':countermodels,'solver_runs':solves,
                'native_loss_by_context':native_limits,'native_loss':sum(native_limits.values()),
                'all_supplied_native_constraints_satisfied':not any(native_limits.values()),
                'all_supplied_partial_constraints_hold_for_every_declared_possible_observation':True,
                'revision_prior_rule_ids':deepcopy(prior_rule_ids),
                'selection_edits':len(set(selected)^set(prior_rule_ids)) if prior_rule_ids is not None else None,
                'objective_order':['native_loss','selection_edits','complexity'] if prior_rule_ids is not None
                    else ['native_loss','complexity'],
                'source_semantics_or_generalization_certified':False,'new_model_requests':0}


def execute_composition(language,selected_rule_ids,context,*,timeout_seconds=30):
    identity=language_identity(language);validate_context(context,language)
    if not set(selected_rule_ids)<={r['id'] for r in language['rules']}:
        raise ValueError('Unacquired composition rule')
    text=_program(language,[context],selected=set(selected_rule_ids))
    result=_solve(text,'all',timeout_seconds)
    complete=result['status']=='sat' and result['exhausted']
    return {'status':result['status'],'complete':complete,'language_sha256':identity,
        'selected_rule_ids':sorted(selected_rule_ids),'program_sha256':digest(text),
        'certain_outputs':decode_outputs(result.get('certain',[]),language) if complete else [],
        'possible_outputs':decode_outputs(result.get('possible',[]),language),
        'unknown_observations_preserved':deepcopy(context['unknown_groups']),
        'solver':result,'new_model_requests':0}
