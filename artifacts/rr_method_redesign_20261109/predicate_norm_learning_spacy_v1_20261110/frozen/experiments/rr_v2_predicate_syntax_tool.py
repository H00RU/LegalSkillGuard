"""Fixed public CPU dependency preprocessing, with its own inference receipt.

Run in the isolated spaCy environment. This trained NLP component is not the
executor/teacher LLM and is not a normative rule learner. Every control may use
the same exact token/dependency data. No task labels are read or generated.
"""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import sys
import time


def main():
    seal = Path(sys.argv[1]);output = Path(sys.argv[2])
    data = json.loads(seal.read_text())
    units = [{k: u[k] for k in ['key', 'source', 'text', 'focus']} for u in data['units']]
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    wheel_sha = '1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85'
    request = {'units': units, 'script_sha256': script_sha, 'model_wheel_sha256': wheel_sha,
               'model': 'en_core_web_sm', 'model_version': '3.8.0', 'device': 'cpu', 'disabled': ['ner']}
    request_hash = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    if output.exists():
        assert json.loads(output.read_text())['request_hash'] == request_hash
        print(json.dumps({'exact_cache_reused': True, 'new_NLP_model_inferences': 0}));return
    import spacy
    assert importlib.metadata.version('en-core-web-sm') == '3.8.0'
    spacy.require_cpu();start = time.monotonic()
    nlp = spacy.load('en_core_web_sm', disable=['ner']);load_seconds = time.monotonic() - start
    parsed = []
    for u in units:
        start = time.monotonic();doc = nlp(u['text']);seconds = time.monotonic() - start
        tokens = [{'i': t.i, 'text': t.text, 'lemma': t.lemma_, 'pos': t.pos_, 'tag': t.tag_,
                   'dep': t.dep_, 'head': t.head.i, 'start': t.idx, 'end': t.idx + len(t),
                   'morph': str(t.morph)} for t in doc]
        assert all(u['text'][t['start']:t['end']] == t['text'] for t in tokens)
        parsed.append({**u, 'tokens': tokens,
            'noun_chunks': [{'start': c.start, 'end': c.end, 'root': c.root.i,
                             'start_char': c.start_char, 'end_char': c.end_char, 'text': c.text} for c in doc.noun_chunks],
            'sentences': [{'start': s.start, 'end': s.end, 'start_char': s.start_char,
                           'end_char': s.end_char, 'text': s.text} for s in doc.sents],
            'elapsed_cpu_pipeline_wall_seconds': seconds, 'normative_labels_supplied': False})
    value = {'request_hash': request_hash, 'request': request, 'results': parsed,
             'spacy_version': spacy.__version__, 'model_load_seconds': load_seconds,
             'NLP_model_inferences': len(units), 'executor_or_teacher_generations': 0,
             'incremental_API_cash_usd': 0, 'CPU_allocation_cost_usd': None,
             'trained_syntax_component_not_deterministic_legal_oracle': True,
             'package_versions': sorted({(d.metadata['Name'], d.version) for d in importlib.metadata.distributions()})}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True))
    frozen = output.parent / 'frozen' / 'experiments' / Path(__file__).name
    frozen.parent.mkdir(parents=True, exist_ok=True);frozen.write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'saved': str(output), 'NLP_model_inferences': len(units),
                      'executor_or_teacher_generations': 0, 'spacy': spacy.__version__,
                      'total_parse_seconds': sum(r['elapsed_cpu_pipeline_wall_seconds'] for r in parsed)}), flush=True)


if __name__ == '__main__':
    main()
