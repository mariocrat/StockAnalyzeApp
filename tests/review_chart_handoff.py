"""Synthetic real route/storage/adapter -> production frontend chart handoff."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

REPOSITORY = Path(__file__).resolve().parents[1]
HANDOFF = "scripts/fixtures/generated-review-chart-results.json"
STAGES = ("basic", "advanced", "failures", "titles", "paired")
SECTIONS = {"results": list, "body_results": list, "failures": dict, "legacy": dict,
            "history_titles": list, "v2_results": list}


def validate_stage(stage, report):
    owned = {"basic": {"results", "body_results"}, "advanced": {"results", "body_results"},
             "failures": {"failures", "legacy"}, "titles": {"history_titles"}, "paired": {"v2_results"}}
    if (type(report) is not dict or set(report) != set(SECTIONS) | {
            "stage", "passed", "unexpected", "restored", "patches_restored"}
            or report["stage"] != stage or stage not in owned
            or any(report[key] is not True for key in ("passed", "restored", "patches_restored"))
            or type(report["unexpected"]) is not int or report["unexpected"] != 0
            or any(type(report[key]) is not kind for key, kind in SECTIONS.items())
            or any(report[key] for key in SECTIONS if key not in owned[stage])):
        raise ValueError("chart handoff stage lifecycle/coverage mismatch")
    if stage in ("basic", "advanced"):
        valid = ([row.get("review_type") for row in report["results"]] == [stage]
                 and [(row.get("review_type"), row.get("body_case")) for row in report["body_results"]]
                 == [(stage, shape) for shape in ("plain", "strong")])
    elif stage == "failures":
        valid = (set(report["failures"]) == {"safety", "invalid", "compatibility"}
                 and set(report["legacy"]) == {"safe", "chart", "tooltip", "trade", "canonical"})
    elif stage == "titles":
        valid = ([row.get("case") for row in report["history_titles"]]
                 == ["new", "legacy_canonical", "legacy_adapted"] * 3 + ["legacy_unavailable"])
    else:
        valid = [row.get("review_type") for row in report["v2_results"]] == ["basic", "advanced"]
    if not valid:
        raise ValueError("chart handoff stage lifecycle/coverage mismatch")


def prepare_chart_results(root, host):
    from tests.module_isolation import protected_paths, sanitized_environment

    report = {key: kind() for key, kind in SECTIONS.items()}
    stage_results = {}
    # Independent evidence cohorts keep their original 60-second child budget.
    # Every cohort runs the same H4 boundary and must finish before publication.
    for stage in STAGES:
        runtime = root / "tmp" / ("chart-backend-" + stage)
        started = time.perf_counter()
        process = subprocess.run(
            [sys.executable, "-I", "-X", "utf8", "-B", str(Path(__file__).resolve()), str(runtime), stage],
            cwd=root, env=sanitized_environment(host, runtime),
            input=json.dumps(protected_paths(host).metadata()), capture_output=True,
            text=True, encoding="utf-8", timeout=60,
        )
        if process.returncode:
            raise ValueError("chart route handoff child failed: " + process.stderr[-3000:])
        partial = json.loads(process.stdout)
        validate_stage(stage, partial)
        for key in SECTIONS:
            if type(report[key]) is list:
                report[key].extend(partial[key])
            else:
                report[key].update(partial[key])
        stage_results[stage] = {key: partial[key] for key in ("passed", "unexpected", "restored", "patches_restored")}
        stage_results[stage]["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    report.update(passed=True, unexpected=0, restored=True, patches_restored=True)
    if (report.get("passed") is not True or report.get("unexpected") != 0
            or any(report.get(key) is not True for key in ("restored", "patches_restored"))
            or [row.get("review_type") for row in report.get("results", [])] != ["basic", "advanced"]
            or [(row.get("review_type"), row.get("body_case")) for row in report.get("body_results", [])]
                != [(kind, shape) for kind in ("basic", "advanced") for shape in ("plain", "strong")]
            or [row.get("review_type") for row in report.get("v2_results", [])] != ["basic", "advanced"]
            or set(report.get("failures", {})) != {"safety", "invalid", "compatibility"}):
        raise ValueError("chart handoff lifecycle/coverage mismatch")
    destination = root / HANDOFF
    if destination.exists():
        raise ValueError("chart handoff collision")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return {**{key: report[key] for key in ("passed", "unexpected", "restored", "patches_restored")},
            "stages": stage_results}


def child(runtime, stage):
    if stage not in STAGES:
        raise ValueError("unknown chart handoff stage")
    sys.path.insert(0, str(REPOSITORY))
    from backend.core.review_display_contract import SCHEMA_VERSION
    from tests.module_isolation import Boundary, ProtectedPaths, isolated_module

    protected = ProtectedPaths(**json.loads(sys.stdin.read()))
    boundary = Boundary(runtime, protected)
    baseline = Path.cwd(), dict(os.environ), tempfile.tempdir
    results, body_results, failures, legacy, history_titles, v2_results = [], [], {}, {}, [], []
    with isolated_module(runtime, protected, boundary=boundary):
        # Reuse fixture/setup/assertions, never clone the generation/route/adapter.
        from tests.test_review_route_compatibility import ProductionRouteCompatibilityTest, model_output
        from tests.test_review_history_adapter import legacy_record, canonical_record, UNSAFE
        from tests.review_source_fixtures import approved_chart_fixture, history_chart_fixture
        from backend.core.review_history_adapter import history_list_projection
        import copy

        case = ProductionRouteCompatibilityTest()
        try:
            case.setUp()
            def collect(review_type, *, named_chart=None, output=None):
                if named_chart is None and output is None:
                    response, expected = case.chart_route(review_type)
                else:
                    case.compact_provider.return_value = named_chart if named_chart is not None else approved_chart_fixture()
                    response = case.run_route(review_type, storage=True, output=output)
                    sealed = json.loads(case.last[3]["snapshot"].json_text)
                    expected = {key: sealed[key] for key in ("charts", "chart_cards")}
                identity = response["review_history_id"]
                exported = next(row for row in case.main.export_me_data(authorization=case.token, x_review_display_contract=[SCHEMA_VERSION])["review_history"]
                                if row["id"] == identity)
                saved = case.history.get_review_history(identity, user_id=case.user_id)
                return {
                    "review_type": review_type, "response": response, "snapshot": expected,
                    "replay": case.last_replay, "replay_effects": case.last_replay_effects,
                    "cache": case.last[2]["result"], "exported": exported,
                    "saved": saved, "saved_admitted": case.ai.safe_legacy_history_snapshot(saved),
                    "detail": case.main.get_journal_review_history_detail(identity, authorization=case.token, x_review_display_contract=[SCHEMA_VERSION]),
                    "listed": next(row for row in case.main.get_journal_review_history(
                        authorization=case.token, x_review_display_contract=[SCHEMA_VERSION]) if row["id"] == identity),
                    "general": case.charts,
                }
            for review_type in ((stage,) if stage in ("basic", "advanced") else ()):
                results.append(collect(review_type))
            for review_type in ((stage,) if stage in ("basic", "advanced") else ()):
                for shape in ("plain", "strong"):
                    output = model_output(review_type)
                    output["main_issue"] = "**체결 기록**을 확인합니다." if shape == "strong" else "체결 기록을 확인합니다."
                    row = collect(review_type, output=output)
                    row["body_case"] = shape
                    body_results.append(row)
            for mode in (("safety", "invalid", "compatibility") if stage == "failures" else ()):
                output = model_output("basic")
                output["main_issue"] = UNSAFE if mode == "safety" else "MA20을 확인했습니다."
                failures[mode] = case.run_route(
                    "basic", output=output, raw="{" if mode == "invalid" else None,
                    status="error", internal="safety_rejected" if mode == "safety" else "invalid_structured_output",
                    storage=True, bodyless=mode in {"invalid", "compatibility"},
                )
            if stage == "failures":
                safe_legacy = legacy_record()
                safe_legacy["ai_review"]["chart_reviews"] = safe_legacy["chart_snapshot"]["chart_reviews"]
                legacy["safe"] = case.ai.safe_legacy_history_snapshot(safe_legacy)
            for surface in (("chart", "tooltip", "trade", "canonical") if stage == "failures" else ()):
                record = canonical_record()
                if surface == "chart": record["chart_snapshot"]["charts"][0]["name"] = UNSAFE
                elif surface == "tooltip": record["chart_snapshot"]["charts"][0]["markers"][0]["tooltip"]["label"] = UNSAFE
                elif surface == "trade": record["trade_snapshot"]["memo"] = UNSAFE
                else: record["ai_review"]["display_snapshot"]["schema_version"] = "review-display.v99"
                legacy[surface] = case.ai.safe_legacy_history_snapshot(record)
                case.assertEqual("unavailable", legacy[surface]["history_read_status"])
            case.doCleanups()
            for name in (("합성  이중  공백", "**합성** [이름](label) # 1", "합성  e\u0301 😀 한글") if stage == "titles" else ()):
                # Each F4 name gets fresh owned storage/account/quota state.
                case = ProductionRouteCompatibilityTest()
                case.setUp()
                for trade in case.trades:
                    trade["name"] = name
                case.charts = history_chart_fixture(case.trades)
                case.general_chart_provider.return_value = case.charts
                named_chart = approved_chart_fixture()
                named_chart["name"] = name
                row = collect("basic", named_chart=named_chart)
                row["case"] = "new"
                case.assertEqual(row["listed"]["display_snapshot"], row["detail"]["display_snapshot"])
                case.assertEqual(row["snapshot"], row["detail"]["ai_review"]["chart_display_snapshot"])
                history_titles.append(row)
                for status, factory in (("canonical", canonical_record), ("adapted", legacy_record)):
                    record = factory()
                    record["name"] = record["trade_snapshot"]["name"] = name
                    record["recent_trades_snapshot"][0]["name"] = name
                    chart = record["chart_snapshot"]["charts"][0]
                    chart["name"] = name
                    second = copy.deepcopy(chart)
                    second.update(ticker="000660", name=name + "  두번째")
                    record["chart_snapshot"]["charts"].append(second)
                    detail = case.ai.safe_legacy_history_snapshot(record)
                    case.assertEqual(status, detail["history_read_status"])
                    history_titles.append({"case": "legacy_" + status, "detail": detail,
                                           "listed": history_list_projection(detail)})
                if len(history_titles) == 9:
                    record = canonical_record()
                    record["chart_snapshot"]["charts"][0]["name"] = UNSAFE
                    detail = case.ai.safe_legacy_history_snapshot(record)
                    case.assertEqual("unavailable", detail["history_read_status"])
                    history_titles.append({"case": "legacy_unavailable", "detail": detail,
                                           "listed": history_list_projection(detail)})
                case.doCleanups()
        finally:
            case.doCleanups()
        # Synthetic paired issuance only: production generation remains v1-only.
        # Capture the SAME approved bundle through actual cache/SQL/HTTP boundaries.
        if stage == "paired":
            from tests import test_review_display_negotiation as negotiation
            from tests.test_review_durable_storage import assemble
            from backend.core.review_source_projection import trade_payload
        paired_case = negotiation.ReviewDisplayNegotiationTest() if stage == "paired" else None
        try:
            if paired_case is not None:
                paired_case.setUp()
            for kind in (("basic", "advanced") if stage == "paired" else ()):
                _, seed = paired_case.cache.seed(kind)
                value = paired_case.history.value(kind)
                access = copy.deepcopy(seed["result"]["access"])
                value["record"]["ai_review"]["access"] = access
                value["record"]["access_snapshot"] = copy.deepcopy(access)
                value = assemble(value["source"], value["snapshot"], value["prepared"], value["record"])
                committed = paired_case.history.save(value)
                batch = paired_case.main.JournalAiReviewIn(privacy_consent=True, review_type=kind,
                    trades=[paired_case.main.JournalTradeIn(**trade_payload(trade)) for trade in value["source"].trades])
                key = "slice5-paired-handoff-" + kind
                cache_key, _ = paired_case.main._begin_ai_review_idempotency(paired_case.case.token, key,
                    paired_case.main._ai_review_payload_fingerprint(batch))
                result = copy.deepcopy(value["record"]["ai_review"])
                result["review_history_id"] = committed.id
                paired_case.main._finish_ai_review_idempotency(cache_key, result,
                    snapshot=value["snapshot"], bundle=value["bundle"])
                before, wallet = paired_case.http.history_state(), paired_case.case.balance(kind)
                response = paired_case.replay(key, batch, negotiation.DUAL)
                v1 = paired_case.replay(key, batch, negotiation.V1)
                with paired_case.http.no_effects(lookup=False, reads=False) as effects:
                    detail = paired_case.http.request("GET", f"/api/journal/review-history/{committed.id}", negotiation.DUAL)
                    listed = paired_case.http.request("GET", "/api/journal/review-history", negotiation.DUAL)
                    exported = paired_case.http.request("GET", "/api/me/export-data", negotiation.DUAL)
                for received in (detail, listed, exported):
                    paired_case.assertEqual(received.status_code, 200)
                paired_case.assertTrue(all(spy.call_count == 0 for spy in effects.values()))
                paired_case.assertEqual(before, paired_case.http.history_state())
                paired_case.assertEqual(wallet, paired_case.case.balance(kind))
                v2_results.append({"review_type": kind, "response": response, "v1": v1,
                    "snapshot": value["record"]["ai_review"]["chart_display_snapshot"], "detail": detail.json(),
                    "listed": next(row for row in listed.json() if row["id"] == committed.id),
                    "exported": next(row for row in exported.json()["review_history"] if row["id"] == committed.id),
                    "replay_effects": {"ai": 0, "charge": 0, "history_insert": 0}})
        finally:
            if paired_case is not None:
                paired_case.doCleanups()
    restored = (Path.cwd(), dict(os.environ), tempfile.tempdir) == baseline
    report = {"stage": stage, "results": results, "body_results": body_results, "failures": failures, "legacy": legacy,
              "history_titles": history_titles, "v2_results": v2_results,
              "unexpected": boundary.unexpected, "restored": restored,
              "patches_restored": boundary.patches_restored}
    report["passed"] = restored and boundary.patches_restored and boundary.unexpected == 0
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(child(Path(sys.argv[1]).resolve(), sys.argv[2]))
