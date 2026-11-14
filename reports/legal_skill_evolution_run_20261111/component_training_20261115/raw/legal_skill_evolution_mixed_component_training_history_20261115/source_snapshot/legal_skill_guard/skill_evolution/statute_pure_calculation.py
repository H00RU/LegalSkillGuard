"""Conservative public fast path for directly arithmetic statute clauses.

All clauses of every query head must use only the listed pure builtins. Any
custom call, factual predicate, meta-call or unrecognized body denies the
certificate. This is shared execution infrastructure, not learned observation
success, and consumes neither a case label nor a model request.
"""
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

from .sara_statute_kernel import ROOT, query_term


INSPECTOR = r'''
lsg_pure_calc(true).
lsg_pure_calc(fail).
lsg_pure_calc(!).
lsg_pure_calc((A,B)) :- lsg_pure_calc(A), lsg_pure_calc(B).
lsg_pure_calc((A;B)) :- lsg_pure_calc(A), lsg_pure_calc(B).
lsg_pure_calc((A->B)) :- lsg_pure_calc(A), lsg_pure_calc(B).
lsg_pure_calc(\+ A) :- lsg_pure_calc(A).
lsg_pure_calc(Goal) :- nonvar(Goal), functor(Goal,Name,Arity),
    memberchk(Name/Arity,[is/2,(>)/2,(<)/2,(>=)/2,(=<)/2,(=:=)/2,(=\=)/2,
        (=)/2,(==)/2,(\==)/2,(\=)/2,nonvar/1,var/1,number/1,integer/1,float/1,ground/1]).
lsg_calc_head(Name/Arity) :- functor(Head,Name,Arity),
    findall(Body,clause(Head,Body),Bodies), Bodies\=[],
    forall(member(Body,Bodies),lsg_pure_calc(Body)).
'''


@lru_cache(maxsize=128)
def _certificate(directory, hashes, heads):
    source = ROOT / directory
    texts = {}
    for name, sha in hashes:
        body = (source / name).read_bytes()
        if hashlib.sha256(body).hexdigest() != sha:
            raise ValueError('Immutable statute changed before common calculation check')
        texts[name] = body.decode()
    order = ['events.pl','utils.pl', *sorted(n for n in texts if n.startswith('section'))]
    targets = '[' + ','.join(name+'/'+str(arity) for name,arity in heads) + ']'
    program = ':- style_check(-singleton).\n:- use_module(library(lists)).\n'
    program += '\n'.join(texts[n] for n in order) + INSPECTOR
    program += "\nlsg_calc_main :- (forall(member(H,"+targets+"),lsg_calc_head(H)) -> write('LSG_PURE') ; write('LSG_NOT_CERTIFIED')),halt.\n"
    runtime = ROOT / '.local-tools/swi-prolog-reference/root'
    env = {**os.environ,'SWI_HOME_DIR':str(runtime/'usr/lib/swi-prolog'),'LD_LIBRARY_PATH':str(runtime/'usr/lib')}
    with tempfile.TemporaryDirectory(prefix='lsg-pure-statute-') as folder:
        path = Path(folder)/'statutes_and_calculation_check.pl'
        path.write_text(program)
        result = subprocess.run([str(runtime/'usr/lib/swi-prolog/bin/amd64/swipl'),'-q','-s',str(path),'-g','lsg_calc_main'],
            text=True,capture_output=True,timeout=10,cwd=folder,env=env)
    return {'certified_fact_independent':result.returncode==0 and result.stdout.strip()=='LSG_PURE' and 'ERROR' not in result.stderr,
        'scope':'All direct clause bodies are pure arithmetic/type/control operations; no custom calls accepted.',
        'statute_sha256':dict(hashes),'query_heads':[name+'/'+str(arity) for name,arity in heads],
        'not_a_learned_mechanism':True,'new_model_calls':0}


def certificate(kernel):
    for call in kernel['native_query']:
        query_term(call)  # Validate the prepared statutory name/argument syntax.
    heads = tuple(sorted({(c['predicate'],len(c['arguments'])) for c in kernel['native_query']}))
    return _certificate(kernel['statute_directory'],tuple(sorted(kernel['statute_sha256'].items())),heads)
