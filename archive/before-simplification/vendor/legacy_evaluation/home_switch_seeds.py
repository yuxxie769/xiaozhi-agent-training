"""Home-switch 1.5 templates and preset-grounded seed generation."""

import copy
import json
import random
import re
import sys
from pathlib import Path

VERSION = "home_switch/1.5"
TEMPLATES = json.loads(
    Path(__file__).with_name("home-switch-templates.json").read_text()
)["templates"]
FORBIDDEN = {
    "device_fixture",
    "tool_behavior",
    "turn_expectations",
    "reply_action",
    "random_seed",
    "sample_type",
}


def sample_type(seed):
    return "positive" if int(seed["template_id"][1:]) <= 16 else "negative"


def definition(seed):
    template = TEMPLATES[seed["template_id"]]
    variant = seed.get("variant_id", "basic")
    if variant == "basic":
        return template
    if variant not in template["variants"]:
        raise ValueError("未知或不属于模板的variant_id")
    return template["variants"][variant]


def turn_scenarios(seed):
    scenes = copy.deepcopy(definition(seed)["scenarios"])
    form = seed.get("request_form", "single")
    if form == "two_devices":
        for n in range(len(scenes)):
            if seed["template_id"] in ("T19", "T20") or (
                seed["template_id"] == "T18" and n == 1
            ):
                scenes[n] = [s for s in scenes[n] if s != "HS01"] + ["HS14"]
    elif form == "mixed":
        scenes[0].append("HS15")
    return [list(dict.fromkeys(row)) for row in scenes]


def target(*pairs):
    return {
        "devices": [
            {"entity_id": entity, "desired_state": state} for entity, state in pairs
        ]
    }


def validate_seed(seed, library=None, config=None):
    if (
        seed.get("design_version") != VERSION
        or seed.get("template_id") not in TEMPLATES
    ):
        raise ValueError("家居Seed版本或模板无效；旧草稿不能只改版本号")
    if FORBIDDEN & set(seed):
        raise ValueError("家居Seed含已废弃字段")
    if seed.get("question_pattern_id") not in ("P1", "P2", "P3"):
        raise ValueError("缺少有效question_pattern_id")
    if (
        not seed.get("preset")
        or not seed.get("seed_id")
        or not seed.get("variable_group_id")
    ):
        raise ValueError("Seed身份或preset缺失")
    form = seed.get("request_form", "single")
    if form not in ("single", "two_devices", "mixed") or (
        form != "single" and seed["template_id"] not in ("T18", "T19", "T20")
    ):
        raise ValueError("无效的请求结构")
    if seed["template_id"] == "T11" and not seed.get("target_selector"):
        raise ValueError("候选模板缺少target_selector")
    if (
        seed["template_id"] == "T20"
        and seed.get("variant_id") == "query_after_error"
        and ("first_target" not in seed or form != "single")
    ):
        raise ValueError("异常后查询需要单设备及first_target")
    scenes = turn_scenarios(seed)
    if len(seed.get("user_turns", [])) != len(scenes) or any(
        not isinstance(t, str) or not t.strip() for t in seed["user_turns"]
    ):
        raise ValueError("Seed轮数与模板不匹配")
    if set(seed.get("scenario_ids", [])) != {s for row in scenes for s in row}:
        raise ValueError("Seed场景并集与模板不匹配")
    refs = []
    for name in ("target", "first_target"):
        obj = seed.get(name)
        if name == "first_target" and obj is None:
            continue
        if (
            not isinstance(obj, dict)
            or set(obj) != {"devices"}
            or not isinstance(obj["devices"], list)
            or len(obj["devices"]) > 2
        ):
            raise ValueError("target必须包含最多两个devices")
        ids = []
        for item in obj["devices"]:
            if set(item) != {"entity_id", "desired_state"} or item[
                "desired_state"
            ] not in ("on", "off", None):
                raise ValueError("target设备或目标状态无效")
            eid = item["entity_id"]
            if eid is not None and (not isinstance(eid, str) or not eid):
                raise ValueError("entity_id无效")
            if eid is not None:
                ids.append(eid)
            refs.append(eid)
        if len(ids) != len(set(ids)):
            raise ValueError("目标设备不得重复")
    selector = seed.get("target_selector")
    if selector:
        if selector.get("kind") == "exclude":
            if (
                not isinstance(selector.get("entity_id"), str)
                or not selector["entity_id"]
            ):
                raise ValueError("排除候选必须引用明确编号")
            refs.append(selector.get("entity_id"))
        elif selector != {"kind": "displayed_index", "index": 2}:
            raise ValueError("候选选择关系无效")
    if (
        seed["template_id"] in ("T05", "T06", "T15", "T17")
        and seed.get("variant_id") != "no_action"
        and "first_target" not in seed
    ):
        raise ValueError("模板缺少first_target")
    expected_count = (
        0
        if seed["template_id"] == "T17"
        else 2
        if seed["template_id"] in ("T13", "T14") or form == "two_devices"
        else 1
    )
    if len(seed["target"]["devices"]) != expected_count:
        raise ValueError("target设备数量与模板不一致")
    if (
        seed["template_id"] == "T11"
        and seed["target"]["devices"][0]["entity_id"] is not None
    ):
        raise ValueError("候选选择必须保留空编号，不能预填答案")
    query = seed["template_id"] == "T02" or (
        seed["template_id"] == "T20" and seed.get("variant_id") == "query_after_error"
    )
    if any((d["desired_state"] is None) != query for d in seed["target"]["devices"]):
        raise ValueError("target目标状态与查询或控制模板不一致")
    if (
        seed["template_id"] == "T07"
        and seed.get("variant_id") == "change_action"
        and "first_target" not in seed
    ):
        raise ValueError("修改动作变体缺少first_target")
    if library:
        library.validate_entities(seed["preset"], refs)
    if config:
        if config.get("preset") != seed["preset"] or any(
            e is not None and e not in config["devices"] for e in refs
        ):
            raise ValueError("目标编号不属于运行时preset")
    return seed

