"""Restore an enclosing source section by a unique literal excerpt anchor.

No answer, label, topic keyword, graph or model output enters extraction. Only
whitespace and a terminal native page annotation are normalized for matching.
The returned text is an exact slice of the verified parent. Section coverage
is syntactic; it does not certify legal cross-reference or task closure.
"""
from bisect import bisect_right
import hashlib
import re


class SourceContextUnavailable(ValueError):
    pass


HEAD = re.compile(r'(?m)^[ \t]*Section[ \t]+(?P<number>\d+(?:\.\d+)+)[ \t]+(?=[A-Z])')
PAGE = re.compile(r'\s*\(Page\s+\d+(?:\s*[-–]\s*\d+)?\)\s*\Z')


def sha_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def normalized(text):
    tokens=list(re.finditer(r'\S+',text))
    starts=[];cursor=0
    for token in tokens:
        starts.append(cursor);cursor+=len(token.group())+1
    return ' '.join(t.group() for t in tokens),tokens,starts


def enclosing_section(parent,excerpt,*,max_characters=32768):
    """Return the exact whole section or refuse, never a favorable truncation."""
    if not isinstance(parent,str) or not isinstance(excerpt,str) or type(max_characters) is not int or max_characters<=0:
        raise ValueError('Text inputs and a positive declared section limit are required')
    anchor=PAGE.sub('',excerpt).strip()
    offered,tokens,starts=normalized(parent)
    wanted,_,_=normalized(anchor)
    if not wanted:
        raise SourceContextUnavailable('An empty excerpt cannot identify source context')
    occurrences=list(re.finditer(re.escape(wanted),offered))
    if len(occurrences)!=1:
        raise SourceContextUnavailable('The normalized literal excerpt is absent or ambiguous in its parent')
    hit=occurrences[0]
    first=bisect_right(starts,hit.start())-1
    last=bisect_right(starts,hit.end()-1)-1
    raw_start=tokens[first].start()+hit.start()-starts[first]
    raw_end=tokens[last].start()+hit.end()-starts[last]
    if ' '.join(parent[raw_start:raw_end].split())!=wanted:
        raise SourceContextUnavailable('The exact source anchor cannot be reconstructed')
    headers=list(HEAD.finditer(parent))
    preceding=[(i,h) for i,h in enumerate(headers) if h.start()<=raw_start]
    if not preceding:
        raise SourceContextUnavailable('The excerpt has no supported enclosing section header')
    index,header=preceding[-1]
    end=headers[index+1].start() if index+1<len(headers) else len(parent)
    start=header.start()
    if raw_end>end:
        raise SourceContextUnavailable('The excerpt crosses a section boundary; one section cannot cover it')
    if end-start>max_characters:
        raise SourceContextUnavailable('The full section exceeds its fixed input budget; no suffix is dropped')
    text=parent[start:end]
    receipt={'protocol':'unique-literal-enclosing-section-v1',
        'parent_text_sha256':sha_text(parent),'original_excerpt_sha256':sha_text(excerpt),
        'normalized_anchor_sha256':sha_text(wanted), 'anchor_occurrences':1,
        'parent_anchor_span':[raw_start,raw_end],'parent_section_span':[start,end],
        'section_number':header['number'],'section_sha256':sha_text(text),
        'section_characters':len(text),'max_characters':max_characters,
        'text_is_exact_parent_slice':True,'native_page_annotation_removed_only_for_matching':anchor!=excerpt.strip(),
        'answer_or_topic_keyword_used_for_selection':False,
        'syntactic_enclosing_section_complete':True,
        'cross_reference_closure_established':False,
        'native_task_scope_complete':False,
        'source_semantic_graph_or_native_answer_created':False}
    return text,receipt
