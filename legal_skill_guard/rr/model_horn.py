"""Model-generated, source-annotated Horn clauses, following LINC/Logic-LM.

The model supplies facts, rules and a query. The public English grammar is an
independent semantic checker on ProofWriter, never the prediction generator.
Missing translations stay residual. No native result is read from model text.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
import re

from .coverage import FiniteTheory, Residual, Unsupported, certificate, complete, digest
from .horn import Atom, Rule, variables
from .public_horn import GroundHornQuery, LibraryHornQuery, VERBS, parse_atom, parse_rule
from .source_structure import inspect_source


class LogicTranslationError(Unsupported):
    def __init__(self, message, *, line=None, source=None, actual=None, public_source_text=None):
        super().__init__(message)
        self.diagnostics={'line':line,'source':source,'message':message,'actual_statement':actual,
                          'public_source_text':public_source_text,'source_only':True,
                          'native_answer_or_grading_used':False}


def _atom(node):
    positive=True
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):
        positive=False;node=node.operand
    if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Name) or node.keywords:
        raise LogicTranslationError('An atom is predicate(arguments), with optional classical minus')
    predicate=node.func.id.casefold()
    if not re.fullmatch('[a-z][a-z0-9_]*',predicate):
        raise LogicTranslationError('A predicate must be a named relation')
    args=[]
    for argument in node.args:
        if isinstance(argument,ast.Name):
            name=argument.id
            # A Prolog identifier encodes a multiword entity with underscores.
            # The independent source check still requires that exact entity.
            args.append('?'+name if name[0].isupper() else name.casefold().replace('_',' '))
        elif isinstance(argument,ast.Constant) and type(argument.value) is str:
            args.append(argument.value.casefold().replace('_',' ').removeprefix('the '))
        else:raise LogicTranslationError('Arguments are named constants, quoted entities or uppercase variables')
    if not args:raise LogicTranslationError('An atom needs explicit arguments')
    return Atom(VERBS.get(predicate,predicate),tuple(args),positive)


def _atoms(text):
    try:node=ast.parse(text.strip(),mode='eval').body
    except (SyntaxError,ValueError,RecursionError) as exc:
        raise LogicTranslationError('Invalid Horn term: '+str(exc)) from exc
    nodes=node.elts if isinstance(node,ast.Tuple) else [node]
    if not nodes:raise LogicTranslationError('A Horn statement cannot be empty')
    return tuple(_atom(n) for n in nodes)


def _equivalent_rule(actual, expected):
    """Conjunction is unordered; variable renaming must preserve all sharing."""
    if len(actual.body)!=len(expected.body):return False
    def unify(a,b,forward,back):
        if (a.predicate,a.positive,len(a.arguments))!=(b.predicate,b.positive,len(b.arguments)):return None
        forward,back=dict(forward),dict(back)
        for x,y in zip(a.arguments,b.arguments):
            if x.startswith('?') and y.startswith('?'):
                if forward.get(x,y)!=y or back.get(y,x)!=x:return None
                forward[x]=y;back[y]=x
            elif x!=y:return None
        return forward,back
    first=unify(actual.head,expected.head,{},{})
    if first is None:return False
    def match(at,remaining,forward,back):
        if at==len(actual.body):return True
        for index,b in enumerate(remaining):
            pairs=unify(actual.body[at],b,forward,back)
            if pairs is not None and match(at+1,remaining[:index]+remaining[index+1:],*pairs):return True
        return False
    return match(0,list(expected.body),*first)


@dataclass
class ModelHorn:
    source: dict
    structure: object
    facts: dict[str,Atom]
    rules: list[Rule]
    query: Atom
    query_source: str
    raw_sha256: str

    @property
    def represented(self):return set(self.facts)|{r.source for r in self.rules}|{self.query_source}

    def export(self):
        def atom(a):return {'predicate':a.predicate,'arguments':list(a.arguments),'positive':a.positive}
        return {'language':'source_annotated_horn_v1','source':self.source['key'],
            'public_input_hash':self.source['content_hash'],'raw_code_hash':self.raw_sha256,
            'facts':{sid:atom(value) for sid,value in self.facts.items()},
            'rules':[{'source':r.source,'body':[atom(a) for a in r.body],'head':atom(r.head)} for r in self.rules],
            'query':atom(self.query),'query_source':self.query_source,
            'represented_units':sorted(self.represented),
            'missing_units':[c.id for c in self.structure.ledger.clauses if c.id not in self.represented],
            'source_semantics_checker':'exact restricted English atom/rule checker; no answer inference',
            'fallback_used':False,'program_origin':'new_model_translation'}


def parse_model_horn(source,code):
    if source['dataset']!='ProofWriter_OWA_depth5':
        raise LogicTranslationError('This Horn adapter currently covers the fixed ProofWriter contract')
    original=code
    if code.strip().startswith('```'):
        lines=code.strip().splitlines()
        if lines[0] not in {'```prolog','```datalog','```'} or lines[-1]!='```':
            raise LogicTranslationError('An optional code fence must enclose the whole completed program')
        code='\n'.join(lines[1:-1])
    structure=inspect_source(source)
    units={c.id:structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses}
    facts={};rules=[];query=None;query_source=None;seen=set()
    for line_no,line in enumerate(code.splitlines(),1):
        line=line.strip()
        if not line or line.startswith('%'):continue
        match=re.fullmatch(r'(.+?)\s*%\s*(s(?:0|[1-9][0-9]*))\s*',line)
        if not match:raise LogicTranslationError('Every statement needs its exact trailing % sN source marker',line=line_no)
        statement,sid=match.groups()
        if sid not in units or sid in seen:
            raise LogicTranslationError('Source marker is absent or already owned',line=line_no,source=sid)
        if not statement.endswith('.'):
            raise LogicTranslationError('A complete Horn statement ends with a period',line=line_no,source=sid)
        statement=statement[:-1].strip();role=structure.roles[sid]['role']
        try:
            if statement.startswith('?-'):
                values=_atoms(statement[2:]);value=values[0]
                if len(values)!=1 or query is not None or role!='query' or variables(value):
                    raise LogicTranslationError('Exactly one ground query must cite the public query unit')
                if value!=parse_atom(units[sid]):raise LogicTranslationError('Query polarity, entity or predicate differs from its public source')
                query,query_source=value,sid
            elif ':-' in statement:
                head,body=statement.split(':-',1);heads=_atoms(head);premises=_atoms(body)
                if len(heads)!=1 or role!='rule':raise LogicTranslationError('A rule has one head and cites a rule unit')
                value=Rule(premises,heads[0],sid)
                if not variables(value.head)<={v for a in value.body for v in variables(a)}:
                    raise LogicTranslationError('Every head variable must be bound by its rule premises')
                if not _equivalent_rule(value,parse_rule(units[sid],sid)):
                    raise LogicTranslationError('Rule guard, polarity, constants or shared variables differ from the public rule')
                rules.append(value)
            else:
                values=_atoms(statement);value=values[0]
                if len(values)!=1 or role!='fact' or variables(value):
                    raise LogicTranslationError('A fact is one ground atom citing a factual unit')
                if value!=parse_atom(units[sid]):raise LogicTranslationError('Fact polarity, entity or predicate differs from its public source')
                facts[sid]=value
        except LogicTranslationError as exc:
            raise LogicTranslationError(str(exc),line=line_no,source=sid,actual=statement,
                                        public_source_text=units[sid]) from exc
        except ValueError as exc:
            raise LogicTranslationError('Independent public-source check unavailable: '+str(exc),line=line_no,source=sid) from exc
        seen.add(sid)
    if query is None:raise LogicTranslationError('A complete model-supplied query is required')
    return ModelHorn(source,structure,facts,rules,query,query_source,hashlib.sha256(original.encode()).hexdigest())


def assess_model_horn(program,library=None,*,interface='ordinary_IO_local_binding_repair'):
    ledger=deepcopy(program.structure.ledger)
    for i,c in enumerate(ledger.clauses):
        if c.id in program.represented:ledger.clauses[i]=replace(c,state='compiled')
    residuals=[Residual(c.id,(),'unverified_llm',True) for c in ledger.clauses if c.id not in program.represented]
    args=(tuple(sorted(program.facts.values())),{},tuple(program.rules),program.query)
    query=LibraryHornQuery(*args,deepcopy(library or {'patterns':[]})) if interface=='collision_refined' else GroundHornQuery(*args)
    theory=FiniteTheory(ledger,{}, {},query,residuals,containment_assumptions=(
        'Model supplied every accepted fact/rule/query; each was independently checked against its restricted public source',))
    result=complete(theory)
    execution=query.execute({}) if isinstance(query,LibraryHornQuery) and result.status=='completion_stable' else None
    if execution is not None:
        execution['predefined_components']=['formal Horn parsing','factual witness matching','fixed-point scheduler']
        for use in execution['pattern_uses']:use['source_units']=[program.rules[use['rule_index']].source]
    return {'answer':result.answer,'certificate_status':result.status,
        'completion_reason':result.reason,
        'certificate':certificate(theory,result) if result.status=='completion_stable' else None,
        'program_status':'model_Horn_IR_compiled','structural_pass':True,'fallback_used':False,
        'A_main_path_executed':result.status=='completion_stable',
        'B_main_path_executed':bool(execution and any(u['query_relevant'] for u in execution['pattern_uses'])),
        'execution':execution,'missing_source_units':[r.source for r in residuals],
        'translation_origin':'actual model Horn text; no public grammar prediction substitution',
        'A_residual_followup_proved':False}


def model_horn_prompt(source,library=None,*,feedback=None):
    structure=inspect_source(source)
    units=[{'id':c.id,'role':structure.roles[c.id]['role'],'text':structure.ledger.text[c.start:c.end]}
           for c in structure.ledger.clauses]
    system=('Translate the CURRENT public English task into a complete concise Prolog/Datalog program. '
        'Represent facts as ground atoms and rules as their actual conclusion followed by :- and their actual conjunctive premises. '
        'Each statement ends with a period and then a percent comment containing its exact sN source ID. '
        'The final query starts with ?-. Source IDs are provenance comments, never entities or predicate names. '
        'Every predicate must name the actual English property or relation, never a placeholder such as predicate or head. '
        'Uppercase names are universally shared rule variables; lowercase or quoted names are actual entities. '
        'Multiword entities may use quoted words or lowercase underscores. '
        'Use exact lowercase adjectives and verbs as predicates: blue, kind, chases, sees, needs, eats, likes, visits. '
        'Classical negation uses -predicate(args), including negative facts, heads and queries; it is not negation-as-failure. '
        'Preserve every conjunct, every shared variable, every explicit entity, polarity and rule direction. '
        'Each original fact and rule has its own line citing its actual sN. Translate every unit, including the query; '
        'do not derive extra facts or include native True/False/Unknown labels, JSON, witness tables, Python or explanations. '
        'The runtime computes closure and checks entailment and explicit refutation. '
        'Feedback contains source-only syntax or semantic errors, never target labels.')
    payload={'units':units,'source_only_feedback':feedback}
    from .compiler_templates import template_examples
    examples=template_examples(source,library)
    if examples:
        payload['compiler_training_examples']=examples
        system+=' Earlier TRAIN examples illustrate complete translation. Their entities and sN namespaces are local; translate CURRENT units independently.'
    return [{'role':'system','content':system},{'role':'user','content':json.dumps(
        payload,ensure_ascii=False,separators=(',',':'))}]
