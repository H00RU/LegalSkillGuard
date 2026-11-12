"""Audit actual used records and native TRAIN evidence without changing answers."""
import json
from pathlib import Path

from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.relational_compiler import spans_for
from legal_skill_guard.skill_evolution.span_compiler import execute


def run(root):
    folder = root / 'artifacts/legal_skill_evolution_relational_acquisition_v2_20261113'
    read = lambda p: json.loads(p.read_text())
    completed = read(folder / 'completed.json')
    public = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    old = read(folder / 'shared_prior_asset.json')['spec']
    entries = []
    for arm, rows in completed['results'].items():
        spec = old if arm == 'NoExamplesSameP' else read(folder / arm / 'frozen_candidate.json')['spec']
        for row in rows:
            source = public[row['source']]
            views = {v['id']: v for v in source['views']}
            source_spans = spans_for(source)
            for result in row['views']:
                if not result['core_executed']:
                    continue
                used = result['execution']['used_records']
                assert used and len(set(used)) == len(used)
                assert all(type(i) is int and 0 <= i < len(row['records']) for i in used)
                records = [row['records'][i] for i in used]
                # Existing record provenance is mapped back to native sentence indices.
                proof_spans = []
                for record in records:
                    if arm == 'NoExamplesSameP':
                        start, end = record['span']
                        proof_spans.extend(s for s in source_spans if s['start'] < end and start < s['end'])
                    else:
                        proof_spans.extend(record['source_evidence'])
                evidence = sorted({s['public_sentence_id'] for s in proof_spans if 'public_sentence_id' in s})
                score = grade_view('ContractNLI', views[result['view']],
                    grading[row['source']][result['view']], result['answer'], evidence)
                assert {k: v for k, v in score.items() if k != 'evidence_f1'} == {
                    k: v for k, v in result['score'].items() if k != 'evidence_f1'}
                error = None
                try:
                    replay = execute(spec['procedure'], {'task_id': result['view'],
                        'question': views[result['view']]['public']['question']}, {'records': records})
                except (ValueError, KeyError, TypeError) as exc:
                    replay = None
                    error = type(exc).__name__ + ': ' + str(exc)
                sufficient = replay is not None and replay['handled'] and replay['answer'] == result['answer']
                entries.append({'arm': arm, 'source': row['source'], 'task': result['view'],
                    'original_answer': result['answer'], 'native_correct': score['correct'],
                    'used_records': used, 'predicted_evidence_sentence_ids': evidence,
                    'original_TRAIN_evidence_sentence_ids': grading[row['source']][result['view']]['evidence'],
                    'native_evidence_f1': score.get('evidence_f1'),
                    'reported_record_subset_reproduces_original_answer': sufficient,
                    'subset_execution_error': error,
                    'entire_record_or_legal_semantics_verified_by_this_test': False})
    assert len(entries) == 27
    summary = {arm: {'core_views': len(xs := [e for e in entries if e['arm'] == arm]),
        'native_correct': sum(e['native_correct'] for e in xs),
        'used_record_subset_sufficient': sum(e['reported_record_subset_reproduces_original_answer'] for e in xs),
        'evidence_scored_core_views': len(scored := [e for e in xs if e['native_evidence_f1'] is not None]),
        'mean_native_evidence_f1_on_evidence_scored_core_only': (
            sum(e['native_evidence_f1'] for e in scored) / len(scored) if scored else None),
        'native_correct_with_zero_gold_span_overlap': sum(e['native_correct'] and e['native_evidence_f1'] == 0 for e in xs)}
        for arm in completed['results']}
    result = {'new_model_calls': 0, 'split': 'original_TRAIN_only', 'original_answers_and_outputs_unchanged': True,
        'evidence_mapping': 'Union of public_sentence_id for actual used relation records. The example-removal control uses native sentence spans overlapping its actual bound quote offsets. No proof spans inferred from labels.',
        'limits': 'Gold evidence is not exhaustive semantic supervision of each extracted field. Span overlap and program-subset sufficiency do not establish faithful participant ownership, action or legal scope.',
        'summary': summary, 'entries': entries, 'goal_complete': False}
    target = folder / 'postrun_audit' / 'actual_used_proof_audit.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('Preserve the prior audit; do not overwrite it')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


if __name__ == '__main__':
    result = run(Path(__file__).resolve().parents[1])
    print(json.dumps(result['summary'], ensure_ascii=False))
