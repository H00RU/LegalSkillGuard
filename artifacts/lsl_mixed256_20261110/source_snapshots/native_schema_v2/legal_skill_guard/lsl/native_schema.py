"""Shared native JSON grammar. This enforces format, not legal correctness."""
from .projection import KINDS,TAGS


def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


def array(items):return {'type':'array','items':items}
STRING={'type':'string'}


def schema(dataset,public=None):
    if dataset=='NormBench':
        leaf=obj({'tag':{'type':'string','enum':list(TAGS)},'text':STRING})
        operator=obj({'op':{'type':'string','enum':['AND','OR']},'items':array({'$ref':'#/$defs/condition'})})
        branch=obj({'a':STRING,'k':{'type':'string','enum':list(KINDS)},'e':array(STRING),
                    'c':{'anyOf':[{'$ref':'#/$defs/condition'},{'type':'null'}]}})
        unit=obj({'text':STRING,'b':array(branch)})
        return {**obj({'units':array(unit)}),'$defs':{'condition':{'anyOf':[leaf,operator]}}}
    if dataset=='ProofWriter_OWA_depth5':
        atom={'type':'array','prefixItems':[STRING,array(STRING),{'type':'boolean'}],'minItems':3,'maxItems':3,'items':False}
        program=obj({'facts':array(atom),'rules':array(obj({'body':array(atom),'head':atom})),'query':atom})
        return obj({'program':program,'answer':{'type':'string','enum':['True','False','Unknown']}})
    if dataset=='ContractNLI':
        if not public or len(public['queries'])!=17:raise ValueError('All17 public hypotheses required')
        positive=obj({'id':{'type':'string','enum':list(public['queries'])},
                      'label':{'type':'string','enum':['Entailment','Contradiction']},
                      'evidence':array({'type':'integer','minimum':0,'maximum':len(public['sentence_spans'])-1})})
        not_mentioned=obj({'id':{'type':'string','enum':list(public['queries'])},
                           'label':{'type':'string','enum':['NotMentioned']}})
        return obj({'answers':{**array({'anyOf':[positive,not_mentioned]}),'minItems':17,'maxItems':17}})
    if dataset=='SARA_v2_Binary':return obj({'answer':{'type':'string','enum':['Entailment','Contradiction']}})
    if dataset=='RuleArena_Airline':return obj({'answer':{'type':'integer'}})
    raise ValueError(dataset)
