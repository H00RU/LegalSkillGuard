"""Apply the shared general-property correction to the sealed B8 EC release."""

from pathlib import Path
from statistics import mean

from experiments import convergence_revision5_release_dev as release
from experiments import convergence_revision6_ec_general_property as property_rule
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_ec_property_release'
POINTER = HANDOFF / 'revision6_ec_property_release_current.json'


class PropertyReleaseActor:
    """Wrap the existing sealed DEV actor and install one common EC rule."""

    def __init__(self, parent, cells):
        self.parent = release.ReleaseActor(parent, cells, {})

    def __call__(self, source, library, purpose):
        inherited = self.parent(source, library, purpose)
        if source['dataset'] != release.OE:
            return inherited
        view = property_rule.view_for(source)
        original = inherited['native']['EC']
        updated = original['answer']
        for citation in property_rule.TEXT:
            supported = property_rule.source_claims(view, citation)
            _, updated = property_rule.project(updated, {}, supported, citation)
        if updated == original['answer']:
            return inherited
        return {**inherited, 'native': {**inherited['native'], 'EC': {**original, 'answer': updated}}}


def run():
    ledger = release.formal.diversity_formal.ledger_status()
    if ledger.get('reserved'):
        raise ValueError('Register the current running experiment before a settled DEV amendment')
    parent, terminal, parent_spec = release.stage(release.POINTER)
    proof_path = ROOT / read(property_rule.POINTER)['artifact_root']
    proof = verify(read(proof_path / 'terminal.json'), 'terminal_sha256')
    if (proof['TEST_opened'] or sha(proof_path / 'sealed_predictions.json') != proof['predictions_sha256']
            or proof['terminal_sha256'] != read(property_rule.POINTER)['terminal_sha256']):
        raise ValueError('Require original verified TRAIN and DEV replay evidence')
    cohort, _, study, _ = release.formal.common.archive()
    if digest(cohort) != parent_spec['DEV_public_sha256']:
        raise ValueError('Use the exact fixed development source roster')
    oe = {s['key']: s for s in cohort if s['dataset'] == release.OE and s['project_split'] == 'dev'}
    if len(oe) != 16:
        raise ValueError('Use the full OpenExempt DEV subset')
    grade = study['grading_paths'][release.OE]
    expected_grade = study['grading_file_sha256'][grade]
    cells = release.parent_cells(parent, terminal)
    spec = {'parent_terminal_sha256': terminal['terminal_sha256'], 'grade_sha256': expected_grade,
            'general_property_evidence': proof['terminal_sha256'], 'original_cells': {
                arm: cell['cell_sha256'] for arm, (_, cell) in cells.items()},
            'scope': 'All arms use the same supplied statute/Jurisdiction/title relation for EC only.',
            'changed_case_set': sorted(oe), 'TEST_opened': False,
            'source_sha256': {str(Path(name).relative_to(ROOT)): sha(Path(name)) for name in (
                __file__, property_rule.__file__, release.__file__,
            )}}
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    for name, expected in spec['source_sha256'].items():
        snap = out / 'source_snapshot' / name
        snap.parent.mkdir(parents=True, exist_ok=True)
        if not snap.exists():
            with snap.open('xb') as file:
                file.write((ROOT / name).read_bytes())
        if sha(snap) != expected:
            raise ValueError('Reuse this exact release actor and rule')
    actor = PropertyReleaseActor(parent, cells)
    bank = {}
    for arm in release.ARMS:
        bank[arm] = {}
        library = {'arm': arm, 'batch': 8}
        for key, source in oe.items():
            old = actor.parent(source, library, 'skill_dev')['native']
            new = actor(source, library, 'skill_dev')['native']
            if set(new) != set(old) or new['EV'] != old['EV']:
                raise ValueError('The classification update must preserve the archived valuation task')
            bank[arm][key] = new['EC']
    pred = immutable_json(out / 'sealed_ec_predictions.json', bank)
    path = ROOT / grade
    if 'dev' not in path.parts or sha(path) != expected_grade:
        raise ValueError('Use original native DEV scoring only after sealing the amendment')
    labels = read(path)
    details, new_rows = {}, {}
    for arm, (_, cell) in cells.items():
        old = [r for r in cell['source_scores'] if r['dataset'] == release.OE and r['view'] == 'EC']
        if {r['source'] for r in old} != set(oe):
            raise ValueError('Original release scores must cover the same cohort and target')
        new = []
        changes = 0
        for row in old:
            key = row['source']
            predicted = bank[arm][key]
            before = actor.parent.original(arm, key)['result']['native']['EC']
            if predicted != before:
                changes += 1
                current = grade_view(release.OE, property_rule.view_for(oe[key]), labels[key]['EC'],
                                     predicted['answer'])['grade']
            else:
                current = row['grade']
            new.append({'source': key, 'view': 'EC', 'grade': current})
        original = [{k: row[k] for k in ('source', 'view', 'grade')} for row in old]
        new_rows[arm] = new
        details[arm] = {'inherited_EC_F1': mean(r['grade'] for r in original),
                        'revised_EC_F1': mean(r['grade'] for r in new), 'outputs_changed': changes,
                        'paired_EC_effect': paired_source_effect(original, new),
                        'other_368_task_scores_inherited_sha256': digest([
                            r for r in cell['source_scores'] if r['dataset'] != release.OE or r['view'] != 'EC'
                        ])}
    if ledger != release.formal.diversity_formal.ledger_status():
        raise ValueError('Only archived development responses may be used')
    result = sealed({
        'status': 'settled_revision6_ec_property_release', 'binding_sha256': out.name,
        'fixed_DEV_mothers': len(oe), 'per_arm': details,
        'EC_method_contrasts': {name: paired_source_effect(new_rows[control], new_rows[active])
                                for name, (active, control) in release.CONTRASTS.items()},
        'archive_terminal_sha256': terminal['terminal_sha256'], 'predictions_sha256': pred,
        'new_executor_requests': 0, 'new_teacher_requests': 0, 'TEST_opened': False, 'ledger': ledger,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
