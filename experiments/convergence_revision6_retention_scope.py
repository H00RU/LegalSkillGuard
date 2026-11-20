"""Project a B5 retention veto onto its independently reviewed contract scope."""

from pathlib import Path
import re
import sqlite3

from experiments import convergence_revision6_retention_group_transfer as transfer
from legal_skill_guard.rr.checkpoint import immutable_json


BASE, HANDOFF, ROOT = transfer.BASE, transfer.HANDOFF, transfer.ROOT
retention = transfer.selection.retention
HOME = BASE / 'revision6_retention_scope'
POINTER = HANDOFF / 'revision6_retention_scope_current.json'
DISPOSITION, RETENTION = retention.TASKS
ENTERING, PROPOSAL = 'entering', 'proposal'

DISPOSITION_TEXT = re.compile(
    r'\b(?:return(?:ed|ing)?|destroy(?:ed|ing)?|deliver(?:ed|ing)?)\b.*\b(?:all|any)\b.*'
    r'\b(?:documents?|records?|confidential information|data|copies)\b',
    re.I,
)
INLINE_BAN = re.compile(r'\bwithout retaining any cop(?:y|ies)[. ]*$', re.I)
PASSIVE_BAN = re.compile(r'^.{0,125}\bno copies\b[^.;]{0,90}\bshall be retained\b', re.I)
ACTIVE_BAN = re.compile(
    r'^.{0,100}\b(?:shall|will|must) not retain any cop(?:y|ies)\b'
    r'(?: of (?:any of )?(?:(?:these|such|the foregoing) (?:documents|records|materials)|'
    r'(?:such |the )?confidential information))?[. ]*$',
    re.I,
)
EXCEPTION = re.compile(
    r'\b(?:except|unless|notwithstanding|provided|however|subject to|'
    r'(?:can|may|entitled to|permitted to)\s+(?:keep|retain|maintain)|'
    r'archival|back.?up|record retention)\b',
    re.I,
)


def prohibition(spans):
    """Return a unique disposition-linked prohibition with no nearby exception."""
    spans = [' '.join(line.split()) for line in spans]
    proofs = []
    for index, line in enumerate(spans):
        if INLINE_BAN.search(line) and DISPOSITION_TEXT.search(line):
            anchor = index
        elif index and (PASSIVE_BAN.search(line) or ACTIVE_BAN.search(line)):
            anchor = index - 1
            if not DISPOSITION_TEXT.search(spans[anchor]):
                continue
        else:
            continue
        # The next unit can supply an exception to the prohibition.
        neighborhood = ' '.join(spans[anchor:index + 2])
        if not EXCEPTION.search(neighborhood):
            proofs.append((anchor, index))
    return proofs[0] if len(proofs) == 1 else None


def apply(entering, proposal, witness):
    """Return the scoped reader route and a direct assertion with the same proof."""
    if witness is None or proposal[RETENTION]['answer'] != retention.ENTAIL:
        return proposal, proposal
    scoped = {**proposal, RETENTION: entering[RETENTION]}
    direct = {**proposal, RETENTION: {
        **proposal[RETENTION], 'answer': retention.DENY,
        'evidence_sentence_ids': [witness[1]], 'handled': True, 'reason': None,
    }}
    return scoped, direct


def load_parent(module):
    pointer = transfer.read(module.POINTER)
    root = ROOT / pointer['artifact_root']
    binding = transfer.read(root / 'binding.json')
    terminal = transfer.verify(transfer.read(root / 'terminal.json'), 'terminal_sha256')
    if (terminal['TEST_opened'] or terminal['binding_sha256'] != transfer.digest(binding)
            or root.name != terminal['binding_sha256']
            or pointer['terminal_sha256'] != terminal['terminal_sha256']):
        raise ValueError('Require the sealed TRAIN and DEV reader comparison')
    return root, binding, terminal


def train_witness(fitted):
    a = fitted['choices']['candidate_driven']
    if a['compatible_proposal'] or not a['compatible_entering']:
        raise ValueError('The TRAIN group must support a veto on the B5 candidate')
    checkpoint = ROOT / transfer.read(retention.BOOTSTRAP)['artifact_root']
    study = transfer.read(checkpoint / 'binding.json')
    sources = retention.source_material(retention.load_roster(study))
    calibrated = {}
    for _, (position, view, _) in sources.items():
        if position[0] > 5:
            continue
        label = retention.REVIEWS[position][1]
        proof = prohibition(retention.spans_for(view))
        calibrated[position] = proof
        if proof is not None and label != retention.DENY:
            raise ValueError('Prohibition must leave the reviewed positive exceptions intact')
    pos = tuple(a['selected_position'])
    proof = calibrated.get(pos)
    close, hold, close_ids, hold_ids = retention.REVIEWS[pos]
    if (close, hold) != (retention.ENTAIL, retention.DENY) or proof is None:
        raise ValueError('The ranked TRAIN group must identify both legal assertions')
    if proof[0] not in close_ids or proof[1] not in hold_ids:
        raise ValueError('The original source audit must support the exact proof path')
    return {'source_groups': len(calibrated), 'proofs': sum(p is not None for p in calibrated.values()),
            'selected_position': pos, 'support_spans': proof,
            'same_information_direct_uses_same_source_spans': True}


def run():
    fit, _, fitted = load_parent(transfer.selection)
    old, old_binding, original = load_parent(transfer)
    if old_binding['fit_TERMINAL'] != fitted['terminal_sha256']:
        raise ValueError('Use the DEV archive for the exact B5 proposal')
    train = train_witness(fitted)
    libraries = {p: transfer.verify(transfer.read(fit / 'TRAIN_batch_libraries' / f'{p}.json'),
                                    'snapshot_sha256') for p in transfer.POLICIES}
    if {p: lib['snapshot_sha256'] for p, lib in libraries.items()} != fitted['library_sha256']:
        raise ValueError('Reader snapshots changed after selection')
    with sqlite3.connect(transfer.LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        cases, archived, grade, _, count, input_hash = transfer.materials(db, libraries)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if (transfer.sha(old / 'sealed_predictions.json') != original['predictions_sha256']
            or archived != transfer.read(old / 'sealed_predictions.json')
            or input_hash != old_binding['matched_public_and_executor_sha256']
            or grade[1] != old_binding['DEV_grade_sha256']):
        raise ValueError('Require exact archived predictions and scoring inputs')

    proposal, entering = (archived[p] for p in transfer.POLICIES)
    bank = {PROPOSAL: proposal, ENTERING: entering, 'scoped': {}, 'same_information_direct': {}}
    coverage = {}
    for key, source in cases.items():
        view, = (v for v in source['views'] if v['id'] == RETENTION)
        proof = prohibition(retention.spans_for(view))
        coverage[key] = proof
        scoped, direct = apply(entering[key], proposal[key], proof)
        bank['scoped'][key] = scoped
        bank['same_information_direct'][key] = direct

    source_files = [Path(name).resolve() for name in (transfer.__file__, retention.__file__, __file__)]
    binding = {'TRAIN_terminal': fitted['terminal_sha256'], 'DEV_terminal': original['terminal_sha256'],
               'TRAIN_proof': train, 'DEV_proofs_sha256': transfer.digest(coverage),
               'DEV_grade_sha256': grade[1], 'TEST_opened': False,
               'source_sha256': {str(p.relative_to(ROOT)): transfer.sha(p) for p in source_files}}
    out = HOME / transfer.digest(binding)
    immutable_json(out / 'binding.json', binding)
    for path in source_files:
        snapshot = out / 'source_snapshot' / path.relative_to(ROOT)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            with snapshot.open('xb') as handle:
                handle.write(path.read_bytes())
        if transfer.sha(snapshot) != binding['source_sha256'][str(path.relative_to(ROOT))]:
            raise ValueError('Source changed during replay')
    prediction_sha = immutable_json(out / 'sealed_predictions.json', bank)
    path = ROOT / grade[0]
    if 'dev' not in path.parts or transfer.sha(path) != grade[1]:
        raise ValueError('Use the original native DEV scoring inputs only after sealing')
    labels = transfer.read(path)
    effects = {}
    for comparison in (ENTERING, PROPOSAL, 'same_information_direct'):
        effects[comparison] = transfer.score(cases, dict(zip(
            transfer.POLICIES, (bank[comparison], bank['scoped']), strict=True)), labels)
    hits = [key for key, proof in coverage.items() if proof is not None]
    activated = [key for key in hits if proposal[key][RETENTION]['answer'] == retention.ENTAIL]
    terminal = transfer.sealed({
        'status': 'settled_revision6_retention_scope', 'binding_sha256': out.name,
        'TRAIN': train, 'DEV_mothers': len(cases), 'DEV_proofs': len(hits), 'activated': len(activated),
        'scoped_retention_changed': sum(bank['scoped'][k][RETENTION] != proposal[k][RETENTION] for k in hits),
        'retention_outputs': [{
            'scope': list(coverage[key]),
            'prediction': {a: outputs[key][RETENTION]['answer'] for a, outputs in bank.items()},
            'native_label': labels[key][RETENTION]['answer'],
        } for key in hits],
        'native': effects, 'predictions_sha256': prediction_sha,
        'original_executor_calls_reused': count, 'new_executor_requests': 0,
        'ledger': ledger, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    transfer.write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
