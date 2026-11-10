"""Real predicate readings and typed semantic induction on existing TRAIN.

No previously generated normative heads are used as raw syntax or model output.
The current Goal and cumulative ledger are retained; DEV and TEST remain closed.
"""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor, MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.semantic_frames import obj
from legal_skill_guard.rr.source_attachment_forests import literal
from legal_skill_guard.rr.predicate_norm_learning import enrich, fit, predict, score_outputs, validate_outputs, STEMS
from legal_skill_guard.rr.contract_compiler_runtime import check, run
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rr_method_redesign_20261109'
RUN = 'predicate_norm_learning_v1_20261110'
STAGE = BASE / RUN
PROTOCOL = ROOT / 'reports/method_redesign_20261109/predicate_norm_learning_protocol.md'
S = {'type': 'string'}
A = lambda t: {'type': 'array', 'items': t}
NODE = obj({k: S for k in ['id', 'predicate_quote', 'modal_quote', 'negation_quote', 'actor_quote', 'object_quote']})
EDGE = obj({'parent': S, 'child': S, 'relation': {'type': 'string', 'enum':
    ['complement', 'condition', 'exception', 'reference', 'coordination', 'relative']}, 'quote': S})
SYNTAX = obj({'nodes': A(NODE), 'edges': A(EDGE)})
CODE = obj({'code': S, 'learned_operations': A(S), 'limitations': A(S)})


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot():
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as c:
        return {t: c.execute('select * from ' + t + ' order by 1').fetchall() for t in ['calls', 'meta', 'oracle_views']}


def prepare():
    if (STAGE / 'seal.json').exists():
        return read(STAGE / 'seal.json')
    previous = read(BASE / 'contract_attachment_update_v1_20261110/training_seal.json')
    annotated = read(BASE / 'source_attachment_learning_v6_20261110/author_checked_partial_source_feedback.json')
    units = [{'key': r['training_key'], 'source': r['source'], 'text': r['support_spans'][0]} for r in annotated['annotations']]
    paths = ['experiments/rr_v2_predicate_norm_learning.py', 'legal_skill_guard/rr/predicate_norm_learning.py',
             'tests/test_rr_predicate_norm_learning.py', 'legal_skill_guard/rr/source_attachment_forests.py',
             'legal_skill_guard/rr/method_client.py', 'legal_skill_guard/rr/method_ledger.py',
             'legal_skill_guard/rr/client.py', 'legal_skill_guard/rr/contract_compiler_runtime.py']
    files = {p: sha(ROOT / p) for p in paths}
    public = {p['key']: p for p in read(ROOT / 'data/packets/rr_v2/public_train.json')['sources']}
    reserved = []
    for ordinal in [121, 122]:
        source = previous['sources']['train'][ordinal - 1];p = public[source]
        assert p['dataset'] == 'ContractNLI'
        reserved.append({'ordinal': ordinal, 'source': source, 'group': p['group'],
                         'document_sha256': hashlib.sha256(p['public']['document'].encode()).hexdigest()})
    seal = {'run_id': RUN, 'config': previous['config'], 'sources': previous['sources'],
            'units': units, 'training_documents_and_native_supervision': previous['documents'],
            'source_feedback': annotated, 'older_explicit_p15_prohibition_feedback': previous['feedback'][0],
            'source_only_reuse_metadata': reserved, 'files': files,
            'binding': {'code_hash': digest(files), 'config_hash': digest(previous['config'])},
            'protocol_sha256': sha(PROTOCOL), 'syntax_schema': SYNTAX,
            'DEV_text_or_labels_loaded': False, 'goal_complete': False}
    assert strict_output_schema_issues(SYNTAX) == strict_output_schema_issues(CODE) == []
    immutable_json(STAGE / 'seal.json', seal)
    for p in paths:
        dest = STAGE / 'frozen' / p;dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((ROOT / p).read_bytes())
    return seal


def ledger(s):
    return MethodLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        binding=s['binding'], sources=s['sources'], authorization_hash=s['protocol_sha256'],
        question='Can existing TRAIN source feedback learn type-guarded modal/predicate composition that acquires conduct/consequence nodes from real non-normative source syntax, compared with an independently induced ordinary programme? No DEV/TEST, new pairs or source-ID prediction lookup.')


def frozen(s):
    for p, h in s['files'].items():
        assert sha(ROOT / p) == h, p
    assert sha(PROTOCOL) == s['protocol_sha256']


def acquire(key):
    output = STAGE / (key + '_syntax.json')
    if output.exists():
        print(json.dumps({'existing': True, 'no_redispatch': True, 'key': key}));return
    s = prepare();frozen(s);unit = next(u for u in s['units'] if u['key'] == key)
    system = (
        'Extract compact predicate structure from the exact source unit. This is syntax/semantic-role acquisition, '
        'not a permission/prohibition/obligation classifier. Do not supply normative effect labels or answer a legal question. '
        'Include each predicate governing disclosure, return/destruction or retention and each such conduct predicate, '
        'including an embedded condition, lexical governor, exception, coordination and source references. '
        'predicate_quote is the exact lexical head word, excluding auxiliaries and negation. '
        'modal_quote is the exact modal auxiliary word such as shall or may, or empty if absent. '
        'negation_quote is an exact local negation cue, or empty; it belongs to the predicate actually negated, '
        'not automatically every embedded conduct. actor_quote/object_quote identify the actual role arguments '
        'as exact SOURCE substrings. Include information ownership and original copy quantifiers when stated. '
        'Do not invent an antecedent; unresolved roles are empty. All nonempty quotes must occur literally in this unit. '
        'Edges go from governing predicate to child. A condition is not a complement. For an archival exception '
        'the main obligation predicate is parent and retention is the exception child. Relation quote preserves '
        'the whole relevant qualifying clause including its marker, not just if/except. '
        'A reference such as exceptions provided elsewhere is reference, not a new permission. '
        'Do not create alternative false parses to populate a quota. Use unique local node IDs and omit nonexistent edges. '
        'Return only the schema object with nodes and edges. No native queries, answers or source feedback are supplied.')
    client = MethodExecutor(ledger(s), STAGE, s['config']['executor']);client.readiness()
    wire = client.generate(RUN + ':syntax:' + key, source=unit['source'], purpose='method_train_synthesis',
        messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': unit['text']}],
        thinking=False, schema=SYNTAX)
    result = {'key': key, 'unit': unit, 'wire': wire, 'new_physical_requests': 1,
              'normative_semantics_not_supplied_by_reader': True, 'core_success_not_claimed': True}
    try:
        syntax = json.loads(wire['content']);jsonschema.validate(syntax, SYNTAX)
        adaptations = []
        for n in syntax['nodes']:
            for field in ['predicate_quote', 'modal_quote', 'negation_quote', 'actor_quote', 'object_quote']:
                value, changed = literal(n[field], unit['text'])
                if changed:adaptations.append({'node': n['id'], 'field': field, 'original': n[field], 'literal': value})
                n[field] = value
        for e in syntax['edges']:
            value, changed = literal(e['quote'], unit['text'])
            if changed:adaptations.append({'edge': e, 'original': e['quote'], 'literal': value})
            e['quote'] = value
        result.update(accepted=True, acquired=enrich({**unit, 'syntax': syntax}),
                      literal_only_adaptations=adaptations)
    except Exception as e:
        result.update(accepted=False, error=type(e).__name__ + ': ' + str(e))
    immutable_json(output, result)
    print(json.dumps({'key': key, 'accepted': result['accepted'], 'error': result.get('error'),
                      'nodes': len(result.get('acquired', {}).get('syntax', {}).get('nodes', [])),
                      'goal_complete': False}), flush=True)


def learn():
    s = prepare();frozen(s);rows = [read(STAGE / (k + '_syntax.json')) for k in ['p15', 'p20', 'p111']]
    if not all(r['accepted'] for r in rows):
        raise ValueError('Localize rejected real syntax before any changed retry; no implicit fill')
    units = [r['acquired'] for r in rows];library = fit(units)
    immutable_json(STAGE / 'learned_semantic_library.json', library)
    if library['accepted']:
        outputs = {u['key']: validate_outputs(u, predict(u, library)) for u in units}
        immutable_json(STAGE / 'TRAIN_semantic_replay.json', score_outputs(outputs))
    print(json.dumps({'accepted': library['accepted'], 'compatible_programs': len(library['states']),
                      'programs_checked': library['programs_checked'], 'new_model_calls': 0, 'goal_complete': False}))


def ordinary():
    out = STAGE / 'independent_ordinary_learned.json'
    if out.exists():
        print(json.dumps({'existing': True, 'no_redispatch': True}));return
    s = prepare();frozen(s)
    lib = read(STAGE / 'learned_semantic_library.json')
    assert lib['accepted'], 'No expensive control generation before actual prototype availability'
    units = [read(STAGE / (k + '_syntax.json'))['acquired'] for k in ['p15', 'p20', 'p111']]
    system = (
        'Independently learn an ordinary reusable source-to-norm programme from these TRAIN originals, native '
        'annotations and source feedback. You may use source syntax, plain source text, regex, a dictionary, '
        'typed composition, version-space search or any permitted ordinary Python. No candidate learned tables '
        'or predictions are supplied. Define infer(document,query); document is a dict {text,syntax}; query is null. '
        'Return {frames:[...]} for source conduct heads. Each frame has predicate_id,governor_id,action '
        '(share/return_or_destroy/retain), formula (A or nested unary [P/O/F/BREACH/OTHER/NOT,operand], '
        'or null for unresolved), source_predicate_quotes (exact strings), conditions (exact strings), '
        'references (exact strings), actor_quote,object_quote,information_anchor (exact strings, empty if unresolved), '
        'exception_target (predicate ID or null). You may add diagnostics. '
        'Include actual normative heads and distinguish negated breach consequence from a prohibition or grant '
        'of embedded disclosure. Unknown acquisition must not become NotMentioned. F(A), O(NOT(A)) and '
        'NOT(P(A)) are not scored as a manufactured superiority over one another here. '
        'Common public semantics/types and observed source syntax are available equally to you. Syntax has no '
        'normative effect labels. Use the same explicit actor/information binding provenance where useful; '
        'such/all-copy/one-copy are not automatically identical physical collections. '
        'All quotes emitted at runtime must occur in the current document.text, not a stored TRAIN document. '
        'No source ID, company-name lookup, answer cache or full training-document constants. '
        'Available builtins: set,frozenset,list,dict,tuple,str,int,float,bool,len,sorted,enumerate,zip,any,all,min,max,sum,isinstance,range,abs,next,reversed. '
        'Host supplies re with compile,search,match,fullmatch,findall,finditer,sub,split,escape and I,S,M flags. '
        'Ordinary functions, loops, comprehensions, collections and literal module constants are allowed. '
        'No imports,classes,lambdas,exceptions,annotations,defaults,decorators,global/nonlocal,tools,files,network or environment. '
        'Return JSON code,learned_operations,limitations. Your programme may implement the same typed logic or '
        'a more general alternative; you are not restricted to a weak lexical classifier.')
    user = json.dumps({'originals_and_native_TRAIN': s['training_documents_and_native_supervision'],
        'syntax_TRAIN': units, 'source_feedback': s['source_feedback'],
        'earlier_explicit_p15_feedback': s['older_explicit_p15_prohibition_feedback'],
        'public_conduct_lexical_catalogue': STEMS}, ensure_ascii=False)
    wire = MethodTeacher(ledger(s), STAGE, s['config']['teacher']).summarize(RUN + ':ordinary',
        source_ids=[m['source'] for m in s['training_documents_and_native_supervision']],
        system_prompt=system, user_prompt=user, output_schema=CODE)
    result = {'wire': wire, 'same_raw_text_supervision_and_syntax': True, 'fresh_independent_ordinary_acquisition': True,
              'goal_complete': False}
    try:
        code = wire['value']['code'];check(code);outputs = {}
        for u in units:
            value = run(code, {'text': u['text'], 'syntax': u['syntax']}, [None])[0]
            if 'error' in value:raise ValueError(str(value))
            outputs[u['key']] = validate_outputs(u, value['value'])
        result.update(accepted=True, code=code, TRAIN=score_outputs(outputs))
    except Exception as e:result.update(accepted=False, error=type(e).__name__ + ': ' + str(e))
    immutable_json(out, result)
    print(json.dumps({'accepted': result['accepted'], 'error': result.get('error'),
                      'checks': result.get('TRAIN', {}).get('checks'), 'goal_complete': False}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('action');a = p.parse_args()
    if a.action == 'prepare':prepare();print(json.dumps({'prepared': True, 'new_model_calls': 0}))
    elif a.action == 'learn':learn()
    elif a.action == 'ordinary':ordinary()
    else:acquire(a.action)
