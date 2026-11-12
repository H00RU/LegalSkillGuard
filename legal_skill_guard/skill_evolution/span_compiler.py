"""Learn reusable text-to-record productions from aligned source examples.

No legal rule or native decision is implemented by this module. Teachers learn
the lexicons, source annotations and consequence procedure. The host induces
and compresses span transducers, checking native feedback before each merge.
"""
import ast
from copy import deepcopy
from difflib import SequenceMatcher
from functools import lru_cache
import json
from pathlib import Path
import re
import subprocess
import sys

import jsonschema
import regex

from .native import record_schema
from .objects import digest
from .source_schema import LABELS, TASKS

PAIR = record_schema({'name': {'type': 'string'}, 'value': {'type': 'string'}})
SLOT = record_schema({'name': {'type': 'string'}, 'quote': {'type': 'string'},
    'lexicon': {'type': ['string', 'null']}})
SEED = record_schema({'source': {'type': 'string'}, 'quote': {'type': 'string', 'maxLength': 1800},
    'kind': {'type': 'string'}, 'slots': {'type': 'array', 'maxItems': 5, 'items': SLOT},
    'constants': {'type': 'array', 'maxItems': 8, 'items': PAIR}})
LEXICON = record_schema({'name': {'type': 'string'}, 'entries': {'type': 'array', 'items':
    record_schema({'symbol': {'type': 'string'}, 'forms': {'type': 'array', 'items': {'type': 'string'}}})}})
SCHEMA = record_schema({'kind': {'type': 'string', 'enum': ['compiler', 'program', 'text_policy']},
    'rationale': {'type': 'string'}, 'protected_tokens': {'type': 'array', 'items': {'type': 'string'}},
    'glue_words': {'type': 'array', 'items': {'type': 'string'}},
    'lexicons': {'type': 'array', 'maxItems': 6, 'items': LEXICON},
    'seeds': {'type': 'array', 'maxItems': 12, 'items': SEED},
    'procedure': {'type': ['string', 'null']}, 'policy_text': {'type': ['string', 'null']}})
RESULT_SCHEMA = record_schema({'handled': {'type': 'boolean'},
    'answer': {'type': 'string', 'enum': list(LABELS)},
    'used_records': {'type': 'array', 'uniqueItems': True, 'items': {'type': 'integer', 'minimum': 0}}})
METHODS = {'lower', 'upper', 'casefold', 'strip', 'lstrip', 'rstrip', 'split', 'rsplit',
    'splitlines', 'replace', 'find', 'index', 'startswith', 'endswith', 'join', 'count',
    'get', 'keys', 'values', 'items', 'append', 'extend', 'add', 'update', 'pop',
    'compile', 'search', 'match', 'fullmatch', 'findall', 'finditer', 'escape', 'sub', 'group',
    'groups', 'groupdict', 'start', 'end', 'span', 'I', 'IGNORECASE', 'S', 'DOTALL',
    'M', 'MULTILINE', 'UNICODE', 'isalnum', 'isalpha', 'isdigit', 'intersection', 'rfind'}
CALLS = {'min', 'max', 'sum', 'len', 'abs', 'round', 'sorted', 'all', 'any', 'int',
    'float', 'bool', 'str', 'list', 'dict', 'set', 'tuple', 'range', 'enumerate',
    'zip', 'isinstance', 'ValueError', 'KeyError', 'TypeError', 'bind_scope'}


def validate_procedure(code, *, allow_helpers=False):
    tree = ast.parse(code)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if not allow_helpers and (len(tree.body) != 1 or len(functions) != 1):
        raise ValueError('One apply(inputs, premises) function required')
    if len(functions) != len(tree.body) or sum(f.name == 'apply' for f in functions) != 1:
        raise ValueError('Pure top-level functions with one apply entry required')
    if len({f.name for f in functions}) != len(functions):raise ValueError('Duplicate source helper')
    f = next(f for f in functions if f.name == 'apply')
    if (f.decorator_list or f.args.vararg or f.args.kwarg or f.args.kwonlyargs
            or f.args.defaults or [a.arg for a in f.args.args] != ['inputs', 'premises']):
        raise ValueError('Explicit JSON input bindings required')
    forbidden = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.ClassDef,
        ast.Lambda, ast.With, ast.AsyncFunctionDef)
    if any(isinstance(n, forbidden) for n in ast.walk(tree)):raise ValueError('Effectful code forbidden')
    if sum(isinstance(n, ast.FunctionDef) for n in ast.walk(tree)) != len(functions):raise ValueError('No nested functions')
    if any(f.decorator_list for f in functions):raise ValueError('No function decorators')
    local_calls = {f.name for f in functions} if allow_helpers else set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id.startswith('__'):raise ValueError('No introspection')
        if isinstance(n, ast.Attribute) and n.attr not in METHODS:raise ValueError('Unsupported attribute: ' + n.attr)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id not in CALLS | local_calls:
            raise ValueError('Unsupported call: ' + n.func.id)
    graph = {f.name: {n.func.id for n in ast.walk(f) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name) and n.func.id in local_calls} for f in functions}
    visited = set()
    def visit(name, stack):
        if name in stack:raise ValueError('Recursive source helper')
        if name in visited:return
        for target in graph[name]:visit(target, stack | {name})
        visited.add(name)
    for name in graph:visit(name, set())
    return code


def execution_source_spans(spans):
    """Canonical whitespace for learned readers; retain raw provenance outside.

    Dataset span boundaries, IDs and character offsets are unchanged. Only the
    execution view of each span's text is folded, so a physical newline cannot
    split an otherwise identical phrase when the reader joins adjacent spans.
    """
    return [{**span, 'text': ' '.join(span['text'].split())} for span in spans]


def execution_source_units(text, spans):
    """Join physical fragments, preserving every original evidence identity.

    This is a common execution view, not a learned legal scope classifier.
    Sentence/clause punctuation closes a unit; an omitted nonwhite gap or a
    field change also closes it. Generated witnesses cite unit anchors and are
    expanded back to the original spans before semantic checks or scoring.
    """
    units, supports, pending = [], {}, []
    def flush():
        if pending:
            first, last = pending[0], pending[-1]
            units.append({**first, 'end': last['end'],
                          'text': ' '.join(text[first['start']:last['end']].split())})
            supports[first['id']] = [s['id'] for s in pending]
            pending.clear()
    for span in spans:
        if span['field'] != 'source_text':
            raise ValueError('Execution units require source material only')
        if not 0 <= span['start'] < span['end'] <= len(text):
            raise ValueError('Execution unit lies outside the current source')
        if pending and (pending[-1]['end'] > span['start']
                        or text[pending[-1]['end']:span['start']].strip()):
            flush()
        pending.append(span)
        if re.search(r'[.;:!?][\"”\')]*(?:\s+(?:and|or))?$', span['text'].strip(), re.I):
            flush()
    flush()
    return units, supports


def expand_unit_support(ids, supports):
    if any(i not in supports for i in ids):
        raise ValueError('Generated witness cites an absent current source unit')
    return sorted({j for i in ids for j in supports[i]})


def execute_json(code, inputs, premises, *, allow_helpers=False, trace=False):
    validate_procedure(code, allow_helpers=allow_helpers)
    out = subprocess.run([sys.executable, '-I', '-S', str(Path(__file__).with_name('span_compiler_worker.py'))],
        input=json.dumps({'procedure': code, 'inputs': inputs, 'premises': premises, 'trace': trace}, ensure_ascii=False),
        capture_output=True, text=True, timeout=4, cwd='/tmp', env={'LANG': 'C.UTF-8'}, close_fds=True)
    if out.returncode:raise ValueError('Learned source procedure failed: ' + out.stderr[-1000:])
    return json.loads(out.stdout)


def execute(code, inputs, premises, *, allow_helpers=False):
    value = execute_json(code, inputs, premises, allow_helpers=allow_helpers)
    jsonschema.validate(value, RESULT_SCHEMA)
    if 'records' in premises:
        if any(i >= len(premises['records']) for i in value['used_records']):raise ValueError('Missing record proof reference')
        if value['handled'] and not value['used_records']:raise ValueError('No grounded record for handled result')
    return value


def token_spans(text):return [(m.group(), m.start(), m.end()) for m in re.finditer(r'\w+|[^\w\s]', text)]


def occurrences(text, quote):
    """Only whitespace changes are ignored; words, case and punctuation agree."""
    source, target = token_spans(text), token_spans(quote)
    tokens = [t[0] for t in target]
    if not tokens:raise ValueError('Empty source quote')
    hits = [(source[i][1], source[i + len(tokens) - 1][2]) for i in range(len(source) - len(tokens) + 1)
            if [t[0] for t in source[i:i + len(tokens)]] == tokens]
    return hits


def locate(text, quote):
    hits = occurrences(text, quote)
    if len(hits) != 1:raise ValueError('Source quote requires one exact token occurrence')
    return hits[0]


def align_slots(text, slots):
    """Resolve repeats only when joint nonoverlap has one unique solution.

    No slot order, legal role, target label or nearest-match heuristic is
    inferred. A genuinely ambiguous alignment remains rejected.
    """
    choices = [occurrences(text, s['quote']) for s in slots]
    if any(not c for c in choices):raise ValueError('Source slot has no exact token occurrence')
    solutions = []
    def visit(index, chosen):
        if len(solutions) > 1:return
        if index == len(slots):solutions.append(list(chosen));return
        for a, b in choices[index]:
            if any(a < d and c < b for c, d in chosen):continue
            visit(index + 1, chosen + [(a, b)])
    visit(0, [])
    if len(solutions) != 1:raise ValueError('Source slots have no unique joint nonoverlapping alignment')
    return sorted([(a, b, slot) for (a, b), slot in zip(solutions[0], slots)], key=lambda x: x[0])


def protected_signature(tokens, protected):
    words = [x.lower() if x is not None else None for x in tokens];found = []
    for phrase in protected:
        target = [x[0].lower() for x in token_spans(phrase)]
        if not target:continue
        for i in range(len(words) - len(target) + 1):
            if words[i:i + len(target)] == target:found.append((i, 'phrase:' + ' '.join(target)))
    found += [(i, 'number:' + x) for i, x in enumerate(words) if x is not None and x.isnumeric()]
    return [name for _, name in sorted(found)]


def token_regex(tokens, protected=()):
    protected_forms = [r'\b' + r'\s+'.join(re.escape(t[0]) for t in token_spans(s)) + r'\b' for s in protected]
    stop = '|'.join([r'\d', *protected_forms])
    gap = r'(?:(?!(?:' + stop + r'))[\s\S]){0,160}?'
    pieces = []
    for token in tokens:
        if token is None:pieces.append(gap)
        else:pieces.append((r'\b' + re.escape(token) + r'\b') if re.fullmatch(r'\w+', token) else re.escape(token))
    return r'\s*'.join(pieces)


def pattern(rule):
    parts = []
    for i, literal in enumerate(rule['literals']):
        parts.append(token_regex(literal, rule['protected_tokens']))
        if i < len(rule['slots']):
            slot = rule['slots'][i]
            # Untyped raw fields retain their demonstrated surface forms.
            # They cannot swallow arbitrary paragraphs or absorb the next
            # typed role capture. New forms require an actual learned merge.
            body = ('(?:' + '|'.join(token_regex([t[0] for t in token_spans(form)]) for form in slot['raw_forms']) + ')'
                if slot['lexicon'] is None else r'[\s\S]{1,' + str(slot['capture_max']) + r'}?')
            parts.append(r'(?P<' + slot['name'] + '>' + body + ')')
    return re.compile(r'\s*'.join(parts), re.IGNORECASE)


@lru_cache(maxsize=2048)
def source_matches(expression, text):
    # Bound real backtracking and reuse unchanged source/rule matches while
    # evaluating grammar edits. A timeout is unresolved, never a negative fact.
    compiled = regex.compile(expression, regex.IGNORECASE | regex.VERSION0)
    try:return tuple((m.start(), m.end(), m.groupdict()) for m in compiled.finditer(text, timeout=2.0))
    except TimeoutError as error:raise ValueError('Source grammar match timed out; interpretation unresolved') from error


def compile_annotations(spec, materials):
    jsonschema.validate(spec, SCHEMA)
    if spec['kind'] == 'text_policy':
        if not spec['policy_text'] or spec['procedure'] is not None or spec['seeds'] or spec['lexicons']:
            raise ValueError('One explicit learned text policy')
        return []
    validate_procedure(spec['procedure'])
    if spec['policy_text'] is not None:raise ValueError('No hidden alternate policy')
    if spec['kind'] == 'program':
        if spec['seeds'] or spec['lexicons']:raise ValueError('A free raw program has no hidden compiler acquisition')
        return []
    if not spec['seeds']:raise ValueError('The compiler needs acquired source examples')
    lexicons = {x['name']: x for x in spec['lexicons']}
    if len(lexicons) != len(spec['lexicons']):raise ValueError('Duplicate lexicon')
    for lexicon in lexicons.values():
        if len({x['symbol'] for x in lexicon['entries']}) != len(lexicon['entries']):raise ValueError('Duplicate symbol')
        for entry in lexicon['entries']:
            if entry['symbol'] in LABELS or not entry['forms']:raise ValueError('Lexical concepts, not labels')
            for form in entry['forms']:
                if not form.strip() or not any(re.search(r'(?<!\w)' + re.escape(form) + r'(?!\w)', text, re.I)
                        for text in materials.values()):raise ValueError('Lexical form not acquired from TRAIN: ' + form)
    rules = []
    for seed in spec['seeds']:
        if seed['source'] not in materials:raise ValueError('Non-TRAIN annotation')
        begin, end = locate(materials[seed['source']], seed['quote'])
        text = materials[seed['source']][begin:end]
        for slot in seed['slots']:
            if not slot['name'].isidentifier() or slot['name'].startswith('_'):raise ValueError('Literal slot identifier required')
            if slot['lexicon'] is not None and slot['lexicon'] not in lexicons:raise ValueError('Unknown lexical type')
        slots = align_slots(text, seed['slots'])
        names = [s[2]['name'] for s in slots]
        constants = {c['name']: c['value'] for c in seed['constants']}
        if len(set(names)) != len(names) or set(names) & set(constants) or len(constants) != len(seed['constants']):raise ValueError('Duplicate binding')
        if seed['kind'] in LABELS or any(v in LABELS for v in constants.values()):raise ValueError('No source answer labels')
        literals, cursor = [], 0
        for a, b, slot in slots:
            if a < cursor:raise ValueError('Overlapping source bindings')
            literals.append([t[0] for t in token_spans(text[cursor:a])]);cursor = b
        literals.append([t[0] for t in token_spans(text[cursor:])])
        if slots and not literals[-1]:raise ValueError('The last source capture requires literal right context')
        if sum(len(t) for t in literals) < 2:raise ValueError('Source context cannot consist only of holes')
        rule = {'kind': seed['kind'], 'constants': constants,
            'slots': [{**s, 'capture_max': max(500, b - a + 4), 'raw_forms': [text[a:b]] if s['lexicon'] is None else []} for a, b, s in slots],
            'literals': literals, 'seed_sources': [seed['source']], 'seed_quotes': [text],
            'protected_tokens': sorted(set(spec['protected_tokens'])), 'merged_from': []}
        rule['id'] = digest(rule);pattern(rule);rules.append(rule)
    if len({r['id'] for r in rules}) != len(rules):raise ValueError('Duplicate source annotations')
    return rules


def compile_grounded_examples(spec, materials):
    """Keep independently grounded examples; reject ambiguous units explicitly.

    Removing an invalid annotation cannot justify a legal absence. Missing
    productions remain missing; the learned procedure must still use fallback.
    """
    if spec['kind'] != 'compiler':return compile_annotations(spec, materials), []
    # Validate the common learned lexicon/program independently of any seed.
    jsonschema.validate(spec, SCHEMA);validate_procedure(spec['procedure'])
    rules, rejected = [], []
    for index, seed in enumerate(spec['seeds']):
        unit = {**spec, 'seeds': [seed]}
        try:rules.extend(compile_annotations(unit, materials))
        except ValueError as error:rejected.append({'seed_index': index, 'source': seed['source'], 'error': str(error)})
    if not rules:raise ValueError('No grounded source production remains: ' + str(rejected))
    return rules, rejected


def recognize_terms(text, lexicon, glue):
    hits = []
    for entry in lexicon['entries']:
        for form in entry['forms']:
            hits += [(m.start(), m.end(), entry['symbol']) for m in
                     re.finditer(r'(?<!\w)' + re.escape(form) + r'(?!\w)', text, re.I)]
    # Nested aliases may agree, but competing meanings remain unresolved.
    ambiguous = any(a < d and c < b and x != y for a, b, x in hits for c, d, y in hits)
    occupied = {i for a, b, _ in hits for i in range(a, b)}
    unresolved = [word for word, a, b in token_spans(text)
                  if re.fullmatch(r'\w+', word) and word.lower() not in glue and not all(i in occupied for i in range(a, b))]
    return {'symbols': sorted({x for _, _, x in hits}), 'complete': not unresolved and not ambiguous,
            'unresolved_surface': unresolved, 'ambiguous': ambiguous}


def parse_source(spec, rules, text):
    lexicons = {x['name']: x for x in spec['lexicons']};glue = {x.lower() for x in spec['glue_words']}
    records = []
    for rule in rules:
        for start, end, captures in source_matches(pattern(rule).pattern, text):
            values = dict(rule['constants']);surface = {};lexical = {}
            for slot in rule['slots']:
                raw = captures[slot['name']];surface[slot['name']] = raw
                if slot['lexicon'] is None:values[slot['name']] = raw
                else:
                    lex = recognize_terms(raw, lexicons[slot['lexicon']], glue)
                    lexical[slot['name']] = lex
                    # No matches is unresolved, never a known-empty role set.
                    values[slot['name']] = lex['symbols'] if lex['symbols'] else None
            record = {'kind': rule['kind'], 'values': values, 'surface': surface,
                'lexical': lexical, 'span': [start, end], 'production': rule['id']}
            if record not in records:records.append(record)
    return sorted(records, key=lambda r: (r['span'], r['production']))


def merge_rules(a, b, protected):
    if (a['kind'] != b['kind'] or a['constants'] != b['constants'] or
            [(x['name'], x['lexicon']) for x in a['slots']] != [(x['name'], x['lexicon']) for x in b['slots']]):return None
    literals = []
    for left, right in zip(a['literals'], b['literals']):
        if None in left or None in right:return None  # One finite merge pass, no unconstrained wildcard growth.
        protected_left = protected_signature(left, protected)
        protected_right = protected_signature(right, protected)
        if protected_left != protected_right:return None
        result, li, ri = [], 0, 0
        for block in SequenceMatcher(None, [x.lower() for x in left], [x.lower() for x in right], autojunk=False).get_matching_blocks():
            if block.a > li or block.b > ri:result.append(None)
            result.extend(left[block.a:block.a + block.size]);li, ri = block.a + block.size, block.b + block.size
        kept = protected_signature(result, protected)
        if kept != protected_left:return None
        literals.append(result)
    if sum(x is not None for part in literals for x in part) < 4:return None
    merged = {**deepcopy(a), 'literals': literals,
        'slots': [{**left, 'capture_max': max(left['capture_max'], right['capture_max']),
                   'raw_forms': sorted(set(left['raw_forms'] + right['raw_forms']))}
                  for left, right in zip(a['slots'], b['slots'])],
        'seed_sources': sorted(set(a['seed_sources'] + b['seed_sources'])),
        'seed_quotes': sorted(set(a['seed_quotes'] + b['seed_quotes'])), 'merged_from': [a['id'], b['id']]}
    merged['id'] = digest({k: v for k, v in merged.items() if k != 'id'})
    pattern(merged)
    return merged


def grammar_cost(rules):
    return sum(1 + sum(4 if x is None else len(x) + 1 for part in r['literals'] for x in part)
               + 8 * len(r['slots']) for r in rules)


def learn_grammar(spec, seeds, evaluate, *, native_feedback):
    """Finite typed anti-unification with whole-source feedback before commit."""
    current = deepcopy(seeds);scores = evaluate(current);history = []
    protected = {x.lower() for x in spec['protected_tokens']}
    candidates = []
    for i, a in enumerate(seeds):
        for b in seeds[i + 1:]:
            merged = merge_rules(a, b, protected)
            if merged is not None:candidates.append((a['id'], b['id'], merged))
    # Descending compression is fixed from source annotations, not probe labels.
    candidates.sort(key=lambda c: (grammar_cost([c[2]]) - grammar_cost([next(s for s in seeds if s['id'] == c[0]), next(s for s in seeds if s['id'] == c[1])]), c[2]['id']))
    for a, b, merged in candidates:
        ids = {r['id'] for r in current}
        if not {a, b} <= ids:continue
        trial = [r for r in current if r['id'] not in (a, b)] + [merged]
        if grammar_cost(trial) >= grammar_cost(current):continue
        after = evaluate(trial)
        retained = all(after[k] >= v for k, v in scores.items())
        accepted = retained or not native_feedback
        history.append({'parents': [a, b], 'merged': merged['id'], 'before': scores,
            'after': after, 'native_nonregression': retained, 'accepted': accepted,
            'cost_before': grammar_cost(current), 'cost_after': grammar_cost(trial)})
        if accepted:current, scores = trial, after
    return current, history
