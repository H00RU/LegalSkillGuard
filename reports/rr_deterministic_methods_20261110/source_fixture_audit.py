"""Dataset-era, scope-limited legal arithmetic checks; no model or test labels.

These are newly constructed mechanism cases, NOT native SARA results or a
complete tax oracle. Eligibility/exclusion are supplied inputs. Two independent
computational formulations cross-check arithmetic, not independent legal review.
"""
from __future__ import annotations

import hashlib
import argparse
import itertools
import json
import tarfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARCHIVE = ROOT / 'work/final-plan/data-audit/sara_v2.tar.gz'


@dataclass(frozen=True)
class Payment:
    employer: str
    employee: str
    year: int
    amount: int
    excluded: bool = False

    @property
    def key(self):
        return self.employer, self.employee, self.year


def grouped_wages(payments, ceiling=7000):
    totals = defaultdict(int)
    for p in payments:
        if p.amount < 0:
            raise ValueError('Refunds/negative adjustments outside this fixture')
        if not p.excluded:
            totals[p.key] += p.amount
    return sum(min(ceiling, amount) for amount in totals.values())


def remaining_allowance_wages(payments, ceiling=7000):
    remaining = {}
    wages = 0
    for p in payments:
        if p.amount < 0:
            raise ValueError('Refunds/negative adjustments outside this fixture')
        if p.excluded:
            continue
        allowance = remaining.get(p.key, ceiling)
        taxable = min(allowance, p.amount)
        wages += taxable
        remaining[p.key] = allowance - taxable
    return wages


def per_payment_local_extension(payments, ceiling=7000):
    # Arithmetic extension of the observed local two-scalar predicate.
    # This is not a claim to have executed complete upstream Prolog cases.
    return sum(min(ceiling, p.amount) for p in payments if not p.excluded)


def basic_then_additional(basic, earned_income, additional):
    return min(basic, max(500, 250 + earned_income)) + additional


def basic_then_additional_piecewise(basic, earned_income, additional):
    limit = 500 if earned_income <= 250 else earned_income + 250
    limited_basic = basic if basic <= limit else limit
    return limited_basic + additional


def source_evidence(archive):
    requests = [
        ('statutes/source/section3306', 31, 55),
        ('statutes/prolog/section3306.pl', 270, 306),
        ('statutes/source/section63', 1, 250),
        ('statutes/prolog/section63.pl', 49, 79),
    ]
    records = []
    with tarfile.open(archive) as tf:
        for suffix, begin, end in requests:
            member = next(n for n in tf.getnames() if n.endswith(suffix))
            raw = tf.extractfile(member).read()
            lines = raw.decode('utf-8').splitlines()
            records.append({
                'member': member, 'sha256': hashlib.sha256(raw).hexdigest(),
                'first_line': begin, 'last_line': min(end, len(lines)),
                'excerpt': '\n'.join(lines[begin-1:end]),
            })
    return records


def run(archive):
    fixtures = {
        'same_employer_employee_year': [Payment('A','X',2015,6000), Payment('A','X',2015,6000)],
        'different_employees': [Payment('A','X',2015,6000), Payment('A','Y',2015,6000)],
        'different_employers': [Payment('A','X',2015,6000), Payment('B','X',2015,6000)],
        'different_years': [Payment('A','X',2015,6000), Payment('A','X',2016,6000)],
        'excluded_does_not_consume_cap': [Payment('A','X',2015,3000,True), Payment('A','X',2015,6000)],
    }
    fixture_rows = []
    for name, payments in fixtures.items():
        expected = grouped_wages(payments)
        other = remaining_allowance_wages(payments)
        assert expected == other
        fixture_rows.append({'name': name, 'input': [p.__dict__ for p in payments],
                             'grouped': expected, 'remaining_allowance': other,
                             'per_payment_local_extension': per_payment_local_extension(payments)})

    keys = [('A','X',2015), ('A','Y',2015), ('B','X',2015), ('A','X',2016)]
    options = [Payment(*k, a, e) for k in keys for a in (0,1,4,7,8) for e in (False,True)]
    checks = differences = 0
    for n in range(4):
        for payments in itertools.product(options, repeat=n):
            answer = grouped_wages(payments, ceiling=7)
            assert answer == remaining_allowance_wages(payments, ceiling=7)
            assert answer == remaining_allowance_wages(tuple(reversed(payments)), ceiling=7)
            differences += answer != per_payment_local_extension(payments, ceiling=7)
            checks += 1

    basic_checks = 0
    for basic, income, additional in itertools.product(
            (0,499,500,501,2000,5000), (0,249,250,251,1000,6000), (0,1,3000)):
        assert basic_then_additional(basic,income,additional) == basic_then_additional_piecewise(basic,income,additional)
        basic_checks += 1
    if archive.exists():
        evidence = source_evidence(archive)
        archive_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        evidence_status = 're-extracted from original archive'
    else:
        bundled = json.loads((HERE/'source_fixture_sources.json').read_text(encoding='utf-8'))
        evidence = bundled['source_evidence']
        archive_digest = bundled['source_archive_sha256']
        evidence_status = 'bundled source excerpts; original archive not reverified in this run'
    result = {
        'purpose': 'Source-grounded restricted arithmetic fixture audit',
        'source_archive_sha256': archive_digest,
        'source_evidence': evidence,
        'source_evidence_status': evidence_status,
        'assumptions': [
            'Dataset-era source texts, not current-law tax guidance',
            'Employment, employer/employee identity, calendar year and exclusion qualification supplied correctly',
            'Nonnegative payment amounts; no refunds, successors, identity ambiguity or missing payments',
            'Total wages over supplied complete payment records, not per-payment liability allocation',
            'Section63 fixture covers dependent basic cap plus supplied additional amount; other exceptions upstream',
            'Uses earned_income from source, does not inherit upstream gross_income substitution',
        ],
        'native_model_results': False, 'native_prolog_executed': False,
        'independent_legal_adjudication': False, 'model_calls': 0,
        '3306_named_fixtures': fixture_rows,
        '3306_constructed_domain': {'max_records':3,'keys':keys,'amounts':[0,1,4,7,8],
                                   'ceiling':7,'excluded':[False,True]},
        '3306_cases_checked': checks, '3306_local_vs_grouped_disagreements': differences,
        '63_cases_checked': basic_checks,
        '63_example': {'basic':2000,'earned_income':0,'additional':3000,
                       'correct_restricted_value':3500,'incorrect_cap_after_addition':500},
    }
    (HERE/'source_fixture_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k in ['3306_cases_checked','3306_local_vs_grouped_disagreements','63_cases_checked','model_calls']},ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive',type=Path,default=ARCHIVE)
    run(parser.parse_args().archive)
