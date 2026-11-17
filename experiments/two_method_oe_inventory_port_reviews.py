"""Exact-source F-port reviews for the remaining19 original OE mothers.

All38 literal factual views were read before the recorded heldout-search
incident. This table uses those TRAIN facts and their public use/regime only;
heldout answers, construction metadata, weak reads and F outputs are not inputs.
It does not restore the exposed DEV/TEST cohorts' independence.
"""
from collections import Counter
from pathlib import Path
import json

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from experiments.two_method_maud_covenant_source_reviews import prepare as previous_reviews
from legal_skill_guard.paired_interfaces.asset_interfaces import context_from_public, frozen_skill
from legal_skill_guard.paired_interfaces.asset_graph_pairs import reference_world
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


LOCK_PATH = ROOT / 'experiments/source_review_locks/oe_remaining38_20261117.json'
PERSONAL = 'asset_is_personal_nonbusiness_property'
FEDERAL = 'asset_is_federal_household_category'
TANGIBLE = 'asset_is_personal_tangible_property'
APPAREL = 'asset_is_wearing_apparel'
AZ_APPAREL = 'asset_is_arizona_wearing_apparel'
AZ_HOME = 'asset_is_arizona_household_good_or_appliance'


def a(description, amount, kind, ownership=('stated', 'stated')):
    return {'description': description, 'amount': amount, 'kind': kind, 'ownership': ownership}


# This is a reviewed source table, not a classifier fitted to answer labels.
# Ownership states are separate for each literal view. A claimed ownership,
# possession, asset disclosure or "has" does not establish an owned interest.
SPECS = {
 '0d6a5c5f': ('Federal and Pennsylvania', 2, [
     a('decorative bowl filled with dried botanicals',120,'household',('stated','unknown')),
     a('custom dress shirt made from Egyptian cotton with monogram cuffs',190,'apparel',('stated','unknown')),
     a('dishwasher with stainless steel tub and delayed start functionality',1720,'household'),
     a('wireless router with mesh network support and four LAN ports',1630,'household')]),
 '1bb6328a': ('Federal and Pennsylvania', 1, [
     a('personal-sized blender with travel cup and lid',115,'household',('unknown','stated')),
     a('child booster seat with detachable tray and harness',95,'household',('unknown','stated')),
     a('countertop ice maker with 26-pound daily capacity',130,'household',('unknown','stated')),
     a('nylon windbreaker with mesh lining and elastic cuffs',23,'apparel',('unknown','stated'))]),
 '1ca28cd2': ('Illinois', 1, [
     a('Pembroke Welsh corgi',1600,'animal'),
     a('accent chair with floral upholstery and carved oak legs',2350,'household',('stated','unknown')),
     a('mini rice cooker with nonstick pot and keep-warm function',210,'household')]),
 '1fcfad02': ('Arizona', 1, [
     a('pair of sterling silver hoop earrings with cubic zirconia accents',98,'jewelry'),
     a('energy-efficient window air conditioning unit rated for 500 sq ft',255,'household',('unknown','stated'))]),
 '3ab6950c': ('Federal and Wisconsin', 2, [
     a('hospital bed with pressure-relief mattress (required by doctor for treatment of a diagnosed condition)',3045,'household'),
     a('step trash can with soft-close lid and removable liner',34,'household')]),
 '41b3a127': ('Illinois', 1, [
     a('silk evening gown with rhinestone embellishments',740,'apparel'),
     a('reclaimed wood coffee table with industrial metal frame',83,'household')]),
 '48b137c1': ('Federal and Pennsylvania', 2, [
     a('single-family primary home with detached carport and wraparound porch',264525,'real'),
     a('fleece-lined vest with zip-up front and chest logo',44,'apparel',('unknown','stated'))]),
 '4f3b7eff': ('Federal and Wisconsin', 1, [
     a('wall-mounted floating shelf made of reclaimed barn wood',800,'household',('unknown','stated')),
     a('hooded fleece robe with belt and two front pockets',105,'apparel',('unknown','stated'))]),
 '5a573dfd': ('Federal and Wisconsin', 2, [
     a('smart thermostat with geofencing and voice control',241,'household'),
     a('decorative wall clock with roman numerals and bronze frame',980,'household'),
     a('two-bedroom, two-bath condominium (owner-occupied) on the third floor with 1,200 square feet of living space',112850,'real'),
     a('wool cashmere cardigan with embroidered logo on chest',610,'apparel',('unknown','unknown'))]),
 '65e34328': ('Federal and Wisconsin', 1, [
     a('three-piece formal tuxedo with silk peak lapels and pleated trousers',1745,'apparel'),
     a('pair of polished black leather dress shoes with laces',480,'apparel',('unknown','stated'))]),
 '74dbd97c': ('Arizona', 2, [
     a('white wool suit featuring contrast stitching',1300,'apparel',('unknown','stated')),
     a('high-performance cycling jersey',140,'apparel',('unknown','stated')),
     a('complete set of stainless steel pots and pans with glass lids',450,'household'),
     a('vacuum sealer with roll storage and adjustable settings',285,'household')]),
 'ae1e4bdb': ('Federal and Wisconsin', 2, [
     a("digital camera for Debtor's photography business, including professional lenses",555,'business'),
     a("adjustable massage table (needed for Debtor's licensed massage therapy practice)",1025,'business'),
     a('Siberian husky',980,'animal')]),
 'b5dc2ec9': ('Illinois', 1, [
     a('home office webcam with 1080p resolution and privacy shutter',1200,'household'),
     a('fashion earrings in geometric shapes with silver-tone finish',85,'jewelry'),
     a('collapsible drying rack with adjustable wings',34,'household')]),
 'cdf5d6eb': ('Illinois', 1, [
     a('oxygen concentrator with portable carry cart and backup battery (physician authorized)',3250,'household'),
     a('pet crate suitable for a medium-sized dog with locking door',470,'household',('stated','unknown'))]),
 'cf6e576c': ('Arizona', 2, [
     a('desktop fan with three-speed settings and tilt head',40,'household',('unknown','stated')),
     a('48-inch LED smart TV with Roku interface',850,'household'),
     a('tailored navy suit with silk lining and hand-finished seams',500,'apparel'),
     a('folding card table with vinyl top and metal legs',24,'household',('stated','unknown'))]),
 'd2908306': ('Illinois', 2, [
     a('child safety gate with pressure mount system',85,'household',('unknown','stated')),
     a('vintage brooch with floral enamel detailing and rhinestones',245,'jewelry',('unknown','stated')),
     a('African grey parrot',1450,'animal',('unknown','stated'))]),
 'd68639e8': ('Arizona', 1, [
     a('torch red 2024 Chevrolet Corvette Stingray Coupe',71975,'vehicle'),
     a('upright acoustic bass with ebony fingerboard',775,'instrument',('unknown','stated'))]),
 'dbbe6b3d': ('Illinois', 1, [
     a('electric clothes dryer with moisture sensors and reversible door',1550,'household',('unknown','stated')),
     a('pair of ceramic table lamps with linen shades and USB ports',114,'household',('unknown','stated'))]),
 'fbed840c': ('Illinois', 1, [
     a("circular saw for Debtor's carpentry business, including replacement blades",1600,'business'),
     a('concert-grade oboe (French key system)',2415,'instrument'),
     a('ivory dashiki with colorful geometric embroidery',94,'apparel'),
     a('oversized crystal chandelier with dimmable LED lighting and brass fittings',2875,'household',('unknown','stated'))]),
}


def port_flags(regime, item, view):
    kind = item['kind']; owner = item['ownership'][int(view[1:])]
    if regime in ('Illinois', 'Federal and Pennsylvania'):
        personal = False if kind in ('business', 'real') else True if owner == 'stated' else None
        flags = {PERSONAL: personal}
        if regime == 'Federal and Pennsylvania':
            flags.update({TANGIBLE: kind not in ('real', 'business'), APPAREL: kind == 'apparel'})
        return flags
    if regime == 'Federal and Wisconsin':
        return {FEDERAL: kind in ('household', 'apparel', 'animal', 'instrument'),
                TANGIBLE: kind not in ('real', 'business')}
    if regime == 'Arizona':
        # Jewelry is not automatically classified as wearing apparel from the
        # supplied bare term. Instruments/vehicles have separate supplied
        # statute provisions;they are not general household goods here.
        return {AZ_HOME: kind == 'household',
                AZ_APPAREL: None if kind == 'jewelry' else kind == 'apparel'}
    raise ValueError('Unreviewed public regime')


def reviewed_card(source, view, units, context):
    matches = [r for r in read(LOCK_PATH) if r['source']==source and r['view']==view
               and r['source_units_sha256']==digest(units)]
    if len(matches) != 1:
        raise ValueError('Review requires one of38 exact separately read source views')
    key = source.split(':')[1][:8]; regime, debtors, items = SPECS[key]
    if context['governing_regime'] != regime or not context['public_task_assumptions']:
        raise ValueError('The reviewed classification requires its own public regime and use assumption')
    assets, unknown = [], []
    for item in items:
        description=item['description']; amount=item['amount']
        matches=[u for u in units if u['text'].count(description)==1]
        if len(matches)!=1: raise ValueError('Exact full asset description lacks a unique source anchor')
        unit=matches[0]; amount_quote='$'+format(amount,',.2f')
        if unit['text'].count(amount_quote)!=1: raise ValueError('Reviewed amount lacks a unique denomination in the asset unit')
        flags=port_flags(regime,item,view)
        fields={name:{'value':None,'status':'unread'} for name in frozen_skill()['inputs'] if name.startswith('asset_is_')}
        fields.update({name:{'value':value,'status':'unknown' if value is None else 'stated'} for name,value in flags.items()})
        fields.update(asset_descriptions={'value':description,'status':'stated'},asset_values={'value':amount,'status':'stated'})
        owner=item['ownership'][int(view[1:])]
        if owner=='unknown':unknown.append(description+': ownership is not established in this literal view;do not borrow another view')
        assets.append({'unit_id':unit['id'],'quote':description,'fields':fields,
            'amount_evidence':{'unit_id':unit['id'],'quote':amount_quote},
            'ownership_evidence':{'status':owner,'unit_id':unit['id'],'quote':unit['text'].strip()},
            'source_review_rationale':{'reviewed_literal_kind':item['kind'],
                'explicit_business_use_overrides_personal_use_assumption':item['kind']=='business',
                'port_judgment_not_an_exemption_citation_or_claim_value':True}})
    header=units[0]
    if '(hereinafter the Debtor'+('s' if debtors==2 else '')+')' not in header['text']:
        raise ValueError('The filing header no longer supplies the reviewed debtor count')
    record={'assets':assets,'globals':{'number_of_debtors':{'value':debtors,'status':'stated','unit_id':header['id'],'quote':header['text'].strip()}},
            'inventory_complete':True,'unresolved':[]}
    card={'source':source,'role':next(r['role'] for r in read(LOCK_PATH) if r['source']==source and r['view']==view),
          'view_id':view,'source_units_sha256':digest(units),'fixed_skill_sha256':digest(frozen_skill()),
          'public_regime':regime,'public_task_context':context,'port_record':record,
          'source_semantic_truth_verified':True,'reference_ready':True,'native_answers_used':False,
          'native_answers_used_to_create_or_repair_graph':False,'complete_native_case_gold_claimed':False,
          'source_uncertainties_not_resolved_by_F_ports':unknown,
          'unused_category_ports_remain_unread':True,'inventory_scope':'all listed assets in this supplied view,not certification of an entire bankruptcy estate',
          'reviewer':'root assistant source audit;not independent human annotation',
          'interactive_root_annotation_cost_usd':None,'interactive_annotation_cost_not_counted_as_free':True,
          'heldout_exposure_not_reset_by_this_TRAIN_review':True,'new_model_requests':0}
    reference_world(card,units,regime)  # Binding/schema only;no F output or native grade.
    return card


def prepare():
    previous_root,previous=previous_reviews()
    lock=read(LOCK_PATH);roles={r['source']:r['role'] for r in lock}
    public_path=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    source_lock=read(BASE/'prepared/source_lock.json')
    if sha(public_path)!=source_lock['prepared_sha256']['train']['public']:raise ValueError('Original TRAIN public bytes changed')
    public={s['key']:s for s in read(public_path)}
    paths=[Path(__file__).relative_to(ROOT),LOCK_PATH.relative_to(ROOT),
           'legal_skill_guard/paired_interfaces/asset_graph_pairs.py','legal_skill_guard/paired_interfaces/asset_interfaces.py',
           'legal_skill_guard/paired_interfaces/control_tools.py','legal_skill_guard/skill_evolution/objects.py',
           'experiments/two_method_annotate.py']
    binding={str(p):sha(ROOT/p) for p in paths}
    protocol={'experiment':'remaining19_OE_mothers38_source_port_reviews_v1','source_sha256':binding,
              'source_units_locks_sha256':sha(LOCK_PATH),'review_table_sha256':digest(SPECS),
              'previous_manifest':str((previous_root/'manifest.json').relative_to(ROOT)),
              'previous_manifest_sha256':sha(previous_root/'manifest.json'),'fixed_skill_sha256':digest(frozen_skill()),
              'native_labels_construction_metadata_weak_reads_or_F_outputs_used':False,
              'new_model_requests':0,'heldout_exposure_boundary_unchanged':True}
    out=BASE/'OE_inventory_port_source_reviews_v1'/digest(protocol);immutable_json(out/'protocol.json',protocol)
    for name,expected in binding.items():
        p=out/'source_snapshot'/name;p.parent.mkdir(parents=True,exist_ok=True)
        if p.exists():
            if sha(p)!=expected:raise ValueError('An immutable source snapshot changed')
        else:p.write_bytes((ROOT/name).read_bytes())
    rows=list(previous['reviews'])
    for row in lock:
        source=public[row['source']];task,mapping=inputs(source)
        view=next(v for v in task['views'] if v['view_id']==row['view'])
        natives=[v for v in source['views'] if mapping[v['id']]==row['view']]
        contexts=[context_from_public(v['public']) for v in natives]
        if any(c!=contexts[0] for c in contexts):raise ValueError('Native families do not share the same own-view public context')
        card=reviewed_card(row['source'],row['view'],view['source_units'],contexts[0])
        path=out/'cards'/digest([row['source'],row['view']])/'source_port_review.json';immutable_json(path,card)
        rows.append({'source':row['source'],'view':row['view'],'kind':'asset_program_ports',
                     'path':str(path.relative_to(ROOT)),'sha256':sha(path)})
    manifest={'reviews':rows,'previous_extra_reviews_retained':len(previous['reviews']),
              'new_root_reviewed_views':38,'new_reviewed_mothers':19,'new_original_mother_roles':dict(Counter(roles.values())),
              'source_views_are_not_independent_mothers':True,'native_outputs_computed_for_annotation':False,
              'interactive_root_annotation_cost_usd':None,'independent_human_or_complete_legal_gold_claimed':False,
              'heldout_exposure_not_repaired_by_source_review':True,'new_model_requests':0}
    if len(rows)!=138 or len(roles)!=19:raise ValueError('The cumulative source review inventory changed')
    immutable_json(out/'manifest.json',manifest)
    return out,manifest


if __name__=='__main__':
    out,manifest=prepare()
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),'cumulative_extra_reviews':len(manifest['reviews']),
                      'new_source_views':38,'new_original_mothers':19,'new_model_requests':0},ensure_ascii=False))
