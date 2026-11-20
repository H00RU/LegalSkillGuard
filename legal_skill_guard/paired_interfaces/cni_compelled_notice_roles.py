"""Bind a legally compelled notice duty to the source's information provider."""

import re

AUTHORITY = re.compile(
    r'\b(?:valid(?:ly)?\s+(?:subpoena|issued)|subpoenas?|judicial process|legal process|'
    r'court orders?|order by a court|orders? issued by a court|'
    r'government(?:al)?\s+(?:body|agenc\w*|authorit\w*)|(?:operation of|applicable) law|'
    r'legal requirement|required by law|order of a court)\b', re.I,
)
TRIGGER = re.compile(
    r'\b(?:request(?:s|ed|ing)? to disclos\w*|(?:required|compelled) to (?:be )?disclos\w*|'
    r'(?:disclos\w*|produc\w*)\b.{0,115}\b(?:pursuant to|in response to|in order to satisfy)|'
    r'(?:in response to|pursuant to|is otherwise required)\b.{0,115}\bdisclos\w*|'
    r'disclos\w*\b.{0,75}\bunder the terms of)\b', re.I,
)
ACTOR = r'(?:receiving party|recipient|disclosee|party receiving the request(?: for the information)?|you|[A-Z][A-Za-z]+)'
RECIPIENT = r'(?:the )?(?P<recipient>disclosing party|discloser|other party|[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)??)'
NOTIFY = re.compile(r'\b(?:notify|advise)\s+' + RECIPIENT + r'(?=\s+(?:in writing|of|as|by|and provide)\b|[,.;]|$)', re.I)
GIVES_NOTICE = re.compile(
    r'\b(?:gives?|provides?|presents?)\s+' + RECIPIENT
    + r'\s+(?:(?:with|as much)\s+){0,2}(?:(?:prompt|actual|prior|written)\s+){1,4}notice\b', re.I,
)
GIVEN_NOTICE = re.compile(
    r'\bshall\s+(?:first\s+)?have given (?:prior )?written notice of such required disclosure to\s+'
    + RECIPIENT + r'(?=\s+to allow\b|[,.;]|$)', re.I,
)
ACTOR_BEFORE = re.compile(r'\b(?:the )?(?P<actor>' + ACTOR + r')\s+(?:shall|must|will)\s+(?:first\s+|promptly\s+)?$', re.I)
GIVER_BEFORE = re.compile(r'\b(?:provided(?: that)?|except that)\s+(?:the )?(?P<actor>' + ACTOR + r')\s*$', re.I)
LEAD = re.compile(r'\b(?:the )?(?P<actor>' + ACTOR + r')\s+(?:agrees to|will|shall)\s*:?$', re.I)
PROVIDE = re.compile(r'\b(?:the )?(?P<actor>' + ACTOR + r')\s+provides\s+' + RECIPIENT + r'\s+with\s*:$', re.I)
FIRST = re.compile(r'^\s*\((?:i|a|1)\)\s*', re.I)
DUTY_ITEM = re.compile(r'^(?:(?:immediately|promptly|first)\s+)?(?:notify|advise)\b', re.I)
NOTICE_ITEM = re.compile(r'^(?:(?:prompt|actual|prior|written)\s+){1,4}notice of such (?:order|request|disclosure)', re.I)
REFERENCE = re.compile(
    r'^(?:\s+in writing)?(?:\s+immediately)?\s+(?:of (?:same|such (?:disclosure|requirement|request)|'
    r'the (?:court order|existence, terms and circumstances))|and provide\b[^;.!?]{0,110}'
    r'\bobjecting to production)\b', re.I,
)
FORMAL_RECEIVER = {'receiving party', 'recipient', 'disclosee', 'party receiving the request for the information',
                   'party receiving the request'}
FORMAL_PROVIDER = {'disclosing party', 'discloser', 'other party'}
PAIR_FLOW = (
    re.compile(r'\bprovided by one party \((?:the )?[“"](?P<provider>Provider)[”"]\) '
               r'to the other \((?:the )?[“"](?P<receiver>Recipient)[”"]\)', re.I),
    re.compile(r'\b(?:for\s+)?(?P<provider>[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?)\s+'
               r'(?:to |may )disclose to\s+(?P<receiver>[A-Z][A-Za-z]+)\s+'
               r'(?i:(?:certain\s+)?(?:confidential|proprietary))\b'),
    re.compile(r'\b(?:information|material|data) furnished to (?P<receiver>you)\b.{0,100}'
               r'\bby the (?P<provider>Company)\b', re.I),
    re.compile(r'\b(?P<provider>[A-Z]{2,}) proprietary (?:software|systems|data)[^;.!?]{0,28}'
               r'\bdisclosed to, or accessed by, (?P<receiver>[A-Z][A-Za-z]+)\b'),
    re.compile(r'\bthe (?P<receiver>contractor) will need access to (?P<provider>[A-Z]{2,}) '
               r'data, software, and computer systems\b'),
)


def roles(spans):
    return {(_case(m['receiver']), _case(m['provider'])): index
            for index, text in enumerate(spans)
            for form in PAIR_FLOW for m in form.finditer(text)}


def _case(text):
    return text.casefold().removeprefix('the ')


def affirm(actor, provider, pairs):
    actor, provider = _case(actor), _case(provider)
    if actor in FORMAL_RECEIVER and provider in FORMAL_PROVIDER:
        return True, None
    if (actor, provider) in pairs:
        return True, pairs[actor, provider]
    return False, None


def governed(lines):
    """Recognize same-sentence duties and uniquely governed first list items."""
    pairs = roles(lines)
    proofs = {}
    for i, text in enumerate(lines):
        if not (AUTHORITY.search(text) and TRIGGER.search(text)):
            continue
        candidates = []
        for pattern, context in ((NOTIFY, ACTOR_BEFORE), (GIVES_NOTICE, GIVER_BEFORE), (GIVEN_NOTICE, None)):
            for duty in pattern.finditer(text):
                head = text[:duty.start()]
                if not (AUTHORITY.search(head) and TRIGGER.search(head)):
                    continue
                if pattern is not GIVEN_NOTICE and not REFERENCE.match(text[duty.end():]):
                    continue
                actor = (context.search(head) if context is not None
                         else re.search(r'\b(?:the )?(?P<actor>' + ACTOR + r')\s*$', head, re.I))
                if actor is None:
                    continue
                candidates.append((actor['actor'], duty['recipient'], i))
        if i + 1 < len(lines) and (item := FIRST.match(lines[i + 1])) is not None:
            content = lines[i + 1][item.end():]
            if ((head := LEAD.search(text)) and DUTY_ITEM.match(content) and (duty := NOTIFY.search(content))
                    and REFERENCE.match(content[duty.end():])):
                candidates.append((head['actor'], duty['recipient'], i + 1))
            if (head := PROVIDE.search(text)) and NOTICE_ITEM.match(content):
                candidates.append((head['actor'], head['recipient'], i + 1))
        for actor, provider, duty_index in candidates:
            matched, role_span = affirm(actor, provider, pairs)
            if matched:
                key = (i, duty_index)
                proofs[key] = {'trigger': i, 'duty': duty_index, 'role_context': role_span}
    return [proofs[key] for key in sorted(proofs)]


def project(native, proofs):
    if not proofs:
        return native
    evidence = sorted({proof[field] for proof in proofs for field in ('trigger', 'duty')})
    return {**native, 'answer': 'Entailment', 'evidence_sentence_ids': evidence, 'handled': True}
