"""Read-only adversarial precheck on an existing development TRAIN output.

The changed IR below is explicitly constructed, not a new model result or
method repair. It tests whether native answers plus their exact citation score
can identify a material condition already present in the actual source.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.skill_evolution.native import source_spans, grade_view
from legal_skill_guard.skill_evolution.scoped_grammar import constructors, term_sort, material_public
from legal_skill_guard.skill_evolution.span_compiler import execute_json


ROOT = Path('/home/yndx/hhy/legal-skill-current')
OUT = Path('/tmp/lsg_native_evidence_identifiability_20261113.json')


def read(p):
    return json.loads(p.read_text())


def snapshot():
    c = sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro', uri=True)
    rows = c.execute('select * from calls order by id').fetchall()
    return {'rows':len(rows),'sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()}


before = snapshot()
key = 'ContractNLI:d9360f2a8c03efc35524289167a83e9505ebae476367505b868af29f37fcffa0'
all_public = read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
source = next(s for s in all_public if s['key']==key)
annotation = read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')[key]
actual = next(x for x in read(ROOT/'reports/legal_skill_evolution_run_20261111/open_effect_evidence/results/development/SourceEffect.json')['results'] if x['source']==key)
bundle = read(ROOT/'artifacts/legal_skill_evolution_open_effect_acquisition_20261113/SourceEffect/compiled.json')
schema = constructors(bundle['grammar'])
bad = deepcopy(actual['interpretation'])
removed = []


def remove_material_condition(tree, path):
    if not isinstance(tree,list):
        return tree
    if tree[0]=='and_condition' and len(tree)==3 and tree[2][0]=='confidentiality_bound':
        removed.append({'path':path,'before':deepcopy(tree),'after':deepcopy(tree[1])})
        return deepcopy(tree[1])
    return [tree[0],*(remove_material_condition(t,path+[i]) for i,t in enumerate(tree[1:],1))]


for n in bad['nodes']:
    n['term'] = remove_material_condition(n['term'],['nodes',n['id'],'term'])
    term_sort(n['term'],schema)
assert len(removed)==2
assert [n['support_ids'] for n in bad['nodes']]==[n['support_ids'] for n in actual['interpretation']['nodes']]
spans = source_spans(material_public(source['views'][0]['public']))


def run(interp):
    out=[]
    for view in source['views']:
        value=execute_json(bundle['grammar']['decision_program'],{'task_id':view['id'],'question':view['public']['question']},interp,allow_helpers=True)
        evidence=sorted({spans[s]['public_sentence_id'] for n in value['used_nodes'] for s in interp['nodes'][n]['support_ids'] if 'public_sentence_id' in spans[s]})
        score=grade_view(source['dataset'],view,annotation[view['id']],value['answer'],evidence)
        out.append({'view':view['id'],'execution':value,'evidence':evidence,'score':score})
    return out


a,b=run(actual['interpretation']),run(bad)
assert a==b
after = snapshot();assert before==after
OUT.write_text(json.dumps({'source':key,'TRAIN_development_only':True,'constructed_counterexample_not_model_output':True,'source_program_not_changed':True,'source_text_not_changed':True,'support_ids_unchanged':True,'material_condition_removed':removed,'all_four_native_answers_used_roots_citations_and_scores_identical':True,'actual_original':a,'constructed_wrong_variant':b,'new_project_model_requests':0,'ledger_before':before,'ledger_after':after,'scientific_scope':'This shows non-identification by the existing native/evidence loss for this real condition. It does not prove learning from raw source and pretrained priors impossible, does not repair a source, and is not a method result.'},ensure_ascii=False,indent=2)+'\n')
print(OUT)
print('All4 target answers, used roots, citation sets and scores remain identical after removing2 material confidentiality-condition instances.')
