"""Compare linked disposal triggers on sealed ContractNLI TRAIN and DEV."""

import json
import re
from collections import Counter
from pathlib import Path
from statistics import mean

from experiments import convergence_revision5_cni_compose_scope as composed
from experiments import convergence_revision5_cni_disposition_literal as literal
from experiments import convergence_revision5_cni_disposition_scope as legacy
from experiments import convergence_revision5_cni_reverse_engineering as archive
from experiments import convergence_revision5_cni_trigger_coverage as reviewed
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha
from experiments.convergence_revision5_diversity_formal import ledger_status
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision5_cni_disposition_events_20261119'
POINTER = HANDOFF / 'revision5_cni_disposition_events_current.json'
TASK = legacy.TASK
E, N = 'Entailment', 'NotMentioned'
OBJECT = re.compile(r'\b(?:information|evaluation material|confidential data|documents?|material[s]?|copies|files|records?)\b', re.I)
ACTION = re.compile(r'\b(?:return(?:ed)?|destroy(?:ed|s)?|eras(?:e|ed)|delet(?:e|ed)|deliver(?:ed)?)\b', re.I)
END = re.compile(
    r'\b(?:at the end of (?:this|the) (?:confidentiality )?agreement|'
    r'upon termination of (?:my )?(?:service with|employment/affiliation/association with)|'
    r'upon termination of service)\b', re.I)
END_CUE = re.compile(r'\b(?:terminat\w*|expir\w*|end of|completion of|cessation|withdr\w*|not to proceed)\b', re.I)
REQUEST = re.compile(
    r'\b(?:upon |on |at |after |of |receipt of |following )'
    r'(?:(?:a |the |any |such |our |your |written |prior |its |that party[’\']s |discloser[’\']s |'
    r'disclosing party[’\']s |the disclosing party[’\']s |company[’\']s )+)?'
    r'(?:(?:written )?(?:request|demand|instruction))\b|'
    r'\bif (?:so )?requested\b|\bif (?:the )?(?:disclosing party|discloser) so requests\b', re.I)
REQUEST_AT_END = re.compile(r'\bat that party[’\']s request\b', re.I)
OBLIGATION = re.compile(r'\b(?:shall|will|must|agrees? to|bound to|required to)\b', re.I)
NON_DUTY = re.compile(
    r'\b(?:is not required|shall not be required|shall not authorize|neither party is required)\b', re.I)
CERTIFIED_MAIL = re.compile(r'\breturn receipt requested\b', re.I)
CONFIRMATION = re.compile(r'\b(?:certif\w*|confirm\w*|notification|report)\b', re.I)
SIGNING = re.compile(r'\b(?:sign|execute)\b[^.;]{0,85}\breturn\b[^.;]{0,80}\b(?:this|the) (?:letter )?agreement\b', re.I)
LIST = re.compile(r'^(?:\d+(?:\.\d+)+\s+|\([a-z0-9]+\)\s+|[a-z]\)\s+)', re.I)
HEADING = re.compile(r'^(?:\d+\.\s*)?return (?:or destruction )?of [\w ]+[.]?$', re.I)
INDEPENDENT_DUTY = re.compile(
    r';|\b(?:surviv\w*|shall remain|will remain|shall continue|will continue|'
    r'shall keep|will keep|shall maintain|will maintain)\b', re.I)


def normalize(view):
    return [' '.join(line.split()).replace('relation- ship', 'relationship') for line in legacy.spans_for(view)]


def candidate(text):
    if not ACTION.search(text) or not OBJECT.search(text):
        return False
    if HEADING.fullmatch(text):
        return False
    if NON_DUTY.search(text) and len(OBLIGATION.findall(text)) == 1:
        return False
    return bool(ACTION.search(SIGNING.sub('', CERTIFIED_MAIL.sub('', text))))


def previous_lead(spans, i):
    """Recognize an adjacent or continued request-governed disposition list."""
    if not LIST.match(spans[i]):
        return None
    for j in range(i - 1, max(-1, i - 7), -1):
        text = spans[j]
        if not text:
            continue
        if text.endswith((':', ':-', ':–', ':—')) and REQUEST.search(text) and not END_CUE.search(text):
            return j
        if not LIST.match(text):
            return None
    return None


def request_link(spans, i):
    text = spans[i]
    if END_CUE.search(text):
        return None
    if (REQUEST.search(text) or REQUEST_AT_END.search(text)) and (
            OBLIGATION.search(text) or LIST.match(text) or text.lower().startswith('upon receipt of such request')):
        return (i,)
    if (lead := previous_lead(spans, i)) is not None:
        return (lead, i)
    if CONFIRMATION.search(text) and i and REQUEST.search(spans[i - 1]) and candidate(spans[i - 1]):
        if OBLIGATION.search(text) and re.search(r'\b(?:has|have|had) (?:destroyed|returned)\b', text, re.I):
            return (i - 1, i)
    return None


def attached_end(text):
    """An agreement or role endpoint must qualify this same disposal action."""
    if not OBLIGATION.search(text):
        return False
    for event in END.finditer(text):
        for action in ACTION.finditer(text):
            gap = text[min(action.end(), event.end()):max(action.start(), event.start())]
            if not INDEPENDENT_DUTY.search(gap):
                return True
    return False


def source_proof(view):
    spans = normalize(view)
    old = literal.positive_citations(spans)
    if old:
        return {'kind': 'existing_closure', 'answer': E, 'citations': sorted(old[0]), 'candidate_count': 0}
    obligations = [i for i, text in enumerate(spans) if candidate(text)]
    for i in obligations:
        text = spans[i]
        if attached_end(text):
            return {'kind': 'linked_explicit_closure', 'answer': E, 'citations': [i], 'candidate_count': len(obligations)}
    scopes = {i: request_link(spans, i) for i in obligations}
    if scopes and all(link is not None for link in scopes.values()):
        return {'kind': 'only_request_governed', 'answer': N, 'citations': [], 'candidate_count': len(obligations),
                'source_request_witnesses': list(scopes.values())}
    return {'kind': 'unresolved_disposal_scope', 'answer': None, 'citations': [], 'candidate_count': len(obligations)}


def predictions(view, before, proof):
    evidence = before['evidence_sentence_ids']
    if proof['answer'] is not None and proof['kind'] != 'existing_closure':
        ids = proof['citations']
        if proof['answer'] == E and before['answer'] == E and set(ids) <= set(evidence):
            selected = before
        else:
            selected = {'answer': proof['answer'], 'evidence_sentence_ids': ids}
    else:
        selected = before
    if any(i not in range(len(legacy.spans_for(view))) for i in selected['evidence_sentence_ids']):
        raise ValueError('A disposition must cite original native source IDs')
    return {'composed': before, 'event_scoped': selected}


def evaluate(bank, policy, views, labels):
    by_arm = {}
    for arm, data in bank.items():
        measurements = {}
        for key, variants in data.items():
            for mode, output in variants.items():
                row = grade_view(legacy.DATASET, views[key], labels[key][TASK], output['answer'],
                                 output['evidence_sentence_ids'])
                measurements.setdefault(mode, []).append({'source': key, 'view': TASK, **row})
        old = measurements['composed']
        by_arm[arm] = {m: {'correct': int(sum(r['grade'] for r in rows)),
                           'evidence_f1': mean(r['evidence_f1'] for r in rows),
                           'corrected': sum(b['grade'] > a['grade'] for a, b in zip(old, rows, strict=True)),
                           'regressed': sum(b['grade'] < a['grade'] for a, b in zip(old, rows, strict=True)),
                           'paired_vs_composed': paired_source_effect(old, rows)} for m, rows in measurements.items()}
    return {'arms': by_arm, 'native_and_scoped_prediction_disagreements': dict(Counter(
        f['kind'] for key, f in policy.items() if f['answer'] is not None and f['answer'] != labels[key][TASK]['answer']))}


def run():
    ledger = ledger_status()
    current = read(composed.POINTER)
    parent = ROOT/current['artifact_root']
    terminal = verify(read(parent/'terminal.json'), 'terminal_sha256')
    if terminal['terminal_sha256'] != current['terminal_sha256'] or terminal['TEST_opened'] or ledger.get('reserved'):
        raise ValueError('The comparison must inherit the settled CNI development cells')
    source_files = (Path(__file__), Path(literal.__file__), Path(composed.__file__), Path(reviewed.__file__))
    spec = {'stage': 'disposition_trigger_attachment_TRAIN_DEV',
            'parent_terminal_sha256': terminal['terminal_sha256'],
            'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in source_files},
            'changes': 'source-bound termination, and request-only classification if every candidate is linked'}
    out = HOME/digest(spec)
    immutable_json(out/'binding.json', spec)
    if (out/'terminal.json').is_file():
        print(out, flush=True)
        return
    partitions, hashes = {}, {}
    for part in ('train', 'dev'):
        checkpoint, study, roster = archive.archive_context()
        sources, _, grade, _ = archive.collect(checkpoint, study, roster, part)
        previous = parent/f'{part}_predictions.json'
        if sha(previous) != terminal['predictions_sha256'][part] or sha(grade) != read(parent/'binding.json')[part.upper()+'_grade_sha256']:
            raise ValueError('Native baseline predictions and labels must match their receipts')
        views = {k: next(v for v in s['views'] if v['id'] == TASK) for k, s in sources.items()}
        proofs = {k: source_proof(v) for k, v in views.items()}
        bank = {arm: {key: predictions(views[key], tasks[TASK], proofs[key]) for key, tasks in data.items()}
                for arm, data in read(previous).items()}
        hashes[part] = immutable_json(out/f'{part}_predictions.json', bank)
        partitions[part] = (views, grade, proofs, bank)
        if part == 'train':
            scope_review = {s['key']: reviewed.REVIEW[b, i][0] for b, cohort in enumerate(roster, 1)
                            for i, s in enumerate(x for x in cohort if x['dataset'] == legacy.DATASET)}
    results = {}
    for part, (views, grade, proofs, bank) in partitions.items():
        results[part] = {'mothers': len(views), 'scope_counts': dict(Counter(p['kind'] for p in proofs.values())),
                         **evaluate(bank, proofs, views, read(grade))}
        if part == 'train':
            results[part]['request_scopes_vs_prior_source_reviews'] = dict(Counter(
                scope_review[key] for key, proof in proofs.items() if proof['kind'] == 'only_request_governed'))
    if ledger_status() != ledger:
        raise ValueError('No new physical response belongs to the reserved local analysis')
    report = sealed({'status': 'settled_cni_disposition_event_attachment', 'binding_sha256': digest(spec),
                     'results': results, 'predictions_sha256': hashes, 'new_model_calls': 0,
                     'TEST_opened': False, 'ledger': ledger}, 'terminal_sha256')
    immutable_json(out/'terminal.json', report)
    pending = POINTER.with_suffix('.pending')
    pending.write_text(json.dumps({'status': report['status'], 'terminal_sha256': report['terminal_sha256'],
                                   'artifact_root': str(out.relative_to(ROOT))})+'\n')
    pending.replace(POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
