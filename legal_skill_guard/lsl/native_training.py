"""Common native supervision for MIX256, before method-specific weak learning.

All targets derive solely from the same TRAIN256. Source-level means prevent
17 ContractNLI hypotheses from masquerading as17 source updates. No candidate
program is promoted to gold by this module.
"""
from copy import deepcopy
import json
import random

from .projection import b0_target,compact,TAGS,KINDS
from .role_codec import WIRE_ROLES,encode_native
from .contract_wire import encode_evidence,actor_public
from .horn_codec import normalize as normalize_horn


SYSTEM='You learn legal and rule-constrained reasoning from the supplied source. Return only the specified JSON. Do not output reasoning or markdown. The public source and current case are input; hidden reference programs are never prediction tools.'


def prompt(record,semantic=None):
    dataset=record['dataset'];public=record['public']
    if dataset=='NormBench':
        instruction='Convert only rule_text into native units and branches. Output {"units":[{"text":unit source,"b":[{"a":source anchor,"k":native norm kind,"e":[effect text],"c":condition tree}]}]}. A condition is {"tag":native Chinese role,"text":source content} or {"op":"AND" or "OR","items":[conditions]}; null only means no condition. Preserve repeated instances and inferred subjects. full_article_text is context, not extra target.'
        instruction+=' The k field uses exactly these English codes: '+','.join(KINDS)+'. Condition tag codes use exactly: '+','.join(WIRE_ROLES)+'. Codes respectively mean 主体、对象、前置条件、方式、情节、行为、引用、目的、排除、结果、程序、数额. Do not translate schema codes. The wire codes are a lossless serialization of the native roles.'
    elif dataset=='ProofWriter_OWA_depth5':
        instruction='Acquire the complete source facts and Horn rules, preserving explicit negation and shared variables. Output {"program":{"facts":[atom],"rules":[{"body":[atom],"head":atom}],"query":atom},"answer":"True" or "False" or "Unknown"}. Each atom is [predicate,[arguments],positive_boolean]. Variables start with ?, concrete names/properties are lowercase. Unknown means neither polarity is provable under OWA.'
        instruction+=' Exact syntax examples only: "Amy is blue" -> ["blue",["amy"],true]; "Amy is not blue" -> ["blue",["amy"],false]; "If someone is blue then they are kind" -> {"body":[["blue",["?x"],true]],"head":["kind",["?x"],true]}. Use these arrays, never predicate/arguments objects. The answer is outside program. Reuse the same variable within one rule; different rule variables are local. Do not prepend is_ to unary predicates.'
    elif dataset=='ContractNLI':
        instruction='Answer all17 DISTINCT native hypotheses from the contract. All original source characters are preserved in document_segments; span_id is a public evidence identifier, not legal text. For Entailment/Contradiction acquire evidence before reading out the label: output {"answers":[{"id":hypothesis_id,"evidence":{"0":true,"2":true},"label":"Entailment" or "Contradiction"}]}. The example shows syntax only. Evidence is a sparse set of selected native span IDs: use each selected span ID once as a string key with value true, in ascending numeric order. Do not enumerate irrelevant spans. The label follows its acquired evidence. For NotMentioned output {"id":hypothesis_id,"label":"NotMentioned"} without evidence, because absence is not a global negative evidence label. Do not replace normative existence with actual event applicability.'
    elif dataset=='SARA_v2_Binary':
        instruction='Apply the supplied tax statute to the current facts and query. Output {"answer":"Entailment" or "Contradiction"}. Use the available public referenced sections; do not invent missing statutory context.'
    elif dataset=='RuleArena_Airline':
        instruction='Apply the airline policy to this current passenger and every current bag. Output {"answer":integer_total_cost}. The total includes the current ticket price and applicable bag fees. Do not inherit values from another passenger.'
    else:raise ValueError(dataset)
    if semantic is not None:instruction+='\nAcquired source semantics selected by the shared composition model:\n'+compact(semantic)
    view=actor_public(public) if dataset=='ContractNLI' else public
    return [{'role':'system','content':SYSTEM},{'role':'user','content':instruction+'\nDATASET='+dataset+'\nPUBLIC_INPUT='+compact(view)}]


def target(record):
    d=record['dataset'];g=record['grade']
    if d=='NormBench':return encode_native(b0_target(record['native_record'],len(record['public']['rule_text'])))
    if d=='ProofWriter_OWA_depth5':return {'program':normalize_horn(g['horn']),'answer':g['answer']}
    if d=='ContractNLI':
        return {'answers':[{'id':k,**({'evidence':encode_evidence(g['evidence'][k],len(record['public']['sentence_spans']))} if k in g['evidence'] else {}),'label':g['answers'][k]} for k in record['public']['queries']]}
    return {'answer':g['answer']}


def common_source_order(records,seed=45):
    rows=[r for r in records if r['split']=='train']
    if len(rows)!=256 or len({r['key'] for r in rows})!=256:raise ValueError('Warm-up must use exactly TRAIN256')
    rng=random.Random(seed);rng.shuffle(rows)
    # Predeclared first ten updates exercise two sources of every native
    # interface, then the same one-pass initialization continues normally.
    datasets=('NormBench','SARA_v2_Binary','ContractNLI','ProofWriter_OWA_depth5','RuleArena_Airline')
    first=[];counts={d:0 for d in datasets}
    for r in rows:
        if counts[r['dataset']]<2:first.append(r);counts[r['dataset']]+=1
    rest=[r for r in rows if r['key'] not in {x['key'] for x in first}]
    return first+rest


def _find_piece(response,piece,start=0):
    begin=response.find(piece,start)
    if begin<0:raise ValueError('Target token-weight alignment failed')
    return begin,begin+len(piece)


def response_regions(record,result,response):
    """Actual native labels/evidence/structure get separate normalized loss.

    Region weights are source/query means; JSON syntax has a small common
    auxiliary weight. No unannotated semantic field receives a pseudo label.
    """
    d=record['dataset'];regions=[]
    if d=='ContractNLI':
        n=len(result['answers']);evidence_items=[a for a in result['answers'] if 'evidence' in a]
        cursor=0
        for item in result['answers']:
            encoded=compact(item);span=_find_piece(response,encoded,cursor);cursor=span[1]
            label=compact(item['label']);local=_find_piece(encoded,label)
            regions.append((span[0]+local[0],span[0]+local[1],1/n,'native_task'))
            if 'evidence' in item:
                evidence=compact(item['evidence']);a,b=_find_piece(encoded,evidence)
                regions.append((span[0]+a,span[0]+b,1/len(evidence_items),'native_evidence'))
    elif d=='ProofWriter_OWA_depth5':
        a,b=_find_piece(response,compact(result['program']));regions.append((a,b,1.,'native_structure'))
        a,b=_find_piece(response,compact(result['answer']),b);regions.append((a,b,1.,'native_task'))
    else:regions.append((0,len(response),1.,'native_structure' if d=='NormBench' else 'native_task'))
    return regions


def tokenize_record(record,tokenizer,semantic=None):
    text=compact(target(record));messages=prompt(record,semantic)
    prefix=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,enable_thinking=False)
    encoded=tokenizer(text,add_special_tokens=False,return_offsets_mapping=True)
    response=encoded['input_ids']+[tokenizer.eos_token_id]
    offsets=encoded['offset_mapping']+[(len(text),len(text))]
    weights=[0.]*len(response);kinds=[]
    for start,end,mass,kind in response_regions(record,target(record),text):
        selected=[i for i,(a,b) in enumerate(offsets) if b>start and a<end]
        if not selected:raise ValueError('Supervision region has no tokens')
        for i in selected:weights[i]+=mass/len(selected)
        kinds.append(kind)
    syntax=[i for i,w in enumerate(weights) if not w]
    for i in syntax:weights[i]=.05/max(len(syntax),1)
    ids=prefix+response
    if len(ids)>32768:raise ValueError('Native source+target exceeds context; segment before training, never silently truncate')
    return {'key':record['key'],'dataset':record['dataset'],'input_ids':ids,
            'response_start':len(prefix),'response_ids':response,'weights':weights,
            'supervision':sorted(set(kinds)),'prompt_tokens':len(prefix),'response_tokens':len(response),
            'thinking':False,'source_group_weight':1.}
