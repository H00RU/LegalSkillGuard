"""Use the preserved official-grading environment, isolated from inference deps."""
import json
import sys
from legal_skill_guard.rr.scoring import official_openexempt_metrics


if __name__ == '__main__':
    value = json.load(sys.stdin)
    json.dump(official_openexempt_metrics(value['family'], value['answer'], value['target']),
              sys.stdout, ensure_ascii=False, allow_nan=False)
