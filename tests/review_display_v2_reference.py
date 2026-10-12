"""Test-only reference contract. Shared schema is authoritative; never runtime-import."""
import copy
import json
import re


def require(ok, message="contract violation"):
    if not ok:
        raise ReferenceContractError(message)


class ReferenceContractError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def stable(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _exact(value, keys, path):
    require(type(value) is dict, "INVALID_TYPE")
    require(not (set(value) - set(keys)), "UNKNOWN_KEY")
    missing = set(keys) - set(value)
    if missing:
        code = ("MISSING_BLOCK_ID" if path.startswith("$.blocks[") and "id" in missing else
                "V1_MISSING" if path == "$.representations" and "v1" in missing else
                "V2_MISSING" if path == "$.representations" and "v2" in missing else "MISSING_FIELD")
        require(False, code)


def _scalar_code(path, issue):
    if path.endswith(".role"):
        return "WRONG_SECTION_ORDER"
    if path.endswith(".compiler_version"):
        return "COMPILER_VERSION_MISMATCH"
    if path.endswith(".schema_version"):
        return "INVALID_VERSION"
    if path.endswith(".surface"):
        return "INVALID_SURFACE"
    if path.endswith(".review_type"):
        return "INVALID_REVIEW_TYPE"
    if path.endswith(".status"):
        return "INVALID_BUNDLE_STATUS"
    if path.endswith(".level"):
        return "INVALID_CONFIDENCE"
    if path.endswith(".phase"):
        return "INVALID_PHASE"
    if path.endswith(".separator_after"):
        return "INVALID_SEPARATOR"
    if path.endswith(".type"):
        return "INVALID_RUN_TYPE" if ".runs[" in path else "INVALID_BLOCK_TYPE"
    if path.endswith(".id"):
        return "INVALID_BLOCK_ID"
    if path.endswith("_identity"):
        return "INVALID_IDENTITY"
    return "INVALID_REFERENCE" if issue == "pattern" else "INVALID_TYPE"


def schema_check(value, rule, path="$"):
    require(rule is not False, "INVALID_TYPE")
    if "oneOf" in rule:
        discriminator = "kind" if any("kind" in r["properties"] for r in rule["oneOf"]) else "review_type"
        require(type(value) is dict, "INVALID_TYPE")
        match = next((r for r in rule["oneOf"] if value.get(discriminator) ==
                      r["properties"][discriminator]["const"]), None)
        require(match is not None, "INVALID_BUNDLE_KIND" if discriminator == "kind" else "INVALID_REVIEW_TYPE")
        schema_check(value, match, path)
        return
    if "const" in rule:
        require(value == rule["const"], _scalar_code(path, "const"))
    if "enum" in rule:
        require(value in rule["enum"], _scalar_code(path, "enum"))
    kind = rule.get("type")
    if kind == "object":
        require(type(value) is dict, "INVALID_TYPE")
        if "properties" in rule:
            _exact(value, rule["required"], path)
            for key, child in rule["properties"].items():
                schema_check(value[key], child, path + "." + key)
    elif kind == "array":
        require(type(value) is list, "INVALID_MISSING_INFORMATION" if path.endswith(".missing_information") else "INVALID_TYPE")
        require(rule["minItems"] <= len(value) <= rule["maxItems"],
                "WRONG_SECTION_ORDER" if path == "$.sections" else "LIMIT_EXCEEDED")
        for i, child in enumerate(value):
            schema_check(child, rule["prefixItems"][i] if "prefixItems" in rule else rule["items"], f"{path}[{i}]")
    elif kind == "string":
        require(type(value) is str, "INVALID_REFERENCE" if rule.get("x-block-ref") else "INVALID_TYPE")
        require(rule.get("minLength", 0) <= len(value) <= rule.get("maxLength", float("inf")), "LIMIT_EXCEEDED")
        if "pattern" in rule:
            require(re.fullmatch(rule["pattern"], value) is not None, _scalar_code(path, "pattern"))


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
                     or 0xD800 <= ord(c) <= 0xDFFF) for c in text), "INVALID_UNICODE")


def validate_v2(doc, schema):
    _exact(doc, ("schema_version", "surface", "review_type", "blocks", "sections", "canonical_text"), "$")
    require(doc["schema_version"] == "review-display.v2", "INVALID_VERSION")
    require(doc["surface"] == "body", "INVALID_SURFACE")
    shape = next((s for s in schema["oneOf"] if s["properties"]["review_type"]["const"] == doc["review_type"]), None)
    require(shape is not None, "INVALID_REVIEW_TYPE")
    rules = shape["properties"]["sections"]["prefixItems"]
    require(type(doc["sections"]) is list, "INVALID_TYPE")
    require(len(doc["sections"]) == len(rules), "WRONG_SECTION_ORDER")
    vocabulary = {r["properties"]["role"]["const"] for s in schema["oneOf"]
                  for r in s["properties"]["sections"]["prefixItems"]}
    for section, rule in zip(doc["sections"], rules):
        require(type(section) is dict, "INVALID_TYPE")
        require(type(section.get("role")) is str and section["role"] in vocabulary, "UNKNOWN_ROLE")
        require(section["role"] == rule["properties"]["role"]["const"], "WRONG_SECTION_ORDER")
    schema_check(doc, schema)
    ids = [b["id"] for b in doc["blocks"]]
    require(len(set(ids)) == len(ids), "DUPLICATE_BLOCK_ID")
    require(sum(len(b["runs"]) for b in doc["blocks"]) <= 512, "LIMIT_EXCEEDED")
    for block in doc["blocks"]:
        if block["type"] == "divider":
            require(len(block["runs"]) == 1 and block["runs"][0]["type"] == "text", "INVALID_DIVIDER")
        for run in block["runs"]:
            check_text(run["text"])
    owned = [ref for section in doc["sections"] for ref in section["block_ids"]]
    require(len(set(owned)) == len(owned), "DUPLICATE_OWNERSHIP")
    require(set(owned) <= set(ids), "MISSING_BLOCK_REFERENCE")
    require(set(ids) <= set(owned), "ORPHAN_BLOCK")
    for section, rule in zip(doc["sections"], rules):
        refs = references(section, rule)
        require(set(refs) <= set(ids), "MISSING_BLOCK_REFERENCE")
        require(len(set(refs)) == len(refs), "DUPLICATE_BLOCK_REFERENCE")
        require(set(refs) <= set(section["block_ids"]), "FOREIGN_SECTION_REFERENCE")
        require(refs == section["block_ids"], "WRONG_REFERENCE_ORDER")
    require(ids == owned, "WRONG_BLOCK_ORDER")
    check_text(doc["canonical_text"])
    require(flatten(doc) == doc["canonical_text"], "CANONICAL_TEXT_MISMATCH")
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
    try:
        validate_v1(v1["document"])
    except ValueError as error:
        raise ReferenceContractError("V1_DOCUMENT_INVALID") from error
    require(v1["summary"] == witness["expected_summary"], "A1_SUMMARY_MISMATCH")
    require(bundle["review_type"] == witness["source"]["review_type"], "REVIEW_TYPE_MISMATCH")
    if bundle["kind"] == "paired_v1_v2":
        validate_v2(bundle["representations"]["v2"]["document"], schema)
        for version, rep in bundle["representations"].items():
            require(rep["review_type"] == bundle["review_type"], "REVIEW_TYPE_MISMATCH")
            require(rep["source_identity"] == bundle["source_identity"], "SOURCE_IDENTITY_MISMATCH")
            require(rep["objective_identity"] == bundle["objective_identity"], "OBJECTIVE_IDENTITY_MISMATCH")
        for key, code in (("source_identity", "SOURCE_IDENTITY_MISMATCH"),
                          ("objective_identity", "OBJECTIVE_IDENTITY_MISMATCH")):
            require(bundle[key] == witness[key], code)
    for version, rep in bundle["representations"].items():
        require(stable(rep["document"]) == stable(witness[f"expected_{version}"]), "COMPILER_OUTPUT_MISMATCH")
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
