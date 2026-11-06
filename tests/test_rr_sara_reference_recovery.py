"""Regression for the actual fixed-TRAIN conjunction reference query."""
from io import BytesIO
import json
import re
import tarfile

import pytest

from legal_skill_guard.rr import source_learning
from legal_skill_guard.rr.oracles import ROOT


def test_original_conjunction_keeps_both_statute_calls():
    prefix, query = source_learning.sara_case({'original_id':'s3306_c_10_A_i_pos'})
    assert query == ('s3306_c_10_A("services","Johns Hopkins University","Alice","2017-01-01"),\n'
                     '    s3306_c_10_A_i("Alice","Johns Hopkins University","2017-01-01")')
    assert 'attending_classes_' in prefix


def test_other_original_train_queries_are_unchanged():
    grades = json.loads((ROOT/'data/packets/rr_v2/grading_only/train.json').read_text())['sources']
    old_supported = 0
    with tarfile.open(ROOT/'data/cache/rr_v2/sara_v2.tar.gz') as archive:
        for sid, grade in grades.items():
            if not sid.startswith('SARA_v2_Binary:'):
                continue
            raw = archive.extractfile('sara_v2/cases/'+grade['original_id']+'.pl').read().decode()
            prefix, tests = raw.split('% Test', 1)
            old_query = re.search(r':-\s*(.*?)\.\s*(?:\n|$)', tests, re.S)[1].strip().removeprefix('\\+').strip()
            if re.fullmatch(r's[\w]+\([\w\s,".\-]*\)', old_query):
                assert source_learning.sara_case(grade) == (prefix, old_query)
                old_supported += 1
    assert old_supported == 23


@pytest.mark.parametrize('query', [
    's1(1);halt', 's1(1),halt', 's1(1),consult("bad")',
    's1(1),shell("bad")', 'call(s1(1))', 's1(1)->s2(2)',
])
def test_reference_query_still_rejects_arbitrary_prolog_goals(monkeypatch, query):
    class Archive:
        def __enter__(self):return self
        def __exit__(self, *args):return False
        def extractfile(self, name):
            return BytesIO(('fact.\n% Test\n:- '+query+'.\n:- halt.\n').encode())
    monkeypatch.setattr(source_learning.tarfile, 'open', lambda *a, **k:Archive())
    with pytest.raises(ValueError, match='Unsupported reference question syntax'):
        source_learning.sara_case({'original_id':'untrusted'})
