"""Manual source-only reviews of all four fixed Airline TRAIN views.

All 35 item rows, itinerary/cabin/ticket assertions and original relations were
read against the entire supplied units. No question, fee result, grading,
reference parameters or hidden construction data is used.
"""
import json

from experiments.two_method_source_reviews import BASE, persist_review
from legal_skill_guard.skill_evolution.objects import digest


def corrections(indices):
    return [{'operation': 'source_relation_status_correction', 'index': index,
             'predicate': 'owner', 'before': 'stated', 'after': 'not_stated'} for index in indices]


LIMITATIONS = [
    {'operation': 'source_scope_limitation', 'text': 'The passenger is accompanied by the listed items, but the source does not state legal title to each bag; keep source ownership not_stated.'},
    {'operation': 'source_scope_limitation', 'text': 'Each dimension triple and its order is literal source data; length/width/height are positional interface names, not separately established physical axes. No checked/carry-on/personal-item classification or fee is inferred.'}]

REVIEWS = {
    'RuleArena_Airline:51954a46': {
        'graph_sha256': 'ad1404607a9a3a1667d7a4408695cb8c7a30f4a05ebf93d5d624adc68f9a2e91',
        'units_sha256': 'c58bb8f91a8e32866651a84a4629abb60892c4049620dcbfa46a487961706902',
        'review': 'All ten supplied units, thirteen nodes and fifty-three original relations were checked. Michael, the ordered Orlando/Lima itinerary, Business cabin and ticket amount557 are explicit. All eight distinct bags and their category, three ordered dimension components and weight agree with their own unit. The 51,53,63,67,72,95-pound entries are not reclassified. Numbered bag display names are projected only to their own existing literal quotes. Flying does not assert a SARA employment-service relationship, and a city is not itself a domestic or program-specific South-America route class; remove those unsupported concept tags without changing the cities or route. Accompaniment does not establish legal ownership, so only the eight bag-owner assertions become not_stated. Ticket possession, original unchecked-bag/payment-date unknowns and all numerical strings stay unchanged. This is source-local evidence, not a complete fee-case gold assertion.',
        'evidence': [
            {'unit_id': 0, 'quote': 'Michael is a Business Class passenger flying from Orlando to Lima'},
            {'unit_id': 1, 'quote': '18 x 13 x 7 inches, 8 lbs'},
            {'unit_id': 5, 'quote': '43 x 22 x 19 inches, 53 lbs'},
            {'unit_id': 8, 'quote': '33 x 20 x 12 inches, 53 lbs'},
            {'unit_id': 9, 'quote': "Michael's flight ticket is $557"}],
        'project_display_names': True,
        'corrections': corrections(list(range(3,11))) + [
            {'operation': 'source_concept_correction', 'node': 'flight', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'orlando', 'concept': 'unspecified'},
            {'operation': 'source_concept_correction', 'node': 'lima', 'concept': 'unspecified'}] + LIMITATIONS},
    'RuleArena_Airline:0c00a88c': {
        'graph_sha256': '31b295e4d6d1ca5ffbe9b244911bc49bee4de97dbf3342532ed15dadc8969232',
        'units_sha256': 'b5f7ee8c52453711758cb70d9831ed36f0764760a0f7c168b3d75a50a2a175df',
        'review': 'All thirteen supplied units, eighteen nodes and eighty-two original relations were checked. James, Philadelphia/NewYork route, BasicEconomy wording and ticket185 are explicit. All eleven source-ordered bag rows agree, including the separate 52/53-pound bags and the 49x27x24 and46x33x24 triples; no zip truncation, carry-on decision or weight grouping is introduced. Quantity1 follows each singular enumerated item. Keep all original unit labels, strings and ticket linkage uncertainty. Accompaniment does not establish legal ownership of bags, so the eleven bag-owner assertions become not_stated; the possessive ticket relation stays. Preserve unspecified bag concepts and all original unresolved statements; no previous consumer output or fee label was used.',
        'evidence': [
            {'unit_id': 0, 'quote': 'James is a Basic Economy Class passenger flying from Philadelphia to New York'},
            {'unit_id': 4, 'quote': '36 x 17 x 12 inches, 52 lbs'},
            {'unit_id': 8, 'quote': '49 x 27 x 24 inches, 53 lbs'},
            {'unit_id': 9, 'quote': '46 x 33 x 24 inches, 64 lbs'},
            {'unit_id': 12, 'quote': "James's flight ticket is $185"}],
        'project_display_names': True,
        'corrections': corrections([3,10,17,24,31,38,45,52,59,66,73]) + LIMITATIONS},
    'RuleArena_Airline:575fd48c': {
        'graph_sha256': '1078e498d47aef899620f534942e2ba3989ec4af405045dda89717fd2a3bdce2',
        'units_sha256': 'fc46e63ff6d6bdc8f381d7c63e8fd6ac5361f395f9a8baf478081c0de4faca4a',
        'review': 'All seven supplied units, ten nodes and forty original relations were checked. James is the PremiumEconomy passenger on the Dallas/Berlin itinerary; the ticket amount is400. All five bag categories, singular quantities, dimension triples and weights6/65/52/53/51 agree with their own unit, including the different 47x31x27 and34x20x11 rows. Keep their literal unit-bearing number strings and unspecified baggage class. The five asserted bag-owner edges have only accompaniment wording and become not_stated. The possessive ticket relation and original unresolved checked-baggage statement stay. No geographical domain extension or fee computation is part of this audit.',
        'evidence': [
            {'unit_id': 0, 'quote': 'James is a Premium Economy Class passenger flying from Dallas to Berlin'},
            {'unit_id': 3, 'quote': '47 x 31 x 27 inches, 52 lbs'},
            {'unit_id': 5, 'quote': '33 x 17 x 14 inches, 51 lbs'},
            {'unit_id': 6, 'quote': "James's flight ticket is $400"}],
        'project_display_names': True,
        'corrections': corrections([3,10,17,24,31]) + LIMITATIONS},
    'RuleArena_Airline:e3a6fee4': {
        'graph_sha256': '8e7b9ea3f95583cd5c2eb27f95c0db3c6112e0659b9afb6ca48523ee515f7553',
        'units_sha256': '3509c2e2d3ca8f9fd1d96b0a70bee1b5c0481abb2b54134fbcf0d42b0f1e5a12',
        'review': 'All thirteen supplied units, sixteen nodes and eighty-two original relations were checked. Emily, the ordered SaltLakeCity/Zurich route, PremiumEconomy cabin and ticket251 agree with the source. All eleven distinct item rows, singular quantities and ordered component/weight values agree, including the 55x30x30/61 row and the different 51/52/53-pound bags. Project the nonliteral flight display gloss to its existing flying quote only. Accompaniment does not establish legal bag ownership, so eleven bag-owner assertions become not_stated; the possessive ticket relation stays. Keep both original baggage-class and dimension-axis unresolved statements, every original scalar and inventory scope. No legal checked-bag status, route eligibility, other-view fact or target result is inferred.',
        'evidence': [
            {'unit_id': 0, 'quote': 'Emily is a Premium Economy Class passenger flying from Salt Lake City to Zurich'},
            {'unit_id': 7, 'quote': '45 x 28 x 22 inches, 51 lbs'},
            {'unit_id': 9, 'quote': '55 x 30 x 30 inches, 61 lbs'},
            {'unit_id': 12, 'quote': "Emily's flight ticket is $251"}],
        'project_display_names': True,
        'corrections': corrections([3,10,17,24,31,38,45,52,59,66,73]) + LIMITATIONS}
}


def main():
    completed = []
    for path in sorted((BASE / 'proposed_references').glob('*/source_checks.json')):
        check = json.loads(path.read_text())
        selected = [review for prefix, review in REVIEWS.items() if check['source'].startswith(prefix)]
        if not selected:
            continue
        if len(selected) != 1 or check['role'] not in ('development', 'calibration'):
            raise ValueError('Manual Airline review cohort changed')
        task = json.loads(path.with_name('task.json').read_text())
        response = json.loads((BASE / 'calls' / digest(check['physical_call_id']) / 'result.json').read_text())
        completed.append(persist_review(path, check, task, response, 'v0', selected[0]))
    if len(completed) != 4:
        raise ValueError('The fixed four source views were not all audited')
    print(json.dumps({'source_only_views': completed, 'new_model_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
