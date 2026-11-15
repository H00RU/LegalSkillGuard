"""Complete the actual payment/service observation handoff on original TRAIN.

Learn representations and transductions from real errors; compare a learned
coupled contract, its keyed refinement, and two independent teacher contracts.
Selection uses whole native cases. Existing family, income and legal-given
assets remain available, with no new law, data, model or TEST access.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_observation_domain_update as latest
from experiments import legal_skill_evolution_relation_contract_learning as runtime
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_observation_contract import validate, schema, split
from legal_skill_guard.skill_evolution.case_observation_contract import validate_adapter
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, PROGRAM_INSTRUCTION, pack_programs

ROOT = runtime.ROOT
RUN = 'legal_skill_evolution_payment_contract_refinement_20261115'
OUT = ROOT / 'artifacts' / RUN
BASE = latest.OUT / 'candidate_libraries/Method/1.json'
TARGETS = ('source_payment_relations', 'service_events')
SCHEMA = runtime.SCHEMA
SYSTEM = '''Learn a runnable observation-contract update from actual weak-reader
errors. Return strict JSON only. No tools, model weight changes, new sources,
DEV or TEST. Author statutes and native scoring remain fixed.

Both arms get the SAME common current library, current source texts, lawful TRAIN
supervision, actual failures, API and resources. Target IDs are exactly
source_payment_relations and service_events. The first is a NEW payment relation
component, replacing only payment observation work. Current income and exact
legal-given components remain. Current kinship/residence components remain.

Actual blockage: a single economic read mixed annual income, payment, legal givens
and service records, also asking the reader to identify queried records. It copied
the SERVICE year into PAYMENT year while marking payment time unstated; its
converter discarded the entire payment. A source-grounded diagnostic that kept
only actual payment roles/amount/purpose still exposed means_(payment), plan_(payee)
and end_(service) as unread. Fix the actual requirements, not merely payment_.
This is not output truncation. Do not infer payment dates from work dates, wages
as cash, domestic service as a private home, or work as a kinship period.

The supplied relational_observation_contract.py is the complete contract API:
key_domain, enumerator, constants, relations[{name,key,fields,prompt}],
covered_families, covered_properties, rules. Fields are scalar string/integer/
number/boolean with name,type,copy,nullable,normalizer(null/literal_date),enum?.
Shared keys identify the SAME source event across relations. Rules are finite
positive conjunctive views; head predicates must be public native FACT inputs.
No legal rule, source ID, remembered entity/year or answer constant is allowed.
Each relation read returns complete/unread, records and exact facts witnesses.
Complete empty/null must mean the relevant facts were actually checked. Ambiguous
or insufficient temporal granularity is unread, never a fabricated exact date or
a false closure. Only genuinely stated dates receive literal_date normalization.

Method: base_components has the two contracts, each with ONE genuinely coupled
relation. partitions_json maps each ID to [{name,fields:[non-key names],prompt}]
partitioning its actual non-key fields once. Host split preserves transduction
semantics and keys, removes irrelevant existential dependencies, and selects
coupled vs refined by real whole-case execution. Do not invent fields to sabotage
the coupled view. alternate_components is empty.

FreeTeacher: base_components and alternate_components each contain the two
independently strongest contracts. You may directly decompose, use the identical
architecture and learn the same constraints. partitions_json is {}. Do not keep
a weak coupled interface to create an artificial method gain. You receive the
same two real candidate evaluations and full feedback, code and lawful sources.
observation_programs_json is {} in this phase; existing observers remain assets.

Both arms may learn read_constraint_program, a pure apply(inputs,premises)
program with the documented status/domains/witnesses result. It may inspect facts,
record_fields, requested_relation and actual_prior_source_records. The prior map
additionally has observed_related_source_events: other already trusted component
facts with their actual event IDs. A payment purpose may reference an observed
service event ONLY by matching its actual source roles/kind; retain ambiguity.
Source-generated keys are nominal, not copied facts. Do not invent target IDs or
query-dependent facts. No native query is supplied to the weak reader. Shared
code handles unique public service/payment nominal ABI binding after reading.

Keep payment existence/roles, payment means/purpose, payment time and service
roles/period/venue separable where justified by the actual error and dependencies.
Optional null fields can close a checked non-temporal property only when source
scan supports absence; remaining relations stay unread. Include each actually
needed alternate native factual port (for example type_ versus purpose_) in
coverage; never use an unread alternative as known false. plan_ concerns the
actual public event ontology, not an invented financial fact. Read the supplied
native program before choosing its fields. Source checks and whole-case accuracy
select candidates; field-level formatting is not a method success.
'''


def read(path):
    return json.loads(path.read_text())


def prepare():
    public, kernels = runtime.previous.data()
    old = read(latest.OUT / 'protocol.json')
    acquisition = [next(s for s in public if ':' + prefix in s) for prefix in ('bb6b0bc1', '3e22604a')]
    reuse = [next(s for s in public if ':' + prefix in s) for prefix in ('d5e1138c', '6939feda')]
    assert all(public[s]['split'] == 'train' for s in acquisition + reuse)
    assert not set(acquisition) & set(reuse)
    base = read(BASE)
    immutable_json(OUT / 'common_library.json', base)
    actual = read(ROOT / 'reports/legal_skill_evolution_run_20261111/component_training_20261115/M2_responsibility_review/actual_failure_evidence.json')
    probe = read(ROOT / 'reports/legal_skill_evolution_run_20261111/component_training_20261115/M2_responsibility_review/payment_core_localization_probe.json')
    grading = {}
    files = sorted(runtime.previous.train.OUT.glob('B*/teacher_task.json'))
    files.append(ROOT / 'artifacts/legal_skill_evolution_mixed_component_training_source_review_20261115/B1/teacher_task.json')
    for file in files:
        for case in read(file)['acquisition_cases']:
            if case['source'] in acquisition + reuse:
                value = case['original_TRAIN_supervision']
                if case['source'] in grading:
                    assert grading[case['source']] == value
                grading[case['source']] = value
    assert set(grading) == set(acquisition + reuse)
    immutable_json(OUT / 'TRAIN_grading.json', grading)
    task = {'common_current_library': base, 'target_component_ids': TARGETS,
        'actual_failure': actual, 'diagnostic_not_a_method_output': probe,
        'acquisition_sources': [{'source': s, 'public': public[s]['views'][0]['public'],
            'native_factual_vocabulary': kernels[s]['fact_arities'],
            'original_TRAIN_supervision': grading[s]} for s in acquisition],
        'author_native_programs': {name: (ROOT / kernels[acquisition[0]]['statute_directory'] / name).read_text()
            for name in ('section3306.pl', 'utils.pl', 'events.pl')},
        'contract_API': (ROOT / 'legal_skill_guard/skill_evolution/relational_observation_contract.py').read_text(),
        'existing_full_B8_exposure_disclosed_not_new_blind_data': True}
    immutable_json(OUT / 'teacher_task.json', task)
    imported = []
    for folder in (latest.OUT, runtime.OUT, runtime.previous.OUT,
                   ROOT / 'artifacts/legal_skill_evolution_residual_reader_recovery_20261115'):
        for channel in ('component_reads', 'relation_reads'):
            for path in (folder / channel).glob('*.json'):
                value = read(path)
                if value.get('source') not in acquisition + reuse or value.get('error') or not value.get('receipt'):
                    continue
                if channel == 'relation_reads' and 'raw_content' not in value:
                    continue
                target = OUT / channel / path.name
                if not target.exists():
                    immutable_json(target, value)
                    imported.append(str(path.relative_to(ROOT)))
    immutable_json(OUT / 'paid_cache_origins.json', imported)
    p = {k: deepcopy(old[k]) for k in ('sources', 'teacher_profile', 'executor_profile', 'shared_native_event_encoding')}
    p.update(run_id=RUN, acquisition_sources=acquisition, fixed_reuse_sources=reuse,
        original_TRAIN_only=True, no_full_training_DEV_TEST=True, goal_complete=False,
        compile_finite_copy_obligations=True, stop_without_supported_demand=True,
        include_observed_event_context=True,
        selection='whole native-case correctness, then source errors, real time and fixed candidate ID',
        common_start_not_independent_cold_start_acquisition=True,
        original_sources_and_model_configuration_unchanged=True)
    bound = [Path(__file__), Path(runtime.__file__), OUT / 'common_library.json',
             OUT / 'teacher_task.json', OUT / 'TRAIN_grading.json']
    bound += sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))
    p['source_sha256'] = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in bound}
    assert not strict_output_schema_issues(SCHEMA)
    immutable_json(OUT / 'protocol.json', p)
    for f in bound:
        target = OUT / 'source_snapshot' / f.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f.read_bytes())
    print(json.dumps({'acquisition': acquisition, 'fixed_reuse': reuse,
        'packed_task_characters': len(json.dumps(pack_programs(task), ensure_ascii=False)),
        'new_model_calls': 0}), flush=True)


def protocol():
    p = read(OUT / 'protocol.json')
    for path, sha in p['source_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path
    return p


def ledger(p):
    return EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p), teacher_concurrency=2)


def acquire():
    p = protocol()
    def one(arm):
        target = OUT / arm / 'teacher.json'
        if target.exists():
            return
        result = FrozenTeacher(ledger(p), OUT, p['teacher_profile']).propose(RUN + ':' + arm + ':contracts',
            source_ids=p['acquisition_sources'], system_prompt=SYSTEM + '\nYour arm: ' + arm + '\n' + INSTRUCTION + '\n' + PROGRAM_INSTRUCTION,
            user_prompt=json.dumps(pack_programs(read(OUT / 'teacher_task.json')), ensure_ascii=False, separators=(',', ':')),
            output_schema=SCHEMA)
        immutable_json(target, result)
        print(json.dumps({'teacher_saved': arm}), flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(one, arm) for arm in ('Method', 'FreeTeacher')]
        for job in jobs:
            job.result()


def candidates(p, program_transform=None):
    _, kernels = runtime.previous.data()
    result = {}
    for arm in ('Method', 'FreeTeacher'):
        proposal = read(OUT / arm / 'teacher.json')['value']
        first = proposal['base_components']
        if arm == 'Method':
            plans = json.loads(proposal['partitions_json'])
            second = []
            for item in first:
                contract = json.loads(item['contract_json'])
                assert len(contract['relations']) == 1
                refined = split(contract, contract['relations'][0]['name'], plans[item['id']])
                second.append({'id': item['id'], 'contract_json': json.dumps(refined)})
        else:
            second = proposal['alternate_components']
        for index, items in enumerate((first, second)):
            assert len(items) == 2 and {i['id'] for i in items} == set(TARGETS)
            library = read(OUT / 'common_library.json')
            for item in items:
                contract = json.loads(item['contract_json'])
                validate(contract, kernels[p['acquisition_sources'][0]])
                if contract.get('read_constraint_program'):
                    if program_transform is not None:
                        contract['read_constraint_program'] = program_transform(contract['read_constraint_program'])
                    validate_adapter(contract['read_constraint_program'], excluded_source_ids=p['sources'])
                group_schema = schema(contract)
                group_schema['required'] = []
                component = {'id': item['id'], 'meaning': 'Learned current-source payment/service relations',
                    'prompt': 'Read the acquired factual relation.', 'facts_only': True,
                    'complete_native_families': [], 'relation_contract': contract,
                    'schema_json': json.dumps(record_schema({'views': {'type': 'array', 'minItems': 1, 'items': group_schema}}))}
                library['components'] = [c for c in library['components'] if c['id'] != item['id']]
                library['components'].append(component)
            result[arm + '/' + str(index)] = library
    return result


def validate_proposals():
    libraries = candidates(protocol())
    for name, library in libraries.items():
        immutable_json(OUT / 'candidate_libraries' / (name + '.json'), library)
    immutable_json(OUT / 'offline_proposal_validation.json', {'candidates': sorted(libraries),
        'new_model_calls': 0, 'not_a_semantic_or_whole_case_success': True})
    print(json.dumps({'validated_candidates': sorted(libraries)}), flush=True)


def execute():
    p = protocol()
    public, kernels = runtime.previous.data()
    libraries = candidates(p)
    client = FrozenExecutor(ledger(p), OUT, p['executor_profile'])
    assert (OUT / 'offline_proposal_validation.json').exists()
    acquired, selected = [], {}
    for name, library in libraries.items():
        rows = [runtime.run_case(client, p, name, library, sid,
            public[sid]['views'][0]['public'], kernels[sid]) for sid in p['acquisition_sources']]
        acquired.append({'candidate': name, 'rows': rows})
    for arm in ('Method', 'FreeTeacher'):
        best = min((r for r in acquired if r['candidate'].startswith(arm + '/')),
            key=lambda r: (-sum(v['core_correct'] for v in r['rows']),
                sum(v['source_failures'] for v in r['rows']),
                sum(x.get('elapsed_seconds') or 0 for v in r['rows'] for x in v['reads']), r['candidate']))
        selected[arm] = best['candidate']
    immutable_json(OUT / 'selected_before_reuse.json', {'selected': selected, 'acquisition_only': True})
    reuse = [runtime.run_case(client, p, name, libraries[name], sid,
        public[sid]['views'][0]['public'], kernels[sid])
        for name in selected.values() for sid in p['fixed_reuse_sources']]
    ordinary = [runtime.run_case(client, p, selected['Method'], libraries[selected['Method']], sid,
        public[sid]['views'][0]['public'], kernels[sid], policy='ordinary') for sid in p['fixed_reuse_sources']]
    immutable_json(OUT / 'result.json', {'acquisition': acquired, 'selected': selected,
        'fixed_reuse': reuse, 'same_contract_ordinary_reuse': ordinary,
        'goal_complete': False, 'DEV_TEST_loaded': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'acquire', 'validate', 'execute'))
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'prepare': prepare, 'acquire': acquire, 'validate': validate_proposals, 'execute': execute}[args.phase]()
