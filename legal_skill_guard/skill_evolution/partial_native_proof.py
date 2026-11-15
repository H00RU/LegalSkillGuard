"""Guard native execution by the factual scopes it actually reads.

The author clauses and finite-failure semantics are unchanged. Every factual
lookup records its acquired closure. A verdict needs either a native execution
with no unread lookup, or known independent negated conjuncts refuting every
compatible author clause. The latter records the original heads and witnesses;
unknown attributes remain unknown and no factual completion is asserted.
"""
import json
import re
import subprocess

from .literal_statutory_givens import admissible, validate_givens
from .objects import digest
from .sara_statute_kernel import GIVENS, prepare_case, run_program, scalar
from .statute_input_dependencies import _read


EVENT_ROLE_PORTS = {'agent_', 'patient_', 'start_', 'end_', 'location_',
    'purpose_', 'type_', 'reason_', 'amount_', 'means_', 'beneficiary_', 'country_', 'destination_'}


GUARD = r'''
:- dynamic lsg_seen/4.
:- dynamic lsg_alternative_read/4.
:- discontiguous lsg_case_complete/0,lsg_family_complete/1,lsg_event_complete/2,lsg_given_absent/1,lsg_fact/2,lsg_scan_complete/1,lsg_property_complete/2.
lsg_case_complete :- fail.
lsg_family_complete(_) :- fail.
lsg_event_complete(_,_) :- fail.
lsg_scan_complete(_) :- fail.
lsg_property_complete(_,_) :- fail.
lsg_given_absent(_) :- fail.
lsg_fact(_,_) :- fail.

lsg_scope(P,Args) :-
    (Args=[E|_],string(E) -> Key=E ; Key=null),
    ( lsg_case_complete -> Known=true,Origin="complete_case_contract"
    ; lsg_family_complete(P) -> Known=true,Origin="acquired_family_contract"
    ; lsg_scan_complete(P) -> Known=true,Origin="acquired_family_scan_contract"
    ; memberchk(P,ROLE_PORTS), Args=[Event|_],ground(Event),
      lsg_property_complete(Event,P) -> Known=true,Origin="acquired_property_contract"
    ; memberchk(P,ROLE_PORTS), Args=[Event|_],ground(Event),
      lsg_event_complete(Event,_) -> Known=true,Origin="acquired_event_contract"
    ; lsg_given_absent(P) -> Known=true,Origin="literal_given_contract"
    ; Known=false,Origin="unread" ),
    (lsg_seen(P,Key,Known,Origin) -> true ; assertz(lsg_seen(P,Key,Known,Origin))).

% An independent, known-true negated conjunct makes its author clause false.
% Variables shared with the head or other conjuncts must already be ground.
% No source fact is completed, and every compatible author clause must have
% such a witness. An unknown or unsuccessful witness proves nothing.
lsg_conjuncts((A,B),Rows) :- !,lsg_conjuncts(A,L),lsg_conjuncts(B,R),append(L,R,Rows).
lsg_conjuncts(A,[A]).
lsg_disjoint([], _).
lsg_disjoint([X|Xs],Ys) :- \+ (member(Y,Ys),X==Y),lsg_disjoint(Xs,Ys).
lsg_save_alternatives :-
    findall(r(P,E,K,O),lsg_seen(P,E,K,O),Rows),lsg_save_unknown(Rows).
lsg_save_unknown([]).
lsg_save_unknown([r(P,E,false,O)|Tail]) :- !,
    (lsg_alternative_read(P,E,false,O) -> true ; assertz(lsg_alternative_read(P,E,false,O))),
    lsg_save_unknown(Tail).
lsg_save_unknown([_|Tail]) :- lsg_save_unknown(Tail).
lsg_known_witness(Goal,Reads) :-
    retractall(lsg_seen(_,_,_,_)),
    (catch(once(Goal),_,fail),\+ lsg_seen(_,_,false,_) ->
        findall(r(P,E,K,O),lsg_seen(P,E,K,O),Reads)
    ; lsg_save_alternatives,fail).
lsg_refute_clause(Head,Body,proof(H,N,Reads)) :-
    lsg_conjuncts(Body,Conjuncts),select(\+ Negative,Conjuncts,Others),
    term_variables(Negative,Local),term_variables((Head,Others),Shared),
    lsg_disjoint(Local,Shared),lsg_known_witness(Negative,Reads),
    term_string(Head,H),term_string(Negative,N),!.
lsg_refute_clauses([],[]).
lsg_refute_clauses([c(H,B)|Tail],[Proof|Rest]) :-
    lsg_refute_clause(H,B,Proof),lsg_refute_clauses(Tail,Rest).
lsg_refute_root((A,B),Proofs) :- !,(lsg_refute_root(A,Proofs);lsg_refute_root(B,Proofs)).
lsg_refute_root(Goal,Proofs) :-
    findall(c(Goal,Body),clause(Goal,Body),Rows),Rows=[_|_],lsg_refute_clauses(Rows,Proofs).
lsg_restore_reads([]).
lsg_restore_reads([r(P,E,K,O)|Tail]) :-
    (lsg_seen(P,E,K,O) -> true ; assertz(lsg_seen(P,E,K,O))),lsg_restore_reads(Tail).
lsg_restore_proofs([]).
lsg_restore_proofs([proof(_,_,Reads)|Tail]) :-lsg_restore_reads(Reads),lsg_restore_proofs(Tail).
lsg_try_refutation(Goal,Proofs) :-
    catch(lsg_refute_root(Goal,Proofs),_,fail),
    retractall(lsg_seen(_,_,_,_)),lsg_restore_proofs(Proofs).

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
lsg_json_proofs([]).
lsg_json_proofs([proof(H,N,_)|Tail]) :-
    write('{"author_head":'),lsg_json_string(H),write(',"known_blocking_goal":'),
    lsg_json_string(N),write('}'),(Tail=[] -> true ; write(','),lsg_json_proofs(Tail)).
'''


def execute(kernel, binding, complete_families, public, *, scope_contract=None):
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
    scans, properties = set(), set()
    if scope_contract is not None:
        if set(scope_contract) != {'family_scans', 'event_properties'}:
            raise ValueError('An explicit partial scope has family scans and event properties')
        scans = set(scope_contract['family_scans'])
        if not scans <= {p for p,a in primitive.items() if a==1}:
            raise ValueError('A family scan closes only a declared unary factual predicate')
        subjects = {r['arguments'][0] for r in facts if primitive.get(r['predicate'])==1}
        countries = {r['arguments'][1] for r in facts if r['predicate']=='location_'}
        countries.update(r['arguments'][0] for r in facts if r['predicate']=='country_')
        for row in scope_contract['event_properties']:
            if set(row) != {'event', 'predicate'}:
                raise ValueError('A property scope names its observed referent and predicate')
            event,predicate = row['event'],row['predicate']
            if predicate not in EVENT_ROLE_PORTS or primitive.get(predicate)!=2:
                raise ValueError('A property scope must be a declared factual role or property')
            if event not in (countries if predicate=='country_' else subjects):
                raise ValueError('Property closure cannot invent an unobserved referent')
            properties.add((event,predicate))
    event_families = {}
    for row in facts:
        if primitive.get(row['predicate'])==1:
            event_families.setdefault(row['arguments'][0],set()).add(row['predicate'])
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
    for p in sorted(scans):
        body += 'lsg_scan_complete('+scalar(p)+').\n'
    for event,predicate in sorted(properties):
        body += 'lsg_property_complete('+scalar(event)+','+scalar(predicate)+').\n'
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
        # Log successful witnesses after unification. If enumeration is
        # exhausted, log the original lookup before finite failure. Positive
        # existentials need one complete witness; negation/aggregation still
        # require closure of their original (possibly unbound) lookup scope.
        body += name+'('+args+') :- lsg_fact('+scalar(name)+',['+args+']), lsg_scope('+scalar(name)+',['+args+']).\n'
        body += name+'('+args+') :- lsg_scope('+scalar(name)+',['+args+']), fail.\n'
    conflicts = ';'.join('once(('+term+'))' for term in prepared['negative_terms']) or 'fail'
    body += '''
lsg_case_main :-
    catch(( (''' + conflicts + ''') -> Verdict="negative_given_conflict"
          ; lsg_try_refutation((''' + prepared['goal'] + '''),Proofs) ->
                Verdict="Contradiction",Mode="independent_author_conjunct_refutation"
          ; retractall(lsg_seen(_,_,_,_)),once((''' + prepared['goal'] + ''')) -> Verdict="Entailment"
          ; Verdict="Contradiction" ), Error,
          (term_string(Error,Text),Verdict="execution_error")),
    (var(Text) -> Detail=null ; Detail=Text),
    (var(Mode) -> Mode="guarded_native_execution" ; true),
    (var(Proofs) -> Proofs=[] ; true),
    findall(r(P,E,K,O),lsg_seen(P,E,K,O),Reads),
    findall(r(P,E,K,O),lsg_alternative_read(P,E,K,O),Alternatives),
    write('{"verdict":'),lsg_json_string(Verdict),write(',"reads":['),lsg_json_rows(Reads),
    write('],"error":'),lsg_json_nullable(Detail),write(',"proof_mode":'),lsg_json_string(Mode),
    write(',"refutations":['),lsg_json_proofs(Proofs),
    write('],"alternative_refutation_demands":['),lsg_json_rows(Alternatives),write(']}'),halt.
'''
    receipt = {**prepared['receipt'], 'backend':'guarded_official_statute_program',
        'complete_families':sorted(complete),'known_complete_events':{k:sorted(v) for k,v in complete_events.items()},
        'explicit_family_scans':sorted(scans),
        'explicit_event_properties':[{'event':e,'predicate':p} for e,p in sorted(properties)],
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
        elif read['origin']=='acquired_family_scan_contract':used_families.add(read['predicate'])
        elif read['origin']=='acquired_property_contract':used_families.update(event_families.get(read['event'],()))
        elif read['origin']=='acquired_event_contract':used_families.update(complete_events[read['event']])
        elif read['origin']=='complete_case_contract':used_families.update(complete)
    return {**receipt,'handled':accepted,'answer':value['verdict'] if accepted else None,
        'raw_native_probe_verdict':value['verdict'],'factual_accesses':reads,'unread_factual_scopes':unread,
        'proof_mode':value['proof_mode'],'independent_author_refutations':value['refutations'],
        'alternative_refutation_demands':value['alternative_refutation_demands'],
        'used_observation_families':sorted(used_families), 'execution_error':value['error'],
        'reason':None if accepted else 'Native proof depends on unread scopes or failed execution'}
