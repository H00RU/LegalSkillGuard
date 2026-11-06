"""Recompute the preserved76-source prefix without generation or new views."""
import ast
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parent))
from audit_build import mechanism_check, sql_state
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.engine import analyze
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.preflight import science_files


def read(path):return json.loads(Path(path).read_text())


def main():
    run = ROOT/'artifacts/rr_v2_formal_build_20261106/run_citation_fix'
    preserved = ROOT/'artifacts/rr_v2_formal_build_20261106/preserved_before_sara_query_fix'
    old_state = read(preserved/'run/state.json')
    assert old_state['complete_sources'] == 76
    cfg = read(ROOT/'configs/rr_v2_preflight.json')
    order = read(ROOT/cfg['source_manifest'])['formal_train_order'][:76]
    public = {s['key']:s for s in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
    grades = read(ROOT/'data/packets/rr_v2/grading_only/train.json')['sources']
    path = ROOT/cfg['ledger_path']
    before = sql_state(path)
    assert before == sql_state(preserved/'ledger.sqlite3')
    old_source = preserved/'source/legal_skill_guard/rr/source_learning.py'
    new_source = ROOT/'legal_skill_guard/rr/source_learning.py'
    def other_nodes(path):
        return [ast.dump(n) for n in ast.parse(path.read_text()).body
                if not isinstance(n, ast.FunctionDef) or n.name != 'sara_case']
    assert other_nodes(old_source) == other_nodes(new_source)
    old_func = next(n for n in ast.parse(old_source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name == 'sara_case')
    new_func = next(n for n in ast.parse(new_source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name == 'sara_case')
    assert [ast.dump(n) for n in old_func.body[:4]] == [ast.dump(n) for n in new_func.body[:4]]
    assert ast.dump(old_func.body[-1]) == ast.dump(new_func.body[-1])
    def deny(*args, **kwargs):raise RuntimeError('Prefix audit cannot use network/models/subprocesses')
    library, rows = SkillLibrary(stage='formal_train'), []
    with patch.object(socket.socket,'connect',deny), patch.object(socket.socket,'connect_ex',deny), \
            patch.object(subprocess,'run',deny), patch.object(subprocess,'Popen',deny):
        for sid in order:
            record = read(run/'sources'/(digest(sid)+'.json'))
            assert (run/'sources'/(digest(sid)+'.json')).read_bytes() == (preserved/'run/sources'/(digest(sid)+'.json')).read_bytes()
            assert record['library_before_hash'] == digest(library.export())
            checked = []
            for call in record['calls']:
                result = analyze(public[sid], call['raw_content'])
                assert digest(result) == digest(call['analysis']), (sid,call['step'])
                checked.append({'step':call['step'],'analysis_exact':True})
            learned = mechanism_check(record, public[sid], grades[sid], path)
            pattern = record['learning'].get('learned_pattern')
            if pattern:library.add(pattern, source=sid)
            rows.append({'source':sid,'record_hash':digest(record),'analyses':checked,
                         'learning_attempts_exact':len(learned)})
    assert before == sql_state(path)
    generation_files = ['engine.py','strict_contract.py','compiler_prompt.py','client.py','preflight.py',
                        'compilation.py','coverage.py','interfaces.py','learning.py','typed_learning.py',
                        'ir_types.py','public_horn.py','scoring.py']
    seal = read(run/'seal.json')
    current = science_files(ROOT)
    for filename in generation_files:
        key = 'legal_skill_guard/rr/'+filename
        assert current[key] == seal['protected_files'][key]
    result = {'generation_binding':seal['binding'],'preserved_sources':76,
        'source_learning_sha256':hashlib.sha256(new_source.read_bytes()).hexdigest(),
        'source_learning_AST_unchanged_except_sara_case':True,
        'sara_query_extraction_and_return_unchanged':True,
        'generation_and_semantic_files_unchanged':generation_files,
        'record_hashes':[r['record_hash'] for r in rows], 'records':rows,
        'all_original_analyses_exact':True,'all_original_learning_exact':True,
        'prior_library_hash':digest(library.export()), 'ledger_calls_meta_oracle_unchanged':True,
        'new_model_calls':0,'new_oracle_views':0,'network_and_subprocesses_blocked':True}
    (OUT/'compatible_prefix.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'records','record_hashes'}},ensure_ascii=False),flush=True)


if __name__ == '__main__':main()
