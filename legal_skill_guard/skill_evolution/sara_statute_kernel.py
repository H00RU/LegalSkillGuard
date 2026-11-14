"""Run immutable author statute code on model-supplied, typed case facts.

This is a shared correct-program control for factual grounding. No original
case facts, answer labels, construction metadata or reference oracle is loaded.
Unknown extraction never becomes finite failure. Only data are serialized;
model strings cannot become Prolog code or a new legal rule.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
GIVENS = {'s151_b_applies': 3, 's151_c_applies': 3}


def input_schema(kernel):
    """Expose the existing native predicate arities/types to guided decoding."""
    from .native import record_schema
    def record(name, arity):
        types = ['string'] * arity
        if name == 'amount_':
            types[-1] = 'number'
        elif name in GIVENS:
            types[-1] = 'integer'
        return record_schema({'predicate': {'type': 'string', 'enum': [name]},
            'arguments': {'type': 'array', 'prefixItems': [{'type': value} for value in types],
                          'items': False, 'minItems': arity, 'maxItems': arity}})
    facts = {'oneOf': [record(name, arity) for name, arity in sorted(kernel['fact_arities'].items())]}
    negatives = {'oneOf': [record(name, arity) for name, arity in sorted(GIVENS.items())]}
    return record_schema({'facts': {'type': 'array', 'items': facts},
        'negative_givens': {'type': 'array', 'items': negatives},
        'extraction_status': {'type': 'string', 'enum': ['complete', 'unread']}})


def fact_vocabulary(events_text):
    declared = {name: int(arity) for name, arity in re.findall(
        r'^:- discontiguous ([a-z][A-Za-z0-9_]*)/(\d+)\.', events_text, re.M)}
    # Calendar predicates are operations, not case facts. The remaining
    # underscore predicates are the author's primitive event vocabulary.
    return {name: arity for name, arity in declared.items() if name.endswith('_')}


def scalar(value):
    if type(value) is str:
        return json.dumps(value, ensure_ascii=False)
    if type(value) is int or type(value) is float and math.isfinite(value):
        return repr(value)
    raise ValueError('Native factual arguments are finite numbers or literal strings')


def fact_term(record, vocabulary):
    if set(record) != {'predicate', 'arguments'}:
        raise ValueError('A native fact is a predicate and its ground arguments')
    predicate, args = record['predicate'], record['arguments']
    if predicate not in vocabulary or not isinstance(args, list) or len(args) != vocabulary[predicate]:
        raise ValueError('Undeclared native factual predicate or wrong arity')
    return predicate + '(' + ','.join(scalar(arg) for arg in args) + ')'


def query_term(call):
    predicate = call['predicate']
    if not re.fullmatch(r's\d+[A-Za-z0-9_]*', predicate):
        raise ValueError('Only a prepared native statutory query can be executed')
    args = []
    for arg in call['arguments']:
        if isinstance(arg, dict):
            if arg != {'variable': '_'}:
                raise ValueError('Only the original anonymous native query variable is supported')
            args.append('_')
        else:
            args.append(scalar(arg))
    return predicate + '(' + ','.join(args) + ')'


def execute(kernel, binding):
    if binding.get('extraction_status') != 'complete':
        return {'handled': False, 'answer': None, 'reason': 'Case extraction is unread or incomplete'}
    if set(binding) != {'facts', 'negative_givens', 'extraction_status'}:
        raise ValueError('Native case binding has undeclared or missing fields')
    source = ROOT / kernel['statute_directory']
    sources = {}
    for name, expected in kernel['statute_sha256'].items():
        if Path(name).name != name or name not in ('events.pl', 'utils.pl') and not re.fullmatch(r'section\d+\.pl', name):
            raise ValueError('Not a declared statute-only source file')
        body = (source / name).read_bytes()
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError('Immutable official statute source changed')
        sources[name] = body.decode()
    primitive = fact_vocabulary(sources['events.pl'])
    vocabulary = {**primitive, **GIVENS}
    targets = {call['predicate'] for call in kernel['native_query']}
    if not isinstance(binding['facts'], list) or not isinstance(binding['negative_givens'], list):
        raise ValueError('Factual channels must be arrays')
    terms = [fact_term(record, vocabulary) for record in binding['facts']]
    if len(terms) != len(set(terms)):
        raise ValueError('Duplicate factual assertions are not separate events')
    if any(record['predicate'] in targets for record in binding['facts']):
        raise ValueError('The target query cannot be asserted as a case fact')
    negatives = [fact_term(record, GIVENS) for record in binding['negative_givens']]
    goal = ','.join(query_term(call) for call in kernel['native_query'])
    order = ['events.pl', 'utils.pl', *sorted(name for name in sources if name.startswith('section'))]
    declarations = '\n'.join(':- discontiguous ' + name + '/' + str(arity) + '.' for name, arity in GIVENS.items())
    body = ':- style_check(-singleton).\n:- use_module(library(lists)).\n' + declarations + '\n'
    body += '\n'.join(sources[name] for name in order) + '\n'
    body += '\n'.join(term + '.' for term in terms) + '\n'
    conflicts = ';'.join('once((' + term + '))' for term in negatives) or 'fail'
    body += '''lsg_case_main :-
        ( (''' + conflicts + ''') -> write('LSG_NEGATIVE_GIVEN_CONFLICT')
        ; catch(((''' + goal + ''') -> write('LSG_ENTAILMENT') ; write('LSG_CONTRADICTION')),
                Error,(write('LSG_ERROR:'),write_canonical(Error))) ), halt.
'''
    runtime = ROOT / '.local-tools/swi-prolog-reference/root'
    env = {**os.environ, 'SWI_HOME_DIR': str(runtime / 'usr/lib/swi-prolog'),
           'LD_LIBRARY_PATH': str(runtime / 'usr/lib')}
    with tempfile.TemporaryDirectory(prefix='lsg-native-factual-') as folder:
        path = Path(folder) / 'statutes_and_current_model_facts.pl'
        path.write_text(body)
        result = subprocess.run([str(runtime / 'usr/lib/swi-prolog/bin/amd64/swipl'),
            '-q', '-s', str(path), '-g', 'lsg_case_main'], cwd=folder,
            env=env, text=True, capture_output=True, timeout=35)
    receipt = {'backend': 'official_statute_program_with_model_facts',
               'fact_count': len(terms), 'source_program_unchanged': True,
               'case_truth_not_certified_by_types_or_quotes': True}
    if result.returncode or 'ERROR' in result.stderr or 'LSG_ERROR:' in result.stdout or 'LSG_NEGATIVE_GIVEN_CONFLICT' in result.stdout:
        return {**receipt, 'handled': False, 'answer': None,
                'error': (result.stdout + '\n' + result.stderr)[-1800:]}
    answer = {'LSG_ENTAILMENT': 'Entailment', 'LSG_CONTRADICTION': 'Contradiction'}.get(result.stdout.strip())
    return {**receipt, 'handled': answer is not None, 'answer': answer}
