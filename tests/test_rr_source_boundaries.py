"""Regress actual OE scope contamination without translating legal outcomes."""
import json
from pathlib import Path
import re

from legal_skill_guard.rr.clause_scope import lower_clauses
from legal_skill_guard.rr.engine import source_text
from legal_skill_guard.rr.source_structure import CITATION,inspect_source


def citation_parts(text):
    base=re.sub(r'(?:\([A-Za-z0-9]+\))+$','',text)
    return base,tuple(re.findall(r'\([A-Za-z0-9]+\)',text[len(base):]))


def test_all32_original_OE_views_keep_exact_text_and_only_actual_statute_ancestors():
    root=Path(__file__).resolve().parents[1]
    sources=[s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']
             if s['dataset']=='OpenExempt']
    assert len(sources)==32
    prefixes=('11 U.S.C.','Ariz. Rev. Stat.','735 Ill. Comp. Stat.','Or. Rev. Stat.',
              '42 Pa. Cons. Stat.','Wis. Stat.')
    for source in sources:
        a=inspect_source(source);assert a.ledger.text==source_text(source)
        text={c.id:a.ledger.text[c.start:c.end] for c in a.ledger.clauses}
        headers={key:value for key,value in text.items() if value.startswith(prefixes) and len(value)<100}
        assert len(headers)==144 and all(CITATION.fullmatch(value) for value in headers.values())
        assert not a.exact_references  # Supplied standalone duplicates are declarations.
        for child,value in headers.items():
            base,qualifiers=citation_parts(value)
            for parent in a.ledger.closure({child})-{child}:
                if parent in headers:
                    other,parts=citation_parts(headers[parent])
                    assert other==base and len(parts)<len(qualifiers) and qualifiers[:len(parts)]==parts
                assert int(parent[1:])<int(child[1:])
        assert all(c.state=='residual' for c in a.ledger.clauses)


def test_actual_instruction_labels_and_public_supplied_premises_are_not_untranslated_laws():
    root=Path(__file__).resolve().parents[1]
    source=next(s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']
                if s['dataset']=='OpenExempt')
    a=inspect_source(source);counts={'statute_label':0,'solved_label':0,'boilerplate':0,'given':0}
    for c in a.ledger.clauses:
        text=a.ledger.text[c.start:c.end];role=a.roles[c.id]['role']
        if text=='Statutes:':assert role=='heading';counts['statute_label']+=1
        if text=='Solved Reasoning Steps:':assert role=='instruction';counts['solved_label']+=1
        if text.startswith('The following reasoning steps have already been solved.'):
            assert role=='instruction';counts['boilerplate']+=1
        if text.startswith('The Debtor may claim property exemptions under'):
            assert role=='fact';counts['given']+=1
    assert counts=={'statute_label':2,'solved_label':2,'boilerplate':2,'given':2}


def test_citation_prefixes_do_not_invent_a_missing_parent_or_keep_another_section():
    source={'dataset':'SARA_v2_Binary','public':{'rules':
        '11 U.S.C. § 522\n11 U.S.C. § 522(b)\n11 U.S.C. § 522(b)(1)\n'
        '11 U.S.C. § 522(d)(1)\n11 U.S.C. § 523(d)(1)', 'facts':'Alice owns property.','query':'Does it apply?'}}
    a=inspect_source(source)
    assert a.ledger.closure({'s2'})=={'s0','s1','s2'}
    assert a.ledger.closure({'s3'})=={'s0','s3'}
    assert a.ledger.closure({'s4'})=={'s4'}


def test_foreign_applicability_scope_is_not_physically_inserted_into_another_statute():
    source={'dataset':'SARA_v2_Binary','public':{'rules':
        '11 U.S.C. § 522\nFederal provision.\nAriz. Rev. Stat. § 33-1125(1)\nArizona provision.',
        'facts':'Alice owns property.','query':'Does it apply?'}}
    a=inspect_source(source)
    program={'nodes':[],'scopes':[{'name':'federal','source':'s0','condition':{'var':'b_federal_applies'}},
        {'name':'arizona','source':'s2','condition':True}],
        'clauses':[{'name':'local_rule','sources':['s3'],'value':1,'otherwise':0}],
        'query':{'var':'local_rule'}}
    lowered=lower_clauses(a,program)
    assert lowered['scope_bindings'][0]['enforced_scopes']==['arizona']
    assert lowered['covered']=={'s2','s3'}
    assert lowered['unused_scope_sources']==['s0']
