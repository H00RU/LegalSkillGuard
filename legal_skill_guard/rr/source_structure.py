"""Public-source regions and conservative heading/reference context.

This module registers structure, not legal applicability or truth. Every source
unit remains residual until a semantic translation is accepted elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import re

from .coverage import SourceLedger, digest


CITATION = re.compile(r'(?:(?:[0-9]+ U\.S\.C\.|Ariz\. Rev\. Stat\.|Or\. Rev\. Stat\.|'
                      r'42 Pa\. Cons\. Stat\.|Wis\. Stat\.) §\s*[0-9]+(?:[.-][0-9]+)*[A-Za-z]?(?:\([A-Za-z0-9]+\))*|'
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
        solved=list(re.finditer(r'^Solved Reasoning Steps:\s*$',part,re.M))
        if len(solved)>1 or solved and not statute[0].end()<=solved[0].start()<facts[0].start():
            raise ValueError('Ambiguous original OpenExempt supplied-premise boundaries')
        output = re.search(r'^Output contract:', part[facts[0].end():], re.M)
        end_facts = facts[0].end()+output.start() if output else len(part)
        regions.extend([(offset, offset+statute[0].start(), 'instruction', view),
            (offset+statute[0].start(),offset+statute[0].end(),'heading',view),
            (offset+statute[0].end(),offset+(solved[0].start() if solved else facts[0].start()),'rule',view),
            (offset+facts[0].start(), offset+facts[0].end(), 'heading', view),
            (offset+facts[0].end(), offset+end_facts, 'fact', view),
            (offset+end_facts, offset+len(part), 'instruction', view)])
        if solved:
            regions.append((offset+solved[0].start(),offset+solved[0].end(),'instruction',view))
            position=solved[0].end()
            boilerplate=('The following reasoning steps have already been solved. '
                         'Use this information to aid you in completing the remainder of the task.')
            for line in part[position:facts[0].start()].splitlines(keepends=True):
                # The adapter supplies these premises as public input. This
                # registration neither verifies them nor infers new truth.
                role='instruction' if not line.strip() or line.strip()==boilerplate else 'fact'
                regions.append((offset+position,offset+position+len(line),role,view));position+=len(line)
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
        citation=None
        if legal_heading:
            base=re.sub(r'(?:\([A-Za-z0-9]+\))+$','',stripped)
            citation=(base,tuple(re.findall(r'\([A-Za-z0-9]+\)',stripped[len(base):])))
        sara_heading = re.match(r'^§[0-9]+\.', stripped)
        enumerated = re.match(r'^\([A-Za-z0-9]+\)', stripped)
        level = len(markdown[1]) if markdown else len(re.findall(r'\([^)]*\)', stripped)) if legal_heading else 0 if sara_heading else \
            10+len(line)-len(line.lstrip()) if enumerated and region[0]=='rule' else None
        if level is not None:
            if citation is not None:
                # A different statute is not a parent merely because its
                # citation has fewer parentheses. Keep only actual prefixes
                # within this same supplied statute, including its preface.
                while stack:
                    parent=stack[-1].get('citation')
                    if parent and parent[0]==citation[0] and len(parent[1])<len(citation[1]) and \
                            citation[1][:len(parent[1])]==parent[1]:break
                    stack.pop()
            else:
                while stack and stack[-1]['level']>=level:stack.pop()
            if stack:
                stack[-1]['has_child'] = True
            headings.append(clause.id)
        context = {frame['key'] for frame in stack}
        context.update(key for frame in stack for key in frame['preface'])
        exact = []
        for reference in (() if legal_heading else CITATION.findall(line)):
            target = citation_heads.get((region[1], reference))
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
            stack.append({'level':level,'key':clause.id,'preface':set(),'has_child':False,'citation':citation})
        elif stack and not stack[-1]['has_child']:
            stack[-1]['preface'].add(clause.id)
    ledger.validate()
    return SourceStructure(ledger, roles, tuple(headings), references, unresolved)


def explicit_query_target(source):
    """Locate an explicit SARA section path; no applicability or truth inference.

    This is source-only prompt/diagnostic metadata. A target pointer does not
    cover a rule, discharge another unit, or narrow any completion domain.
    Unsupported/ambiguous references remain unresolved.
    """
    if source['dataset']!='SARA_v2_Binary':return None
    matches=re.findall(r'\bsection\s+([0-9]+)((?:\([A-Za-z0-9]+\))*)',source['public']['query'],re.I)
    if len(matches)!=1:return None
    number,suffix=matches[0];target=tuple(re.findall(r'\(([A-Za-z0-9]+)\)',suffix))
    structure=inspect_source(source);current=None;stack=[];selected=[]
    for clause in structure.ledger.clauses:
        if structure.roles[clause.id]['role']!='rule':continue
        text=structure.ledger.text[clause.start:clause.end]
        heading=re.match(r'^\s*§([0-9]+)\.',text)
        if heading:current=heading[1];stack=[]
        else:
            paragraph=re.match(r'^(\s*)\(([A-Za-z0-9]+)\)',text)
            if paragraph:
                depth=len(paragraph[1])
                while stack and stack[-1][0]>=depth:stack.pop()
                stack.append((depth,paragraph[2]))
        if current==number and tuple(token for _,token in stack)==target:selected.append(clause.id)
    return {'reference':number+suffix,'unit_ids':selected,'basis':'explicit public section path and original indentation',
            'source_obligations_discharged':False} if selected else None


def compact_contexts(structure):
    """Reduce printed context edges while preserving every full closure.

    The source ledger and its semantics stay unchanged. Cyclic components keep
    their original edges; DAG parents use an exact transitive cover. A final
    all-unit check forbids any loss or invention of context reachability.
    """
    original={c.id:set(c.context) for c in structure.ledger.clauses}
    order={c.id:i for i,c in enumerate(structure.ledger.clauses)}
    def reachable(key,graph):
        pending=[key];seen=set()
        while pending:
            item=pending.pop()
            if item not in seen:seen.add(item);pending.extend(graph[item])
        return seen
    closure={key:reachable(key,original) for key in original}
    reduced={}
    for key,parents in original.items():
        if any(key in closure[parent] for parent in parents):reduced[key]=set(parents);continue
        selected=set();covered=set()
        for parent in sorted(parents,key=lambda p:(-len(closure[p]),order[p])):
            if not closure[parent]<=covered:selected.add(parent);covered.update(closure[parent])
        reduced[key]=selected
    if any(reachable(key,reduced)!=closure[key] for key in original):
        raise ValueError('Compact context graph changed source reachability')
    return {key:sorted(parents,key=order.__getitem__) for key,parents in reduced.items()}
