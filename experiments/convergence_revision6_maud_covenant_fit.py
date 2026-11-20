"""Fit a full native MAUD covenant reader from indexed exception attachments."""

import argparse
from collections import Counter
import fcntl
from functools import lru_cache
import inspect
import json
from pathlib import Path
import re
import sqlite3

import jsonschema

from experiments import convergence_revision5_maud_adoption_scope as previous
from experiments import convergence_revision5_maud_section_scope as section
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import maud_scope_relational as scope, residual
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision6_maud_covenant_fit'
POINTER = HANDOFF / 'revision6_maud_covenant_fit_current.json'
MAUD = previous.MAUD
TASKS = {'ordinary': previous.ORDINARY_COVENANT, 'negative': previous.NEGATIVE}
FAMILIES = {'ordinary': 'governs_ordinary_course', 'negative': 'governs_negative_interim'}
ROLES = ('synthesized', 'fixed', 'direct')
CUE = re.compile(r'\b(?:COVID(?:\s*[-‐–]?\s*19)?|pandemic|coronavirus|SARS[- ]CoV[- ]2)\b', re.I)
TRIGGER_NAME = 'is_pandemic_condition'
GUIDANCE = (
    'Read both original source excerpts and their covenant questions. Focus markers point to literal source text; '
    'a marker itself does not assert an exception or its scope. Identify actions, restrictions and exceptions for '
    'the Company, not a different party. Treat the ordinary-course affirmative duty and the enumerated '
    'negative interim restrictions as distinct. Bind the exception to its own governing text. A common preamble '
    'or an express import can govern both. A separately numbered exception often governs only its own subclause. '
    'Clauses expressly incorporated by number govern only the stated recipients or duties. A pandemic mention '
    'in a definition, a reporting requirement, a different obligation or a mere reference is not an exception. '
    'A condition expressly permitting a pandemic response, or expressly permitting actions to implement named '
    'pandemic measures, can qualify; a generic reference to compliance with law does not by itself establish '
    'a pandemic exception. Distinguish text shown from text omitted. Do not assume the scope of an omitted '
    'provision or transfer a condition between unrelated clauses. For Yes, identify the focus marker in the '
    'operative exception. Use No only after checking that no shown marker governs that task, and null when '
    'the attachment or the coverage of task-relevant markers cannot be resolved.'
)


@lru_cache(maxsize=1)
def layouts():
    module = scope.module()
    fixed, synthesized, *_ = scope.candidate_assets()
    # Use descriptive names in the wire while retaining each generated projection.
    rows = []
    for feature in synthesized['features']:
        decoded_values = [residual.encode([feature], s)[feature['name']] for s in module.states]
        field, = (name for name in scope.PROJECTIONS
                  if decoded_values == [scope.local_consumer(s, {})[name] for s in module.states])
        rows.append({**feature, 'name': field})
    asset = residual.compile_pair(module, rows, operation=synthesized['operation'], layout='anchored')
    for state in module.states:
        for candidate in (fixed, asset):
            encoded = residual.encode(candidate['features'], state)
            decoded = residual.decode(candidate, encoded, {}, module_binding=module.binding)
            if not decoded['valid'] or decoded['outputs'] != scope.local_consumer(state, {}):
                raise ValueError('Renamed relations must preserve all partial covenants and triggers')
    return module, {'fixed': fixed, 'synthesized': asset}


def group(source, position):
    views = {task: next(v for v in source['views'] if v['id'] == task) for task in TASKS.values()}
    excerpt_ids, texts, marked = {}, {}, {}
    for family, task in TASKS.items():
        text = views[task]['public']['source_text']
        idx = next((key for key, value in texts.items() if value == text), None)
        if idx is None:
            idx = f'excerpt_{len(texts) + 1}'
            texts[idx] = text
            for match in CUE.finditer(text):
                start, end = match.span()
                marked[f'focus_{len(marked) + 1}'] = {
                    'excerpt': idx, 'range': [start, end], 'cue': match[0],
                    'context': text[max(0, start - 105):min(len(text), end + 105)],
                }
        excerpt_ids[family] = idx
    if not marked:
        return None
    return {'source': source['key'], 'position': position, 'views': views, 'public': {
        'original_excerpts': texts, 'focus_markers': marked, 'task_excerpts': excerpt_ids,
        'questions': TASKS,
    }}


def query(case, role):
    markers = tuple(case['public']['focus_markers'])
    if role == 'direct':
        answer_record = record_schema({'answer': {'enum': ['Yes', 'No', None]},
                                       'focus': {'enum': [*markers, None]}})
        schema = record_schema({'answers': record_schema(dict.fromkeys(TASKS, answer_record))})
        instruction = (
            'Give the native answer for each question and its decisive focus marker if the answer is Yes. '
            'Use a null focus for No and unresolved answers.'
        )
    else:
        layout = layouts()[1][role]
        observation = record_schema({field['name']: {'enum': layout['domains'][field['name']]}
                                     for field in layout['features']})
        schema = record_schema({
            'observations': record_schema(dict.fromkeys(markers, observation)),
            'checked_coverage': record_schema(dict.fromkeys(TASKS, {'type': 'boolean'})),
        })
        fields = '\n'.join(residual.reader_prompt(layout, verbalize_relations=True).splitlines()[4:])
        instruction = (
            'Provide one local observation per focus marker. Mark task coverage true only when all relevant '
            'markers and associated portions have been checked. A cue with no operative attachment can '
            'yield a negative local relation even if the text contains the word COVID. For the local '
            'trigger field, interpret pandemic as the condition of an operative exception, including '
            'implementation of named pandemic measures. Return pandemic for a categorical field or true for '
            'a Boolean field in that case. Otherwise use the actual condition type, false for a Boolean, '
            'or null if unread. Use null for unresolved scope. Read the local fields:\n'
            + fields
        )
    return ([{'role': 'system', 'content': GUIDANCE + '\n' + instruction},
             {'role': 'user', 'content': json.dumps(case['public'], ensure_ascii=False, sort_keys=True)}], schema)


def consume(observations, checked):
    answers = {}
    for family, relation in FAMILIES.items():
        yes, unknown = [], False
        for marker, readout in observations.items():
            condition = readout[TRIGGER_NAME]
            attachment = readout[relation]
            if condition is True and attachment is True:
                yes.append(marker)
            elif condition is not False and attachment is not False:
                unknown = True
        answers[family] = {'answer': 'Yes' if yes else 'No' if checked[family] and not unknown else None,
                           'focus': yes[0] if yes else None}
    return answers


def decode(schema, role, raw):
    missing = {family: {'answer': None, 'focus': None} for family in TASKS}
    if raw['finish_reason'] != 'stop':
        return missing, raw['finish_reason']
    try:
        wire = json.loads(raw['content'])
        jsonschema.validate(wire, schema)
    except (ValueError, jsonschema.ValidationError):
        return missing, 'invalid_transport'
    if role == 'direct':
        return {k: v if (v['answer'] == 'Yes') == bool(v['focus']) else missing[k]
                for k, v in wire['answers'].items()}, None
    module, assets = layouts()
    asset = assets[role]
    projections = {}
    unread = dict.fromkeys(scope.PROJECTIONS)
    for marker, values in wire['observations'].items():
        row = residual.decode(asset, values, {}, module_binding=module.binding)
        projections[marker] = row['outputs'] if row['valid'] else unread
    return consume(projections, wire['checked_coverage']), None


def materials():
    _, study, roster = previous.archive_context()
    cases, archives, grade_refs = {}, [], set()
    for b, batch in enumerate(roster[:4], 1):
        stage, config, seal = section.bound_stage(section.FIRST if b == 1 else section.observe_pointer(b))
        archives.append(sha(stage / 'terminal.json'))
        name = config['native_grade_paths'][MAUD]
        grade_refs.add((name, config['native_grade_sha256'][name]))
        for i, source in enumerate(s for s in batch if s['dataset'] == MAUD):
            if source['project_split'] != 'train':
                raise ValueError('The native interface choice uses only original TRAIN')
            grouped = group(source, [b, i])
            if grouped is not None:
                cases[source['key']] = grouped
    (name, expected), = grade_refs
    grade = ROOT / name
    if len(cases) < 8 or 'train' not in grade.parts or sha(grade) != expected:
        raise ValueError('Require source-defined cohort and byte-exact original TRAIN labels')
    return study['executor'], cases, archives, grade


def score(cases, outputs, labels):
    per_arm, per_task = {}, {}
    for arm, output in outputs.items():
        rows = per_arm[arm] = []
        sub = per_task[arm] = {}
        for family, task in TASKS.items():
            for key, predictions in output.items():
                view = cases[key]['views'][task]
                value = predictions[family]['answer']
                metric = grade_view(MAUD, view, labels[key][task], value)
                rows.append({'source': key, 'view': task, 'grade': metric['grade']})
            values = [x[family]['answer'] for x in output.values()]
            sub[family] = {'correct': sum(r['grade'] for r in rows if r['view'] == task),
                           'answered': sum(v is not None for v in values),
                           'native_labels': dict(Counter(labels[k][task]['answer'] for k in output)),
                           'predicted_shares': dict(Counter(str(v) for v in values))}
    effects = {arm: paired_source_effect(per_arm[arm], per_arm['synthesized']) for arm in ROLES[1:]}
    return per_task, effects


def snapshot(out, sources):
    for name, sha256 in sources.items():
        path = out / 'source_snapshot' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open('xb') as handle:
                handle.write((ROOT / name).read_bytes())
        if sha(path) != sha256 or sha(ROOT / name) != sha256:
            raise ValueError('The archived candidate or original control implementation changed')


def run(execute=False):
    config, cases, archives, grade = materials()
    prompts = {key: {role: query(case, role) for role in ROLES} for key, case in cases.items()}
    if any(len({prompt[0][1]['content'] for prompt in by_role.values()}) != 1 for by_role in prompts.values()):
        raise ValueError('Keep the full common original input and focus inventory in every arm')
    files = {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in (
        __file__, scope.__file__, residual.__file__, inspect.getfile(grade_view),
        inspect.getfile(FrozenExecutor), inspect.getfile(EvolutionLedger), inspect.getfile(verify_physical_response),
    )}
    spec = {'stage': 'revision6_maud_covenant_fit', 'partition': 'TRAIN', 'TEST_opened': False,
            'executor': config, 'TRAIN_observe_terminals': archives, 'TRAIN_grade_sha256': sha(grade),
            'cohort': [case['position'] for case in cases.values()], 'common_public_sha256': digest(
                {k: c['public'] for k, c in cases.items()}), 'wire_sha256': digest(prompts), 'source_sha256': files,
            'reader_versions': {k: v['version'] for k, v in layouts()[1].items()},
            'advance_rule': 'Require a positive mother-paired lower 95% bound over both controls on the two native tasks before further deployment.',
            'cohort_rule': 'Every original TRAIN B1–B4 MAUD mother with any pandemic cue in either covenant excerpt.'}
    out = HOME / digest(spec)
    immutable_json(out / 'binding.json', spec)
    immutable_json(out / 'wire_tasks.json', prompts)
    snapshot(out, files)
    if (out / 'terminal.json').exists():
        print(out)
        return
    if not execute:
        write_status(out, {'status': 'prepared', 'physical_requests_planned': len(cases) * len(ROLES)}, POINTER)
        print(out)
        return
    if ROOT / read(POINTER)['artifact_root'] != out:
        raise ValueError('Prepare the original TRAIN cohort before execution')
    with (out / 'driver.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        measure(out, spec, cases, prompts, grade)


def measure(out, spec, cases, prompts, grade):
    ledger = EvolutionLedger(LEDGER, run_id='revision6-M1-maud-covenants-' + out.name[:12],
                             sources={'train': list(cases), 'dev': [], 'test': []}, binding=spec)
    executor = FrozenExecutor(ledger, out, spec['executor'])
    executor.readiness()
    max_context = spec['executor']['context_tokens'] - spec['executor']['max_tokens']
    for by_role in prompts.values():
        for messages, _ in by_role.values():
            if executor.tokenize(messages, thinking=False)['count'] > max_context:
                raise ValueError('Original public inputs must fit without truncation')
    bank = {role: {} for role in ROLES}
    usage, errors = Counter(), Counter()
    for i, key in enumerate(cases):
        for role in ROLES[i % len(ROLES):] + ROLES[:i % len(ROLES)]:
            identity = f'{ledger.run_id}:{digest(key)}:{role}'
            status = {'status': 'running', 'completed_mothers': i, 'current_request': identity}
            write_status(out, status, POINTER)
            messages, schema = prompts[key][role]
            try:
                raw = executor.generate(identity, source=key, purpose='skill_actor', thinking=False,
                                        messages=messages, schema=schema)
                verify_physical_response(executor, identity=identity, source=key, purpose='skill_actor',
                    content_sha256=digest(raw['content']), usage=raw['usage'], finish_reason=raw['finish_reason'])
                parsed, error = decode(schema, role, raw)
                bank[role][key] = parsed
                usage[role] += raw['usage']['total_tokens']
                errors[role] += error is not None
                immutable_json(out / 'responses' / (digest(identity) + '.json'),
                               {'call_id': identity, 'error': error, 'native': parsed})
            except Exception:
                write_status(out, {**status, 'status': 'interrupted'}, POINTER)
                raise
    pred = immutable_json(out / 'sealed_predictions.json', bank)
    if sha(grade) != spec['TRAIN_grade_sha256']:
        raise ValueError('Score only with the original TRAIN references after prediction seal')
    scores, effects = score(cases, bank, read(grade))
    # The lower bound is for exploratory comparison of both matched controls.
    # Any qualified choice would still need an unselected forward comparison.
    passed = all(values['paired_source_bootstrap_95'][0] > 0 for values in effects.values())
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        current = dict(db.execute('select status,count(*) from calls where id like ? group by status',
                                   (ledger.run_id + ':%',)))
        totals = dict(db.execute('select status,count(*) from calls group by status'))
    if current != {'completed': len(cases) * len(ROLES)} or totals.get('reserved'):
        raise ValueError('Every matched original TRAIN request must settle in the continuous ledger')
    result = sealed({'status': 'settled_revision6_maud_covenant_fit', 'binding_sha256': out.name,
                     'cohort_size': len(cases), 'scores': scores, 'effects': effects, 'proceed': passed,
                     'tokens': dict(usage), 'wire_errors': dict(errors), 'predictions_sha256': pred,
                     'new_executor_requests': current['completed'], 'new_teacher_requests': 0,
                     'TEST_opened': False, 'ledger': totals}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'terminal_sha256': result['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase == 'run')
