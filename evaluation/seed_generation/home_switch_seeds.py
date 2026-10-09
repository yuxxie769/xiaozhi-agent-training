"""Home-switch 1.5 templates and preset-grounded seed generation."""

import copy
import json
import random
import re
from pathlib import Path

from snapshot_library import Library, PresetError

SERVER = Path(__file__).resolve().parent

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


def public_catalog(config):
    return [
        {
            "entity_id": eid,
            **{
                k: copy.deepcopy(d[k])
                for k in ("name", "aliases", "room", "controllable")
                if k in d
            },
        }
        for eid, d in config["devices"].items()
    ]


def real_library(path, presets):
    """Validate declared real permissions before any device request is sent."""
    root = Path(path).resolve()
    builtin = (SERVER / "core/home_switch_simulator/presets").resolve()
    if root.is_relative_to(builtin):
        raise ValueError("真实测试不得使用内置模拟设备库")
    library = Library(root)
    files = (
        [root]
        if root.is_file()
        else list(root.glob("*.json")) + list((root / "special").glob("*.json"))
    )
    for file in files:
        raw = json.loads(file.read_text(encoding="utf-8"))
        if raw["id"] in presets and any(
            type(d.get("controllable")) is not bool for d in raw.get("devices", [])
        ):
            raise ValueError("真实preset每个设备必须显式声明controllable权限")
    return library


def category(device):
    name = device["name"]
    return "插座" if "插座" in name else "灯" if "灯" in name else "开关"


def eligible(library, preset, tid, variant):
    cfg = library.resolve(preset)
    rows = library.get_devices(preset)
    writable = [d for d in rows if d["controllable"]]
    if not writable:
        return False
    special = {x["preset"] for x in library.list_special_presets()}
    if tid == "T19":
        initial = cfg.get("initial", {})
        return preset in special and (
            initial.get("connected") is False
            or initial.get("outdated") is True
            or bool(initial.get("snapshot_error"))
            or bool(initial.get("hidden"))
            or any(
                v in ("unknown", "unavailable")
                for v in initial.get("states", {}).values()
            )
        )
    if tid == "T20":
        return preset in special and bool(cfg.get("rules"))
    if preset in special:
        return False
    count = (
        3
        if tid == "T14"
        else 2
        if tid in ("T05", "T07", "T10", "T11", "T13", "T15", "T17")
        and variant not in ("no_action", "cancel_after_execution")
        else 1
    )
    if len(writable) < count:
        return False
    if tid in ("T07", "T10", "T11", "T14", "T17") and variant not in (
        "no_action",
        "cancel_after_execution",
    ):
        return any(
            (
                sum(category(d) == c for d in writable) == 2
                if tid == "T11" and variant == "exclude"
                else sum(category(d) == c for d in writable) >= count
            )
            for c in ("插座", "灯", "开关")
        )
    return True


def make_group(library, preset, tid, variant, group, rng, form="single"):
    cfg = library.resolve(preset)
    devices = library.get_devices(preset, controllable_only=True)
    candidates = library.get_devices(
        preset, candidates_only=True, controllable_only=True
    )
    if tid in ("T07", "T10", "T11", "T14", "T17") and variant not in (
        "no_action",
        "cancel_after_execution",
    ):
        count = 3 if tid == "T14" else 2
        classes = [
            c
            for c in ("插座", "灯", "开关")
            if (
                sum(category(d) == c for d in devices) == 2
                if tid == "T11" and variant == "exclude"
                else sum(category(d) == c for d in devices) >= count
            )
        ]
        chosen = rng.choice(classes)
        devices = [d for d in devices if category(d) == chosen]
        candidates = [d for d in candidates if category(d) == chosen]
    a = rng.choice(candidates or devices)
    if tid == "T19":
        initial = cfg.get("initial", {})
        affected = set(initial.get("hidden", [])) | {
            e
            for e, v in initial.get("states", {}).items()
            if v in ("unknown", "unavailable")
        }
        if affected:
            options = [d for d in devices if d["entity_id"] in affected]
            if options:
                a = rng.choice(options)
    if tid == "T20":
        rule = cfg["rules"][0]
        a = next(d for d in devices if d["entity_id"] == rule["entity_id"])
    others = [d for d in devices if d["entity_id"] != a["entity_id"]]
    b = rng.choice(others) if others else a
    if tid == "T20" and form == "two_devices" and group % 2 == 0:
        a, b = b, a
    eid, bid = a["entity_id"], b["entity_id"]
    state = rng.choice(["on", "off"])
    if tid == "T20":
        state = {"turn_on": "on", "turn_off": "off"}.get(
            rule.get("action"),
            "off"
            if next(d for d in devices if d["entity_id"] == rule["entity_id"])["state"]
            == "on"
            else "on",
        )
    action = "打开" if state == "on" else "关闭"
    values = {
        "设备": a["name"],
        "设备一": a["name"],
        "设备二": b["name"],
        "设备全称": a["name"],
        "设备类别": category(a),
        "模糊称呼": category(a),
        "设备称呼": rng.choice([a["name"]] + a["aliases"]),
        "动作": action,
        "动作一": action,
        "动作二": action,
        "排除设备": b["name"],
        "独立请求": "讲个笑话",
        "非操作话语": "不要关闭" + a["name"],
        "控制请求": action + a["name"],
        "不支持请求": "十分钟后" + action + a["name"],
        "有效请求": "立即" + action + a["name"],
    }
    base = {
        "design_version": VERSION,
        "template_id": tid,
        "variable_group_id": f"{tid}-G{group:03}",
        "preset": preset,
        "target": target((eid, state)),
    }
    if variant != "basic":
        base["variant_id"] = variant
    if tid == "T02":
        base["target"] = target((eid, None))
    if tid == "T03":
        base["target"] = target((eid, "off"))
    if tid == "T05":
        base.update(first_target=target((eid, state)), target=target((bid, state)))
    if tid == "T06":
        base.update(first_target=target((eid, "on")), target=target((eid, "off")))
    if tid == "T07":
        base["target"] = target((eid, "on" if variant == "change_action" else "off"))
        if variant == "change_action":
            base["first_target"] = target((None, "off"))
    if tid == "T11":
        base["target"] = target((None, state))
        base["target_selector"] = (
            {"kind": "exclude", "entity_id": bid}
            if variant == "exclude"
            else {"kind": "displayed_index", "index": 2}
        )
    if tid == "T12":
        base["target"] = target((eid, "off"))
    if tid in ("T13", "T14"):
        second = (
            ("off" if state == "on" else "on")
            if tid == "T13" and group % 2 == 0
            else state
        )
        values["动作二"] = "打开" if second == "on" else "关闭"
        base["target"] = target(
            (eid, state if tid == "T13" else "off"),
            (bid, second if tid == "T13" else "off"),
        )
    if tid == "T15":
        base.update(
            first_target=target((eid, "on"), (bid, "on")), target=target((bid, "off"))
        )
    if tid == "T16":
        base["other_request"] = "讲个笑话"
    if tid == "T17":
        base["target"] = target()
        if variant != "no_action":
            base["first_target"] = (
                target((eid, "on"))
                if variant == "cancel_after_execution"
                else target((None, "off"))
            )
    if tid == "T18":
        unsupported = [
            "十分钟后" + action + a["name"],
            "天黑后" + action + a["name"],
            "把" + a["name"] + "亮度调到一半",
            action + "全屋设备",
        ]
        restricted = [d for d in library.get_devices(preset) if not d["controllable"]]
        if restricted:
            unsupported.append(action + restricted[0]["name"])
        values["不支持请求"] = unsupported[(group - 1) % len(unsupported)]
    if tid in ("T18", "T19", "T20") and form != "single":
        base["request_form"] = form
        if form == "two_devices":
            base["target"] = target((eid, state), (bid, state))
            values["控制请求"] = action + a["name"] + "，再" + action + b["name"]
            values["有效请求"] = "立即" + values["控制请求"]
        else:
            base["other_request"] = "讲个笑话"
            values["控制请求"] += "，再讲个笑话"
    if tid == "T20" and variant == "query_after_error":
        base["first_target"] = base["target"]
        base["target"] = target((eid, None))
    rows = []
    for pattern, wording in definition(base)["patterns"].items():
        # Generalize the legacy socket wording to the actual category.
        if tid == "T17" and variant in ("basic", "change_topic"):
            wording = wording.replace("插座", "{设备类别}")
        wording = wording.format_map(values)
        turns = [re.sub(r"^[①②③]\s*", "", x.strip()) for x in wording.split("→")]
        seed = {
            **copy.deepcopy(base),
            "seed_id": f"{tid}-G{group:03}-{pattern}",
            "question_pattern_id": pattern,
            "user_turns": turns,
        }
        seed["scenario_ids"] = sorted({s for row in turn_scenarios(seed) for s in row})
        validate_seed(seed, library)
        rows.append(seed)
    return rows


def generate_seeds(
    library, presets=None, templates=None, groups_per_template=10, random_seed=42
):
    if groups_per_template < 1:
        raise ValueError("变量组数必须大于0")
    rng = random.Random(random_seed)
    seeds = []
    unavailable = []
    pool = presets or [p["preset"] for p in library.list_presets(include_special=True)]
    for tid in templates or TEMPLATES:
        if tid not in TEMPLATES:
            raise ValueError("未知模板")
        variants = ["basic", *TEMPLATES[tid]["variants"]]
        for g in range(1, groups_per_template + 1):
            variant = variants[(g - 1) % len(variants)]
            choices = [p for p in pool if eligible(library, p, tid, variant)]
            if not choices:
                unavailable.append(
                    {
                        "template_id": tid,
                        "variant_id": variant,
                        "group": g,
                        "reason": "没有满足模板条件的preset",
                    }
                )
                continue
            preset = rng.choice(choices)
            form = "single"
            if tid in ("T18", "T19", "T20") and variant == "basic":
                count = len(library.get_devices(preset, controllable_only=True))
                form = (
                    ("single", "two_devices", "mixed")[(g - 1) % 3]
                    if count >= 2
                    else "single"
                )
                if tid == "T18" and form == "mixed":
                    form = "single"
            seeds.extend(make_group(library, preset, tid, variant, g, rng, form))
    return seeds, unavailable
