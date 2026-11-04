import os, sys
from pathlib import Path
root = Path(__file__).resolve().parents[4]
os.chdir(root)
sys.path.insert(0, str(root))
import json, socket, collections, hashlib
from pathlib import Path
def blocked(*a,**k): raise RuntimeError("No network")
socket.socket.connect=blocked
socket.create_connection=blocked
from legal_skill_guard.learning.legal_namespace import public_asset_catalog, public_catalog, decode_asset_references, decode_classification, decode_reference
def read(p): return json.loads(Path(p).read_text())
root=Path(".")
records=read("runs/legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01/scored_records.json")
preds=read("runs/legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01/predictions_before_any_grading.json")
scroot=Path("runs/legal_openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05")
records["skillcommit_paper45"]=read(scroot/"TEST_scored_records.json")
preds["skillcommit_paper45"]=read(scroot/"TEST_predictions_before_grading.json")
packet=read("data/packets/openexempt_IID128_confirmatory_TEST_20261030/inputs.json")
rows={(r["case_id"],r["family"]):r for r in packet["rows"]}
train=read("data/packets/openexempt_closed_feedback_public_assets128_20261021/inputs.json")
train_keys={r["source_key"] for r in train["rows"]}
test_keys={r["source_key"] for r in packet["rows"]}
asset_maps={i:public_asset_catalog(r) for i,r in rows.items()}
law_maps={i:public_catalog(r) for i,r in rows.items()}
raw_errors=[]; pred_errors=[]; controls=collections.Counter(); costs={}; rawpaths=[]; rawids=[]
for arm,rr in records.items():
    costs[arm]={"input":0,"output":0,"stop":0,"length":0,"invalid":0}
    pr={(r["case_id"],r["family"]):r for r in preds[arm]}
    for r in rr:
        ident=r["case_id"],r["family"]
        if {k:v for k,v in r.items() if k!="score"} != pr[ident]: pred_errors.append([arm,*ident])
        p=Path(r["raw_call_path"]); raw=read(p); rawpaths.append(str(p))
        if raw.get("transport_error"): raw_errors.append([arm,*ident,"transport_error"])
        if len(raw["calls"])!=1: raw_errors.append([arm,*ident,"wire_call_count"])
        wire=raw["calls"][-1]
        resp=raw["response"]; wresp=wire["response"]; choice=wresp["choices"][0]
        if (choice["message"].get("content") or "").strip()!=resp["content"]: raw_errors.append([arm,*ident,"wire_content"])
        if choice["finish_reason"]!=resp["finish_reason"]: raw_errors.append([arm,*ident,"finish_reason"])
        if wresp["id"]!=resp["raw_id"]: raw_errors.append([arm,*ident,"response_id"])
        rawids.append(resp["raw_id"])
        for short,long in (("prompt_tokens","prompt_tokens"),("completion_tokens","completion_tokens")):
            if resp[short]!=wresp["usage"][long]: raw_errors.append([arm,*ident,"usage"])
        costs[arm]["input"]+=resp["prompt_tokens"]
        costs[arm]["output"]+=resp["completion_tokens"]
        costs[arm][resp["finish_reason"]]+=1
        costs[arm]["invalid"]+=r["score"]["invalid_format"]
        req=wire["request"]
        controls[json.dumps({k:req.get(k) for k in ("model","seed","temperature","top_p","top_k","max_tokens","chat_template_kwargs")},sort_keys=True)]+=1
        try: submitted=json.loads(resp["content"])
        except json.JSONDecodeError: submitted=None
        if not r["score"]["invalid_format"] and submitted!=r.get("public_label_submission",r.get("actual_wrapper_submission")): raw_errors.append([arm,*ident,"submission_not_wire"])
        if r["score"]["invalid_format"]:
            if resp["finish_reason"]!="length": raw_errors.append([arm,*ident,"invalid_non_length"])
            continue
        if arm=="ACE45": submitted=submitted["final_answer"]
        decoded=decode_asset_references(submitted,asset_maps[ident])
        if r["family"]=="EC": answer=decode_classification(decoded,law_maps[ident])
        else:
            answer={a:[{"citation":decode_reference(c["citation_ref"],law_maps[ident]),"claim_value":c["claim_value"]} for c in claims] for a,claims in decoded.items()}
        if r["parsed"]!={"answer":answer}: raw_errors.append([arm,*ident,"decoded_answer_differs"])
        if r.get("execution_receipt") is not None or r.get("native_program") is not None:
            raw_errors.append([arm,*ident,"numeric_tool_detected"])
mainroot=Path("runs/legal_openexempt_complete_output_utility_public_assets128_20261030_run01")
teacher_responses=[read(p) for p in sorted((mainroot/"teacher").glob("*/response.json"))]
teacher_summaries=[]
for v in teacher_responses:
    teacher_summaries.append({"keys":sorted(v),"usage":v.get("usage"),"invocation_usage":v.get("invocation",{}).get("usage")})
print(json.dumps({"raw_response_records":len(rawpaths),"unique_raw_paths":len(set(rawpaths)),"unique_response_ids":len(set(rawids)),
"raw_HTTP_submission_decode_usage_errors":raw_errors,"pregrading_prediction_vs_scored_record_errors":pred_errors,
"raw_generation_profile_counts":dict(controls),"actual_frozen_inference_tokens_and_finishes":costs,
"train_sources":len(train_keys),"test_sources":len(test_keys),"train_test_source_overlap":len(train_keys&test_keys),
"main_teacher_response_files":len(teacher_responses),"first_main_teacher_summary":teacher_summaries[:1],
"main_teacher_total_usage":{k:sum((v.get("invocation",{}).get("usage") or {}).get(k,0) for v in teacher_responses) for k in ("input_tokens","output_tokens","cached_input_tokens","reasoning_output_tokens")},
"network_disabled":True,"new_model_calls":0},ensure_ascii=False))
