"""Weather evaluation V2: plan seven checks, execute them, and aggregate results."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


VERSION = "2.0"
CHECKS = {
    "C01": {"name": "工具调用行为", "method": "rule"},
    "C02": {"name": "工具参数正确性", "method": "rule"},
    "C03": {"name": "报告城市名保留", "method": "rule"},
    "C04": {
        "name": "对话动作正确性",
        "method": "llm",
        "rubric": "按expected.action完成澄清、回答、限制说明、工具错误处理或取消；不得擅自补全未知信息，也不得用不必要的澄清阻塞本可直接完成的请求。",
    },
    "C05": {
        "name": "用户需求完成度",
        "method": "llm",
        "rubric": "回应expected中的城市、日期、问题类型和全部子任务；报告不能回答的目标应明确说明。这里只判断目标是否完成，不判断天气事实真假。",
    },
    "C06": {
        "name": "答复事实有据",
        "method": "llm",
        "rubric": "用户可见答复中的每项具体天气事实必须由该答复之前的工具结果支持。数值错位、无报告编造、把湿度当降水概率或工具报错后继续编造均失败。只说明限制且不添加天气事实可以通过。",
    },
    "C07": {
        "name": "回复语言符合要求",
        "method": "llm",
        "rubric": "答复主体使用中文；城市原名、数字、单位和必要专有名词可以保留。",
    },
}

# Candidate checks. Template/turn rules below decide which candidates apply.
SCENARIO_CHECKS = {
    "R01": ["C01", "C02", "C05"],
    "R02": ["C01", "C06"],
    "R03": ["C01", "C05"],
    "R04": ["C01", "C02", "C05"],
    "T01": ["C04", "C05"],
    "T02": ["C01", "C02", "C05"],
    "T03": ["C05"],
    "T04": ["C04", "C05"],
    "T05": ["C02", "C04", "C06"],
    "T06": ["C02", "C04", "C06"],
    "T07": ["C05", "C06"],
    "L01": ["C01", "C02"],
    "L02": ["C01", "C02"],
    "L04": ["C01", "C02", "C04"],
    "L05": ["C01", "C02", "C04"],
    "L06": ["C02", "C04"],
    "L08": ["C01", "C02", "C04", "C06"],
    "F01": ["C01", "C02", "C04", "C05"],
    "F02": ["C01", "C02", "C04", "C06"],
    "M01": ["C05"],
    "M02": ["C01", "C02", "C05"],
    "M03": ["C01", "C02", "C05"],
    "M04": ["C01", "C02", "C05"],
    "O01": ["C05", "C06"],
    "O02": ["C03", "C05"],
    "O03": ["C01", "C04", "C06"],
    "O04": ["C07"],
    "G02": ["C01", "C04"],
}
SCENARIO_TOTALS = {"R": 4, "T": 7, "L": 6, "F": 2, "M": 4, "O": 4, "G": 1}
TEMPLATE_IDS = {f"S{n:02}" for n in range(1, 26)} - {"S14", "S16", "S18", "S23", "S25"}
ALL_CHECKS = set(CHECKS)
TEMPLATE_TURN_CHECKS = {
    "S01": {1: ALL_CHECKS},
    "S02": {1: ALL_CHECKS},
    "S03": {1: {"C01", "C06", "C07"}},
    "S04": {1: {"C01", "C05", "C07"}},
    "S05": {1: ALL_CHECKS},
    "S06": {1: ALL_CHECKS},
    "S07": {1: {"C02", "C04", "C07"}, 2: ALL_CHECKS},
    "S08": {1: {"C02", "C04", "C06", "C07"}},
    "S09": {1: {"C02", "C04", "C06", "C07"}},
    "S10": {1: ALL_CHECKS, 2: ALL_CHECKS},
    "S11": {1: {"C02", "C04", "C07"}, 2: ALL_CHECKS},
    "S12": {1: {"C02", "C04", "C07"}, 2: ALL_CHECKS},
    "S13": {1: ALL_CHECKS},
    "S15": {1: {"C02", "C04", "C06", "C07"}, 2: ALL_CHECKS},
    "S17": {1: {"C01", "C02", "C04", "C06", "C07"}},
    "S19": {1: ALL_CHECKS, 2: ALL_CHECKS},
    "S20": {1: ALL_CHECKS, 2: ALL_CHECKS},
    "S21": {1: ALL_CHECKS, 2: ALL_CHECKS},
    "S22": {1: ALL_CHECKS},
    "S24": {1: {"C02", "C04", "C07"}, 2: {"C01", "C04", "C07"}},
}
FIELD_PATTERNS = {
    "hourly_temperature": r"(?:15[:：]00|下午(?:三|3)点|15点).*?(?:温度|气温)",
    "hourly_rain": r"(?:降雨时间|开始下雨时间|(?:\d{1,2}[:：]\d{2}|\d{1,2}点).*?(?:下雨|降雨))",
    "minute_rain": r"(?:\d{1,2}[:：]\d{2}|\d{1,2}点\d{1,2}分).*?(?:开始下雨|开始降雨)",
    "rain_probability": r"(?:降水概率|降雨概率).*?\d+(?:\.\d+)?\s*%",
    "rain_duration": r"(?:雨|降水).*?持续.*?\d+(?:\.\d+)?\s*(?:小时|分钟)",
}


from eval_scoring import ScoringError as WeatherScoringError, apply_judgments

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def clean_messages(messages):
    return [
        {
            key: item[key]
            for key in ("role", "content", "tool_calls", "tool_call_id")
            if key in item
        }
        for item in messages
    ]


def same_city(value, city):
    if not isinstance(value, str) or not isinstance(city, str):
        return False

    def normalize(text):
        return "".join(text.split()).removesuffix("市")

    return normalize(value) == normalize(city)


def city_name_in_reply(report_city, reply):
    """Accept the report city verbatim or with a trailing 市 omitted."""
    if not isinstance(report_city, str) or not isinstance(reply, str):
        return False
    aliases = {report_city}
    if report_city.endswith("市") and len(report_city) > 1:
        aliases.add(report_city[:-1])
    return any(alias in reply for alias in aliases)


def same_adm(value, adm):
    if not isinstance(value, str) or not isinstance(adm, str):
        return False

    def normalize(text):
        return "".join(text.split()).removesuffix("省").removesuffix("市")

    return normalize(value) == normalize(adm)


def same_qualified_location(value, city, value_adm, expected_adm):
    """Accept a district/county short name only when its parent region matches."""
    if not all(
        isinstance(item, str) and item.strip()
        for item in (value, city, value_adm, expected_adm)
    ):
        return False

    def normalize(text):
        normalized = "".join(text.split())
        for suffix in ("特别行政区", "自治州", "自治县", "新区", "市", "区", "县"):
            if normalized.endswith(suffix):
                return normalized[: -len(suffix)]
        return normalized

    return normalize(value) == normalize(city) and same_adm(value_adm, expected_adm)


def resolve_date(text, base):
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        try:
            return date(*map(int, match.groups())).isoformat()
        except ValueError as exc:
            raise WeatherScoringError(
                "report_parse", "invalid_forecast_date", "报告日期无效"
            ) from exc
    match = re.search(r"(\d{1,2})月(\d{1,2})日", text)
    if not match:
        raise WeatherScoringError(
            "report_parse", "invalid_forecast_date", "无法识别报告日期"
        )
    month, day = map(int, match.groups())
    candidates = []
    for year in (base.year - 1, base.year, base.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            pass
    if not candidates:
        raise WeatherScoringError(
            "report_parse", "invalid_forecast_date", "报告日期无效"
        )
    closest = min(candidates, key=lambda value: abs((value - base).days))
    if abs((closest - base).days) > 31:
        raise WeatherScoringError(
            "report_parse", "invalid_forecast_date", "无年份日期无法可靠补全年份"
        )
    return closest.isoformat()


def parse_report(text, base):
    head = re.match(r"您查询的位置是[：:]\s*([^\n]+)", text)
    if not head:
        return None
    if "未来7天预报：" not in text:
        raise WeatherScoringError(
            "report_parse", "missing_forecast_section", "天气报告缺少预报段"
        )
    report = {"city": head.group(1).strip(), "forecast": [], "raw": text}
    forecast = text.split("未来7天预报：", 1)[1].split("（如需", 1)[0]
    pattern = r"^(.+?)[:：]\s*([^，,]+)[，,]\s*气温\s*(-?\d+(?:\.\d+)?)\s*[°℃度]*\s*[~～至]\s*(-?\d+(?:\.\d+)?)\s*[°℃度]*\s*$"
    for line in forecast.splitlines():
        if not line.strip():
            continue
        match = re.match(pattern, line.strip())
        if not match:
            if any(re.search(item, line) for item in FIELD_PATTERNS.values()):
                continue
            raise WeatherScoringError(
                "report_parse", "invalid_forecast_row", "天气报告包含无法解析的预报行"
            )
        day = resolve_date(match[1], base)
        low, high = float(match[3]), float(match[4])
        if low > high:
            raise WeatherScoringError(
                "report_parse", "invalid_temperature_range", "最低温高于最高温"
            )
        report["forecast"].append(
            {"date": day, "weather": match[2].strip(), "low": low, "high": high}
        )
    dates = [row["date"] for row in report["forecast"]]
    if not dates:
        raise WeatherScoringError(
            "report_parse", "empty_forecast", "天气报告没有可解析的预报日期"
        )
    if len(dates) != len(set(dates)):
        raise WeatherScoringError(
            "report_parse", "duplicate_forecast_date", "天气报告包含重复日期"
        )
    return report


def analyze(sample):
    try:
        seed, context, messages = sample["seed"], sample["context"], sample["messages"]
    except (KeyError, TypeError) as exc:
        raise WeatherScoringError(
            "scoring_input", "invalid_sample_schema", "样本缺少seed、context或messages"
        ) from exc
    template = seed.get("template_id")
    if template not in TEMPLATE_IDS:
        raise WeatherScoringError(
            "scoring_input", "unknown_template", "样本模板未知或已停用"
        )
    scenarios = seed.get("scenario_ids")
    if (
        not isinstance(scenarios, list)
        or not scenarios
        or set(scenarios) - set(SCENARIO_CHECKS)
    ):
        raise WeatherScoringError(
            "scoring_input", "missing_scenario_mapping", "样本包含空或未知场景"
        )
    for field in ("base_date", "timezone", "default_city"):
        if not context.get(field):
            raise WeatherScoringError(
                "scoring_input", "invalid_sample_schema", f"context缺少{field}"
            )
    try:
        base = date.fromisoformat(context["base_date"])
        ZoneInfo(context["timezone"])
    except (ValueError, TypeError) as exc:
        raise WeatherScoringError(
            "scoring_input", "invalid_sample_schema", "基准日期或时区无效"
        ) from exc
    if context.get("trace_complete") is not True:
        raise WeatherScoringError(
            "scoring_input", "incomplete_message_trace", "消息轨迹未声明完整"
        )
    if context["default_city"] != seed.get("default_city"):
        raise WeatherScoringError(
            "scoring_input", "default_city_mismatch", "运行默认城市与种子不一致"
        )
    if not isinstance(messages, list) or not messages:
        raise WeatherScoringError(
            "scoring_input", "invalid_sample_schema", "messages必须是非空数组"
        )

    turns, calls, reports, pending = [], {}, [], set()
    current = None
    for index, message in enumerate(messages):
        if not isinstance(message, dict) or message.get("role") not in {
            "system",
            "user",
            "assistant",
            "tool",
        }:
            raise WeatherScoringError(
                "scoring_input", "invalid_message", f"消息{index}结构无效"
            )
        role, content = message["role"], message.get("content")
        if isinstance(content, str) and "...(truncated)" in content:
            raise WeatherScoringError(
                "scoring_input", "truncated_message", f"消息{index}被截断"
            )
        if role in {"system", "user", "tool"} and not isinstance(content, str):
            raise WeatherScoringError(
                "scoring_input", "invalid_message", f"消息{index}缺少字符串content"
            )
        if role == "user":
            if pending:
                raise WeatherScoringError(
                    "tool_link", "missing_tool_result", "新用户轮次前仍有未配对工具调用"
                )
            current = {
                "turn": len(turns) + 1,
                "start": index,
                "end": index,
                "calls": [],
                "results": [],
                "replies": [],
            }
            turns.append(current)
        if current is None:
            if role != "system":
                raise WeatherScoringError(
                    "scoring_input",
                    "invalid_message_order",
                    "用户消息前出现非system消息",
                )
            continue
        current["end"] = index
        if role == "assistant":
            if content is not None and not isinstance(content, str):
                raise WeatherScoringError(
                    "scoring_input", "invalid_message", "assistant.content格式无效"
                )
            if content:
                if pending:
                    raise WeatherScoringError(
                        "tool_link", "missing_tool_result", "工具响应前出现最终答复"
                    )
                current["replies"].append(index)
            tool_calls = message.get("tool_calls", [])
            if not isinstance(tool_calls, list):
                raise WeatherScoringError(
                    "tool_link", "invalid_tool_call", "tool_calls必须是数组"
                )
            for call in tool_calls:
                function = call.get("function") if isinstance(call, dict) else None
                if (
                    not isinstance(call, dict)
                    or not isinstance(call.get("id"), str)
                    or not call["id"]
                    or call.get("type") != "function"
                    or not isinstance(function, dict)
                    or not isinstance(function.get("name"), str)
                ):
                    raise WeatherScoringError(
                        "tool_link", "invalid_tool_call", "工具调用结构无效"
                    )
                if call["id"] in calls:
                    raise WeatherScoringError(
                        "tool_link", "duplicate_tool_call_id", "工具调用ID重复"
                    )
                raw = function.get("arguments")
                try:
                    arguments = json.loads(raw) if isinstance(raw, str) else None
                except ValueError:
                    arguments = None
                entry = {
                    "id": call["id"],
                    "name": function["name"],
                    "arguments": arguments,
                    "raw_arguments": raw,
                    "message_index": index,
                    "turn": current["turn"],
                }
                calls[call["id"]] = entry
                current["calls"].append(entry)
                pending.add(call["id"])
        elif role == "tool":
            call_id = message.get("tool_call_id")
            if not isinstance(call_id, str) or call_id not in pending:
                raise WeatherScoringError(
                    "tool_link", "tool_call_id_mismatch", "工具响应ID没有唯一待完成调用"
                )
            pending.remove(call_id)
            call = calls[call_id]
            result = {
                "message_index": index,
                "call": call,
                "status": "unknown",
                "content": content,
            }
            if call["name"] == "get_weather":
                report = parse_report(content, base)
                if report:
                    report.update(message_index=index, call=call)
                    reports.append(report)
                    result.update(status="report", report=report)
                else:
                    try:
                        body = json.loads(content)
                    except ValueError:
                        body = None
                    if isinstance(body, dict) and isinstance(body.get("status"), str):
                        result["status"] = body["status"]
            current["results"].append(result)
    if pending:
        raise WeatherScoringError("tool_link", "missing_tool_result", "缺少工具响应")
    actual_users = [
        item.get("content") for item in messages if item.get("role") == "user"
    ]
    if actual_users != seed.get("user_turns") or len(turns) != len(
        seed.get("user_turns", [])
    ):
        raise WeatherScoringError(
            "scoring_input", "user_turn_mismatch", "用户轮次与种子不一致"
        )
    for turn in turns:
        last = messages[turn["end"]]
        if (
            not turn["replies"]
            or last.get("role") != "assistant"
            or not last.get("content")
            or last.get("tool_calls")
        ):
            raise WeatherScoringError(
                "scoring_input",
                "missing_final_reply",
                f"第{turn['turn']}轮缺少最终助手答复",
            )
    return {
        "base": base,
        "turns": turns,
        "reports": reports,
        "messages": clean_messages(messages),
    }


def available_report(state, turn_number):
    results = [
        result
        for turn in state["turns"]
        if turn["turn"] <= turn_number
        for result in turn["results"]
        if result["call"]["name"] == "get_weather"
    ]
    return results[-1].get("report") if results else None


def current_turn_report(turn):
    """Return the latest normal weather report received in this turn."""
    reports = [
        result.get("report")
        for result in turn["results"]
        if result["call"]["name"] == "get_weather" and result.get("report")
    ]
    return reports[-1] if reports else None


def expectation(seed, turn, state):
    template, number = seed["template_id"], turn["turn"]
    city, offset, adm = (
        seed.get("target_city"),
        seed.get("target_day"),
        seed.get("target_adm"),
    )
    call_mode, action, default_mode = "required", "answer_weather", False
    if template == "S03":
        call_mode, action = "forbidden", "chat_about_weather"
    elif template == "S04":
        call_mode, action = "forbidden", "answer_other_request"
    elif template in {"S08", "S09"}:
        call_mode, action = None, "explain_capability_limit"
    elif template == "S17":
        action = "explain_tool_error"
    elif template == "S10":
        action = "explain_forecast_range" if number == 1 else "answer_forecast_boundary"
        call_mode = "required" if number == 1 else "reuse_allowed"
    if template in {"S01", "S21"} and number == 1:
        city, default_mode = seed["default_city"], True
    if template == "S20" and number == 1:
        city = seed["first_city"]
    if template == "S19" and number == 1:
        offset = seed["first_day"]
    if template in {"S07", "S19"} and number == 2:
        call_mode = "reuse_allowed"
    if template in {"S07", "S11", "S12", "S15", "S24"} and number == 1:
        call_mode = None
        if (
            template == "S07"
            or template == "S24"
            and seed.get("clarification_kind") == "date"
        ):
            action, offset = "clarify_date", None
        elif template == "S11" or template == "S24":
            action, city = "clarify_province_city", None
        elif template == "S12":
            action, city, adm = "clarify_ambiguous_city", None, None
        else:
            action, city = "request_location_correction", None
    if template == "S24" and number == 2:
        call_mode, action, city, offset = "forbidden", "cancel_request", None, None
    known_location = city
    if number == 1:
        known_location = {
            "S11": seed.get("province"),
            "S12": seed.get("ambiguous_name"),
            "S15": seed.get("invalid_location"),
        }.get(template, city)
        if template == "S24" and seed.get("clarification_kind") == "city":
            known_location, adm = seed.get("province"), seed.get("province")
    if template == "S11":
        adm = seed.get("province")
    offsets = seed.get("target_days", [offset] if offset is not None else [])
    if action.startswith("clarify_") or action == "cancel_request":
        offsets = []
    if template == "S08":
        offsets = [-seed["days_ago"]]
    if template == "S09":
        offsets = [seed["days_ahead"]]
    dates = [(state["base"] + timedelta(days=value)).isoformat() for value in offsets]
    if template == "S10":
        first_reports = [
            report for report in state["reports"] if report["call"]["turn"] == 1
        ]
        if number == 1 and first_reports:
            dates = [row["date"] for row in first_reports[-1]["forecast"]]
        elif number == 2 and first_reports:
            last = max(row["date"] for row in first_reports[-1]["forecast"])
            dates = [last, (date.fromisoformat(last) + timedelta(days=1)).isoformat()]
    report = available_report(state, number)
    available_dates = [row["date"] for row in report["forecast"]] if report else []
    tool_statuses = [
        result["status"]
        for result in turn["results"]
        if result["call"]["name"] == "get_weather"
    ]
    return {
        "action": action,
        "call_mode": call_mode,
        "city": city,
        "dates": dates,
        "available_dates": available_dates,
        "uncovered_dates": [value for value in dates if value not in available_dates],
        "known_location": known_location,
        "adm": adm,
        "ambiguous_name": seed.get("ambiguous_name"),
        "default_mode": default_mode,
        "query_kind": seed.get("query_kind"),
        "other_request": seed.get("other_request"),
        "requested_field": seed.get("requested_field"),
        "tool_statuses": tool_statuses,
    }


def scenario_applies(template, number, scenario):
    if template == "S24":
        if scenario == "G02":
            return number == 2
        if scenario in {"T04", "L04"}:
            return number == 1
        return scenario == "O04"
    if template == "S07" and scenario == "T04":
        return number == 1
    if template == "S21" and scenario == "L02":
        return number == 1
    if template == "S21" and scenario == "L01":
        return number == 2
    if template == "S15" and scenario == "O02":
        return number == 2
    return True


def _selection_reason(check_id, allowed, expected, turn):
    if check_id not in allowed:
        return "template_turn_not_applicable", "模板逐轮计划未选择该检查项"
    if check_id == "C01" and expected["call_mode"] is None:
        return "no_call_mode", "该轮允许直接澄清或说明限制，不检查是否调用"
    calls = [call for call in turn["calls"] if call["name"] == "get_weather"]
    if check_id == "C02" and not calls:
        return "no_weather_call", "当前轮没有发生get_weather调用"
    if check_id == "C03" and current_turn_report(turn) is None:
        return (
            "no_new_weather_report",
            "当前轮没有新的正常天气报告；沿用已有报告不重复检查城市名",
        )
    return None, None


def plan_checks(sample, state):
    seed, template = sample["seed"], sample["seed"]["template_id"]
    checks, requests, events = {}, [], []
    for turn in state["turns"]:
        number = turn["turn"]
        allowed = TEMPLATE_TURN_CHECKS[template].get(number)
        if allowed is None:
            raise WeatherScoringError(
                "check_selection",
                "missing_turn_plan",
                f"{template}第{number}轮没有检查计划",
            )
        expected = expectation(seed, turn, state)
        applicable = [
            scenario
            for scenario in dict.fromkeys(seed["scenario_ids"])
            if scenario_applies(template, number, scenario)
        ]
        candidate_ids = sorted(
            {check for scenario in applicable for check in SCENARIO_CHECKS[scenario]}
        )
        for check_id in candidate_ids:
            scenario_ids = [
                scenario
                for scenario in applicable
                if check_id in SCENARIO_CHECKS[scenario]
            ]
            reason_code, reason = _selection_reason(check_id, allowed, expected, turn)
            base_event = {
                "sample_id": sample["sample_id"],
                "template_id": template,
                "turn": number,
                "check_id": check_id,
                "scenario_ids": scenario_ids,
            }
            if reason_code:
                events.append(
                    {
                        "event": "check_filtered",
                        **base_event,
                        "selected": False,
                        "reason_code": reason_code,
                        "reason": reason,
                    }
                )
                continue
            key = f"{number}:{check_id}"
            checks[key] = {
                "sample_id": sample["sample_id"],
                "turn": number,
                "check_id": check_id,
                "scenario_ids": scenario_ids,
                "method": CHECKS[check_id]["method"],
            }
            events.append({"event": "check_selected", **base_event, "selected": True})
            if CHECKS[check_id]["method"] == "llm":
                requests.append(
                    {
                        "key": key,
                        "turn": number,
                        "check_id": check_id,
                        "expected": expected,
                        "context": {
                            field: sample["context"][field]
                            for field in ("base_date", "timezone")
                        },
                        "messages": [
                            {**message, "message_index": index}
                            for index, message in enumerate(
                                state["messages"][: turn["end"] + 1]
                            )
                        ],
                        "reply_indices": list(turn["replies"]),
                        "reports": [
                            {
                                "message_index": item["message_index"],
                                "city": item["city"],
                                "forecast": item["forecast"],
                            }
                            for item in state["reports"]
                            if item["message_index"] <= turn["end"]
                        ],
                    }
                )
    selected_by_turn = Counter(item["turn"] for item in checks.values())
    for turn in state["turns"]:
        if not selected_by_turn[turn["turn"]]:
            raise WeatherScoringError(
                "check_selection",
                "empty_turn_checks",
                f"第{turn['turn']}轮筛选后没有检查项",
            )
    bound = {scenario for item in checks.values() for scenario in item["scenario_ids"]}
    missing = set(seed["scenario_ids"]) - bound
    if missing:
        raise WeatherScoringError(
            "check_selection",
            "empty_scenario_result",
            "场景没有实际检查项：" + ",".join(sorted(missing)),
        )
    return checks, requests, events


def evidence(messages, indices):
    output = []
    for index in dict.fromkeys(indices):
        message = messages[index]
        quote = message.get("content") or json.dumps(
            message.get("tool_calls", []), ensure_ascii=False
        )
        output.append({"message_index": index, "quote": quote[:500]})
    return output


def rule_check(check_id, turn, expected, state):
    messages = state["messages"]
    calls = [call for call in turn["calls"] if call["name"] == "get_weather"]
    report = available_report(state, turn["turn"])
    call_indices = [call["message_index"] for call in calls] or [turn["start"]]
    if check_id == "C01":
        mode = expected["call_mode"]
        if mode == "required" and not calls:
            return (
                "fail",
                "该轮必须查询天气，但没有调用get_weather",
                evidence(messages, call_indices),
            )
        if mode == "forbidden" and calls:
            return (
                "fail",
                "该轮禁止查询天气，但调用了get_weather",
                evidence(messages, call_indices),
            )
        if mode == "reuse_allowed" and not calls:
            if report is None or not same_city(report["city"], expected["city"]):
                return (
                    "fail",
                    "没有目标城市的可复用天气报告",
                    evidence(messages, call_indices),
                )
            required = (
                expected["dates"][:1]
                if expected["action"] == "answer_forecast_boundary"
                else expected["dates"]
            )
            report_dates = {row["date"] for row in report["forecast"]}
            if not set(required).issubset(report_dates):
                return (
                    "fail",
                    "已有报告没有覆盖需要复用的日期",
                    evidence(messages, [report["message_index"]]),
                )
            return (
                "pass",
                "沿用报告的城市和日期范围符合要求",
                evidence(messages, [report["message_index"]]),
            )
        return "pass", "工具调用行为符合调用模式", evidence(messages, call_indices)
    if check_id == "C02":
        problems = []
        for call in calls:
            args = call["arguments"]
            if not isinstance(args, dict):
                problems.append("arguments不是有效JSON对象")
                continue
            if set(args) - {"location", "adm", "lang"}:
                problems.append("包含工具不接受的字段或日期参数")
            if not isinstance(args.get("lang"), str) or not args["lang"].strip():
                problems.append("缺少有效lang")
            for name in ("location", "adm"):
                if name in args and (
                    not isinstance(args[name], str) or not args[name].strip()
                ):
                    problems.append(f"{name}必须是非空字符串")
            location = args.get("location")
            if expected["default_mode"]:
                if "location" in args or "adm" in args:
                    problems.append("默认城市查询应省略location和adm")
            elif expected["city"]:
                ambiguous_location = (
                    expected.get("ambiguous_name")
                    and same_city(location, expected["ambiguous_name"])
                    and expected.get("adm")
                    and same_adm(args.get("adm"), expected["adm"])
                )
                qualified_location = same_qualified_location(
                    location,
                    expected["city"],
                    args.get("adm"),
                    expected.get("adm"),
                )
                if (
                    not same_city(location, expected["city"])
                    and not ambiguous_location
                    and not qualified_location
                ):
                    problems.append("location不是本轮目标城市")
            elif expected["adm"] and location is not None:
                problems.append("只知道上级地区时不能把它当作具体城市")
            elif location is not None and not same_city(
                location, expected["known_location"]
            ):
                problems.append("澄清前使用了尚未确定的城市")
            elif (
                expected["known_location"] and location is None and not args.get("adm")
            ):
                problems.append("地点尚不明确时不能回退默认城市")
            if "adm" in args and (
                not expected["adm"] or not same_adm(args["adm"], expected["adm"])
            ):
                problems.append("adm不是用户已提供的上级地区")
            if (
                expected["city"] in {"朝阳市", "朝阳区"}
                and location == "朝阳"
                and not args.get("adm")
            ):
                problems.append("重名地点没有携带消歧地区")
        if problems:
            return (
                "fail",
                "；".join(dict.fromkeys(problems)),
                evidence(messages, call_indices),
            )
        return (
            "pass",
            "所有天气调用参数符合工具定义和本轮已知信息",
            evidence(messages, call_indices),
        )
    replies = [
        index for index in turn["replies"] if report and index > report["message_index"]
    ]
    copied = bool(
        report
        and replies
        and any(
            city_name_in_reply(report["city"], messages[index]["content"])
            for index in replies
        )
    )
    indices = ([report["message_index"]] if report else []) + replies
    if copied:
        return "pass", "答复包含报告城市名或省略“市”后的同名城市", evidence(messages, indices)
    return (
        "fail",
        "答复没有原样包含报告城市名",
        evidence(messages, indices or [turn["start"]]),
    )


def score_sample(sample, judge, judge_retries=1, event_sink=None):
    import sys
    import eval_scoring
    return eval_scoring.score_sample(sys.modules[__name__], sample, judge, judge_retries, event_sink)


def _rate(statuses):
    from eval_scoring import _rate as rate
    return rate(statuses)


def aggregate_report(results, errors, input_count):
    import sys
    import eval_scoring
    return eval_scoring.aggregate_report(sys.modules[__name__], results, errors, input_count)


def score_samples(samples, judge, judge_retries=1, event_sink=None):
    import sys
    import eval_scoring
    report = eval_scoring.score_samples(sys.modules[__name__], samples, judge, judge_retries, event_sink)
    report["failure_summary"] = build_failure_summary(report)
    return report


def _format_rate(row):
    return "—" if row.get("pass_rate") is None else f"{row['pass_rate']:.1%}"


def _md(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def build_failure_summary(report):
    """Aggregate failures by stable fields; never summarize free text with an LLM."""
    results = report.get("samples", [])
    completed = len(results)
    failed_results = [r for r in results if r.get("status") == "fail"]
    check_failures = Counter()
    check_samples = {}
    combinations = Counter()
    for result in failed_results:
        failed_checks = [
            c for c in result.get("checks", []) if c.get("status") == "fail"
        ]
        ids = sorted({c["check_id"] for c in failed_checks})
        if ids:
            combinations[" + ".join(ids)] += 1
        for check in failed_checks:
            cid = check["check_id"]
            check_failures[cid] += 1
            check_samples.setdefault(cid, set()).add(result["sample_id"])
    by_check = []
    for cid in sorted(check_failures):
        affected = len(check_samples[cid])
        by_check.append(
            {
                "check_id": cid,
                "name": CHECKS.get(cid, {}).get("name", cid),
                "failed_results": check_failures[cid],
                "affected_samples": affected,
                "affected_sample_rate": affected / completed if completed else None,
            }
        )
    templates = sorted({r.get("template_id") or "unknown" for r in results + report.get("errors", [])})
    by_template = []
    for template in templates:
        selected = [r for r in results if (r.get("template_id") or "unknown") == template]
        errors = [r for r in report.get("errors", []) if (r.get("template_id") or "unknown") == template]
        passed = sum(r.get("status") == "pass" for r in selected)
        failed = sum(r.get("status") == "fail" for r in selected)
        by_template.append({
            "template_id": template,
            "input": len(selected) + len(errors),
            "completed": len(selected),
            "scoring_errors": len(errors),
            "pass": passed,
            "fail": failed,
            "pass_rate": passed / len(selected) if selected else None,
        })
    return {
        "completed_samples": completed,
        "failed_samples": len(failed_results),
        "by_check": by_check,
        "by_template": by_template,
        "check_combinations": [
            {"checks": checks, "samples": count}
            for checks, count in sorted(combinations.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


def _append_selection_markdown(lines, report):
    selection = report["selection"]
    completed = report["summary"]["check_total"]["count"]
    missing = max(selection["selected"] - completed, 0)
    lines += [
        "", "## 检查项筛选", "",
        "评分器先按场景为每一轮列出候选检查项，再去掉本轮不适用的项目。这里统计的是检查项次数，不是样本数。",
        "",
        "| 阶段 | 数量 | 说明 |",
        "|---|---:|---|",
        f"| 初始候选 | {selection['candidate_events']} | 根据样本场景和轮次列出的全部可能检查项 |",
        f"| 不适用并过滤 | {selection['filtered']} | 本轮没有对应天气调用、正常天气报告，或模板规定本轮不检查 |",
        f"| 进入评分 | {selection['selected']} | 过滤后真正需要执行的检查项 |",
        f"| 成功产生结果 | {completed} | 已得到 pass/fail 的检查项 |",
        f"| 因评分错误未产生结果 | {missing} | 所属样本评分失败，因此整条样本未落分 |",
        "",
        f"计算关系：{selection['candidate_events']} 个候选 = {selection['filtered']} 个过滤 + {selection['selected']} 个进入评分；"
        f"{selection['selected']} 个进入评分 = {completed} 个已产出结果 + {missing} 个未产出结果。",
    ]
    if missing:
        lines.append(f"本批 {missing} 个未产出检查项不计模型通过或未通过。")
    labels = {
        "template_turn_not_applicable": "按模板定义，本轮不需要此检查",
        "no_call_mode": "本轮允许直接澄清或说明限制，不检查是否调用",
        "no_weather_call": "本轮没有天气工具调用，不检查工具参数",
        "no_new_weather_report": "本轮没有新的正常天气报告，不重复检查城市名",
    }
    if selection["filtered_by_reason"]:
        lines += ["", "| 过滤原因 | 数量 | 含义 |", "|---|---:|---|"]
        for reason, count in sorted(selection["filtered_by_reason"].items()):
            lines.append(f"| `{_md(reason)}` | {count} | {_md(labels.get(reason, reason))} |")
    lines += [
        "",
        "> 被过滤的检查项不计通过或未通过。逐条筛选明细保留在 `scores.json` 的 `selection.filtered_details` 中，Markdown 不展开。",
    ]


def _append_failure_summary_markdown(lines, report):
    failure = report.get("failure_summary") or build_failure_summary(report)

    def fmt(value):
        return "—" if value is None else f"{value:.1%}"

    lines += [
        "",
        "## 未通过汇总",
        "",
        f"有效评分 {failure['completed_samples']} 条，其中未通过 {failure['failed_samples']} 条。",
        "",
        "### 按检查项",
        "",
        "| 检查项 | 名称 | 未通过判定次数 | 涉及样本 | 有效样本占比 |",
        "|---|---|---:|---:|---:|",
    ]
    for row in failure["by_check"]:
        lines.append(
            f"| {row['check_id']} | {_md(row['name'])} | {row['failed_results']} | "
            f"{row['affected_samples']} | {fmt(row['affected_sample_rate'])} |"
        )
    lines += [
        "",
        "### 按模板",
        "",
        "| 模板 | 输入 | 有效评分 | 评分错误 | 通过 | 未通过 | 通过率 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in failure["by_template"]:
        lines.append(
            f"| {row['template_id']} | {row['input']} | {row['completed']} | "
            f"{row['scoring_errors']} | {row['pass']} | {row['fail']} | "
            f"{fmt(row['pass_rate'])} |"
        )
    combinations = failure.get("check_combinations", [])
    if combinations:
        lines += [
            "",
            "### 常见未通过检查项组合",
            "",
            "| 检查项组合 | 样本数 |",
            "|---|---:|",
        ]
        for row in combinations[:10]:
            lines.append(f"| {row['checks']} | {row['samples']} |")
        if len(combinations) > 10:
            lines.append(f"\n仅展示前 10 种；其余 {len(combinations) - 10} 种保留在 `scores.json`。")


def _append_scoring_errors_markdown(lines, report):
    lines += ["", "## 评分错误", ""]
    history = report.get("historical_errors", [])
    if isinstance(history, dict):
        history = history.get("records", [])
    if history:
        lines += [f"历史评分错误记录 {len(history)} 条，保留在 `scores.json.historical_errors`；不计入本次最终评分错误或模型未通过。", ""]
    errors = report.get("errors", [])
    if not errors:
        lines.append("本批没有评分错误。")
        return
    lines += [
        "| 样本 | 模板 | 阶段 | 错误码 | 原因 | 诊断 |",
        "|---|---|---|---|---|---|",
    ]
    for error in errors:
        details = error.get("details") or {}
        diagnostic = "—"
        if details:
            diagnostic = "；".join(
                f"{key}={_short_text(value, 80)}"
                for key, value in details.items()
                if key in {"key", "validation", "message_index", "turn"}
            ) or "详见 scores.json"
        elif error.get("judge_diagnostics"):
            diagnostic = "已保存评分响应摘要，详见 scores.json"
        lines.append(
            f"| `{_md(error.get('sample_id', '—'))}` | {_md(error.get('template_id', '—'))} | "
            f"{_md(error.get('stage', '—'))} | `{_md(error.get('error_code', 'unknown'))}` | "
            f"{_md(error.get('message', ''))} | {_md(diagnostic)} |"
        )
    lines += [
        "",
        "> 评分错误不计为模型通过或未通过，也不进入有效评分通过率。",
    ]


def _short_text(value, limit=140):
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _evidence_excerpt(evidence):
    if not evidence:
        return "—"
    parts = []
    for item in evidence[:2]:
        index = item.get("message_index", "?")
        parts.append(f"消息{index}：{_short_text(item.get('quote', ''), 140)}")
    if len(evidence) > 2:
        parts.append(f"另有{len(evidence) - 2}条")
    return "<br>".join(parts)


def render_failures_markdown(report):
    """Render only scoring errors and failed checks with compact evidence excerpts."""
    failure = report.get("failure_summary") or build_failure_summary(report)
    failed = sorted(
        (r for r in report.get("samples", []) if r.get("status") == "fail"),
        key=lambda row: (row.get("template_id", ""), row["sample_id"]),
    )
    lines = [
        "# 天气未通过详情",
        "",
        f"规则：{report.get('rubric_version', VERSION)}；有效评分 {failure['completed_samples']} 条；未通过 {len(failed)} 条。",
        "",
        "本文件只展示未通过检查项和证据摘录；通过项及完整证据保留在 `scores.json`。",
    ]
    _append_scoring_errors_markdown(lines, report)
    lines += ["", "## 未通过样本", ""]
    if not failed:
        lines.append("本批没有模型未通过样本。")
        return "\n".join(lines) + "\n"
    current_template = None
    template_counts = Counter(r.get("template_id", "unknown") for r in failed)
    for result in failed:
        template = result.get("template_id", "unknown")
        if template != current_template:
            current_template = template
            lines += [
                f"### {template}（{template_counts[template]} 条未通过）",
                "",
            ]
        failed_checks = [
            c for c in result.get("checks", []) if c.get("status") == "fail"
        ]
        check_ids = "、".join(sorted({c["check_id"] for c in failed_checks}))
        lines += [
            f"#### {result['sample_id']}",
            "",
            f"未通过检查项：{check_ids or '—'}",
            "",
            "| 轮次 | 检查项 | 场景 | 原因 | 证据摘录 |",
            "|---:|---|---|---|---|",
        ]
        for check in failed_checks:
            lines.append(
                f"| {check['turn']} | {check['check_id']} | {_md(', '.join(check.get('scenario_ids', [])))} | {_md(check.get('reason', ''))} | "
                f"{_md(_evidence_excerpt(check.get('evidence', [])))} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def render_markdown(report):
    summary = report["summary"]
    completion = summary["scoring_completion_rate"]
    lines = [
        "# 天气评分报告 V2",
        "",
        f"规则版本：`{report['rubric_version']}`；评分来源：`{report['judge']['source']}`。",
        "",
        "## 核心结果",
        "",
        "| 指标 | 结果 |",
        "|---|---:|",
        f"| 评分完成率 | {summary['completed_samples']}/{summary['input_samples']}（{completion:.1%}） |",
        f"| 样本总通过率 | {_format_rate(summary['sample_total'])} |",
        f"| 检查项总通过率 | {_format_rate(summary['check_total'])} |",
        f"| 筛掉的候选检查项 | {report['selection']['filtered']} |",
        f"| 评分错误样本 | {summary['scoring_error_samples']} |",
    ]
    if report["judge"]["source"] == "mock":
        lines.extend(
            ["", "**模拟评分响应只验证接口和汇总，不代表真实评分模型的准确性。**"]
        )
    lines.extend(
        [
            "",
            "## C01—C07",
            "",
            "| 检查项 | 通过 | 未通过 | 通过率 |",
            "|---|---:|---:|---:|",
        ]
    )
    for check_id, row in summary["checks"].items():
        lines.append(
            f"| {check_id} {CHECKS[check_id]['name']} | {row['pass']} | {row['fail']} | {_format_rate(row)} |"
        )
    lines.extend(
        ["", "## 场景分类", "", "| 分类 | 覆盖 | 宏平均通过率 |", "|---|---:|---:|"]
    )
    for category, row in summary["categories"].items():
        rate = "—" if row["pass_rate"] is None else f"{row['pass_rate']:.1%}"
        lines.append(
            f"| {category} | {row['covered_scenarios']}/{row['planned_scenarios']} | {rate} |"
        )
    lines.extend(
        [
            "",
            "## 单场景通过率",
            "",
            "| 场景 | 通过 | 未通过 | 通过率 |",
            "|---|---:|---:|---:|",
        ]
    )
    for scenario, row in summary["scenarios"].items():
        lines.append(
            f"| {scenario} | {row['pass']} | {row['fail']} | {_format_rate(row)} |"
        )
    _append_failure_summary_markdown(lines, report)
    _append_selection_markdown(lines, report)
    _append_scoring_errors_markdown(lines, report)
    lines += [
        "",
        "## 输出文件",
        "",
        "- [scoring-report.md](scoring-report.md)：汇总报告。",
        "- [scoring-failures.md](scoring-failures.md)：未通过样本、未通过检查项和简短证据。",
        "- [scores.json](scores.json)：完整评分结果、全部通过/未通过证据和筛选审计数据。",
        "- `scoring-events.jsonl`：评分执行事件；合并报告的事件保留在各原评分目录。",
        "",
    ]
    return "\n".join(lines)
