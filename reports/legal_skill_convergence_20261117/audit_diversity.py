import concurrent.futures
import csv
import hashlib
import io
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data_audit'
OUT.mkdir(exist_ok=True)
HF = 'daec8237410aa23e3faf4bc41ad8b3a7e1696826'
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def get(url):
    with OP.open(url, timeout=30) as r:
        return r.read()

def parse(text):
    citizens = re.findall(r'(\w+) is from ([^.]+)\.', text)
    citizenship = dict(citizens)
    if len(citizens) != len(citizenship):
        raise ValueError('duplicate named citizen')
    claims = []
    for sentence in text.split('. '):
        if ' sue' not in sentence:
            continue
        match = re.search(r'^(.+?) (?:both sue|sues|sue) (.+?)(?: each)? for (.+)', sentence)
        if not match:
            raise ValueError('unrecognized claim sentence: ' + sentence)
        ps, ds, tail = match.groups()
        plaintiffs = ps.split(' and ')
        defendants = ds.split(' and ')
        amounts = [int(x.replace(',', '')) for x in re.findall(r'\$([\d,]+)', tail)]
        if not amounts:
            raise ValueError('no amount')
        for plaintiff in plaintiffs:
            for defendant in defendants:
                for amount in amounts:
                    claims.append((plaintiff, defendant, amount))
    if not claims:
        raise ValueError('no claims')
    plaintiffs = {p for p,d,a in claims}
    defendants = {d for p,d,a in claims}
    missing = (plaintiffs | defendants) - citizenship.keys()
    if missing:
        raise ValueError('missing citizenship: ' + repr(missing))
    totals = {}
    for p,d,a in claims:
        totals[p,d] = totals.get((p,d),0) + a
    diverse = all(citizenship[p] != citizenship[d] for p in plaintiffs for d in defendants)
    # Benchmark convention: every represented plaintiff-defendant pair passes.
    # This checks the released task convention, not general civil procedure.
    aic = all(a > 75000 for a in totals.values())
    return {'parties_are_diverse': diverse, 'aic_is_met': aic,
            'answer': 'Yes' if diverse and aic else 'No',
            'entities': len(citizenship), 'pair_count': len(totals),
            'claim_count': len(claims)}

def audit_variant(i):
    name = f'diversity_{i}'
    url = f'https://huggingface.co/datasets/nguha/legalbench/raw/{HF}/data/{name}/train.tsv'
    raw = get(url)
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), delimiter='\t'))
    results = []
    for row in rows[:4]:
        record = {'dataset': name, 'native_index': row['index'],
                  'source_text_sha256': hashlib.sha256(row['text'].encode()).hexdigest()}
        try:
            result = parse(row['text'])
            record['parse'] = result
            record['native_matches'] = {
                'answer': result['answer'].lower() == row['answer'].lower(),
                'parties_are_diverse': result['parties_are_diverse'] == (row['parties_are_diverse'].lower() == 'true'),
                'aic_is_met': result['aic_is_met'] == (row['aic_is_met'].lower() == 'true')}
        except Exception as e:
            record['error'] = str(e)
        results.append(record)
    return {'variant': name, 'url': url, 'file_sha256': hashlib.sha256(raw).hexdigest(),
            'official_train_rows': len(rows), 'design_train_indices': [x['index'] for x in rows[:4]],
            'selected_source_checks': results}

variants = list(concurrent.futures.ThreadPoolExecutor().map(audit_variant, range(1,7)))
records = [r for v in variants for r in v['selected_source_checks']]
size_url = 'https://datasets-server.huggingface.co/size?dataset=nguha%2Flegalbench'
size = json.loads(get(size_url))
stats = [x for x in size['size']['splits'] if x['config'].startswith('diversity_')]
report = {'date': '2026-11-18', 'dataset_revision': HF,
          'license': 'CC BY 4.0; cite LegalBench (Guha et al., 2023)',
          'model_calls': 0, 'official_test_content_or_labels_read': False,
          'metadata_rows_not_deduplicated_source_count': True,
          'purpose': 'TRAIN-only adapter feasibility audit; not M1/M2 performance evidence',
          'native_task_fields_are_scoring_only': ['answer','parties_are_diverse','aic_is_met'],
          'server_history_and_cross_variant_dedup_pending': True,
          'source_checks': len(records),
          'parsed': sum('parse' in r for r in records),
          'all_three_native_fields_match': sum(all(r.get('native_matches', {'failed':False}).values()) for r in records),
          'exact_text_duplicates_in_selected': len(records)-len({r['source_text_sha256'] for r in records}),
          'inventory_metadata_url': size_url, 'inventory_metadata': stats,
          'variants': variants,
          'extra_design_exposure': {'official_github_diversity_6_prompts': 'All six public examples in base/application prompts were inspected; exclude these and close variants from project TEST. Do not use prompt demonstrations outside the locked TRAIN set.'}}
(OUT / 'DIVERSITY_TRAIN_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ['variants','inventory_metadata']},ensure_ascii=False,indent=2))
for r in records:
    if 'error' in r or not all(r['native_matches'].values()):
        print(json.dumps(r,ensure_ascii=False))
