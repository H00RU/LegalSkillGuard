"""Root source reviews of the three fixed OE development/calibration mothers.

Local F-port annotation, not native answer annotation. All previous full-graph
reviews and unresolved evidence remain intact. No structural-evaluation source,
grading file, weak output or DEV/TEST input is opened by this entry point.
"""
import json
from pathlib import Path

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from legal_skill_guard.paired_interfaces.asset_graph_pairs import consumer_signature, reference_world
from legal_skill_guard.paired_interfaces.asset_interfaces import context_from_public, frozen_skill
from legal_skill_guard.paired_interfaces.native_graph_consumers import money
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


REVIEWS = {
    'OpenExempt:d7a7ea93cee4a34d9e80d95eed868bb20bbc9726fa4f6c1131be9be93bd64102': {
        'regime': 'Federal and Wisconsin',
        'assets': [
            ('single-bedroom carriage house (year-round residence) with 12-foot ceilings', 142200,
             {'asset_is_federal_household_category': False, 'asset_is_personal_tangible_property': False},
             'The residence building is real estate,not a household furnishing/appliance or movable personal property.'),
            ('countertop blender with 1200-watt motor and ice-crushing capability', 315,
             {'asset_is_federal_household_category': True, 'asset_is_personal_tangible_property': True},
             'The named countertop appliance is a household good and tangible personal item;the explicit personal-use task assumption applies.'),
            ('twin bunk bed with integrated drawers and ladder', 750,
             {'asset_is_federal_household_category': True, 'asset_is_personal_tangible_property': True},
             'The named bed is a household furnishing and tangible personal item;the explicit personal-use task assumption applies.')],
        'ownership_uncertainty': 'All three assets are expressly owned by the named filing Debtors in each view.'},
    'OpenExempt:fe5acb6c980638b2750321e28fadcc69d98f49992871bfc44accbc3b147ca597': {
        'regime': 'Federal and Pennsylvania',
        'assets': [
            ('gas range with cast iron grates and double oven compartments', 680,
             {'asset_is_personal_nonbusiness_property': True,
              'asset_is_personal_tangible_property': True, 'asset_is_wearing_apparel': False},
             'The range is expressly the Debtors property,an appliance rather than clothing,and the public personal-use assumption applies.'),
            ('Henry Golden Boy .22 LR lever-action rifle with brass receiver', 600,
             {'asset_is_personal_nonbusiness_property': None,
              'asset_is_personal_tangible_property': True, 'asset_is_wearing_apparel': False},
             'The rifle is a tangible personal object rather than clothing;personal use is an explicit task assumption.Possession alone in v0 does not establish ownership.')],
        'v1_overrides': {'Henry Golden Boy .22 LR lever-action rifle with brass receiver': {
            'asset_is_personal_nonbusiness_property': True}},
        'ownership_uncertainty': 'v0 states possession of the rifle,not its ownership;v1 expressly states both assets are owned by the Debtors.'},
    'OpenExempt:de89e35f7b94fb912ba36805ea74042cf096ac6b8e69bc72bbfc6ca7b89eeed8': {
        'regime': 'Illinois',
        'assets': [
            ('medically approved prosthetic leg with carbon fiber pylon and silicone socket liner', 12900,
             {'asset_is_personal_nonbusiness_property': None},
             'v0 merely claims ownership and v1 reports an asset disclosure.Neither is converted into established ownership.'),
            ('blender bottle-style protein mixer with USB charging port', 225,
             {'asset_is_personal_nonbusiness_property': True},
             'The mixer is expressly described as belonging to/owned by the Debtors and the stated personal-use assumption applies.')],
        'ownership_uncertainty': 'The prosthetic leg keeps unknown ownership in both source views;no medical exemption or statute applicability is inferred.'},
}


def main():
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    source_lock = read(BASE / 'prepared/source_lock.json')
    if sha(public_path) != source_lock['prepared_sha256']['train']['public']:
        raise ValueError('The original TRAIN bytes changed')
    train = {source['key']: source for source in read(public_path)}
    lock_path = BASE / 'pilot_lock.json'
    lock = read(lock_path)
    roles = {row['key']: row['role'] for row in lock['rows']}
    if any(roles.get(key) not in ('development', 'calibration') for key in REVIEWS):
        raise ValueError('This source-review table cannot open an evaluation mother')
    paths = [Path(__file__).relative_to(ROOT), 'legal_skill_guard/paired_interfaces/asset_graph_pairs.py',
             'legal_skill_guard/paired_interfaces/asset_interfaces.py',
             'legal_skill_guard/paired_interfaces/program_residual.py']
    binding = {str(path): sha(ROOT / path) for path in paths}
    protocol = {'experiment': 'fixed_OE_source_only_F_port_reviews_v1', 'source_sha256': binding,
        'TRAIN_public_sha256': sha(public_path), 'pilot_lock_sha256': sha(lock_path),
        'review_table_sha256': digest(REVIEWS), 'fixed_skill_sha256': digest(frozen_skill()),
        'source_unit': 'original mother with its separate literal factual views',
        'native_labels_predictions_or_structural_evaluation_inputs_opened': False,
        'reviewer': 'root assistant source audit;not independent human annotation',
        'new_model_requests': 0, 'old_generic_reference_audits_not_rewritten': True,
        'reference_scope': 'F-port facts under the explicit public regime;unused attributes remain unreviewed'}
    out = BASE / 'asset_port_source_reviews_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    manifest = []
    for key, review in REVIEWS.items():
        source = train[key]
        task, mapping = inputs(source)
        old_folder = BASE / 'annotation_v1/proposed_references' / digest(key)
        original_task = read(old_folder / 'task.json')
        if original_task['task'] != task:
            raise ValueError('A source no longer binds its original annotation task')
        for view in task['views']:
            old_path = old_folder / 'audits' / view['view_id'] / 'source_review.json'
            old = read(old_path)
            if (old['source_units_sha256'] != digest(view['source_units'])
                    or not old['source_semantic_truth_verified'] or old['native_answers_used_to_create_or_repair_graph']):
                raise ValueError('The preserved source review lost its local truth binding')
            native_view = next(native for native in source['views'] if mapping[native['id']] == view['view_id'])
            context = context_from_public(native_view['public'])
            if context['governing_regime'] != review['regime'] or not context['public_task_assumptions']:
                raise ValueError('The source port judgments require this explicit public regime/use assumption')
            units = view['source_units']
            assets = []
            for description, amount, flags, rationale in review['assets']:
                supported = [unit for unit in units if description in unit['text']]
                if len(supported) != 1:
                    raise ValueError('A reviewed full asset description lacks its own unique source span')
                unit = supported[0]
                if ('$' + format(amount, ',.2f')) not in unit['text']:
                    raise ValueError('A reviewed amount lacks its literal source denomination')
                antecedents = [node for node in old['graph']['nodes'] if node['kind'] == 'asset'
                               and node['unit_id'] == unit['id'] and node['name'] in description]
                if len(antecedents) != 1:
                    raise ValueError('The full asset description lost its unique audited local antecedent')
                amounts = [money(edge['value']) for edge in old['graph']['relations']
                           if edge['predicate'] == 'amount' and edge['status'] == 'stated'
                           and edge['arguments'] == [antecedents[0]['id']]]
                if amounts != [amount]:
                    raise ValueError('The source-reviewed amount was rebound to another asset')
                cells = {name: {'value': None, 'status': 'unread'}
                         for name in frozen_skill()['inputs'] if name.startswith('asset_is_')}
                actual_flags = {**flags, **review.get(view['view_id'] + '_overrides', {}).get(description, {})}
                for name, value in actual_flags.items():
                    cells[name] = {'value': value, 'status': 'unknown' if value is None else 'stated'}
                cells.update(asset_descriptions={'value': description, 'status': 'stated'},
                             asset_values={'value': amount, 'status': 'stated'})
                assets.append({'unit_id': unit['id'], 'quote': description, 'fields': cells,
                               'source_review_rationale': rationale})
            header = units[0]
            if ' and ' not in header['text'] or '(hereinafter the Debtors)' not in header['text']:
                raise ValueError('The two named filing debtors are not explicitly represented')
            record = {'assets': assets, 'globals': {'number_of_debtors': {
                'value': 2, 'status': 'stated', 'unit_id': header['id'], 'quote': header['text'].strip()}},
                'inventory_complete': True, 'unresolved': []}
            card = {'source': key, 'role': roles[key], 'view_id': view['view_id'],
                'source_units_sha256': digest(units), 'fixed_skill_sha256': digest(frozen_skill()),
                'public_regime': review['regime'], 'public_task_context': context, 'port_record': record,
                'source_semantic_truth_verified': True, 'native_answers_used': False,
                'old_source_audit_path': str(old_path.relative_to(ROOT)), 'old_source_audit_sha256': sha(old_path),
                'source_uncertainties_outside_F_ports_preserved': old['graph']['unresolved'],
                'ownership_uncertainty': review['ownership_uncertainty'],
                'unrequested_category_ports_not_asserted_or_set_false': True,
                'no_new_blindness_independent_human_or_complete_legal_gold_claim': True,
                'new_model_requests': 0}
            path = out / 'cards' / digest([key, view['view_id']]) / 'source_port_review.json'
            immutable_json(path, card)
            world, receipt = reference_world(card, units, review['regime'])
            result = consumer_signature(world)
            immutable_json(path.with_name('reference_program_domain.json'), {
                'handled': result['handled'], 'reason': result.get('reason'),
                'not_native_grading_or_gold_accuracy': True, 'residual_scope_receipt': receipt})
            manifest.append({'source': key, 'role': roles[key], 'view': view['view_id'],
                             'card_path': str(path.relative_to(ROOT)), 'card_sha256': sha(path),
                             'native_reference_F_defined': result['handled']})
    immutable_json(out / 'manifest.json', {'reviews': manifest, 'new_model_requests': 0,
        'structural_evaluation_mothers_opened': False, 'old_pilot_scores_or_graph_audits_changed': False})
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), 'source_mothers': len(REVIEWS),
        'source_views': len(manifest), 'native_reference_F_defined_views': sum(row['native_reference_F_defined'] for row in manifest),
        'new_weak_reads_channels_or_native_scores': 0, 'new_model_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
