"""Executable format examples from invented inputs, independent of benchmarks."""
from __future__ import annotations

import json


def format_examples():
    def binding(name, value, source, kind="integer"):
        return {"name": name, "type": kind, "value": value, "source": source}
    def var(name):
        return {"var": name}
    def op(name, *args):
        return {"op": name, "args": list(args)}
    def proposal(answer, bindings, query, ids):
        return {"program": {"kind": "expression", "body": {
            "bindings": bindings, "query": query, "source_links": {s: ["query"] for s in ids}}},
            "answer": answer, "compiled_units": ids, "unsupported_units": [], "interfaces": []}
    numeric = proposal(14, [binding("n_count", 2, "s0"), binding("n_fee", 7, "s1")],
                       op("scale", 7, var("n_count")), ["s0", "s1"])
    boolean = proposal("Entailment", [binding("n_age", 25, "s0"), binding("n_threshold", 21, "s1")],
        op("if", op("le", var("n_threshold"), var("n_age")), "Entailment", "Contradiction"), ["s0", "s1"])
    asset = var("s_asset")
    cite = "Toy Rule §1"
    amount = op("min", var("n_value"), var("n_cap"))
    structured = proposal({"EC": {"sample vase": ["Toy Rule §1"]},
                          "EV": {"sample vase": [{"citation": "Toy Rule §1", "claim_value": 30}]}},
        [binding("s_asset", "sample vase", "s0", "scalar"), binding("n_value", 30, "s0"),
         binding("n_cap", 40, "s1")],
        op("object", op("pair", "EC", op("object", op("pair", asset, op("array", cite)))),
           op("pair", "EV", op("object", op("pair", asset, op("array", op("object",
              op("pair", "citation", cite), op("pair", "claim_value", amount))))))), ["s0", "s1"])
    examples = [
        {"public_text": "Number of parcels: 2.\nFee per parcel is 7; multiply the count by 7.", "proposal": numeric},
        {"public_text": "Age: 25.\nThe claim is Entailment if age is at least 21, otherwise Contradiction.", "proposal": boolean},
        {"public_text": "Asset sample vase has value 30.\nToy Rule §1 covers this asset with a cap of 40.", "proposal": structured}]
    return examples


def compiler_instructions(dataset):
    examples = format_examples()
    selected = {'RuleArena_Airline': 0, 'SARA_v2_Binary': 1, 'OpenExempt': 2}
    if dataset in selected:
        examples = [examples[selected[dataset]]]
    return (
        "\nExecutable contract clarification: bindings contain only extracted public inputs and rule constants; "
        "never put an answer object or a program into a scalar string. JSON text in a string is not executable. "
        "A source identifier such as s0 is provenance metadata, never a boolean or a variable. "
        "Read a bound input with {\"var\":\"name\"}. and/or/not take booleans; comparisons return booleans. "
        "Expression binding names use n_ for integer/rational, s_ for strings, b_ for booleans; "
        "numeric references must name n_ slots, string keys s_ slots, boolean references b_ slots. "
        "Choose op before writing args. The maximum expression depth is16; use concise expressions. "
        "The root query must return the native task result: a numeric operation for Airline, an if producing "
        "an Entailment/Contradiction string for SARA, and an object operation producing EC/EV for OpenExempt. "
        "OpenExempt EC values are arrays of literal legal citation strings containing §. EV values are arrays "
        "of object operations with exactly citation (a literal citation string) and claim_value (a numeric expression). "
        "if has exactly [boolean condition, complete true branch, complete false branch]; both branches must type check. "
        "add/sub/min/max/lt/le take exact numbers. scale is [literal integer, numeric expression]; "
        "divide_constant is [numeric expression, nonzero literal integer]. Arrays use {op:array,args:[...]}; "
        "pair is [string key,value expression]; object takes pair operations as its args, never raw JSON fields. "
        "source_links maps current unit IDs to existing node names: query or binding:NAME (connector:i for connectors). "
        "Use actual cited lines for each input; cite all rule/exception lines needed for the query. "
        "Every scalar string must be an exact nonempty substring of its cited unit, never a paraphrase. "
        "A boolean binding is allowed only when its cited unit explicitly contains the standalone literal "
        "true or false. Assumptions, inferred states and absent information are not boolean inputs. "
        "Express rule conditions using comparisons on quoted inputs; otherwise leave the translation unsupported. "
        "Do not mark unrelated units compiled. Omitted units remain residual. Unknown semantics must remain unsupported, "
        "never replaced with a guessed rule. Interfaces use only the seven documented connector operators, or []. "
        "The complete example below illustrates syntax using an invented task. Its answer definition and "
        "facts belong only to that invented task. Read the CURRENT public question to determine all required "
        "components of its answer. Compile the current public task afresh.\n" +
        json.dumps(examples, ensure_ascii=False, separators=(",", ":")))
