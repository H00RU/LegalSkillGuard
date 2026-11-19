"""Separate a named filer's asset attribution from possession in matched EC reads."""

import json
from pathlib import Path
import re
import sqlite3
from statistics import mean

from experiments import convergence_oe_feedback_pair as initial
from experiments import convergence_revision5_oe_repair as corrective
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_oe_category_scope import ec_read
from experiments.convergence_revision5_oe_wildcard_replay import old_amount_bank
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_OE_illinois_asset_attribution_20261119'
TABLE = ROOT / 'reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_ILLINOIS_ASSET_ATTRIBUTION_20261119.json'
CITATION = '735 Ill. Comp. Stat. 5/12-1001(b)'
RULE = "The debtor's equity interest, not to exceed $4,000 in value, in any other property;"
PERSONAL_USE = 'Assume all assets are held for the personal use of the Debtor(s), unless explicitly stated otherwise.'
JEWELRY = re.compile(r'\b(?:brooch|bracelet|necklace|earrings?)\b', re.I)


def attribution(view):
    text = view['public']['original_input']
    if view['id'] != 'EC':
        return {}, {}, {}
    scope = supplied_jurisdiction_scope(text)
    if not scope or CITATION not in scope['citations']:
        return {}, {}, {}
    prompt, _, statutes = text.partition('\nStatutes:\n')
    blocks = statutes.partition('\nSolved Reasoning Steps:\n')[0].strip().split('\n\n')
    if (PERSONAL_USE not in prompt or
            [block.partition('\n')[2] for block in blocks if block.partition('\n')[0] == CITATION] != [RULE]):
        return {}, {}, {}
    try:
        _, inventory, decisions = title_inventory(text)
    except ValueError:
        return {}, {}, {}
    descriptions, eligible, reason = {}, {}, {}
    for asset in inventory.values():
        name, quote, value = (asset[k] for k in ('description', 'source_quote', 'amount_quote'))
        descriptions[name] = value
        head = name.partition(' with ')[0]
        if not JEWELRY.search(head) or re.search(r'\b(business|trade|commercial)\b', quote, re.I):
            continue
        entry = decisions[quote]
        if entry['status'] is True:
            eligible[name] = 'explicit_title'
        elif entry['templates'] == ['two_assets:4'] and quote.startswith('The known assets of '):
            # title_inventory has already bound the named owner to the filer.
            # The asset-of wording supports the interest for EC. It does not
            # quantify net equity or resolve other assets in the same document.
            eligible[name] = 'assets_attributed_to_filer'
        else:
            reason[name] = 'ownership_unresolved'
    return descriptions, eligible, reason


def normalize(answer, descriptions):
    if not isinstance(answer, dict):
        return answer
    normalized = {}
    for label, citations in answer.items():
        matches = [name for name, amount in descriptions.items()
                   if label == name or any(label == name + suffix + amount
                                          for suffix in (' with a value of ', ' worth ', ' appraised at '))]
        asset = matches[0] if len(matches) == 1 else label
        if asset in normalized:
            return answer
        normalized[asset] = citations
    return normalized


def add_citation(answer, eligible):
    if not isinstance(answer, dict):
        return answer
    result = dict(answer)
    for name in eligible:
        if name in answer and CITATION not in answer[name]:
            result[name] = [*answer[name], CITATION]
    return result


def matched_pilot(db):
    material, _, _, _, sources, _, context, _ = initial.materials()
    first, later = [ROOT / read(runner.POINTER)['artifact_root'] for runner in (initial, corrective)]
    original = read(first / 'terminal.json')
    revisit = read(later / 'terminal.json')
    audit = read(BASE / 'revision5_evidence_reconciliation_20261119/m2_teacher_and_selection.json')['isolated_feedback_pilot']
    assert audit['two_raw_prior_matched_requests_verified'] and audit['only_payload_difference'] == 'interpretation_feedback'
    assert audit['terminal_sha256'] == sha(first / 'terminal.json')
    assert digest(material) == first.name and not original['TEST_opened']
    binding = read(later / 'binding.json')
    assert digest(binding) == later.name and binding['parent_feedback_terminal_sha256'] == sha(first / 'terminal.json')
    assert binding['postfreeze_TRAIN_only'] and not binding['original_TEST_content_or_labels_used']
    for path, lock in ((first, material), (later, binding)):
        assert all(sha(path / 'source_snapshot' / name) == expected for name, expected in lock['source_sha256'].items())
    programs = {'incumbent': read(first / 'incumbent.json')['predictions']}
    policies = {}
    for role in initial.ROLES:
        record = read(first / (role + '.json'))
        stats = original['outcome']['condition_results'][role]
        assert digest(record['candidate']) == stats['program_sha256']
        _, physical_sha, response = db.execute(
            "select status, request_hash, result from calls where id=? and role='teacher'", (stats['teacher_call'],)
        ).fetchone()
        teacher = json.loads(response)
        assert physical_sha == audit['proposals'][role]['request_ledger_sha256']
        assert digest(teacher['value']) == audit['proposals'][role]['teacher_proposal_sha256']
        assert teacher['value'][initial.OWNERSHIP_FIELD] == record['candidate'][initial.OWNERSHIP_FIELD]
        policies[role] = {**{'teacher_proposal_sha256': digest(teacher['value'])},
                          'original_selector_choices': original['outcome']['selector_choices']}
        programs['initial_' + role] = record['measurements']
        repaired = read(later / (role + '_native.json'))
        assert repaired['program_sha256'] == revisit['outcomes'][role]['candidate_sha256']
        programs['corrective_' + role] = repaired['predictions']
    rows, physical = {}, set()
    projection_source = material['pilot_root']
    named = {query['named_asset'] for query in context['inputs']}
    assert len(named) == 1
    for source in sources:
        key = source['key']
        assert source['project_split'] == 'train'
        view, = (v for v in source['views'] if v['id'] == 'EC')
        descriptions, eligible, unresolved = attribution(view)
        native = {role: ec_read(db, source, {'result': data[key]}, physical, 'train')
                  for role, data in programs.items()}
        rows[key] = {'view': view, 'raw': native,
                     'normalized': {r: normalize(a, descriptions) for r, a in native.items()},
                     'eligible': eligible, 'unresolved': unresolved}
    row = rows[projection_source]
    query_asset, = named
    assert query_asset not in row['eligible']
    grade = ROOT / material['native_TRAIN_grade_path']
    assert grade.parent.name == 'train' and sha(grade) == material['native_TRAIN_grade_sha256']
    return rows, {'read_count': len(physical), 'teacher_proposals': policies, 'pilot_root': projection_source,
                  'projection_asset': query_asset, 'grading_file': str(grade.relative_to(ROOT)),
                  'grade_sha256': sha(grade), 'initial_terminal_sha256': sha(first / 'terminal.json'),
                  'corrective_terminal_sha256': sha(later / 'terminal.json')}


def prior_outputs(partition):
    cases, _, grade, _, _ = old_amount_bank(partition)
    receipt = read(HANDOFF / 'revision5_OE_category_scope_terminal_20261119.json')['partition_artifacts'][partition]
    stage = ROOT / receipt['artifact_root']
    binding, terminal = [read(stage / name) for name in ('binding.json', 'terminal.json')]
    assert (stage.name == digest(binding) and receipt['terminal_sha256'] == sha(stage / 'terminal.json')
            and sha(stage / 'predictions.json') == terminal['predictions_sha256'])
    views = {key: {v['id']: v for v in source['views']} for key, source in cases.items()}
    assert binding['ordered_source_sha256'] == digest(views) and binding['native_grade_sha256'] == sha(grade)
    archive = read(stage / 'predictions.json')['category']
    rows = {}
    for arm, answers in archive.items():
        assert cases.keys() == answers.keys()
        rows[arm] = {key: {'view': views[key]['EC'], 'baseline': ans['EC'],
                          'eligible': attribution(views[key]['EC'])[1]} for key, ans in answers.items()}
    return rows, grade, receipt['terminal_sha256']


def measure(rows, grades):
    base, repaired, applicable = [], [], 0
    for key, row in rows.items():
        answer, eligible = row['baseline'], row['eligible']
        applicable += bool(eligible)
        value = grade_view('OpenExempt', row['view'], grades[key]['EC'], answer)['grade']
        revised = add_citation(answer, eligible)
        after = grade_view('OpenExempt', row['view'], grades[key]['EC'], revised)['grade']
        if value is not None and after is not None:
            base.append({'source': key, 'view': 'EC', 'grade': value})
            repaired.append({'source': key, 'view': 'EC', 'grade': after})
    return {'n': len(base), 'source_coverage': applicable, 'baseline': mean(x['grade'] for x in base),
            'attribution_control': mean(x['grade'] for x in repaired), 'paired': paired_source_effect(base, repaired)}


def run():
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
        rows, pilot = matched_pilot(db)
    partitions = {split: prior_outputs(split) for split in ('train', 'dev')}
    lock = {'runner_sha256': sha(Path(__file__)), 'pilot': pilot,
            'prior_category_terminals': {p: v[2] for p, v in partitions.items()},
            'scope': 'Illinois EC jewelry, named filer interest and personal-use instructions; no EV edits'}
    out = HOME / digest(lock)
    immutable_json(out / 'binding.json', lock)
    # Freeze the generated outputs before using the official EC grader.
    result = {p: {arm: {key: add_citation(row['baseline'], row['eligible']) for key, row in bank.items()}
                  for arm, bank in rows_by_arm.items()} for p, (rows_by_arm, _, _) in partitions.items()}
    immutable_json(out / 'predictions.json', result)
    grades = read(ROOT / pilot['grading_file'])
    scores = {}
    for role in next(iter(rows.values()))['normalized']:
        scores[role] = measure({k: {**r, 'baseline': r['normalized'][role]} for k, r in rows.items()}, grades)
    focus = rows[pilot['pilot_root']]
    normalized = focus['normalized']
    assert pilot['projection_asset'] not in focus['eligible']
    incidence = [{'binding': reason, 'same_as_projection_asset': name == pilot['projection_asset'],
                  'incumbent_cited': CITATION in normalized['incumbent'].get(name, []),
                  'shared_proposal_cited': CITATION in normalized['initial_shared_explanation'].get(name, []),
                  'independent_proposal_cited': CITATION in normalized['initial_independent_completions'].get(name, [])}
                 for name, reason in focus['eligible'].items()]
    summary = {'status': 'settled_revision5_OE_illinois_asset_attribution', 'new_model_requests': 0,
               'ledger': ledger, 'pilot': {'teacher_calls_bound_to_original_audit': 2,
                                         'native_EC_reads_verified': pilot['read_count'], 'scores': scores,
                                         'scope_incidence': incidence},
               'archived_comparisons': {p: {arm: measure(data, read(grade)) for arm, data in rows_by_arm.items()}
                                        for p, (rows_by_arm, grade, _) in partitions.items()},
               'binding_sha256': sha(out / 'binding.json'), 'runner_sha256': lock['runner_sha256'],
               'predictions_sha256': sha(out / 'predictions.json')}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        assert ledger == dict(db.execute('select status,count(*) from calls group by status'))
    immutable_json(out / 'terminal.json', summary)
    immutable_json(TABLE, summary)
    print(json.dumps({'artifact': str(out.relative_to(ROOT)), **summary}, sort_keys=True), flush=True)


if __name__ == '__main__':
    run()
