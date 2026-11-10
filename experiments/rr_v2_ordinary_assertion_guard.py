"""Simple diagnostic control for the actual self-describing legal API.

This is a partial lexical/citation guard, not a learned contract, semantic parser,
or general NL-fidelity certificate. Uncertified rows are quarantined, never made
false. Original raw frames remain unchanged. It uses no labels or teacher table.
"""
from copy import deepcopy
import re


def citations(text):
    out=[]
    for m in re.finditer(r'\bsection\s+(\d+)((?:\s*\([a-zA-Z0-9]+\))*)',text,re.I):
        out.append((m[1],*re.findall(r'\(([a-zA-Z0-9]+)\)',m[2].lower())))
    return out


def guarded_case(programme,case):
    heads={r['head']['predicate'] for r in programme['rules']}
    accepted=[];quarantined=[];unhandled=[]
    for row in case['facts']:
        name=row['atom']['predicate'];quote=row['quote'];refs=citations(quote);reason=None
        exact=re.fullmatch(r'section_(\d+)([a-z])(\d*)_applies',name)
        root=re.search(r'_under_(\d+)_',name)
        if name not in heads:pass
        elif exact:
            required=(exact[1],exact[2])+((exact[3],) if exact[3] else ())
            if required not in refs:reason='No exact named applicability citation; not proof the status is false'
        elif root:
            if not any(x[0]==root[1] for x in refs):reason='No citation of the declared allowance section; not proof of falsity'
        elif re.fullmatch(r'[a-z]+',name):
            if not re.search(r'\b'+re.escape(name)+r'\b',quote,re.I):reason='No literal status word; synonyms remain uncertified, not false'
        else:unhandled.append(name)
        if reason:quarantined.append({'row':deepcopy(row),'reason':reason})
        else:accepted.append(deepcopy(row))
    return {**deepcopy(case),'facts':accepted},{'quarantined':quarantined,'unhandled_head_predicates':sorted(set(unhandled)),
        'not_a_complete_semantic_validator':True,'quarantine_is_not_negation_or_label_repair':True,
        'self_describing_API_name_assumption_explicit':True,'source_learned_guidance_not_used':True}
