"""Separate disposition duties from administrative delivery on archived TRAIN/DEV."""

import json
import re
from collections import Counter
from pathlib import Path

from experiments import convergence_revision5_cni_disposition_events as events
from experiments.convergence_revision5_cni_disposition_events import E, N, TASK

HOME = events.BASE / 'revision5_cni_disposition_roles_20261119'
POINTER = events.HANDOFF / 'revision5_cni_disposition_roles_current.json'
SIGNATURE_DELIVERY = re.compile(
    r'\bexecut(?:e|ed) and deliver (?:any |the )?documents?(?:\(s\))? or legal instruments?\b|'
    r'\b(?:executed|signed)\b[^;]*\b(?:fax|facsimile)\b[^;]*\bhand delivered original\b', re.I)
NOTICE_DELIVERY = re.compile(
    r'^\s*(?:\d+\.\s*)?(?:all |any )[^.;]{0,70}\bnotices?\b'
    r'[^.;]*\b(?:in writing|in person)\b[^.;]*\bdeliver(?:ed)?\b'
    r'[^.;]*\b(?:hand|courier|fax|facsimile)\b', re.I)
CERTIFICATE = re.compile(
    r'^where\b[^;]*\bsatisfies its obligation to (?:return|destroy)\b'
    r'[^;]*\bby destroying\b[^;]*\bwill deliver\b[^;]*\ba certificate\b'
    r'[^;]*\bcertifying such destruction\b', re.I)
CUSTODY = re.compile(
    r'\bagrees to comply with\b[^.;]*\bconditions\b[^.;]*\bimposes upon approved removal\b'
    r'[^.;]*\bthe removed materials or items must be returned by a certain date\b', re.I)
HEADING = re.compile(r'^(?:\d+(?:\.\d+)*\.?\s+)?return (?:or destruction )?of [\w ]+\.?$', re.I)
DISPOSAL = re.compile(
    r'\b(?:return(?:ed|s|ing)?|destroy\w*|destruct\w*|eras(?:e|ed|ure|ing)|delet(?:e|ed|ion|ing))\b',
    re.I)
PERFORMATIVE_REQUEST = re.compile(
    r'\brequest in writing (?:the )?(?:return or destruction|destruction or return) of\b'
    r'[^;]*\bconfidential information\b[^;]*\bthe receiving party\s+(?:shall|will|must)\s+'
    r'(?:promptly )?comply with such request\b', re.I)


def administrative_role(text):
    """Classify the delivery object and preserve any separate operative duty."""
    if HEADING.fullmatch(text):
        return 'disposition_heading'
    if ';' in text:
        return None
    duties = len(events.OBLIGATION.findall(text))
    if CUSTODY.search(text) and duties == 2 and len(DISPOSAL.findall(text)) == 1:
        return 'return_of_item_removed_with_approval'
    if duties > 1:
        return None
    if certificate := CERTIFICATE.search(text):
        if not DISPOSAL.search(text[certificate.end():]):
            return 'certificate_of_previous_disposal'
    if (DISPOSAL.search(events.CERTIFIED_MAIL.sub('', text))
            or len(re.findall(r'\bdeliver(?:ed)?\b', text, flags=re.I)) > 1
            or re.search(r'\b(?:confidential|protected) (?:information|materials?)\b', text, flags=re.I)):
        return None
    if SIGNATURE_DELIVERY.search(text):
        return 'execution_of_instrument'
    if NOTICE_DELIVERY.search(text):
        return 'delivery_of_notice'
    return None


def revised_proof(view, prior, use_performative):
    if prior['answer'] is not None:
        return prior
    spans = events.normalize(view)
    roles, links = {}, {}
    for i, span in enumerate(spans):
        if events.candidate(span):
            if (role := administrative_role(span)) is not None:
                roles[i] = role
            elif use_performative and PERFORMATIVE_REQUEST.search(span) and not events.END_CUE.search(span):
                links[i] = (i,)
            else:
                links[i] = events.request_link(spans, i)
    proof = {**prior, 'excluded_span_roles': roles}
    if links and all(link is not None for link in links.values()):
        return {**proof, 'kind': 'only_request_governed_after_role_binding', 'answer': N,
                'source_request_witnesses': list(links.values())}
    if roles and not links and set(roles.values()) <= {'execution_of_instrument', 'delivery_of_notice'}:
        if not any(
            DISPOSAL.search(events.SIGNING.sub('', events.CERTIFIED_MAIL.sub('', span)))
            for i, span in enumerate(spans) if i not in roles
        ):
            return {**proof, 'kind': 'only_administrative_delivery', 'answer': N}
    return proof


def compare(parent, terminal, out):
    context = events.archive.archive_context()
    cells, hashes = {}, {}
    for part in ('train', 'dev'):
        sources, _, grade, _ = events.archive.collect(*context, part)
        previous = parent / f'{part}_predictions.json'
        if events.sha(previous) != terminal['predictions_sha256'][part]:
            raise ValueError('Archived predictions failed verification')
        common = events.ROOT / events.read(events.composed.POINTER)['artifact_root']
        if events.sha(grade) != events.read(common / 'binding.json')[part.upper() + '_grade_sha256']:
            raise ValueError('Native grades failed verification')
        views = {k: next(v for v in s['views'] if v['id'] == TASK) for k, s in sources.items()}
        prior = {k: events.source_proof(v) for k, v in views.items()}
        proofs = {k: revised_proof(v, prior[k], use_performative=True) for k, v in views.items()}
        roles_only = {k: revised_proof(v, prior[k], use_performative=False) for k, v in views.items()}
        bank = {}
        for arm, data in events.read(previous).items():
            for key, variants in data.items():
                base = variants['event_scoped']
                bank.setdefault(arm, {})[key] = {
                    'composed': base,
                    'role_scope': events.predictions(views[key], base, roles_only[key])['event_scoped'],
                    'role_scope_with_performative': events.predictions(views[key], base, proofs[key])['event_scoped'],
                }
        hashes[part] = events.immutable_json(out / f'{part}_predictions.json', bank)
        cells[part] = views, proofs, prior, grade, bank
    results = {}
    for part, (views, proofs, prior, grade, bank) in cells.items():
        labels = events.read(grade)
        changed = [k for k, proof in proofs.items() if proof['answer'] != prior[k]['answer']]
        results[part] = {
            'mothers': len(views),
            'new_source_decisions': dict(Counter(proofs[k]['kind'] for k in changed)),
            'new_decisions_agreeing_with_native_reference': sum(
                proofs[k]['answer'] == labels[k][TASK]['answer'] for k in changed),
            **events.evaluate(bank, proofs, views, labels),
        }
        if part == 'train':
            roster = context[2]
            audited = {s['key']: events.reviewed.REVIEW[b, i][0] for b, cohort in enumerate(roster, 1)
                       for i, s in enumerate(x for x in cohort if x['dataset'] == events.legacy.DATASET)}
            results[part]['prior_source_reviews_of_new_decisions'] = dict(Counter(audited[k] for k in changed))
    return results, hashes


def run():
    ledger = events.ledger_status()
    current = events.read(events.POINTER)
    parent = events.ROOT / current['artifact_root']
    terminal = events.verify(events.read(parent / 'terminal.json'), 'terminal_sha256')
    if terminal['terminal_sha256'] != current['terminal_sha256'] or terminal['TEST_opened'] or ledger.get('reserved'):
        raise ValueError('A settled, unchanged development comparison is required')
    parent_spec = events.read(parent / 'binding.json')
    source_hashes = parent_spec['source_sha256']
    if (events.digest(parent_spec) != terminal['binding_sha256']
            or any(events.sha(events.ROOT / path) != h for path, h in source_hashes.items())):
        raise ValueError('Prior event proof sources changed')
    source = Path(__file__)
    spec = {'stage': 'disposition_scope_delivery_roles_TRAIN_DEV',
            'parent_terminal_sha256': terminal['terminal_sha256'],
            'source_sha256': {**source_hashes, str(source.relative_to(events.ROOT)): events.sha(source)},
            'comparison': ['event_scoped', 'administrative_role_scope', 'administrative_roles_and_performative_request']}
    out = HOME / events.digest(spec)
    events.immutable_json(out / 'binding.json', spec)
    if (out / 'terminal.json').exists():
        print(out, flush=True)
        return
    results, hashes = compare(parent, terminal, out)
    if events.ledger_status() != ledger:
        raise ValueError('This comparison does not authorize new physical calls')
    report = events.sealed({
        'status': 'settled_cni_disposition_role_scope', 'binding_sha256': events.digest(spec),
        'results': results, 'predictions_sha256': hashes, 'new_model_calls': 0,
        'TEST_opened': False, 'ledger': ledger,
        'performative_request_scope': 'exploratory_DEV_construction',
    }, 'terminal_sha256')
    events.immutable_json(out / 'terminal.json', report)
    pending = POINTER.with_suffix('.pending')
    pending.write_text(json.dumps({'status': report['status'], 'terminal_sha256': report['terminal_sha256'],
                                   'artifact_root': str(out.relative_to(events.ROOT))}) + '\n')
    pending.replace(POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
