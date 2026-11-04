import os, sys
from pathlib import Path
root = Path(__file__).resolve().parents[4]
os.chdir(root)
sys.path.insert(0, str(root))
import json, re, math, socket, hashlib
from pathlib import Path
import numpy as np
def blocked(*a, **k):
    raise RuntimeError("No network in read-only review")
socket.socket.connect = blocked
socket.create_connection = blocked
from experiments.openexempt_frozen_eval import paired_source_statistics
from legal_skill_guard.openexempt import evaluate, metrics
def read(p): return json.loads(Path(p).read_text())
def norm(x):
    if isinstance(x, float) and not math.isfinite(x): return None
    if isinstance(x, dict): return {k:norm(v) for k,v in x.items()}
    if isinstance(x, list): return [norm(v) for v in x]
    return x
def differences(a,b,path=""):
    if isinstance(a,dict) and isinstance(b,dict):
        return [p for k in set(a)|set(b) for p in differences(a.get(k),b.get(k),path+"/"+str(k))]
    if isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b): return [path+"/length"]
        return [p for i,(x,y) in enumerate(zip(a,b)) for p in differences(x,y,path+"/"+str(i))]
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        return [] if abs(a-b)<1e-12 else [path]
    return [] if a==b else [path]
records=read("runs/legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01/scored_records.json")
cfg=read("artifacts/launches/openexempt_v6_final_after_withheld_20261031_run01/actual_final_matrix_config.json")
base=read("paper/tables/utility_frozen_results_20261101.json")
now=paired_source_statistics(cfg,records)
stat_diff=differences(base["paired_statistics"],now)
table=read("paper/tables/utility_frozen_results_with_skillcommit_20261104.json")
sc=read("runs/legal_openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05/TEST_scored_records.json")
keys=sorted({r["source_key"] for r in sc})
indices=np.random.default_rng(2026110101).integers(len(keys),size=(20000,len(keys)))
scnow={}
for f in ("EC","EV"):
    main={r["source_key"]:r["score"]["f1"] for r in records["utility45"] if r["family"]==f}
    other={r["source_key"]:r["score"]["f1"] for r in sc if r["family"]==f}
    d=np.array([main[k]-other[k] for k in keys])
    boot=d[indices].mean(axis=1)
    scnow[f]={"delta_pp":float(d.mean()*100),"ordinary95_pp":(100*np.quantile(boot,[.025,.975],method="linear")).tolist(),
              "two_endpoint_fwer95_pp":(100*np.quantile(boot,[.0125,.9875],method="linear")).tolist()}
scdiff=differences({f:table["supplementary_SkillCommit_source_paired_statistics"][f] for f in ("EC","EV")},scnow)
def tables(path):
    output=[]; active=None
    for lineno,line in enumerate(Path(path).read_text().splitlines(),1):
        if line.startswith("|"):
            if active is None:
                active={"line":lineno,"cells":[]}; output.append(active)
            active["cells"].append([v.strip().replace("**","") for v in line.strip().strip("|").split("|")])
        else: active=None
    return output
en=tables("paper/utility_skill_manuscript_working_20261030.md")
zh=tables("paper/sections-zh/utility_skill_manuscript_working_20261030.md")
number=lambda s:[float(x.replace(",","")) for x in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?",s)]
bilingual=[]
for i,(e,z) in enumerate(zip(en,zh)):
    if len(e["cells"])!=len(z["cells"]): bilingual.append({"table":i,"row_count":True}); continue
    for j,(ec,zc) in enumerate(zip(e["cells"][2:],z["cells"][2:]),2):
        ev=[n for s in ec[1:] for n in number(s)]
        zv=[n for s in zc[1:] for n in number(s)]
        if ev!=zv: bilingual.append({"table":i,"row":j,"en":ev,"zh":zv})
order=["empty","static","ACE45","ACE_common45","text45","skillcommit_paper45","utility_own_B1_45","strict45","no_execution45","projection45","utility45"]
arms={r["condition"]:r for r in table["conditions"]}
main_table_errors=[]; quality_errors=[]
for arm,row,qrow in zip(order,en[1]["cells"][2:],next(t for t in en if "Strict object match EC / EV" in t["cells"][0])["cells"][2:]):
    m=arms[arm]["metrics"]
    wanted=[round(100*m[f]["f1"],2) for f in ("EC","EV")]+[round(100*m["mean_family_f1"],2)]
    if [float(v) for v in row[1:]]!=wanted: main_table_errors.append(arm)
    wantedq=[round(100*m[f]["full_output_f1"],2) for f in ("EC","EV")]
    wantedq += [round(100*m[f]["exact_target"],2) for f in ("EC","EV")]
    wantedq += [m[f]["invalid_format"] for f in ("EC","EV")]
    if [n for s in qrow[1:] for n in number(s)]!=wantedq: quality_errors.append(arm)
paired_table_errors=[]
for contrast,row in zip(now["contrasts"].values(),next(t for t in en if t["cells"][0][0] == "Comparator")["cells"][2:]):
    for f,cell in zip(("EC","EV"),row[1:]):
        ep=contrast["endpoints"][f]
        wanted=[round(ep["difference_pp"],2)]+[round(v,2) for v in ep["conditional_Bonferroni_interval_pp"]]
        if number(cell)!=wanted: paired_table_errors.append({"label":row[0],"task":f})
sc_table_errors=[]
for f,row in zip(("EC","EV"),next(t for t in en if t["cells"][0][0] == "Task")["cells"][2:]):
    wanted=[round(scnow[f]["delta_pp"],2)]+[round(v,2) for k in ("ordinary95_pp","two_endpoint_fwer95_pp") for v in scnow[f][k]]
    if [n for s in row[1:] for n in number(s)]!=wanted: sc_table_errors.append(f)
curve=read("paper/figures/utility_learning_curves_20261030/source_data.json")
trainroot=Path("runs/legal_openexempt_complete_output_utility_public_assets128_20261030_run01")
train_gold={p.stem:read(p) for p in Path("data/packets/openexempt_closed_feedback_public_assets128_20261021/grading_only").glob("*.json")}
curve_diff=[]; training_score_errors=[]; training_compared=0
combined={arm:[] for arm in ("empty","skills","frozen_after_B1")}
curve_hash_errors=[]
for src,series in zip(curve["source_files"],curve["series"]):
    for part in ("records","summary"):
        p=Path(src[part]["path"])
        if hashlib.sha256(p.read_bytes()).hexdigest()!=src[part]["sha256"]: curve_hash_errors.append(str(p))
    rows=read(src["records"]["path"])
    for arm in combined:
        rrows=rows[arm]
        m=metrics(rrows)
        for r in rrows:
            target=train_gold[str(r["case_id"])]["targets"][r["family"]]
            score=norm(evaluate(r,(r["parsed"] or {}).get("answer"),target))
            training_compared+=1
            if score!=norm(r["score"]): training_score_errors.append([src["batch"],arm,r["case_id"],r["family"]])
        for f in ("EC","EV"):
            for metric in ("f1","full_output_f1"):
                v=m[f][metric]*100; expected=series["percent"][arm][f][metric]
                if abs(v-expected)>1e-12: curve_diff.append([src["batch"],arm,f,metric])
        if src["batch"]>1: combined[arm]+=rrows
continuation={arm:{f:{k:100*v for k,v in vals.items() if k in ("f1","full_output_f1")} for f,vals in metrics(rows).items() if f in ("EC","EV")} for arm,rows in combined.items()}
table2_diff=[]
for arm,row in zip(("empty","frozen_after_B1","skills"),en[2]["cells"][2:5]):
    expected=[round(continuation[arm][f][k],2) for k in ("f1","full_output_f1") for f in ("EC","EV")]
    if [float(v) for v in row[1:]]!=expected: table2_diff.append(arm)
diff_row=[round(continuation["skills"][f][k]-continuation["frozen_after_B1"][f][k],2) for k in ("f1","full_output_f1") for f in ("EC","EV")]
if [float(v) for v in en[2]["cells"][5][1:]]!=diff_row: table2_diff.append("difference")
print(json.dumps({"bootstrap_original18_endpoint_difference_paths":stat_diff,"bootstrap_original_adjusted_positive_endpoints":sum(v["adjusted_lower_positive"] for c in now["contrasts"].values() for v in c["endpoints"].values()),"bootstrap_SkillCommit2_endpoint_difference_paths":scdiff,
"bootstrap_SkillCommit_recomputed":scnow,"EN_tables":len(en),"ZH_tables":len(zh),"bilingual_table_numeric_differences":bilingual,
"main_table_errors":main_table_errors,"quality_table_errors":quality_errors,"paired_table_errors":paired_table_errors,"supplement_table_errors":sc_table_errors,
"training_curve_record_comparisons_including_saved_reuses":training_compared,"training_curve_score_errors":training_score_errors,
"curve_original_file_hash_errors":curve_hash_errors,"curve_metric_differences":curve_diff,"continuation_table_errors":table2_diff,
"all112_first_answer_means":continuation,"network_disabled":True,"new_predictions":0},ensure_ascii=False))
