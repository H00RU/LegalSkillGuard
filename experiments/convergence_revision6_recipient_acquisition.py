"""Select a B5 disclosure reader with source-bound internal and external roles."""

from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
from statistics import mean

from experiments import convergence_revision6_contract_employee_witnesses as employees
from experiments import convergence_revision6_retention_group_transfer as replay
from experiments.convergence_formal_train_fit import pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_scoped_update import verify_public_wire
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.paired_interfaces.shared_semantics import (
    SourceCase, Theory, allowed_relation, matches_assertions,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_recipient_acquisition'
POINTER = HANDOFF / 'revision6_recipient_acquisition_current.json'
RETENTION = replay.selection.retention
CNI, EXTERNAL = replay.CNI, replay.EXTERNAL
TASKS = ('nda-5', 'nda-7')
ENTERING, PROPOSAL = 'incumbent', 'proposal'
YES, ABSENT = 'Entailment', 'NotMentioned'
NAMED_SHARING = re.compile(
    r"\bmay divulge nonpublic information\b[^.;]+?\bto (?P<receiver>the [\w ]{2,75}?)"
    r" and such information may be shared among (?P=receiver)[’']s employees and agents\b", re.I
)
FURNISHING = re.compile(r'\bin consideration of your furnishing us with the information, we agree that\b', re.I)
NEED_TO_KNOW = re.compile(
    r'\bwe agree to reveal the information only to our agents, representatives and employees who need to know\b', re.I
)
INBOUND_EMPLOYEES = re.compile(
    r'\binformation disclosed by the Company to Recipient, including without limitation '
    r'information acquired by Recipient from Company employees\b', re.I
)
INBOUND_OUTSIDER = re.compile(r'^.{0,9}is lawfully obtained by Recipient from a third party\b', re.I)
OUTGOING_BY_CONSENT = re.compile(r'\bthe Company agrees in writing may be disclosed by Recipient\b', re.I)
ROLE = re.compile(r'\b(?:employe\w*|agents?|consultants?|advi[cs]ers?|representatives?|third part(?:y|ies))\b', re.I)


def complete_group(view):
    """Recognize paired permissions and a narrow complete inbound-only form."""
    spans = [' '.join(s.split()) for s in employees.links.linked.span_inventory(view)]
    matches = []
    for i, text in enumerate(spans):
        if NAMED_SHARING.search(text):
            matches.append(('named_receiving_group', YES, [i]))
        if NEED_TO_KNOW.search(text):
            leads = [j for j in range(max(0, i - 3), i) if FURNISHING.search(spans[j])]
            if len(leads) == 1:
                matches.append(('receiving_party_undertaking', YES, [*leads, i]))
    if len(matches) == 1:
        kind, answer, citations = matches[0]
        return kind, {task: {'answer': answer, 'evidence_sentence_ids': citations} for task in TASKS}
    if matches:
        return None
    role_spans = [text for text in spans if ROLE.search(text)]
    if len(role_spans) != 2 or not INBOUND_EMPLOYEES.search(role_spans[0]) \
            or not INBOUND_OUTSIDER.search(role_spans[1]):
        return None
    # The only stated outgoing disclosure permission documents a generally
    # approved declassification. It specifies neither recipient class.
    permissions = [text for text in spans if re.search(r'\bmay be disclosed\b', text, re.I)]
    if len(permissions) == 1 and OUTGOING_BY_CONSENT.search(permissions[0]) \
            and not re.search(r'\brepresentatives?|intermediaries|officers|directors|staff\b',
                              view['public']['source_text'], re.I):
        return 'inbound_recipient_mentions_only', {
            task: {'answer': ABSENT, 'evidence_sentence_ids': []} for task in TASKS}
    return None


def relation_output(primitives, _law):
    return primitives['source_answer']


def screen(key, view, proof, alternatives):
    scope = digest([view['public'], proof])
    theory = Theory(
        {scope: [{}]}, {key: [{}]}, relation_output, sha(Path(__file__)),
        provenance=({'kind': 'independent_source_audit', 'evidence_sha256': scope},),
    )
    facts = [proof[t]['answer'] for t in TASKS]
    cases = [SourceCase(key + ':' + task, key, scope, view['public'], {'source_answer': answer})
             for task, answer in zip(TASKS, facts, strict=True)]
    checks = [allowed_relation(theory, cases, mode=mode) for mode in ('shared', 'independent_completions')]
    decisions = {}
    for role, answers in alternatives.items():
        # A read with no opinion cannot establish positive update evidence.
        direct = all(answer is not None and answer == expected
                     for answer, expected in zip(answers, facts, strict=True))
        for relation in checks:
            matched = all(a is not None for a in answers) and any(
                matches_assertions(answers, signature) for signature in relation['signatures'].values())
            if matched != direct:
                raise ValueError('Both exact source controls must see the same recipient-role evidence')
        decisions[role] = direct
    return decisions


def pick(pool):
    # Both selectors have the full same archive for ranking and screen one
    # mother, using two observed responses. Source proof is computed before
    # reading either native answer or grading.
    def risk(row):
        before, after = (row['responses'][role] for role in (ENTERING, PROPOSAL))
        return sum(witness['answer'] == YES and a == YES and b != YES
                   for witness, a, b in zip(row['proof'].values(), before, after, strict=True))

    def disagreement(row):
        before, after = (row['responses'][role] for role in (ENTERING, PROPOSAL))
        return replay.selection.rank(before, after)

    return {
        'chronological': max(pool, key=lambda row: row['position']),
        'answer_disagreement': max(pool, key=lambda row: (disagreement(row), row['position'])),
        'candidate_driven': max(pool, key=lambda row: (risk(row), disagreement(row), row['position'])),
    }


def train_response(db, source, output, proposal, program):
    identity = RETENTION.verify_prediction(db, source['key'], output)
    verify_public_wire(db, source, identity)
    if proposal is None:
        entry, = output['reads']
        if entry['execution']['program_sha256'] != digest(program) or entry['native'] != output['native']:
            raise ValueError('Bind the entering native consumer and its exact read')
    else:
        trace, = output['schema_reads']
        if trace['proposal_sha256'] != digest(proposal) or trace['native'] != output['native']:
            raise ValueError('Bind the original candidate schema and its exact read')
    raw, = db.execute('select result from calls where id=?', (identity,)).fetchone()
    request = read(Path(json.loads(raw)['artifact_directory']) / 'request.json')['payload']
    envelope = {k:v for k,v in request.items() if k not in ('messages', 'response_format')}
    return identity, [output['native'][t]['answer'] for t in TASKS], envelope


def training(db):
    batch = 5
    folder, spec, terminal = replay.bound.bound_stage(pointer(batch))
    stage_data = read(folder / 'matched_decisions.json')
    if terminal['batch'] != batch or digest(stage_data) != terminal['matched_decisions_sha256']:
        raise ValueError('Keep the actual B5 proposal and original TRAIN comparison')
    checkpoint = ROOT / spec['checkpoint_root']
    study = read(checkpoint / 'binding.json')
    roster = RETENTION.load_roster(study)
    journal = replay.TrainingJournal(checkpoint, study, roster)
    training_arms = {ENTERING: journal.library(EXTERNAL, batch-1),
                     PROPOSAL: journal.library(EXTERNAL, batch)}
    readers = {role: lib.get('schema_proposals', {}).get(CNI) for role, lib in training_arms.items()}
    program = training_arms[ENTERING]['programs'][CNI]
    if program != training_arms[PROPOSAL]['programs'][CNI]:
        raise ValueError('Hold the native consumer fixed')
    records = folder / 'candidates' / EXTERNAL / CNI
    measured = read(records / 'measurements.json')
    prior = read(records / 'prior_TRAIN_regression.json')
    recorded = stage_data['teacher'][EXTERNAL][CNI]
    if (readers[PROPOSAL] != measured['candidate'] or recorded['selected'] != 'candidate'
            or recorded['predictions_sha256'] != digest(measured['predictions'])
            or recorded['earlier_TRAIN_regression']['evidence_sha256'] != digest(prior)):
        raise ValueError('Bind the original adopted schema reader and all original TRAIN reads')
    original_observation = journal._observations(EXTERNAL, batch)
    lab_spec = read(ROOT / spec['observations_root'] / 'binding.json')
    grade = ROOT / lab_spec['native_grade_paths'][CNI]
    if 'train' not in grade.parts or sha(grade) != lab_spec['native_grade_sha256'][lab_spec['native_grade_paths'][CNI]]:
        raise ValueError('TRAIN reference must match the original observation')
    pool = []
    verified = set()
    for bi, mothers in enumerate(roster[:batch], 1):
        for index, source in enumerate(s for s in mothers if s['dataset'] == CNI):
            key = source['key']
            view = next(v for v in source['views'] if v['id'] == TASKS[0])
            finding = complete_group(view)
            if finding is None:
                continue
            if source['project_split'] != 'train':
                raise ValueError('Only TRAIN source evidence can select a group')
            if bi == batch:
                file = journal.directory(EXTERNAL, batch) / 'predictions' / (digest(key) + '.json')
                entering = read(file)
                if digest(entering) != original_observation['predictions'][key]:
                    raise ValueError('The entering B5 read changed')
                a, b = entering['result'], measured['predictions'][key]
            else:
                a, b = prior['before'][key], prior['candidate'][key]
            responses, inputs, identities = {}, {}, set()
            for role, output in ((ENTERING, a), (PROPOSAL, b)):
                identity, responses[role], inputs[role] = train_response(db, source, output, readers[role], program)
                identities.add(identity)
            if len(identities) != 2 or inputs[ENTERING] != inputs[PROPOSAL]:
                raise ValueError('The role group requires distinct actual reads of the same public source')
            verified.update(identities)
            form, proof = finding
            pool.append({'position': [bi, index], 'key': key, 'view': view, 'form': form, 'proof': proof,
                         'responses': responses, 'physical_read_count': len(identities)})
    if len(pool) < 3 or len(verified) != 2 * len(pool):
        raise ValueError('Require multiple paired original TRAIN role groups')
    return pool, readers, program, sha(folder / 'terminal.json'), grade, len(verified)


def grades(sources, predictions, grade):
    labels = read(grade)
    measured = {}
    for arm, rows in predictions.items():
        scored = measured[arm] = []
        for key, source in sources.items():
            for view in (v for v in source['views'] if v['id'] in TASKS):
                task = view['id']
                row = rows[key][task]
                result = grade_view(CNI, view, labels[key][task], row['answer'], row['evidence_sentence_ids'])
                scored.append({'source': key, 'view': task, **result,
                               'correct_evidence_f1': result['grade'] * result['evidence_f1']})
    values = {arm: {'correct': sum(r['grade'] for r in rows), 'n': len(rows),
                    'evidence_f1': mean(r['evidence_f1'] for r in rows),
                    'correct_evidence_f1': mean(r['correct_evidence_f1'] for r in rows)}
              for arm, rows in measured.items()}
    effects = {arm: {metric: paired_source_effect(*[
        [{**r, 'grade': r[metric]} for r in measured[version]] for version in (arm, 'candidate_driven')])
        for metric in ('grade', 'evidence_f1', 'correct_evidence_f1')}
        for arm in measured if arm != 'candidate_driven'}
    return values, effects


def run():
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        pool, readers, program, fit_terminal, train_grade, physical = training(db)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved'):
        raise ValueError('Reconcile any running generation request before settling replay')
    choices = {}
    for policy, row in pick(pool).items():
        check = screen(row['key'], row['view'], row['proof'], row['responses'])
        choices[policy] = {
            'position': row['position'], 'form': row['form'], 'supports': check,
            'choice': PROPOSAL if check[PROPOSAL] else ENTERING, 'actual_comparisons': row['physical_read_count'],
        }
    spec = {
        'stage': 'revision6_recipient_acquisition', 'initial_evidence': fit_terminal,
        'TRAIN_pool': digest(pool), 'TRAIN_grade_sha256': sha(train_grade),
        'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in (
            __file__, employees.__file__, replay.__file__, RETENTION.__file__, verify_public_wire.__code__.co_filename,
        )}, 'TEST_opened': False,
    }
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    for file, expected in spec['source_sha256'].items():
        path = out / 'source_snapshot' / file
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open('xb') as stream:
                stream.write((ROOT / file).read_bytes())
        if sha(path) != expected:
            raise ValueError('Preserve the exact recipient-rule source')
    libraries = {}
    for name, record in choices.items():
        choice = record['choice']
        skill = sealed({'batch': 5, 'active_hypotheses': list(TASKS), 'decision': record,
                        'schema_proposal': readers[choice], 'program': program,
                        'binding_sha256': out.name}, 'snapshot_sha256')
        libraries[name] = skill['snapshot_sha256']
        immutable_json(out / 'TRAIN_batch_libraries' / f'{name}.json', skill)
    label = read(train_grade)
    facts_confirmed = sum(label[row['key']][task]['answer'] == expected['answer']
                          for row in pool for task, expected in row['proof'].items())
    if facts_confirmed != len(TASKS) * len(pool):
        raise ValueError('Report source-reference disagreement before scoring the fit')
    inherited = ROOT / read(replay.POINTER)['artifact_root']
    inherited_spec = read(inherited / 'binding.json')
    inherited_stop = verify(read(inherited / 'terminal.json'), 'terminal_sha256')
    if (digest(inherited_spec) != inherited.name or inherited_stop['TEST_opened']
            or inherited_stop['terminal_sha256'] != read(replay.POINTER)['terminal_sha256']
            or sha(inherited / 'sealed_predictions.json') != inherited_stop['predictions_sha256']):
        raise ValueError('Use the exact previously verified fixed DEV program pair')
    available_libraries = {p: {'schema_proposal': readers[actual], 'program': program}
                           for p, actual in zip(replay.POLICIES, (PROPOSAL, ENTERING), strict=True)}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        sources, bank, grade_ref, stage_terms, dev_reads, wire = replay.materials(db, available_libraries)
    grade_path, grade_sha = grade_ref
    if (grade_sha != inherited_spec['DEV_grade_sha256'] or wire != inherited_spec['matched_public_and_executor_sha256']
            or stage_terms != inherited_spec['original_DEV_terminals']):
        raise ValueError('The DEV request and split must retain their earlier exact binding')
    choices_to_arrays = dict(zip((PROPOSAL, ENTERING), replay.POLICIES, strict=True))
    raw = {}
    for name, decision in choices.items():
        raw[name] = {key: {task: pred[task] for task in TASKS}
                     for key, pred in bank[choices_to_arrays[decision['choice']]].items()}
    source_corrections = {}
    for key, source in sources.items():
        view = next(v for v in source['views'] if v['id'] == TASKS[0])
        proof = complete_group(view)
        one = employees.witness(view)
        source_corrections[key] = proof[1] if proof else ({TASKS[0]: one} if one else {})
    patched = {arm: {key: {task: source_corrections[key].get(task, value)
                          for task, value in row.items()} for key, row in native.items()}
               for arm, native in raw.items()}
    pred_sha = immutable_json(out / 'sealed_predictions.json', {'raw': raw, 'same_information': patched})
    path = ROOT / grade_path
    if 'dev' not in path.parts or sha(path) != grade_sha:
        raise ValueError('Seal outputs before loading the original DEV annotations')
    before, _ = grades(sources, raw, path)
    after, effects = grades(sources, patched, path)
    result = sealed({
        'status': 'settled_revision6_recipient_acquisition', 'binding_sha256': out.name,
        'TRAIN_fit': choices, 'TRAIN_group_forms': dict(Counter(row['form'] for row in pool)),
        'TRAIN_original_reads_verified': physical, 'TRAIN_exact_source_facts': facts_confirmed,
        'TRAIN_libraries': libraries, 'same_pool': True, 'actual_screening_budget': 2,
        'same_information_screening_matches': True, 'DEV_mothers': len(sources),
        'DEV_original_reads_verified': dev_reads, 'DEV_proof_coverage': sum(map(len, source_corrections.values())),
        'DEV_before_common_proof': before, 'DEV_with_common_proof': after, 'DEV_effects': effects,
        'DEV_archived_receipt': inherited_stop['terminal_sha256'], 'predictions_sha256': pred_sha,
        'ledger': ledger, 'TEST_opened': False, 'new_executor_requests': 0, 'new_teacher_requests': 0,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
