"""Source-grounded attachment updates over an already learned contract parser.

This is a finite program-repair experiment, not a claim of full legal parsing.
The host knows no linguistic trigger for any semantic head. Such triggers must
come from learned productions or an independently learned ordinary program.
"""
import itertools
import json
from copy import deepcopy

from .contract_compiler_runtime import run, scope_answer

KINDS = {'permission', 'prohibition', 'obligation', 'no_breach', 'reference_only'}
ACTIONS = {'share', 'return_or_destroy', 'retain'}


def production_code(productions):
    """Compile named-capture productions to the same bounded Python runtime."""
    return 'PRODUCTIONS = ' + repr(productions) + '''
def infer(document, query):
    records = []
    for production in PRODUCTIONS:
        for match in re.finditer(production['pattern'], document, re.I | re.S):
            groups = match.groupdict()
            anchor = groups.get('anchor')
            head = groups.get('head')
            behavior = groups.get('behavior')
            if not anchor or not head or not behavior:
                continue
            records.append({'start': match.start('anchor'), 'end': match.end('anchor'),
                'quote': anchor, 'head': head, 'behavior': behavior,
                'kind': production['kind'], 'action': production['action'],
                'conditions': [groups[name] for name in production['condition_groups'] if groups.get(name)],
                'references': [groups[name] for name in production['reference_groups'] if groups.get(name)],
                'clear_overrides': production['clear_overrides']})
    return records
'''


def annotations(code, document):
    entry = run(code, document, [None])[0]
    if 'error' in entry:
        raise ValueError(entry['error_type'] + ': ' + entry['error'])
    records = entry['value']
    if not isinstance(records, list):
        raise ValueError('Attachment program must return a list')
    unique = []
    for record in records:
        expected = {'start', 'end', 'quote', 'head', 'behavior', 'kind', 'action',
                    'conditions', 'references', 'clear_overrides'}
        if not isinstance(record, dict) or set(record) != expected:
            raise ValueError('Unexpected attachment fields')
        start, end = record['start'], record['end']
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(document):
            raise ValueError('Invalid attachment span')
        quote = record['quote']
        if document[start:end] != quote:
            raise ValueError('Attachment quote differs from its source span')
        if record['kind'] not in KINDS or record['action'] not in ACTIONS:
            raise ValueError('Unsupported attachment kind/action')
        if type(record['clear_overrides']) is not bool:
            raise ValueError('Override decision must be explicit')
        for key in ['conditions', 'references']:
            if not isinstance(record[key], list) or any(not isinstance(x, str) or not x or x not in quote for x in record[key]):
                raise ValueError('A qualification is not captured from its own anchor')
        if any(not isinstance(record[k], str) or not record[k] or record[k] not in quote for k in ['head', 'behavior']):
            raise ValueError('Normative head/behavior must be captured from its own anchor')
        if record not in unique:
            unique.append(record)
    return unique


def rewrite(graph, records):
    """Reattach only already acquired claims with a unique source owner.

    No new conduct norm, recipient or trigger is manufactured. Non-conduct
    consequences remain explicit residuals; they do not become permissions or
    native NotMentioned. Every removed/rewritten original is saved in the trace.
    """
    updated = deepcopy(graph)
    changes, residuals, kept = [], [], []
    removed = set()
    for rule in updated['rules']:
        matches = [a for a in records if a['action'] == rule['action'] and
                   any(a['quote'] in q for q in rule['source_quotes'])]
        semantics = {(a['kind'], tuple(a['conditions']), tuple(a['references']), a['clear_overrides']) for a in matches}
        if not matches:
            kept.append(rule)
            continue
        original = deepcopy(rule)
        if len(semantics) != 1:
            residuals.append({'reason': 'ambiguous_attachment', 'original_rule': original, 'attachments': matches})
            removed.add(rule['id'])
            changes.append({'original_rule': original, 'replacement': None, 'reason': 'ambiguous_attachment'})
            continue
        a = matches[0]
        if a['kind'] in {'no_breach', 'reference_only'}:
            residuals.append({'reason': 'non_conduct_head_requires_distinct_projection',
                              'original_rule': original, 'attachment': a})
            removed.add(rule['id'])
            changes.append({'original_rule': original, 'replacement': None, 'attachment': a})
            continue
        rule['effect'] = a['kind']
        rule['conditions'] = a['conditions'] + a['references']
        if a['clear_overrides']:
            rule['overrides'] = []
        kept.append(rule)
        if original != rule:
            changes.append({'original_rule': original, 'replacement': deepcopy(rule), 'attachment': a})
    # A removed claim is not a valid target. Removing its incident priority
    # edges preserves graph integrity without constructing a replacement norm.
    for rule in kept:
        invalid = sorted(set(rule['overrides']) & removed)
        if invalid:
            changes.append({'rule_id': rule['id'], 'removed_edges_to_removed_claims': invalid})
            rule['overrides'] = [x for x in rule['overrides'] if x not in removed]
    updated['rules'] = kept
    if residuals:
        updated['unresolved'].append('Unprojected attachment residual; no absence conclusion from dropped conduct claim')
    return {'graph': updated, 'changes': changes, 'residuals': residuals, 'attachments': records}


def apply(code, document, graph):
    return rewrite(graph, annotations(code, document))


def assess(code, documents, feedback):
    """Visible TRAIN constraints only; no DEV or held-out source access."""
    results, states = [], {}
    for material in documents:
        key = material['key']
        try:
            state = apply(code, material['document'], material['graph'])
            states[key] = state
            for example in material.get('examples', []):
                value = scope_answer(state['graph'], material['document'], example['id'])
                results.append({'constraint': key + ':' + example['id'],
                                'passed': value['answer'] == example['answer'], 'execution': value})
        except Exception as e:
            results.append({'constraint': key + ':execution', 'passed': False,
                            'error': type(e).__name__ + ': ' + str(e)})
    for f in feedback:
        state = states.get(f['key'])
        if state is None:
            results.append({'constraint': f['id'], 'passed': False, 'error': 'No execution'})
            continue
        matching = [a for a in state['attachments'] if f['anchor_contains'] in a['quote'] and
                    a['kind'] == f['kind'] and a['action'] == f['action']]
        # Head and condition ownership have positive as well as negative
        # constraints: returning no annotations/deleting all norms cannot pass.
        good = [a for a in matching if f['head_contains'] in a['head'] and
                f['behavior_contains'] in a['behavior'] and
                (not f['reference_contains'] or any(f['reference_contains'] in x for x in a['references'])) and
                (not f['condition_contains'] or any(f['condition_contains'] in x for x in a['conditions']))]
        bad = [r['id'] for r in state['graph']['rules'] if r['action'] == f['action'] and
               r['effect'] in f['forbidden_effects_on_anchor'] and
               any(f['anchor_contains'] in q for q in r['source_quotes'])]
        results.append({'constraint': f['id'], 'passed': bool(good) and not bad,
                        'positive_attachment_witnesses': good, 'remaining_bad_claim_ids': bad})
    return {'constraints': results, 'passed': bool(results) and all(x['passed'] for x in results), 'states': states}


def select(productions, documents, feedback):
    """Exact minimum consistent update in a finite learned hypothesis bank.

    Lexicographic objective: number of productions, total serialized bytes,
    canonical IDs. No model reruns or evaluation-driven hyperparameter choice.
    This is a finite consistency search, not a universal semantic proof/CEGIS
    verifier. It does not see the fixed source-only reuse documents or DEV.
    """
    if not productions or len(productions) > 8 or len({p['id'] for p in productions}) != len(productions):
        raise ValueError('Expected 1..8 uniquely named proposed productions')
    candidates = []
    for n in range(len(productions) + 1):
        for subset in itertools.combinations(productions, n):
            serial = json.dumps(list(subset), sort_keys=True)
            candidates.append(((n, len(serial.encode()), tuple(sorted(p['id'] for p in subset))), list(subset)))
    trace = []
    for objective, subset in sorted(candidates, key=lambda x: x[0]):
        code = production_code(subset)
        result = assess(code, documents, feedback)
        trace.append({'ids': [p['id'] for p in subset], 'objective': objective,
                      'passed': result['passed'], 'constraints': result['constraints']})
        if result['passed']:
            return {'accepted': True, 'productions': subset, 'code': code, 'training': result,
                    'selection_trace': trace, 'universal_semantic_proof': False}
    return {'accepted': False, 'productions': [], 'code': None, 'selection_trace': trace,
            'reason': 'No proposed combination satisfies visible source and native TRAIN constraints'}
