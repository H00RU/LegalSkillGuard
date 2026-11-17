"""Compile the published domestic standard-weight fee clauses into a local consumer."""

import re

from legal_skill_guard.skill_evolution.objects import digest

DOMESTIC = 'Within and between U.S., Canada, Puerto Rico and U.S. Virgin Islands'
STANDARD_WEIGHT_CABINS = frozenset({'Basic Economy', 'Main Cabin', 'Main Plus', 'Premium Economy'})


def public_domestic_scope(public):
    from legal_skill_guard.paired_interfaces.native_adapters import public_geography

    header = re.search(
        r'^.+? is an? (.+?) Class passenger flying from (.+?) to (.+?) with the following items:',
        public.get('facts', ''))
    if not header or header[1] not in STANDARD_WEIGHT_CABINS:
        return None
    countries = public_geography()
    if any(countries.get(city) != 'U.S.' for city in header.groups()[1:]):
        return None
    return {'cabin': header[1], 'origin': header[2], 'destination': header[3],
            'explicit_public_trip_sha256': digest(header[0])}


def section(source, heading):
    lines = source.splitlines()
    matches = [i for i, line in enumerate(lines) if line.strip() == heading]
    if len(matches) != 1:
        raise ValueError('The published rule section is missing or ambiguous')
    start = matches[0]
    level = len(heading) - len(heading.lstrip('#'))
    end = next((i for i in range(start + 1, len(lines))
                if re.match(rf'^#{{1,{level}}} ', lines[i])), len(lines))
    return lines[start + 1:end]


def table_fees(lines, region, columns):
    header = None
    for line in lines:
        if not line.startswith('|'):
            continue
        row = [value.strip().rstrip('^') for value in line.strip().strip('|').split('|')]
        if row[0] in ('Regions', 'Region'):
            header = row
        elif row[0] == region:
            if header is None:
                raise ValueError('The published fee row has no typed header')
            result = []
            for column in columns:
                value = row[header.index(column)]
                if not re.fullmatch(r'\$[0-9]+', value):
                    raise ValueError('A rule fee is outside the exact USD consumer')
                result.append(int(value[1:]))
            return result
    raise ValueError('The bound regional fee row is missing')


def compile_rule(source, *, cabin='Main Plus'):
    """Bind table entries, thresholds, allowances, and the source’s combiner."""
    if cabin not in STANDARD_WEIGHT_CABINS:
        raise ValueError('Cabin has a different complimentary baggage weight rule')
    column = 'Main Cabin' if cabin == 'Main Plus' else cabin
    first = section(source, '### First Bag')
    second = section(source, '### Second Bag')
    first_fee, = table_fees(first, 'Within and between U.S., Puerto Rico and U.S. Virgin Islands', [column])
    second_fee, = table_fees(second, DOMESTIC, [column])
    third, = table_fees(section(source, '### Third Bag'), DOMESTIC, [column])
    fourth, = table_fees(section(source, '### Fourth Bag +'), DOMESTIC, [column])
    if cabin == 'Main Plus':
        allowance = '^Main Plus includes 1 extra free checked bag in addition to the Main Cabin allowance (max of 2).'
        if allowance not in first or allowance not in second or first_fee == 0 or second_fee == 0:
            raise ValueError('The explicit Main Plus allowance is outside this consumer')
        first_fee = 0
    weight = section(source, '#### Overweight Bags')
    if not any('The higher fee between oversize and overweight applies, in addition to the checked bag fee.' in line
               for line in weight):
        raise ValueError('The source does not establish the checked-bag combiner')
    weight_schedule = []
    for heading, region in (
        ('##### Over 50 lbs / 23 kgs to 53 lbs / 24 kgs', 'All Regions'),
        ('##### Over 53 lbs / 24 kgs to 70 lbs / 32 kgs', DOMESTIC),
        ('##### Over 70 lbs / 32kgs to 100 lbs / 45 kgs', DOMESTIC),
    ):
        upper = int(re.search(r'to (\d+) lbs', heading)[1])
        fee, = table_fees(section(source, heading), region, [column])
        weight_schedule.append([upper, fee])
    size_columns = ['Over 62 in / 158 cm – 65 in / 165 cm', 'Over 65 in / 165 cm – 115 in / 292 cm']
    small, large = table_fees(section(source, '#### Oversize Bags'),
                              'Between U.S., Puerto Rico, U.S. Virgin Islands and Canada', size_columns)
    carry = re.findall(r'cannot exceed (\d+) x (\d+) x (\d+) inches', source)
    if len(carry) != 1:
        raise ValueError('Carry-on dimensions must be independently stated')
    return {
        'public_rule_sha256': digest(source), 'scope': 'domestic_' + cabin.replace(' ', '_'),
        'base_fees': [first_fee, second_fee, third, fourth],
        'oversize_schedule': [[62, 0], [65, small], [115, large]],
        'overweight_schedule': [[50, 0], *weight_schedule],
        'carry_on_dimensions': sorted(map(int, carry[0])), 'joint_surcharge_combiner': 'max',
    }


def local_charges(rule, bags):
    """Apply the compiled local rule to explicit measurements without native labels."""
    if len(bags) < 2 or len(bags) - 1 > 10:
        raise ValueError('The checked inventory is outside the bounded domestic scope')
    if any(len(bag['dimensions']) != 3 or any(type(x) is not int or x <= 0 for x in bag['dimensions'])
           or type(bag['weight']) is not int or bag['weight'] <= 0 for bag in bags):
        raise ValueError('Explicit integer dimensions and weight are required')
    eligible = [i for i, bag in enumerate(bags) if all(
        dimension <= bound for dimension, bound in zip(sorted(bag['dimensions']), rule['carry_on_dimensions'], strict=True))]
    if eligible != [0]:
        raise ValueError('The scope requires exactly one eligible named carry-on')
    rows = []
    for ordinal, bag in enumerate(bags[1:]):
        dimensions = bag['dimensions']
        weight = bag['weight']
        total = sum(dimensions)
        size = next((fee for limit, fee in rule['oversize_schedule'] if total <= limit), None)
        heavy = next((fee for limit, fee in rule['overweight_schedule'] if weight <= limit), None)
        if size is None or heavy is None:
            raise ValueError('A checked bag exceeds the accepted measurement domain')
        rows.append({'bag_id': ordinal + 2, 'base_fee': rule['base_fees'][min(ordinal, 3)],
                     'oversize': size, 'overweight': heavy})
    return rows
