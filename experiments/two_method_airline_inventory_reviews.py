"""Explicit source-only reviews of twenty remaining Airline inventories.

These recipes transcribe the entire supplied facts,not a fee computation.
No reference parameters,construction records,native questions,labels,weak
outputs or program results are used to make or repair these annotations.
"""
from collections import Counter
from pathlib import Path
import json

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT, BASE, read, sha
from experiments.two_method_maud_knowledge_reviews import ReviewedGraph
from experiments.two_method_sara_source_reviews import prepare as previous_reviews
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


LOCK_PATH = ROOT / 'experiments/source_review_locks/airline_remaining20_20261117.json'

# Root transcription after reading every whole source view. B/L are literal
# backpack/luggage-box names,not carry-on/checked classifications. Measurements
# remain in their original x order and pounds;no derived linear size or fee.
RECIPES = {
    'e88c2c8f': ('Karen', 'Basic Economy', 'Phoenix', 'Rio de Janeiro', 563,
        'B:19,13,6,10 L:38,18,9,64 B:35,15,14,53 B:43,24,20,53 L:36,18,10,52'),
    '9b47bd06': ('Emily', 'Premium Economy', 'San Francisco', 'Auckland', 875,
        'B:21,13,6,6 L:44,29,20,62 L:45,23,19,53 B:36,18,9,66 B:33,21,10,53 B:46,31,27,57 L:36,15,14,63 L:35,18,10,58 L:51,29,24,52 B:37,17,9,52 L:38,20,13,53'),
    '92d91f15': ('David', 'Main Cabin', 'Austin', 'Los Angeles', 53,
        'B:22,14,9,10 L:33,21,9,57 B:36,18,16,82 B:35,16,14,53 B:48,29,22,99 B:34,20,9,72 L:40,24,14,51 L:41,24,18,64 B:37,25,12,63 B:40,21,16,81 B:38,17,9,83'),
    'f5e2570b': ('David', 'Business', 'Miami', 'Orlando', 86,
        'B:21,14,9,10 L:48,29,26,57 L:35,19,9,51 L:33,16,14,82 L:38,14,12,52'),
    'f20219c3': ('Daniel', 'Premium Economy', 'Atlanta', 'Rio de Janeiro', 735,
        'B:22,11,7,7 B:37,23,12,53 L:44,23,18,53 L:34,19,11,70 L:51,33,28,53 L:36,16,13,66'),
    'cf4251b3': ('Jennifer', 'Main Cabin', 'New Orleans', 'Amsterdam', 344,
        'B:22,14,6,8 B:48,32,26,52 B:44,26,22,66 B:36,16,11,52 L:48,33,25,69 B:50,32,25,68 B:53,34,27,54 L:35,17,12,52'),
    '748306d9': ('David', 'First', 'Minneapolis', 'Orlando', 197,
        'B:22,12,7,8 B:48,35,26,86 B:46,23,18,68 B:35,17,13,62 L:36,17,10,75 L:34,16,13,51 B:47,31,23,59 B:51,25,26,79'),
    'bc47b812': ('Linda', 'Main Cabin', 'Salt Lake City', 'Minneapolis', 262,
        'B:18,11,9,7 L:48,33,24,53 L:38,16,10,53 B:51,29,23,51 B:36,18,10,58'),
    '7882b36c': ('Elizabeth', 'Main Cabin', 'Dallas', 'Sydney', 675,
        'B:19,13,6,7 L:40,22,16,64 B:33,18,13,51 L:46,28,22,63 B:34,22,9,52 B:34,18,13,69 L:47,23,23,53 B:34,23,11,51'),
    '3e9dfb75': ('Elizabeth', 'First', 'Salt Lake City', 'Chicago', 247,
        'B:20,12,6,9 B:39,27,17,68 L:35,19,10,52 L:42,21,14,65 B:39,13,15,51'),
    '9b080c74': ('Susan', 'Main Cabin', 'Hong Kong', 'Charlotte', 1394,
        'B:20,11,6,5 B:38,13,13,52 L:44,23,15,66 L:36,15,13,99 B:34,21,10,70 B:36,19,17,95 L:51,25,26,53 B:39,16,13,60 L:47,28,27,60 B:44,21,17,61 L:40,20,13,55'),
    '3b3bf13a': ('Joseph', 'Main Plus', 'Austin', 'Denver', 173,
        'B:20,13,8,5 B:35,18,12,52 L:37,16,12,69 B:33,21,11,100 B:40,27,17,52'),
    'f91df7e1': ('Patricia', 'Premium Economy', 'Salt Lake City', 'Guangzhou', 824,
        'B:22,14,9,5 L:35,20,10,74 B:46,34,21,89 B:44,25,22,64 L:54,30,27,70'),
    '7b4b9947': ('Patricia', 'Premium Economy', 'Los Angeles', 'Washington D.C.', 43,
        'B:20,11,7,6 L:48,28,19,69 B:37,19,9,74 L:38,13,14,86 L:33,17,13,64 B:43,29,17,60 B:48,35,24,98 L:47,22,24,96'),
    '0e94355b': ('Jennifer', 'Basic Economy', 'New York', 'Washington D.C.', 245,
        'B:21,12,8,11 L:36,14,14,72 L:35,21,9,82 L:40,19,12,51 L:35,17,11,51'),
    '68dc5c0d': ('Jessica', 'Premium Economy', 'Portland', 'Jerusalem', 863,
        'B:22,13,9,6 B:41,26,20,70 B:38,24,18,53 B:34,17,14,51 B:37,18,10,54 L:40,27,16,51 L:37,14,12,57 B:33,18,13,53 B:33,19,12,53 B:38,16,10,60 B:36,20,15,53'),
    '30fe9798': ('Sarah', 'First', 'Hong Kong', 'Austin', 1209,
        'B:22,12,9,11 B:40,28,15,51 B:38,17,10,53 B:38,26,13,63 B:35,21,9,67 L:33,20,10,57 L:48,32,26,51 L:39,25,13,71 B:39,25,18,95 B:37,25,12,51 L:53,31,26,99'),
    '3e743f75': ('James', 'Main Plus', 'Seattle', 'New York', 241,
        'B:19,11,9,10 B:39,17,12,52 B:34,15,14,91 L:46,25,18,53 L:41,17,15,84 B:51,35,25,59 B:48,29,20,95 B:40,24,13,52 L:47,31,21,60 B:34,17,13,60 L:34,19,10,53'),
    '27dccd09': ('William', 'Business', 'Chengdu', 'Miami', 1303,
        'B:19,11,7,12 B:34,15,14,55 L:37,18,17,81 L:40,24,14,64 B:38,18,9,69 L:37,16,12,52 L:35,15,14,80 L:50,29,28,76 B:44,28,18,51 L:46,28,18,52 L:38,20,15,87'),
    '51ecb012': ('Elizabeth', 'Business', 'Mexico City', 'Sacramento', 133,
        'B:18,13,9,8 B:35,16,12,53 L:36,13,14,67 L:36,19,15,53 L:44,24,15,68 L:42,27,16,77'),
}


class InventoryGraph(ReviewedGraph):
    def relation(self, predicate, arguments, quote, *, value=None):
        self.relations.append({'predicate': predicate, 'arguments': arguments,
            'value': value, 'status': 'stated', 'quote': quote, 'unit_id': self.evidence(quote)})


def reviewed_graph(source, units):
    locks = {r['source']: r for r in read(LOCK_PATH)}
    if source not in locks or digest(units) != locks[source]['units_sha256']:
        raise ValueError('Only twenty exact source views explicitly read for these recipes are covered')
    name, cabin, origin, destination, price, raw_bags = RECIPES[source.split(':')[1][:8]]
    header = f'{name} is a {cabin} Class passenger flying from {origin} to {destination} with the following items:'
    if units[0]['text'].strip() != header + '\n1.':
        raise ValueError('The reviewed header must cover its full unchanged source unit')
    bags = raw_bags.split()
    if len(units) != len(bags) + 2:
        raise ValueError('No listed bag or source unit may be dropped')
    g = InventoryGraph(units)
    g.node('passenger', 'person', 'unspecified', header, name=name)
    flight = f'flying from {origin} to {destination}'
    g.node('flight', 'event', 'unspecified', flight)
    g.node('origin', 'place', 'unspecified', origin)
    g.node('destination', 'place', 'unspecified', destination)
    # Literal route only;no guessed country/fee region. Public geography stays
    # a consumer assumption,not an assertion licensed by this source review.
    g.node('itinerary', 'information', 'unspecified', f'from {origin} to {destination}')
    g.node('cabin', 'information', cabin, cabin + ' Class')
    g.edge('actor', 'flight', 'passenger', header)
    g.relation('route', ['flight', 'itinerary', 'origin', 'destination'], flight)
    g.edge('cabin', 'flight', 'cabin', cabin + ' Class')
    for position, raw in enumerate(bags, 1):
        kind, measures = raw.split(':')
        literal_kind = {'B': 'backpack', 'L': 'luggage box'}[kind]
        length, width, height, weight = [int(v) for v in measures.split(',')]
        quote = f'A {literal_kind}: {length} x {width} x {height} inches, {weight} lbs'
        expected = quote + ';' + (f'\n{position+1}.' if position < len(bags) else '')
        if units[position]['text'].strip() != expected:
            raise ValueError('Every reviewed inventory row must match its full source unit and position')
        identity = 'bag_' + str(position)
        g.node(identity, 'bag', 'unspecified', quote)
        # An item carried on the flight does not assert legal title or a
        # checked/carry-on fee classification.
        g.edge('object', 'flight', identity, header)
        g.relation('category', [identity], quote, value=literal_kind)
        for predicate, value in zip(('length', 'width', 'height', 'weight'), (length, width, height, weight)):
            g.relation(predicate, [identity], quote, value=value)
    ticket = f"{name}'s flight ticket"
    quote = ticket + f' is ${price}.'
    if units[-1]['text'].strip() != quote:
        raise ValueError('Keep the stated ticket price separate from any computed total')
    g.node('ticket', 'asset', 'other_asset', ticket)
    g.edge('owner', 'ticket', 'passenger', ticket)
    g.relation('ticket_price', ['ticket'], quote, value=price)
    return g.finish(complete=True, unknown=[])


def prepare():
    locks = read(LOCK_PATH)
    if (len(locks) != 20 or len({r['source'] for r in locks}) != 20
            or Counter(r['role'] for r in locks) != Counter(development=8, calibration=8, reference_only=4)
            or set(RECIPES) != {r['source'].split(':')[1][:8] for r in locks}):
        raise ValueError('Preserve the twenty original source/view/role bindings')
    _, previous = previous_reviews()
    checkpoint = read(BASE / 'handoff/current_checkpoint.json')
    registry_root = ROOT / checkpoint['formal_source_reference_registry']['artifact_root']
    roles = {r['source']: r for r in read(registry_root / 'roles.json')}
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    public = {s['key']: s for s in read(public_path)}
    # Prior manifests bind their own builders;retain all prior card bytes and
    # include this recipe's direct helper dependencies in its source snapshot.
    builders = [Path(__file__), LOCK_PATH, ROOT / 'experiments/two_method_annotate.py',
        ROOT / 'experiments/two_method_maud_knowledge_reviews.py',
        ROOT / 'experiments/two_method_sara_source_reviews.py',
        ROOT / 'legal_skill_guard/paired_interfaces/graph_interface.py',
        ROOT / 'legal_skill_guard/skill_evolution/objects.py']
    protocol = {'experiment': 'remaining20_Airline_source_only_root_reviews_v1',
        'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in builders},
        'original_TRAIN_public_sha256': sha(public_path), 'locked_original_roles_and_sources': locks,
        'prior32_explicit_manifest_sha256': digest(previous),
        'native_target_questions_labels_weak_outputs_or_program_results_used': False,
        'explicit_root_review_not_automatic_semantic_certification': True,
        'scope': 'Entire supplied source-local travel/item inventory;not complete policy or fee gold',
        'interactive_root_annotation_cost_usd': None, 'new_experimental_endpoint_requests': 0}
    out = BASE / 'Airline_source_reviews_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    rows = list(previous['reviews'])
    for lock in locks:
        source = lock['source']; role = roles[source]
        if (role['role'], role['batch']) != (lock['role'], lock['batch']) or lock['view'] != 'v0':
            raise ValueError('Do not change an original source role,batch or view')
        task, mapping = inputs(public[source])
        if len(task['views']) != 1: raise ValueError('Do not collapse distinct source views')
        units = task['views'][0]['source_units']; graph = reviewed_graph(source, units)
        card = {'source': source, 'view_id': 'v0', 'role': role['role'],
            'source_units_sha256': lock['units_sha256'], 'native_views': sorted(mapping),
            'graph': graph, 'reference_ready': True, 'source_semantic_truth_verified': True,
            'native_answers_used_to_create_or_repair_graph': False, 'complete_native_case_gold_claimed': False,
            'reviewer': 'root assistant explicit source review;not independent human annotation',
            'verification_scope': protocol['scope'], 'source_span_checks': gi.validate(graph, units),
            'review': {'entire_supplied_view_read': True, 'source_sha_locked': True,
                'all_item_occurrences_and_source_order_retained': True,
                'dimensional_units_inches_and_weight_units_lbs_retained_in_evidence': True,
                'no_item_name_to_checked_carryon_or_legal_title_inference': True,
                'no_geographic_fee_region_or_fee_total_asserted': True,
                'unsupported_consumer_routes_not_relabelled_as_supported': True,
                'no_native_reference_parameters_or_F_output_used_to_edit_graph': True},
            'new_model_requests': 0}
        path = out / 'cards' / digest([source, 'v0']) / 'source_review.json'
        immutable_json(path, card)
        rows.append({'source': source, 'view': 'v0', 'kind': 'literal_semantic_graph',
                     'path': str(path.relative_to(ROOT)), 'sha256': sha(path)})
    if len(rows) != 52 or len({(r['source'], r['view']) for r in rows}) != 52:
        raise ValueError('Retain all previous32 and new20 source views exactly once')
    manifest = {'reviews': rows, 'new_root_reviewed_views': 20, 'previous_extra_reviews_retained': 32,
        'interactive_root_annotation_cost_usd': None, 'unmetered_interactive_annotation_not_counted_as_free': True,
        'independent_human_or_complete_legal_gold_claimed': False, 'new_model_requests': 0}
    immutable_json(out / 'manifest.json', manifest)
    for builder in builders:
        target = out / 'source_snapshot' / builder.relative_to(ROOT); target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != builder.read_bytes(): raise ValueError('A frozen source builder changed')
        if not target.exists(): target.write_bytes(builder.read_bytes())
    return out, manifest


if __name__ == '__main__':
    out, manifest = prepare()
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), 'new_reviewed_mothers': 20,
        'cumulative_explicit_review_views': len(manifest['reviews']),
        'new_model_requests': 0, 'complete_goal_claimed': False}, ensure_ascii=False))
