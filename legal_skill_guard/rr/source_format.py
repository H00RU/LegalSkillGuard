"""Public task/language contracts and one unrelated example; no grading data."""


def native_schema(dataset):
    from .scoring import LABELS
    if dataset in LABELS:
        return {'type':'string','enum':sorted(LABELS[dataset])}
    if dataset=='RuleArena_Airline':return {'type':'integer','minimum':0}
    if dataset!='OpenExempt':raise ValueError('Unknown native task contract')
    from legal_skill_guard.openexempt import answer_schema
    return {'anyOf':[{'type':'object','additionalProperties':False,'required':['EC','EV'],
        'properties':{family:answer_schema(family) for family in ('EC','EV')}},{'type':'null'}]}


def language_contract(dataset, *, literal_text=None):
    """Expose the actual decoder's value shapes and graph parameters to the LM.

    A response-format schema constrains generated tokens; it is not part of the
    chat-template input. This description contains no case values or answers.
    """
    from .strict_contract import interface_definitions,type_enum_schemas,EXPRESSION_DEPTH
    definitions=interface_definitions(literal_text=literal_text)
    type_enum_schemas(definitions)
    values={item['properties']['type']['enum'][0]:item['properties']['value']
            for item in definitions['binding']['anyOf']}
    signatures=[{'op':item['properties']['op']['enum'][0],
                 'arity':item['properties']['inputs']['minItems'],
                 'params_schema':item['properties']['params']}
                for item in definitions['connector']['anyOf'] if 'op' in item.get('properties',{})]
    return {
        'binding_value_schemas':values,
        'binding_semantics':{
            'integer_rational_scalar':'Exact public inputs only; derived quantities and legal conclusions belong in expression nodes. Amount or relation objects are not expression numbers or Booleans.',
            'relation':'Each row is an explicit factual witness with one cell per named column; closed records whether this supplied relation is complete. Use slot_list only for already declared slots.',
            'amount':'value is a nonnegative integer in the stated unit; unit, owner, period and lineage describe the public inputs. stage=element before aggregation; closed_group after a justified complete aggregation. Do not invent metadata or use a legal exemption conclusion as a binding.',
            'allowance_bank':'One shared consumable resource per [rule,owner,period] key; balance and observable ordering must come from public source. resource_key references that same triple. Never create a second bank for the same allowance.'},
        'connector_syntax':{'leaf':{'slot':'DECLARED_BINDING_OR_NODE_NAME'},
            'max_nested_operators':EXPRESSION_DEPTH,
            'operator':'{op:NAME,inputs:[CHILD_GRAPHS],params:PARAMETERS}; params={} for an empty parameter schema',
            'signatures':signatures},
        'connector_semantics':{
            'bind_rename':'One relation -> relation, renaming the from columns to the corresponding to columns.',
            'join_on':'Two relations -> relation, equating witnesses on keys; empty keys mean a Cartesian product, not shared-witness equality.',
            'project_exists':'One relation -> Boolean indicating at least one row; this loses witness identity.',
            'group_by':'One closed relation or amount collection -> groups keyed by the stated columns or amount owner/period/unit.',
            'map':'cap maps typed amounts using numeric limit_slot and matching element/closed_group scope; exists maps relation groups to Booleans; sum_amounts maps explicit amount groups to grouped totals.',
            'fold_reduce':'sum_amounts reduces a typed amount list to one same-resource closed_group amount; all/any reduce Boolean lists.',
            'thread_allowance':'An ordered amount list consumes the one bank_slot at key_slot, returning the actual allocated amount list. Do not fork or re-consume the bank.'},
        'connector_projection':{'identity':'Preserve its typed value.',
            'amount_value':'One Amount -> exact number.',
            'amount_values':'Amount list -> exact number list; number_at selects an actual element.',
            'entailment_label':'Boolean -> Entailment/Contradiction, only for a task using those labels.'},
        'query_result_schema':native_schema(dataset),
        'query_result_instruction':
            'The root query evaluates to this native result; do not emit an answer field beside the program. '
            'Use object/pair/array expressions and guarded clause outputs. For OpenExempt include both EC and EV, '
            'each keyed by every actual public asset description. EC values are citation-string arrays; EV values '
            'are arrays of {citation:verbatim public citation,claim_value:numeric expression}. The public wording '
            'about a supplied response schema refers to this shape, not paragraph IDs or Entailment labels. '
            'For Airline include the public ticket price and all applicable baggage costs. A null or unsupported '
            'result has no core success certificate. The unrelated format example does not redefine this task.'}

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
