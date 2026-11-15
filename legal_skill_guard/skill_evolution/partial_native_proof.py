"""Guard native execution by the factual scopes it actually reads.

The author clauses and finite-failure semantics are unchanged. Every factual
lookup records whether its whole family, or its specific event's family, was
observed completely. A verdict is accepted only if the actual execution visited
no unread scope. No unknown fact is asserted or silently assumed absent.
"""
import json
import re
import subprocess

from .literal_statutory_givens import admissible, validate_givens
from .objects import digest
from .sara_statute_kernel import GIVENS, prepare_case, run_program, scalar
from .statute_input_dependencies import _read


EVENT_ROLE_PORTS = {'agent_', 'patient_', 'start_', 'end_', 'location_',
    'purpose_', 'amount_', 'means_', 'beneficiary_', 'country_', 'destination_'}


GUARD = r'''
:- dynamic lsg_seen/4.
:- discontiguous lsg_case_complete/0,lsg_family_complete/1,lsg_event_complete/2,lsg_given_absent/1,lsg_fact/2.
lsg_case_complete :- fail.
lsg_family_complete(_) :- fail.
lsg_event_complete(_,_) :- fail.
lsg_given_absent(_) :- fail.
lsg_fact(_,_) :- fail.

lsg_scope(P,Args) :-
    (Args=[E|_],string(E) -> Key=E ; Key=null),
    ( lsg_case_complete -> Known=true,Origin="complete_case_contract"
    ; lsg_family_complete(P) -> Known=true,Origin="acquired_family_contract"
    ; memberchk(P,ROLE_PORTS), Args=[Event|_],ground(Event),
      lsg_event_complete(Event,_) -> Known=true,Origin="acquired_event_contract"
    ; lsg_given_absent(P) -> Known=true,Origin="literal_given_contract"
    ; Known=false,Origin="unread" ),
    (lsg_seen(P,Key,Known,Origin) -> true ; assertz(lsg_seen(P,Key,Known,Origin))).

% A fixed, typed result protocol; the minimal author runtime has no JSON FFI.
lsg_json_hex(N) :- (N<10 -> C is 48+N ; C is 87+N),put_code(C).
lsg_json_codes([]).
lsg_json_codes([C|Tail]) :-
    ( (C=:=34;C=:=92) -> put_code(92),put_code(C)
    ; C<32 -> put_code(92),put_code(117),put_code(48),put_code(48),
              H is C//16,L is C mod 16,lsg_json_hex(H),lsg_json_hex(L)
    ; put_code(C) ),lsg_json_codes(Tail).
lsg_json_string(S) :- put_code(34),string_codes(S,Codes),lsg_json_codes(Codes),put_code(34).
lsg_json_nullable(S) :- (S==null -> write('null') ; lsg_json_string(S)).
lsg_json_rows([]).
lsg_json_rows([r(P,E,K,O)|Tail]) :-
    write('{"predicate":'),lsg_json_string(P),write(',"event":'),lsg_json_nullable(E),
    write(',"complete_scope":'),write(K),write(',"origin":'),lsg_json_string(O),write('}'),
    (Tail=[] -> true ; write(','),lsg_json_rows(Tail)).
'''


def execute(kernel, binding, complete_families, public):
    """Execute one coherent observation world; this is not a source oracle."""
    prepared = prepare_case(kernel, binding)
    validate_givens(binding, public)
    primitive = prepared['primitive']
    complete = set(complete_families)
    if not complete <= {p for p,a in primitive.items() if a==1} | set(GIVENS):
        raise ValueError('Partial proof needs declared whole-family observation contracts')
    rows, _ = _read(kernel['statute_directory'], tuple(sorted(kernel['statute_sha256'].items())))
    if any(row['predicate'] in primitive for row in rows):
        return {'handled':False,'answer':None,'reason':'Author-defined factual predicates require separate scope analysis'}
    if any('opaque' in call for row in rows for call in row['calls']):
        return {'handled':False,'answer':None,'reason':'Opaque author meta-call is outside factual scope instrumentation'}
    if re.search(r'\b(?:clause|assertz?|asserta|retract(?:all)?|predicate_property|current_predicate)\s*\(',
            prepared['statute_program']):
        return {'handled':False,'answer':None,'reason':'Reflective author code is outside factual scope instrumentation'}

    facts = prepared['normalized_facts']
    complete_events = {}
    for row in facts:
        if row['predicate'] in complete and primitive.get(row['predicate'])==1:
            complete_events.setdefault(row['arguments'][0],set()).add(row['predicate'])
    targets = {q['predicate'] for q in kernel['native_query']}
    absent_givens = set(GIVENS) - admissible(public, targets)
    body = prepared['statute_program'] + GUARD.replace('ROLE_PORTS',
        '['+','.join(scalar(p) for p in sorted(EVENT_ROLE_PORTS))+']')
    if binding['extraction_status']=='complete':body+='lsg_case_complete.\n'
    for p in sorted(complete):
        body += 'lsg_family_complete('+scalar(p)+').\n'
    for event, families in sorted(complete_events.items()):
        for family in sorted(families):
            body += 'lsg_event_complete('+scalar(event)+','+scalar(family)+').\n'
    for p in sorted(absent_givens):
        body += 'lsg_given_absent('+scalar(p)+').\n'
    for row in facts:
        body += 'lsg_fact('+scalar(row['predicate'])+',['+','.join(scalar(a) for a in row['arguments'])+']).\n'
    vocabulary = {**primitive, **{p:len(args) for p,args in GIVENS.items()}}
    for name,arity in sorted(vocabulary.items()):
        args = ','.join('A'+str(i) for i in range(arity))
        body += name+'('+args+') :- lsg_scope('+scalar(name)+',['+args+']), lsg_fact('+scalar(name)+',['+args+']).\n'
    conflicts = ';'.join('once(('+term+'))' for term in prepared['negative_terms']) or 'fail'
    body += '''
lsg_case_main :-
    catch(( (''' + conflicts + ''') -> Verdict="negative_given_conflict"
          ; once((''' + prepared['goal'] + ''')) -> Verdict="Entailment"
          ; Verdict="Contradiction" ), Error,
          (term_string(Error,Text),Verdict="execution_error")),
    (var(Text) -> Detail=null ; Detail=Text),
    findall(r(P,E,K,O),lsg_seen(P,E,K,O),Reads),
    write('{"verdict":'),lsg_json_string(Verdict),write(',"reads":['),lsg_json_rows(Reads),
    write('],"error":'),lsg_json_nullable(Detail),write('}'),halt.
'''
    receipt = {**prepared['receipt'], 'backend':'guarded_official_statute_program',
        'complete_families':sorted(complete),'known_complete_events':{k:sorted(v) for k,v in complete_events.items()},
        'literal_absent_source_givens':sorted(absent_givens),
        'declared_case_extraction_status':binding['extraction_status'],
        'binding_sha256':digest(binding), 'instrumented_program_sha256':digest(body),
        'unknown_observations_not_assumed_false':True,
        'family_completeness_is_an_acquired_claim_not_a_source_truth_certificate':True}
    try:
        raw = run_program(body)
    except subprocess.TimeoutExpired:
        return {**receipt,'handled':False,'answer':None,
            'error':'Author-native execution exceeded the unchanged 35-second limit'}
    if raw.returncode or 'ERROR' in raw.stderr:
        return {**receipt,'handled':False,'answer':None,'error':raw.stdout+'\n'+raw.stderr}
    try:
        value = json.loads(raw.stdout)
    except json.JSONDecodeError:
        return {**receipt,'handled':False,'answer':None,'error':'Non-JSON native proof output: '+raw.stdout}
    reads = value['reads']
    unread = [r for r in reads if not r['complete_scope']]
    accepted = value['verdict'] in ('Entailment','Contradiction') and not unread
    used_families = set()
    for read in reads:
        if read['origin']=='acquired_family_contract':used_families.add(read['predicate'])
        elif read['origin']=='acquired_event_contract':used_families.update(complete_events[read['event']])
        elif read['origin']=='complete_case_contract':used_families.update(complete)
    return {**receipt,'handled':accepted,'answer':value['verdict'] if accepted else None,
        'raw_native_probe_verdict':value['verdict'],'factual_accesses':reads,'unread_factual_scopes':unread,
        'used_observation_families':sorted(used_families), 'execution_error':value['error'],
        'reason':None if accepted else 'Native proof depends on unread scopes or failed execution'}
