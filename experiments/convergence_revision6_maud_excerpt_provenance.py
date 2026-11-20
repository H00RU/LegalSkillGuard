"""Replay MAUD marker aliasing and audit the exact source of fixed DEV errors."""

import json
import re
import sqlite3
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from experiments import convergence_revision6_maud_operative_attribution as prior
from experiments import convergence_revision6_maud_section_reference as release
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_maud_sibling_cue import ARCHIVE, unpage
from legal_skill_guard.paired_interfaces import maud_covenant_anchors as anchors
from legal_skill_guard.paired_interfaces import maud_excerpt_provenance as provenance
from legal_skill_guard.paired_interfaces import maud_parallel_excerpt as parallel
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_maud_excerpt_provenance'
POINTER = HANDOFF / f'{STAGE}_current.json'
fit, measured = prior.fit, prior.measured
archived = prior.controls.branch.archive.bound_result
EXCEPTION = re.compile(
    r'\bsection\s+\d+\.\d+\s+COVID-19 Exception\.\s+'
    r'Notwithstanding anything to the contrary contained herein \(including in Section '
    r'(?P<target>\d+\.\d+)\), nothing herein shall prevent the Company or any of its subsidiaries '
    r'from taking or failing to take any COVID-19 Measures\b', re.I,
)


def excerpts(source):
    texts = {view['id']: view['public']['source_text'] for view in source['views']}
    return tuple(unpage(texts[name]) for name in release.TASKS.values())


def cue_aliases(source, position):
    case = fit.group(source, position)
    if case is None:
        return {}
    public = case['public']
    texts = public['original_excerpts']
    inventory = anchors.inventory(texts)
    if {row['candidate_family'] for row in inventory.values()} != set(fit.TASKS):
        return {}
    return {name: provenance.repeated_occurrences(texts, records) for name, records in
            (('markers', public['focus_markers']), ('anchors', inventory))}


def public_proofs(texts):
    ordinary, negative = texts
    import_proof = parallel.attachment(negative, ordinary)
    return {'parallel_law_preambles': provenance.parallel_company_exceptions(*texts),
            'excluded_preamble_import': import_proof if import_proof is not None and
            import_proof['scope'] == 'excluded_by_explicit_clause_list' else None}


def parent_witness(contracts, source, texts):
    name = 'data/contracts/' + source['parent_id'] + '.txt'
    raw = contracts.read(name)
    full = unpage(raw.decode('utf-8-sig'))
    located = [provenance.locate_excerpt(text, full) for text in texts]
    # A uniquely located sibling can disambiguate a short fragment at the
    # start of the negative view. It contributes only its visible text.
    if located[1] is None and len(located[0] or ()) == 1:
        left, right = located[0][0]
        sibling = provenance.locate_excerpt(texts[1], full[left:right])
        if sibling:
            located[1] = [(left + start, left + end) for start, end in sibling]
    heading = release.section.HEADER.match(texts[0])
    external = [
        hit.span() for hit in EXCEPTION.finditer(full)
        if heading and hit['target'] == heading['number'] and all(
            fragments and not provenance.visible(hit.span(), fragments) for fragments in located
        )
    ]
    return {'parent_sha256': sha256(raw).hexdigest(), 'visible_parent_spans': located,
            'visible_pandemic_counts': [len(list(parallel.PANDEMIC.finditer(text))) for text in texts],
            'first_parent_pandemic_span': hit.span() if (hit := parallel.PANDEMIC.search(full)) else None,
            'parent_only_section_override': external}


def count_correct(results, labels):
    return sum(labels[key][fit.TASKS[role]]['answer'] == answer['answer']
               for key, rows in results.items() for role, answer in rows.items())


def compare_aliased_reads(db):
    out, binding, terminal = archived(measured)
    executor, cases, _, grade, _ = measured.anchored.materials()
    wire = read(out / 'wire_tasks.json')
    path = out / 'sealed_predictions.json'
    bank = read(path)
    proof = read(out / 'same_scope_proofs.json')
    if (sha(path) != terminal['predictions_sha256'] or sha(grade) != binding['reference_sha256']
            or 'train' not in grade.parts or
            digest([proof['known'], proof['witness']]) != binding['source_evidence_sha256']):
        raise ValueError('Use the exact settled TRAIN reads and their shared evidence')
    calls, _ = prior.restored(cases, binding, executor, out, bank['raw'], wire)
    revised, changes = {}, []
    for key, call in zip(cases, calls, strict=True):
        case = cases[key]
        public = case['public']
        pairs = provenance.repeated_occurrences(public['original_excerpts'], public['focus_markers'])
        encoded, = db.execute('select result from calls where id=?', (call,)).fetchone()
        payload = json.loads(json.loads(encoded)['content'])
        local = {name: measured.edges.project(public['candidate_clause_anchors'], row['first'], row['second'])
                 for name, row in payload['observations'].items()}
        folded = provenance.fold_repeated_relations(local, pairs)
        revised[key] = fit.consume({
            name: {**dict(zip(fit.FAMILIES.values(), values, strict=True)), fit.TRIGGER_NAME: True}
            for name, values in folded.items()
        }, payload['checked_coverage'])
        for left, right in pairs:
            changes.append({'position': case['position'], 'markers': [left, right],
                            'decoded': [local[left], local[right]], 'folded': folded[left]})
    shared = measured.visible.common_scope({'folded': revised}, proof['known'])
    shared = measured.visible.revise(shared, proof['witness'])['folded']
    attribution, rules, endpoint = archived(prior)
    proofs = read(attribution / 'source_proofs.json')
    latest_path = attribution / 'sealed_predictions.json'
    if (rules['operative_edges_terminal'] != terminal['terminal_sha256'] or
            digest(proofs) != rules['proofs_sha256'] or sha(latest_path) != endpoint['predictions_sha256']):
        raise ValueError('Preserve the most recent matched scope attribution')
    latest = read(latest_path)
    corrections = {key: found['answer'] if (found := proofs['TRAIN'][key]) else {} for key in cases}
    check = measured.visible.common_scope(bank['comparable'], corrections)
    if check != latest:
        raise ValueError('The shared preamble replay must reproduce the prior attribution')
    shared = measured.visible.common_scope({'folded': shared}, corrections)['folded']
    bank['comparable'] = latest
    labels = read(grade)
    return {
        'archived_operative_terminal': terminal['terminal_sha256'],
        'verified_reads': len(calls),
        'comparisons': {
            scope: {name: count_correct(results, labels)
                    for name, results in {**bank[scope], 'folded_composed': folded}.items()}
            for scope, folded in (('raw', revised), ('comparable', shared))
        },
        'decoded_aliases': changes,
        'changed_composed_rows_after_shared_proofs': sum(
            shared[key] != bank['comparable']['synthesized'][key] for key in cases
        ),
    }


def run():
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        if ledger.get('reserved') or read(HANDOFF / 'run_state.json')['active_tasks']:
            raise ValueError('Require a settled checkpoint')
        _, _, roster = fit.previous.archive_context()
        _, cohort, original, study, _ = release.base_actor()
        dev = {s['key']: s for s in cohort if s['dataset'] == release.MAUD and s['project_split'] == 'dev'}
        train = [([batch, i], s) for batch, rows in enumerate(roster, 1)
                 for i, s in enumerate(r for r in rows if r['dataset'] == release.MAUD)]
        if (len(train), len(dev)) != (24, 16) or any(s['project_split'] != 'train' for _, s in train):
            raise ValueError('Preserve all original TRAIN and fixed DEV MAUD mothers')
        coverage = {}
        proofs = {}
        for split, sources in (('TRAIN', train), ('DEV', list(enumerate(dev.values(), 1)))):
            coverage[split] = [{'position': pos, 'marker_aliases': p['markers'], 'anchor_aliases': p['anchors']}
                               for pos, s in sources if (p := cue_aliases(s, pos)) and any(p.values())]
            proofs[split] = [(pos, s['key'], public_proofs(excerpts(s))) for pos, s in sources]
        folded = compare_aliased_reads(db)
        dev_reads = release.parallel.verify_original_inputs(db, original, dev, dev)
        if dict(db.execute('select status,count(*) from calls group by status')) != ledger:
            raise ValueError('Keep the continuous ledger')

    root, binding, terminal = archived(release)
    grade = study['grading_paths'][release.MAUD]
    prediction_path = root / 'sealed_predictions.json'
    if (sha(prediction_path) != terminal['predictions_sha256'] or
            sha(ROOT / grade) != binding['DEV_grade_sha256'] or 'dev' not in Path(grade).parts):
        raise ValueError('Use the exact sealed fixed DEV predictions and references')
    predictions = read(prediction_path)
    if set(predictions) != set(original) or any(set(bank) != set(dev) for bank in predictions.values()):
        raise ValueError('Preserve all five matched arms')
    reference = read(ROOT / grade)
    archive_receipt = BASE / 'postfreeze_M2_MAUD_source_scope_20261119' / 'terminal.json'
    archive_hash = read(archive_receipt)['parent_reference_audit']['official_archive_sha256']
    if sha(ARCHIVE) != archive_hash:
        raise ValueError('Preserve the originally audited full-contract release')

    misses = []
    with ZipFile(ARCHIVE) as contracts:
        for position, key, proof in proofs['DEV']:
            by_family = {family: {'reference': reference[key][task]['answer'],
                                  'predicted': {arm: rows[key]['after'][task] for arm, rows in predictions.items()}}
                         for family, task in release.TASKS.items()}
            residuals = {family: row for family, row in by_family.items()
                         if any(value != row['reference'] for value in row['predicted'].values())}
            if residuals:
                misses.append({'position': position, 'tasks': residuals, 'public_proofs': proof,
                               **parent_witness(contracts, dev[key], excerpts(dev[key]))})
    scope = {split: [{'position': pos, **proof} for pos, _, proof in rows if any(proof.values())]
             for split, rows in proofs.items()}
    package = {
        'stage': STAGE, 'TEST_opened': False, 'new_executor_requests': 0, 'new_teacher_requests': 0,
        'ledger': ledger, 'formal_fixed_DEV_verified_requests': dev_reads,
        'roster_mothers': {'TRAIN': len(train), 'DEV': len(dev)},
        'quoted_context_repeat_coverage': coverage, 'shared_source_proof_hits': scope,
        'TRAIN_archived_relation_alias_replay': folded, 'fixed_DEV_residuals': misses,
        'fixed_DEV_score': terminal['score'],
        'design': 'Diagnostic replay. Parent coordinates audit source visibility and never enter a model input. '
                  'Native references and predictions are the archived original grades and shared repairs.',
    }
    names = (__file__, provenance.__file__, parallel.__file__, prior.__file__, release.__file__)
    spec = {
        'stage': STAGE, 'original_DEV_release': terminal['terminal_sha256'],
        'official_archive_sha256': archive_hash, 'archive_authority_sha256': sha(archive_receipt),
        'result_sha256': digest(package), 'TEST_opened': False,
        'source_sha256': {str(Path(path).relative_to(ROOT)): sha(Path(path)) for path in names},
    }
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    fit.snapshot(out, spec['source_sha256'])
    result = sealed({**package, 'binding_sha256': out.name}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': f'settled_{STAGE}', 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
