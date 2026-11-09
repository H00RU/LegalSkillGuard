"""Finite ordinary source-program/interval baseline on original TRAIN13.

A provided scalar contract, ordinary Python and a shared calendar adapter are
controls, not claimed learned inventions. Unknown age/return values stay unknown.
"""
import argparse
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re

import z3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.python_scalar_module import compile_function
from legal_skill_guard.rr.semantic_contracts import ContractError, compare_modules, expression, variables
from legal_skill_guard.rr.semantic_frames import obj

ROOT = Path(__file__).resolve().parents[1]
RUN = 'legal_temporal13_v3_20261110'
PREVIOUS = ROOT/'artifacts/rr_method_redesign_20261109/legal_temporal13_v1_20261110'
STAGE = ROOT/'artifacts/rr_method_redesign_20261109'/RUN
OLD = ROOT/'artifacts/rr_method_redesign_20261109/redesign_source_roles_v1_20261109/seal.json'
SIGNATURE = {'relationship_152_c_2': 'boolean', 'same_abode_days': 'integer', 'tax_year_days': 'integer',
             'younger_than_taxpayer': 'boolean', 'age_at_year_end': 'integer', 'joint_nonrefund_return': 'boolean'}
DOMAIN = 'same_abode_days >= 0 and tax_year_days > 0 and same_abode_days <= tax_year_days and age_at_year_end >= 0'
# Audit reference from the four supplied textual conjuncts. Never sent to models.
REFERENCE = 'relationship_152_c_2 and 2 * same_abode_days > tax_year_days and younger_than_taxpayer and age_at_year_end < 25 and not joint_nonrefund_return'


def read(p): return json.loads(p.read_text())


def union_days(intervals, year):
    """Inclusive calendar dates, clipped to this calendar year, without overlap."""
    lo = date(year, 1, 1); hi = date(year, 12, 31)
    ranges = []
    for start, end in intervals:
        a, b = date.fromisoformat(start), date.fromisoformat(end)
        if a > b: raise ContractError('A stated interval ends before it starts')
        a, b = max(a, lo), min(b, hi)
        if a <= b: ranges.append((a, b))
    total = 0; merged = []
    for a, b in sorted(ranges):
        if merged and a <= merged[-1][1]+timedelta(days=1): merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else: merged.append((a,b))
    return sum((b-a).days+1 for a,b in merged)


def assess(expr, bindings):
    syms = variables(SIGNATURE); body = expression(expr, syms)
    assert z3.is_bool(body)
    known = [syms[k] == v for k,v in bindings.items() if v is not None]
    values = []
    for value in [False,True]:
        s = z3.Solver(); s.add(expression(DOMAIN,syms), *known, body == value)
        if s.check() == z3.sat: values.append(value)
    if not values: raise ContractError('Inconsistent scalar binding/domain')
    return {'possible_values': values, 'answer': 'Entailment' if values == [True] else 'Contradiction' if values == [False] else None,
            'unknown_inputs': [k for k,v in bindings.items() if v is None], 'missing_inputs_not_defaulted': True}


def offline():
    assert union_days([('2015-09-01','2019-02-03')],2019) == 34
    assert union_days([('2020-01-01','2020-12-31')],2020) == 366
    assert union_days([('2019-01-01','2019-01-20'),('2019-01-10','2019-01-31')],2019) == 31
    base = {'relationship_152_c_2': True,'same_abode_days':34,'tax_year_days':365,
            'younger_than_taxpayer':None,'age_at_year_end':None,'joint_nonrefund_return':None}
    assert assess(REFERENCE,base)['possible_values'] == [False]
    unknown = base|{'same_abode_days': None}
    assert assess(REFERENCE,unknown)['possible_values'] == [False,True]
    boundary = base|{'same_abode_days':183,'tax_year_days':366,'younger_than_taxpayer':True,'age_at_year_end':24,'joint_nonrefund_return':False}
    assert assess(REFERENCE,boundary)['possible_values'] == [False]
    assert assess(REFERENCE,boundary|{'same_abode_days':184})['possible_values'] == [True]
    assert assess(REFERENCE,boundary|{'same_abode_days':184,'age_at_year_end':25})['possible_values'] == [False]
    return {'passed':8,'calendar_days_inclusive':True,'overlapping_intervals_not_double_counted':True,
            'strict_more_than_half_and_less_than_25':True,'software_probes_not_extra_native_cases':True,'model_calls':0}


def frame_errors(frame, facts):
    errors = []
    for i, r in enumerate(frame['relationships_152_c_2']):
        quote = r['quote']
        m = re.fullmatch(r'(\w+) bears a relationship to (\w+) pursuant to section 152\(c\)\(2\) for the years (\d{4}) to (\d{4})\.', quote)
        if quote not in facts or not m:
            errors.append({'field': f'relationships_152_c_2[{i}]', 'error': 'Unsupported literal relationship quote'})
        elif (r['individual'],r['taxpayer'],r['start_year'],r['end_year']) != (m[1],m[2],int(m[3]),int(m[4])):
            errors.append({'field': f'relationships_152_c_2[{i}]', 'error': 'Role/year binding differs from its own quote'})
    # The actual original case has no dated birth or return assertion. Do not
    # re-interpret a son statement or marriage date as one. The scope is explicit.
    for i,r in enumerate(frame['reported_birth_dates']):
        if r['quote'] not in facts or not re.search(r'\bborn\b|\bbirth\b', r['quote'], re.I):
            errors.append({'field':f'reported_birth_dates[{i}]','error':'No dated birth event is stated in its own quote'})
    if frame['reported_joint_returns']:
        errors.append({'field':'reported_joint_returns','error':'No joint-return event is stated in this original case'})
    return errors


def literal_frame(facts):
    """Narrow ordinary source parser, not a repair of model output or a learner.

    Only the two explicit surface forms present in this original case are
    supported. There is no entity/date/answer table and no model-label access.
    """
    from datetime import datetime
    def iso(text):
        return datetime.strptime(re.sub(r'(\d)(?:st|nd|rd|th)',r'\1',text),'%B %d, %Y').date().isoformat()
    if re.search(r'\bborn\b|\bbirth\b|\bjoint return',facts,re.I):
        raise ContractError('This narrow original-case parser does not support explicit birth/return events')
    rel=list(re.finditer(r'(\w+) bears a relationship to (\w+) pursuant to section 152\(c\)\(2\) for the years (\d{4}) to (\d{4})\.',facts))
    homes=list(re.finditer(r'From (\w+ \d{1,2}(?:st|nd|rd|th)?, \d{4}) to (\w+ \d{1,2}(?:st|nd|rd|th)?, \d{4}), (\w+) and (\w+) lived in the same home\.',facts))
    if len(rel)!=1 or len(homes)!=1:raise ContractError('Unsupported original-case sentence inventory')
    return {'relationships_152_c_2':[{'individual':m[1],'taxpayer':m[2],'start_year':int(m[3]),'end_year':int(m[4]),'quote':m[0]} for m in rel],
        'co_residence_intervals':[{'person1':m[3],'person2':m[4],'start':iso(m[1]),'end':iso(m[2]),'quote':m[0]} for m in homes],
        'reported_birth_dates':[],'reported_joint_returns':[]}


def grounding_regressions():
    seal = read(PREVIOUS/'seal.json'); facts = seal['case']['public']['facts']
    bad = read(PREVIOUS/'facts.json')['value']
    found = frame_errors(bad,facts)
    assert [r['field'] for r in found] == ['relationships_152_c_2[0]','reported_birth_dates[0]']
    role_only = deepcopy(bad)
    role_only['relationships_152_c_2'][0].update(taxpayer='Alice',individual='Bob')
    assert [r['field'] for r in frame_errors(role_only,facts)] == ['reported_birth_dates[0]']
    birth_only = deepcopy(bad); birth_only['reported_birth_dates']=[]
    assert [r['field'] for r in frame_errors(birth_only,facts)] == ['relationships_152_c_2[0]']
    software_fixture = deepcopy(role_only); software_fixture['reported_birth_dates']=[]
    assert frame_errors(software_fixture,facts) == []
    assert literal_frame(facts)==software_fixture
    return {'passed':5,'actual_bad_response_is_regression':True,
            'in_memory_repaired_software_fixture_not_used_as_real_prediction':True,
            'raw_bad_frame_unchanged':True,'native_label_read':False}


def prepare():
    old = read(OLD); packet = {r['key']:r for r in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    case = packet[old['sources']['train'][12]]; text = case['public']['rules']
    a,b = text.index('(c) Qualifying child'),text.index('(d) Qualifying relative')
    policy = text[a:b]; facts = case['public']['facts']
    sentences = re.split(r'(?<=\.)\s+',facts)
    assert len(sentences) == 4
    source_system = ('Write one ordinary pure Python Boolean function implementing section152(c)(1) using the supplied source and scalar input contract. '
        'The caller supplies explicit primitive/previously stated inputs; do not introduce a qualifying_child input or return a fixed test answer. '
        'Each interval count is a count of calendar days, including endpoints; year length is the actual calendar-year day count. '
        'Use all four statutory conditions, including paragraph3. You receive no case facts, queries or labels. '
        'Use integer/Boolean arithmetic, assignments, if/else, return and min/max only; no imports, I/O, loops, decorators or chained comparisons. '
        'Unknown values are handled by the shared symbolic caller, not by defaulting to true/false/zero in your code. '
        'Return only one complete Python function, no JSON or explanation.')
    source_material = {'source_152_c':policy,'function_header':'def qualifying_child('+', '.join(k+': '+('int' if t=='integer' else 'bool') for k,t in SIGNATURE.items())+') -> bool:',
        'provided_input_contract':{
            'relationship_152_c_2':'The paragraph2 relationship holds for this taxpayer/individual/year, explicitly supplied or separately proved; this is not the complete qualifying-child conclusion.',
            'same_abode_days':'Count of same-principal-abode days in this taxable year from the case residence records under the original native-case normalization. Do not substitute a kinship relationship interval.',
            'tax_year_days':'Number of calendar days in the taxable year.',
            'younger_than_taxpayer':'Whether the individual is younger than the taxpayer; unknown remains unknown.',
            'age_at_year_end':'Integer age of the individual at the end of the taxable year; unknown remains unknown.',
            'joint_nonrefund_return':'Whether the individual filed the joint return excluded by paragraph1(E); marriage alone does not establish this.'}}
    # Reader returns raw reported relations/events; the legal program is not sent.
    string={'type':'string'}; integer={'type':'integer'}
    quote={'type':'string','enum':sentences}
    relation=obj({'taxpayer':string,'individual':string,'start_year':integer,'end_year':integer,'quote':quote})
    residence=obj({'person1':string,'person2':string,'start':string,'end':string,'quote':quote})
    schema=obj({'relationships_152_c_2':{'type':'array','items':relation},'co_residence_intervals':{'type':'array','items':residence},
                'reported_birth_dates':{'type':'array','items':obj({'person':string,'date':string,'quote':quote})},
                'reported_joint_returns':{'type':'array','items':obj({'person1':string,'person2':string,'year':integer,'refund_only':{'type':'boolean'},'quote':quote})}})
    reader_system=('Extract every directly reported paragraph152(c)(2) relationship interval, co-residence interval, birth date and joint-return event from this original case. '
        'Preserve each interval\'s own relation and participants. In paragraph152(c)(2), individual is the person who bears the relationship; taxpayer is the person TO WHOM that relationship is borne. Do not assign roles by first-mention order. Use ISO YYYY-MM-DD for full dates and integer bounds for stated year ranges. '
        'A son relation without a date is not a birth date. A marriage is not a joint return. '
        'Do not infer legal qualifications, add unreported events, transfer a relationship interval to residence, or answer a legal question. '
        'Use the complete exact supporting supplied sentence as quote. A reported birth date must be explicitly supported by that same birth-event sentence, never a date borrowed from a residence or marriage sentence. Empty lists mean no such event was reported, not that a legal condition is false. Your previous frame and concrete diagnostics are supplied for source-grounded correction. Return the complete corrected frame, not an explanation. Return only the schema.')
    protocol=ROOT/'reports/method_redesign_20261109/legal_temporal13_protocol.md'
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
        'experiments/rr_v2_legal_temporal13.py','legal_skill_guard/rr/python_scalar_module.py','legal_skill_guard/rr/semantic_contracts.py',
        'legal_skill_guard/rr/method_client.py','legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/client.py')}
    evidence=offline()
    seal={'run_id':RUN,'config':old['config'],'sources':old['sources'],'binding':{'code_hash':digest(files),'config_hash':digest(old['config'])},
        'files':files,'case':case,'source_excerpt':policy,'source_messages':[{'role':'system','content':source_system},{'role':'user','content':json.dumps(source_material,ensure_ascii=False)}],
        'reader_messages':[{'role':'system','content':reader_system},{'role':'user','content':json.dumps({'case_text':facts,'source_sentence_options':sentences,'previous_raw_frame':read(PREVIOUS/'facts.json')['value'],'source_only_diagnostics':read(PREVIOUS/'rejection_diagnostics.json')['errors']},ensure_ascii=False)}],
        'reader_schema':schema,'shared_scalar_signature':SIGNATURE,'domain':DOMAIN,'audit_reference_NOT_sent':REFERENCE,
        'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'offline':evidence,'actual_failure_regressions':grounding_regressions(),
        'manual_provided_scalar_API_not_learned_here':True,'native_residence_record_CWA_normalization_explicit':True,
        'unrestricted_NL_view_also_retained':True,'no_source_rule_or_case_semantic_gap_repaired_from_labels':True,'goal_complete':False}
    immutable_json(STAGE/'seal.json',seal)
    prior_source=read(PREVIOUS/'source.json'); assert prior_source['status']=='source_verified'
    immutable_json(STAGE/'source.json',prior_source|{'source_physical_response_reused_without_dispatch':True,'original_source_sha256':hashlib.sha256((PREVIOUS/'source.json').read_bytes()).hexdigest()})
    immutable_json(STAGE/'literal_grounded_facts.json',{'value':literal_frame(facts),'created_by':'narrow_deterministic_original_text_parser','model_output':False,'raw_model_frames_not_modified':True,'learned_fact_skill':False,'reader_fallback_used':True})
    return seal


def ledger(s):
    return MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,binding=s['binding'],sources=s['sources'],authorization_hash=s['protocol_sha256'],
        question='Complete a finite ordinary source152(c)(1) control from raw TRAIN13 intervals without opaque target input; distinguish native closed-world record normalization from unrestricted NL entailment. No new method contribution claim or full build.')


def generate(s,action):
    p=STAGE/(action+'.json')
    if p.exists():print(json.dumps({'existing':str(p)}));return
    e=MethodExecutor(ledger(s),STAGE,s['config']['executor']);e.readiness()
    if action=='facts':raise ContractError('The two model grounding failures are preserved; V3 uses an explicit deterministic control instead of more identical reader calls')
    if action=='direct':
        done=read(STAGE/'execution_closed_before_grading.json')
        messages=[{'role':'system','content':'Solve the original TRAIN legal question from the supplied original simplified policy, original case and shared extraction/bindings. Return only JSON {"answer":"Entailment" or "Contradiction" or null,"decisive_condition":string,"reason":string}. Do not make absent ages/returns false; distinguish the native complete event-record reading from an unrestricted narrative. No tools or labels.'},
                  {'role':'user','content':json.dumps({'public':s['case']['public'],'shared_raw_frame':read(STAGE/'literal_grounded_facts.json')['value'],'shared_calendar_bindings':done['native_bindings'],'normalization':done['normalization']},ensure_ascii=False)}]
        schema=None
    else:messages=s[action+'_messages'] if action=='source' else s['reader_messages'];schema=None if action=='source' else s['reader_schema']
    w=e.generate(RUN+':'+action,source=s['case']['key'],purpose='method_train_synthesis' if action=='source' else 'method_primitive_observation',messages=messages,thinking=False,schema=schema)
    result={'physical_response':w,'new_method_contribution':False,'goal_complete':False}
    if action=='source':
        try:
            comp=compile_function(w['content'],SIGNATURE);comparison=compare_modules(comp['expression'],REFERENCE,SIGNATURE,DOMAIN)
            if not comparison['equivalent_over_supplied_domain']:raise ContractError('Not equivalent to the supplied four source conditions: '+str(comparison))
            result.update(compiled=comp,source_comparison=comparison,status='source_verified')
        except Exception as exc:result.update(status='rejected',error_type=type(exc).__name__,error=str(exc))
    else:
        try:result['value']=json.loads(w['content']);result['status']='raw_observation_captured'
        except Exception as exc:result.update(status='rejected',error_type=type(exc).__name__,error=str(exc))
    immutable_json(p,result)
    print(json.dumps({k:v for k,v in result.items() if k!='physical_response'},ensure_ascii=False,indent=2))


def execute(s):
    target=STAGE/'execution_closed_before_grading.json'
    if target.exists():print(target.read_text());return
    source=read(STAGE/'source.json');reader=read(STAGE/'literal_grounded_facts.json')
    assert source['status']=='source_verified'
    frame=reader['value']; facts=s['case']['public']['facts']; query=s['case']['public']['query']
    errors=frame_errors(frame,facts)
    if errors:raise ContractError('Rejected source grounding: '+str(errors))
    m=re.fullmatch(r'Under section 152\(c\)\(1\), (\w+) is a qualifying child of (\w+) for the year (\d{4})\.',query)
    if not m:raise ContractError('Unsupported original native query')
    subject,taxpayer,year=m[1],m[2],int(m[3])
    # Check actual reported typed events against this original literal narrative.
    relationship=frame['relationships_152_c_2']; residence=frame['co_residence_intervals']
    if len(relationship)!=1 or len(residence)!=1:raise ContractError('The original case has one explicit relationship interval and one co-residence interval')
    r=relationship[0];h=residence[0]
    if r['quote'] not in facts or h['quote'] not in facts:raise ContractError('A reader evidence quote is absent')
    pattern=re.fullmatch(r'(\w+) bears a relationship to (\w+) pursuant to section 152\(c\)\(2\) for the years (\d{4}) to (\d{4})\.',r['quote'])
    if not pattern or (r['individual'],r['taxpayer'],r['start_year'],r['end_year'])!=(pattern[1],pattern[2],int(pattern[3]),int(pattern[4])):
        raise ContractError('Reported paragraph2 roles/year interval differ from their own quote')
    from datetime import datetime
    pattern=re.fullmatch(r'From (\w+ \d{1,2}(?:st|nd|rd|th)?, \d{4}) to (\w+ \d{1,2}(?:st|nd|rd|th)?, \d{4}), (\w+) and (\w+) lived in the same home\.',h['quote'])
    if not pattern:raise ContractError('Unsupported original co-residence sentence')
    def normalize(d):return datetime.strptime(re.sub(r'(\d)(?:st|nd|rd|th)',r'\1',d),'%B %d, %Y').date().isoformat()
    if (h['person1'],h['person2'],h['start'],h['end'])!=(pattern[3],pattern[4],normalize(pattern[1]),normalize(pattern[2])):
        raise ContractError('Residence roles/dates differ from their own quote; no relationship interval substitution')
    if frame['reported_birth_dates'] or frame['reported_joint_returns']:
        raise ContractError('No birth or joint-return event occurs in this literal case; marriage is not a return')
    if {h['person1'],h['person2']}!={taxpayer,subject} or (r['taxpayer'],r['individual'])!=(taxpayer,subject):
        raise ContractError('Participant binding differs from the original query')
    bindings={k:None for k in SIGNATURE};bindings.update(relationship_152_c_2=r['start_year']<=year<=r['end_year'],
        same_abode_days=union_days([(h['start'],h['end'])],year),tax_year_days=(date(year+1,1,1)-date(year,1,1)).days)
    native=assess(source['compiled']['expression'],bindings)
    # The narrative alone does not say that these are ALL possible residence
    # events; show that assumption separately instead of claiming pure NL proof.
    unrestricted=assess(source['compiled']['expression'],bindings|{'same_abode_days':None})
    assert native['possible_values']==[False] and unrestricted['possible_values']==[False,True]
    value={'native_bindings':bindings,'actual_learned_program_execution':native,
        'normalization':'Under the original native complete-event-record reading, the reported bounded co-residence record supplies34 of365 calendar days. This is a benchmark case-normalization convention, not a claim that the bare narrative excludes all unreported residence events.',
        'unrestricted_NL_without_event_completeness':unrestricted,
        'law_conditions_inferred_from_actual_executor_program':True,'reader_fallback_used':True,
        'deterministic_facts_not_learned':True,'this_native_result_NOT_counted_as_core_method_validation':True,'qualifying_child_NOT_supplied_as_input':True,
        'relationship_interval_not_used_as_residence_interval':True,'absence_of_birth_or_returns_not_defaulted_to_false':True,
        'original_reference_age_defaults_NOT_imported':True,'provided_API_and_calendar_adapter_NOT_claimed_learned':True,
        'program_sha256':hashlib.sha256((STAGE/'source.json').read_bytes()).hexdigest(),
        'reader_sha256':hashlib.sha256((STAGE/'literal_grounded_facts.json').read_bytes()).hexdigest(),
        'prediction':native['answer'],'native_label_not_opened_yet':True,'new_method_contribution':False,'goal_complete':False}
    immutable_json(target,value)
    immutable_json(STAGE/'frozen_library.json',{'compiled':source['compiled'],'input_contract':SIGNATURE,'domain':DOMAIN})
    restored=read(STAGE/'frozen_library.json');assert assess(restored['compiled']['expression'],bindings)==native
    print(json.dumps(value,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['offline','prepare','source','facts','execute','direct']);action=p.parse_args().action
    if action=='offline':print(json.dumps(offline()))
    else:
        s=prepare()
        if action=='prepare':print(json.dumps({'prepared':True,'offline':s['offline'],'new_calls':0}))
        elif action=='execute':execute(s)
        else:generate(s,action)
