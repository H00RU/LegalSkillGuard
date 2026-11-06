"""Observe only this controller's child argv; no model or network requests."""
import json,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).with_name('teacher_effective_argv.json')
identity=json.loads((ROOT/'artifacts/rr_v2_formal_build_20261106/run_citation_fix/process_identity.json').read_text())
pid=identity['pid'];start=identity['start_ticks']
while True:
    try:
        if (Path('/proc')/str(pid)/'stat').read_text().split()[21]!=start:break
    except FileNotFoundError:break
    queue=[pid];seen=set()
    while queue:
        current=queue.pop()
        if current in seen:continue
        seen.add(current)
        try:
            parent=Path('/proc')/str(current)
            queue.extend(int(n) for n in (parent/'task'/str(current)/'children').read_text().split())
            args=[a.decode() for a in (parent/'cmdline').read_bytes().split(b'\0') if a]
        except (FileNotFoundError,ProcessLookupError):continue
        if 'exec' not in args or '--model' not in args:continue
        model=args[args.index('--model')+1]
        effort=next((x.split('=',1)[1].strip('"') for x in args if x.startswith('model_reasoning_effort=')),None)
        if model!='gpt-5.6-sol' or effort!='high':raise RuntimeError('Unexpected teacher effective configuration')
        result={'captured_utc':datetime.now(timezone.utc).isoformat(),'controller_pid':pid,'controller_start_ticks':start,
            'child_pid':current,'actual_model_argument':model,'actual_reasoning_effort_argument':effort,
            'sandbox_argument':args[args.index('--sandbox')+1] if '--sandbox' in args else None,
            'ignore_user_config':'--ignore-user-config' in args,'temperature_argument_present':any('temperature' in x for x in args),
            'no_prompt_or_environment_captured':True,'new_model_calls':0}
        OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result),flush=True)
        raise SystemExit(0)
    time.sleep(2)
print('Controller terminated before an argv observation; use frozen client and actual response receipts',flush=True)
