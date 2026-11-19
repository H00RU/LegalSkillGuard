"""Measure remaining reader fields after binding source-proved use/license clauses."""

from collections import Counter
from dataclasses import replace
from functools import lru_cache
from itertools import combinations
import json
from pathlib import Path
import sqlite3
from statistics import mean

from experiments.convergence_revision5_cni_clause_witness import paired, source_proofs
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.rr.checkpoint import immutable_json


HOME = paired.BASE / 'revision5_CNI_conditioned_use_license_20261119'
TABLE = paired.ROOT / 'reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_CONDITIONED_USE_LICENSE_20261119.json'
PREMISES = dict(zip(paired.TASKS, (tuple(paired.MEANINGS)[:2], tuple(paired.MEANINGS)[3:5]), strict=True))


def source_binding(source):
    view, = (v for v in source['views'] if v['id'] == paired.TASKS['purpose_scope'])
    forms = source_proofs(view)
    return {task: next(iter(groups.values())) for task, groups in forms.items() if len(groups) == 1}


@lru_cache(maxsize=8)
def specialize(tasks, *, preserve_status=True):
    original, assets = paired.layouts()
    known = {field for task in tasks for field in PREMISES[task]}
    compatible = [(state, runs) for state, runs in zip(original.states, original.outcomes, strict=True)
                  if all(state[field] is True for field in known)]
    outcomes = tuple(runs for _, runs in compatible)
    if not preserve_status:
        outcomes = tuple(tuple({**r, 'semantic_obligations': {}} for r in runs) for runs in outcomes)
    module = replace(original, states=tuple(s for s, _ in compatible), outcomes=outcomes,
                     protected_status_fields=original.protected_status_fields if preserve_status else ())
    compiled = {}
    for role, asset in assets.items():
        fields = asset['features']
        for width in range(len(fields) + 1):
            selected = next((f for f in combinations(fields, width) if residual.witness(module, f) is None), None)
            if selected is not None:
                break
        assert selected is not None
        candidate = (residual.compile_pair(module, list(selected), operation='source_conditioned_use_license', layout='anchored')
                     if selected else None)
        if candidate is not None:
            for state, output in zip(module.states, module.outcomes, strict=True):
                actual = residual.decode(candidate, residual.encode(selected, state), {}, module_binding=module.binding)
                assert actual == output[0]
        else:
            assert all(output == module.outcomes[0] for output in module.outcomes)
        compiled[role] = candidate
    return module, compiled


def overlay(original, proof):
    """Apply the same source-known conclusions to the direct and interface arms."""
    return {task: {'answer': paired.YES, 'evidence': list(proof[task])} if task in proof else row
            for task, row in original.items()}


def partitions(repertoire):
    results = {}
    for part in ('train', 'dev'):
        sources, original, grade, terminal = paired.collect(*repertoire, part)
        labels = paired.read(grade)
        proof = {key: source_binding(source) for key, source in sources.items()}
        shape = Counter(tuple(bound) for bound in proof.values())
        widths = {}
        for condition in (True, False):
            counts = Counter()
            for shape_key, n in shape.items():
                _, assets = specialize(shape_key, preserve_status=condition)
                for role, asset in assets.items():
                    counts[role] += n * (len(asset['features']) if asset is not None else 0)
            widths['full_receipt' if condition else 'native_outputs_only'] = dict(counts)
        covered = {key: value for key, value in proof.items() if value}
        arms = {}
        for arm, predictions in original.items():
            scores, pending = [], []
            for key, bound in covered.items():
                for kind, task in paired.TASKS.items():
                    view, = (v for v in sources[key]['views'] if v['id'] == task)
                    row = predictions[key]['native'][task]
                    reference = labels[key][task]
                    a = paired.grade_view(paired.DATASET, view, reference, row['answer'], row['evidence_sentence_ids'])
                    if kind in bound:
                        b = paired.grade_view(paired.DATASET, view, reference, paired.YES, bound[kind])
                        scores.append((a, b))
                    else:
                        pending.append(a)
            arms[arm] = {'source_known_tasks': len(scores),
                         'known_before_correct': sum(a['correct'] for a, _ in scores),
                         'known_after_correct': sum(b['correct'] for _, b in scores),
                         'known_before_evidence_f1': mean(a['evidence_f1'] for a, _ in scores),
                         'known_after_evidence_f1': mean(b['evidence_f1'] for _, b in scores),
                         'remaining_tasks': len(pending), 'remaining_correct': sum(x['correct'] for x in pending)}
        results[part] = {'mothers': len(sources), 'source_shapes': {'+'.join(k) or 'unconditioned': n for k, n in shape.items()},
                         'total_book_fields': widths, 'original_terminals': terminal, 'arms': arms}
    return results


def run():
    repertoire = paired.archive_context()
    binding, cases = paired.materials()
    stage = paired.ROOT / paired.read(paired.POINTER)['artifact_root']
    terminal = paired.read(stage / 'terminal.json')
    assert paired.digest(binding) == stage.name and terminal['status'] == paired.DONE
    assert all(paired.sha(stage / 'source_snapshot' / name) == sha for name, sha in binding['source_sha256'].items())
    assert terminal['predictions_sha256'] == paired.sha(stage / 'predictions.json')
    rows = paired.read(stage / 'predictions.json')
    scores = {r: {'before': [], 'after': []} for r in paired.ROLES}
    labels = paired.read(paired.ROOT / binding['grade_path'])
    with sqlite3.connect(paired.LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
        for case, pair in zip(cases, rows, strict=True):
            proof = source_binding({'views': list(case['views'].values())})
            model, assets = specialize(tuple(proof))
            for role, cell in pair.items():
                raw, wire = paired.response(db, case['source'], cell['id'])
                messages, schema = paired.contract(case, role)
                assert wire == paired.request_payload(binding['executor'], messages=messages, thinking=False, schema=schema)
                assert paired.decode(case, role, raw) == (cell['decoded'], cell['error'])
                corrected = overlay(cell['decoded'], proof)
                if role in assets:
                    relations = json.loads(raw['content'])['relations']
                    asset = assets[role]
                    projected = {f['name']: relations[f['name']] for f in asset['features']}
                    decoded = residual.decode(asset, projected, {}, module_binding=model.binding)
                    assert decoded['valid'] and decoded['outputs'] == {k: v['answer'] for k, v in corrected.items()}
                scores[role]['before'].extend(paired.measure(case, cell['decoded'], labels).values())
                scores[role]['after'].extend(paired.measure(case, corrected, labels).values())
        assert ledger == dict(db.execute('select status,count(*) from calls group by status'))
    result = {'status': 'settled_revision5_CNI_conditioned_use_license', 'new_model_requests': 0, 'ledger': ledger,
              'original_pilot_terminal_sha256': paired.sha(stage / 'terminal.json'), 'pilot_physical_reads': 18,
              'archived': partitions(repertoire), 'runner_sha256': paired.sha(Path(__file__)),
              'pilot': {role: {phase: {'exact': sum(x['exact'] for x in values),
                                      'evidence_f1': mean(x['evidence_f1'] for x in values)}
                               for phase, values in pair.items()} for role, pair in scores.items()}}
    immutable_json(HOME / 'terminal.json', result)
    immutable_json(TABLE, result)
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    run()
