"""Finite admissible source theories from native TRAIN/partial source checks.

The universe comes from acquired rule heads on actual observations. Relaxed
subsets diagnose the output language separately from restricted composition.
This enumerator adds no rule, fact, annotation or model call. Incomplete search
is explicitly timeout; its partial allowed set cannot supervise the learner.
"""
from copy import deepcopy
import time

from .objects import digest
from .relational_learning import execute_composition
from .relational_rules import canonical,context_identity,language_identity
from .source_composition import render_composition,validate_renderers


def admissible_theories(library,observation,check_native,*,timeout_seconds=30):
    language=library['language'];context=observation['context'];deadline=time.monotonic()+timeout_seconds
    if timeout_seconds<=0:raise ValueError('Positive finite admission time allowance required')
    validate_renderers(language,library['renderers'])
    result=execute_composition(language,[r['id'] for r in language['rules']],context,
        timeout_seconds=max(0.001,deadline-time.monotonic()))
    base={'language_sha256':language_identity(language),'context_sha256':context_identity(context),
        'all_candidates_execution':result,'new_model_requests':0,
        'semantics':'Relative to this acquired finite output language and supplied lawful checks; not full source truth.'}
    if not result['complete']:
        return {**base,'status':'timeout' if result['status']=='timeout' else 'inconsistent_observations',
            'vocabulary':None,'allowed_theories':None,'evaluations':[]}
    vocabulary=[{k:v for k,v in a.items() if k!='context_index'} for a in result['possible_outputs']]
    vocabulary=sorted(vocabulary,key=canonical);allowed=[];evaluations=[]
    required={canonical(a) for a in context['required']};forbidden={canonical(a) for a in context['forbidden']}
    for mask in range(1<<len(vocabulary)):
        if time.monotonic()>=deadline:
            return {**base,'status':'timeout','vocabulary':vocabulary,'allowed_theories':None,
                'partial_allowed_theories_not_complete':allowed,'evaluations':evaluations,
                'finite_theory_count':1<<len(vocabulary)}
        theory=[a for i,a in enumerate(vocabulary) if mask&(1<<i)];keys={canonical(a) for a in theory}
        record={'theory_index':mask,'theory':theory,'partial_source_constraints_satisfied':required<=keys and not forbidden&keys}
        if not record['partial_source_constraints_satisfied']:
            record.update({'admissible':False,'reason':'explicit_partial_source_constraint'})
        else:
            candidate={**result,'certain_outputs':[{**a,'context_index':0} for a in theory],
                'possible_outputs':[{**a,'context_index':0} for a in theory]}
            try:
                rendered=render_composition(language,library['renderers'],observation,candidate,library['spec'])
            except (ValueError,KeyError,TypeError) as error:
                record.update({'admissible':False,'reason':'type_or_provenance_failure',
                    'error':type(error).__name__+': '+str(error)})
            else:
                # Native callback reports execution faults separately; a fault is
                # never interpreted as evidence that a legal assertion is false.
                feedback=check_native(rendered)
                if type(feedback['accepted']) is not bool or not isinstance(feedback['reason'],str):
                    raise ValueError('Native feedback must give an explicit acceptance and reason')
                record['native_feedback']=feedback
                record.update({'admissible':feedback['accepted'],'reason':feedback['reason']})
                if record['admissible']:allowed.append(theory)
        evaluations.append(record)
    return {**base,'status':'complete','vocabulary':vocabulary,'allowed_theories':allowed,
        'evaluations':evaluations,'finite_theory_count':1<<len(vocabulary),
        'accepted_theory_count':len(allowed),'elapsed_seconds':timeout_seconds-(deadline-time.monotonic())}


def attach_theories(observation,admission):
    if admission['status']!='complete':raise ValueError('Incomplete admission is not a training constraint')
    if admission['context_sha256']!=context_identity(observation['context']):
        raise ValueError('Source observations or partial constraints changed after admission')
    updated=deepcopy(observation)
    updated['context']['theory_constraints']={k:deepcopy(admission[k]) for k in
        ('status','language_sha256','context_sha256','vocabulary','allowed_theories')}
    return updated


def native_loss(feedback):
    """Original target mistakes/uncovered targets remain mistakes, not passes."""
    if feedback['reason']=='execution_error' or feedback.get('source_review_passed') is False:return None
    if 'views' in feedback:
        return sum(not r['core_executed'] or not (r.get('score') or {}).get('correct',False) for r in feedback['views'])
    return int(not feedback['accepted'])


def attach_scored_theories(observation,admission):
    """Keep strict diagnosis, optimize native errors without a zero-error gate.

    Only theories that passed hard source/type/execution checks receive loss.
    The original allowed_theories and every original score remain unchanged.
    """
    updated=attach_theories(observation,admission);rows=[]
    for evaluation in admission['evaluations']:
        if not evaluation['partial_source_constraints_satisfied'] or 'native_feedback' not in evaluation:continue
        loss=native_loss(evaluation['native_feedback'])
        if loss is not None:rows.append({'theory':deepcopy(evaluation['theory']),'native_loss':loss})
    updated['context']['theory_constraints'].update({'optimization':'native_loss','scored_theories':rows})
    return updated


def diagnose_inputs(observations,admissions,composition_status):
    from .observation_diagnosis import diagnose_observations
    if not observations or len(observations)!=len(admissions):raise ValueError('One admission per actual observation required')
    languages={a['language_sha256'] for a in admissions};contracts={o['contract_sha256'] for o in observations}
    if len(languages)!=1 or len(contracts)!=1:raise ValueError('Recompute diagnosis under one frozen language/interface')
    records=[]
    for o,a in zip(observations,admissions):
        if a['context_sha256']!=context_identity(o['context']):raise ValueError('Stale admissible theories')
        if a['status']=='inconsistent_observations':
            return {'decision':'inconsistent_observations','context':o['context']['id'],
                'representation_certificates':[]}
        records.append({'context_id':o['context']['id'],'visible_inputs':o['visible_inputs'],
            'allowed_theories':a['allowed_theories'] if a['status']=='complete' else [],
            'solver_status':'complete' if a['status']=='complete' else 'timeout'})
    return diagnose_observations(records,observation_contract_sha256=next(iter(contracts)),
        theory_language_sha256=next(iter(languages)),composition_status=composition_status)
