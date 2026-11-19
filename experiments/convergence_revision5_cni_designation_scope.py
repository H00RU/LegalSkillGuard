"""Separate original qualification from other marking cues on sealed CNI cells."""

import json
import re
from collections import Counter
from pathlib import Path
from statistics import mean

from experiments import convergence_revision5_cni_compose_scope as composed
from experiments import convergence_revision5_cni_designation_control as prior
from experiments import convergence_revision5_cni_reverse_engineering as archive
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha
from experiments.convergence_revision5_diversity_formal import ledger_status
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed, verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / 'revision5_cni_designation_scope_20261119'
POINTER = HANDOFF / 'revision5_cni_designation_scope_current.json'
TASK = prior.TASK
DEFINITION = re.compile(
    r'\bconfidential information[”"\']?(?:,\s*whenever used in this agreement,)?\s*'
    r'(?:(?:shall|will)\s+)?(?:mean(?:s)?|includ(?:e|es))\b', re.I)
ORIGINAL_ACT = re.compile(
    r'\b(?:mark(?:ed|ing|s)?|label(?:led|ed|ing|s)?|designat\w*|identif\w*|legend\w*|stamp(?:ed|ing|s)?|'
    r'classif(?:ied|ication)|declared\s+as|pointed\s+out|'
    r'(?:confirm\w*|indicat\w*|notif\w*)[^.;]{0,60}(?:confidential|proprietary)|'
    r'(?:confidential|proprietary)[^.;]{0,50}(?:confirm\w*|indicat\w*))\b', re.I)
PRIVACY = re.compile(r'\bpersonally identifiable\b', re.I)
ALL_MEDIA = re.compile(r'\b(?:in any form whatsoever|in whatever form|regardless of (?:its )?form or medium)\b', re.I)
CONJUNCTIVE_MARK = re.compile(
    r'\band that,?\s+(?:at the time of disclosure(?: to the recipient)?,?\s+)?'
    r'(?:is|shall be|must be)\s+(?:designated|identified|marked)\s+as\s+[“"]?confidential[”"]?\.?$', re.I)
NARROW_COPIES = re.compile(
    r'^(?:(?:the )?receiving party (?:will|shall|must) clearly label all copies of confidential information as confidential\.?$|'
    r'(?:any and all reproductions|each copy(?:, including its storage media,)?|any copies made by the contractor)'
    r'[^.;]{0,160}\b(?:shall|must)\b[^.;]{0,105}\b(?:marked|identified|contain a confidentiality legend|'
    r'contain any and all confidential or proprietary notices)\b)', re.I)
REPRODUCTION = re.compile(
    r'^any reproduction of any confidential information by the recipient shall remain the property of the provider '
    r'and shall contain any and all confidential or proprietary notices or legends that appear on the original\b', re.I)
RETAINED_ID = re.compile(r'\bshall identify in writing the specific confidential information retained\b', re.I)
RELEASE_ID = re.compile(r'\b(?:designated|identified) in writing by the source as no longer being confidential information\b', re.I)
ALTER_NOTICE = re.compile(
    r'\bnot\b[^.;]{0,70}\b(?:remove|overprint|deface)\b[^.;]{0,100}\b(?:notice|legend)\b'
    r'(?: of confidentiality, copyright, trademark, logo, legend or other notices of ownership or confidentiality)?',
    re.I)
SEPARATE_ORIGINAL = re.compile(r'\b(?:and|but)\s+(?:original(?:s| information)?|information at disclosure)\b', re.I)
OPEN_ALTERNATIVE = re.compile(
    r'\b(?:whether or not|regardless of (?:whether|any marking)|or should be deemed)\b[^.;]{0,110}'
    r'(?:marked|designated|identified|confidential)', re.I)


def role(line):
    """Identify a checked non-qualification use of a designation cue."""
    text = PRIVACY.sub('', line)
    if not ORIGINAL_ACT.search(text):
        return None
    if not SEPARATE_ORIGINAL.search(text):
        for label, patterns in (('copy_or_notice_preservation', (NARROW_COPIES, REPRODUCTION, ALTER_NOTICE)),
                                ('retention_or_release', (RETAINED_ID, RELEASE_ID))):
            for pattern in patterns:
                clause = pattern.search(text)
                if clause and not ORIGINAL_ACT.search(text[:clause.start()] + ' ' + text[clause.end():]):
                    return label
    return 'potential_qualification'


def proof(view):
    """Retain uncertainty when an original-information cue cannot be resolved."""
    previous = prior.direct(view)
    spans = [' '.join(line.split()) for line in prior.spans_for(view)]
    roles = {i: kind for i, line in enumerate(spans) if (kind := role(line)) is not None}
    if previous['answer'] is not None:
        return {'kind': 'established_positive_or_negative', 'answer': previous['answer'],
                'evidence_sentence_ids': previous['evidence'], 'roles': roles}
    definitions = [i for i, line in enumerate(spans) if DEFINITION.search(line)]
    if len(definitions) == 1:
        i, = definitions
        text = spans[i]
        if (ALL_MEDIA.search(text) and CONJUNCTIVE_MARK.search(text)
                and all(k == i or kind != 'potential_qualification' for k, kind in roles.items())
                and not any(OPEN_ALTERNATIVE.search(line) for line in spans)):
            return {'kind': 'all_media_conjunctive_qualification', 'answer': 'Entailment',
                    'evidence_sentence_ids': [i], 'roles': roles}
    if 'potential_qualification' not in roles.values():
        return {'kind': 'no_in_scope_marking_cue', 'answer': 'NotMentioned',
                'evidence_sentence_ids': [], 'roles': roles}
    return {'kind': 'unresolved_original_qualification', 'answer': None, 'evidence_sentence_ids': [], 'roles': roles}


def alternatives(view, before, facts):
    incumbent = {'answer': before['answer'], 'evidence_sentence_ids': before['evidence_sentence_ids']}
    source = {k: facts[k] for k in incumbent}
    if facts['kind'] == 'no_in_scope_marking_cue':
        # The comparison guard treats any observed role of a marking cue as unresolved.
        naive = source if not facts['roles'] else incumbent
    elif facts['answer'] is not None and facts['kind'] != 'established_positive_or_negative':
        naive = source
    else:
        naive = incumbent
    revised = source if facts['answer'] is not None and facts['kind'] != 'established_positive_or_negative' else incumbent
    if any(i not in range(len(prior.spans_for(view))) for i in revised['evidence_sentence_ids']):
        raise ValueError('Use exact native zero-based source spans')
    return {'composed': incumbent, 'all_cues_block_absence': naive, 'role_scoped': revised}


def grade_set(bank, views, labels):
    by_arm = {}
    for arm, predictions in bank.items():
        task_rows = {}
        for key, record in predictions.items():
            for label, output in record.items():
                score = grade_view(composed.DATASET, views[key], labels[key][TASK],
                                   output['answer'], output['evidence_sentence_ids'])
                task_rows.setdefault(label, []).append({'source': key, 'view': TASK, **score})
        original = task_rows['composed']
        by_arm[arm] = {label: {'correct': int(sum(r['grade'] for r in rows)),
                             'evidence_f1': mean(r['evidence_f1'] for r in rows),
                             'native_better': sum(b['grade'] > a['grade'] for a, b in zip(original, rows, strict=True)),
                             'native_worse': sum(b['grade'] < a['grade'] for a, b in zip(original, rows, strict=True)),
                             'paired_vs_composed': paired_source_effect(original, rows)}
                       for label, rows in task_rows.items()}
    return by_arm


def run():
    ledger = ledger_status()
    parent_status = read(composed.POINTER)
    parent = ROOT / parent_status['artifact_root']
    terminal = verify(read(parent / 'terminal.json'), 'terminal_sha256')
    if terminal['terminal_sha256'] != parent_status['terminal_sha256'] or terminal['TEST_opened'] or ledger.get('reserved'):
        raise ValueError('Use the settled revised ContractNLI TRAIN and DEV cells')
    spec = {'parent_terminal_sha256': terminal['terminal_sha256'], 'task': TASK,
            'source_sha256': {str(f.relative_to(ROOT)): sha(f) for f in (
                Path(__file__), Path(prior.__file__), Path(composed.__file__))},
            'scope': 'original information qualification, native TRAIN and fixed B8 DEV only'}
    out = HOME / digest(spec)
    immutable_json(out/'binding.json', spec)
    if (out/'terminal.json').is_file():
        print(out, flush=True)
        return
    partitions, hashes, scores = {}, {}, {}
    for part in ('train', 'dev'):
        sources, _, grade, _ = archive.collect(*archive.archive_context(), part)
        views = {key: next(v for v in s['views'] if v['id'] == TASK) for key, s in sources.items()}
        attested = parent/f'{part}_predictions.json'
        if (sha(attested) != terminal['predictions_sha256'][part]
                or sha(grade) != read(parent/'binding.json')[part.upper()+'_grade_sha256']):
            raise ValueError('Preserve the native evaluation baseline and matching split grades')
        before = read(attested)
        facts = {key: proof(view) for key, view in views.items()}
        variant = {arm: {key: alternatives(views[key], tasks[TASK], facts[key]) for key, tasks in rows.items()}
                   for arm, rows in before.items()}
        hashes[part] = immutable_json(out/f'{part}_predictions.json', variant)
        partitions[part] = (views, grade, facts, variant)
    for part, (views, grade, facts, variant) in partitions.items():
        labels = read(grade)
        counts = Counter()
        for key, scope in facts.items():
            counts[scope['kind']] += 1
            if scope['kind'] == 'no_in_scope_marking_cue':
                counts['supported_absence_with_irrelevant_cues'] += bool(scope['roles'])
                counts['absence_native_label_disagreement'] += labels[key][TASK]['answer'] != scope['answer']
        scores[part] = {'mothers': len(views), 'scope_counts': dict(counts), 'arms': grade_set(variant, views, labels)}
    if ledger_status() != ledger:
        raise ValueError('No physical requests belong to this replay')
    result = sealed({'status': 'settled_CNI_original_designation_scope', 'binding_sha256': digest(spec),
                     'prediction_sha256': hashes, 'results': scores, 'new_model_calls': 0,
                     'TEST_opened': False, 'ledger': ledger}, 'terminal_sha256')
    immutable_json(out/'terminal.json', result)
    pending = POINTER.with_suffix('.pending')
    pending.write_text(json.dumps({'status': result['status'], 'artifact_root': str(out.relative_to(ROOT)),
                                   'terminal_sha256': result['terminal_sha256']})+'\n')
    pending.replace(POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
