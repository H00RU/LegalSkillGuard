"""Bind disclosure polarity to the fact of an agreement in native ContractNLI views."""

import json
from collections import Counter
from pathlib import Path
import re
import sqlite3
from statistics import mean

from experiments import convergence_revision5_cni_reverse_engineering as archive
from experiments.convergence_pilot_b0 import BASE, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


TASK = 'nda-10'
HOME = BASE / 'revision5_CNI_agreement_object_20261119'
TABLE = ROOT / 'reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_AGREEMENT_OBJECT_20261119.json'
EXISTS = (r'\b(?:the )?existence(?: and (?:content|nature|terms))? of (?:this |the |any )?'
          r'(?:business )?(?:agreement|negotiations?|discussions?)\b')
TAKEN_PLACE = (r'\b(?:the )?fact that\b[^.;]{0,125}\b(?:confidential relationship|entered into discussions|'
               r'discussions? (?:have|has|are|were)|negotiations? (?:have|has|are|were))\b|'
               r'\bdiscussions? that give rise to this agreement\b')
EVENT = re.compile(EXISTS + '|' + TAKEN_PLACE, re.I)
EVENT_CUE = re.compile(r'\b(?:existence|discussions?|negotiat\w*|arrangement|relationship|announc\w*|'
                       r'publicity|news release|truth|content, nature or extent|terms of this (?:confidentiality )?agreement)\b', re.I)
PUBLIC_ACT = r'(?:disclos\w*|publiciz\w*|advertis\w*|announc\w*|publish\w*|make public|reveal\w*|news release)'
BAR = re.compile(r'\b(?:shall|will|may|must)\s+not\b[^.;]{0,220}\b' + PUBLIC_ACT + r'\b', re.I)
KEEP = re.compile(r'\b(?:keep\b[^.;]{0,160}\bconfidential|shall be kept confidential)\b', re.I)
GRANT = re.compile(r'\b(?:may freely|may publicly|expressly permits?\b[^.;]{0,35}\bto|may expressly)\s+'
                   + PUBLIC_ACT + r'\b', re.I)
BREAK = re.compile(r'[.;]|\b(?:provided (?:however|that)|as long as|nor shall|may however)\b', re.I)
MEMBER = re.compile(r'\bconfidential information\b[^.;]{0,120}\b(?:means|shall include|includes)\b', re.I)
LIST = re.compile(r'^\(([a-z])\)\s+', re.I)
CI = re.compile(r'\bconfidential information\b', re.I)
LIMIT = re.compile(r'\b(?:subject to|except that|to the extent|without the prior)\b', re.I)


def signed_clauses(spans):
    restricted, granted = set(), set()
    for index, text in enumerate(spans):
        for clause in BREAK.split(text):
            for match in BAR.finditer(clause):
                if EVENT.search(clause[match.end():]):
                    restricted.add(index)
            for match in KEEP.finditer(clause):
                if EVENT.search(match[0]) or (match[0].lower().startswith('shall') and EVENT.search(clause[:match.start()])):
                    restricted.add(index)
            for match in GRANT.finditer(clause):
                if EVENT.search(clause[match.end():]) and not LIMIT.search(clause) and not BAR.search(clause):
                    granted.add(index)
    return restricted, granted


def membership(spans):
    definitions = set()
    protection = set()
    for index, text in enumerate(spans):
        head = MEMBER.search(text)
        if head and not LIMIT.search(text):
            if EVENT.search(text[head.end():]):
                definitions.add((index,))
            if text.endswith(':') or text.endswith('including'):
                for count, pos in enumerate(range(index + 1, min(index + 7, len(spans)))):
                    item = LIST.match(spans[pos])
                    if not item or ord(item[1].lower()) - ord('a') != count:
                        break
                    if EVENT.search(spans[pos]) and not LIMIT.search(spans[pos]):
                        definitions.add((index, pos))
        for clause in BREAK.split(text):
            if any(CI.search(clause[m.end():]) for m in BAR.finditer(clause)) and not LIMIT.search(clause):
                protection.add(index)
    if len(definitions) != 1 or not protection:
        return []
    (defined,) = definitions
    return sorted(set(defined) | protection)


def compile_scope(view):
    text = view['public']['source_text']
    spans = [archive.clean(span) for span in archive.span_inventory(view)]
    restricted, granted = signed_clauses(spans)
    linked = membership(spans) if not restricted else []
    if granted and (restricted or linked):
        return 'ambiguous', None
    if restricted:
        return 'explicit_bar', {'answer': 'Entailment', 'evidence_sentence_ids': sorted(restricted)}
    if linked:
        return 'defined_object_bar', {'answer': 'Entailment', 'evidence_sentence_ids': linked}
    if granted:
        return 'explicit_grant', {'answer': 'Contradiction', 'evidence_sentence_ids': sorted(granted)}
    if not EVENT_CUE.search(archive.clean(text)):
        return 'no_event_cue', {'answer': 'NotMentioned', 'evidence_sentence_ids': []}
    return 'unbound_event_cue', None


def score(sources, predictions, annotations):
    rows = {metric: {phase: [] for phase in ('original', 'common')} for metric in ('accuracy', 'evidence_f1')}
    for key, pair in predictions.items():
        view, = (v for v in sources[key]['views'] if v['id'] == TASK)
        for phase, output in pair.items():
            result = grade_view('ContractNLI', view, annotations[key][TASK], output['answer'], output['evidence_sentence_ids'])
            for metric, field in (('accuracy', 'grade'), ('evidence_f1', 'evidence_f1')):
                rows[metric][phase].append({'source': key, 'view': TASK, 'grade': result[field]})
    return {metric: {'before': mean(r['grade'] for r in v['original']), 'after': mean(r['grade'] for r in v['common']),
                     'better': sum(y['grade'] > x['grade'] for x, y in zip(*v.values(), strict=True)),
                     'worse': sum(y['grade'] < x['grade'] for x, y in zip(*v.values(), strict=True)),
                     'paired': paired_source_effect(v['original'], v['common'])}
            for metric, v in rows.items()}


def run():
    contexts = archive.archive_context()
    cohorts, lock = {}, {}
    for partition in ('train', 'dev'):
        sources, original, grade, receipts = archive.collect(*contexts, partition)
        scopes = {key: compile_scope(next(v for v in case['views'] if v['id'] == TASK)) for key, case in sources.items()}
        cohorts[partition] = sources, original, grade, scopes
        lock[partition] = {'sources': digest(sources), 'terminals': receipts, 'native_grade_sha256': sha(grade),
                           'scope_sha256': digest(scopes)}
    binding = {'study': 'agreement_object_worktree_development', 'partitions': lock, 'runner_sha256': sha(Path(__file__)),
               'policy': 'Shared native control with an explicit abstention outside source-bound scope.'}
    out = HOME / digest(binding)
    immutable_json(out / 'binding.json', binding)
    bank = {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
        for partition, (sources, original, _, scopes) in cohorts.items():
            predictions, accepted = {}, {}
            for arm, records in original.items():
                predictions[arm] = {}
                for key, record in records.items():
                    native = record['native'][TASK]
                    native = {k: native[k] for k in ('answer', 'evidence_sentence_ids')}
                    state, bound = scopes[key]
                    if bound and bound != native:
                        _, measured = archive.checked_result(db, sources[key], record, accepted, dev=partition == 'dev')
                        # Use the saved official prediction in both arms. Verifying the raw record
                        # can additionally recover complete entries from a cutoff response.
                        if measured[TASK]['handled'] and record['native'][TASK]['handled']:
                            assert all(measured[TASK][k] == v for k, v in native.items())
                    predictions[arm][key] = {'original': native, 'common': bound if bound else native}
            bank[partition] = (predictions, len(accepted))
    digest_predictions = immutable_json(out / 'predictions.json', {k: v[0] for k, v in bank.items()})
    results = {}
    for partition, (sources, _, grade, scopes) in cohorts.items():
        predictions, verified = bank[partition]
        assert sha(grade) == lock[partition]['native_grade_sha256'] and partition in grade.parts
        labels = read(grade)
        result = {'mothers': len(sources), 'scopes': dict(Counter(s[0] for s in scopes.values())),
                  'physical_reads_of_affected_sources_verified': verified,
                  'arms': {arm: score(sources, data, labels) for arm, data in predictions.items()}}
        results[partition] = result
    terminal = {'status': 'settled_revision5_CNI_agreement_object', 'runner_sha256': binding['runner_sha256'],
                'ledger': ledger, 'new_model_requests': 0, 'partition_results': results,
                'predictions_sha256': digest_predictions}
    immutable_json(out / 'terminal.json', terminal)
    immutable_json(TABLE, terminal)
    print(json.dumps({'stage': str(out.relative_to(ROOT)), **terminal}), flush=True)


if __name__ == '__main__':
    run()
