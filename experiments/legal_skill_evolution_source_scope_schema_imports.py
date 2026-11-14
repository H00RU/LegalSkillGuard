from pathlib import Path
import json,ast
from copy import deepcopy
from experiments import legal_skill_evolution_source_scope_repair as r
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
p=r.OUT;t=json.loads((p/'teacher_task.json').read_text());raw=json.loads((p/'FreeUpdate/compiled.json').read_text());a=deepcopy(raw)
provided={c['name']:c for c in t['actual_current_libraries_both_available']['ConstraintAcquire']['spec']['constructors']}
known={c['name']:c for c in raw['spec']['constructors']}
used=set()
for field in ['source_program','composition_program']:
 for n in ast.walk(ast.parse(raw[field])):
  if isinstance(n,ast.List) and n.elts and isinstance(n.elts[0],ast.Constant) and isinstance(n.elts[0].value,str):used.add(n.elts[0].value)
missing=sorted((used & set(provided))-set(known));assert missing==['acq_disclosure_v3','acq_disposal_action_v3','acq_disposal_link_v3','acq_residual_v3','acq_retention_v3'],missing
for name in missing:a['spec']['constructors'].append(deepcopy(provided[name]))
assert a['source_program']==raw['source_program'] and a['composition_program']==raw['composition_program']
assert a['spec']['decision_program']==raw['spec']['decision_program']
immutable_json(p/'FreeUpdate/unbound_schema_imports/library.json',a)
immutable_json(p/'FreeUpdate/unbound_schema_imports/proof.json',{'imported_exact_already_supplied_C_definitions':[provided[n] for n in missing],
 'before_library_sha256':digest(raw),'after_library_sha256':digest(a),'no_constructor_alias_or_value_mapping':True,
 'source_composition_consumer_unchanged':True,'raw_teacher_and_original_compiled_library_retained':True,'new_model_requests':0,
 'reason':'Free generated names from the shared actual C library but omitted their declarations in its own spec.'})
print(json.dumps({'same_meaning_schema_imports':missing,'new_model_requests':0}))
