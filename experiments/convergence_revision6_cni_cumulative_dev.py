"""Execute the released ContractNLI development rules in one fixed-cohort actor."""

import sqlite3
from math import fsum, isclose
from pathlib import Path

from experiments import convergence_revision6_cni_b5_disagreement as definition
from experiments import convergence_revision6_cni_development_release as development
from experiments import convergence_revision6_cni_event_linkage as linkage
from experiments import convergence_revision6_cni_external_recipients as external
from experiments import convergence_revision6_cni_independent_receipt as receipt
from experiments import convergence_revision6_cni_notice_roles as notices
from experiments import convergence_revision6_cni_recipient_evidence as employee
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_cumulative_dev'
POINTER = HANDOFF / f'{STAGE}_current.json'
CNI = notices.CNI
RULES = (development, definition, employee, receipt, linkage, external, notices)


def projected(row):
    evidence = row['evidence_sentence_ids'] if 'evidence_sentence_ids' in row else row['evidence']
    return row['answer'], evidence


def apply_receipt(row, proof):
    answer, _ = projected(row)
    revised = receipt.proof.apply({'answer': answer, 'evidence': row['evidence_sentence_ids']}, proof)
    return {**row, 'answer': revised['answer'], 'evidence_sentence_ids': revised['evidence']}


def compile_rules(sources):
    _, receipt_proofs = receipt.inventory(sources)
    return {
        key: (
            development.proof(source),
            definition.definition_proof(source),
            employee.source_paths(source),
            receipt_proofs[key],
            linkage.proofs(source),
            external.proof(source),
            notices.missing_proofs(source),
        )
        for key, source in sources.items()
    }


class CumulativeContractActor:
    def __init__(self, parent, proofs, source_hashes):
        self.parent = parent
        self.proofs = proofs
        self.source_hashes = source_hashes

    def trace(self, source, original):
        key = source['key']
        if digest(source) != self.source_hashes[key]:
            raise ValueError('Keep the original fixed development source and sentence coordinates')
        dev, defining, recipient, third_party, linked, outside, compelled = self.proofs[key]
        native = original['native']
        baseline = native
        native = {**native, development.TASK: development.apply(native[development.TASK], dev)}
        yield baseline, native
        baseline, native = native, {**native, development.TASK: development.apply(native[development.TASK], defining)}
        yield baseline, native
        baseline, native = native, {**native, employee.TASK: employee.graph.complete(native[employee.TASK], recipient)}
        yield baseline, native
        baseline, native = native, {**native, receipt.TASK: apply_receipt(native[receipt.TASK], third_party)}
        yield baseline, native
        baseline = native
        changed = {
            linkage.TASKS[role]: {**native[linkage.TASKS[role]], 'answer': proof['answer'],
                                  'evidence_sentence_ids': proof['evidence']}
            for role, proof in linked.items() if role in linkage.TASKS
        }
        native = {**native, **changed}
        yield baseline, native
        baseline, native = native, {**native, external.TASK: external.external.apply(native[external.TASK], outside)}
        yield baseline, native
        baseline, native = native, notices.project_result({'native': native}, compelled)['native']
        yield baseline, native

    def __call__(self, source, library, purpose):
        base = self.parent(source, library, purpose)
        if (purpose != 'skill_dev' or library['batch'] != 8 or source['dataset'] != CNI
                or source['project_split'] != 'dev' or source['key'] not in self.proofs):
            return base
        for _, native in self.trace(source, base):
            pass
        return {**base, 'native': native}


def prepare():
    parent, cohort, original, study, predecessor = notices.cumulative.fixed.base_actor()
    sources = {source['key']: source for source in cohort if source['dataset'] == CNI
               and source['project_split'] == 'dev'}
    if (len(sources), len(original)) != (16, 5):
        raise ValueError('Keep every original fixed-development source and arm')
    actor = CumulativeContractActor(parent, compile_rules(sources), {k: digest(s) for k, s in sources.items()})
    return actor, sources, original, study, predecessor


def released_rows(documents, arm, key):
    dev, defining, recipient, third_party, linked, outside, compelled = documents

    def by_phase(doc, task):
        return {task: (doc['before'][key], doc['after'][key])}

    yield by_phase(dev['fixed_B8'][arm], development.TASK)
    yield {development.TASK: (dev['fixed_B8'][arm]['after'][key], defining['fixed'][arm][key])}
    yield by_phase(recipient['fixed_DEV'][arm], employee.TASK)
    yield by_phase(third_party['fixed_DEV'][arm], receipt.TASK)
    linked = linked['all']['dev'][arm]
    yield {task: (linked['before'][key][role], linked['after'][key][role]) for role, task in linkage.TASKS.items()}
    outside = outside['banks']['dev'][arm][key]
    yield {external.TASK: (outside['before'], outside['after'])}
    yield by_phase(compelled['DEV'][arm], notices.TASK)


def loaded_releases(aggregate, grade_sha):
    documents, terminals = [], {}
    for step in RULES:
        pointer = read(step.POINTER)
        folder = ROOT / pointer['artifact_root']
        lock = read(folder / 'binding.json')
        end = verify(read(folder / 'terminal.json'), 'terminal_sha256')
        path = folder / 'sealed_predictions.json'
        bound_grade = lock['grades_sha256']['DEV'] if step is notices else lock['DEV_grade_sha256']
        if (folder.name != digest(lock) or pointer['terminal_sha256'] != end['terminal_sha256']
                or end['terminal_sha256'] not in aggregate['additional_common_repair_terminals']
                or end['TEST_opened'] or bound_grade != grade_sha
                or sha(path) != end['predictions_sha256']):
            raise ValueError(f'Preserve sealed rule and original split for {step.POINTER.name}')
        if any(sha(folder / 'source_snapshot' / name) != tag or sha(ROOT / name) != tag
               for name, tag in lock['source_sha256'].items()):
            raise ValueError(f'Rule source differs from the released version for {step.POINTER.name}')
        terminals[step.POINTER.name] = end['terminal_sha256']
        documents.append(read(path))
    return documents, terminals


def measure(actor, sources, originals, documents):
    before_banks, after_banks, requests, counts = {}, {}, {}, [0] * len(RULES)
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        if ledger.get('reserved') or read(HANDOFF / 'run_state.json')['active_tasks']:
            raise ValueError('Compose released results after the experiment has settled')
        for arm, (directory, seal, cell) in originals.items():
            initial, cumulative = {}, {}
            for key, source in sources.items():
                row = read(directory / 'predictions' / f'{digest(key)}.json')
                if (digest(row) != seal['predictions_sha256'][key] or row['public_source_sha256'] != digest(source)
                        or row['library_sha256'] != cell['libraries'][CNI]):
                    raise ValueError('Preserve the exact original fixed DEV observation and B8 library')
                notices.archived.checked_result(db, source, row['result'], requests, dev=True)
                library = {'arm': arm, 'batch': 8}
                base = actor.parent(source, library, 'skill_dev')
                initial[key] = base['native']
                for i, ((before, after), expected) in enumerate(zip(
                    actor.trace(source, base), released_rows(documents, arm, key), strict=True,
                )):
                    touched = {task for task in before if projected(before[task]) != projected(after[task])}
                    if not touched <= set(expected) or any(
                        (projected(before[task]), projected(after[task])) != tuple(map(projected, pair))
                        for task, pair in expected.items()
                    ):
                        raise ValueError(f'Released projection differs for stage {RULES[i].POINTER.name}')
                    counts[i] += len(touched)
                cumulative[key] = after
            before_banks[arm], after_banks[arm] = initial, cumulative
    return before_banks, after_banks, counts, requests, ledger


def scores(bank, sources, grades):
    result = {}
    for arm, rows in bank.items():
        cells = [
            grade_view(CNI, view, grades[key][view['id']], *projected(rows[key][view['id']]))
            for key, source in sources.items() for view in source['views']
        ]
        result[arm] = {'units': len(cells), 'correct': int(fsum(row['grade'] for row in cells)),
                       'evidence_F1': fsum(row['evidence_f1'] for row in cells) / len(cells)}
    return result


def run():
    actor, sources, originals, study, predecessor = prepare()
    state = read(HANDOFF / 'run_state.json')
    latest = state['revision6_oe_pa_civilian_assets']
    aggregate_file = ROOT / latest['table']
    if sha(aggregate_file) != latest['table_sha256']:
        raise ValueError('Use the latest settled five-library aggregate')
    aggregate = read(aggregate_file)['cumulative_fixed_B8_DEV']
    name = study['grading_paths'][CNI]
    grade = ROOT / name
    grade_sha = study['grading_file_sha256'][name]
    if 'dev' not in grade.parts or sha(grade) != grade_sha:
        raise ValueError('Keep the original fixed DEV reference')
    expected, terminals = loaded_releases(aggregate, grade_sha)
    before, after, counts, requests, ledger = measure(actor, sources, originals, expected)
    files = (__file__, *(step.__file__ for step in RULES))
    spec = {
        'stage': STAGE, 'TEST_opened': False, 'prior_fixed_DEV_terminal': predecessor,
        'five_library_aggregate_sha256': latest['table_sha256'], 'fixed_DEV_grade_sha256': grade_sha,
        'released_terminals': terminals, 'ordered_shared_rules': list(terminals),
        'source_proofs_sha256': digest(actor.proofs), 'original_DEV_source_sha256': actor.source_hashes,
        'physical_reads_sha256': digest(sorted(requests)),
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in files},
    }
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    snapshot(out, spec['source_sha256'])
    immutable_json(out / 'source_proofs.json', actor.proofs)
    tag = immutable_json(out / 'sealed_predictions.json', {'base': before, 'cumulative': after})
    labels = read(grade)
    actual = scores(after, sources, labels)
    for arm, cell in actual.items():
        inherited = aggregate['by_arm'][arm]
        if (cell['units'] != 272 or
                not isclose(cell['correct'], inherited['native_utility'][CNI]['all'] * 272, abs_tol=1e-9) or
                not isclose(cell['evidence_F1'], inherited['ContractNLI_evidence_f1']['mean'], abs_tol=1e-12)):
            raise ValueError(f'Full fixed DEV execution differs from the released score for {arm}')
    result = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': tag,
        'fixed_DEV_before': scores(before, sources, labels), 'fixed_DEV_cumulative': actual,
        'rule_prediction_changes': dict(zip(terminals, counts, strict=True)),
        'fixed_DEV_mothers': len(sources), 'physical_automatic_responses_reused': len(requests),
        'TEST_opened': False, 'ledger': ledger, 'new_executor_requests': 0, 'new_teacher_requests': 0,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
