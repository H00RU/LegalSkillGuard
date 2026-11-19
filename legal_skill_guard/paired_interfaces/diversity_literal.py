"""Source-bound Diversity literal readings and prefix-only interface selection."""

import re

from legal_skill_guard.paired_interfaces import diversity_claim_groups, diversity_relational, relational_program, residual
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.skill_evolution.objects import digest


DATASET = 'LegalBench_Diversity'
DOLLARS = r'\$(?:[1-9][0-9]{0,2}(?:,[0-9]{3})+|[1-9][0-9]*|0)'
CLAIM = rf'[A-Za-z]+(?: [A-Za-z]+)* for ({DOLLARS})'
CLAUSES = {count: re.compile(' and '.join([CLAIM] * count) + r'\.') for count in (1, 2)}


def coordinates(unit, excerpts):
    fields = unit['entity_context']
    if 'claim_count' in fields:
        (quote,) = excerpts
        _, separator, body = quote.partition(' for ')
        pattern = CLAUSES.get(fields['claim_count'])
        match = pattern.fullmatch(body) if separator and pattern else None
        if not match:
            raise ValueError('Unsupported literal Diversity claim construction')
        amounts = [int(s[1:].replace(',', '')) for s in match.groups()]
        if any(amount % 1000 for amount in amounts):
            raise ValueError('Fractional thousands are outside this consumer domain')
        return {f'claim{i}': min(amount // 1000, 76) for i, amount in enumerate(amounts)}
    result = {}
    for role, quote in zip(('plaintiff', 'defendant'), excerpts, strict=True):
        match = re.fullmatch(re.escape(fields[role]) + r' is from ([A-Za-z]+(?: [A-Za-z]+)*)\.', quote)
        if match is None or match[1] not in diversity_relational.STATES:
            raise ValueError('Citizenship requires a bound literal state')
        result[f'{role}_state'] = match[1]
    return result


def measure(source, view, plan):
    diversity_claim_groups.Provider().verify_plan(source, view, plan)
    program = plan['relational_program']
    excerpts = {v['source_anchor']: v['source_excerpts'] for v in view['read_input']['unit_requests']}
    text = source['views'][0]['public']['source_text']
    if set(excerpts) != set(program['units']) or text != view['relational_public_source']['source_text']:
        raise ValueError('Literal evidence must bind the original source and candidate units')
    raw, source_coordinates = {}, {}
    for anchor, unit in program['units'].items():
        quotes = excerpts[anchor]
        if any(not q or text.count(q) != 1 for q in quotes):
            raise ValueError('Each literal evidence fragment must have a unique source occurrence')
        source_coordinates[anchor] = coordinates(unit, quotes)
        values = residual.encode(unit['asset']['features'], source_coordinates[anchor])
        raw[anchor] = {'status': 'complete', 'observation': {'source_anchor': anchor, 'relations': values},
                       'evidence': [{'field': 'source_text', 'quote': q} for q in quotes]}
    result = relational_program.decode(program, raw, view['relational_public_source'])
    if any(not item['consumer']['valid'] for item in result['local_receipts'].values()):
        raise ValueError('Literal reading produced a value outside a certified consumer domain')
    return {'channel': 'verified_public_literal_v1', 'source_public_sha256': digest(source),
            'plan_version': plan['version'], 'program_sha256': program['program_sha256'],
            'literal_read_sha256': digest(raw), 'source_coordinates_sha256': digest(source_coordinates),
            'coordinate_count': sum(len(x['observation']['relations']) for x in raw.values()),
            'outputs': result['outputs'], 'diagnostics': result['diagnostics'], 'physical_model_call': False}


def template(plan):
    return plan['reader_template_sha256']


def snapshot(batch, prior, keys, rows):
    if (batch == 0 and (prior is not None or keys or rows)
            or batch > 0 and (prior is None or verify(prior, 'snapshot_sha256')['batch'] != batch - 1)):
        raise ValueError('A revised Diversity library advances one chronological prefix at a time')
    prefix = ([] if prior is None else prior['visible_TRAIN']) + list(keys)
    all_rows = ([] if prior is None else prior['candidate_records']) + list(rows)
    pairs = {(r['source'], r['template']) for r in all_rows}
    if (len(prefix) != len(set(prefix)) or {r['source'] for r in rows} != set(keys)
            or len(all_rows) != len(pairs)):
        raise ValueError('The library must bind each visible TRAIN mother once')
    return sealed({'channel': 'verified_public_literal_v1', 'batch': batch, 'visible_TRAIN': prefix,
                   'parent_library_sha256': None if prior is None else prior['snapshot_sha256'],
                   'candidate_records': all_rows}, 'snapshot_sha256')


def choose(source, view, library, *, learned):
    verify(library, 'snapshot_sha256')
    plans = view['plans']
    fixed, = (p for p in plans if p['is_correct_fixed_raw_control'])
    if not learned:
        return fixed, {'mode': 'information_matched_fixed', 'paired_TRAIN': 0}
    first = {template(p): {} for p in plans}
    for row in library['candidate_records']:
        if row['template'] in first and row['source'] != source['key']:
            first[row['template']][row['source']] = row
    shared = sorted(set.intersection(*(set(r) for r in first.values())))
    if not shared:
        return fixed, {'mode': 'fixed_no_paired_TRAIN', 'paired_TRAIN': 0}

    def rank(plan):
        matched = [first[template(plan)][key] for key in shared]
        return (-sum(r['grounded_native'] for r in matched), sum(r['coordinate_count'] for r in matched),
                not plan['is_correct_fixed_raw_control'], template(plan))

    chosen = min(plans, key=rank)
    return chosen, {'mode': 'paired_TRAIN_native_then_coordinate_count', 'paired_TRAIN': len(shared),
                    'paired_TRAIN_sha256': digest(shared), 'fixed_coordinate_total': rank(fixed)[1],
                    'chosen_coordinate_total': rank(chosen)[1]}
