"""Admit verified model programs and retrieve bounded common compiler examples.

This is common compilation infrastructure, not a learned B connector skill.
No native target, oracle representation or DEV program is used for admission.
"""
from collections import Counter
import json
import sqlite3
from .atom_frontend import decode_atom_response, atom_slots
from .compiler_templates import make_template


def promote_verified_horn(source,record,*,train_sources,ledger_path):
    if source['key'] not in train_sources:raise ValueError('Only original TRAIN programs may enter the compiler library')
    pred=record['prediction'];result=pred['result']
    if result['program_status']!='model_Horn_IR_compiled' or result['fallback_used']:return None
    for call in reversed(pred['calls']):
        if call['analysis']['program_status']!='model_Horn_IR_compiled':continue
        parsed,code=decode_atom_response(source,json.loads(call['raw_content']))
        if code!=pred['model_horn_code'] or parsed.export()['missing_units']:continue
        with sqlite3.connect('file:'+str(ledger_path)+'?mode=ro',uri=True) as db:
            rows=db.execute("select id,request_hash,result from calls where source=? and role='executor' and status='completed' and request_hash=?",(source['key'],call['request_hash'])).fetchall()
        rows=[r for r in rows if json.loads(r[2]).get('content')==call['raw_content']]
        if len(rows)!=1:raise ValueError('Verified template lacks one exact settled physical origin')
        cid,request_hash,_=rows[0]
        return make_template(source,code,{'role':'executor','call_id':cid,'request_hash':request_hash,
            'independent_source_check':'complete_restricted_Horn_equivalence'})
    raise ValueError('No actual model response supplied the complete accepted program')


def select_compiler_templates(source,templates,limit):
    """One fixed source-only structural nearest-example rule; no score tuning."""
    if type(limit) is not int or limit<1:raise ValueError('A positive example budget is required')
    if any(t['source']['key']==source['key'] for t in templates):
        raise ValueError('A compiler template cannot provide the current program')
    def features(s):
        slots,_=atom_slots(s)
        c=Counter((x['position'],x['literal_polarity_hint']) for x in slots.values())
        c['generic_rules']=sum('people are' in r or 'things are' in r for r in s['public']['rules'])
        return c
    target=features(source)
    eligible=[t for t in templates if t['source']['dataset']==source['dataset'] and t['source']['key']!=source['key']]
    def rank(t):
        other=features(t['source'])
        return (sum(abs(target[k]-other[k]) for k in target.keys()|other.keys()),
                len(atom_slots(t['source'])[0]),t['template_hash'])
    return sorted(eligible,key=rank)[:limit]
