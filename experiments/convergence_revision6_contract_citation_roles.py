"""Apply a TRAIN-audited citation filter to both ContractNLI reading routes."""

import json
from pathlib import Path
import re
import sqlite3

import jsonschema

from experiments import convergence_revision6_contract_link_control as control
from experiments import convergence_revision6_contract_links as links
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision6_contract_citation_roles'
POINTER = HANDOFF / 'revision6_contract_citation_roles_current.json'
TASK = links.linked.TASK

INFORMATION = re.compile(r"\b(?:confidential\s+information|the\s+information)\b", re.I)
AGREEMENT_OBJECT = re.compile(
    r'\bdisclos\w*\s+the\s+existence\s+of\s+this\s+agreement\b', re.I)
USE_ONLY = re.compile(r'\b(?:will|shall)\s+(?:only\s+)?use\b', re.I)
EMPLOYEE_RECIPIENT = re.compile(
    r"\b(?:to\s+(?:those\s+of\s+)?|except\s+)(?:each\s+party['’]s\s+|"
    r"(?:its|their)\s+)[^.;]{0,105}\bemployees\b", re.I)


def select_citations(spans, permission, definition):
    """Remove source-irrelevant citations while preserving operative scope and lead-ins."""
    texts = [' '.join(span.split()) for span in spans]
    anchors = [i for i in permission if INFORMATION.search(texts[i])
               and links.linked.ACT.search(texts[i])
               and (links.linked.USE.search(texts[i]) or EMPLOYEE_RECIPIENT.search(texts[i]))]
    if not anchors:
        return list(permission), definition
    used = [i for i in permission if i in anchors or not (
        (AGREEMENT_OBJECT.search(texts[i]) and not INFORMATION.search(texts[i]))
        or (USE_ONLY.search(texts[i]) and not links.linked.ACT.search(texts[i]))
    )]
    # An inline recipient can support employee membership without a definition elsewhere.
    if definition is not None and any(EMPLOYEE_RECIPIENT.search(texts[i]) for i in anchors):
        definition = None
    return used, definition


def apply(spans, native, permission, definition):
    if native['answer'] != 'Entailment':
        return native
    if set(native['evidence_sentence_ids']) != set(permission) | (
            {definition} if definition is not None else set()):
        raise ValueError('Only modify the original decoded permission and definition slots')
    permission, definition = select_citations(spans, permission, definition)
    ids = set(permission)
    if definition is not None:
        ids.add(definition)
    return {**native, 'evidence_sentence_ids': sorted(ids)}


def raw_call(db, identity, source, purpose):
    row = db.execute('select status,source,purpose,result from calls where id=?', (identity,)).fetchone()
    if row is None or tuple(row[:3]) != ('completed', source, purpose):
        raise ValueError('A citation audit requires its original completed response')
    return json.loads(row[3])


def run():
    spec, cohort, dev, wires, study, parent, linked_terminal = control.materials()
    direct = ROOT / read(control.POINTER)['artifact_root']
    terminal = verify(read(direct/'terminal.json'), 'terminal_sha256')
    if (direct.name != digest(spec) or read(direct/'binding.json') != spec
            or terminal['binding_sha256'] != direct.name or terminal['TEST_opened']
            or sha(direct/'direct_predictions.json') != terminal['prediction_sha256']):
        raise ValueError('Bind the original same-input control')
    for stage in (parent, direct):
        for name, expected in read(stage/'binding.json')['source_sha256'].items():
            if sha(stage/'source_snapshot'/name) != expected or sha(ROOT/name) != expected:
                raise ValueError('Use the exact archived reader and decoder versions')
    linked_spec, cases, views, *_ = links.materials()
    binding = {
        'stage': 'revision6_contract_citation_roles',
        'linked_terminal': linked_terminal['terminal_sha256'],
        'direct_terminal': terminal['terminal_sha256'],
        'TRAIN_source_review_sha256': digest([
            [list(pos), kind, definition, sorted(required), sorted(allowed)]
            for pos, (kind, definition, required, allowed) in links.linked.REVIEWS.items()
        ]),
        'source_sha256': {str(Path(__file__).relative_to(ROOT)): sha(Path(__file__))},
        'TEST_opened': False, 'new_executor_calls': 0,
    }
    out = HOME / digest(binding)
    immutable_json(out/'binding.json', binding)
    if (out/'terminal.json').exists():
        print(out)
        return
    reads = {}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as db:
        for path in (parent/'measured_reads').glob('*.json'):
            row = read(path)
            key = row['source']
            split = 'dev' if key in dev else 'train'
            view = views[split][key]
            plan, = (p for p in view['plans'] if p['version'] == row['raw_read_version'])
            proof = raw_call(db, row['physical_call_id'], key, 'skill_dev' if split == 'dev' else 'skill_actor')
            if (digest(proof['content']), proof['usage'], proof['finish_reason']) != (
                    row['response_content_sha256'], row['usage'], row['response_finish_reason']):
                raise ValueError('The saved decode must refer to the original physical response')
            reads[key, plan['name']] = row['native']

        calibration = {}
        for pos, item in cases.items():
            key = item['source']['key']
            review = links.linked.REVIEWS[pos]
            required, allowed = review[2:]
            calibration[str(pos)] = {}
            for role in links.ROLES:
                observation = reads[key, role]
                native = links.native(observation)
                refined = apply(views['train'][key]['spans'], native, observation['permission_spans'],
                                observation['definition_span'])
                old, new = (set(p['evidence_sentence_ids']) for p in (native, refined))
                must_retain = required | ({review[1]} if review[1] is not None else set())
                if must_retain & old - new:
                    raise ValueError('A TRAIN-reviewed required citation would be lost')
                calibration[str(pos)][role] = {
                    'removed': len(old - new),
                    'removed_outside_source_review': len(old - new - allowed - must_retain),
                }
        if not any(cell['removed_outside_source_review'] for rows in calibration.values() for cell in rows.values()):
            raise ValueError('The filter lacks source-audited TRAIN evidence')
        immutable_json(out/'TRAIN_source_calibration.json', calibration)

        bank = {role:{k: rows[k][TASK] for k in dev}
                for role, rows in read(parent/'sealed_predictions.json').items()}
        bank['direct_same_input'] = read(direct/'direct_predictions.json')
        bank.update({role+'_filtered':{} for role in (*links.ROLES, 'learned', 'direct_same_input')})
        choices = {row['source']: row for row in linked_terminal['pre_read_selected_pairs']}
        for key, view in dev.items():
            spans = view['spans']
            for role in links.ROLES:
                observation = reads[key, role]
                if links.native(observation) != bank[role][key]:
                    raise ValueError('The filter requires the exact paired native decode')
                bank[role+'_filtered'][key] = apply(spans, bank[role][key], observation['permission_spans'],
                                                    observation['definition_span'])
            choice = 'synthesized' if choices[key]['picked_synthesized'] else 'fixed'
            bank['learned_filtered'][key] = bank[choice+'_filtered'][key]
            receipt = read(direct/'physical_reads'/(digest(key)+'.json'))
            proof = raw_call(db, receipt['call_id'], key, 'skill_dev')
            schema = wires[key][1]
            baseline = bank['direct_same_input'][key]
            if control.decode(view, schema, proof) != baseline or baseline != receipt['output']:
                raise ValueError('The filter requires the exact matched direct decode')
            if baseline['answer'] == 'Entailment':
                value = json.loads(proof['content'])
                jsonschema.validate(value, schema)
                slots = links.citations.canonical_citations(value)
                baseline = apply(spans, baseline, slots['permission_spans'], slots['definition_span'])
            bank['direct_same_input_filtered'][key] = baseline

    prediction_sha = immutable_json(out/'predictions.json', bank)
    grade = study['grading_paths'][links.linked.DATASET]
    if sha(ROOT/grade) != study['grading_file_sha256'][grade] or 'dev' not in Path(grade).parts:
        raise ValueError('Use the fixed DEV grader after sealing predictions')
    labels = read(ROOT/grade)
    compare = links.first.compare(cohort, bank, labels)
    contrasts = {}
    for before, after in (('learned', 'learned_filtered'), ('direct_same_input', 'direct_same_input_filtered'),
                          ('direct_same_input_filtered', 'learned_filtered')):
        for metric in ('grade', 'evidence_f1'):
            rows = [
                [{'source': s['key'], 'view': TASK,
                  'grade': links.first.native_score(s, bank[role][s['key']], labels)[metric]} for s in cohort]
                for role in (before, after)
            ]
            contrasts[f'{after}_vs_{before}_{metric}'] = paired_source_effect(*rows)
    result = sealed({
        'status':'settled_revision6_contract_citation_roles', 'binding_sha256':out.name,
        'predictions_sha256':prediction_sha, 'TRAIN_calibration_sha256':sha(out/'TRAIN_source_calibration.json'),
        'TRAIN_mothers':len(cases), 'DEV_mothers':len(cohort), 'scores':compare, 'effects':contrasts,
        'original_read_count':len(reads)+len(dev), 'new_executor_calls':0, 'TEST_opened':False,
    }, 'terminal_sha256')
    immutable_json(out/'terminal.json', result)
    write_status(out, {'status':result['status'], 'terminal_sha256':result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
