"""Calibrate M1 on the current journaled TRAIN batch and persist its learned interfaces."""

from collections import defaultdict
from functools import lru_cache

from legal_skill_guard.paired_interfaces import diversity, diversity_relational
from legal_skill_guard.paired_interfaces.convergence_actors import M1_ARMS
from legal_skill_guard.paired_interfaces.convergence_training import calibrate_source
from legal_skill_guard.paired_interfaces.formal_training import RelationalInterfaceLibrary
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def diversity_unit_reviews(source, view):
    """Construct the independent factual review of each named party and claim pair."""
    if (source['project_split'] != 'train' or source['dataset'] != 'LegalBench_Diversity'
            or view['source'] != source['key']):
        raise ValueError('Diversity reference reviews are scoped to the exact TRAIN mother')
    fixed, = (plan for plan in view['plans'] if plan['is_correct_fixed_raw_control'])
    if fixed['source_public_sha256'] != digest(source):
        raise ValueError('The fixed control must bind the source independently reviewed here')
    text = source['views'][0]['public']['source_text']
    record = diversity.audit_source(text)
    amounts = defaultdict(list)
    for claim in record['claims']:
        amounts[claim['plaintiff'], claim['defendant']].append(claim['amount'])
    reviews = {}
    for name, unit in fixed['relational_program']['units'].items():
        context = unit['entity_context']
        plaintiff, defendant = context['plaintiff'], context['defendant']
        kind = unit['template_key'].split(':', 1)[0]
        if kind == 'citizenship':
            state = {'plaintiff_state': record['citizenship'][plaintiff],
                     'defendant_state': record['citizenship'][defendant]}
        else:
            claims = amounts[plaintiff, defendant]
            if len(claims) != context['claim_count'] or any(amount < 0 or amount % 1000 for amount in claims):
                raise ValueError('The source review falls outside the certified claim domain')
            state = {f'claim{index}': min(amount // 1000, 76) for index, amount in enumerate(claims)}
        reviews[name] = {'module': diversity_relational.module(kind), 'admissible_states': [state],
                         'provenance': [{'kind': 'explicit_source',
                                         'evidence_sha256': record['source_text_sha256']}]}
    return reviews


def fit_interface_batch(journal, arm, batch, *, actor, reviewers, grade_provider):
    """Advance an M1 library after verified primary reads of the fixed batch.

    The learner receives certified observations from visible TRAIN only. No
    previous pilot library is loaded. Per-dataset public applicability and all
    rejection/fidelity outcomes are retained in the receipt.
    """
    if arm not in M1_ARMS or not 1 <= batch <= len(journal.batches):
        raise ValueError('M1 training requires an interface arm and a fixed positive TRAIN batch')
    sources = journal.batches[batch - 1]
    ids = [source['key'] for source in sources]
    before = journal.library(arm, batch - 1)
    observation = journal._observations(arm, batch)
    train = [source['key'] for group in journal.batches for source in group]
    prefix = train[:sum(len(group) for group in journal.batches[:batch])]
    initial = digest(journal.library(arm, 0)['programs'])
    prior = before['interface_library']
    if prior is None:
        if batch != 1:
            raise ValueError('M1 batches must carry their own preceding interface history')
        learner = RelationalInterfaceLibrary(journal.root, actor=actor, train_sources=train,
                                            initial_common_library_sha256=initial)
    else:
        if (prior['batch'] != batch - 1 or prior['initial_common_library_sha256'] != initial
                or set(prior['visible_prefix']) != set(prefix[:-len(ids)])):
            raise ValueError('M1 cannot restore calibration from another batch or initialization')
        learner = RelationalInterfaceLibrary.restore(journal.root, actor=actor, train_sources=train, snapshot=prior)

    @lru_cache(maxsize=None)
    def grade(key):
        if key not in ids:
            raise ValueError('New M1 native supervision belongs to the current fixed TRAIN batch')
        return grade_provider(key)

    results = []
    for source in sources:
        key, dataset = source['key'], source['dataset']
        reviewer = reviewers.get(dataset)
        if reviewer is None:
            results.append({'source': key, 'dataset': dataset, 'status': 'no_review_provider'})
            continue
        views = actor.views(source)
        receipts = []
        for view in views:
            if view.get('pre_generation_domain_refusal'):
                receipts.append({'view': view['view'], 'status': 'outside_certified_domain'})
                continue
            reviews = reviewer(source, view)
            paired = calibrate_source(learner, source, view, unit_reviews=reviews,
                                      grade_provider=grade, visible_prefix=prefix)
            receipts.append({'view': view['view'], 'status': 'measured',
                             'candidate_observations_sha256': [digest(row) for row in paired]})
        results.append({'source': key, 'dataset': dataset, 'status': 'processed', 'views': receipts})
    snapshot = learner.snapshot(batch=batch, visible_prefix=prefix)
    receipt = {'arm': arm, 'batch': batch, 'visible_prefix_sha256': digest(prefix),
               'observations_sha256': observation['train_observation_sha256'],
               'interface_library_sha256': snapshot['snapshot_sha256'], 'sources': results}
    immutable_json(journal.directory(arm, batch) / 'interface_update.json', receipt)
    return snapshot, receipt
