"""Add source-anchored knowledge effects to the cumulative fixed B8 DEV release."""

from pathlib import Path
import sqlite3

from experiments import convergence_revision5_maud_adoption_scope as adoption
from experiments import convergence_revision5_maud_knowledge_residual as previous
from experiments import convergence_revision6_maud_parallel_release as parallel
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import maud_knowledge_effect as local
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_maud_knowledge_release'
POINTER = HANDOFF / 'revision6_maud_knowledge_release_current.json'
TASK = previous.TASK
CONSTRUCTIVE = 'Constructive knowledge'
MAUD = previous.DATASET


def effect(source):
    text = previous.normalize(previous.view_for(source)['public']['source_text'])
    definitions = previous.definitions(text)
    if len(definitions) != 1:
        return None
    definition, = definitions
    proof = local.positive_effect(definition['text'])
    if proof is None:
        return None
    old = previous.independent_direct(previous.facts(definition))
    return {**proof, 'previous_source_answer': old, 'definition_sha256': digest(definition['text'])}


class KnowledgeEffectActor:
    def __init__(self, parent, cells, parallel_proofs, effects):
        self.parent = parallel.ParallelExcerptActor(parent, cells, parallel_proofs)
        self.effects = effects

    def __call__(self, source, library, purpose):
        baseline = self.parent(source, library, purpose)
        if source['dataset'] != MAUD or self.effects.get(source['key']) is None:
            return baseline
        current = baseline['native'][TASK]
        if current['answer'] == CONSTRUCTIVE:
            return baseline
        update = {**current, 'answer': CONSTRUCTIVE, 'handled': True}
        return {**baseline, 'native': {**baseline['native'], TASK: update}}


def training():
    _, _, roster = adoption.archive_context()
    sources = {s['key']:s for b in roster for s in b if s['dataset'] == MAUD and s['project_split'] == 'train'}
    old_binding, old, _, old_terminal = adoption.prior_knowledge('TRAIN')
    if len(sources) != 24 or digest(sources) != old_binding['source_sha256'] or sources.keys() != old.keys():
        raise ValueError('Keep the original source-audited TRAIN cohort')
    bank = {key: effect(source) for key,source in sources.items()}
    if not any(proof and proof['form'] == 'imputation_in_definition' for proof in bank.values()):
        raise ValueError('Use original evidence for the imputed knowledge effect')
    stage, spec, end = previous.bound_stage(previous.observe_pointer(7))
    if end['TEST_opened']:
        raise ValueError('Use original TRAIN source only')
    name = spec['native_grade_paths'][MAUD]
    return bank, old_terminal, name, spec['native_grade_sha256'][name], sha(stage / 'terminal.json')


def run():
    train, train_terminal, train_path, train_hash, observe_hash = training()
    prior, old_release, old_bound = parallel.release.stage(parallel.release.POINTER)
    last_entry = read(parallel.POINTER)
    last = ROOT / last_entry['artifact_root']
    parallel_spec = read(last / 'binding.json')
    previous_term = verify(read(last / 'terminal.json'), 'terminal_sha256')
    parallel_proofs = read(last / 'source_proofs.json')['dev']
    if (digest(parallel_spec) != last.name or previous_term['terminal_sha256'] != last_entry['terminal_sha256']
            or parallel_spec['original_terminal_sha256'] != old_release['terminal_sha256']
            or sha(last / 'sealed_predictions.json') != previous_term['predictions_sha256']
            or digest(parallel_proofs) != parallel_spec['proof_sha256'] or previous_term['TEST_opened']):
        raise ValueError('Use the exact previous cumulative development amendment')
    cohort, original, study, _ = parallel.release.formal.common.archive()
    if digest(cohort) != old_bound['DEV_public_sha256']:
        raise ValueError('Original DEV sources must be byte bound to the released evaluation')
    sources = {s['key']:s for s in cohort if s['dataset'] == MAUD and s['project_split'] == 'dev'}
    effects = {key: effect(s) for key,s in sources.items()}
    reached = [key for key,p in effects.items() if p and p['previous_source_answer'] != CONSTRUCTIVE]
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as db:
        count = parallel.verify_original_inputs(db, original, sources, reached)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or len(sources) != 16:
        raise ValueError('Require a settled ledger and the untouched fixed DEV roster')
    grading = study['grading_paths'][MAUD]
    cells = parallel.release.parent_cells(prior, old_release)
    spec = {
        'stage': 'revision6_maud_knowledge_release', 'parallel_release': previous_term['terminal_sha256'],
        'TRAIN_prior': train_terminal, 'TRAIN_observe': observe_hash, 'TRAIN_effects': digest(train),
        'DEV_effects': digest(effects), 'TRAIN_grade': train_hash,
        'DEV_grade': study['grading_file_sha256'][grading], 'TEST_opened': False,
        'source_sha256': {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in (
            __file__, local.__file__, parallel.__file__, previous.__file__,
        )},
    }
    outcome = HOME / digest(spec)
    immutable_json(outcome / 'binding.json', spec)
    for name, expected in spec['source_sha256'].items():
        snapshot = outcome / 'source_snapshot' / name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            with snapshot.open('xb') as handle:
                handle.write((ROOT / name).read_bytes())
        if sha(snapshot) != expected:
            raise ValueError('This cumulative actor must preserve its bound source rules')
    actor = KnowledgeEffectActor(prior, cells, parallel_proofs, effects)
    outputs = {}
    for arm in parallel.release.ARMS:
        library = {'arm': arm, 'batch': 8}
        outputs[arm] = {}
        for key, source in sources.items():
            original_rows = actor.parent(source, library, 'skill_dev')['native']
            revised = actor(source, library, 'skill_dev')['native']
            if {t:v for t,v in revised.items() if t != TASK} != {t:v for t,v in original_rows.items() if t != TASK}:
                raise ValueError('Keep the cumulative negative and ordinary covenant outputs')
            outputs[arm][key] = {'before':original_rows[TASK], 'after':revised[TASK]}
    prediction_sha = immutable_json(outcome / 'sealed_predictions.json', outputs)
    immutable_json(outcome / 'source_effects.json', {'TRAIN':train, 'DEV':effects})
    train_file, dev_file = ROOT / train_path, ROOT / grading
    if ('train' not in train_file.parts or sha(train_file) != train_hash
            or 'dev' not in dev_file.parts or sha(dev_file) != spec['DEV_grade']):
        raise ValueError('Use the original native graders only after sealing')
    train_annotations, dev_annotations = read(train_file), read(dev_file)
    recognized = [p for p in train.values() if p]
    if any(train_annotations[key][TASK]['answer'] != CONSTRUCTIVE for key, p in train.items() if p):
        raise ValueError('A source-proved constructive form conflicts with the original TRAIN reference')
    rows = {}
    for arm, values in outputs.items():
        scores = {'before': [], 'after': []}
        for key, row in values.items():
            for mode, prediction in row.items():
                cell = grade_view(MAUD, previous.view_for(sources[key]), dev_annotations[key][TASK],
                                  prediction['answer'])
                scores[mode].append({'source':key, 'view':TASK, 'grade':cell['grade']})
        rows[arm] = {'before_correct':sum(r['grade'] for r in scores['before']),
                     'after_correct':sum(r['grade'] for r in scores['after']),
                     'predictions_changed':sum(r['before'] != r['after'] for r in values.values()),
                     'paired_effect':paired_source_effect(scores['before'], scores['after'])}
    result = sealed({
        'status': 'settled_revision6_maud_knowledge_release', 'binding_sha256': outcome.name,
        'TRAIN_support': {'mothers':len(train), 'positive_standards':len(recognized),
                          'exact_imputation_forms':sum(p['form'] == 'imputation_in_definition' for p in recognized)},
        'DEV_newly_resolved_forms': [effects[key]['form'] for key in reached],
        'DEV_mothers': len(sources), 'per_arm': rows, 'original_DEV_requests_reused': count,
        'shared_rule_only': True, 'predictions_sha256': prediction_sha,
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(outcome / 'terminal.json', result)
    write_status(outcome, {'status':result['status'], 'terminal_sha256':result['terminal_sha256']}, POINTER)
    print(outcome)


if __name__ == '__main__':
    run()
