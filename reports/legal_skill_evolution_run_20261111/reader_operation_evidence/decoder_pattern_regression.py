"""Replay the real malformed response against both local decoding grammars.

No model requests. Paths use the exported evidence, not private service paths.
"""
from copy import deepcopy
import json
from pathlib import Path

import xgrammar as xgr


if __name__=='__main__':
    root=Path(__file__).resolve().parent/'raw/constructive'
    result=json.loads((root/'shared_direct_failure_v2.json').read_text())['result']
    request=json.loads((root/'calls'/Path(result['artifact_directory']).name/'request.json').read_text())
    original=request['payload']['response_format']['json_schema']['schema']
    corrected=deepcopy(original)
    corrected['properties']['statements']['items']['properties']['expression'].pop('pattern')
    compiler=xgr.GrammarCompiler(xgr.TokenizerInfo([bytes([i]) for i in range(256)]))
    outcomes={}
    for name,schema in [('broad_pattern',original),('ordinary_JSON',corrected)]:
        matcher=xgr.GrammarMatcher(compiler.compile_json_schema(schema),terminate_without_stop_token=True)
        outcomes[name]={'accepted_as_prefix':matcher.accept_string(result['content']),
                        'terminated':matcher.is_terminated()}
    assert outcomes['broad_pattern']=={'accepted_as_prefix':True,'terminated':False}
    assert outcomes['ordinary_JSON']['accepted_as_prefix'] is False
    print(json.dumps({'actual_failure_regression':outcomes,'new_model_requests':0}))
