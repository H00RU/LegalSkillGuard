"""Read input dependencies from the immutable author Prolog, without case data.

The graph overapproximates all clause branches, including negation and findall.
It is a public routing component, not a learned skill, proof trace or answer.
Unrecognized meta calls and undefined non-input predicates remain explicit.
"""
from collections import deque
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .sara_statute_kernel import ROOT, GIVENS, fact_vocabulary, query_term


# Public native-call ABI: the first argument denotes a source service event.
# The author's body uses its agent_/patient_ relations without calling service_.
# This declares the input type; it adds neither a service fact nor a legal rule.
QUERY_EVENT_INPUTS = {'s3306_c_10_A': {
    'arity': 4, 'argument': 0, 'family': 'service_', 'file': 'section3306.pl',
    'head': r's3306_c_10_A\(\s*Service\s*,\s*Employer\s*,\s*Employee\s*,\s*Workday\s*\)\s*:-'},
    's3306_c_1':{'arity':2,'argument':0,'family':'service_','file':'section3306.pl',
        'head':r's3306_c_1\(\s*Service\s*,\s*Caly\s*\)\s*:-'},
    's3306_c_2':{'arity':3,'argument':0,'family':'service_','file':'section3306.pl',
        'head':r's3306_c_2\(\s*Service\s*,\s*Location\s*,\s*Caly\s*\)\s*:-'},
    's3306_c_5':{'arity':4,'argument':0,'family':'service_','file':'section3306.pl',
        'head':r's3306_c_5\(\s*Service\s*,\s*Employer\s*,\s*Employee\s*,\s*Workday\s*\)\s*:-'},
    's3306_c_21':{'arity':4,'argument':0,'family':'service_','file':'section3306.pl',
        'head':r's3306_c_21\(\s*Service\s*,\s*Employee\s*,\s*S235\s*,\s*Workday\s*\)\s*:-'}}


def query_event_inputs(kernel):
    result = []
    for call in kernel['native_query']:
        declaration = QUERY_EVENT_INPUTS.get(call['predicate'])
        if declaration is None:
            continue
        if len(call['arguments']) != declaration['arity']:
            raise ValueError('Native query does not match its declared input ABI')
        name = declaration['file']
        body = (ROOT/kernel['statute_directory']/name).read_bytes()
        if hashlib.sha256(body).hexdigest() != kernel['statute_sha256'][name]:
            raise ValueError('Immutable author code changed before query-input binding')
        head = re.search(r'(?m)^' + declaration['head'], body.decode())
        if head is None:
            raise ValueError('Native query input declaration lacks its bound author signature')
        result.append({'predicate': call['predicate'], 'argument': declaration['argument'],
            'family': declaration['family'], 'source_file': name,
            'author_head': head.group(), 'routing_input_not_a_source_fact': True})
    return result


READER = r'''
:- use_module(library(lists)).

signature(Term,Name,Arity) :-
    (compound(Term) -> compound_name_arguments(Term,Name,Args),length(Args,Arity)
    ; atom(Term),Name=Term,Arity=0).
calls(Goal,_,[_{opaque:"variable_goal"}]) :- var(Goal), !.
calls((A,B),N,Rows) :- !, calls(A,N,L),calls(B,N,R),append(L,R,Rows).
calls((A;B),N,Rows) :- !, calls(A,N,L),calls(B,N,R),append(L,R,Rows).
calls((A->B),N,Rows) :- !, calls(A,N,L),calls(B,N,R),append(L,R,Rows).
calls(\+ A,_,Rows) :- !,calls(A,true,Rows).
calls(findall(_,Goal,_),N,Rows) :- !,calls(Goal,N,Rows).
calls(bagof(_,Goal,_),N,Rows) :- !,calls(Goal,N,Rows).
calls(setof(_,Goal,_),N,Rows) :- !,calls(Goal,N,Rows).
calls(forall(A,B),N,Rows) :- !,calls(A,N,L),calls(B,N,R),append(L,R,Rows).
calls(once(A),N,Rows) :- !,calls(A,N,Rows).
calls(call(A),N,Rows) :- !,calls(A,N,Rows).
calls(catch(A,_,B),N,Rows) :- !,calls(A,N,L),calls(B,N,R),append(L,R,Rows).
calls(Goal,_,[]) :- predicate_property(Goal,built_in), !.
calls(Goal,_,[]) :- predicate_property(Goal,imported_from(lists)), !.
calls(Goal,N,[_{predicate:Name,arity:Arity,negated:N}]) :-
    signature(Goal,Name,Arity).

record((:- _),_,_,none) :- !.
record((Head :- Body),File,Line,Row) :- !,
    signature(Head,Name,Arity), calls(Body,false,Calls),
    Row=_{predicate:Name,arity:Arity,calls:Calls,file:File,line:Line}.
record(Head,File,Line,_{predicate:Name,arity:Arity,calls:[],file:File,line:Line}) :-
    signature(Head,Name,Arity).
read_rows(Stream,File,Rows) :-
    stream_property(Stream,position(Pos)),stream_position_data(line_count,Pos,Line),
    read_term(Stream,Term,[syntax_errors(error)]),
    ( Term == end_of_file -> Rows=[]
    ; record(Term,File,Line,Row),read_rows(Stream,File,Tail),
      (Row==none -> Rows=Tail ; Rows=[Row|Tail]) ).
emit_calls([]).
emit_calls([Row|Rest]) :-
    (get_dict(opaque,Row,Value) -> format('O\t~w~n',[Value])
    ; format('C\t~w\t~d\t~w~n',[Row.predicate,Row.arity,Row.negated])),
    emit_calls(Rest).
emit_rows([]).
emit_rows([Row|Rest]) :-
    format('H\t~w\t~d\t~w\t~d~n',[Row.predicate,Row.arity,Row.file,Row.line]),
    emit_calls(Row.calls),emit_rows(Rest).
read_files([]).
read_files([Path|Rest]) :-
    setup_call_cleanup(open(Path,read,S),read_rows(S,Path,Rows),close(S)),
    emit_rows(Rows),read_files(Rest).
main :- current_prolog_flag(argv,Paths),read_files(Paths),halt.
'''


@lru_cache(maxsize=4)
def _read(directory, hashes):
    source = ROOT / directory
    paths, texts = [], {}
    for name, expected in hashes:
        if Path(name).name != name or name not in ('events.pl', 'utils.pl') and not (
                name.startswith('section') and name.endswith('.pl')):
            raise ValueError('Only the bound author statute files may be read')
        path = source / name
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError('Immutable statute changed before dependency extraction')
        paths.append(str(path))
        texts[name] = body.decode()
    runtime = ROOT / '.local-tools/swi-prolog-reference/root'
    env = {**os.environ, 'SWI_HOME_DIR': str(runtime/'usr/lib/swi-prolog'),
           'LD_LIBRARY_PATH': str(runtime/'usr/lib')}
    with tempfile.TemporaryDirectory(prefix='lsg-statute-dependencies-') as folder:
        path = Path(folder)/'read_author_terms.pl'
        path.write_text(READER)
        result = subprocess.run([str(runtime/'usr/lib/swi-prolog/bin/amd64/swipl'),
            '-q', '-s', str(path), '-g', 'main', '--', *paths],
            text=True, capture_output=True, timeout=15, env=env, cwd=folder)
    if result.returncode or 'ERROR' in result.stderr:
        raise ValueError('Author dependency extraction failed: '+result.stderr[-1500:])
    rows = []
    for line in result.stdout.splitlines():
        parts = line.split('\t')
        if parts[0] == 'H' and len(parts) == 5:
            rows.append({'predicate':parts[1], 'arity':int(parts[2]),
                'file':Path(parts[3]).name,'line':int(parts[4]),'calls':[]})
        elif parts[0] == 'C' and len(parts) == 4 and rows:
            rows[-1]['calls'].append({'predicate':parts[1],'arity':int(parts[2]),'negated':parts[3]=='true'})
        elif parts[0] == 'O' and len(parts) == 2 and rows:
            rows[-1]['calls'].append({'opaque':parts[1]})
        else:
            raise ValueError('Malformed author dependency record')
    return rows, fact_vocabulary(texts['events.pl'])


def dependency_graph(kernel):
    """Follow every author clause from the query; never inspect current facts."""
    for call in kernel['native_query']:
        query_term(call)
    rows, primitives = _read(kernel['statute_directory'],
        tuple(sorted(kernel['statute_sha256'].items())))
    definitions = {}
    for row in rows:
        definitions.setdefault((row['predicate'], row['arity']), []).append(row)
    inputs = {**primitives, **{p:len(args) for p,args in GIVENS.items()}}
    roots = {(c['predicate'], len(c['arguments'])) for c in kernel['native_query']}
    queue, visited, required, edges, opaque, missing = deque(sorted(roots)), set(), set(), [], [], []
    while queue:
        key = queue.popleft()
        if key in visited:
            continue
        visited.add(key)
        if inputs.get(key[0]) == key[1] and key not in roots:
            required.add(key)
        if key not in definitions:
            if inputs.get(key[0]) != key[1]:
                missing.append(key[0]+'/'+str(key[1]))
            continue
        for row in definitions[key]:
            for call in row['calls']:
                origin = {'from':key[0]+'/'+str(key[1]),'file':row['file'],'line':row['line']}
                if 'opaque' in call:
                    opaque.append({**origin, **call})
                else:
                    target = (call['predicate'],call['arity'])
                    edges.append({**origin,'to':target[0]+'/'+str(target[1]),'negated':call['negated']})
                    queue.append(target)
    query_inputs = query_event_inputs(kernel)
    required.update((row['family'], 1) for row in query_inputs)
    return {'query_heads':sorted(p+'/'+str(a) for p,a in roots),
        'input_predicates':dict(sorted(required)),
        'declared_query_event_inputs':query_inputs,
        'reachable_predicates':sorted(p+'/'+str(a) for p,a in visited),
        'edges':edges,'opaque_calls':opaque,'undefined_non_input_predicates':sorted(set(missing)),
        'graph_complete_for_supported_control_forms':not opaque and not missing,
        'scope':'Overapproximation of public clause branches and declared native-call inputs, not a minimal current-case read or proof',
        'no_case_data_or_labels_read':True,'not_a_learned_mechanism':True,
        'statute_sha256':kernel['statute_sha256'],'new_model_calls':0}
