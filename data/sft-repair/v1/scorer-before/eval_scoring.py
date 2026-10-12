"""Shared binary scoring engine; all business rules are supplied by adapters."""

import json
from collections import Counter


class ScoringError(RuntimeError):
    def __init__(self, stage, error_code, message, retryable=False, details=None):
        super().__init__(message)
        self.stage = stage
        self.error_code = error_code
        self.retryable = retryable
        self.details = details if isinstance(details, dict) else {}

    def record(self, sample=None):
        seed = sample.get("seed", {}) if isinstance(sample, dict) else {}
        record = {
            "event": "sample_scoring_error",
            "sample_id": sample.get("sample_id") if isinstance(sample, dict) else None,
            "template_id": seed.get("template_id"),
            "stage": self.stage,
            "error_code": self.error_code,
            "exception_type": type(self).__name__,
            "message": str(self),
            "retryable": self.retryable,
        }
        if self.details:
            record["details"] = self.details
        return record


def apply_judgments(checks, requests, response):
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except ValueError as exc:
            raise ScoringError(
                "judge_response", "invalid_judge_json", "评分模型没有返回合法JSON", True
            ) from exc
    if not isinstance(response, dict) or not isinstance(response.get("results"), list):
        raise ScoringError(
            "judge_response", "invalid_judge_json", "评分响应缺少results数组", True
        )
    expected, received = {item["key"]: item for item in requests}, {}
    for result in response["results"]:
        key = result.get("key") if isinstance(result, dict) else None
        if key not in expected or key in received:
            raise ScoringError(
                "judge_response",
                "invalid_judge_key",
                "评分响应包含未知或重复key",
                True,
                {"key": key, "expected_keys": sorted(expected)},
            )
        received[key] = result
    if set(received) != set(expected):
        raise ScoringError(
            "judge_response",
            "missing_judge_item",
            "评分模型遗漏检查项",
            True,
            {
                "expected_keys": sorted(expected),
                "received_keys": sorted(received),
            },
        )
    updates = {}
    for key, request in expected.items():
        result = received[key]
        status, reason, proof = (
            result.get("status"),
            result.get("reason"),
            result.get("evidence"),
        )
        if (
            status not in {"pass", "fail"}
            or not isinstance(reason, str)
            or not reason.strip()
            or not isinstance(proof, list)
            or not proof
        ):
            raise ScoringError(
                "judge_response",
                "invalid_judge_status",
                "评分状态、理由或证据无效",
                True,
                {
                    "key": key,
                    "status": status,
                    "reason_is_nonempty_string": isinstance(reason, str) and bool(reason.strip()),
                    "evidence_is_nonempty_list": isinstance(proof, list) and bool(proof),
                },
            )
        reply_evidence = False
        for evidence_index, item in enumerate(proof):
            index, quote = (
                (item.get("message_index"), item.get("quote"))
                if isinstance(item, dict)
                else (None, None)
            )
            if (
                type(index) is not int
                or not 0 <= index < len(request["messages"])
                or not isinstance(quote, str)
                or not quote
                or quote not in (request["messages"][index].get("content") or "")
            ):
                raise ScoringError(
                    "judge_response",
                    "invalid_judge_evidence",
                    "评分证据不是合法消息原文",
                    True,
                    {
                        "key": key,
                        "evidence_index": evidence_index,
                        "message_index": index,
                        "message_count": len(request["messages"]),
                        "reply_indices": request["reply_indices"],
                        "validation": (
                            "message_index_invalid"
                            if type(index) is not int
                            or not 0 <= index < len(request["messages"])
                            else "quote_not_in_message"
                        ),
                        "quote_excerpt": quote[:240] if isinstance(quote, str) else None,
                    },
                )
            reply_evidence |= index in request["reply_indices"]
        if not reply_evidence:
            raise ScoringError(
                "judge_response",
                "invalid_judge_evidence",
                "评分证据没有引用当前轮助手答复",
                True,
                {
                    "key": key,
                    "reply_indices": request["reply_indices"],
                    "evidence_message_indices": [
                        item.get("message_index")
                        for item in proof
                        if isinstance(item, dict)
                    ],
                    "validation": "current_reply_not_cited",
                },
            )
        updates[key] = {"status": status, "reason": reason, "evidence": proof}
    for key, update in updates.items():
        checks[key].update(update)


def score_sample(adapter, sample, judge, judge_retries=1, event_sink=None):
    analyze, plan_checks = adapter.analyze, adapter.plan_checks
    requests_before = getattr(judge, "request_count", 0)
    rule_check, expectation = adapter.rule_check, adapter.expectation
    state = analyze(sample)
    checks, requests, events = plan_checks(sample, state)
    if event_sink:
        for event in events:
            event_sink(event)
    for key, item in checks.items():
        if item["method"] in ("rule", "program"):
            turn = state["turns"][item["turn"] - 1]
            status, reason, proof = rule_check(
                item["check_id"], turn, expectation(sample["seed"], turn, state), state
            )
            item.update(status=status, reason=reason, evidence=proof)
    if requests:
        if judge is None:
            raise ScoringError(
                "judge_request",
                "missing_judge_config",
                "存在LLM检查项，但没有配置评分模型",
            )
        last_error = None
        for _ in range(judge_retries + 1):
            try:
                apply_judgments(
                    checks, requests, judge.evaluate(sample["sample_id"], requests)
                )
                last_error = None
                break
            except ScoringError as exc:
                last_error = exc
            except Exception as exc:
                last_error = ScoringError(
                    "judge_request",
                    "judge_request_failed",
                    f"评分模型请求失败：{type(exc).__name__}",
                    True,
                )
        if last_error:
            raise last_error
    ordered = [
        checks[key]
        for key in sorted(checks, key=lambda key: (int(key.split(":")[0]), key))
    ]
    for item in ordered:
        event = {"event": "check_result", **item}
        events.append(event)
        if event_sink:
            event_sink(event)
    turns = []
    for turn in state["turns"]:
        keys = [
            f"{item['turn']}:{item['check_id']}"
            for item in ordered
            if item["turn"] == turn["turn"]
        ]
        turns.append(
            {
                "turn": turn["turn"],
                "status": (
                    "pass"
                    if all(checks[key]["status"] == "pass" for key in keys)
                    else "fail"
                ),
                "check_keys": keys,
            }
        )
    scenarios = []
    for scenario in dict.fromkeys(sample["seed"]["scenario_ids"]):
        keys = [
            f"{item['turn']}:{item['check_id']}"
            for item in ordered
            if scenario in item["scenario_ids"]
        ]
        if not keys:
            raise ScoringError(
                "aggregation", "empty_scenario_result", f"场景{scenario}没有检查结果"
            )
        scenarios.append(
            {
                "scenario_id": scenario,
                "status": (
                    "pass"
                    if all(checks[key]["status"] == "pass" for key in keys)
                    else "fail"
                ),
                "check_keys": keys,
            }
        )
    result = {
        "sample_id": sample["sample_id"],
        "source": sample.get("source", "unknown"),
        "template_id": sample["seed"]["template_id"],
        "seed_id": sample["seed"]["seed_id"],
        "target_only": bool(sample["seed"].get("target_only")),
        "status": "pass" if all(item["status"] == "pass" for item in turns) else "fail",
        "turns": turns,
        "checks": ordered,
        "scenarios": scenarios,
        "llm_request_count": (
            getattr(judge, "request_count", requests_before + 1) - requests_before
        )
        if requests
        else 0,
    }
    return result


def _rate(statuses):
    values = list(statuses)
    passed, failed = (
        sum(value == "pass" for value in values),
        sum(value == "fail" for value in values),
    )
    total = passed + failed
    return {
        "pass": passed,
        "fail": failed,
        "count": total,
        "pass_rate": passed / total if total else None,
    }


def aggregate_report(adapter, results, errors, input_count):
    CHECKS, SCENARIO_CHECKS = adapter.CHECKS, adapter.SCENARIO_CHECKS
    SCENARIO_TOTALS = adapter.SCENARIO_TOTALS
    check_rows = [item for sample in results for item in sample["checks"]]
    scenario_rows = [item for sample in results for item in sample["scenarios"]]
    per_check = {
        cid: _rate(item["status"] for item in check_rows if item["check_id"] == cid)
        for cid in CHECKS
    }
    per_scenario = {
        sid: _rate(
            item["status"] for item in scenario_rows if item["scenario_id"] == sid
        )
        for sid in SCENARIO_CHECKS
    }
    categories = {}
    for category, planned in SCENARIO_TOTALS.items():
        covered = [
            row
            for sid, row in per_scenario.items()
            if sid.startswith(category) and row["count"]
        ]
        categories[category] = {
            "covered_scenarios": len(covered),
            "planned_scenarios": planned,
            "coverage_rate": len(covered) / planned,
            "pass_rate": (
                sum(row["pass_rate"] for row in covered) / len(covered)
                if covered
                else None
            ),
        }
    return {
        "input_samples": input_count,
        "completed_samples": len(results),
        "scoring_error_samples": len(errors),
        "scoring_completion_rate": len(results) / input_count if input_count else None,
        "sample_total": _rate(item["status"] for item in results),
        "check_total": _rate(item["status"] for item in check_rows),
        "checks": per_check,
        "scenarios": per_scenario,
        "categories": categories,
    }


def score_samples(adapter, samples, judge, judge_retries=1, event_sink=None):
    VERSION = adapter.VERSION
    if not isinstance(samples, list) or not samples:
        raise ScoringError(
            "scoring_input", "invalid_sample_json", "评分输入必须是非空数组"
        )
    ids = [
        item.get("sample_id") if isinstance(item, dict) else None for item in samples
    ]
    if any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(
        set(ids)
    ):
        raise ScoringError(
            "scoring_input", "duplicate_sample_id", "sample_id必须非空且唯一"
        )
    results, errors, events = [], [], []
    for sample in samples:
        sample_events = []

        def capture(event):
            sample_events.append(event)
            if event_sink:
                event_sink(event)

        try:
            result = score_sample(
                adapter, sample, judge, judge_retries=judge_retries, event_sink=capture
            )
            results.append(result)
        except ScoringError as exc:
            record = exc.record(sample)
            diagnostic_reader = getattr(judge, "error_diagnostics", None)
            if callable(diagnostic_reader):
                diagnostics = diagnostic_reader(sample["sample_id"])
                if diagnostics:
                    record["judge_diagnostics"] = diagnostics
            errors.append(record)
            capture(record)
        except Exception as exc:
            record = ScoringError(
                "scoring",
                "unexpected_exception",
                f"未预料的评分异常：{type(exc).__name__}",
            ).record(sample)
            errors.append(record)
            capture(record)
        events.extend(sample_events)
    return {
        "schema_version": 2,
        "rubric_version": VERSION,
        "judge": (
            judge.metadata if judge else {"source": "not_configured", "model": None}
        ),
        "samples": results,
        "errors": errors,
        "selection": {
            "candidate_events": sum(
                event["event"] in {"check_selected", "check_filtered"}
                for event in events
            ),
            "selected": sum(event["event"] == "check_selected" for event in events),
            "filtered": sum(event["event"] == "check_filtered" for event in events),
            "filtered_by_reason": dict(
                Counter(
                    event["reason_code"]
                    for event in events
                    if event["event"] == "check_filtered"
                )
            ),
            "filtered_details": [
                event for event in events if event["event"] == "check_filtered"
            ],
        },
        "summary": adapter.aggregate_report(results, errors, len(samples)),
    }
