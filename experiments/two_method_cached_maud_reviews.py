"""Two explicit root-reviewed source cards from already cached TRAIN text.

This is not a general semantic-certification algorithm. The complete supplied
v0 texts were read manually;exact source-unit hashes lock those two reviews.
The older partial judgments remain partial and are retained as provenance.
No teacher/client/native grader,answer file or new proposal is used.
"""
import json
from pathlib import Path

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


CACHE = ROOT / 'artifacts/legal_skill_evolution_MAUD_role_repair_20261114/partial_source_reviews.json'
CACHE_SHA256 = '280ba3f296aa9c18848cae790793f475a24b3a7e4ed09157ac8f9ddb18e0ec82'
LOCKS = {
    'MAUD:7e2add3ce5bb9160f13ccedb9f8405507934d213f01de0c03eec20dfc62136ed':
        '2bdd98cd59cddc8e8722bdd4cf086524e4aed7547cf45c69907e59ebca15b60a',
    'MAUD:cef0e433b890a453713ec1a02a59ce4df7ef357eb4a379989e78225d83c773ba':
        'f6aa905971262ed212808afa2901380802be1604cf92c6a5e185ec7a61975720',
}


def reviewed_graph(source, units):
    if source not in LOCKS or digest(units) != LOCKS[source]:
        raise ValueError('Only the two exact manually read source views are reviewed')
    nodes, relations = [], []
    def node(identity, kind, concept, quote, unit=0):
        nodes.append({'id': identity, 'kind': kind, 'concept': concept,
                      'name': quote, 'quote': quote, 'unit_id': unit})
    def edge(predicate, *arguments, quote, unit=0, status='stated'):
        relations.append({'predicate': predicate, 'arguments': list(arguments),
                          'quote': quote, 'unit_id': unit, 'status': status, 'value': None})
    unknowns = [
        'The inquiry target is not supplied;the named knowledge holders are not inferred to be its target.',
        'The source does not establish employee/officer status of the designated holders.',
        'The actor who performs the inquiry is not specified separately from the knowledge attribution.',
    ]
    if source.startswith('MAUD:7e2add3c'):
        node('definition', 'definition', 'knowledge_definition', '“knowledge of the Company”')
        node('company', 'organization', 'unspecified', 'the Company')
        node('holders', 'group', 'unspecified', 'Mike Finley, Peter Hovenier, Derek Peterson, Dawn Callahan, Michael Zeto and Bruce Crair')
        node('inquiry', 'condition', 'reasonable_inquiry_required', 'after reasonable inquiry')
        edge('subject', 'definition', 'company', quote='“knowledge of the Company”')
        edge('object', 'definition', 'holders', quote='of each of Mike Finley, Peter Hovenier, Derek Peterson, Dawn Callahan, Michael Zeto and Bruce Crair')
        edge('condition', 'definition', 'inquiry', quote='means the knowledge, after reasonable inquiry')
        node('IP_scope', 'information', 'unspecified', 'Intellectual Property and Intellectual Property Rights', 1)
        node('patent_scope', 'condition', 'unspecified', 'with respect to Patents', 1)
        exception = ('“reasonable inquiry” does not require the Company or any of the individuals named in the previous sentence '
                     'to conduct, have conducted, obtain, or have obtained any freedom-to-operate opinions or similar opinions '
                     'of counsel or any clearance searches, in each case, with respect to Patents')
        node('limited_inquiry_exception', 'exception', 'no_inquiry_required', exception, 1)
        node('covered_people', 'group', 'unspecified', 'the Company or any of the individuals named in the previous sentence', 1)
        work = ('conduct, have conducted, obtain, or have obtained any freedom-to-operate opinions or similar opinions '
                'of counsel or any clearance searches')
        node('clearance_work', 'event', 'unspecified', work, 1)
        edge('exception_for', 'limited_inquiry_exception', 'inquiry', quote=exception, unit=1)
        edge('condition', 'limited_inquiry_exception', 'IP_scope',
             quote='With respect to Intellectual Property and Intellectual Property Rights', unit=1)
        edge('condition', 'limited_inquiry_exception', 'patent_scope', quote='in each case, with respect to Patents', unit=1)
        edge('actor', 'limited_inquiry_exception', 'covered_people', quote='does not require the Company or any of the individuals named in the previous sentence', unit=1)
        edge('action', 'limited_inquiry_exception', 'clearance_work', quote='to ' + work, unit=1)
        info = 'knowledge of any third-party Intellectual Property Rights that would have been revealed by such inquiries, opinions, or searches'
        prohibition = 'no ' + info + ' will be imputed to the Company or any such individual'
        node('non_imputation', 'effect', 'prohibition', prohibition, 1)
        node('imputation_action', 'event', 'constructive_imputation', info + ' will be imputed', 1)
        node('qualified_IP_information', 'information', 'unspecified', info, 1)
        edge('condition', 'non_imputation', 'IP_scope', quote='With respect to Intellectual Property and Intellectual Property Rights', unit=1)
        edge('action', 'non_imputation', 'imputation_action', quote='no ' + info + ' will be imputed', unit=1)
        edge('information', 'non_imputation', 'qualified_IP_information', quote=info, unit=1)
        edge('recipient', 'non_imputation', 'covered_people', quote='to the Company or any such individual', unit=1)
        unknowns.extend([
            'No explicit actual-knowledge wording appears in the general knowledge definition.',
            'The limited exception removes only the specified patent opinions/searches;it does not remove all reasonable inquiry.',
            'Non-imputation has its own stated information qualifier;no extra requirement that searches were not performed is supplied.',
            'The graph retains the literal company-or-individual pool without inferring organizational membership or logical-union internals.',
        ])
    else:
        node('definition', 'definition', 'knowledge_definition', '“knowledge” means')
        node('company', 'organization', 'unspecified', 'the Company')
        node('holders', 'group', 'unspecified', 'the individuals listed in Section 1.1(A) of the Company Disclosure Letter')
        node('actual_wording', 'condition', 'explicit_actual_wording', 'actual knowledge')
        node('inquiry', 'condition', 'reasonable_inquiry_required', 'after reasonable inquiry')
        edge('subject', 'definition', 'company', quote='with respect to the Company')
        edge('object', 'definition', 'holders', quote='the actual knowledge of the individuals listed in Section 1.1(A) of the Company Disclosure Letter')
        edge('standard', 'definition', 'actual_wording', quote='the actual knowledge')
        edge('actor', 'actual_wording', 'holders', quote='the actual knowledge of the individuals listed in Section 1.1(A) of the Company Disclosure Letter')
        edge('condition', 'definition', 'inquiry', quote='in each case after reasonable inquiry')
        unknowns.extend([
            'The supplied (a) Company-side branch does not supply any other party branch or the disclosure-letter individuals.',
            'The schedule reference supplies a designated group,not the names or employment roles of its members.',
        ])
    graph = {'nodes': nodes, 'relations': relations, 'scope_complete': False, 'unresolved': unknowns}
    gi.validate(graph, units)
    return graph


def prepare():
    if sha(CACHE) != CACHE_SHA256:
        raise ValueError('Preserve the exact historical partial source judgments')
    checkpoint = read(BASE / 'handoff/current_checkpoint.json')
    registry_root = ROOT / checkpoint['formal_source_reference_registry']['artifact_root']
    roles = {r['source']: r for r in read(registry_root / 'roles.json')}
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    public = {s['key']: s for s in read(public_path)}
    cache = {r['source']: r for r in read(CACHE)}
    builders = [Path(__file__), ROOT / 'experiments/two_method_annotate.py',
                ROOT / 'legal_skill_guard/paired_interfaces/graph_interface.py',
                ROOT / 'legal_skill_guard/skill_evolution/objects.py']
    protocol = {'experiment': 'two_cached_MAUD_knowledge_views_root_source_review_v1',
        'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in builders},
        'original_TRAIN_public_sha256': sha(public_path), 'cached_partial_review_sha256': sha(CACHE),
        'source_units_locks': LOCKS, 'view': 'v0',
        'manual_source_review_not_automatic_semantic_certification': True,
        'native_questions_answers_or_labels_used': False, 'new_model_requests': 0,
        'older_partial_judgments_not_promoted_to_whole_case_gold': True,
        'fixed_source_roles': {source: roles[source] for source in LOCKS}}
    out = BASE / 'cached_MAUD_source_reviews_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    rows = []
    for source, units_sha in LOCKS.items():
        if roles[source]['role'] != 'calibration':
            raise ValueError('These two original calibration mothers cannot change role')
        task, mapping = inputs(public[source])
        units = next(v['source_units'] for v in task['views'] if v['view_id'] == 'v0')
        if (digest(units) != units_sha or cache[source]['evidence_quote'] != ''.join(u['text'] for u in units)
                or cache[source]['partial_only'] is not True or cache[source]['unreviewed_fields_are_not_false'] is not True):
            raise ValueError('The partial review no longer matches the complete current supplied view')
        graph = reviewed_graph(source, units)
        card = {'source': source, 'view_id': 'v0', 'role': roles[source]['role'],
            'source_units_sha256': units_sha, 'native_views': sorted(k for k, v in mapping.items() if v == 'v0'),
            'graph': graph, 'source_semantic_truth_verified': True, 'reference_ready': True,
            'native_answers_used_to_create_or_repair_graph': False, 'complete_native_case_gold_claimed': False,
            'reviewer': 'root assistant source audit;not independent human annotation',
            'verification_scope': 'Every asserted local node and relation checked against both supplied units/branch;unknown scope retained.',
            'source_span_checks': gi.validate(graph, units),
            'review': {'cached_partial_source_judgment': str(CACHE.relative_to(ROOT)),
                'cached_partial_sha256': sha(CACHE), 'entire_supplied_view_read': True,
                'inquiry_holder_target_distinction_verified': True,
                'no_employment_membership_or_missing_branch_inferred': True,
                'scoped_IP_exception_and_non_imputation_separate': source.startswith('MAUD:7e2add3c')},
            'new_model_requests': 0}
        path = out / 'cards' / digest([source, 'v0']) / 'source_review.json'
        immutable_json(path, card)
        rows.append({'source': source, 'view': 'v0', 'kind': 'literal_semantic_graph',
                     'path': str(path.relative_to(ROOT)), 'sha256': sha(path)})
    manifest = {'reviews': rows, 'root_source_review_not_independent_human_gold': True,
        'partial_ontology_and_unresolved_facts_retained': True, 'new_model_requests': 0,
        'no_native_grading_or_reference_consumer_score_used_to_edit_graph': True}
    immutable_json(out / 'manifest.json', manifest)
    for builder in builders:
        snapshot = out / 'source_snapshot' / builder.relative_to(ROOT)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if snapshot.exists() and snapshot.read_bytes() != builder.read_bytes():
            raise ValueError('An immutable source-review builder changed')
        if not snapshot.exists(): snapshot.write_bytes(builder.read_bytes())
    return out, manifest


if __name__ == '__main__':
    out, manifest = prepare()
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), 'reviewed_views': len(manifest['reviews']),
        'new_model_requests': 0, 'complete_goal_claimed': False}, ensure_ascii=False))
