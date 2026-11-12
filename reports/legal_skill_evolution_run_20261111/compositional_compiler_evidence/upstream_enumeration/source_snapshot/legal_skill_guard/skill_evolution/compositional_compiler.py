"""Lossless grounded-source interface to the public NQG grammar baseline.

This is a common component, not a new research contribution.  Grammar examples
come only from acquired, unambiguously aligned source annotations.  Native task
answers are absent from the induction interface.  Unknowns stay unresolved.
"""
import base64
from dataclasses import dataclass
import re

from legal_skill_guard._vendor.nqg.model.induction import induction_utils
from legal_skill_guard._vendor.nqg.model.qcfg import qcfg_parser, qcfg_rule
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.span_compiler import (
    align_slots, compile_grounded_examples, locate, recognize_terms, token_spans)


def atom(value):
    return 'v' + base64.urlsafe_b64encode(value.encode()).decode().rstrip('=')


def unatom(value):
    if not value.startswith('v'):
        raise ValueError('Unencoded semantic atom')
    raw = value[1:]
    decoded = base64.b64decode(raw + '=' * (-len(raw) % 4), altchars=b'-_', validate=True).decode()
    if atom(decoded) != value:
        raise ValueError('Noncanonical semantic atom')
    return decoded


def source_tokens(text):
    # Encoding prevents source text such as NT_1 from becoming a nonterminal.
    # Case, words and punctuation are unchanged; whitespace alone is ignored.
    return tuple(atom(t[0]) for t in token_spans(text))


def pack(value):
    if isinstance(value, str):
        return atom(value)
    return '( ' + ' '.join(pack(v) for v in value) + ' )'


def unpack(text):
    tokens = text.split(); index = 0
    def one():
        nonlocal index
        if index >= len(tokens):
            raise ValueError('Incomplete semantic expression')
        token = tokens[index]; index += 1
        if token == '(':
            values = []
            while index < len(tokens) and tokens[index] != ')':
                values.append(one())
            if index >= len(tokens):
                raise ValueError('Unclosed semantic expression')
            index += 1
            return values
        if token == ')':
            raise ValueError('Unexpected semantic close')
        return unatom(token)
    value = one()
    if index != len(tokens):
        raise ValueError('Trailing semantic expression')
    return value


def acquired_pairs(spec, materials):
    """Full records, aligned slot values and acquired lexical aliases only."""
    rules, rejected = compile_grounded_examples(spec, materials)
    lexicons = {x['name']: x for x in spec['lexicons']}
    glue = {x.lower() for x in spec['glue_words']}
    pairs = {}; shapes = []
    def add(source, target, provenance):
        key = (' '.join(source_tokens(source)), pack(target))
        pairs.setdefault(key, []).append(provenance)
    for rule in rules:
        quote = rule['seed_quotes'][0]
        fields = [[name, value] for name, value in sorted(rule['constants'].items())]
        schema = {'kind': rule['kind'], 'constants': rule['constants'], 'slots': {}}
        for _, _, slot in align_slots(quote, rule['slots']):
            if slot['lexicon'] is None:
                target = ['raw', slot['quote']]
            else:
                result = recognize_terms(slot['quote'], lexicons[slot['lexicon']], glue)
                if not result['symbols'] or result['ambiguous']:
                    raise ValueError('An unresolved acquired lexical slot has no unambiguous role value')
                # A recognized existential is useful even when other words
                # remain unknown.  Never turn that partial set into exhaustive
                # knowledge of the recipients.
                target = ['list' if result['complete'] else 'list_partial', *result['symbols']]
            fields.append([slot['name'], target])
            schema['slots'][slot['name']] = slot['lexicon']
            add(slot['quote'], target, {'type': 'aligned_slot', 'rule': rule['id'], 'slot': slot['name']})
        add(quote, ['record', rule['kind'], *fields], {'type': 'record', 'rule': rule['id'],
            'source': rule['seed_sources'][0]})
        shapes.append(schema)
    for lexicon in spec['lexicons']:
        for entry in lexicon['entries']:
            for form in entry['forms']:
                add(form, entry['symbol'], {'type': 'acquired_alias', 'lexicon': lexicon['name']})
    return [{'source': s, 'target': t, 'provenance': p} for (s, t), p in sorted(pairs.items())], shapes, rejected


def induction_config():
    # Official GeoQuery codelength settings; all examples and all relevant
    # encoding costs are evaluated, without sampling or a parameter search.
    return induction_utils.InductionConfig(sample_size=0, max_iterations=10000,
        min_delta=0, terminal_codelength=8, non_terminal_codelength=1,
        parse_sample=0, allow_repeated_target_nts=False, seed_exact_match=True,
        balance_parens=True)


def induce(pairs):
    examples = [(p['source'], p['target']) for p in pairs]
    return sorted(induction_utils.induce_rules(examples, induction_config()))


def rule_json(rule):
    return {'source': list(rule.source), 'target': list(rule.target), 'arity': rule.arity}


def from_json(value):
    return qcfg_rule.QCFGRule(tuple(value['source']), tuple(value['target']), value['arity'])


def record_from_target(target, source, shapes, spec):
    """Decode a typed record and retain actual source bindings, never defaults."""
    obj = unpack(target)
    if not isinstance(obj, list) or len(obj) < 2 or obj[0] != 'record':
        raise ValueError('Not a complete source record')
    kind = obj[1]; values = {}; raw_slots = []; typed = {}
    for item in obj[2:]:
        if not isinstance(item, list) or len(item) != 2 or not isinstance(item[0], str) or item[0] in values:
            raise ValueError('Malformed or repeated source field')
        name, value = item
        if isinstance(value, str):
            values[name] = value
        elif isinstance(value, list) and len(value) == 2 and value[0] == 'raw' and isinstance(value[1], str):
            values[name] = value[1]; raw_slots.append({'name': name, 'quote': value[1]})
        elif isinstance(value, list) and value and value[0] in {'list', 'list_partial'} and all(isinstance(v, str) for v in value[1:]):
            if len(value) == 1 or len(set(value[1:])) != len(value[1:]):
                raise ValueError('Empty or duplicate semantic role list')
            values[name] = value[1:]; typed[name] = (value[1:], value[0] == 'list')
        else:
            raise ValueError('Unknown semantic value constructor')
    compatible = [s for s in shapes if s['kind'] == kind
        and set(values) == set(s['constants']) | set(s['slots'])
        and all(values[k] == v for k, v in s['constants'].items())
        and all((name in typed) == (lexicon is not None) for name, lexicon in s['slots'].items())]
    if not compatible:
        raise ValueError('No acquired record type supports these fields and constants')
    # Joint uniqueness prevents quietly selecting a repeated actor/object.
    aligned = align_slots(source, raw_slots)
    surface = {s['name']: source[a:b] for a, b, s in aligned}
    values.update(surface)
    lexicons = {x['name']: x for x in spec['lexicons']}
    lexical = {}
    for name, (symbols, acquired_complete) in typed.items():
        lexname = compatible[0]['slots'][name]
        known = {e['symbol']: e for e in lexicons[lexname]['entries']}
        for symbol in symbols:
            if symbol not in known or not any(
                re.search(r'(?<!\w)' + re.escape(f) + r'(?!\w)', source, re.I)
                for f in known[symbol]['forms']):
                raise ValueError('Semantic role has no acquired source witness')
        lexical[name] = {'symbols': symbols, 'complete': None if acquired_complete else False,
            'unresolved_surface': None, 'ambiguous': None,
            'proof': 'QCFG derivation; aliases present in the actual record span; exhaustiveness not inferred'}
    return {'kind': kind, 'values': values, 'surface': surface, 'lexical': lexical}


@dataclass(frozen=True)
class Node:
    target: str
    proof: tuple


def parse_window(text, rules, shapes, spec, offset=0, max_cell=512):
    """Collect record-valued chart spans, without target labels or beam choice.

    All distinct targets per cell are retained. Overflow raises an unresolved
    error; it is never a score-based or arbitrary top-k semantic decision.
    """
    spans = token_spans(text); encoded = [atom(t[0]) for t in spans]
    found = {}; failures = []
    ids = {r: digest(rule_json(r)) for r in rules}
    def node_fn(begin, end, rule, children):
        target = qcfg_rule.apply_target(rule, [c.target for c in children])
        proof = tuple(sorted({ids[rule], *(x for c in children for x in c.proof)}))
        node = Node(target, proof)
        if target.startswith('( ' + atom('record') + ' '):
            a, b = spans[begin][1], spans[end - 1][2]
            try:
                record = record_from_target(target, text[a:b], shapes, spec)
                key = (a, b, target)
                value = {**record, 'span': [a + offset, b + offset],
                    'production': digest({'target': target, 'proof': proof}), 'derivation': list(proof)}
                if key not in found or len(proof) < len(found[key]['derivation']):
                    found[key] = value
            except (ValueError, UnicodeError) as error:
                failures.append({'span': [a + offset, b + offset], 'error': str(error)})
        return node
    def postprocess(nodes):
        unique = {}
        for node in nodes:
            if node.target not in unique or (len(node.proof), node.proof) < (len(unique[node.target].proof), unique[node.target].proof):
                unique[node.target] = node
        if len(unique) > max_cell:
            raise ValueError('Ambiguous grammar chart exceeded resource bound; unresolved')
        return [unique[k] for k in sorted(unique)]
    qcfg_parser.parse(encoded, rules, node_fn, postprocess)
    return sorted(found.values(), key=lambda r: (r['span'], r['production'])), failures


def parse_source(text, rules, shapes, spec):
    # Paragraphs preserve actual source characters and clause punctuation.
    # No evidence annotation, question, task label or learned keyword filters
    # the input. Both adjacent paragraphs are included for split clauses.
    units = [(m.start(), m.end()) for m in re.finditer(r'[^\n]+(?:\n|$)', text) if m.group().strip()]
    windows = list(units) + [(a, d) for (a, _), (_, d) in zip(units, units[1:])]
    found = {}; errors = []
    for a, b in windows:
        rows, rejected = parse_window(text[a:b], rules, shapes, spec, offset=a)
        errors.extend(rejected)
        for row in rows:
            key = (tuple(row['span']), digest({'kind': row['kind'], 'values': row['values']}))
            found[key] = row
    # Different semantic values on overlapping equal spans are unresolved;
    # never union incompatible parses into a single legal fact set.
    by_span = {}
    for row in found.values():
        by_span.setdefault(tuple(row['span']), []).append(row)
    ambiguous = {span for span, rows in by_span.items() if len(rows) > 1}
    if ambiguous:
        raise ValueError('Distinct semantic records on the same source span: ' + str(sorted(ambiguous)))
    return sorted(found.values(), key=lambda r: (r['span'], r['production'])), errors
