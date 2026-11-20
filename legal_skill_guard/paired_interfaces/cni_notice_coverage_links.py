"""Separate lawful disclosure exceptions from notice of a disclosure demand."""

import re

ORDER = r'(?:the (?:order|mandate) of )?(?:a |any )?(?:governmental agency|legislative body|court|legal process|law|regulatory authority)'
BARE_EXCEPTION = re.compile(
    rf'^(?:\(?[a-z]\)?[.)]?\s+)?(?:information which )?is required to be disclosed by {ORDER}\b'
    r'[^;:.]{0,115}\.?$', re.I,
)
CONSENT_EXCEPTION = re.compile(
    r'\bwill disclose such information only pursuant to the express written permission of the party who made '
    r'such information available save where\b[^.;]{0,140}\bunder the order of '
    r'a competent (?:court|government agency)\b', re.I,
)
PATIENT_EXCEPTION = re.compile(
    r'\bwill not disclose any phi\b[^.;]{0,130}\bupon receiving a written authorization from the patient '
    r'\(unless otherwise required by applicable law\)', re.I,
)
POTENTIAL_NOTICE = re.compile(
    r'\b(?:notic\w*|notif\w*|inform(?:s|ing)?|advis(?:e[sd]?|ing)|alert\w*|warn\w*|'
    r'(?:shall|will|must|should|to|promptly|immediately)(?: promptly| immediately)? (?:inform|consult|contact)|'
    r'notice thereof|provide\w*[^.;]{0,80}(?:copy of (?:the |such )?(?:request|subpoena|order)|'
    r'opportunity to (?:intervene|object))|send\w*[^.;]{0,45}(?:order|subpoena|request)|'
    r'communicat\w*[^.;]{0,45}(?:request|order|demand)|'
    r'(?:request|order|demand|subpoena)[^.;]{0,75}be (?:sent|communicated|reported|provided|forwarded))\b', re.I,
)
SERVICE = re.compile(
    r'^(?:\d+\.\s+)?any (?:written )?notice (?:or other communication )?'
    r'(?:required or allowed to be given hereunder shall be deemed to have been duly and properly '
    r'given and delivered|made or given by any party in connection with this agreement shall be sent via)',
    re.I,
)
TERMINATION_NOTICE = re.compile(r'\bmay terminate\b[^.;]{0,150}\bby giving\b[^.;]{0,70}\bwritten notice\b', re.I)
ADDRESS_NOTICE = re.compile(r'^or such other address\b[^.;]{0,125}\bnotify in writing\b[^.;]{0,105}'
                            r'\bin case of changes of the above addresses\b', re.I)
NEGOTIATION_COUNSEL = re.compile(r'\bample opportunity to consult legal, financial and other counsel\b', re.I)
SECURITY_REPORT = re.compile(r'^if i suspect that my user id or password has been compromised, '
                             r'i should immediately contact\b', re.I)
PROCESS_REQUEST = re.compile(
    r'\breceives? a subpoena or other validly issued administrative or judicial process requesting '
    r'confidential information\b', re.I,
)
REQUEST_COUNSEL = re.compile(
    r'\brecipient shall provide prompt actual notice to the general counsel of\s+(?P<provider>[A-Z][A-Za-z ]+?) '
    r'of such receipt, providing (?:the |such )?\w+(?: \w+)? with a reasonable opportunity to intervene\b', re.I,
)
MUTUAL_COUNSEL = re.compile(
    r'\bthe receiving party shall provide prompt actual notice to, in the case of (?:<[^>]+>|[^,;]+), '
    r'the general counsel of (?:<[^>]+>|[^,;]+), and, in the case of [^,;]+, to the general counsel of '
    r'[^,;]+, of such receipt, providing the party with a reasonable opportunity to intervene\b', re.I,
)
GOVERNING_FLOW = re.compile(
    r'\b(?:confidential information (?:disclosed|furnished|provided) (?:to the recipient )?by|'
    r'recipient (?:may|will) (?:receive|have access to) (?:the )?confidential information of)\s+', re.I,
)


def counsel_witness(lines):
    results = []
    for index, line in enumerate(lines):
        request = PROCESS_REQUEST.search(line)
        if request is None:
            continue
        following = line[request.end():]
        if following.casefold().startswith(' received from the other') and MUTUAL_COUNSEL.search(following):
            results.append(index)
        if match := REQUEST_COUNSEL.search(following):
            who = re.escape(match['provider'].strip())
            flow = re.compile(
                rf'{GOVERNING_FLOW.pattern}{who}\b|'
                rf'^in consideration of {who}[’\']s\b[^.;]{{0,90}}\bprovision of access to '
                r'certain confidential information by recipient\b', re.I,
            )
            if any(flow.search(prior) for prior in lines[:index]):
                results.append(index)
    return results


def bind(spans, trigger_spans):
    """Certify a counsel duty or a checked, separate disclosure exception."""
    lines = [' '.join(text.split()) for text in spans]
    hits = counsel_witness(lines)
    if len(hits) == 1:
        return {'kind': 'provider_counsel', 'answer': 'Entailment', 'evidence_sentence_ids': hits}
    if hits or len(trigger_spans) != 1:
        return None
    trigger, = trigger_spans
    if not any(rule.search(lines[trigger]) for rule in (BARE_EXCEPTION, CONSENT_EXCEPTION, PATIENT_EXCEPTION)):
        return None
    distinct = (SERVICE, TERMINATION_NOTICE, ADDRESS_NOTICE, NEGOTIATION_COUNSEL, SECURITY_REPORT)
    notices = []
    for index, line in enumerate(lines):
        candidates = list(POTENTIAL_NOTICE.finditer(line))
        if not candidates:
            continue
        unrelated = [match.span() for rule in distinct for match in rule.finditer(line)]
        if index == trigger or any(not any(left <= match.start() < right for left, right in unrelated)
                                   for match in candidates):
            return None
        notices.append(index)
    return {'kind': 'disclosure_exception_only', 'answer': 'NotMentioned', 'evidence_sentence_ids': [],
            'disclosure_span': trigger, 'separate_notice_spans': notices}
