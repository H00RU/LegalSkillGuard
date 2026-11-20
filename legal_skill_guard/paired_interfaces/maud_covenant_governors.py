"""Compile clause anchors with an explicit governor of enumerated restrictions."""

from itertools import product
import re

from legal_skill_guard.paired_interfaces import maud_covenant_anchors as anchors
from legal_skill_guard.paired_interfaces import maud_operative_edges as edges


BARE_PROHIBITION = re.compile(r'\b(?:shall|will)\s+not(?=\s*\(\s*unless\b)', re.I)
INDIRECT_PROHIBITION = re.compile(
    r'\b(?:shall|will)\s+not\s+directly\s+or\s+indirectly'
    r'(?:,\s*including\s+through\s+any\s+Subsidiary)?(?=\s*:)', re.I,
)
COLLECTIVE_PROHIBITION = re.compile(
    r'\bnone of\s+[^:;.<>]{1,100}?\bshall\s*,\s*and\s+[^:;.<>]{1,100}?\bshall\s+cause\s+'
    r'[^:;.<>]{1,100}?\bSubsidiaries\s+not\s+to\b', re.I,
)
LIST_TAIL = re.compile(r'\s*(?:,\s*do any of the following)?\s*:', re.I)
ITEM = re.compile(r'\s*(?:\([a-z]+\)|\(Page \d+\)\s*$|$)', re.I)
EXCLUDED = 'excluded'
UNRESOLVED = 'unresolved'


def after_proviso(text, end):
    """Skip one balanced modifier, preserving offsets through nested parentheses."""
    left = end + len(text[end:]) - len(text[end:].lstrip())
    if left == len(text) or text[left] != '(':
        return end
    depth = 0
    for pos in range(left, len(text)):
        char = text[pos]
        if char == '<':
            return None
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if not depth:
                return pos + 1
    return None


def supplemental_inventory(excerpts, legacy):
    """Add literal prohibitions governing the list, keeping matched legacy anchors."""
    found = {}
    for excerpt, text in excerpts.items():
        for pattern in (BARE_PROHIBITION, INDIRECT_PROHIBITION, COLLECTIVE_PROHIBITION):
            for head in pattern.finditer(text):
                start = head.start()
                if any(row['excerpt'] == excerpt and row['candidate_family'] == 'negative'
                       and row['range'][0] <= start < row['range'][1] for row in legacy.values()):
                    continue
                end = after_proviso(text, head.end())
                if end is None or (tail := LIST_TAIL.match(text, end)) is None:
                    continue
                if not ITEM.match(text, tail.end()):
                    continue
                heading = next(reversed(list(anchors.SECTION.finditer(text, 0, start))), None)
                found[f'clause_{len(legacy) + len(found) + 1}'] = {
                    'excerpt': excerpt, 'range': [start, tail.end()], 'quote': text[start:tail.end()],
                    'candidate_family': 'negative', 'preceding_section_heading': heading[0].strip() if heading else None,
                }
    return found


def joint_values(inventory):
    """Enumerate canonical pairs so a response cannot assert one family twice."""
    domains = {
        family: [*(key for key, item in inventory.items() if item['candidate_family'] == family),
                 EXCLUDED, UNRESOLVED]
        for family in edges.FAMILIES
    }
    return {f'ordinary={ordinary};negative={negative}': (ordinary, negative)
            for ordinary, negative in product(*(domains[f] for f in edges.FAMILIES))}


def project(inventory, values):
    ports = []
    for family, value in zip(edges.FAMILIES, values, strict=True):
        if value == EXCLUDED:
            ports.append(False)
        elif value == UNRESOLVED:
            ports.append(None)
        elif inventory[value]['candidate_family'] == family:
            ports.append(True)
        else:
            raise ValueError('An operative relation must refer to its own covenant family')
    return tuple(ports)


def check_equivalence():
    inventory = {family: {'candidate_family': family} for family in edges.FAMILIES}
    compiled = joint_values(inventory)
    canonical = {project(inventory, pair) for pair in compiled.values()}
    if len(compiled) != 9 or canonical != set(product((None, False, True), repeat=2)):
        raise ValueError('The joint response must preserve all partial edge states')
    return edges.check_equivalence()
