"""Remove semantic requests the frozen composition cannot consume.

This is a cost correction of the actual C execution path, not a new contribution.
No learning or model requests are started by the replay command below.
"""
import ast
from copy import deepcopy
import json
from pathlib import Path


def prune_planner(library):
    result=deepcopy(library)
    selected=set(library['selected_rule_ids'])
    rules=[r for r in library['language']['rules']if r['id']in selected]
    all_operations={o['name']for o in library['operations']}
    query_inputs={'reader_query','query_window','query_focus','reader_observed_value',
                  'query_choice','query_unknown','query_unread','evidence_unit','evidence_quote'}
    live=set()
    for rule in rules:
        anchors={}
        for atom in rule['body']:
            if atom['predicate'].startswith('json_'):
                return result,{'pruned':False,'reason':'Selected composition can inspect unrestricted observation JSON'}
            if atom['predicate']=='reader_query':
                query,operation=atom['arguments']
                if atom['sign']!='positive' or not isinstance(query,dict)or set(query)!={'var'}or not isinstance(operation,str):
                    return result,{'pruned':False,'reason':'Dynamic semantic-operation dependency'}
                anchors[query['var']]=operation;live.add(operation)
        for atom in rule['body']:
            if atom['predicate']in query_inputs-{'reader_query'}:
                query=atom['arguments'][0]
                if not isinstance(query,dict)or query.get('var')not in anchors:
                    return result,{'pruned':False,'reason':'A selected query observation has no fixed operation scope'}
    if not live<=all_operations:
        raise ValueError('Composition refers to an unavailable semantic operation')
    tree=ast.parse(library['planner_program']);entry=next(f for f in tree.body if isinstance(f,ast.FunctionDef)and f.name=='apply')
    returns=[n for n in ast.walk(entry)if isinstance(n,ast.Return)]
    if not returns or any(not isinstance(n.value,ast.Dict)or [k.value for k in n.value.keys if isinstance(k,ast.Constant)]!=['queries']for n in returns):
        return result,{'pruned':False,'reason':'Planner does not have the current explicit query-list return shape'}
    for node in returns:
        original=node.value
        replacement=ast.parse("{'queries':[query for query in original['queries'] if query['operation'] in permitted]}",mode='eval').body
        class Bind(ast.NodeTransformer):
            def visit_Name(self,name):
                if name.id=='original':return deepcopy(original)
                if name.id=='permitted':return ast.List(elts=[ast.Constant(v)for v in sorted(live)],ctx=ast.Load())
                return name
        node.value=Bind().visit(replacement)
    result['planner_program']=ast.unparse(ast.fix_missing_locations(tree))
    return result,{'pruned':True,'live_operations':sorted(live),
                  'unconsumed_operations':sorted(all_operations-live),'semantic_rules_and_source_program_unchanged':True}


def replay():
    root=Path.cwd();old=root/'artifacts/legal_skill_evolution_source_frame_update_20261115'
    # Execute the original scientific core, rather than silently changing its
    # historical version after the observation runtime was subsequently edited.
    import legal_skill_guard.skill_evolution as package
    package.__path__.insert(0,str(old/'source_snapshot/legal_skill_guard/skill_evolution'))
    from experiments import legal_skill_evolution_source_frame_update as c
    from legal_skill_guard.skill_evolution.open_acquisition import observe
    from legal_skill_guard.rr.checkpoint import immutable_json
    from legal_skill_guard.skill_evolution.objects import digest
    class NoRequests:
        def tokenize(self,*args,**kwargs):raise RuntimeError('Unexpected new semantic read in the pruning replay')
        def generate(self,*args,**kwargs):raise RuntimeError('Offline replay cannot dispatch a model')
    library=c.read(old/'ConstraintAcquire/selected_before_reuse.json')['library']
    updated,receipt=prune_planner(library);assert receipt['pruned']
    public,grading=c.bank();task=c.read(old/'teacher_task.json');p=c.read(old/'protocol.json');rows=[]
    original=c.read(old/'ConstraintAcquire/result.json');baseline={r['source']:r for kind in ('acquisition','fixed_reuse')for r in original[kind]}
    for sid in p['acquisition_sources']+p['fixed_reuse_sources']:
        prior=c.read(c.previous.OUT/'ConstraintAcquire/results'/c.previous.update.train.previous.old.name_for(sid))['observation']
        upstream=c.read(c.previous.update.train.parent.OUT/'source_pass/upstream'/c.previous.update.train.previous.old.name_for(sid))['source_output']
        obs=observe(NoRequests(),'offline',sid,updated,source_text=public[sid]['views'][0]['public']['source_text'],
            units=prior['visible_inputs']['units'],source_output=upstream,previous_observation=prior)
        actual=c.assessed(updated,obs,sid,public,grading,task);before=baseline[sid]
        assert actual['source_output']['statements']==before['source_output']['statements']
        assert actual['native_correct']==before['native_correct']and actual['hard_source_pass']==before['hard_source_pass']
        full=c.read(old/'ConstraintAcquire/observations'/(digest(sid)+'.json'))
        rows.append({'source':sid,'native_correct':actual['native_correct'],'source_hard_pass':actual['hard_source_pass'],
            'norm_statements_unchanged':True,'actual_new_requests':0,'previous_new_requests':full['execution']['new_physical_requests'],
            'same_acquisition_or_reuse_partition':'acquisition'if sid in p['acquisition_sources']else'reuse'})
    out=root/'artifacts/legal_skill_evolution_source_read_pruning_20261115'
    immutable_json(out/'library.json',updated)
    immutable_json(out/'result.json',{'rows':rows,'pruning':receipt,'new_model_calls':0,
        'cost_saving_is_a_retrospective_after_selection_replay':True,'not_an_independent_C_gain':True,'goal_complete':False})
    print(json.dumps({'rows':rows,'pruning':receipt}),flush=True)


if __name__=='__main__':replay()
