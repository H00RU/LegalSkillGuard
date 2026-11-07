"""Public-source regions and conservative heading/reference context.

This module registers structure, not legal applicability or truth. Every source
unit remains residual until a semantic translation is accepted elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import re

from .coverage import SourceLedger, digest


CITATION = re.compile(r'(?:[0-9]+ U\.S\.C\. §\s*[0-9]+[A-Za-z]?(?:\([A-Za-z0-9]+\))*|'
                      r'735 Ill\. Comp\. Stat\. [0-9]+/[0-9]+-[0-9]+(?:\([A-Za-z0-9]+\))*)')


@dataclass
class SourceStructure:
    ledger: SourceLedger
    roles: dict
    heading_units: tuple
    exact_references: dict
    unresolved_references: dict

    @property
    def version(self):
        return digest({'ledger': self.ledger.version, 'roles': self.roles,
            'headings': self.heading_units, 'references': self.exact_references,
            'unresolved_references': self.unresolved_references})


def source_regions(source):
    """Return exact offsets of fields already supplied by the five adapters."""
    from .engine import source_text
    public, dataset = source['public'], source['dataset']
    text = source_text(source)
    if dataset in {'SARA_v2_Binary', 'RuleArena_Airline'}:
        end = len(public['rules'])
        facts = public['facts'] if dataset == 'SARA_v2_Binary' else public['prompt']
        regions = [(0, end, 'rule', None), (end+2, end+2+len(facts), 'fact', None)]
        if dataset == 'SARA_v2_Binary':
            regions.append((end+len(facts)+4, len(text), 'query', None))
        return regions
    if dataset == 'ProofWriter_OWA_depth5':
        regions, offset = [], 0
        for role, parts in [('fact', public['facts']), ('rule', public['rules']), ('query', [public['query']])]:
            for part in parts:
                regions.append((offset, offset+len(part), role, None))
                offset += len(part)+1
        return regions
    if dataset == 'ContractNLI':
        end = len(public['document'])
        return [(0, end, 'rule', None), (end+2, len(text), 'query', None)]
    if dataset != 'OpenExempt':
        raise ValueError('Unsupported public-source adapter')
    regions, offset = [], 0
    for view in ('EC', 'EV'):
        part = public['views'][view]
        statute = list(re.finditer(r'^Statutes:\s*$', part, re.M))
        facts = list(re.finditer(r'^Facts:\s*$', part, re.M))
        if len(statute)!=1 or len(facts)!=1 or statute[0].start()>=facts[0].start():
            raise ValueError('Ambiguous original OpenExempt source-field boundaries')
        output = re.search(r'^Output contract:', part[facts[0].end():], re.M)
        end_facts = facts[0].end()+output.start() if output else len(part)
        regions.extend([(offset, offset+statute[0].start(), 'instruction', view),
            (offset+statute[0].start(), offset+facts[0].start(), 'rule', view),
            (offset+facts[0].start(), offset+facts[0].end(), 'heading', view),
            (offset+facts[0].end(), offset+end_facts, 'fact', view),
            (offset+end_facts, offset+len(part), 'instruction', view)])
        offset += len(part)+2
    return regions


def inspect_source(source):
    from .engine import source_text
    ledger = SourceLedger.from_text(source_text(source))
    regions = source_regions(source)
    roles, stack, headings, references, unresolved = {}, [], [], {}, {}
    citation_heads = {}
    for clause in ledger.clauses:
        matches = [(role, view) for start,end,role,view in regions if start<=clause.start and clause.end<=end]
        if len(matches)!=1:
            raise ValueError('Source unit is not covered by one original public field')
        role, view = matches[0]
        roles[clause.id] = {'role': role, 'view': view}
        line = ledger.text[clause.start:clause.end].strip()
        if role=='rule' and CITATION.fullmatch(line):
            citation_heads[(view, line)] = clause.id
    previous_region = None
    for i, clause in enumerate(ledger.clauses):
        line = ledger.text[clause.start:clause.end]
        stripped = line.strip()
        region = (roles[clause.id]['role'], roles[clause.id]['view'])
        if region!=previous_region:
            stack = []
        previous_region = region
        markdown = re.match(r'^(#{1,6})\s+', stripped)
        legal_heading = CITATION.fullmatch(stripped)
        sara_heading = re.match(r'^§[0-9]+\.', stripped)
        enumerated = re.match(r'^\([A-Za-z0-9]+\)', stripped)
        level = len(markdown[1]) if markdown else len(re.findall(r'\([^)]*\)', stripped)) if legal_heading else 0 if sara_heading else \
            10+len(line)-len(line.lstrip()) if enumerated and region[0]=='rule' else None
        if level is not None:
            while stack and stack[-1]['level']>=level:
                stack.pop()
            if stack:
                stack[-1]['has_child'] = True
            headings.append(clause.id)
        context = {frame['key'] for frame in stack}
        context.update(key for frame in stack for key in frame['preface'])
        exact = []
        for citation in CITATION.findall(line):
            target = citation_heads.get((region[1], citation))
            if target and target!=clause.id:
                exact.append(target)
                context.add(target)
        if exact:
            references[clause.id] = sorted(set(exact))
        relative = re.findall(r'\b(?:subsection|paragraph|subparagraph|clause)\s*\([^)]*\)', line, re.I)
        if relative:
            # Retain unresolved relative references; context is not a semantic
            # footprint or a license to ignore unparsed cross-clause effects.
            unresolved[clause.id] = relative
        ledger.clauses[i] = replace(clause, context=tuple(sorted(context)))
        if level is not None:
            stack.append({'level':level,'key':clause.id,'preface':set(),'has_child':False})
        elif stack and not stack[-1]['has_child']:
            stack[-1]['preface'].add(clause.id)
    ledger.validate()
    return SourceStructure(ledger, roles, tuple(headings), references, unresolved)
