"""Current source IR assessment and real follow-up requests for the A policies.

No actor, labels or references are imported. The caller supplies the actual
serving tokenizer and dispatches the exact returned messages/schema. A legal
residual requests rule translation, never an oracle-like factual truth value.
"""
from dataclasses import asdict
from fractions import Fraction
import json
import time

from .coverage import Unsupported,certificate,complete,digest,plan_batch
from .source_program import (accept_observations,compile_source,compiler_prompt,
    observation_request,source_theory)
from .source_code import compiler_response_schema,decode_compiler_response
from .strict_contract import obj
from .wire_validation import validate_wire


def exact_native(value):
    """Emit only native JSON numbers whose decimal round trip is exact."""
    if isinstance(value,Fraction):
        if value.denominator==1:return value.numerator
        number=float(value)
        if Fraction(str(number))!=value:
            raise Unsupported('Native numeric output would require rounding')
        return number
    if isinstance(value,list):return [exact_native(v) for v in value]
    if isinstance(value,dict):return {k:exact_native(v) for k,v in value.items()}
    return value


def assess_source(compiled,observed=None,*,compilation='answer_separating',seconds=5):
    if compilation not in {'full','answer_separating','generic_CEGAR_fixed_batch'}:
        raise ValueError('Unknown source compilation policy')
    theory=source_theory(compiled,observed)
    result=complete(theory,deadline=time.monotonic()+max(0,min(seconds,5)))
    record={'status':result.status,'reason':result.reason,'theory_hash':result.theory_hash,
        'answer':None,'projection':result.projection,'unresolved':sorted(theory.domains),
        'unknown_scope':[r.source for r in theory.residuals if r.unknown_scope],
        'full_compilation_required':compilation=='full' and bool(theory.residuals),
        'certificate':None,'execution':None}
    if result.status=='completion_stable' and not record['full_compilation_required']:
        answer=exact_native(result.answer)
        # A source-completion proof does not exempt its output from the task's
        # native format. No target/reference value enters this validation.
        dataset=compiled['source']['dataset']
        if dataset=='RuleArena_Airline':
            if type(answer) is not int or answer<0:raise Unsupported('Airline needs a nonnegative integer total')
        elif dataset=='OpenExempt':
            from legal_skill_guard.openexempt import answer_schema
            if not isinstance(answer,dict) or set(answer)!={'EC','EV'}:
                raise Unsupported('OpenExempt needs the complete EC/EV mapping')
            for family in ('EC','EV'):validate_wire(answer[family],answer_schema(family))
        else:
            from .scoring import LABELS
            if not isinstance(answer,str) or answer not in LABELS[dataset]:
                raise Unsupported('Native label outside the benchmark vocabulary')
        record.update(answer=answer,certificate=certificate(theory,result),
            execution=exact_native(compiled['query'].execute(theory.facts)))
    elif record['full_compilation_required']:
        record.update(status='translation_unresolved',reason='full policy requires remaining source residuals to be parsed')
    return record


def prepare_followup(compiled,observed=None,*,compilation,tokenize,request_config,thinking,library=None,seconds=5):
    if compilation not in {'full','answer_separating','generic_CEGAR_fixed_batch'}:
        raise ValueError('Unknown source compilation policy')
    observed=observed or {};theory=source_theory(compiled,observed)
    deadline=time.monotonic()+max(0,min(seconds,5))
    initial=complete(theory,deadline=deadline)
    active=set(initial.projection.get('active_slots',theory.domains))
    pending={r.source for r in theory.residuals}
    residual_order=[c.id for c in theory.ledger.clauses if c.id in pending]
    unknown_scope={r.source for r in theory.residuals if r.unknown_scope}
    cache={}
    def render(selected):
        closure=theory.ledger.closure(set(selected));key=tuple(sorted(closure))
        if key in cache:return cache[key]
        selected=closure&pending
        relevant=active if compilation=='answer_separating' else set(theory.domains)
        names=sorted(name for unit in selected for name in compiled['by_fact'].get(unit,[])
                     if name in theory.domains and name in relevant)
        factual_messages,factual_schema=observation_request(compiled,names)
        translation=[unit for unit in selected if compiled['structure'].roles[unit]['role']=='rule' or unit in unknown_scope]
        if translation:
            factual_schema['properties']['observations']['items']['properties']['name']['type']='string'
            task=json.loads(factual_messages[1]['content'])
            system,user=compiler_prompt(compiled['source'],library,accepted_program=compiled['program'],
                factual_observation_task=task)
            payload=json.loads(user)
            # Previously accepted K is the supplied program. New source text
            # consists only of the selected residual/context closure, not an
            # unreported second full-source read.
            payload['units']=[u for u in payload['units'] if u['id'] in closure]
            payload['selected_residual_units']=sorted(selected)
            payload['context_closure']=list(key)
            system+=(' Return an envelope with program holding {code:STRING} for the complete declarative program and '
                'factual_observations holding exactly the requested fact rows. Preserve unchanged '
                'primitive names/quotes and accepted definitions. Translate the selected rule residuals; '
                'do not guess truth values for legal subexpressions. Unknown facts remain null.')
            schema=obj({'program':compiler_response_schema(),
                'factual_observations':factual_schema['properties']['observations']})
            if not names:schema['properties']['factual_observations']={'type':'array','maxItems':0,'items':{'type':'null'}}
            messages=[{'role':'system','content':system},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}]
            kind='joint_rule_translation_and_facts'
        else:
            messages,schema=factual_messages,factual_schema;kind='factual_observation'
        measured=tokenize(messages,thinking=thinking)
        if type(measured['count']) is not int or measured['count']<0:raise ValueError('Invalid serving token count')
        value={'kind':kind,'messages':messages,'schema':schema,'names':names,
            'selected':sorted(selected),'context_closure':list(key),'input_tokens':measured['count'],
            'messages_hash':digest(messages),'schema_hash':digest(schema)}
        cache[key]=value
        return value
    budget=request_config['context_tokens']-request_config['max_tokens']
    plan=None
    if compilation=='full':selected=residual_order;basis='full_source_translation'
    elif compilation=='generic_CEGAR_fixed_batch':selected=residual_order[:1];basis='generic_fixed_one_unit'
    else:
        plan=plan_batch(theory,lambda selected:render(selected)['input_tokens'],budget,
            seconds=max(0,deadline-time.monotonic()))
        selected=list(plan.selected) if plan.status=='separation_complete' else residual_order
        basis=plan.status if plan.status=='separation_complete' else 'conservative_full_source_after_'+plan.status
    if not selected:
        return {'kind':'no_followup','selection_basis':basis,'batch_plan':asdict(plan) if plan else None}
    result=render(selected)
    # Verify a planned closure and the exact dispatch use identical payloads.
    actual=tokenize(result['messages'],thinking=thinking)['count']
    if actual!=result['input_tokens'] or plan and plan.status=='separation_complete' and actual!=plan.cost:
        raise ValueError('Planned and actual follow-up token counts differ')
    if actual>budget:raise Unsupported('Follow-up exceeds context; no truncation')
    return {**result,'selection_basis':basis,'batch_plan':asdict(plan) if plan else None,
        'joint_separation_complete':basis=='separation_complete',
        'source_ledger_hash':theory.ledger.version,'remaining_unknown_legal_domains_are_not_fact_queries':True}


def accept_followup(compiled,prepared,response,observed=None,*,library=None):
    validate_wire(response,prepared['schema']);observed=observed or {}
    if prepared['kind']=='joint_rule_translation_and_facts':
        updated=compile_source(compiled['source'],decode_compiler_response(response['program']),library=library)
        for name in set(observed)|set(prepared['names']):
            if updated['observations'].get(name)!=compiled['observations'][name]:
                raise Unsupported('Changed primitive meaning cannot inherit an earlier/requested observation')
        rows={'observations':response['factual_observations']}
    elif prepared['kind']=='factual_observation':updated=compiled;rows=response
    else:raise ValueError('No observation/translation response was requested')
    accepted=accept_observations(updated,prepared['names'],rows)
    return updated,{**observed,**accepted}
