"""Native TRAIN supervision and branch-blind, source-preserving inventories.

Native branch IDs and paths exist only in the separate graph label. No gold
unit boundary determines the source exposure schedule. Inferred/ambiguous
conditions are retained, without invented character offsets.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import re

from .data import context_mask, occurrences

TAGS = ('主体','对象','前置条件','方式','情节','行为','引用','目的','排除','结果','程序','数额')
KINDS = ('OBLIGATION','DEFINITION','LIABILITY','SANCTION','OTHER','RIGHT','PERMISSION','PROHIBITION','PROCEDURE')


def compact(x):return json.dumps(x, ensure_ascii=False, separators=(',', ':'))
def neutral(*args):return hashlib.sha256(compact(args).encode()).hexdigest()[:20]
def empty():return {'u': [], 'h': [], 'p': [], 'v': [], 'o': []}


def exposure_ends(text):
    """One predeclared path: nearest sentence end to half the target, then full.

    This uses only source punctuation/length, never native units/counts.
    """
    cuts = [m.end() for m in re.finditer(r'[。！？；\n]+', text) if m.end() < len(text)]
    if not cuts:return [len(text)]
    return sorted({min(cuts, key=lambda n: abs(n - len(text)/2)), len(text)})


def unit_span(text, value):
    spans = occurrences(text, value)
    if not spans:spans = occurrences(text, value.strip())
    if len(spans) != 1:return None
    return spans[0]


def support(text, unit, content):
    region = unit_span(text, unit)
    spans = occurrences(text, content)
    if region:
        inside = [p for p in spans if region[0] <= p[0] and p[1] <= region[1]]
        if inside:spans = inside
    return {'kind': 'literal' if len(spans) == 1 else 'unresolved' if spans else 'native_inferred',
            'candidates': spans}


def canonical_inventory(state, source):
    """Canonicalize lexical storage only; retain each role-view occurrence."""
    units = sorted(state['u'], key=lambda t: (unit_span(source,t) or [len(source),len(source)], t))
    old_to_new = {i: units.index(v) for i,v in enumerate(state['u'])}
    payloads = sorted(set(state['p']), key=lambda t: neutral(t))
    remap = {i: payloads.index(v) for i,v in enumerate(state['p'])}
    heads = []
    for h in state['h']:
        head = deepcopy(h);head['u'] = old_to_new[h['u']];heads.append(head)
    ops = [[op,old_to_new[u]] for op,u in state['o']]
    views = [[remap[p],tag,old_to_new[u]] for p,tag,u in state['v']]
    return {'u':units,'h':sorted(heads,key=lambda h: neutral(h)), 'p':payloads,
            'v': sorted(views,key=lambda v: neutral(v)), 'o':sorted(ops,key=lambda v: neutral(v))}


def native_projection(record, visible_end=None):
    text = record['input']['rule_text'];visible_end = len(text) if visible_end is None else visible_end
    state = empty()
    for unit in record['gold']['units']:
        span = unit_span(text, unit['unit_text'])
        if not span:raise ValueError('Native unit is not uniquely source aligned')
        if span[1] > visible_end:continue
        ui = len(state['u']);state['u'].append(unit['unit_text'])
        for branch in unit['branches']:
            state['h'].append({'u':ui,'a':branch['anchor']['text'],'k':branch['norm_kind'],
                               'e':[e['effect_text'] for e in branch['effects']]})
            def visit(node):
                if node is None:return
                if 'op' in node:
                    state['o'].append([node['op'],ui])
                    for c in node['items']:visit(c)
                else:
                    if node['text'] not in state['p']:state['p'].append(node['text'])
                    state['v'].append([state['p'].index(node['text']),node['tag'],ui])
            visit(branch.get('conditions'))
    return canonical_inventory(state,text)


def b0_target(record, end):
    text=record['input']['rule_text'];out=[]
    for unit in record['gold']['units']:
        span=unit_span(text,unit['unit_text'])
        if not span or span[1]>end:continue
        branches=[]
        def tree(n):
            if n is None:return None
            if 'op' in n:return {'op':n['op'],'items':[tree(c) for c in n['items']]}
            return {'tag':n['tag'],'text':n['text']}
        for b in unit['branches']:
            branches.append({'a':b['anchor']['text'],'k':b['norm_kind'],
                             'e':[e['effect_text'] for e in b['effects']], 'c':tree(b.get('conditions'))})
        out.append({'text':unit['unit_text'],'b':branches})
    return {'units':out}


def target_for(system, current, prior):
    common={k:current[k] for k in ('u','h','o')}
    if system=='m1':
        return {'p':[p for p in current['p'] if p not in prior['p']],
                'keep':[i for i,p in enumerate(prior['p']) if p in current['p']], **common}
    if system=='edit':return {'p':current['p'],**common}
    if system=='plain':
        return {**common, 'leaves':[[current['p'][p],tag,u] for p,tag,u in current['v']]}
    raise ValueError(system)


def apply_content(system, result, prior, source):
    """Only schema/lexical adaptation. No semantic completion or fallback."""
    if not isinstance(result,dict):raise ValueError('Expected object')
    for k in ('u','h','o'):
        if not isinstance(result.get(k),list):raise ValueError('Expected list at '+k)
    units=result['u']
    if not all(isinstance(u,str) and u for u in units):raise ValueError('Invalid units')
    if len(set(units))!=len(units):raise ValueError('Duplicated unit records')
    if not all(unit_span(source,u) for u in units):raise ValueError('Unit text must uniquely match visible source')
    for h in result['h']:
        if set(h)!={'u','a','k','e'} or type(h['u']) is not int or not 0<=h['u']<len(units):raise ValueError('Invalid head/unit')
        if not isinstance(h['a'],str) or h['k'] not in KINDS or not isinstance(h['e'],list) or not all(isinstance(v,str) for v in h['e']):raise ValueError('Invalid norm head')
    for op in result['o']:
        if not isinstance(op,list) or len(op)!=2 or op[0] not in ('AND','OR') or type(op[1]) is not int or not 0<=op[1]<len(units):raise ValueError('Invalid operator')
    state={'u':deepcopy(units),'h':deepcopy(result['h']),'o':deepcopy(result['o']),'p':[],'v':[]}
    if system=='plain':
        if not isinstance(result.get('leaves'),list):raise ValueError('Invalid leaves')
        for v in result['leaves']:
            if not isinstance(v,list) or len(v)!=3 or not isinstance(v[0],str) or v[1] not in TAGS or type(v[2]) is not int or not 0<=v[2]<len(units):raise ValueError('Invalid local leaf')
            if v[0] not in state['p']:state['p'].append(v[0])
            state['v'].append([state['p'].index(v[0]),v[1],v[2]])
    else:
        if not isinstance(result.get('p'),list) or not all(isinstance(p,str) and p for p in result['p']):raise ValueError('Invalid payload list')
        if system=='m1':
            keep=result.get('keep')
            if not isinstance(keep,list) or not all(type(i) is int and 0<=i<len(prior['p']) for i in keep) or len(keep)!=len(set(keep)):raise ValueError('Invalid payload keep indices')
            state['p']=[prior['p'][i] for i in keep]+result['p']
        else:state['p']=result['p']
        if len(state['p'])!=len(set(state['p'])):raise ValueError('Payload identity emitted twice')
    return canonical_inventory(state,source)


def examples(record):
    prior=empty();text=record['input']['rule_text'];result=[];start=0
    for t,end in enumerate(exposure_ends(text)):
        current=native_projection(record,end)
        result.append({'item_id':record['item_id'],'family_id':record['family_id'],'step':t,
                       'end':end,'start':start,'source':text[:end], 'new_source':text[start:end],
                       'context':context_mask(record['input']['full_article_text'],text,end),
                       'prior':prior,'current':current,'b0':b0_target(record,end)})
        prior=current;start=end
    return result


def view_counts(state):
    return Counter((state['p'][p],tag,state['u'][u]) for p,tag,u in state['v'])


def max_view_count(records):
    return max(max(view_counts(native_projection(r)).values(),default=0) for r in records)


SYSTEM_INSTRUCTION='你将法律目标原文转换为原生规范结构。只输出指定JSON，不输出思考、解释或代码围栏。上下文不属于预测目标。保留推定主体与全部重复条件实例。'
FORMAT={
 'b0':'输出 {"units":[{"text":单元原文,"b":[{"a":锚点原文,"k":规范类别,"e":[效果原文],"c":条件树}]}]}。条件树为 {"op":"AND或OR","items":[子树]} 或 {"tag":原生角色,"text":条件原文}；无条件才为null。',
 'plain':'输出 {"u":[完整单元原文],"h":[{"u":单元零基索引,"a":锚点原文,"k":规范类别,"e":[效果原文]}],"o":[["AND或OR",单元索引]],"leaves":[[条件原文,原生角色,单元索引]]}。条件实例逐一保留，不预测分支或父边。',
 'edit':'通用共享AST编辑：固定使用完整重写配置，允许添加、删除、更换已有内容。输出 {"p":[全部共享条件原文，仅存一次],"u":[完整单元原文],"h":[{"u":单元零基索引,"a":锚点原文,"k":规范类别,"e":[效果原文]}],"o":[["AND或OR",单元索引]]}。角色与来源实例由同容量联合角色头重写。不得输出分支归属或父边。',
 'm1':'共享语义差分获取：输出 {"p":[以前未获取的新增条件原文，每种仅一次],"keep":[保留的旧p零基索引],"u":[截至当前完整可见的单元原文],"h":[{"u":单元零基索引,"a":锚点原文,"k":规范类别,"e":[效果原文]}],"o":[["AND或OR",单元索引]]}。已有条件只回指不再生成；角色和来源视图增减由联合差分角色头预测。不输出分支归属或父边。'}


def messages(system, ex):
    if system not in FORMAT:raise ValueError(system)
    content=FORMAT[system]+'\n原生角色：'+','.join(TAGS)+'\n规范类别：'+','.join(KINDS)
    content+='\n已获局部状态：'+compact(ex['prior'])+'\n上下文（□为尚未暴露部分）：'+ex['context']
    content+='\n当前目标原文：'+ex['source']+'\n本次新增原文：'+ex['new_source']
    return [{'role':'system','content':SYSTEM_INSTRUCTION},{'role':'user','content':content}]
