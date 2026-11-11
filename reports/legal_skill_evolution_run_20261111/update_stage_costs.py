"""Continuous measured requests/tokens/time, separated by fixed study stage."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


def main():
    root = Path(__file__).resolve().parents[2]
    out = {'captured_utc': datetime.now(timezone.utc).isoformat(),
           'GPU_and_teacher_cash_invoice_usd': None, 'executor_incremental_API_cash_usd': 0}
    with sqlite3.connect('file:' + str(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        for stage, prefix in [('first_pass', 'legal_skill_evolution_pilot_'),
                              ('repair', 'legal_skill_evolution_repair_'),
                              ('activation_TRAIN_diagnostic', 'legal_skill_evolution_activation_'),
                              ('formal', 'legal_skill_evolution_formal_'),
                              ('frozen_TEST_and_transfer', 'legal_skill_evolution_frozen_')]:
            result = {}
            for role in ('executor', 'teacher'):
                rows = db.execute('select status,result from calls where id like ? and role=?', (prefix + '%', role)).fetchall()
                usage, statuses = Counter(), Counter()
                for status, raw in rows:
                    statuses[status] += 1
                    value = json.loads(raw) if raw else {}
                    tokens = value.get('usage') or value.get('invocation', {}).get('usage') or {}
                    usage.update({k: x for k, x in tokens.items() if isinstance(x, (int, float))})
                    usage['elapsed_seconds'] += value.get('elapsed_seconds', 0)
                result[role] = {'physical_requests': len(rows), 'statuses': dict(statuses), 'usage': dict(usage)}
            out[stage] = result
    Path(__file__).with_name('stage_costs.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({stage: {r: out[stage][r]['physical_requests'] for r in ('executor', 'teacher')}
        for stage in ('first_pass', 'repair', 'activation_TRAIN_diagnostic', 'formal', 'frozen_TEST_and_transfer')}))


if __name__ == '__main__':main()
