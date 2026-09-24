"""Source-only H4 inventory. Never import a testcase to decide how to run it."""

import ast
from collections import Counter
import json
import os
from pathlib import Path
import hashlib
import re


REPOSITORY = Path(__file__).resolve().parents[1]
EXCLUDED = frozenset({"diagnose_phase_a_probe.py"})
A1 = frozenset("tests." + name for name in (
    "test_api_module_state", "test_storage_fixture", "test_phase_a_socketpair_isolation",
    "test_isolation_foundation", "test_isolation_results", "test_isolation_runner",
    "test_isolation_sqlite", "test_storage_fixture_runner",
))
OUT = frozenset("tests." + name for name in (
    "test_rate_limit", "test_credential_safe_logging", "test_billing_source_contract",
    "test_brand_image_assets", "test_mobile_runtime_source_checks",
))
COORDINATORS = frozenset("tests." + name for name in (
    "test_isolation_foundation", "test_isolation_results", "test_isolation_runner",
    "test_isolation_sqlite", "test_storage_fixture_runner", "test_full_test_entrypoint",
))
STAGE1 = "tests.test_full_test_entrypoint"
CLASSIFICATIONS = ("A1/foundation/helper", "migrated", "OUT")
BASELINE = dict(zip(CLASSIFICATIONS, (35, 393, 22)))


class InventoryError(ValueError):
    pass


def source_inventory(repository):
    """Collect direct declarations, not nested synthetic cases or loaded suites."""
    found = {}
    repository = Path(repository)
    for path in sorted((repository / "tests").rglob("*.py")):
        # Exclude before opening, parsing, or querying file contents.
        if path.name in EXCLUDED:
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(repository.resolve()):
            raise InventoryError("test source escapes repository")
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        module = ".".join(path.relative_to(repository).with_suffix("").parts)
        cases = [f"{cls.name}.{method.name}"
                 for cls in tree.body if isinstance(cls, ast.ClassDef)
                 for method in cls.body if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and method.name.startswith("test_")]
        if any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and
               node.name.startswith("test_") for node in tree.body):
            raise InventoryError("unsupported function testcase: " + module)
        if len(cases) != len(set(cases)):
            raise InventoryError("duplicate source testcase: " + module)
        if cases or path.name.startswith("test_"):
            if not cases:
                raise InventoryError("zero-test source module: " + module)
            found[module] = sorted(cases)
    return found


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InventoryError("duplicate manifest key")
        result[key] = value
    return result


def expected_skips(entry, platform=None):
    platform = os.name if platform is None else platform
    return {entry["module"] + "." + case: policy["reason"]
            for case, policy in entry["skips"].items()
            if policy["when"] == "always" or (policy["when"] == "non_windows" and platform != "nt")}


def validate_manifest(source, manifest):
    if manifest.get("version") != 1 or not isinstance(manifest.get("modules"), list):
        raise InventoryError("unsupported manifest schema")
    entries = {}
    for entry in manifest["modules"]:
        module = entry["module"]
        if module in entries:
            raise InventoryError("duplicate manifest module: " + module)
        cases = entry["cases"]
        if not cases or len(cases) != len(set(cases)):
            raise InventoryError("empty or duplicate manifest cases: " + module)
        if sorted(cases) != source.get(module):
            raise InventoryError("source/manifest testcase mismatch: " + module)
        if entry["execution_role"] not in {"guarded", "coordinator", "probe"}:
            raise InventoryError("unknown execution role")
        if entry["h4_classification"] not in (*CLASSIFICATIONS, None):
            raise InventoryError("unknown H4 classification")
        if entry["cohort"] not in {"baseline", "stage1", "probe"}:
            raise InventoryError("unknown cohort")
        for case, policy in entry["skips"].items():
            if case not in cases or policy.get("when") not in {"always", "non_windows"} or not policy.get("reason"):
                raise InventoryError("invalid expected skip")
        entries[module] = entry
    if set(source) != set(entries):
        raise InventoryError("unclassified source modules: " + ", ".join(sorted(set(source) - set(entries))))
    for entry in entries.values():
        if entry["execution_role"] == "probe":
            if entry["h4_classification"] is not None or entry["cohort"] != "probe" or entry["skips"]:
                raise InventoryError("invalid probe classification")
            owner = entry.get("owner")
            if owner:
                module, cls, method = owner.rsplit(".", 2)
                if (module not in entries or entries[module]["execution_role"] != "coordinator"
                        or cls + "." + method not in entries[module]["cases"]):
                    raise InventoryError("missing probe owner")
            outcome = entry.get("expected")
            if (not isinstance(outcome, dict) or type(outcome.get("passed")) is not bool
                    or type(outcome.get("returncode")) is not int or type(outcome.get("unexpected")) is not int
                    or outcome["unexpected"] < 0
                    or outcome["returncode"] != (0 if outcome["passed"] else 1)
                    or (not outcome["passed"] and not outcome["unexpected"])):
                raise InventoryError("missing probe outcome")
        elif entry["h4_classification"] is None or entry["cohort"] == "probe":
            raise InventoryError("invalid direct classification")
    return entries


def load_inventory(repository=REPOSITORY):
    repository = Path(repository)
    manifest = json.loads((repository / "tests/test_inventory.json").read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_object)
    entries = validate_manifest(source_inventory(repository), manifest)
    # Roles cannot turn arbitrary targets into an unguarded coordinator.
    for module, entry in entries.items():
        role = entry["execution_role"]
        if (role == "coordinator") != (module in COORDINATORS):
            raise InventoryError("coordinator role mismatch: " + module)
        if role == "probe":
            if not module.startswith("tests.isolation_"):
                raise InventoryError("invalid probe module")
            continue
        classification = "A1/foundation/helper" if module in A1 or module == STAGE1 else "OUT" if module in OUT else "migrated"
        if entry["h4_classification"] != classification or entry["cohort"] != ("stage1" if module == STAGE1 else "baseline"):
            raise InventoryError("H4 classification/cohort mismatch: " + module)
    baseline = Counter()
    for entry in entries.values():
        if entry["cohort"] == "baseline":
            baseline[entry["h4_classification"]] += len(entry["cases"])
    if baseline != BASELINE:
        raise InventoryError("baseline H4 classification changed")
    # The migrated list is source data, never imported without its boundary.
    tree = ast.parse((repository / "tests/test_storage_fixture_runner.py").read_text(encoding="utf-8"))
    migrated = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "STORAGE_MODULES" for target in node.targets))
    if set(migrated) != {module for module, entry in entries.items() if entry["h4_classification"] == "migrated"}:
        raise InventoryError("migrated module registry mismatch")
    return entries


def inventory_summary(entries):
    baseline, additions = Counter(), Counter()
    probes = 0
    for entry in entries.values():
        if entry["cohort"] == "probe":
            probes += len(entry["cases"])
        else:
            counts = baseline if entry["cohort"] == "baseline" else additions
            counts[entry["h4_classification"]] += len(entry["cases"])
    return {"baseline_classification": dict(baseline), "baseline_direct": sum(baseline.values()),
            "added_classification": dict(additions), "direct": sum(baseline.values()) + sum(additions.values()),
            "child_probes": probes, "modules": len(entries), "missing": 0, "duplicates": 0,
            "expected_skips": sum(len(expected_skips(entry)) for entry in entries.values())}


NODE_COMMAND = re.compile(r"node --test (scripts/[A-Za-z0-9_-]+\.test\.js)\Z")
NODE_SUPPORT = ("scripts/test-result-reporter.mjs", "scripts/test-entrypoint-guard.mjs")
NODE_PLUGIN_SOURCE = "node_modules/capacitor-plugin-cdv-purchase/android/build.gradle"
NODE_BILLING_FIXTURE = {
    "package": "capacitor-plugin-cdv-purchase",
    "version": "13.17.2",
    "resolved": "https://registry.npmjs.org/capacitor-plugin-cdv-purchase/-/capacitor-plugin-cdv-purchase-13.17.2.tgz",
    "integrity": "sha512-Iarfd5ZV2fzuiNRRqJR+JoX8JxPrMZVAAYyMwaaR/W7PmpsXDypD6wYO6wWsHJ7D3/XbRXbJftHSdzvMRvJldA==",
    "member": "package/android/build.gradle",
    "source": "scripts/fixtures/cdv-purchase-13.17.2/android/build.gradle",
    "destination": NODE_PLUGIN_SOURCE,
    "size": 1345,
    "sha256": "177796cb397239621bbefcff7638a37d4c74c5e64fbb241f28e20a94f2b056d0",
}


def validated_node_fixture(frontend, entry):
    """Offline, byte-exact pinned dependency contract; never install or fetch.

    Return the same verified bytes that the coordinator must copy. This is a
    release-source snapshot check, not evidence about an installed Android build.
    """
    if entry["name"] != "test:android-billing":
        if "fixture" in entry:
            raise InventoryError("unexpected Node fixture mapping")
        return None
    provenance = entry.get("fixture")
    if provenance != NODE_BILLING_FIXTURE:
        raise InventoryError("Node fixture provenance/destination mismatch")
    lock_path = Path(frontend) / "package-lock.json"
    if lock_path.is_symlink() or not lock_path.resolve().is_relative_to(Path(frontend).resolve()):
        raise InventoryError("Node lockfile escapes frontend")
    lock = json.loads(lock_path.read_bytes(), object_pairs_hook=_unique_object)
    package = lock.get("packages", {}).get("node_modules/" + provenance["package"], {})
    if any(package.get(key) != provenance[key] for key in ("version", "resolved", "integrity")):
        raise InventoryError("Node fixture lockfile mismatch")
    content = node_source_path(frontend, provenance["source"]).read_bytes()
    if len(content) != provenance["size"] or hashlib.sha256(content).hexdigest() != provenance["sha256"]:
        raise InventoryError("Node fixture bytes mismatch")
    return provenance["destination"], content


def node_source_path(frontend, relative):
    """An exact manifest source path, never an env/private tree or a directory copy."""
    if not isinstance(relative, str) or "\\" in relative or ".." in relative.split("/"):
        raise InventoryError("invalid Node source path")
    path = Path(relative)
    special = {"package.json", "capacitor.config.json", ".env.example", ".env.release.example"}
    source = (relative.startswith(("scripts/", "src/", "android/")) or relative in {"index.html", "vite.config.js"})
    if (path.is_absolute() or not (relative in special or source and path.suffix in
            {".js", ".mjs", ".jsx", ".css", ".html", ".xml", ".java", ".gradle"})
            or any(part.startswith(".") for part in path.parts) and relative not in special):
        raise InventoryError("non-source Node read rejected")
    frontend = Path(frontend).resolve()
    target = frontend / path
    if target.is_symlink() or not target.resolve().is_relative_to(frontend):
        raise InventoryError("Node source escapes frontend")
    return target


def node_source_hash(source):
    return hashlib.sha256(source.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def node_case_names(source):
    # Reviewed literal top-level declarations; the source hash locks the entire
    # grammar/content, including aliases or dynamic code not matched here.
    literals = re.findall(r'''^test\(("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')\s*,''', source, re.MULTILINE)
    names = [ast.literal_eval(value) for value in literals]
    if not names or len(names) != len(set(names)):
        raise InventoryError("empty/duplicate Node source testcase")
    return names


def load_node_inventory(repository=REPOSITORY):
    repository = Path(repository)
    manifest = json.loads((repository / "tests/test_inventory.json").read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_object)
    return validate_node_inventory(repository / "frontend", manifest["node"])


def validate_node_inventory(frontend, manifest):
    frontend = Path(frontend)
    package = json.loads((frontend / "package.json").read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    scripts = {name: command for name, command in package["scripts"].items() if name.startswith("test:")}
    if manifest.get("version") != 1 or not scripts:
        raise InventoryError("invalid Node inventory")
    entries, files = {}, set()
    for entry in manifest["entries"]:
        name = entry["name"]
        command = scripts.get(name)
        match = NODE_COMMAND.fullmatch(command) if isinstance(command, str) else None
        if (not match or name in entries or entry["file"] in files or match[1] != entry["file"]
                or entry["command"] != command):
            raise InventoryError("Node entrypoint missing/duplicate/command mismatch")
        source = node_source_path(frontend, entry["file"]).read_text(encoding="utf-8")
        if node_source_hash(source) != entry["sha256"] or node_case_names(source) != entry["cases"]:
            raise InventoryError("Node source/manifest testcase mismatch")
        profile = "release" if name in {"test:release-env", "test:mobile-bundle"} else "standard"
        if entry["profile"] != profile:
            raise InventoryError("invalid Node isolation profile")
        reads = entry["reads"]
        if len(reads) != len(set(reads)) or not {"package.json", entry["file"]} <= set(reads):
            raise InventoryError("invalid Node source snapshot")
        for relative in reads:
            node_source_path(frontend, relative)  # No private reads to validate the boundary.
        validated_node_fixture(frontend, entry)
        if profile == "standard" and entry["release_eval_sha256"]:
            raise InventoryError("standard tests cannot launch children")
        entries[name] = entry
        files.add(entry["file"])
    source_files = {"scripts/" + path.name for path in (frontend / "scripts").glob("*.test.js")}
    if set(entries) != set(scripts) or files != source_files:
        raise InventoryError("Node source/package/manifest missing or extra entrypoint")
    return entries


def node_inventory_summary(entries, frontend=None):
    missing = []
    if frontend is not None:
        missing = sorted({relative for entry in entries.values() for relative in entry["reads"]
                          if not node_source_path(frontend, relative).is_file()})
    return {"entrypoints": len(entries), "direct": sum(len(entry["cases"]) for entry in entries.values()),
            "missing": 0, "duplicate": 0, "extra": 0, "missing_source_dependencies": missing}
