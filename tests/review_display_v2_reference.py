"""Test-only reference contract. Shared schema is authoritative; never runtime-import."""
import copy
import json
import re


def require(ok, message="contract violation"):
    if not ok:
        raise ValueError(message)


def stable(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def schema_check(value, rule):
    require(rule is not False)
    if "oneOf" in rule:
        matches = 0
        for candidate in rule["oneOf"]:
            try:
                schema_check(value, candidate)
                matches += 1
            except ValueError:
                pass
        require(matches == 1, "oneOf")
        return
    if "const" in rule:
        require(value == rule["const"], "const")
    if "enum" in rule:
        require(value in rule["enum"], "enum")
    kind = rule.get("type")
    if kind == "object":
        require(type(value) is dict, "object")
        if "properties" in rule:
            require(set(value) == set(rule["required"]), "exact keys")
            for key, child in rule["properties"].items():
                schema_check(value[key], child)
    elif kind == "array":
        require(type(value) is list and rule["minItems"] <= len(value) <= rule["maxItems"], "array")
        for i, child in enumerate(value):
            schema_check(child, rule["prefixItems"][i] if "prefixItems" in rule else rule["items"])
    elif kind == "string":
        require(type(value) is str, "string")
        require(rule.get("minLength", 0) <= len(value) <= rule.get("maxLength", float("inf")), "text bounds")
        if "pattern" in rule:
            require(re.fullmatch(rule["pattern"], value) is not None, "pattern")


def references(value, rule):
    if rule.get("x-block-ref"):
        return [value]
    if rule.get("type") == "array":
        return [ref for child in value for ref in references(child, rule["items"])]
    if rule.get("type") == "object":
        return [ref for key in rule["x-field-order"]
                for ref in references(value[key], rule["properties"][key])]
    return []


def flatten(doc):
    return "".join("".join(run["text"] for run in block["runs"]) + block["separator_after"]
                   for block in doc["blocks"])


def check_text(text):
    require(all(not (ord(c) < 9 or 10 < ord(c) < 32 or ord(c) == 127
                     or 0xD800 <= ord(c) <= 0xDFFF) for c in text), "character")


def validate_v2(doc, schema):
    schema_check(doc, schema)
    shape = next(s for s in schema["oneOf"] if s["properties"]["review_type"]["const"] == doc["review_type"])
    owned = []
    for section, rule in zip(doc["sections"], shape["properties"]["sections"]["prefixItems"]):
        require(references(section, rule) == section["block_ids"], "field ownership/order")
        owned.extend(section["block_ids"])
    ids = [block["id"] for block in doc["blocks"]]
    require(len(set(ids)) == len(ids) and len(set(owned)) == len(owned), "unique ownership")
    require(ids == owned, "document ownership/order")
    require(sum(len(b["runs"]) for b in doc["blocks"]) <= 512, "run total")
    for block in doc["blocks"]:
        if block["type"] == "divider":
            require(len(block["runs"]) == 1 and block["runs"][0]["type"] == "text", "divider")
        for run in block["runs"]:
            check_text(run["text"])
        check_text(block["separator_after"])
    check_text(doc["canonical_text"])
    require(flatten(doc) == doc["canonical_text"], "canonical identity")
    return doc


def make_bundle(witness, kind="paired_v1_v2"):
    bundle = dict(schema_version="review-approval-bundle.v1", kind=kind,
                  review_type=witness["source"]["review_type"], status="ready",
                  representations={"v1": {"document": copy.deepcopy(witness["expected_v1"]),
                                          "summary": witness["expected_summary"]}})
    if kind == "paired_v1_v2":
        for key in ("source_identity", "objective_identity"):
            bundle[key] = witness[key]
        for version in ("v1", "v2"):
            rep = dict(compiler_version=f"review-body.{version}.0",
                       source_identity=witness["source_identity"],
                       objective_identity=witness["objective_identity"],
                       review_type=witness["source"]["review_type"],
                       document=copy.deepcopy(witness[f"expected_{version}"]))
            if version == "v1":
                rep["summary"] = witness["expected_summary"]
            bundle["representations"][version] = rep
    return bundle


def validate_bundle(bundle, witness, schema, validate_v1):
    schema_check(bundle, schema["$defs"]["bundle"])
    v1 = bundle["representations"]["v1"]
    validate_v1(v1["document"])
    require(v1["summary"] == witness["expected_summary"] and v1["document"] == witness["expected_v1"],
            "v1 compiler/A1")
    require(bundle["review_type"] == witness["source"]["review_type"], "review type")
    if bundle["kind"] == "paired_v1_v2":
        validate_v2(bundle["representations"]["v2"]["document"], schema)
        for key in ("source_identity", "objective_identity"):
            require(bundle[key] == witness[key], "source/objective identity")
        for version, rep in bundle["representations"].items():
            require(rep["source_identity"] == witness["source_identity"]
                    and rep["objective_identity"] == witness["objective_identity"]
                    and rep["review_type"] == bundle["review_type"], "representation provenance")
            require(rep["document"] == witness[f"expected_{version}"], "compiler output/coverage")
    return bundle


def at(value, path):
    for key in path:
        value = value[key]
    return value


def mutate(base, operations):
    result = copy.deepcopy(base)
    for op in operations:
        path = op["path"]
        if op["op"] == "swap":
            target = at(result, path)
            left, right = op["left"], op["right"]
            target[left], target[right] = target[right], target[left]
        elif op["op"] == "remove":
            at(result, path).pop(op["index"])
        elif op["op"] == "reflatten":
            target = at(result, path)
            target["canonical_text"] = flatten(target)
        elif op["op"] == "delete":
            del at(result, path[:-1])[path[-1]]
        else:
            require(op["op"] == "set")
            at(result, path[:-1])[path[-1]] = copy.deepcopy(op["value"])
    return result


def replay(*, capability, record, witness, schema, validate_v1, same_body=True, trace=None):
    trace = [] if trace is None else trace
    trace.append("capability_gate")
    require(capability in ("v1", "dual"), "unsupported capability")
    trace.append("execution_identity")
    require(same_body, "idempotency conflict")
    if record is None:
        trace.append("no_replay")
        return {"kind": "new_execution_requires_normal_gates"}
    trace.append("bundle_validation")
    validate_bundle(record, witness, schema, validate_v1)
    trace.append("representation_selection")
    version = "v2" if capability == "dual" and record["kind"] == "paired_v1_v2" else "v1"
    trace.append("projection")
    return dict(version=version, document=copy.deepcopy(record["representations"][version]["document"]),
                ai=0, charge=0, history_insert=0)


def generation(row):
    return ("paired_v1_v2" if row["phase"] == "activation" and row["status"] == "ready"
            and row["body"] == "structured" else "v1_only")
