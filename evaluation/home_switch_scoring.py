"""Home-switch business adapter. State evidence always comes from saved messages."""

import copy
import json
import re
import sys
from collections import Counter

import eval_scoring as engine
from eval_scoring import ScoringError
from home_switch_seeds import (
    VERSION,
    TEMPLATES,
    validate_seed,
    turn_scenarios,
    sample_type,
    target,
)

CHECKS = {
    f"HC{i:02}": {"name": name, "method": "program" if i <= 3 else "llm", "rule": rule}
    for i, name, rule in [
        (
            1,
            "工具调用行为",
            "按本轮意图判断读取、按需写入和后读；相邻上一轮同设备的可用状态可以沿用，有轮间环境变化时必须重读。单设备最多3次、两设备最多5次，每设备最多一次控制，无自动重发；双设备首项未确认时停止后续。",
        ),
        (
            2,
            "工具参数与设备",
            "设备来自本轮明确要求和可信目录；快照仅允许1到80整数max_highlight，控制仅允许单entity_id和state.type=turn_on/turn_off，不越权。",
        ),
        (
            3,
            "状态依据",
            "使用本轮实际快照或相邻上一轮同设备的可用状态：connected=true、outdated=false、实体唯一且为on/off；存在轮间环境变化时旧状态不可沿用。已达目标不写，结果分接受、明确拒绝、已观察到目标或未确认。",
        ),
        (
            4,
            "对话处理",
            "正确澄清缺项、理解取消或更正、解释范围和错误；明确可执行要求不无故再次确认。取消不等于撤销已发生操作。",
        ),
        (
            5,
            "需求与上下文",
            "按本轮expected的设备和动作回应，正确承接指代与前序要求；双设备分别说明，独立文字请求也完成，不回滚先前操作。",
        ),
        (
            6,
            "回复有据",
            "逐句只根据该句之前的可见消息与工具结果。state_hub_snapshot返回tool_error时，可概括为当前无法读取状态、状态服务暂不可用或无法确认；除非工具明确给出，不能扩展为Home Assistant断线、设备离线、权限不足或设备不存在。不能提前宣布成功，不能把电源开启夸大为电器运行，不能把未确认说成确定未执行；配置初态和隐藏规则不是事实证据。",
        ),
        (
            7,
            "回复语言",
            "所有成功、澄清和错误回复使用中文；允许原样使用on/off、entity_id、工具名、错误码等协议技术标识。",
        ),
    ]
}
ALL = set(CHECKS)
SCENARIO_CHECKS = {f"HS{i:02}": set(ALL) for i in range(1, 16)}
for i, ids in {
    1: [1, 2, 3, 5, 6, 7],
    2: [1, 2, 3, 5, 6, 7],
    3: [1, 2, 4, 6, 7],
    7: [1, 2, 4, 5, 6, 7],
    8: [1, 2, 3, 4, 6, 7],
    9: [1, 2, 3, 4, 6, 7],
    10: [1, 2, 3, 5, 6, 7],
}.items():
    SCENARIO_CHECKS[f"HS{i:02}"] = {f"HC{n:02}" for n in ids}
SCENARIO_TOTALS = {"HS": 15}


def error(code, message):
    raise ScoringError("scoring_input", code, message)


def analyze(sample):
    try:
        seed, context, messages = sample["seed"], sample["context"], sample["messages"]
        validate_seed(seed, config=context["preset_config"])
        catalog = context["public_catalog"]
        if not isinstance(catalog, list) or len(
            {d["entity_id"] for d in catalog}
        ) != len(catalog):
            raise ValueError("公开目录无效")
        if context.get("trace_complete") is not True:
            raise ValueError("消息记录不完整")
    except (KeyError, TypeError, ValueError) as exc:
        error("invalid_sample_schema", str(exc))
    if not isinstance(messages, list) or not messages:
        error("invalid_message_trace", "缺少messages")
    turns = []
    calls = {}
    current = None
    for index, m in enumerate(messages):
        if not isinstance(m, dict) or m.get("role") not in (
            "system",
            "user",
            "assistant",
            "tool",
        ):
            error("invalid_message", "无效消息")
        role = m["role"]
        if role == "user" and index not in context.get("internal_message_indices", []):
            if current:
                current["end"] = index - 1
            current = {
                "turn": len(turns) + 1,
                "start": index,
                "end": index,
                "calls": [],
                "replies": [],
            }
            turns.append(current)
        elif role == "assistant":
            if current is None:
                error("invalid_message", "助手消息没有用户轮次")
            if m.get("content"):
                current["replies"].append(index)
            for call in m.get("tool_calls") or []:
                cid = call.get("id")
                if not cid or cid in calls:
                    error("duplicate_tool_call", "工具调用ID缺失或重复")
                f = call.get("function") or {}
                raw = f.get("arguments", {})
                try:
                    args = json.loads(raw) if isinstance(raw, str) else raw
                except (ValueError, TypeError):
                    args = None
                row = {
                    "call_id": cid,
                    "name": f.get("name"),
                    "arguments": args,
                    "raw_arguments": raw,
                    "index": index,
                    "result_index": None,
                    "content": None,
                }
                calls[cid] = row
                current["calls"].append(row)
        elif role == "tool":
            call = calls.get(m.get("tool_call_id"))
            if (
                call is None
                or call["result_index"] is not None
                or call not in current["calls"]
            ):
                error("orphan_tool_result", "工具结果缺少对应调用或重复")
            call.update(result_index=index, content=m.get("content"))
    if not current:
        error("missing_user_turn", "没有用户轮次")
    current["end"] = len(messages) - 1
    if [messages[t["start"]].get("content") for t in turns] != seed["user_turns"]:
        error("user_turn_mismatch", "用户轮次与seed不一致")
    if any(c["result_index"] is None for c in calls.values()):
        error("missing_tool_result", "缺少工具返回")
    if any(not t["replies"] for t in turns):
        error("missing_final_reply", "用户轮次没有可见答复")
    return {
        "messages": messages,
        "turns": turns,
        "catalog": {d["entity_id"]: d for d in catalog},
        "calls": calls,
        "preset_config": context["preset_config"],
    }


def displayed_candidates(state, turn):
    if turn["turn"] < 2:
        return []
    previous = state["turns"][turn["turn"] - 2]
    text = "\n".join(
        state["messages"][i].get("content", "") for i in previous["replies"]
    )

    def identify(fragment):
        matches = []
        for eid, d in state["catalog"].items():
            lengths = [
                len(name)
                for name in [eid, d["name"], *d.get("aliases", [])]
                if name and name in fragment
            ]
            if lengths:
                matches.append((max(lengths), eid))
        if not matches:
            return None
        matches.sort(reverse=True)
        if len(matches) > 1 and matches[0][0] == matches[1][0]:
            return None
        return matches[0][1]

    numbered = list(
        re.finditer(r"(?:^|[\n；;])\s*(?:[-*]\s*)?(\d+)[.、)）]\s*([^\n；;]+)", text)
    )
    if numbered:
        rows = [(int(m.group(1)), identify(m.group(2))) for m in numbered]
        if [n for n, _ in rows] != list(range(1, len(rows) + 1)) or any(
            e is None for _, e in rows
        ):
            return []
        return [e for _, e in rows] if len({e for _, e in rows}) == len(rows) else []
    # Unnumbered explicit alternatives: preserve visible order, never preset order.
    matches = []
    for eid, d in state["catalog"].items():
        positions = [
            text.find(name)
            for name in [eid, d["name"], *d.get("aliases", [])]
            if name and name in text
        ]
        if positions:
            matches.append((min(positions), eid))
    matches.sort()
    if len({p for p, _ in matches}) != len(matches):
        return []
    return [eid for _, eid in matches]


def _has_turn_environment_change(state, turn_number):
    turns = state.get("preset_config", {}).get("turns") or {}
    return bool(turns.get(str(turn_number)) or turns.get(turn_number))


def _judge_expected(check_id, expected):
    """Expose only the business fields needed by each model-scored check."""
    if check_id == "HC05":
        return {
            key: copy.deepcopy(expected[key])
            for key in ("action", "target", "other_request")
        }
    if check_id == "HC07":
        return {}
    return copy.deepcopy(expected)


def expectation(seed, turn, state):
    tid = seed["template_id"]
    v = seed.get("variant_id", "basic")
    n = turn["turn"]
    t = copy.deepcopy(seed["target"])
    first = copy.deepcopy(seed.get("first_target", t))
    action = "control_device"
    read = "required"
    control = "once_if_unmet"
    other = None
    if (
        tid == "T02"
        or (tid == "T03" and n == 1)
        or (tid == "T20" and v == "query_after_error" and n == 2)
    ):
        action = "query_state"
        control = "forbidden"
        for d in t["devices"]:
            d["desired_state"] = None
    if tid in ("T05", "T06", "T15") and n == 1:
        t = first
    if tid == "T20" and v == "query_after_error" and n == 1:
        t = first
    clarify = (
        (tid in ("T07", "T08", "T10", "T11", "T14") and n == 1)
        or (tid == "T08" and v == "missing_both" and n == 2)
        or (tid == "T15" and v == "ambiguous_reference" and n == 2)
    )
    if clarify:
        action = "clarify"
        read = "optional"
        control = "forbidden"
        if tid in ("T07", "T10", "T11"):
            t = target(
                (None, "off" if tid == "T07" else t["devices"][0]["desired_state"])
            )
        if tid == "T08":
            t = target(
                (
                    None
                    if v == "missing_both" and n == 1
                    else t["devices"][0]["entity_id"],
                    None,
                )
            )
        if tid == "T14":
            t["devices"][1]["entity_id"] = None
        if tid == "T15":
            t = target((None, "off"))
    if tid == "T11" and n == 2:
        candidates = displayed_candidates(state, turn)
        selector = seed["target_selector"]
        eid = None
        if (
            selector["kind"] == "displayed_index"
            and len(candidates) >= selector["index"]
        ):
            eid = candidates[selector["index"] - 1]
        elif (
            selector["kind"] == "exclude"
            and len(candidates) == 2
            and selector["entity_id"] in candidates
        ):
            eid = next(e for e in candidates if e != selector["entity_id"])
        t["devices"][0]["entity_id"] = eid
        if eid is None:
            action = "clarify"
            read = "optional"
            control = "forbidden"
    if tid == "T17":
        t = target()
        action = "no_action"
        read = "forbidden"
        control = "forbidden"
        if n == 1 and v != "no_action":
            t = first
            if v == "cancel_after_execution":
                action = "control_device"
                read = "required"
                control = "once_if_unmet"
            else:
                action = "clarify"
                read = "optional"
        if v == "change_topic" and n == 2:
            other = "讲个笑话"
    if tid == "T18" and n == 1:
        action = "unsupported"
        t = target()
        read = "optional"
        control = "forbidden"
    if (tid == "T16" or seed.get("request_form") == "mixed") and n == 1:
        other = seed.get("other_request")
    if action == "control_device" and n > 1 and not _has_turn_environment_change(
        state, n
    ):
        read = "current_or_previous"
    return {
        "action": action,
        "target": t,
        "read_policy": read,
        "control_policy": control,
        "other_request": other,
    }


def allowed_checks(seed, n):
    tid = seed["template_id"]
    v = seed.get("variant_id", "basic")
    no4 = ALL - {"HC04"}
    no3 = ALL - {"HC03"}
    if tid in ("T01", "T02") or (tid in ("T03", "T04", "T05", "T06") and n == 1):
        return no4
    if tid in ("T07", "T08", "T10", "T11", "T14") and n == 1:
        return no3
    if tid == "T08" and v == "missing_both" and n == 2:
        return no3
    if tid == "T15" and v == "ambiguous_reference" and n == 2:
        return no3
    if tid == "T17":
        if v == "no_action":
            return {"HC01", "HC02", "HC04", "HC06", "HC07"}
        if v == "cancel_after_execution" and n == 1:
            return no4
        return no3
    if tid == "T18" and n == 1:
        return no3
    if tid == "T20" and v == "query_after_error" and n == 1:
        return ALL - {"HC05"}
    return ALL


def plan_checks(sample, state):
    checks = {}
    requests = []
    events = []
    seed = sample["seed"]
    scenes = turn_scenarios(seed)
    for turn in state["turns"]:
        n = turn["turn"]
        expected = expectation(seed, turn, state)
        allowed = allowed_checks(seed, n)
        for cid in sorted(set.union(*(SCENARIO_CHECKS[s] for s in scenes[n - 1]))):
            bound = [s for s in scenes[n - 1] if cid in SCENARIO_CHECKS[s]]
            base = {
                "sample_id": sample["sample_id"],
                "template_id": seed["template_id"],
                "turn": n,
                "check_id": cid,
                "scenario_ids": bound,
            }
            reason = None
            if cid not in allowed:
                reason = "template_turn_not_applicable"
            elif cid == "HC02" and not turn["calls"]:
                reason = "no_tool_call"
            elif cid == "HC03" and not any(
                c["name"] == "state_hub_snapshot" for c in turn["calls"]
            ):
                reason = "no_snapshot_result"
            if reason:
                events.append(
                    {
                        "event": "check_filtered",
                        **base,
                        "selected": False,
                        "reason_code": reason,
                        "reason": reason,
                    }
                )
                continue
            key = f"{n}:{cid}"
            checks[key] = {**base, "method": CHECKS[cid]["method"]}
            events.append({"event": "check_selected", **base, "selected": True})
            if CHECKS[cid]["method"] == "llm":
                requests.append(
                    {
                        "key": key,
                        "turn": n,
                        "check_id": cid,
                        "expected": _judge_expected(cid, expected),
                        "messages": [
                            {**message, "message_index": index}
                            for index, message in enumerate(
                                state["messages"][: turn["end"] + 1]
                            )
                        ],
                        "reply_indices": turn["replies"],
                        "reports": [
                            {
                                "message_index": c["result_index"],
                                "tool": c["name"],
                                "content": c["content"],
                            }
                            for c in state["calls"].values()
                            if c["result_index"] <= turn["end"]
                        ],
                    }
                )
    if {s for c in checks.values() for s in c["scenario_ids"]} != set(
        seed["scenario_ids"]
    ):
        error("empty_scenario_result", "场景没有绑定检查")
    return checks, requests, events


def observed(call, eid):
    if call is None:
        return None
    try:
        obj = json.loads(call["content"])
    except (ValueError, TypeError):
        return None
    if (
        not isinstance(obj, dict)
        or obj.get("connected") is not True
        or obj.get("outdated") is not False
    ):
        return None
    rows = obj.get("highlight")
    if not isinstance(rows, list):
        return None
    rows = [d for d in rows if isinstance(d, dict) and d.get("entity_id") == eid]
    return (
        rows[0].get("s")
        if len(rows) == 1 and rows[0].get("s") in ("on", "off")
        else None
    )


def rejected(call):
    content = str(call.get("content") or "")
    return content in (
        "执行失败，错误的设备id",
        "设置失败，错误码: 401",
        "设置失败，错误码: 403",
    ) or ("功能尚未支持" in content)


def rule_check(cid, turn, expected, state):
    calls = turn["calls"]
    reads = [c for c in calls if c["name"] == "state_hub_snapshot"]
    writes = [c for c in calls if c["name"] == "hass_set_state"]
    targets = expected["target"]["devices"]
    ids = [d["entity_id"] for d in targets]
    goals = {d["entity_id"]: d["desired_state"] for d in targets if d["entity_id"]}
    problems = []

    previous_read = None
    if expected["read_policy"] == "current_or_previous" and turn["turn"] > 1:
        previous_turn = state["turns"][turn["turn"] - 2]
        previous_read = next(
            (
                call
                for call in reversed(previous_turn["calls"])
                if call["name"] == "state_hub_snapshot"
            ),
            None,
        )

    def prior(index):
        return next(
            (r for r in reversed(reads) if r["result_index"] < index),
            previous_read,
        )

    def after(w):
        return next((r for r in reads if r["index"] > w["result_index"]), None)

    if cid == "HC01":
        if expected["read_policy"] == "required" and not reads:
            problems.append("本轮未出现必需读取")
        if expected["read_policy"] == "current_or_previous" and not reads and not all(
            eid and observed(previous_read, eid) for eid in ids
        ):
            problems.append("本轮及上一轮均无可沿用状态")
        if expected["read_policy"] == "forbidden" and calls:
            problems.append("不操作轮调用工具")
        if expected["control_policy"] == "forbidden" and writes:
            problems.append("本轮禁止控制")
        if len(calls) > (5 if len(targets) == 2 else 3):
            problems.append("超过本轮工具次数预算")
        if any(
            c["name"] not in ("state_hub_snapshot", "hass_set_state") for c in calls
        ):
            problems.append("调用场景外工具")
        counts = Counter(
            (w["arguments"] or {}).get("entity_id")
            for w in writes
            if isinstance(w["arguments"], dict)
            and isinstance(w["arguments"].get("entity_id"), str)
        )
        if any(n > 1 for n in counts.values()):
            problems.append("同设备重复控制")
        for w in writes:
            if prior(w["index"]) is None:
                problems.append("控制前未读取")
            if not rejected(w) and after(w) is None:
                problems.append("控制接受或效果未知后未读取")
        if expected["control_policy"] == "once_if_unmet" and (reads or previous_read):
            first = next(
                (
                    read
                    for read in reads
                    if not writes or read["result_index"] < writes[0]["index"]
                ),
                previous_read,
            )
            all_usable = bool(targets) and all(
                e
                and observed(first, e)
                and state["catalog"].get(e, {}).get("controllable")
                for e in ids
            )
            if not all_usable and writes:
                problems.append("控制前目标、权限或状态前提未齐全")
            if all_usable:
                stop = False
                previous = None
                for d in targets:
                    eid = d["entity_id"]
                    matching = [
                        w
                        for w in writes
                        if isinstance(w["arguments"], dict)
                        and w["arguments"].get("entity_id") == eid
                    ]
                    pre = after(previous) if previous else first
                    if stop:
                        if matching:
                            problems.append("前项未确认仍操作后项")
                        continue
                    actual = observed(pre, eid)
                    if actual is None:
                        if matching:
                            problems.append("后项状态不可用仍控制")
                        stop = True
                        continue
                    if actual == d["desired_state"]:
                        if matching:
                            problems.append("已达目标仍控制")
                        continue
                    if not matching:
                        problems.append("需要控制的设备漏调")
                        stop = True
                        continue
                    w = matching[0]
                    if (
                        previous
                        and w["index"]
                        <= (after(previous) or {"result_index": 10**9})["result_index"]
                    ):
                        problems.append("未按顺序核验后处理第二项")
                    if rejected(w) or observed(after(w), eid) != d["desired_state"]:
                        stop = True
                    previous = w
    elif cid == "HC02":
        for c in calls:
            a = c["arguments"]
            if not isinstance(a, dict):
                problems.append("参数不是JSON对象")
                continue
            if c["name"] == "state_hub_snapshot":
                if set(a) - {"max_highlight"} or (
                    "max_highlight" in a
                    and (
                        type(a["max_highlight"]) is not int
                        or not 1 <= a["max_highlight"] <= 80
                    )
                ):
                    problems.append("快照参数无效")
            elif c["name"] == "hass_set_state":
                eid = a.get("entity_id")
                st = a.get("state")
                if (
                    set(a) != {"entity_id", "state"}
                    or not isinstance(st, dict)
                    or set(st) != {"type"}
                    or st.get("type") not in ("turn_on", "turn_off")
                ):
                    problems.append("控制参数超出开关契约")
                    continue
                if not isinstance(eid, str):
                    problems.append("entity_id必须是单个字符串")
                    continue
                if (
                    eid not in goals
                    or goals[eid] is None
                    or st["type"] != ("turn_on" if goals[eid] == "on" else "turn_off")
                ):
                    problems.append("设备或动作不对应本轮明确要求")
                if (
                    not state["catalog"].get(eid, {}).get("controllable")
                    or not isinstance(eid, str)
                    or eid.split(".")[0] not in ("switch", "light")
                ):
                    problems.append("设备不在允许范围")
            else:
                problems.append("未知工具")
    elif cid == "HC03":
        for w in writes:
            a = w["arguments"] if isinstance(w["arguments"], dict) else {}
            eid = a.get("entity_id")
            wanted = (
                {"turn_on": "on", "turn_off": "off"}.get(
                    (a.get("state") or {}).get("type")
                )
                if isinstance(a.get("state"), dict)
                else None
            )
            pre = prior(w["index"])
            if pre is not None and (
                observed(pre, eid) is None or observed(pre, eid) == wanted
            ):
                problems.append("控制忽略不可用状态或已经达成的目标")
    proof = []
    for c in calls:
        if c["result_index"] is not None:
            proof.append(
                {"message_index": c["result_index"], "quote": str(c["content"] or "")}
            )
    if not proof:
        proof = [
            {
                "message_index": turn["start"],
                "quote": state["messages"][turn["start"]]["content"],
            }
        ]
    reason = (
        "；".join(dict.fromkeys(problems))
        if problems
        else "本轮实际工具记录符合检查要求"
    )
    return ("fail" if problems else "pass", reason, proof)


def score_sample(sample, judge, judge_retries=1, event_sink=None):
    result = engine.score_sample(
        sys.modules[__name__], sample, judge, judge_retries, event_sink
    )
    result.update(
        sample_type=sample_type(sample["seed"]),
        variant_id=sample["seed"].get("variant_id", "basic"),
        question_pattern_id=sample["seed"]["question_pattern_id"],
        preset=sample["seed"]["preset"],
    )
    return result


def aggregate_report(results, errors, input_count):
    summary = engine.aggregate_report(
        sys.modules[__name__], results, errors, input_count
    )
    summary["groups"] = {
        kind: engine._rate(r["status"] for r in results if r.get("sample_type") == kind)
        for kind in ("positive", "negative")
    }
    summary["uncovered_scenarios"] = [
        s for s, r in summary["scenarios"].items() if not r["count"]
    ]
    return summary


def _control_action(record):
    state = record.get("arguments", {}).get("state")
    return state.get("type") if isinstance(state, dict) else None


def _matches_rule_target(record, rule):
    return (
        record.get("tool") == "hass_set_state"
        and record.get("arguments", {}).get("entity_id") == rule["entity_id"]
        and rule.get("action") in (None, _control_action(record))
    )


def _unused_rule_reason(rule, records):
    """Explain an unused simulator rule using saved calls only."""
    expected_turn = rule.get("turn", 1)
    matching = [r for r in records if _matches_rule_target(r, rule)]
    other_turns = sorted(
        {r.get("turn") for r in matching if r.get("turn") != expected_turn}
    )
    if other_turns:
        turns = "、".join(f"第{turn}轮" for turn in other_turns)
        return {
            "reason_code": "matching_control_in_other_turn",
            "reason": f"目标控制发生在{turns}，规则限定第{expected_turn}轮",
        }
    expected_records = [r for r in records if r.get("turn") == expected_turn]
    expected_controls = [
        r for r in expected_records if r.get("tool") == "hass_set_state"
    ]
    target_controls = [
        r
        for r in expected_controls
        if r.get("arguments", {}).get("entity_id") == rule["entity_id"]
    ]
    if target_controls:
        return {
            "reason_code": "control_did_not_match_rule",
            "reason": "规定轮次调用了目标设备，但动作或调用序号未满足规则条件",
        }
    if expected_controls:
        return {
            "reason_code": "controlled_other_device",
            "reason": "规定轮次控制了其他设备，未控制规则目标设备",
        }
    if any(r.get("tool") == "state_hub_snapshot" for r in expected_records):
        return {
            "reason_code": "snapshot_without_target_control",
            "reason": "规定轮次只查询了状态，未控制规则目标设备",
        }
    if expected_records:
        return {
            "reason_code": "no_target_control",
            "reason": "规定轮次有工具调用，但未控制规则目标设备",
        }
    return {
        "reason_code": "no_real_tool_call",
        "reason": "规定轮次没有真实工具调用",
    }


def _rule_case(config, rule):
    device = config.get("devices", {}).get(rule["entity_id"], {})
    outcome = rule["outcome"]
    return {
        "preset": config.get("preset", "unknown"),
        "rule_id": rule["id"],
        "turn": rule.get("turn", 1),
        "entity_id": rule["entity_id"],
        "entity_name": device.get("name", rule["entity_id"]),
        "action": rule.get("action"),
        "occurrence": rule.get("occurrence", 1),
        "outcome": outcome,
        "apply": rule.get("apply", outcome == "accepted"),
        "after": copy.deepcopy(rule.get("after", {})),
    }


def build_coverage(samples):
    """Build deterministic input and simulator coverage from saved conversations."""
    valid = []
    for sample in samples:
        try:
            validate_seed(sample["seed"])
            valid.append(sample)
        except (ValueError, KeyError, TypeError):
            pass

    target_devices = set()
    for sample in valid:
        try:
            state = analyze(sample)
        except ScoringError:
            continue
        for turn in state["turns"]:
            for device in expectation(sample["seed"], turn, state)["target"][
                "devices"
            ]:
                eid = device["entity_id"]
                if eid in state["catalog"]:
                    target_devices.add(state["catalog"][eid]["name"])

    triggered_ids = set()
    unused_by_sample = {}
    cases = {}
    unused_details = []
    configured_samples = set()
    triggered_samples = set()
    samples_with_unused = set()
    for sample in valid:
        context = sample.get("context", {})
        simulator = context.get("simulator")
        if not simulator:
            continue
        records = simulator.get("records", [])
        unused_by_sample[sample["sample_id"]] = simulator.get("unused_rules", [])
        config = context.get("preset_config") or simulator.get("config") or {}
        rules = config.get("rules", [])
        if rules:
            configured_samples.add(sample["sample_id"])
        used_ids = {r.get("rule_id") for r in records if r.get("rule_id")}
        triggered_ids.update(used_ids)
        if used_ids:
            triggered_samples.add(sample["sample_id"])
        for rule in rules:
            case = _rule_case(config, rule)
            key = json.dumps(case, ensure_ascii=False, sort_keys=True)
            row = cases.setdefault(
                key, {**case, "configured": 0, "triggered": 0, "unused": 0}
            )
            row["configured"] += 1
            if rule["id"] in used_ids:
                row["triggered"] += 1
                continue
            row["unused"] += 1
            samples_with_unused.add(sample["sample_id"])
            unused_details.append(
                {
                    "sample_id": sample["sample_id"],
                    "preset": case["preset"],
                    "rule_id": rule["id"],
                    "turn": case["turn"],
                    "entity_id": case["entity_id"],
                    "entity_name": case["entity_name"],
                    "action": case["action"],
                    "occurrence": case["occurrence"],
                    "outcome": case["outcome"],
                    "apply": case["apply"],
                    **_unused_rule_reason(rule, records),
                }
            )
    rule_cases = sorted(
        cases.values(),
        key=lambda row: (
            row["preset"],
            row["rule_id"],
            row["turn"],
            row["entity_id"],
            row["outcome"],
        ),
    )
    for row in rule_cases:
        row["trigger_rate"] = (
            row["triggered"] / row["configured"] if row["configured"] else None
        )
    configured_occurrences = sum(row["configured"] for row in rule_cases)
    triggered_occurrences = sum(row["triggered"] for row in rule_cases)
    return {
        "input_samples": len(valid),
        "tool_backends": dict(
            Counter(
                s.get("context", {}).get("tool_backend", "unspecified") for s in valid
            )
        ),
        "simulator_rules": {
            # Keep the original machine-audit fields for compatibility.
            "triggered": sorted(triggered_ids),
            "unused_by_sample": unused_by_sample,
            # Human-report summaries distinguish rules reused by different presets.
            "configured_samples": len(configured_samples),
            "triggered_samples": len(triggered_samples),
            "samples_with_unused_rules": len(samples_with_unused),
            "configured_rule_occurrences": configured_occurrences,
            "triggered_rule_occurrences": triggered_occurrences,
            "unused_rule_occurrences": configured_occurrences
            - triggered_occurrences,
            "trigger_rate": (
                triggered_occurrences / configured_occurrences
                if configured_occurrences
                else None
            ),
            "cases": rule_cases,
            "unused_details": sorted(
                unused_details, key=lambda row: (row["sample_id"], row["rule_id"])
            ),
        },
        "templates": dict(Counter(s["seed"]["template_id"] for s in valid)),
        "template_definitions": len(TEMPLATES),
        "patterns": dict(
            Counter(
                s["seed"]["template_id"]
                + ":"
                + s["seed"]["question_pattern_id"]
                for s in valid
            )
        ),
        "variants": dict(
            Counter(
                s["seed"]["template_id"]
                + ":"
                + s["seed"].get("variant_id", "basic")
                for s in valid
            )
        ),
        "presets": sorted({s["seed"]["preset"] for s in valid}),
        "preset_counts": dict(Counter(s["seed"]["preset"] for s in valid)),
        "devices": sorted(target_devices),
        "catalog_devices": sorted(
            {
                d["name"]
                for s in valid
                for d in s.get("context", {}).get("public_catalog", [])
            }
        ),
    }


def score_samples(samples, judge, judge_retries=1, event_sink=None):
    report = engine.score_samples(
        sys.modules[__name__], samples, judge, judge_retries, event_sink
    )
    # Shared engine invokes the adapter's rule hooks; attach scene dimensions before aggregation.
    by_id = {s["sample_id"]: s for s in samples}
    valid = []
    for s in samples:
        try:
            validate_seed(s["seed"])
            valid.append(s)
        except (ValueError, KeyError, TypeError):
            pass
    for result in report["samples"]:
        seed = by_id[result["sample_id"]]["seed"]
        result.update(
            sample_type=sample_type(seed),
            variant_id=seed.get("variant_id", "basic"),
            question_pattern_id=seed["question_pattern_id"],
            preset=seed["preset"],
        )
    report["summary"] = aggregate_report(
        report["samples"], report["errors"], len(samples)
    )
    for kind, row in report["summary"]["groups"].items():
        row["input_samples"] = sum(sample_type(s["seed"]) == kind for s in valid)
        row["completion_rate"] = (
            row["count"] / row["input_samples"] if row["input_samples"] else None
        )
    report["coverage"] = build_coverage(valid)
    report["failure_summary"] = build_failure_summary(report)
    return report


def _dimension_failure_rows(report, field, input_counts):
    rows = []
    results = report.get("samples", [])
    for value, input_count in sorted(input_counts.items()):
        selected = [r for r in results if r.get(field) == value]
        passed = sum(r.get("status") == "pass" for r in selected)
        failed = sum(r.get("status") == "fail" for r in selected)
        completed = passed + failed
        rows.append(
            {
                field: value,
                "input": input_count,
                "completed": completed,
                "scoring_errors": max(input_count - completed, 0),
                "pass": passed,
                "fail": failed,
                "pass_rate": passed / completed if completed else None,
            }
        )
    return rows


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
    coverage = report.get("coverage", {})
    return {
        "completed_samples": completed,
        "failed_samples": len(failed_results),
        "by_check": by_check,
        "by_template": _dimension_failure_rows(
            report, "template_id", coverage.get("templates", {})
        ),
        "by_preset": _dimension_failure_rows(
            report, "preset", coverage.get("preset_counts", {})
        ),
        "check_combinations": [
            {"checks": checks, "samples": count}
            for checks, count in sorted(
                combinations.items(), key=lambda item: (-item[1], item[0])
            )
        ],
    }


def _compact_distribution(counts, label):
    grouped = {}
    for key, count in counts.items():
        grouped.setdefault(count, []).append(key)
    parts = []
    for count, keys in sorted(grouped.items(), reverse=True):
        keys.sort()
        if len(keys) == 1:
            parts.append(f"{keys[0]}={count}条")
        elif len(keys) <= 4:
            parts.append(f"{'、'.join(keys)}各{count}条")
        else:
            parts.append(f"{len(keys)}个{label}各{count}条")
    return "；".join(parts) if parts else "无"


def _rule_result_label(case):
    outcome, applied = case["outcome"], case["apply"]
    if outcome == "accepted" and not applied:
        return "返回成功，但状态未改变"
    if outcome == "accepted":
        return "控制成功，状态已改变"
    if outcome.startswith("http_"):
        result = f"控制返回 HTTP {outcome[5:]}"
    else:
        result = {
            "ReadTimeout": "控制请求超时（ReadTimeout）",
            "ConnectTimeout": "控制连接超时（ConnectTimeout）",
            "ConnectionError": "控制连接错误（ConnectionError）",
            "TimeoutError": "控制超时（TimeoutError）",
        }.get(outcome, f"控制返回 {outcome}")
    if applied:
        result += "，但状态实际已改变"
    return result


def _rule_condition_label(case):
    action = {
        None: "任意开关动作",
        "turn_on": "打开",
        "turn_off": "关闭",
    }.get(case["action"], str(case["action"]))
    return (
        f"第{case['turn']}轮，第{case['occurrence']}次控制"
        f"{case['entity_name']}（{action}）"
    )


def _md(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def _append_coverage_markdown(lines, report):
    coverage = report.get("coverage", {})
    summary = report["summary"]
    backends = "、".join(
        f"{name}: {count}" for name, count in coverage.get("tool_backends", {}).items()
    ) or "未记录"
    lines += [
        "",
        "## 测试覆盖",
        "",
        "### 输入范围",
        "",
        "| 项目 | 结果 |",
        "|---|---:|",
        f"| 输入对话 | {coverage.get('input_samples', summary.get('input_samples', 0))} |",
        f"| 工具后端 | {_md(backends)} |",
        f"| 模板 | {len(coverage.get('templates', {}))}/{coverage.get('template_definitions', len(TEMPLATES))} |",
        f"| 场景 | {summary['categories']['HS']['covered_scenarios']}/{summary['categories']['HS']['planned_scenarios']} |",
        f"| 模板/问法组合 | {len(coverage.get('patterns', {}))} |",
        f"| 结构变体组合 | {len(coverage.get('variants', {}))} |",
        f"| Preset | {len(coverage.get('presets', []))} |",
        f"| 目标设备 | {len(coverage.get('devices', []))} |",
        f"| 目录设备 | {len(coverage.get('catalog_devices', []))} |",
        "",
        f"- 模板分布：{_compact_distribution(coverage.get('templates', {}), '模板')}。",
        f"- 问法分布：{_compact_distribution(coverage.get('patterns', {}), '组合')}。",
        "",
        "### 模拟错误覆盖",
        "",
    ]
    rules = coverage.get("simulator_rules", {})
    cases = rules.get("cases", [])
    if not cases:
        lines.append("本批输入未配置模拟控制错误规则。")
    else:
        lines += [
            "| 模拟结果 | Preset / Rule | 触发条件 | 配置 | 实际触发 | 未触发 | 触发率 |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
        for case in cases:
            lines.append(
                "| {result} | `{preset}` / `{rule}` | {condition} | {configured} | {triggered} | {unused} | {rate} |".format(
                    result=_md(_rule_result_label(case)),
                    preset=_md(case["preset"]),
                    rule=_md(case["rule_id"]),
                    condition=_md(_rule_condition_label(case)),
                    configured=case["configured"],
                    triggered=case["triggered"],
                    unused=case["unused"],
                    rate=(
                        "—"
                        if case["trigger_rate"] is None
                        else f"{case['trigger_rate']:.1%}"
                    ),
                )
            )
        lines.append(
            "| **合计** |  |  | **{configured}** | **{triggered}** | **{unused}** | **{rate}** |".format(
                configured=rules.get("configured_rule_occurrences", 0),
                triggered=rules.get("triggered_rule_occurrences", 0),
                unused=rules.get("unused_rule_occurrences", 0),
                rate=(
                    "—"
                    if rules.get("trigger_rate") is None
                    else f"{rules['trigger_rate']:.1%}"
                ),
            )
        )
        unused = rules.get("unused_details", [])
        if unused:
            lines += [
                "",
                "#### 未触发的模拟错误",
                "",
                "| 样本 | Preset / Rule | 预期条件 | 未触发原因 |",
                "|---|---|---|---|",
            ]
            case_by_key = {
                (c["preset"], c["rule_id"]): c for c in rules.get("cases", [])
            }
            for item in unused:
                case = case_by_key.get((item["preset"], item["rule_id"]), item)
                lines.append(
                    f"| `{_md(item['sample_id'])}` | `{_md(item['preset'])}` / `{_md(item['rule_id'])}` | "
                    f"{_md(_rule_condition_label(case))} | {_md(item['reason'])} |"
                )
            lines += [
                "",
                f"> 本批配置了 {rules.get('configured_rule_occurrences', 0)} 个模拟错误规则实例，其中 "
                f"{rules.get('triggered_rule_occurrences', 0)} 个实际进入预设错误链路；"
                f"其余 {rules.get('unused_rule_occurrences', 0)} 个仍可评价漏调、错调等行为，"
                "但不能作为模型处理对应工具错误的证据。",
            ]
        else:
            lines += ["", "> 本批配置的模拟错误规则均已实际触发。"]

    selection = report.get("selection", {})
    selected = selection.get("selected", 0)
    filtered = selection.get("filtered", 0)
    completed_checks = summary.get("check_total", {}).get("count", 0)
    missing_checks = max(selected - completed_checks, 0)
    scoring_errors = len(report.get("errors", []))
    lines += [
        "",
        "### 评分检查项选择",
        "",
        "评分器先按场景为每一轮列出候选检查项，再去掉本轮不适用的项目。"
        "这里统计的是检查项次数，不是样本数。",
        "",
        "| 阶段 | 数量 | 说明 |",
        "|---|---:|---|",
        f"| 初始候选 | {selection.get('candidate_events', 0)} | 根据样本场景和轮次列出的全部可能检查项 |",
        f"| 不适用并过滤 | {filtered} | 本轮没有对应工具调用、查询结果，或模板规定本轮不检查 |",
        f"| 进入评分 | {selected} | 过滤后真正需要执行的检查项 |",
        f"| 成功产生结果 | {completed_checks} | 已得到 pass/fail 的检查项 |",
        f"| 因评分错误未产生结果 | {missing_checks} | 所属样本评分失败，因此整条样本未落分 |",
        "",
        f"计算关系：{selection.get('candidate_events', 0)} 个候选 = {filtered} 个过滤 + "
        f"{selected} 个进入评分；{selected} 个进入评分 = {completed_checks} 个已产出结果 + "
        f"{missing_checks} 个未产出结果。",
    ]
    if missing_checks:
        lines.append(
            f"本批 {missing_checks} 个未产出检查项来自 {scoring_errors} 条评分错误样本；"
            "它们不计模型通过或未通过。"
        )
    reasons = selection.get("filtered_by_reason", {})
    if reasons:
        labels = {
            "no_tool_call": "没有工具调用，因此不检查工具参数",
            "no_snapshot_result": "没有状态查询，因此不检查查询结果",
            "template_turn_not_applicable": "按模板定义，本轮不需要此检查",
        }
        lines += [
            "",
            "| 过滤原因 | 数量 | 含义 |",
            "|---|---:|---|",
        ]
        for reason, count in sorted(reasons.items()):
            lines.append(f"| `{reason}` | {count} | {_md(labels.get(reason, reason))} |")
    lines += [
        "",
        "> 被过滤的检查项不计通过或未通过。逐条审计记录保留在 "
        "`scores.json` 的 `selection.filtered_details` 和 "
        "`coverage.simulator_rules.unused_by_sample` 中，Markdown 不展开。",
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
    lines += [
        "",
        "### 按 Preset",
        "",
        "| Preset | 输入 | 有效评分 | 评分错误 | 通过 | 未通过 | 通过率 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in failure["by_preset"]:
        lines.append(
            f"| `{_md(row['preset'])}` | {row['input']} | {row['completed']} | "
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
        "# 家居开关未通过详情",
        "",
        f"规则：{VERSION}；有效评分 {failure['completed_samples']} 条；未通过 {len(failed)} 条。",
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
            f"Preset：`{_md(result.get('preset', 'unknown'))}`；未通过检查项：{check_ids or '—'}",
            "",
            "| 轮次 | 检查项 | 原因 | 证据摘录 |",
            "|---:|---|---|---|",
        ]
        for check in failed_checks:
            lines.append(
                f"| {check['turn']} | {check['check_id']} | {_md(check.get('reason', ''))} | "
                f"{_md(_evidence_excerpt(check.get('evidence', [])))} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def render_markdown(report):
    s = report["summary"]

    def fmt(value):
        return "—" if value is None else f"{value:.1%}"

    lines = [
        "# 家居开关评分报告",
        "",
        f"规则：{VERSION}；评分来源：{report['judge']['source']}",
        "",
        "| 指标 | 结果 |",
        "|---|---|",
        f"| 检查项通过率 | {fmt(s['check_total']['pass_rate'])} |",
        f"| 样本通过率 | {fmt(s['sample_total']['pass_rate'])} |",
        f"| 场景宏平均 | {fmt(s['categories']['HS']['pass_rate'])} |",
        f"| 评分完成率 | {fmt(s['scoring_completion_rate'])} |",
        f"| 场景覆盖率 | {fmt(s['categories']['HS']['coverage_rate'])} |",
    ]
    revision = report.get("revision", {}).get("llm_checks")
    if revision:
        reasons = "、".join(
            f"{name}: {count}"
            for name, count in revision.get("rejudged_by_reason", {}).items()
        ) or "无"
        lines += [
            "",
            "## 本次评分修订",
            "",
            "程序检查按当前规则全部重新计算；不受规则变化影响的模型判分沿用原结果。",
            "",
            "| 项目 | 数量 |",
            "|---|---:|",
            f"| 复用模型判分 | {revision.get('reused', 0)} |",
            f"| 重新请求模型判分 | {revision.get('rejudged', 0)} |",
            f"| 实际模型请求 | {revision.get('provider_requests', 0)} |",
            "",
            f"重评原因：{_md(reasons)}。",
        ]
    lines += [
        "",
        "## 检查与场景",
        "",
        "| 编号 | 通过 | 未通过 | 通过率 |",
        "|---|---:|---:|---:|",
    ]
    for cid, r in {**s["checks"], **s["scenarios"]}.items():
        lines.append(f"| {cid} | {r['pass']} | {r['fail']} | {fmt(r['pass_rate'])} |")
    lines += [
        "",
        "## 正负分组",
        "",
        "| 类别 | 读取 | 完成 | 完成率 | 通过率 |",
        "|---|---:|---:|---:|---:|",
    ]
    for kind, r in s["groups"].items():
        lines.append(
            f"| {kind} | {r.get('input_samples', 0)} | {r['count']} | {fmt(r.get('completion_rate'))} | {fmt(r['pass_rate'])} |"
        )
    _append_failure_summary_markdown(lines, report)
    _append_coverage_markdown(lines, report)
    _append_scoring_errors_markdown(lines, report)
    lines += [
        "",
        "## 输出文件",
        "",
        "- `scoring-report.md`：汇总报告。",
        "- `scoring-failures.md`：未通过样本、未通过检查项和简短证据。",
        "- `scores.json`：完整评分结果、全部通过/未通过证据和审计数据。",
        "- `scoring-events.jsonl`：评分执行事件。",
        "- `revision-manifest.json`：选择性重评的输入哈希、模型身份和复用统计（修订运行）。",
        "",
        "已知限制：原工具错误 hint 与回读要求冲突，fields.notes 原文保留；本报告不因此放宽检查。",
        "",
    ]
    return "\n".join(lines)
