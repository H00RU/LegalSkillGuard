"""Bind the settled use/license comparison and measure witness-form coverage."""

import re
import sqlite3

from experiments import convergence_revision5_cni_use_and_license as study
from legal_skill_guard.rr.checkpoint import immutable_json


TABLE = study.ROOT / 'reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_USE_AND_LICENSE_20261119.json'
SPLIT_LEAD = re.compile(r'\b(?:nothing (?:in|contained)|no (?:(?:[a-z]+ ){0,5})grant(?:ed|ing)?)\b', re.I)
SPLIT_CONTINUATION = re.compile(r'^(?:agreement|information|document|disclosure)\b', re.I)
RIGHTS = re.compile(r'\b(?:rights?|grant\w*|licen[sc]es?)\b', re.I)
THEREIN = re.compile(r'\bno (?:rights?|licen[sc]es?)\b.{0,50}\btherein\b', re.I)


def source_forms(spans):
    forms = set()
    for previous, current in zip(spans, spans[1:]):
        a, b = (' '.join(text.split()) for text in (previous, current))
        if (SPLIT_LEAD.search(a) and not a.endswith(('.', '!', '?', ';', ':'))
                and SPLIT_CONTINUATION.search(b) and RIGHTS.search(b)):
            forms.add('split_negation')
        if 'confidential information' in a.lower() and THEREIN.search(b):
            forms.add('preceding_information_antecedent')
    return forms


def run():
    pointer = study.read(study.POINTER)
    out = study.ROOT / pointer['artifact_root']
    binding, terminal, resume = [study.read(out / item) for item in ('binding.json', 'terminal.json', 'resume_transport_receipt.json')]
    assert pointer['status'] == terminal['status'] == study.DONE and study.digest(binding) == out.name
    assert terminal['predictions_sha256'] == study.sha(out / 'predictions.json')
    assert resume['original_binding_sha256'] == study.sha(out / 'binding.json')
    assert all(study.sha(out / 'source_snapshot' / name) == expected for name, expected in binding['source_sha256'].items())
    rows = study.read(out / 'predictions.json')
    calls = {cell['id'] for row in rows for cell in row.values()}
    with sqlite3.connect(study.LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        prefix = resume['settled_original_call'].split(':', 1)[0]
        paid = dict(db.execute('select id,status from calls where id like ?', (prefix + ':%',)))
        assert paid == dict.fromkeys(calls, 'completed') and len(paid) == terminal['paid_calls'] == 18
        assert resume['settled_original_call'] in paid
    context = study.archive_context()
    coverage = {}
    for partition in ('train', 'dev'):
        sources, _, _, _ = study.collect(*context, partition)
        forms = [source_forms(study.span_inventory(next(v for v in source['views'] if v['id'] == 'nda-15')))
                 for source in sources.values()]
        coverage[partition] = {
            'sources': len(forms),
            'split_negation': sum('split_negation' in row for row in forms),
            'preceding_information_antecedent': sum('preceding_information_antecedent' in row for row in forms),
        }
    summary = {**terminal, 'terminal_sha256': study.sha(out / 'terminal.json'),
               'transport_recovery_sha256': study.sha(out / 'resume_transport_receipt.json'),
               'original_paid_response_reused_in_resume': 1,
               'source_form_coverage_only_no_DEV_scores': coverage}
    immutable_json(TABLE, summary)
    print(coverage, flush=True)


if __name__ == '__main__':
    run()
