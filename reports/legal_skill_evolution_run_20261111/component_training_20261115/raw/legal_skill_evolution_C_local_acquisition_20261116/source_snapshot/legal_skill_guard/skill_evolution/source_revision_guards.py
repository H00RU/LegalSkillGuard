"""Learn applicability of acquired frame updates from actual TRAIN outcomes.

The guard vocabulary comes from already acquired source-processing code. The
finite learner cannot output a fact or answer. At inference it sees current
source text only and selects the old/new producer for each complete family.
Both the method and ordinary compiler can use the same public learner.
"""
import ast
from copy import deepcopy

import clingo

from .source_frame_revision import FAMILIES


def vocabulary(programs, texts):
    candidates = set()
    for program in programs:
        for node in ast.walk(ast.parse(program)):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            phrase = node.value
            if (phrase == phrase.lower() and 6 <= len(phrase) <= 90 and len(phrase.split()) >= 2
                    and '\n' not in phrase and not any(c in phrase for c in '{}[]|_')):
                candidates.add(phrase)
    # A feature must recur across existing parent texts. This is a fixed guard
    # language bias, not extra data, a source-ID gate, or a correctness criterion.
    return [None] + sorted(p for p in candidates if sum(p in t.lower() for t in texts) >= 2)


def mask_for(policy, source_text):
    low = source_text.lower()
    return sorted(family for family, phrases in policy['guards'].items()
                  if any(phrase is None or phrase in low for phrase in phrases))


def fit(features, texts, outcomes, *, timeout_seconds=120):
    """Fit one global policy with hard existing source checks and native loss.

    outcomes[i][mask_integer] supplies actual execution correctness and source
    validity for source i. No outcome enters the frozen inference policy.
    Correctness precedes rule-count/length minimization. An unsatisfiable search
    yields no accepted policy; it never weakens a source check.
    """
    families = sorted(FAMILIES)
    assert len(texts) == len(outcomes) and features[0] is None
    assert all(set(row) == set(range(2 ** len(families))) for row in outcomes)
    lines = []
    for family, name in enumerate(families):
        lines.append(f'family({family},{2 ** family}).')
    for key, feature in enumerate(features):
        lines.append(f'feature({key},{0 if feature is None else len(feature)}).')
    for source, text in enumerate(texts):
        lines.append(f'source({source}).')
        for key, phrase in enumerate(features):
            if phrase is None or phrase in text.lower():
                lines.append(f'has({source},{key}).')
        for mask, value in outcomes[source].items():
            lines.append(f'option({source},{mask},{value["native_correct"]}).')
            if value['source_valid']:
                lines.append(f'valid({source},{mask}).')
    lines += ['{use(F,K)} :- family(F,_), feature(K,_).',
        'routed(S,F) :- source(S), has(S,K), use(F,K).',
        'mask(S,M) :- source(S), M=#sum {B,F: routed(S,F), family(F,B)}.',
        'picked(S,M) :- mask(S,M), option(S,M,_).',
        ':- picked(S,M), not valid(S,M).',
        '#maximize { C@2,S,M: picked(S,M), option(S,M,C) }.',
        '#minimize { 1@1,F,K: use(F,K) }.',
        '#minimize { L@0,F,K: use(F,K), feature(K,L) }.',
        '#show use/2.', '#show picked/2.']
    program = '\n'.join(lines)
    control = clingo.Control(['--warn=none', '--opt-mode=opt'])
    control.add('base', [], program); control.ground([('base', [])])
    best = None
    def found(model):
        nonlocal best
        best = {'symbols': [str(s) for s in model.symbols(shown=True)], 'cost': list(model.cost),
                'use': [(s.arguments[0].number, s.arguments[1].number)
                        for s in model.symbols(shown=True) if s.name == 'use']}
    with control.solve(on_model=found, async_=True) as handle:
        finished = handle.wait(timeout_seconds)
        if not finished:
            handle.cancel()
        result = handle.get()
    if best is None:
        return {'accepted': False, 'satisfiable': bool(result.satisfiable),
                'optimization_complete': finished, 'reason': 'No source-valid guard policy found',
                'asp_program': program}
    guards = {name: [] for name in families}
    for family, key in sorted(best['use']):
        guards[families[family]].append(features[key])
    policy = {'guards': guards, 'input': 'current_source_text_only',
              'no_labels_or_source_IDs_at_inference': True}
    masks = [sum(2 ** families.index(f) for f in mask_for(policy, text)) for text in texts]
    assert all(outcomes[i][mask]['source_valid'] for i, mask in enumerate(masks))
    return {'accepted': True, 'policy': policy, 'native_correct': sum(outcomes[i][m]['native_correct']
            for i, m in enumerate(masks)), 'optimization_complete': finished and bool(result.exhausted),
            'feature_vocabulary': deepcopy(features), 'source_masks': masks, 'cost': best['cost'],
            'asp_program': program, 'new_model_calls': 0}
