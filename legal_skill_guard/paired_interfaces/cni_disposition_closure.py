"""Check whether an operative disposition clause covers all controlled copies."""

import re


PROTECTED = re.compile(r'\bconfidential information\b', re.I)
COPIES = re.compile(r'\ball (?:such |the )?copies(?:\s*/\s*formats)?\s+(?:thereof|of)\b', re.I)
ACTIVE_DISPOSAL = re.compile(r'\breturn\b', re.I)
DUTY = re.compile(r'\b(?:shall|must|will|hereby undertakes)\b', re.I)
INLINE_OPERATIVE = re.compile(r'\b(?:shall|must|will)\b[^.;]{0,175}\breturn\b', re.I)
PASSIVE = re.compile(r'\b(?:shall|must|will) be returned\b', re.I)
FOLLOWUP = re.compile(r'\b(?:shall|must|will)\b[^.;]{0,100}\b(?:erase|destroy|delete)\b', re.I)
REQUEST = re.compile(r'\b(?:request|demand|completion of the purpose|terminate\w*|termination)\b', re.I)
SUBJECT = re.compile(r'\b(?:receiving party|recipient|consultant|each party)\b', re.I)
LEAD = re.compile(r'\b(?:each party shall|recipient hereby undertakes)\s*[:;]?$', re.I)
ITEM = re.compile(r'^\s*(?:\([a-z]\)|\d+\.\d+\.\d+\b)', re.I)
LATER_EXCEPTION = re.compile(
    r'\b(?:may|can|is entitled to|will be entitled to|permitted to)\s+(?:retain|keep|maintain)\b'
    r'|\b(?:archiv\w*|back.?up|(?:record|legal) cop(?:y|ies))\b'
    r'|\b(?:except|unless|provided,? however)\b[^.;]{0,170}\b(?:retain\w*|keep\w*)\b'
    r'|\bcop(?:y|ies)\b[^.;]{0,80}\b(?:may be (?:kept|retained)|may remain|are exempt)\b', re.I,
)


def proof(spans):
    """Close retention under a bound all-copy duty with no visible competing exception."""
    lines = [' '.join(s.split()) for s in spans]
    if any(LATER_EXCEPTION.search(line) for line in lines):
        return None
    for i, line in enumerate(lines):
        if not all(pattern.search(line) for pattern in (PROTECTED, COPIES, ACTIVE_DISPOSAL, REQUEST)):
            continue
        chain = [i]
        if PASSIVE.search(line):
            if not SUBJECT.search(line) or i + 1 >= len(lines):
                continue
            adjacent = lines[i + 1]
            if not (adjacent.casefold().startswith('upon receipt of such request')
                    and SUBJECT.search(adjacent) and FOLLOWUP.search(adjacent) and PROTECTED.search(adjacent)):
                continue
            chain.append(i + 1)
        elif not (SUBJECT.search(line) and INLINE_OPERATIVE.search(line)):
            if not ITEM.search(line):
                continue
            prior = [j for j in range(max(0, i - 8), i) if LEAD.search(lines[j]) and DUTY.search(lines[j])]
            if not prior:
                continue
            lead = prior[-1]
            if not all(ITEM.search(t) for t in lines[lead + 1:i] if t):
                continue
            chain.insert(0, lead)
        return {'answer': 'Contradiction', 'evidence': chain}
    return None
