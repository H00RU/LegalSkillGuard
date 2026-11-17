"""Explicit root-reviewed source graphs for sixteen remaining SARA mothers.

The full supplied facts were read before writing these locked recipes. Public
statute/event schemas only validate factual transport;no case Prolog,query,
answer,grading label or weak response is loaded to construct references.
"""
import json
import math
from pathlib import Path

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT, BASE, read, sha
from experiments.two_method_maud_knowledge_reviews import ReviewedGraph, prepare as earlier_reviews
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.paired_interfaces.control_tools import module_assets
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.sara_statute_kernel import GIVENS, fact_vocabulary
from legal_skill_guard.skill_evolution.literal_statutory_givens import CITATIONS, compact


LOCK_PATH = ROOT / 'experiments/source_review_locks/sara_remaining16_20261117.json'


def ref(identity):
    return {'source_node': identity}


class SourceGraph(ReviewedGraph):
    def relation(self, predicate, arguments, quote, *, value=None, status='stated'):
        self.relations.append({'predicate': predicate, 'arguments': arguments,
            'value': value, 'status': status, 'quote': quote, 'unit_id': self.evidence(quote)})

    def factual(self, predicate, arguments, quote):
        ids = list(dict.fromkeys(v['source_node'] for v in arguments if isinstance(v, dict)))
        if not set(ids) <= self.ids: raise ValueError('Factual transport refers to an unobserved node')
        payload = {'predicate': predicate, 'arguments': [
            {'node_argument': ids.index(v['source_node'])} if isinstance(v, dict) else v for v in arguments]}
        self.relation('native_factual_given', ids, quote, value=json.dumps(payload, sort_keys=True))

    def person(self, identity, name, quote):
        return self.node(identity, 'person', 'unspecified', quote, name=name)

    def event(self, identity, concept, quote, *, name=None):
        return self.node(identity, 'event', concept, quote, name=name)

    def date(self, event, predicate, literal, *, quote=None):
        identity = 'time_' + str(len(self.nodes))
        self.node(identity, 'time', 'unspecified', quote or literal, name=literal)
        self.edge(predicate, event, identity, quote or literal)

    def payment(self, identity, quote, payer, payee, amount):
        self.event(identity, 'payment', quote)
        if payer is not None: self.edge('payer', identity, payer, quote)
        self.edge('payee', identity, payee, quote)
        self.relation('amount', [identity], quote, value=amount)

    def marriage(self, identity, quote, people, start):
        self.event(identity, 'marriage', quote)
        for person in people: self.edge('actor', identity, person, quote)
        self.date(identity, 'date_start', start)

    def physical_event(self, identity, predicate, quote, person, date, *, date_quote=None, name=None, date_predicate='date_start'):
        self.event(identity, 'unspecified', quote, name=name)
        self.edge('actor', identity, person, quote)
        self.factual(predicate, [ref(identity)], quote)
        self.factual('agent_', [ref(identity), ref(person)], quote)
        self.date(identity, date_predicate, date, quote=date_quote)

    def service(self, identity, concept, quote, workers, start=None, end=None):
        self.event(identity, concept, quote)
        for worker in workers: self.edge('worker', identity, worker, quote)
        if start: self.date(identity, 'date_start', start)
        if end: self.date(identity, 'date_end', end)

    def income(self, quote, amount, year, *, year_quote):
        self.event('income', 'income', quote)
        self.edge('subject', 'income', 'alice', quote)
        self.relation('amount', ['income'], quote, value=amount)
        self.date('income', 'date_at', str(year), quote=year_quote)

    def allowance(self, identity, quote, claimant, amount=None, beneficiary=None):
        self.node(identity, 'effect', 'unspecified', quote)
        self.edge('subject', identity, claimant, quote)
        if beneficiary: self.edge('recipient', identity, beneficiary, quote)
        if amount is not None: self.relation('amount', [identity], quote, value=amount)


def validate_factual_records(graph):
    """Data-only ABI checks do not certify the source meaning or a verdict."""
    template = module_assets('SARA_v2_Binary')['statute_kernel_template']
    primitive = fact_vocabulary((ROOT / template['statute_directory'] / 'events.pl').read_text())
    arities = {**primitive, **{k: len(v) for k, v in GIVENS.items()}}
    nodes = {n['id'] for n in graph['nodes']}
    count = 0
    for edge in graph['relations']:
        if edge['predicate'] != 'native_factual_given': continue
        record = json.loads(edge['value']); predicate = record['predicate']
        if (set(record) != {'predicate', 'arguments'} or predicate not in arities
                or len(record['arguments']) != arities[predicate] or edge['status'] != 'stated'):
            raise ValueError('Only declared positive source-factual data records are used')
        types = [v['type'] for v in GIVENS[predicate]] if predicate in GIVENS else ['string'] * arities[predicate]
        if predicate == 'amount_': types[-1] = 'number'
        for value, expected_type in zip(record['arguments'], types):
            if isinstance(value, dict):
                if (set(value) != {'node_argument'} or type(value['node_argument']) is not int
                        or not 0 <= value['node_argument'] < len(edge['arguments'])
                        or edge['arguments'][value['node_argument']] not in nodes or expected_type != 'string'):
                    raise ValueError('Preserve graph referents through factual variable renaming')
            elif (expected_type == 'string' and type(value) is not str
                    or expected_type == 'integer' and type(value) is not int
                    or expected_type == 'number' and (type(value) not in (int, float) or not math.isfinite(value))):
                raise ValueError('Native factual literals must keep declared scalar types')
        if predicate in GIVENS:
            if compact(CITATIONS[predicate]) not in compact(edge['quote']):
                raise ValueError('A statutory given needs its exact source citation')
            for value, specification in zip(record['arguments'], GIVENS[predicate]):
                if specification['role'] == 'year' and (type(value) is not int or str(value) not in edge['quote']):
                    raise ValueError('Never fill a statutory-given year from another sentence or a query')
        count += 1
    return {'data_records': count, 'source_meaning_or_native_answer_certified': False}


def reviewed_graph(source, units):
    locks = {r['source']: r for r in read(LOCK_PATH)}
    if source not in locks or digest(units) != locks[source]['units_sha256']:
        raise ValueError('Only the sixteen exact source views read for this review are covered')
    key = source.split(':')[1][:8]; g = SourceGraph(units)
    complete = True
    unknown = []
    text = [u['text'].strip() for u in units]
    g.person('alice', 'Alice', text[0])
    if key not in ('09756870', 'cc4d8236', '02e9175d'):
        bob_quote = next(t for t in text if 'Bob' in t)
        g.person('bob', 'Bob', bob_quote)
    if key == '815f377b':
        g.service('employment', 'employment', text[0], ['bob'])
        g.edge('employer', 'employment', 'alice', text[0])
        g.date('employment', 'date_start', 'Jan 2nd, 2011')
        g.date('employment', 'date_end', 'Oct 10, 2019', quote='to Oct 10, 2019')
        for identity, predicate, word in (('disability', 'disability_', 'diagnosed as disabled'), ('retirement', 'retirement_', 'retired')):
            g.physical_event(identity, predicate, text[1], 'bob', 'Oct 10, 2019',
                date_quote='On Oct 10, 2019', name=word,
                date_predicate='date_at' if identity == 'disability' else 'date_start')
        g.payment('payment', text[2], 'alice', 'bob', 12980)
        reason = "because she had to terminate their contract due to Bob's disability"
        g.node('termination_necessity', 'condition', 'unspecified', reason)
        g.edge('condition', 'payment', 'termination_necessity', reason)
        g.edge('condition', 'termination_necessity', 'disability', "due to Bob's disability")
        complete = False
        unknown = ['Payment date,remuneration means and any benefit-plan terms are not supplied.',
            'Disability diagnosis has a stated observation date,not a stated onset date.',
            'Employment end and diagnosis/retirement dates are stated separately;none is copied into the payment date.',
            'Had-to-terminate is the stated payment explanation;no independently dated termination act or retirement-for-disability causation is invented.']
    elif key in ('8175fcb9', '6a38111a', 'a3080e73'):
        g.payment('payment', text[0], None, 'alice', 33200)
        g.date('payment', 'date_at', '2017', quote='In 2017')
        g.marriage('marriage', text[1], ['alice', 'bob'], 'Feb 3rd, 2017')
        unknown = ['The payer,payment day,remuneration means and tax nature of the paid amount are not supplied.',
                   'Marriage start is given;no unreported end date or other life events are inferred.']
        if key == '8175fcb9':
            g.allowance('bob_itemized_allowance', text[2], 'bob', 4324)
            g.event('separate_returns', 'unspecified', text[3])
            for person in ('alice', 'bob'): g.edge('actor', 'separate_returns', person, text[3])
            g.relation('category', ['separate_returns'], text[3], value='separate returns')
            complete = False
            unknown += ['An itemized deduction allowance is not an assertion that Bob elected to itemize.',
                'No year is stated on the allowance or separate-return clause;2017 is not copied from the payment.',
                'Separate returns are literal filing information,not a fabricated closed-world absence of every joint return.']
        elif key == '6a38111a':
            for identity, beneficiary, citation in (('self_allowance', 'alice', '63(f)(1)(A)'), ('spouse_allowance', 'bob', '63(f)(1)(B)')):
                g.allowance(identity, text[2], 'alice', 600, beneficiary)
                g.node(identity + '_citation', 'information', 'unspecified', citation)
                g.edge('standard', identity, identity + '_citation', citation)
            complete = False
            unknown += ['Each600 allowance keeps its respective beneficiary and citation;no combined1200 record replaces them.',
                'The allowance sentence supplies no tax year;no year-bearing63(f) native given or age/disability conclusion is invented.']
        else:
            g.physical_event('blindness', 'blindness_', text[2], 'alice', 'March 20, 2016', name='blind')
            unknown += ['The blindness onset is explicit;no additional deduction entitlement is derived into the graph.']
    elif key == '5c29a3a2':
        g.person('charlie', 'Charlie', text[2])
        g.event('son_relation', 'kinship', text[0])
        g.factual('son_', [ref('son_relation')], text[0])
        g.factual('agent_', [ref('son_relation'), ref('bob')], text[0])
        g.factual('patient_', [ref('son_relation'), ref('alice')], text[0])
        g.node('home', 'place', 'unspecified', 'the same home')
        g.event('residence', 'residence', text[1])
        for person in ('alice', 'bob'): g.edge('actor', 'residence', person, text[1])
        g.edge('object', 'residence', 'home', 'lived in the same home')
        g.date('residence', 'date_start', 'September 1st, 2015')
        g.date('residence', 'date_end', 'February 3rd, 2019')
        g.marriage('bob_marriage', text[2], ['bob', 'charlie'], 'October 23rd, 2018')
        g.node('relationship_given', 'condition', 'unspecified', text[3])
        g.edge('subject', 'relationship_given', 'bob', text[3]); g.edge('object', 'relationship_given', 'alice', text[3])
        g.date('relationship_given', 'date_at', '2015 to 2020', quote='for the years 2015 to 2020')
        complete = False
        unknown = ['No birth date,age,home title or legal dependency beyond the explicit152(c)(2) wording is supplied.',
            'The152(c)(2) claim is not152(c)(1),and year-range precision is not replaced by invented full-day boundaries.',
            'The current native-given ABI has no152(c)(2) premise port;the literal source claim is retained without a derived statutory fact.']
    elif key == '09756870':
        g.income(text[0], 276932, 2015, year_quote='in 2015')
        g.node('married_status', 'condition', 'unspecified', 'not married', name='married')
        g.relation('category', ['alice', 'married_status'], text[1], status='negated')
        g.node('applicable_amount', 'information', 'unspecified', text[2])
        g.relation('amount', ['applicable_amount'], text[2], value=250000)
        complete = False
        unknown = ['Income year2015 does not supply a full-day interval or a year on the unmarried clause.',
            'No gross/adjusted/taxable classification beyond the literal income wording is inferred.',
            'The literal68(b) applicable amount remains a source statement;no unsupported native-given predicate or status derivation is inserted.']
    elif key == 'cc4d8236':
        g.node('married_given', 'condition', 'unspecified', text[0])
        g.edge('subject', 'married_given', 'alice', text[0])
        g.date('married_given', 'date_at', '2017', quote='married under section 7703 for the year 2017')
        g.income(text[1], 6662, 2017, year_quote="Alice's taxable income for the year 2017")
        g.relation('category', ['income'], text[1], value='taxable income')
        g.event('separate_return', 'unspecified', text[2]); g.edge('actor', 'separate_return', 'alice', text[2])
        complete = False
        unknown = ['The supplied7703 marital status is not a newly invented wedding event,spouse or marriage date.',
            'Taxable income is explicit;its amount is not a payment or a computed tax liability.',
            'The current given ABI does not encode7703 status directly;separate-return year is not explicitly stated.']
    elif key == 'd5e1138c':
        g.payment('payment', text[0], 'alice', 'bob', 2325)
        g.date('payment', 'date_at', '2018', quote='Over the year 2018')
        g.node('hay', 'information', 'noncash', 'in hay', name='hay')
        g.edge('object', 'payment', 'hay', 'in hay')
        g.factual('means_', [ref('payment'), 'hay'], 'in hay')
        g.service('labor', 'agricultural_labor', 'agricultural labor', ['bob'])
        g.edge('service_link', 'payment', 'labor', 'to Bob for agricultural labor')
        unknown = ['2325 is the stated monetary value paid in hay,not a quantity of hay.',
            'Exact payment/service dates,the employer/service recipient and hay quantity are not supplied.']
    elif key == 'e1624002':
        g.allowance('exemption_claim', text[0], 'alice', beneficiary='bob')
        g.date('exemption_claim', 'date_at', '2015', quote='for the year 2015')
        complete = False
        unknown = ['No exemption amount,relationship,age or151(c) premise is supplied.',
            'The explicit151(d) source claim is retained;it is not converted into a different-citation native given.']
    elif key == '02e9175d':
        g.income(text[0], 310192, 2018, year_quote='In 2018')
        g.node('surviving_spouse_status', 'condition', 'unspecified', text[1])
        g.edge('subject', 'surviving_spouse_status', 'alice', text[1])
        g.date('surviving_spouse_status', 'date_at', '2018', quote='for the year 2018')
        g.allowance('itemized_allowance', text[2], 'alice', 600)
        complete = False
        unknown = ['A surviving-spouse status statement supplies no invented spouse,death date or prior marriage chronology.',
            'The allowed600 itemized deduction is not an assertion of a filing election;its sentence states no year.',
            'The parent-section63 citation is not silently strengthened to a particular subsection given.']
    elif key == '743ac2e5':
        g.marriage('marriage', text[0], ['alice', 'bob'], 'April 5th, 2012')
        g.event('separation', 'unspecified', text[1])
        for person in ('alice', 'bob'): g.edge('subject', 'separation', person, text[1])
        g.node('decree', 'information', 'unspecified', 'a decree of divorce')
        g.edge('standard', 'separation', 'decree', 'under a decree of divorce')
        g.factual('legal_separation_', [ref('separation')], text[1])
        g.factual('patient_', [ref('separation'), ref('marriage')], text[1])
        g.factual('agent_', [ref('separation'), 'decree of divorce'], 'under a decree of divorce')
        g.date('separation', 'date_start', 'September 16th, 2017')
        unknown = ['The decree token is the frozen native ABI authority selector,not a newly named human party.',
            'The separation date is not separately asserted as the marriage end date or as a complete later marital history.']
    elif key == 'bb6b0bc1':
        g.payment('payment', text[0], 'alice', 'bob', 3200)
        g.service('service', 'domestic_service', 'domestic service done in her home', ['bob'], 'Feb 1st, 2017', 'Sep 2nd, 2017')
        g.edge('service_link', 'payment', 'service', 'to Bob for domestic service done in her home')
        g.node('home', 'place', 'unspecified', 'in her home', name='her home')
        g.edge('object', 'service', 'home', 'in her home')
        g.factual('location_', [ref('service'), ref('home')], 'in her home')
        g.factual('country_', [ref('home'), 'usa'], 'Baltimore, Maryland, USA')
        unknown = ['Service dates are not payment dates;wages and dollar value do not identify cash means.',
            'Payer and home location do not establish a legal employer,service recipient or legal title to the home.',
            'USA is transported as the immutable native lowercase country token usa;no unstated country is inferred.']
    elif key == 'cc82ab0f':
        g.person('charlie', 'Charlie', text[0])
        g.marriage('marriage', text[0], ['alice', 'charlie'], '2 Feb 2015')
        g.node('dependent_given', 'condition', 'unspecified', text[1])
        g.edge('subject', 'dependent_given', 'bob', text[1]); g.edge('object', 'dependent_given', 'alice', text[1])
        g.factual('s152_c_1', [ref('bob'), ref('alice'), 2015], text[1])
        unknown = ['The explicit152(c)(1) premise is retained;no son relation,birth date or other family relationship is invented.',
            'No source-given record is derived from a native question or answer.']
    elif key == 'cd2ab8fc':
        g.marriage('marriage', text[0], ['alice', 'bob'], 'Feb 3rd, 1992')
        g.physical_event('death', 'death_', text[1], 'alice', 'July 9th, 2014')
        unknown = ['Alice is the stated decedent;no death of Bob,marriage end date or surviving-spouse entitlement is inserted.',
                   'Other marital history and post-death events are not supplied.']
    elif key == 'a51930fd':
        g.person('charlie', 'Charlie', text[1])
        for identity, parent, child, quote in (('son_bob', 'alice', 'bob', text[0]), ('son_charlie', 'bob', 'charlie', text[1])):
            g.event(identity, 'kinship', quote)
            g.factual('son_', [ref(identity)], quote)
            g.factual('agent_', [ref(identity), ref(child)], quote)
            g.factual('patient_', [ref(identity), ref(parent)], quote)
            g.factual('s152_c_1', [ref(child), ref(parent), 2015], quote)
        unknown = ['The two stated parent/son clauses retain their own152(c)(1) premise and2015.',
            'No birth dates,ages or transitive statutory qualification of Charlie with respect to Alice are inferred.']
    elif key == 'd9d6b236':
        for identity, name in (('charlie', 'Charlie'), ('dan', 'Dan')): g.person(identity, name, text[0])
        g.service('agricultural_labor', 'agricultural_labor', 'agricultural labor done from Feb 1st, 2017 to Sep 2nd, 2017',
            ['bob', 'charlie', 'dan'], 'Feb 1st, 2017', 'Sep 2nd, 2017')
        for identity, payee, amount, quote in (('pay_bob', 'bob', 6771, '$6771 to Bob'),
            ('pay_charlie', 'charlie', 6954, '$6954 to Charlie'), ('pay_dan', 'dan', 6872, '$6872 to Dan')):
            g.payment(identity, quote, 'alice', payee, amount)
            g.edge('service_link', identity, 'agricultural_labor', text[0])
        g.service('other_work', 'service', 'work done from Apr 1st, 2017 to Sep 2nd, 2018', ['alice'], 'Apr 1st, 2017', 'Sep 2nd, 2018')
        g.payment('reverse_payment', text[1], 'bob', 'alice', 4520)
        g.edge('service_link', 'reverse_payment', 'other_work', text[1])
        complete = False
        unknown = ['The first labor mention is an aggregate across named payees;the number/grouping of individual physical engagements is not certified.',
            'Each remuneration retains its own payee/amount;the reverse payment and its longer work period stay separate.',
            'No payment dates,cash means or legal employers/service recipients are supplied.']
    else:
        raise ValueError('No explicit reviewed recipe for this locked source')
    graph = g.finish(complete=complete, unknown=unknown)
    validate_factual_records(graph)
    return graph


def prepare():
    locks = read(LOCK_PATH)
    if len(locks) != 16 or len({r['source'] for r in locks}) != 16:
        raise ValueError('Preserve all sixteen reviewed original SARA mothers')
    _, previous = earlier_reviews()
    c = read(BASE / 'handoff/current_checkpoint.json')
    roles = {r['source']: r for r in read(ROOT / c['formal_source_reference_registry']['artifact_root'] / 'roles.json')}
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    public = {s['key']: s for s in read(public_path)}
    template = module_assets('SARA_v2_Binary')['statute_kernel_template']
    builders = [Path(__file__), LOCK_PATH, ROOT / 'experiments/two_method_maud_knowledge_reviews.py',
        ROOT / 'experiments/source_review_locks/maud_knowledge_remaining14_20261117.json',
        ROOT / 'experiments/two_method_cached_maud_reviews.py', ROOT / 'experiments/two_method_annotate.py',
        ROOT / 'legal_skill_guard/paired_interfaces/graph_interface.py', ROOT / 'legal_skill_guard/skill_evolution/objects.py',
        ROOT / 'legal_skill_guard/skill_evolution/sara_statute_kernel.py',
        ROOT / 'legal_skill_guard/skill_evolution/literal_statutory_givens.py',
        ROOT / template['statute_directory'] / 'events.pl']
    protocol = {'experiment': 'remaining16_SARA_source_only_root_reviews_v1',
        'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in builders},
        'original_TRAIN_public_sha256': sha(public_path), 'locked_original_roles_and_sources': locks,
        'prior16_extra_card_index_sha256': digest(previous), 'native_target_questions_labels_or_weak_outputs_used': False,
        'explicit_root_review_not_automatic_semantic_certification': True,
        'interactive_root_annotation_cost_usd': None, 'new_experimental_endpoint_requests': 0}
    out = BASE / 'SARA_source_reviews_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    rows = list(previous['reviews'])
    for lock in locks:
        source = lock['source']; role = roles[source]
        if (role['role'], role['batch']) != (lock['role'], lock['batch']) or role['role'] == 'structure_evaluation':
            raise ValueError('The original role/batch cannot be repaired or reassigned')
        task, mapping = inputs(public[source])
        if len(task['views']) != 1: raise ValueError('Do not collapse multiple source views')
        units = task['views'][0]['source_units']; graph = reviewed_graph(source, units)
        card = {'source': source, 'view_id': 'v0', 'role': role['role'],
            'source_units_sha256': lock['units_sha256'], 'native_views': sorted(mapping),
            'graph': graph, 'reference_ready': True, 'source_semantic_truth_verified': True,
            'native_answers_used_to_create_or_repair_graph': False, 'complete_native_case_gold_claimed': False,
            'reviewer': 'root assistant explicit source review;not independent human annotation',
            'verification_scope': 'All asserted local roles,amounts,dates and source legal claims against the entire supplied facts;unknown scope retained.',
            'source_span_checks': gi.validate(graph, units), 'factual_record_transport_checks': validate_factual_records(graph),
            'review': {'entire_supplied_view_read': True, 'source_sha_locked': True,
                'no_dollars_to_cash_income_or_employer_inference': True,
                'no_missing_year_day_spouse_or_statutory_subsection_filled': True,
                'no_native_reference_F_output_or_grading_used_to_edit_graph': True},
            'new_model_requests': 0}
        path = out / 'cards' / digest([source, 'v0']) / 'source_review.json'
        immutable_json(path, card)
        rows.append({'source': source, 'view': 'v0', 'kind': 'literal_semantic_graph',
                     'path': str(path.relative_to(ROOT)), 'sha256': sha(path)})
    if len(rows) != 32 or len({(r['source'], r['view']) for r in rows}) != 32:
        raise ValueError('Keep the prior sixteen and all new sixteen reviews exactly once')
    manifest = {'reviews': rows, 'new_root_reviewed_views': 16, 'previous_extra_reviews_retained': 16,
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
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), 'new_reviewed_mothers': 16,
        'cumulative_explicit_review_views': len(manifest['reviews']),
        'new_model_requests': 0, 'complete_goal_claimed': False}, ensure_ascii=False))
