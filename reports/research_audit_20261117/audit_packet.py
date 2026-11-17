"""Read-only audit of the published TRAIN evidence. No model calls or relabelling."""
import gzip
import hashlib
import json
import sys
from pathlib import Path

EXPECTED = '303cbf4e990f4de0ec82367a3b76b0c13a57d8308cc6dafb9ba591709a82b5e9'

def audit(path):
    payload = Path(path).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == EXPECTED
    data = json.loads(gzip.decompress(payload))
    rows = []
    for c in data['cases']:
        original = '\n'.join(v['public']['original_input'] for v in c['native_views'].values())
        sent = '\n'.join(m['content'] for m in c['request']['messages'])
        rows.append({
            'source': c['source']['key'], 'view': c['view_id'], 'plan': c['plan']['name'],
            'original_has_joint_ownership_default': 'assume all assets mentioned are jointly owned' in original.lower(),
            'reader_has_joint_ownership_default_literal': 'assume all assets mentioned are jointly owned' in sent.lower(),
            'original_has_personal_use_default': 'assume all assets are held for the personal use' in original.lower(),
            'reader_has_personal_use_default_literal': 'assume all assets are held for the personal use' in sent.lower(),
            'reference_public_context': c['source_card'].get('public_task_context', {}),
        })
    scores = data['native_scores']['calibration_diagnostic']
    selected = data['terminal']['selection']
    arms = {}
    for arm, candidate in selected.items():
        sr = [r for r in scores if r['candidate'] == candidate]
        arms[arm] = {'candidate': candidate, 'rows': len(sr),
                     'mean_grade': sum(r['grade'] for r in sr)/len(sr),
                     'exact_correct': sum(bool(r['metrics'].get('correct')) for r in sr)}
    return {
        'evidence_sha256': EXPECTED, 'cases': len(rows),
        'mother_sources': len({r['source'] for r in rows}),
        'joint_default_literal_missing': sum(r['original_has_joint_ownership_default'] and not r['reader_has_joint_ownership_default_literal'] for r in rows),
        'personal_use_default_literal_missing': sum(r['original_has_personal_use_default'] and not r['reader_has_personal_use_default_literal'] for r in rows),
        'arms_from_persisted_scores': arms, 'case_inventory': rows,
        'scope': 'Literal request/context audit and stored-score arithmetic, NOT independent native replay or truth relabelling',
        'research_model_calls': 0,
    }

if __name__ == '__main__':
    print(json.dumps(audit(sys.argv[1]), ensure_ascii=False, indent=2))
