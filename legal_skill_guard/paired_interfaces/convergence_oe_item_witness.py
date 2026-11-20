"""Establish affirmative federal item claims under the question's own rules."""

import re

from legal_skill_guard.paired_interfaces import convergence_oe_ec_identity as identity
from legal_skill_guard.paired_interfaces import convergence_oe_federal_item_cap as federal
from legal_skill_guard.paired_interfaces import convergence_oe_public_scope as public
from legal_skill_guard.paired_interfaces import convergence_oe_title_scope as title


def eligible_kind(name):
    head, *_ = re.split(r'\s+(?:with|made of|made from)\s+', name, maxsplit=1, flags=re.I)
    if re.search(r',|;|/|\b(?:and|kit|bundle|pair|set|parts?|replacement)\b', head, re.I):
        return False
    return any(match.end() == len(head) for match in federal.TYPE.finditer(head))


def proof(view, mode):
    """Return literal title-bound claims. EC eligibility does not require a full exemption."""
    text = view['public']['original_input']
    allowed = public.supplied_jurisdiction_scope(text)
    if not allowed or federal.CITATION not in allowed['citations']:
        return {}
    if view['id'] == 'EV':
        return {name: federal.expected(fact, mode) for name, fact in federal.scope(view).items()
                if eligible_kind(name)}
    if view['id'] != 'EC':
        return {}
    prompt, _, statutes = text.partition('\nStatutes:\n')
    if federal.PERSONAL not in prompt:
        return {}
    bodies = [body for block in statutes.partition('\nSolved Reasoning Steps:\n')[0].strip().split('\n\n')
              for heading, _, body in [block.partition('\n')] if heading == federal.CITATION]
    if len(bodies) != 1 or not federal.LAW.fullmatch(bodies[0]):
        return {}
    try:
        _, assets, _ = title.title_inventory(text)
    except ValueError:
        return {}
    return {row['description']: True for row in assets.values()
            if row['filing_interest_established'] is True and eligible_kind(row['description'])
            and federal.cents(row['amount_quote']) > 0 and not federal.BUSINESS.search(row['source_quote'])}


def observed(task, answer, asset):
    if task == 'EC':
        return bool(federal.CITATION in answer.get(asset, ()))
    return frozenset(federal.observed(answer, asset))


def compare(task, incumbent, proposal, proofs):
    if not isinstance(incumbent, dict) or not isinstance(proposal, dict):
        return [], []
    repaired, regressed = [], []
    for asset, value in proofs.items():
        expected = value if task == 'EC' else frozenset({value})
        a, b = (observed(task, answer, asset) == expected for answer in (incumbent, proposal))
        if a != b:
            (repaired if b else regressed).append(asset)
        elif task == 'EV' and not b:
            # A new positive amount above the cap refutes the candidate even if the incumbent omitted it.
            previous, current = (observed(task, answer, asset) for answer in (incumbent, proposal))
            if any(amount > value for amount in current - previous):
                regressed.append(asset)
    return repaired, regressed


def project(view, answer, proofs):
    if not isinstance(answer, dict) or not proofs:
        return answer
    task = view['id']
    result = dict(identity.bind(view, answer) if task == 'EC' else answer)
    for asset, value in proofs.items():
        current = list(result.get(asset, ()))
        if task == 'EC':
            if federal.CITATION not in current:
                result[asset] = [*current, federal.CITATION]
        elif observed(task, result, asset) != {value}:
            result[asset] = [row for row in current if row['citation'] != federal.CITATION]
            result[asset].append({'citation': federal.CITATION, 'claim_value': value / 100})
    return result
