"""Keep an agreement's termination trigger separate from the surviving duty."""

import re

AGREEMENT = r'this (?:confidentiality agreement|non-disclosure agreement|agreement|cnda|nda)'
MAY_TERMINATE = re.compile(
    rf'\b(?:either|each|any) party may terminate (?P<instrument>{AGREEMENT})\b', re.I,
)
NAMED_TERMINATION = re.compile(rf'\b(?:termination|expiration) of (?P<instrument>{AGREEMENT})\b', re.I)
RETURN_TRIGGER = re.compile(r'\b(?:notwithstanding|after|following) (?:the )?'
                            r'(?:delivery|destruction|return)\b', re.I)
EARLIER = re.compile(r'\b(?:prior|existing|earlier) (?:confidentiality )?agreements?\b', re.I)
SIGNATURE = re.compile(r'\bsurvive the (?:execution|signing|delivery)\b', re.I)
SOLE_DISCLOSURE = re.compile(r'\b(?:after|from) the date of the last disclosure\b', re.I)
OBLIGATION = r'(?:obligations?|dut(?:y|ies)|restrictions?|covenants?)'
OWN_DUTY = re.compile(
    rf'\b{OBLIGATION}\b.{{0,180}}?\b(?:hereunder|under {AGREEMENT}|during the term of {AGREEMENT})\b', re.I,
)
SURVIVES = re.compile(r'\b(?:shall|will) survive\b', re.I)
REMAINS = re.compile(r'\b(?:shall|will) remain effective\b', re.I)
ANAPHORIC = re.compile(r'\b(?:notwithstanding|after|following) any such termination\b'
                       r'|\bsurvive any such termination\b', re.I)
TRANSITION = re.compile(r'\bprovided(?:,? however)?,? that\b', re.I)
HEADING = re.compile(r'^\s*(?:\d+(?:\.\d+)*\.|[IVX]+\.)\s+')
EXPLICIT_OTHER_END = re.compile(r'\btermination of the (?:relationship|working relationship)\b', re.I)
NO_DUTY = re.compile(rf'\b(?:no|none of the)\s+.{{0,50}}?\b{OBLIGATION}\b', re.I)
ENDS_AT_EVENT = re.compile(r'^\s+(?:only\s+)?(?:until|up to|through|before|prior to|pending|during)\b', re.I)


def named_duty(span):
    cue = NAMED_TERMINATION.search(span)
    if cue is None:
        return False
    own = re.escape(cue['instrument'])
    pattern = rf'\bshall not affect the survival of\b.{{0,95}}?\b{OBLIGATION} under {own}\b'
    return bool(re.search(pattern, span[cue.end():], re.I))


def support(spans):
    """Return operative spans and separate antecedent IDs for same-agreement clauses."""
    paths = []
    for index, text in enumerate(spans):
        if NO_DUTY.search(text):
            continue
        if named_duty(text):
            paths.append({'operative': index, 'trigger': index})
            continue
        force = SURVIVES.search(text) or REMAINS.search(text)
        if force and OWN_DUTY.search(text[:force.start()]) and not EARLIER.search(text[:force.start()]):
            event = text[force.end():].split(';', 1)[0]
            if (NAMED_TERMINATION.search(event) and not ENDS_AT_EVENT.match(event)
                    and not SIGNATURE.search(text[force.start():])):
                paths.append({'operative': index, 'trigger': index})
                continue
        transition = TRANSITION.search(text)
        if transition and MAY_TERMINATE.search(text[:transition.start()]):
            obligation = text[transition.end():]
            if OWN_DUTY.search(obligation) and SURVIVES.search(obligation) and ANAPHORIC.search(obligation):
                paths.append({'operative': index, 'trigger': index})
                continue
        if (index and not HEADING.match(text) and ANAPHORIC.match(text)
                and MAY_TERMINATE.search(spans[index - 1])
                and not EXPLICIT_OTHER_END.search(spans[index - 1])
                and OWN_DUTY.search(text) and SURVIVES.search(text)):
            paths.append({'operative': index, 'trigger': index - 1})
    return paths


def referenced_events(spans, citations):
    """Classify narrower timing anchors without treating them as an absence finding."""
    kinds = set()
    for index in citations:
        text = spans[index]
        if SIGNATURE.search(text):
            kinds.add('prior_agreement_execution' if EARLIER.search(text) else 'execution')
        if RETURN_TRIGGER.search(text):
            kinds.add('return_or_destruction')
        if SOLE_DISCLOSURE.search(text):
            kinds.add('last_disclosure')
        if EXPLICIT_OTHER_END.search(text):
            kinds.add('relationship_end')
    return sorted(kinds)


def project(native, paths, *, include_antecedent):
    if not paths:
        return native
    citations = {p['operative'] for p in paths}
    if include_antecedent:
        citations.update(p['trigger'] for p in paths)
    return {'answer': 'Entailment', 'evidence_sentence_ids': sorted(citations)}
