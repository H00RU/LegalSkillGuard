"""Prepare a shared, source-only native kernel and faithful TRAIN query views.

Only the four fixed original-TRAIN query directives are inspected. Their
expected polarity and original fact sections never enter an actor artifact.
The original prepared dataset, frozen results and continuous ledger stay intact.
"""
import hashlib
import json
from pathlib import Path
import re
import tarfile

from experiments import legal_skill_evolution_execution_reuse as rejected
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.sara_statute_kernel import fact_vocabulary, GIVENS


ROOT = rejected.ROOT
RUN = 'legal_skill_evolution_native_execution_reuse_20261114'
OUT = ROOT / 'artifacts' / RUN
TARGETS = rejected.TARGETS
old = rejected.old


def read(path):
    return json.loads(path.read_text())


def parse_query(text):
    # Restricted to the actual selected source queries: conjunctions of named
    # statutory predicates with JSON scalars or anonymous variable arguments.
    body = re.sub(r':-\s*halt\s*\.\s*$', '', text).strip()
    if not body.startswith(':-'):
        raise ValueError('Expected the original query directive')
    body = body[2:].strip()
    if body.startswith('\\+'):
        body = body[2:].strip()  # discard expected polarity, retain query only
    if not body.endswith('.'):
        raise ValueError('Unterminated source query')
    body = body[:-1].strip()
    result, position = [], 0
    while position < len(body):
        match = re.match(r'(s\d+[A-Za-z0-9_]*)\s*\(', body[position:])
        if not match:
            raise ValueError('Unsupported native query predicate')
        name = match.group(1)
        position += match.end()
        args = []
        while True:
            while body[position].isspace():
                position += 1
            if body[position] == '_':
                args.append({'variable': '_'})
                position += 1
            else:
                value, consumed = json.JSONDecoder().raw_decode(body[position:])
                if type(value) not in (str, int, float):
                    raise ValueError('Query arguments must be source scalars')
                args.append(value)
                position += consumed
            while body[position].isspace():
                position += 1
            if body[position] == ')':
                position += 1
                break
            if body[position] != ',':
                raise ValueError('Unsupported source query syntax')
            position += 1
        result.append({'predicate': name, 'arguments': args})
        while position < len(body) and body[position].isspace():
            position += 1
        if position < len(body):
            if body[position] != ',':
                raise ValueError('Only source query conjunctions are supported')
            position += 1
            while position < len(body) and body[position].isspace():
                position += 1
    return result


def prepare():
    parent = read(rejected.OUT / 'protocol.json')
    sources = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    selected = [sources[key] for key in parent['sources']]
    assert all(s['split'] == 'train' for s in selected)
    old_source = ROOT / 'artifacts/legal_skill_evolution_scoped_premise_repair_20261113/native_semantics_source_only'
    source_manifest = read(old_source / 'source_manifest.json')
    hashes = {}
    for entry in source_manifest['selected_files']:
        name = Path(entry['member']).name
        if name not in ('events.pl', 'utils.pl') and not re.fullmatch(r'section\d+\.pl', name):
            continue
        body = (old_source / name).read_bytes()
        assert hashlib.sha256(body).hexdigest() == entry['sha256']
        target = OUT / 'statutes' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == body
        else:
            target.write_bytes(body)
        hashes[name] = entry['sha256']
    vocabulary = {**fact_vocabulary((OUT / 'statutes/events.pl').read_text()), **GIVENS}
    fact = record_schema({'predicate': {'type': 'string', 'enum': sorted(vocabulary)},
                          'arguments': {'type': 'array', 'items': {'type': ['string', 'number']}}})
    negative = record_schema({'predicate': {'type': 'string', 'enum': sorted(GIVENS)},
                              'arguments': fact['properties']['arguments']})
    input_schema = record_schema({'facts': {'type': 'array', 'items': fact},
        'negative_givens': {'type': 'array', 'items': negative},
        'extraction_status': {'type': 'string', 'enum': ['complete', 'unread']}})
    fields = {'facts': {'type': 'array', 'description': 'Positive source-grounded primitive event facts or explicitly stated intermediate statutory givens; predicate plus typed scalar arguments. Not the target claim.'},
        'negative_givens': {'type': 'array', 'description': 'Explicitly stated negative section151 givens; not unstated facts and not a prediction of the target.'},
        'extraction_status': {'type': 'string', 'description': 'complete means this finite case was successfully read; unread preserves extraction uncertainty. Not real-world completeness.'}}
    annotations = read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    bank, views, receipts = [], [], []
    with tarfile.open('/tmp/lsg_sara_v2_native_archive_20261114.tar.gz') as archive:
        for source, (_, clause, name) in zip(selected, TARGETS):
            original_id = annotations[source['key']]['native']['original_id']
            body = archive.extractfile('sara_v2/cases/' + original_id + '.pl').read()
            query = parse_query(body.decode().split('% Test', 1)[1])
            from legal_skill_guard.skill_evolution.sara_statute_kernel import query_term
            display = ', '.join(query_term(call) for call in query)
            corrected = json.loads(json.dumps(source))
            original_question = corrected['views'][0]['public']['question']
            corrected['views'][0]['public']['question'] += '\nNative query constraints from this same original TRAIN task (truth value not supplied): ' + display + '.'
            views.append(corrected)
            bank.append({'name': name, 'query_clause': clause, 'scope': 'exact_original_native_query',
                'backend': 'sara_statute_program', 'native_query': query,
                'statute_directory': str((OUT / 'statutes').relative_to(ROOT)),
                'statute_sha256': hashes, 'fact_arities': vocabulary,
                'input_fields_json': json.dumps(fields), 'input_schema_json': json.dumps(input_schema),
                'program': 'Immutable author-provided Prolog statutes; source program is shared, not learned or edited by the factual adapter.'})
            receipts.append({'source': source['key'], 'original_case_sha256': hashlib.sha256(body).hexdigest(),
                'original_public_question': original_question, 'native_query_without_expected_polarity': query,
                'original_case_fact_section_copied': False, 'expected_answer_or_polarity_copied': False})
    immutable_json(OUT / 'kernel_bank.json', bank)
    immutable_json(OUT / 'corrected_TRAIN_views.json', views)
    immutable_json(OUT / 'query_restoration_receipts.json', receipts)
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'sources': parent['sources'], 'new_sources_or_synthetic_cases': 0,
        'original_prepared_data_and_results_unchanged': True,
        'TEST_DEV_members_read': False, 'selected_original_TRAIN_query_interfaces_inspected': 4,
        'source_kernel_common_to_all_controls_not_a_method_contribution': True,
        'rejected_generated_kernel_run': rejected.RUN,
        'new_common_kernel_teacher_requests': 0, 'no_new_model_requests_for_preparation': True,
        'teacher_profile': parent['teacher_profile'], 'executor_profile': parent['executor_profile'],
        'kernel_bank_sha256': digest(bank), 'corrected_views_sha256': digest(views),
        'statute_source_sha256': hashes}
    immutable_json(OUT / 'protocol.json', protocol)
    print(json.dumps({'native_kernels_prepared': len(bank), 'restored_original_TRAIN_queries': len(receipts),
                      'new_model_requests': 0}), flush=True)
    return protocol


if __name__ == '__main__':
    prepare()
