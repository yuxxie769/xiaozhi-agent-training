"""Generate weather conversation seeds without running the model or weather tool."""

import argparse
import json
import random
import string
from pathlib import Path


CLIENT_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATES = CLIENT_DIR / "weather-seed-templates.json"
DEFAULT_LEXICON = CLIENT_DIR / "weather-seed-lexicon.json"
QUERY_TEXT = {
    "overview": "天气情况",
    "rain": "降雨情况",
    "temperature": "气温情况",
    "wind": "风力情况",
    "humidity": "湿度情况",
}
GENERAL_QUERY_KINDS = ("overview", "rain", "temperature")
SUCCESS_TEMPLATES = {
    "S01", "S02", "S05", "S06", "S07", "S10", "S11", "S12", "S13",
    "S15", "S19", "S20", "S21", "S22",
}
EXPLICIT_CITY_TEMPLATES = {
    "S02", "S05", "S06", "S07", "S17", "S19", "S20", "S21", "S22",
}
TEMPLATE_IDS = tuple(
    f"S{number:02}" for number in range(1, 26)
    if number not in {14, 16, 18, 23, 25}
)


def read_json(path):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def day_phrase(offset):
    if offset == 0:
        return "今天"
    if offset == 1:
        return "明天"
    if offset == 2:
        return "后天"
    return f"{offset}天后"


def pick_city(lexicon, rng, excluded=()):
    choices = [city for city in lexicon["default_cities"] if city not in excluded]
    if not choices:
        raise ValueError("城市词条库没有满足排除条件的地点")
    return rng.choice(choices)


def sample_variables(template_id, group_index, lexicon, rng, fixed_default_city=None):
    values = {
        "default_city": fixed_default_city or pick_city(lexicon, rng),
        "target_city": None,
        "target_day": rng.randint(0, 6),
        "query_kind": rng.choice(
            tuple(QUERY_TEXT)
            if template_id == "S01" and fixed_default_city
            else GENERAL_QUERY_KINDS
        ),
        "date_mode": "relative",
    }
    if template_id in {"S01", "S03", "S04", "S10"}:
        values["target_day"] = 0 if template_id == "S01" else None
    if template_id == "S01":
        values.update(target_city=values["default_city"], date_mode="omitted")
    elif template_id == "S02":
        if group_index < 3:
            values["target_day"] = (0, 1, 6)[group_index]
        values["date_mode"] = "omitted" if group_index == 3 else "relative"
        if values["date_mode"] == "omitted":
            values["target_day"] = 0
    elif template_id == "S03":
        values["weather_remark"] = rng.choice(lexicon["weather_remarks"])
    elif template_id == "S04":
        values["other_request"] = rng.choice(lexicon["other_requests"])
    elif template_id == "S05":
        values["date_mode"] = rng.choice(("omitted", "relative"))
        if values["date_mode"] == "omitted":
            values["target_day"] = 0
        values["other_request"] = rng.choice(lexicon["other_requests"])
        values["request_order"] = rng.choice(("weather_first", "other_first"))
    elif template_id == "S06":
        values["start_day"] = rng.randint(0, 5)
        values["day_count"] = rng.randint(2, min(4, 7 - values["start_day"]))
        values["target_days"] = list(
            range(values["start_day"], values["start_day"] + values["day_count"])
        )
        values["target_day"] = None
    elif template_id == "S07":
        values["vague_date_text"] = rng.choice(lexicon["vague_dates"])
    elif template_id == "S08":
        values["days_ago"] = rng.randint(1, 14)
        values["target_day"] = None
    elif template_id == "S09":
        values["days_ahead"] = rng.choice((30, 60, 90, 365, 730))
        values["target_day"] = None
    elif template_id == "S11":
        pair = rng.choice(lexicon["province_cities"])
        values.update(province=pair["province"], target_city=pair["city"])
    elif template_id in {"S12", "S13"}:
        place = rng.choice(lexicon["ambiguous_places"])
        values.update(
            ambiguous_name=place["name"], target_adm=place["adm"],
            target_city=place["city"],
        )
    elif template_id == "S15":
        values["invalid_location"] = rng.choice(lexicon["invalid_places"])
    elif template_id == "S19":
        values["first_day"] = rng.choice(
            [offset for offset in range(7) if offset != values["target_day"]]
        )
    elif template_id == "S22":
        detail = rng.choice(lexicon["detail_questions"])
        values.update(requested_field=detail["field"], detail_question=detail["text"])
    elif template_id == "S24":
        values["clarification_kind"] = ("city", "date")[group_index % 2]
        if values["clarification_kind"] == "city":
            pair = rng.choice(lexicon["province_cities"])
            values.update(province=pair["province"], target_city=None)
        else:
            values["target_city"] = pick_city(lexicon, rng)
            values["vague_date_text"] = rng.choice(lexicon["vague_dates"])
            values["target_day"] = None
        values["cancel_text"] = rng.choice(lexicon["cancel_texts"])

    if template_id in {
        "S02", "S05", "S07", "S08", "S09", "S15", "S17", "S19", "S20",
        "S21", "S22",
    } and values["target_city"] is None:
        values["target_city"] = pick_city(
            lexicon, rng, (values["default_city"],)
        )
    if template_id == "S06" or template_id == "S10":
        values["target_city"] = pick_city(lexicon, rng, (values["default_city"],))
    if template_id == "S20":
        values["first_city"] = pick_city(lexicon, rng, (values["target_city"],))
    if template_id == "S21":
        values["target_city"] = pick_city(lexicon, rng, (values["default_city"],))
    if template_id in {"S11", "S12", "S13"} and values["default_city"] == values["target_city"]:
        values["default_city"] = pick_city(lexicon, rng, (values["target_city"],))
    if template_id == "S15" and values["target_city"] == values["default_city"]:
        values["target_city"] = pick_city(lexicon, rng, (values["default_city"],))
    return values


def render_values(values):
    result = dict(values)
    result["query_text"] = QUERY_TEXT[values["query_kind"]]
    offset = values["target_day"]
    result["day_text"] = (
        "" if values["date_mode"] == "omitted" else day_phrase(offset)
    ) if offset is not None else ""
    if "first_day" in values:
        result["first_day_text"] = day_phrase(values["first_day"])
    if "start_day" in values:
        result["start_text"] = day_phrase(values["start_day"])
    if "days_ago" in values:
        days = values["days_ago"]
        result["past_text"] = {1: "昨天", 2: "前天"}.get(days, f"{days}天前")
    if "days_ahead" in values:
        result["future_text"] = f"{values['days_ahead']}天后"
    if "other_request" in values and "target_city" in values and values["target_city"]:
        weather_clause = (
            f"查{values['target_city']}{result['day_text']}的{result['query_text']}"
        )
        other_clause = values["other_request"]
        result["first_clause"], result["second_clause"] = (
            (weather_clause, other_clause)
            if values.get("request_order") == "weather_first"
            else (other_clause, weather_clause)
        )
    if "clarification_kind" in values:
        if values["clarification_kind"] == "city":
            result["clarification_subject"] = values["province"] + result["day_text"]
        else:
            result["clarification_subject"] = (
                values["target_city"] + values["vague_date_text"]
            )
    return result


def scenario_ids(template, values):
    ids = list(template["scenario_ids"])
    template_id = template["id"]
    if template_id == "S24":
        ids.append("L04" if values["clarification_kind"] == "city" else "T04")
    if template_id == "S01" or (
        values["date_mode"] == "omitted"
        and template_id not in {"S03", "S04", "S24"}
    ):
        ids.append("T01")
    elif values["target_day"] is not None and template_id not in {
        "S03", "S04", "S06", "S10", "S24"
    }:
        ids.append("T02")
    if template_id in EXPLICIT_CITY_TEMPLATES:
        ids.append("L01")
    if template_id == "S21":
        ids.append("L02")
    if template_id in {"S11", "S12"}:
        ids.append("M01")
    if template_id in SUCCESS_TEMPLATES:
        ids.extend(("F01", "O01", "O02"))
    if template_id == "S15":
        ids.append("O02")
    ids.append("O04")
    return list(dict.fromkeys(ids))


def validate_template_data(templates, lexicon):
    ids = [item["id"] for item in templates]
    expected = list(TEMPLATE_IDS)
    if ids != expected:
        raise ValueError("模板 ID 与当前启用清单不一致")
    for item in templates:
        patterns = item.get("patterns")
        if not isinstance(patterns, list) or len(patterns) != 3:
            raise ValueError(f"{item['id']} 必须有三套问法骨架")
        if not all(isinstance(pattern, list) and pattern and all(
            isinstance(turn, str) and turn for turn in pattern
        ) for pattern in patterns):
            raise ValueError(f"{item['id']} 的问法骨架必须是非空消息列表")
        if len({tuple(pattern) for pattern in patterns}) != 3:
            raise ValueError(f"{item['id']} 的三套问法骨架不能相同")
        if not item.get("variables") or not item.get("constraints") or not item.get("scenario_ids"):
            raise ValueError(f"{item['id']} 缺少变量、约束或场景映射")
    for key in (
        "default_cities", "province_cities", "ambiguous_places",
        "invalid_places", "weather_remarks", "other_requests", "vague_dates",
        "cancel_texts", "detail_questions",
    ):
        if not lexicon.get(key):
            raise ValueError(f"词条库缺少 {key}")


def generate_seeds(templates, lexicon, random_seed=42, groups_per_template=5,
                   selected_templates=None, default_city=None):
    if groups_per_template < 1:
        raise ValueError("groups_per_template 必须至少为 1")
    validate_template_data(templates, lexicon)
    available = {item["id"] for item in templates}
    selected = set(selected_templates or available)
    unknown = selected - available
    if unknown:
        raise ValueError(f"未知模板：{', '.join(sorted(unknown))}")
    rng = random.Random(random_seed)
    if default_city is not None and (
        not isinstance(default_city, str) or not default_city.strip()
    ):
        raise ValueError("default_city 必须是非空字符串")
    default_city = default_city.strip() if isinstance(default_city, str) else None
    seeds = []
    formatter = string.Formatter()
    for template in templates:
        template_id = template["id"]
        if template_id not in selected:
            continue
        seen_groups = set()
        for group_number in range(1, groups_per_template + 1):
            for _ in range(500):
                values = sample_variables(
                    template_id,
                    group_number - 1,
                    lexicon,
                    rng,
                    fixed_default_city=default_city,
                )
                signature = json.dumps(
                    {key: values[key] for key in template["variables"] if key in values},
                    ensure_ascii=False, sort_keys=True,
                )
                if signature not in seen_groups:
                    seen_groups.add(signature)
                    break
            else:
                raise ValueError(f"{template_id} 的词条不足以生成不重复的变量组")
            rendered = render_values(values)
            group_id = f"{template_id}-G{group_number:02}"
            same_group = set()
            for pattern_number, pattern in enumerate(template["patterns"], start=1):
                for source in pattern:
                    missing = {field for _, field, _, _ in formatter.parse(source) if field} - rendered.keys()
                    if missing:
                        raise ValueError(f"{template_id} 骨架缺少变量：{', '.join(sorted(missing))}")
                turns = [source.format_map(rendered) for source in pattern]
                if tuple(turns) in same_group:
                    raise ValueError(f"{group_id} 三套问法生成了重复消息")
                same_group.add(tuple(turns))
                variables = {
                    key: values[key] for key in template["variables"]
                    if key in values and key not in {"default_city", "target_city", "target_day"}
                }
                seed = {
                    "seed_id": f"{group_id}-P{pattern_number}",
                    "template_id": template_id,
                    "variable_group_id": group_id,
                    "question_pattern_id": f"P{pattern_number}",
                    "default_city": values["default_city"],
                    "target_city": values["target_city"],
                    "target_day": values["target_day"],
                    **variables,
                    "expect_follow": template_id in {"S07", "S11", "S12", "S15", "S24"},
                    "user_turns": turns,
                    "scenario_ids": scenario_ids(template, values),
                    "target_only": bool(template.get("target_only")),
                }
                if "target_days" in values:
                    seed["target_days"] = values["target_days"]
                seeds.append(seed)
    return seeds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="输出种子 JSON 文件")
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--groups-per-template", type=int, default=5)
    parser.add_argument("--template", action="append", dest="templates", help="仅生成指定模板，可重复")
    parser.add_argument("--lexicon", type=Path, default=DEFAULT_LEXICON)
    parser.add_argument("--default-city", help="固定所有种子的默认城市，使其与被测智能体配置一致")
    args = parser.parse_args()
    try:
        data = generate_seeds(
            read_json(DEFAULT_TEMPLATES)["templates"], read_json(args.lexicon),
            random_seed=args.random_seed, groups_per_template=args.groups_per_template,
            selected_templates=args.templates, default_city=args.default_city,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    print(f"已生成 {len(data)} 条种子：{args.output}")


if __name__ == "__main__":
    main()
