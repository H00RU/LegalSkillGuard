"""Attach exact citizenship statements and claim sentences to Diversity units."""

from copy import deepcopy
import re

from legal_skill_guard.paired_interfaces import diversity_relational, relational_program
from legal_skill_guard.skill_evolution.objects import digest


def excerpts(source_text, scope):
    """Locate literal source clauses by public names and roles, without evaluating them."""
    sentence_rows = [match[0].strip() for match in re.finditer(r'[^.]+\.', source_text) if match[0].strip()]
    people = scope['plaintiffs'] + scope['defendants']
    citizenship = {}
    for person in people:
        citizenship[person], = (sentence for sentence in sentence_rows if sentence.startswith(person + ' is from '))
    claims = {}
    for sentence in sentence_rows:
        match = re.match(r'(.+?) (?:both sue|sues|sue) (.+?)(?: each)? for ', sentence)
        if match is None:
            continue
        for plaintiff in match[1].split(' and '):
            for defendant in match[2].split(' and '):
                key = (plaintiff, defendant)
                if key in claims:
                    raise ValueError('Duplicate claim sentence in a single-pair Diversity view')
                claims[key] = sentence
    return citizenship, claims


class Provider(diversity_relational.Provider):
    """Give every reader the same pair-specific contiguous evidence excerpts."""

    def views(self, source):
        view, = super().views(source)
        text = view['read_input']['source_text']
        citizenship, claims = excerpts(text, diversity_relational.locator(text))
        requests = deepcopy(view['read_input']['unit_requests'])
        for unit in requests:
            entities = unit['entities']
            plaintiff, defendant = entities['plaintiff'], entities['defendant']
            if unit['source_anchor'].startswith('citizenship_pair_'):
                unit['source_excerpts'] = [citizenship[plaintiff], citizenship[defendant]]
            else:
                unit['source_excerpts'] = [claims[plaintiff, defendant]]
        view['read_input']['unit_requests'] = requests
        for plan in view['plans']:
            program = plan['relational_program']
            plan['system'] += ('\nEach request gives the exact source excerpts for that local unit. '
                               'Use its own excerpts and include the excerpts verbatim as source_text evidence. '
                               'For a citizenship pair, read both named statements in the order given.')
            plan['reader_template_sha256'] = relational_program.template_version(
                program, system=plan['system'], public_rules=view['read_input']['rules'],
                protocol='diversity_pair_bound_source_excerpts_v1')
            plan['version'] = digest({key: value for key, value in plan.items() if key != 'version'})
        return [view]
