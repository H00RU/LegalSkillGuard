"""Small source-addressed payment relation IR for the existing TRAIN88 gap.

Span validation and arithmetic are shared infrastructure. Work classification is
supplied by a learned program; membership never certifies a semantic relation.
"""
from decimal import Decimal
import re
from .semantic_frames import obj,TEXT_OR_UNKNOWN,occurrences

EVENT_SCHEMA=obj({name:TEXT_OR_UNKNOWN for name in
    ('payer','payee','amount_span','remuneration_kind','work_activity','payment_medium','service_period')} |
    {'event_evidence':{'type':'string'}})
PAYMENT_SCHEMA=obj({'events':{'type':'array','items':EVENT_SCHEMA}})
MONEY=re.compile(r'\$[0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?')


def decode_payments(value,text):
    if set(value)!={'events'} or not isinstance(value['events'],list):raise ValueError('Wrong payment IR envelope')
    rows=[];seen=set()
    for event in value['events']:
        if set(event)!=set(EVENT_SCHEMA['properties']):raise ValueError('Wrong payment event fields')
        evidence=occurrences(text,event['event_evidence']);pointers={}
        for field in EVENT_SCHEMA['properties']:
            if field=='event_evidence':continue
            pos=occurrences(text,event[field]);pointers[field]=[p for p in pos if any(a<=p[0]<p[1]<=b for a,b in evidence)]
            if pos and not pointers[field]:raise ValueError('Event field occurs outside its claimed evidence: '+field)
        amount=None
        if event['amount_span'] is not None:
            if not MONEY.fullmatch(event['amount_span']):raise ValueError('Amount must be an exact dollar literal')
            amount=Decimal(event['amount_span'][1:].replace(',',''))
        signature=tuple(event[k] for k in EVENT_SCHEMA['properties'])
        if signature in seen:raise ValueError('Duplicate event is not an additional payment')
        seen.add(signature)
        rows.append({'values':event,'source_pointers':pointers,'evidence_positions':evidence,
                     'amount_decimal':str(amount) if amount is not None else None})
    return {'events':rows,'all_event_relations_semantically_verified':False,'completeness_verified':False}


def scope_sum(decoded,*,payer,kind,work_classify,threshold):
    """Conditional source-event sum; no inferred payment year or legal answer."""
    lower=Decimal(0);upper=Decimal(0);unbounded=False;trace=[]
    for i,event in enumerate(decoded['events']):
        v=event['values'];payer_ok=None if v['payer'] is None else v['payer']==payer
        kind_ok=None if v['remuneration_kind'] is None else v['remuneration_kind']==kind
        activity=work_classify(v);activity_ok=None if activity==2 else bool(activity)
        gates=[payer_ok,kind_ok,activity_ok]
        if False in gates:status='excluded'
        elif all(x is True for x in gates):status='included'
        else:status='possible'
        amount=Decimal(event['amount_decimal']) if event['amount_decimal'] is not None else None
        if status!='excluded':
            if amount is None:unbounded=True
            else:
                upper+=amount
                if status=='included':lower+=amount
        trace.append({'event_index':i,'payer':v['payer'],'payee':v['payee'],'amount':event['amount_decimal'],
                      'activity_class':activity,'status':status})
    limit=Decimal(str(threshold))
    compare=True if lower>=limit else False if not unbounded and upper<limit else None
    return {'sum_lower':str(lower),'sum_upper':None if unbounded else str(upper),
            'at_least_threshold':compare,'threshold':str(limit),'trace':trace,
            'scope':'Stated extracted wage events for the selected payer and agricultural activity',
            'payment_year_assumed_from_service_period':False,
            'native_legal_answer':None,'native_remaining_obligations':[
                'Full event relation/completeness source review',
                'Applicable payment period and legal wage meaning under original task conventions'],
            'semantic_certificate':False}
