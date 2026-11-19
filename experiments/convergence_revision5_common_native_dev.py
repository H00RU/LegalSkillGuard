"""Run one common native-control pipeline on the sealed five-arm B8 DEV outputs."""

import inspect
import json
from collections import Counter, defaultdict
from pathlib import Path
import sqlite3
from statistics import mean

import jsonschema

from experiments import convergence_revision5_airline_allowance as airline
from experiments import convergence_revision5_cni_compelled_notice as notice
from experiments import convergence_revision5_cni_conditioned_use_license as conditioned
from experiments import convergence_revision5_cni_copy_scope as copies
from experiments import convergence_revision5_cni_nonsolicitation as solicitation
from experiments import convergence_revision5_cni_reverse_engineering as engineering
from experiments import convergence_revision5_maud_adoption_scope as adoption
from experiments import convergence_revision5_maud_knowledge_residual as knowledge
from experiments import convergence_revision5_maud_section_scope as covenants
from experiments import convergence_revision5_oe_category_scope as category
from experiments import convergence_revision5_oe_illinois_asset_attribution as illinois
from experiments import convergence_revision5_oe_oregon_eligibility as oregon
from experiments import convergence_revision5_oe_task_route as exemptions
from experiments import convergence_revision5_oe_wildcard_replay as wildcard
from experiments.convergence_formal_curves import pointer
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY
from experiments.convergence_pilot_b0 import BASE, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces import diversity
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_common_native_dev_20261119'
TABLE = ROOT / 'reports/legal_skill_convergence_20261117/paper/tables/REVISION5_COMMON_NATIVE_DEV_20261119.json'
DATASETS = ('ContractNLI', 'LegalBench_Diversity', 'MAUD', 'OpenExempt', 'RuleArena_Airline')
CONTRASTS = {
    'M1': ('method_one_only', ORDINARY), 'M1_with_M2': ('both', 'method_two_only'),
    'M2': ('method_two_only', ORDINARY), 'M2_with_M1': ('both', 'method_one_only'),
    'both_vs_PARSE': ('both', EXTERNAL_ARM),
}


def contract_rules(source):
    views = {v['id']: v for v in source['views']}
    rules = {}
    for module, rule in (
        (notice, lambda view: (lambda out, p=notice.proof(view): notice.answer(out, p, use_links=True))),
        (engineering, lambda view: (lambda out, p=engineering.source_proof(view): engineering.apply(out, p, linked=True))),
        (solicitation, lambda view: (lambda out, p=solicitation.provision(view): solicitation.project(p, out, use_links=True))),
    ):
        rules[module.TASK] = rule(views[module.TASK])
    independent = copies.matched_direct(copies.source_groups(views[copies.TASK]))
    if independent['answer'] is not None:
        rules[copies.TASK] = lambda _: independent
    for kind, evidence in conditioned.source_binding(source).items():
        rules[conditioned.paired.TASKS[kind]] = lambda _, ids=evidence: {
            'answer': 'Entailment', 'evidence_sentence_ids': list(ids)}
    return rules


def maud_rules(source):
    visible = knowledge.view_for(source)['public']
    anchors = knowledge.definitions(knowledge.normalize(visible['source_text']))
    resolved = knowledge.independent_direct(knowledge.facts(anchors[0])) if len(anchors) == 1 else None
    if resolved is None and adoption.received_notice(visible):
        resolved = 'Actual knowledge'
    proof = covenants.attachment_proof(covenants.view_for(source)['public'])
    rules = {covenants.NEGATIVE: lambda out: {'answer': covenants.policies(out, proof)['attached_exceptions']}}
    if resolved is not None:
        rules[adoption.KNOWLEDGE] = lambda _: {'answer': resolved}
    return rules


def exemption_rules(source):
    def compile_view(view):
        family = view['id']
        bounds = wildcard.native_bounds(view)
        claims = ({name: wildcard.direct_claim(value, bounds['limits']) for name, value in bounds['assets'].items()}
                  if bounds else {})
        facts = category.view_facts(view)
        _, attributed, _ = illinois.attribution(view)

        def apply(out):
            original = out['answer']
            if not isinstance(original, dict):
                return out
            common = exemptions.public_controls(view, original)
            common = wildcard.complete_wildcard(common, family, claims)
            common = category.repair(common, family, facts)
            common = oregon.repair(view, common)
            return {'answer': illinois.add_citation(common, attributed)}

        return apply

    return {v['id']: compile_view(v) for v in source['views']}


def compile_source(source, routes):
    dataset = source['dataset']
    if dataset == 'ContractNLI':
        return contract_rules(source)
    if dataset == 'MAUD':
        return maud_rules(source)
    if dataset == 'OpenExempt':
        return exemption_rules(source)
    view, = source['views']
    public = view['public']
    try:
        if dataset == 'LegalBench_Diversity':
            answer = diversity.reference_outputs(diversity.audit_source(public['source_text']))['answer']
        elif dataset == 'RuleArena_Airline':
            policy = airline.policy(public, routes)
            _, bags = airline.inventory(public['facts'], policy)
            answer = airline.totals(bags, policy)['exact_enumeration']
        else:
            raise KeyError(dataset)
    except ValueError:
        # An input outside the previously verified source grammar keeps its archived prediction.
        return {}
    return {view['id']: lambda _: {'answer': answer}}


def apply_compiled(source, native, rules):
    outputs = {}
    for view in source['views']:
        key = view['id']
        old = native[key]
        original = {'answer': old['answer'], 'evidence_sentence_ids': old['evidence_sentence_ids']}
        rule = rules.get(key)
        revised = {**original, **rule(original)} if rule is not None else original
        if revised != original:
            jsonschema.validate(revised['answer'], view['answer_schema'])
            if source['dataset'] == 'ContractNLI':
                count = len(view['public']['sentence_spans'])
                assert all(type(i) is int and 0 <= i < count for i in revised['evidence_sentence_ids'])
        outputs[key] = {'original': original, 'common': revised}
    return outputs


def archive():
    stage = ROOT / read(pointer(8))['artifact_root']
    binding, terminal = (read(stage / n) for n in ('binding.json', 'terminal.json'))
    assert digest(binding) == stage.name and terminal['batch'] == 8 and not terminal['TEST_opened']
    checkpoint = ROOT / binding['checkpoint_root']
    study = read(checkpoint / 'binding.json')
    assert digest(study) == binding['checkpoint_binding_sha256']
    public = ROOT / binding['b0_dev_data_root']
    cohort = read(public / 'public_DEV_sources.json')
    assert digest(cohort) == read(public / 'binding.json')['DEV_public_sha256']
    assert Counter(s['dataset'] for s in cohort) == dict.fromkeys(DATASETS, 16)
    assert all(s['project_split'] == 'dev' for s in cohort)
    arms = {}
    for arm, expected in terminal['cell_sha256'].items():
        directory = checkpoint / 'dev' / 'B8' / arm
        seal = verify(read(directory / 'prediction_seal.json'), 'prediction_seal_sha256')
        score = verify(read(directory / 'scores.json'), 'cell_sha256')
        assert score['cell_sha256'] == expected and score['partition'] == 'dev'
        assert score['prediction_seal_sha256'] == seal['prediction_seal_sha256']
        assert seal['task_sha256'] == digest(read(directory / 'task.json'))
        arms[arm] = directory, seal, score
    return cohort, arms, study, sha(stage / 'terminal.json')


def grade_outputs(cohort, arms, study, predictions):
    labels = {}
    for dataset, locator in study['grading_paths'].items():
        path = ROOT / locator
        assert 'dev' in path.parts and sha(path) == study['grading_file_sha256'][locator]
        labels[dataset] = read(path)
    cells = {}
    for arm, (_, _, official) in arms.items():
        baseline = {(r['source'], r['view']): r for r in official['source_scores']}
        assert len(baseline) == 384
        rows = {'original': defaultdict(list), 'common': defaultdict(list)}
        for source in cohort:
            dataset, key = source['dataset'], source['key']
            for view in source['views']:
                task = view['id']
                expected = labels[dataset][key][task]
                original = baseline[key, task]
                for phase, output in predictions[arm][key][task].items():
                    metrics = grade_view(dataset, view, expected, output['answer'], output['evidence_sentence_ids'])
                    if phase == 'original':
                        assert original['answer'] == output['answer'] and original['grade'] == metrics['grade']
                    row = {'source': key, 'view': task, 'grade': metrics['grade']}
                    family = task if dataset in ('OpenExempt', 'MAUD') else dataset
                    rows[phase][family].append(row)
                    if dataset == 'LegalBench_Diversity':
                        rows[phase]['Diversity_balanced_accuracy'].append({**row, 'stratum': expected['answer']})
                    if dataset == 'ContractNLI' and 'evidence_f1' in metrics:
                        rows[phase]['ContractNLI_evidence_f1'].append({**row, 'grade': metrics['evidence_f1']})
        cells[arm] = rows
        print(json.dumps({'scored_arm': arm}), flush=True)
    return cells


def compare(base, candidate):
    result = {}
    for metric, entries in base.items():
        a, b = [], []
        for left, right in zip(entries, candidate[metric], strict=True):
            assert (left['source'], left['view']) == (right['source'], right['view'])
            if left['grade'] is not None and right['grade'] is not None:
                a.append(left)
                b.append(right)
        strata = {r['source']: r['stratum'] for r in a} if 'stratum' in a[0] else None
        unit_weighted = metric == 'ContractNLI_evidence_f1'
        effect = paired_source_effect(a, b, strata=strata, native_unit_weighted=unit_weighted)
        def average(rows):
            if not strata:
                return mean(r['grade'] for r in rows)
            return mean(mean(r['grade'] for r in rows if r['stratum'] == s) for s in set(strata.values()))
        result[metric] = {'before': average(a), 'after': average(b),
                          'better_native_units': sum(y['grade'] > x['grade'] for x, y in zip(a, b, strict=True)),
                          'worse_native_units': sum(y['grade'] < x['grade'] for x, y in zip(a, b, strict=True)), **effect}
    return result


def run():
    cohort, arms, study, original = archive()
    routes = airline.public_geography()
    controls = {s['key']: compile_source(s, routes) for s in cohort}
    modules = (airline, notice, conditioned, copies, solicitation, engineering, adoption, knowledge, covenants,
               category, illinois, oregon, exemptions, wildcard, diversity)
    files = [Path(__file__).resolve(), *(Path(inspect.getfile(m)).resolve() for m in modules)]
    binding = {'partition': 'dev', 'stage': 'retrospective_B8_composed_common_control',
               'original_B8_DEV_terminal_sha256': original, 'public_sources_sha256': digest(cohort),
               'source_versions': {str(f.relative_to(ROOT)): sha(f) for f in files},
               'original_cells': {arm: score['cell_sha256'] for arm, (_, _, score) in arms.items()},
               'tariff_reference_sha256': sha(airline.BENCHMARK), 'model_requests_new': 0}
    stage = HOME / digest(binding)
    immutable_json(stage / 'binding.json', binding)
    bank = {}
    for arm, (directory, seal, score) in arms.items():
        bank[arm] = {}
        for source in cohort:
            key, dataset = source['key'], source['dataset']
            saved = read(directory / 'predictions' / (digest(key) + '.json'))
            assert digest(saved) == seal['predictions_sha256'][key] and saved['public_source_sha256'] == digest(source)
            assert saved['library_sha256'] == score['libraries'][dataset]
            bank[arm][key] = apply_compiled(source, saved['result']['native'], controls[key])
    prediction_hash = immutable_json(stage / 'predictions.json', bank)
    cells = grade_outputs(cohort, arms, study, bank)
    contrasts = {name: {phase: compare(cells[ref][phase], cells[target][phase]) for phase in ('original', 'common')}
                 for name, (target, ref) in CONTRASTS.items()}
    disagreements = {
        name: {phase: sum(records[phase] != bank[ref][key][task][phase]
                         for key, by_task in bank[target].items() for task, records in by_task.items())
               for phase in ('original', 'common')}
        for name, (target, ref) in CONTRASTS.items()
    }
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    assert not ledger.get('reserved')
    terminal = {'status': 'settled_revision5_common_native_dev', 'sources': len(cohort), 'views_per_arm': 384,
                'new_model_requests': 0, 'original_b8_dev_terminal_sha256': original, 'ledger': ledger,
                'runner_sha256': sha(Path(__file__)), 'prediction_sha256': prediction_hash,
                'effects_by_arm': {arm: compare(rows['original'], rows['common']) for arm, rows in cells.items()},
                'measured_arm_contrasts': contrasts, 'fixed_source_versions': binding['source_versions'],
                'native_output_disagreements_by_contrast': disagreements,
                'evaluation_role': 'retrospective shared development pipeline, not independent confirmation'}
    immutable_json(stage / 'terminal.json', terminal)
    immutable_json(TABLE, terminal)
    print(stage.relative_to(ROOT), flush=True)


if __name__ == '__main__':
    run()
