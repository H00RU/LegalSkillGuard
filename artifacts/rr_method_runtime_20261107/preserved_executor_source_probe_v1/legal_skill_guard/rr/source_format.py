"""Invented syntax example, independent of every benchmark and grading label."""

FORMAT_EXAMPLE={
    'public':{'rules':'# Eligibility\nFor purposes of requests under the parcel plan, if-\n    (a) Fragile parcels with at least 2 items qualify.',
              'facts':'Alice has 3 fragile parcels.','query':'Do the parcels qualify?'},
    'program':{
        'bindings':[{'name':'n_count','type':'integer','value':3,'sources':['s3']},
                    {'name':'n_minimum','type':'integer','value':2,'sources':['s2']}],
        'observations':[{'name':'b_fragile','entity':'parcels','entity_source':'s3',
                         'predicate':'Fragile','predicate_source':'s2'}],
        'rule_residuals':[{'name':'b_plan_scope','source':'s1','quote':'requests under the parcel plan'}],
        'nodes':[],
        'scopes':[{'name':'scope_title','source':'s0','condition':True},
                  {'name':'scope_plan','source':'s1','condition':{'var':'b_plan_scope'}}],
        'clauses':[{'name':'eligible','sources':['s2'],'value':{'op':'and','args':[
            {'var':'b_fragile'},{'op':'le','args':[{'var':'n_minimum'},{'var':'n_count'}]}]},'otherwise':False}],
        'query':{'op':'if','args':[{'var':'eligible'},'Entailment','Contradiction']}}}
