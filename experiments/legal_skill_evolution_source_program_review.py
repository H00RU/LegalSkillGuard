"""Zero-call mechanism interventions on actual acquired source programs.

Shared-operation interventions are execution controls, not new independent
acquisitions. No native label or manually supplied field enters a program.
"""
import json
from pathlib import Path

from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.relational_compiler import spans_for, bind_records, apply
from legal_skill_guard.skill_evolution.span_compiler import execute_json
from experiments.legal_skill_evolution_span_compiler import warm_base


def run(root):
    folder = root / 'artifacts/legal_skill_evolution_source_program_acquisition_20261113'
    read = lambda p: json.loads(p.read_text())
    protocol = read(folder / 'protocol.json')
    public = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    spec = read(folder / 'frozen_specs.json')['ScopedAcquisition']
    candidate = read(folder / 'LearnedSourceCompiler/teacher.json')['value']['source_program']
    free = read(folder / 'IndependentWholeProgram/teacher.json')['value']['source_program']
    suffix = ', "the l.e.k.", "or to the l.e.k."'
    assert candidate.count(suffix) == 1
    no_names = candidate.replace(suffix, '')
    local = 'recipient_text = exception_text if negative and bounded else text'
    call = 'recipient_text if negative and bounded else ""'
    assert candidate.count(local) == 1 and candidate.count(call) == 1
    no_scope = candidate.replace(local, 'recipient_text = text').replace(call, '""')
    anchor = '                classes = _roles(text)'
    assert free.count(anchor) == 1
    shared_scope = free.replace(anchor,
        '                classes = _roles(_after(text) if prohibited and _after(text) else text)')
    variants = {'candidate_original': candidate, 'candidate_no_company_suffix': no_names,
        'candidate_without_exception_local_binding': no_scope,
        'free_original': free, 'free_shared_simple_exception_binding': shared_scope}
    old = read(root / 'artifacts/legal_skill_evolution_span_compiler_20261112/protocol.json')
    base = warm_base(root, old)
    results = {}
    for name, code in variants.items():
        rows = []
        for key in protocol['teacher_sources'] + protocol['fixed_TRAIN_reuse_sources']:
            source = public[key];spans = spans_for(source)
            raw = execute_json(code, {'source_text': source['views'][0]['public']['source_text'],
                'source_spans': spans}, {}, allow_helpers=True)
            records = bind_records(spec, spans, raw)
            views = []
            inherited = {v['view']: v for v in base[key]['views']}
            for view in source['views']:
                value = apply(spec, source, view, records) if view['id'] in ('nda-5', 'nda-7') else None
                core = value is not None and value['handled']
                answer = value['answer'] if core else inherited[view['id']]['execution']['answer']
                score = grade_view(source['dataset'], view, grading[key][view['id']], answer) if core else inherited[view['id']]['score']
                views.append({'task': view['id'], 'answer': answer, 'core': core, 'native_correct': score['correct'],
                    'grade': score['grade'], 'execution': value})
            rows.append({'source': key, 'raw_source_program_output': raw, 'views': views})
        scores = {r['source']: sum(v['grade'] for v in r['views']) / len(r['views']) for r in rows}
        results[name] = {'core_views': sum(v['core'] for r in rows for v in r['views']),
            'core_native_correct': sum(v['core'] and v['native_correct'] for r in rows for v in r['views']),
            'mean_native_grade': sum(scores.values()) / len(scores),
            'strict_original_trigger_gain': sum(scores[k] - base[k]['native_grade'] for k in old['trigger']) / len(old['trigger']),
            'original_history_nonregression': all(scores[k] >= base[k]['native_grade'] for k in old['history']), 'rows': rows}
    assert results['candidate_original']['rows'] == results['candidate_no_company_suffix']['rows']
    for name, arm in [('candidate_original', 'LearnedSourceCompiler'), ('free_original', 'IndependentWholeProgram')]:
        originals = {r['source']: r for r in read(folder / 'completed.json')['results'][arm]}
        for row in results[name]['rows']:
            original = originals[row['source']]
            assert row['raw_source_program_output'] == original['raw_program_output']
            assert [v['answer'] for v in row['views']] == [v['answer'] for v in original['views']]
    result = {'new_model_calls': 0, 'native_labels_used_only_for_scoring': True,
        'original_teacher_outputs_unchanged': True, 'variants': results,
        'shared_simple_control_is_not_independent_acquisition': True,
        'company_suffix_removal_changes_no_current_raw_record_or_answer': True,
        'semantic_validation_not_proven_by_native_scores': True, 'goal_complete': False}
    target = folder / 'postrun_audit/mechanism_interventions.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists(): raise ValueError('Preserve prior interventions')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


if __name__ == '__main__':
    result = run(Path(__file__).resolve().parents[1])
    print(json.dumps({k: {n: v for n, v in row.items() if n != 'rows'}
        for k, row in result['variants'].items()}, ensure_ascii=False))
