"""Give all retained TRAIN reads the same source-proved retention exception."""

from pathlib import Path
import re
import sqlite3

from experiments import convergence_revision6_retention_interface as readers
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_retention_grant_replay'
POINTER = HANDOFF / 'revision6_retention_grant_replay_current.json'
DISPOSAL = re.compile(r'\b(?:return\w*|destroy\w*|eras\w*|delet\w*)\b', re.I)
REQUIREMENT = re.compile(r'\b(?:shall|will|must|ensure|within)\b', re.I)
EXCEPTION = re.compile(r'\b(?:except that|save that|notwithstanding|provided,? however)\b', re.I)
INFORMATION = re.compile(r'\bconfidential information\b', re.I)
COPY = re.compile(r'\bcop(?:y|ies)\b', re.I)
ACTIVE_GRANT = re.compile(r'\b(?:may|will be entitled to|shall be entitled to) (?:retain|maintain)\b', re.I)
PASSIVE_GRANT = re.compile(r'\bcop(?:y|ies)\b[^.;]{0,110}\bmay be retained\b', re.I)
BACKUP_EXEMPTION = re.compile(
    r'\b(?:neither party will be required|(?:is|are) not required) to (?:delete|return|destroy)\b'
    r'[^.;]{0,200}\b(?:back.?up|archival)\b', re.I,
)


def source_proofs(spans):
    """Bind explicit exceptions to an actual disposal rule and information object."""
    lines = [' '.join(text.split()) for text in spans]
    proofs = []
    for index, line in enumerate(lines):
        if not INFORMATION.search(line):
            continue
        grant = ACTIVE_GRANT.search(line) or PASSIVE_GRANT.search(line)
        if not (grant and COPY.search(line)):
            grant = BACKUP_EXEMPTION.search(line)
        if not grant:
            continue
        for lead in range(index, max(-1, index - 6), -1):
            activation = EXCEPTION.search(line[:grant.start()] if lead == index else lines[lead])
            if activation is None:
                continue
            if lead == index and DISPOSAL.search(line[:activation.start()]):
                proofs.append((index,))
            else:
                anchor = next((j for j in range(lead - 1, max(-1, lead - 5), -1)
                               if DISPOSAL.search(lines[j]) and INFORMATION.search(lines[j])
                               and REQUIREMENT.search(lines[j]) and not EXCEPTION.search(lines[j])), None)
                if anchor is not None:
                    refs = sorted({anchor, lead, index})
                    # A permission that ends in its object can be qualified by
                    # a list caption immediately afterwards, as in B1 TRAIN.
                    if not line.endswith('.') and index + 1 < len(lines) and re.match(r'^\([a-z]\)', lines[index + 1]):
                        refs.append(index + 1)
                    proofs.append(tuple(refs))
            break
    return sorted(set(proofs), key=lambda refs: (len(refs), refs))


def apply(prediction, paths):
    if not paths:
        return prediction
    cited = set(prediction['evidence'])
    if prediction['answer'] == readers.interface.ENTAILMENT and any(set(p) <= cited for p in paths):
        return prediction
    return {'answer': readers.interface.ENTAILMENT, 'evidence': list(paths[0])}


def run():
    marker = read(readers.pointer('train'))
    parent = ROOT / marker['artifact_root']
    binding = read(parent / 'binding.json')
    terminal = verify(read(parent / 'terminal.json'), 'terminal_sha256')
    pred_path = parent / 'sealed_predictions.json'
    if (parent.name != digest(binding) or marker['terminal_sha256'] != terminal['terminal_sha256']
            or terminal['TEST_opened'] or sha(pred_path) != terminal['predictions_sha256']
            or any(sha(parent / 'source_snapshot' / name) != h for name, h in binding['source_sha256'].items())):
        raise ValueError('Use the sealed actual TRAIN comparison')
    cases, grade, reviewed, roles, _, exact = readers.opened_binding('train')
    if digest(exact) != parent.name:
        raise ValueError('The fitted reader, source, or scoring binding changed')
    proofs = {key: source_proofs([r['text'] for r in value['payload']['indexed_spans']])
              for key, value in cases.items()}
    already_positive = {pos for pos, row in readers.review.REVIEWS.items() if row[1] == readers.interface.ENTAILMENT}
    if not all(tuple(reviewed[key]['position']) in already_positive for key, paths in proofs.items() if paths):
        raise ValueError('Each positive exception must be supported by the prior independent source review')
    original = read(pred_path)
    # Seal both the admissible source paths and all revised outputs before native scoring.
    spec = {'TRAIN_terminal_sha256': terminal['terminal_sha256'], 'proofs_sha256': digest(proofs),
            'source_sha256': {str(Path(__file__).relative_to(ROOT)): sha(Path(__file__))}, 'TEST_opened': False}
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    source = Path(__file__).resolve()
    snapshot = out / 'source_snapshot' / source.relative_to(ROOT)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    if not snapshot.exists():
        with snapshot.open('xb') as file:
            file.write(source.read_bytes())
    if sha(snapshot) != spec['source_sha256'][str(source.relative_to(ROOT))]:
        raise ValueError('The proof replay must retain its source version')
    immutable_json(out / 'source_proofs.json', proofs)
    revised = {role: {key: apply(row, proofs[key]) for key, row in bank.items()}
               for role, bank in original.items()}
    pred = immutable_json(out / 'sealed_predictions.json', revised)
    if 'train' not in (ROOT / grade[0]).parts or sha(ROOT / grade[0]) != grade[1]:
        raise ValueError('Keep the exact original TRAIN grading')
    summary, effects = readers.score(cases, revised, read(ROOT / grade[0]))
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    result = sealed({
        'status': 'settled_revision6_retention_grant_replay', 'binding_sha256': out.name,
        'original_scores': terminal['scores'], 'scores': summary, 'synthesized_vs': effects,
        'witnessed_TRAIN': [{'position': reviewed[k]['position'], 'proofs': paths,
                             'original_answers': {role: original[role][k]['answer'] for role in roles}}
                            for k, paths in proofs.items() if paths],
        'predictions_sha256': pred, 'ledger': ledger, 'TEST_opened': False,
        'original_executor_requests_reused': terminal['new_executor_requests'], 'new_executor_requests': 0,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
