"""Explicit root source reviews of the fourteen remaining MAUD v0 excerpts.

Every recipe below was read against its entire hash-locked supplied view.
These are source annotations,not automatically certified legal/answer gold.
No new teacher/executor request,answer label or target question is consumed.
"""
import json
from pathlib import Path

from experiments.two_method_annotate import inputs
from experiments.two_method_cached_maud_reviews import prepare as original_two_cards
from experiments.two_method_graph_corpus import ROOT, BASE, read, sha
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


LOCK_PATH = ROOT / 'experiments/source_review_locks/maud_knowledge_remaining14_20261117.json'


class ReviewedGraph:
    """Evidence bookkeeping only;all concepts/attachments are explicit recipes."""
    def __init__(self, units):
        self.units = units; self.nodes = []; self.relations = []; self.ids = set()

    def evidence(self, quote):
        matches = [u['id'] for u in self.units for _ in range(u['text'].count(quote))]
        if not quote or len(matches) != 1:
            raise ValueError('Use a unique reviewed contiguous quote,without changing source units: ' + quote)
        return matches[0]

    def node(self, identity, kind, concept, quote, *, name=None):
        if identity in self.ids: raise ValueError('Duplicate reviewed node identity')
        self.ids.add(identity)
        self.nodes.append({'id': identity, 'kind': kind, 'concept': concept, 'name': name or quote,
                           'quote': quote, 'unit_id': self.evidence(quote)})
        return identity

    def edge(self, predicate, left, right, quote):
        self.relations.append({'predicate': predicate, 'arguments': [left, right], 'value': None,
            'status': 'stated', 'quote': quote, 'unit_id': self.evidence(quote)})

    def branch(self, identity, anchor, holders, *, subject=None, subject_quote=None,
               holder_id=None, holder_evidence=None, actual_evidence=None, actual_id=None,
               subject_kind='organization', holder_kind='group'):
        self.node(identity, 'definition', 'knowledge_definition', anchor)
        if subject is not None:
            target = self.node(identity + '_subject', subject_kind, 'unspecified', subject_quote or subject, name=subject)
            self.edge('subject', identity, target, subject_quote or subject)
        holder = holder_id or identity + '_holders'
        if holder not in self.ids:
            self.node(holder, holder_kind, 'unspecified', holder_evidence or holders, name=holders)
        self.edge('object', identity, holder, holder_evidence or holders)
        if actual_evidence is not None:
            actual = actual_id or identity + '_actual_wording'
            if actual not in self.ids:
                self.node(actual, 'condition', 'explicit_actual_wording', actual_evidence, name='actual knowledge')
            self.edge('standard', identity, actual, actual_evidence)
        return holder

    def inquiry(self, definitions, quote, concept):
        self.node('inquiry', 'condition', concept, quote)
        for definition in definitions: self.edge('condition', definition, 'inquiry', quote)

    def finish(self, *, complete, unknown):
        graph = {'nodes': self.nodes, 'relations': self.relations,
                 'scope_complete': complete, 'unresolved': unknown}
        gi.validate(graph, self.units)
        return graph


def reviewed_graph(source, units):
    locks = {r['source']: r for r in read(LOCK_PATH)}
    if source not in locks or digest(units) != locks[source]['units_sha256']:
        raise ValueError('Only an exact source view explicitly read for these fourteen reviews is covered')
    key = source.split(':')[1][:8]; g = ReviewedGraph(units)
    complete = True
    unknown = []
    if key == '294850b3':
        h = 'the individuals named on Section 1.1(a) of the Company Disclosure Schedule'
        holders = g.branch('company', '“Knowledge”, whether or not capitalized, or any similar expression:', h,
            subject='the Company', subject_quote='with respect to the Company', actual_evidence='the actual knowledge of ' + h)
        g.inquiry(['company'], 'after reasonable inquiry of those employees directly reporting to such Person', 'reasonable_inquiry_required')
        g.node('direct_report_employees', 'group', 'unspecified', 'those employees directly reporting to such Person')
        g.edge('recipient', 'inquiry', 'direct_report_employees', 'inquiry of those employees directly reporting to such Person')
        g.node('reporting_qualification', 'condition', 'unspecified', 'directly reporting to such Person')
        g.edge('condition', 'direct_report_employees', 'reporting_qualification', 'directly reporting to such Person')
        g.edge('object', 'reporting_qualification', holders, 'directly reporting to such Person')
        complete = False
        unknown = ['Only the supplied (i) Company branch is present;other branches and scheduled identities are unavailable.',
            'The employee group is the inquiry target;the designated holders are the reporting referents,not the same target.',
            'The legal employer and separately designated inquiry performer are not stated.']
    elif key == 'a3142f07':
        h = 'those persons set forth in Section 8.10(a) of the Company Disclosure Schedule'
        g.branch('company', '“Knowledge” means (i) with respect to the Company', h,
            subject='the Company', subject_quote='with respect to the Company', actual_evidence='the actual knowledge of ' + h)
        complete = False
        unknown = ['The supplied clause ends in and;further branches or qualifications are not supplied.',
            'An inquiry policy is not stated in this supplied branch;it is not replaced by no-inquiry-required.',
            'Scheduled identities and legal employment status are not supplied.']
    elif key == '9f3b4889':
        for identity, subject, letter, anchor in (
            ('company', 'the Company and its Subsidiaries', 'the Company’s', '(a) with respect to the Company and its Subsidiaries'),
            ('parent', 'Parent and its Subsidiaries', 'Parent’s', '(b) with respect to Parent and its Subsidiaries')):
            h = 'each of the individuals listed in Section 9.01 of ' + letter + ' Disclosure Letter'
            g.branch(identity, anchor, h, subject=subject, subject_quote=anchor,
                     subject_kind='group', actual_evidence='the actual knowledge of ' + h)
        g.inquiry(['company', 'parent'], 'in each case, after due inquiry', 'due_inquiry_required')
        unknown = ['Neither inquiry targets nor a separate inquiry performer are stated.',
            'The two letters designate their respective groups;member names,employment and overlap are unknown.']
    elif key == 'aaf70b03':
        h = 'the chief executive officer, president, chief financial officer, chief credit officer or general counsel of Nicolet or the Company'
        g.branch('definition', '“Knowledge” means', h, actual_evidence='the actual knowledge of ' + h)
        g.node('party_choice', 'condition', 'unspecified', 'of Nicolet or the Company, as the context requires')
        g.edge('condition', 'definition', 'party_choice', 'of Nicolet or the Company, as the context requires')
        g.inquiry(['definition'], 'assuming due inquiry under the facts or circumstances', 'due_inquiry_required')
        unknown = ['The applicable party/title alternative depends on context;no joint or simultaneous holder assignment is inferred.',
            'Inquiry targets,performer and the underlying facts/circumstances are not supplied.']
    elif key == 'e4081ab8':
        h = 'any of the individuals set forth on Schedule 1.1.'
        g.branch('company', '“Knowledge of the Company”', h, subject='the Company',
            subject_quote='“Knowledge of the Company”', actual_evidence='the actual knowledge of ' + h)
        unknown = ['The supplied definition does not state an inquiry policy;absence is not no-inquiry-required.',
            'Schedule1.1 identities and employment/title details are not supplied.']
    elif key == '04bc1032':
        h = 'the individuals listed on \u200bSection 9.5(b) of the Company Disclosure Letter'
        g.branch('company', '(b) with respect to the Company', h, subject='the Company',
            subject_quote='with respect to the Company', actual_evidence='the actual knowledge of ' + h)
        g.inquiry(['company'], 'after due inquiry', 'due_inquiry_required')
        complete = False
        unknown = ['The explicit omitted portion remains unread;no other party branch or qualifier is reconstructed.',
            'Scheduled identities,inquiry targets,performer and employment status are unavailable.']
    elif key == 'bed0af63':
        for identity, anchor, subject, h in (
            ('company', '(i) with respect to the Company', 'the Company', 'any of the individuals listed on Section 1.01(a) of the Company Disclosure Schedule'),
            ('parent', '(ii) with respect to Parent', 'Parent', 'any of the Chief Executive Officer, Chief Financial Officer or the General Counsel of Parent')):
            g.branch(identity, anchor, h, subject=subject, subject_quote=anchor, actual_evidence='the actual knowledge of ' + h)
        g.inquiry(['company', 'parent'], 'in each case, after reasonable inquiry', 'reasonable_inquiry_required')
        unknown = ['The separate Company schedule and Parent officer group are not exchanged or merged.',
            'The source supplies no inquiry target or separate performer;officer titles are not legal employee classifications.']
    elif key == '5a36bd3b':
        h = 'such Entity’s executive officers'
        g.branch('definition', '“Knowledge” with respect to an Entity', h, actual_evidence='the actual knowledge of ' + h)
        g.node('entity_scope', 'condition', 'unspecified', 'with respect to an Entity')
        g.edge('condition', 'definition', 'entity_scope', 'with respect to an Entity')
        g.node('matter_scope', 'condition', 'unspecified', 'with respect to any matter in question')
        g.edge('condition', 'definition', 'matter_scope', 'with respect to any matter in question')
        g.inquiry(['definition'], 'after reasonable inquiry of their direct reports', 'reasonable_inquiry_required')
        g.node('direct_reports', 'group', 'unspecified', 'their direct reports')
        g.edge('recipient', 'inquiry', 'direct_reports', 'inquiry of their direct reports')
        unknown = ['Entity is a literal definition parameter;no unprovided legal form or employer is inferred.',
            'Direct reports are the target class;they are not substituted with the executive officers or silently typed as employees.',
            'Individual identities and a separately identified inquiry performer remain unknown.']
    elif key == 'b3fc96b4':
        h = 'the chairman, president, chief financial officer, chief credit officer, or any senior or executive vice president of such Person'
        holders = g.branch('definition', '“Knowledge” as used', h)
        g.node('person_scope', 'condition', 'unspecified', 'with respect to a Person')
        g.edge('condition', 'definition', 'person_scope', 'with respect to a Person')
        alias = '(including references to such Person being aware of a particular matter)'
        g.node('awareness_wording_scope', 'condition', 'unspecified', alias)
        g.edge('condition', 'definition', 'awareness_wording_scope', alias)
        standard = 'those facts that are known or should reasonably have been known'
        g.node('knowledge_alternative', 'condition', 'unspecified', standard)
        g.edge('standard', 'definition', 'knowledge_alternative', standard)
        g.inquiry(['definition'], 'after due inquiry of the records and employees of such Person', 'due_inquiry_required')
        g.node('records', 'information', 'unspecified', 'the records and employees of such Person', name='the records')
        g.node('employees', 'group', 'unspecified', 'employees of such Person')
        g.edge('recipient', 'inquiry', 'records', 'inquiry of the records and employees of such Person')
        g.edge('recipient', 'inquiry', 'employees', 'inquiry of the records and employees of such Person')
        g.edge('actor', 'inquiry', holders, 'by ' + h)
        g.node('investigation_limit', 'condition', 'unspecified', 'without any further investigation')
        g.edge('condition', 'inquiry', 'investigation_limit', 'without any further investigation')
        complete = False
        unknown = ['Known-or-should-have-known modality is retained literally;the fixed ontology has no separate modal-alternative operator.',
            'Without further investigation limits the stated records/employee inquiry;it does not remove that due inquiry.',
            'Person remains an unexpanded definition parameter;individual names and legal employment details beyond the stated group are unknown.']
    elif key == '195081ce':
        scheduled = 'the individuals set forth in Section 1.1(a) of the Company Disclosure Letter'
        future = ('any other individuals that, following the date of this Agreement, replace or share the employment '
                  'responsibilities of any such scheduled individuals')
        g.branch('definition', '“Knowledge” means', scheduled, holder_id='scheduled',
            actual_evidence='“Knowledge” means the actual knowledge of', actual_id='actual_wording')
        g.node('future_holders', 'group', 'unspecified', future)
        g.edge('object', 'definition', 'future_holders', 'and ' + future)
        g.node('future_time', 'condition', 'unspecified', 'following the date of this Agreement')
        g.edge('condition', 'future_holders', 'future_time', 'following the date of this Agreement')
        qualification = 'replace or share the employment responsibilities of any such scheduled individuals'
        g.node('role_qualification', 'condition', 'unspecified', qualification)
        g.edge('condition', 'future_holders', 'role_qualification', qualification)
        g.inquiry(['definition'], 'in each case after reasonable due inquiry', 'due_inquiry_required')
        g.node('reasonableness', 'condition', 'unspecified', 'reasonable due inquiry', name='reasonable')
        g.edge('condition', 'inquiry', 'reasonableness', 'reasonable due inquiry')
        unknown = ['Future replacement/sharing is eligibility wording,not an assertion that a replacement has occurred.',
            'The future-date condition is attached only to the additional holder group,not all scheduled holders.',
            'No inquiry target/performer or exact agreement date is supplied;party scope is not inferred solely from the letter title.',
            'Scheduled and future identities and legal employee status are not supplied.']
    elif key == 'b1a2f5ad':
        h = 'any of the officers of CIT listed on Section 9.6 of the CIT Disclosure Schedule'
        g.branch('cit', '“knowledge” of CIT', h, subject='CIT', subject_quote='“knowledge” of CIT',
            actual_evidence='the actual knowledge of ' + h)
        unknown = ['No inquiry policy is stated in this supplied definition;it is not replaced by no-inquiry-required.',
            'The unsupplied schedule identifies officers as a class,not their names or legal employee status.']
    elif key == 'b8241f8f':
        actual = '“Knowledge” means the actual knowledge'
        parent_names = ('George Holm', 'James Hope', 'Brent King', 'Liz Mountjoy')
        company_names = ('Scott McPherson', 'Christopher Miller', 'Jennifer Hulett', 'Brian Brandon', 'Greg Antholzner')
        for identity, anchor, subject, names in (('parent', 'for Parent', 'Parent', parent_names),
                                                ('company', 'for the Company', 'the Company', company_names)):
            g.node(identity, 'definition', 'knowledge_definition', anchor)
            g.node(identity + '_subject', 'organization', 'unspecified', anchor, name=subject)
            g.edge('subject', identity, identity + '_subject', anchor)
            if 'actual_wording' not in g.ids:
                g.node('actual_wording', 'condition', 'explicit_actual_wording', actual, name='actual knowledge')
            g.edge('standard', identity, 'actual_wording', actual)
            for index, name in enumerate(names):
                person = identity + '_person_' + str(index)
                g.node(person, 'person', 'unspecified', name)
                g.edge('object', identity, person, name)
        g.inquiry(['parent', 'company'], 'after reasonable inquiry', 'reasonable_inquiry_required')
        complete = False
        unknown = ['The source-unit cut splits A. from Brent King;the literal Brent King anchor is retained without inventing an A. person or merging source units.',
            'Parent and Company lists continue across that sentence-unit cut;the named persons are kept on their own supplied branch.',
            'Inquiry target,performer and employment/title roles are not supplied.']
    elif key == '447ae333':
        actual = '“Knowledge” means the actual knowledge of'
        company_h = 'the individuals listed in Schedule 1.1 of the Company Disclosure Letter'
        parent_h = 'the individuals listed in Schedule 1.1 of the Parent Disclosure Letter'
        for identity, anchor, subject, h, holder in (
            ('company', '(a) in the case of the Company', 'the Company', company_h, 'company_letter_group'),
            ('holdings', '(b) in the case of Holdings', 'Holdings', company_h, 'company_letter_group'),
            ('parent', '(c) in the case of Parent', 'Parent', parent_h, 'parent_letter_group')):
            g.branch(identity, anchor, h, subject=subject, subject_quote=anchor,
                holder_id=holder, holder_evidence=anchor + ', ' + h, actual_id='actual_wording', actual_evidence=actual)
        unknown = ['Company and Holdings reference the same Company-letter schedule;Parent references the Parent-letter schedule.',
            'No schedule contents,individual identities or disjointness/overlap of persons are inferred.',
            'No inquiry policy is supplied in this definition;absence is not a no-inquiry obligation.']
    elif key == 'ef95fbbc':
        h = 'any of the individuals set forth in Section 1.1(ooo) of the Company Disclosure Letter'
        holders = g.branch('company', '“Knowledge” of a Person', h,
            subject='the Company', subject_quote='with respect to the Company', actual_evidence='the actual knowledge of ' + h)
        g.node('matter_scope', 'condition', 'unspecified', 'with respect to any matter in question')
        g.edge('condition', 'company', 'matter_scope', 'with respect to any matter in question')
        potential = 'such knowledge as any such individuals would have obtained'
        g.node('potential_knowledge', 'condition', 'unspecified', potential)
        g.edge('standard', 'company', 'potential_knowledge', potential)
        g.edge('actor', 'potential_knowledge', holders, potential)
        g.inquiry(['company'], 'in each case, after reasonable inquiry', 'reasonable_inquiry_required')
        reports = ('their respective direct reports who, in each case, would reasonably be expected '
                   'to have actual knowledge of the matter in question')
        g.node('direct_reports', 'group', 'unspecified', reports)
        g.edge('recipient', 'inquiry', 'direct_reports', 'inquiry of ' + reports)
        qualification = 'who, in each case, would reasonably be expected to have actual knowledge of the matter in question'
        g.node('expected_knowledge_qualification', 'condition', 'unspecified', qualification)
        g.edge('condition', 'direct_reports', 'expected_knowledge_qualification', qualification)
        complete = False
        unknown = ['The would-have-obtained alternative is conditional knowledge,not an assertion that those facts are actually known.',
            'Expected knowledge qualifies the direct-report target group;it does not establish actual knowledge of every report.',
            'The fixed ontology retains modal wording literally;scheduled/report identities,employment and a separate inquiry performer are unknown.']
    else:
        raise ValueError('No manually reviewed recipe for this locked source')
    return g.finish(complete=complete, unknown=unknown)


def prepare():
    locks = read(LOCK_PATH)
    if len(locks) != 14 or len({r['source'] for r in locks}) != 14:
        raise ValueError('Preserve the exact fourteen reviewed source views')
    _, existing = original_two_cards()
    checkpoint = read(BASE / 'handoff/current_checkpoint.json')
    roles = {r['source']: r for r in read(ROOT / checkpoint['formal_source_reference_registry']['artifact_root'] / 'roles.json')}
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    public = {s['key']: s for s in read(public_path)}
    builders = [Path(__file__), LOCK_PATH, ROOT / 'experiments/two_method_cached_maud_reviews.py',
        ROOT / 'experiments/two_method_annotate.py', ROOT / 'legal_skill_guard/paired_interfaces/graph_interface.py',
        ROOT / 'legal_skill_guard/skill_evolution/objects.py']
    protocol = {'experiment': 'remaining14_MAUD_knowledge_source_only_root_reviews_v1',
        'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in builders},
        'original_TRAIN_public_sha256': sha(public_path), 'reviewed_source_locks': locks,
        'previous_two_review_card_index_sha256': digest(existing),
        'explicit_manual_review_of_every_supplied_unit': True,
        'span_checks_are_not_automatic_semantic_certification': True,
        'native_labels_questions_or_weak_outputs_used': False,
        'interactive_root_annotation_overhead_is_not_an_experimental_endpoint_call': True,
        'interactive_root_annotation_cost_usd': None,
        'new_model_requests': 0, 'original_128_roles_and_view_inventory_unchanged': True}
    out = BASE / 'MAUD_knowledge_source_reviews_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    rows = list(existing['reviews'])
    for lock in locks:
        source = lock['source']; role = roles[source]
        if (role['role'], role['batch']) != (lock['role'], lock['batch']) or role['role'] == 'structure_evaluation':
            raise ValueError('Preserve the original role/batch;do not import structural evaluation truth')
        task, mapping = inputs(public[source])
        units = next(v['source_units'] for v in task['views'] if v['view_id'] == 'v0')
        graph = reviewed_graph(source, units)
        card = {'source': source, 'view_id': 'v0', 'role': role['role'],
            'source_units_sha256': lock['units_sha256'], 'native_views': sorted(k for k, v in mapping.items() if v == 'v0'),
            'graph': graph, 'reference_ready': True, 'source_semantic_truth_verified': True,
            'native_answers_used_to_create_or_repair_graph': False, 'complete_native_case_gold_claimed': False,
            'reviewer': 'root assistant explicit source review;not independent human annotation',
            'verification_scope': 'Asserted local nodes/relations against every supplied source unit;unknown and omitted scope retained.',
            'source_span_checks': gi.validate(graph, units),
            'review': {'entire_supplied_view_read': True, 'exact_source_units_hash_locked': True,
                'branch_holder_inquiry_target_qualifier_and_temporal_scope_checked': True,
                'no_native_score_or_source_reference_F_output_used_to_edit_graph': True},
            'new_model_requests': 0}
        path = out / 'cards' / digest([source, 'v0']) / 'source_review.json'
        immutable_json(path, card)
        rows.append({'source': source, 'view': 'v0', 'kind': 'literal_semantic_graph',
                     'path': str(path.relative_to(ROOT)), 'sha256': sha(path)})
    if len({(r['source'], r['view']) for r in rows}) != 16:
        raise ValueError('Keep both prior reviews and all fourteen new distinct views')
    manifest = {'reviews': rows, 'new_root_reviewed_views': 14, 'previous_root_reviewed_views_retained': 2,
        'independent_human_or_complete_legal_gold_claimed': False,
        'interactive_root_annotation_cost_usd': None,
        'unmetered_root_annotation_overhead_not_reported_as_free': True,
        'original_source_roles_and_unknowns_retained': True, 'new_model_requests': 0}
    immutable_json(out / 'manifest.json', manifest)
    for p in builders:
        snapshot = out / 'source_snapshot' / p.relative_to(ROOT)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if snapshot.exists() and snapshot.read_bytes() != p.read_bytes():
            raise ValueError('A frozen source-review builder changed')
        if not snapshot.exists(): snapshot.write_bytes(p.read_bytes())
    return out, manifest


if __name__ == '__main__':
    out, manifest = prepare()
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), 'new_reviewed_views': 14,
        'cumulative_explicit_review_views': len(manifest['reviews']),
        'new_model_requests': 0, 'complete_goal_claimed': False}, ensure_ascii=False))
