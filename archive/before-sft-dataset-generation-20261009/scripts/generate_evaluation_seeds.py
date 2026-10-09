"""Generate reproducible evaluation seeds in the source score distribution.

The generator reads the current evaluation reports for template proportions,
uses the original scenario seed generators, and rejects a whole variable group
when its semantic fingerprint or wording overlaps the source/training seeds.
It never calls a model, weather service, or home device.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_DIR = PROJECT_ROOT / "evaluation" / "seed_generation"
sys.path.insert(0, str(GENERATOR_DIR))

import generate_weather_seeds as weather_generator  # noqa: E402
import home_switch_seeds as home_generator  # noqa: E402
from snapshot_library import Library  # noqa: E402


class GenerationError(ValueError):
    pass


IDENTITY_FIELDS = {"seed_id", "variable_group_id", "question_pattern_id", "user_turns"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolve(config_path, value):
    return (Path(config_path).resolve().parent / value).resolve()


def extract_seed_rows(value):
    """Accept a seed array or a conversation array containing a seed field."""
    if not isinstance(value, list):
        raise GenerationError("种子或 conversations 文件必须是数组")
    result = []
    for row in value:
        seed = row.get("seed") if isinstance(row, dict) and "seed" in row else row
        if not isinstance(seed, dict) or not seed.get("template_id"):
            raise GenerationError("输入包含缺少 template_id 的种子")
        result.append(seed)
    return result


def semantic_fingerprint(seed):
    """Group P1/P2/P3 wording variants under one semantic fingerprint."""
    semantic = {
        key: copy.deepcopy(value)
        for key, value in seed.items()
        if key not in IDENTITY_FIELDS
    }
    return sha256_value(semantic)


def wording_fingerprints(seed):
    turns = seed.get("user_turns")
    if not isinstance(turns, list) or not turns or not all(isinstance(x, str) for x in turns):
        raise GenerationError("种子缺少有效 user_turns")
    normalized = [" ".join(turn.split()) for turn in turns]
    return {sha256_value(normalized)}


def group_seeds(seeds):
    grouped = defaultdict(list)
    for seed in seeds:
        group_id = seed.get("variable_group_id")
        if not isinstance(group_id, str) or not group_id:
            raise GenerationError("种子缺少 variable_group_id")
        grouped[(seed["template_id"], group_id)].append(seed)
    for key, rows in grouped.items():
        patterns = {row.get("question_pattern_id") for row in rows}
        if patterns != {"P1", "P2", "P3"}:
            raise GenerationError(f"变量组 {key[1]} 没有完整的 P1/P2/P3")
        fingerprints = {semantic_fingerprint(row) for row in rows}
        if len(fingerprints) != 1:
            raise GenerationError(f"变量组 {key[1]} 的语义字段不一致")
    return grouped


def template_counts(score_report, status="pass"):
    samples = score_report.get("samples") if isinstance(score_report, dict) else None
    if not isinstance(samples, list) or not samples:
        raise GenerationError("评分结果缺少 samples")
    rows = samples if status == "all" else [row for row in samples if row.get("status") == status]
    counts = Counter(row.get("template_id") for row in rows)
    if None in counts or not counts:
        raise GenerationError("评分结果缺少有效 template_id")
    return dict(sorted(counts.items()))


def apportion_groups(counts, ratio, forced_total=None):
    """Largest-remainder allocation with at least one group per template."""
    if not 0 < ratio <= 1:
        raise GenerationError("test_ratio 必须在 0 到 1 之间")
    templates = sorted(counts)
    if not templates or any(type(value) is not int or value <= 0 for value in counts.values()):
        raise GenerationError("模板计数必须是正整数")
    requested_seeds = round(sum(counts.values()) * ratio)
    total_groups = forced_total if forced_total is not None else math.ceil(requested_seeds / 3)
    if type(total_groups) is not int or total_groups < 1:
        raise GenerationError("评估变量组总数必须是正整数")
    total_groups = max(total_groups, len(templates))
    quotas = {template: 1 for template in templates}
    remaining = total_groups - len(templates)
    if remaining:
        total = sum(counts.values())
        raw = {template: remaining * counts[template] / total for template in templates}
        floors = {template: math.floor(value) for template, value in raw.items()}
        for template, value in floors.items():
            quotas[template] += value
        left = remaining - sum(floors.values())
        order = sorted(templates, key=lambda t: (-(raw[t] - floors[t]), t))
        for template in order[:left]:
            quotas[template] += 1
    return quotas, requested_seeds


def source_index(seeds):
    semantics = {semantic_fingerprint(seed) for seed in seeds}
    wording = set()
    for seed in seeds:
        wording.update(wording_fingerprints(seed))
    return semantics, wording


def rename_group(rows, sequence):
    template = rows[0]["template_id"]
    group_id = f"{template}-E{sequence:03}"
    renamed = []
    for row in sorted(rows, key=lambda item: item["question_pattern_id"]):
        item = copy.deepcopy(row)
        item["variable_group_id"] = group_id
        item["seed_id"] = f"{group_id}-{item['question_pattern_id']}"
        renamed.append(item)
    return renamed


def candidate_collision(rows, excluded_semantics, accepted_semantics):
    semantic = semantic_fingerprint(rows[0])
    wording = set().union(*(wording_fingerprints(row) for row in rows))
    if semantic in excluded_semantics:
        return "source_semantic", semantic, wording
    if semantic in accepted_semantics:
        return "evaluation_semantic", semantic, wording
    return None, semantic, wording


def generated_batches(scenario, templates, max_groups, random_seed, attempt, conversations_path):
    attempt_seed = random_seed + attempt * 1009 + (0 if scenario == "weather" else 1000003)
    if scenario == "weather":
        rows = weather_generator.generate_seeds(
            weather_generator.read_json(weather_generator.DEFAULT_TEMPLATES)["templates"],
            weather_generator.read_json(weather_generator.DEFAULT_LEXICON),
            random_seed=attempt_seed,
            groups_per_template=max_groups,
            selected_templates=templates,
        )
        return rows, []
    library = Library(conversations_path)
    return home_generator.generate_seeds(
        library,
        templates=templates,
        groups_per_template=max_groups,
        random_seed=attempt_seed,
    )


def generate_scenario(
    scenario,
    quotas,
    excluded_seeds,
    conversations_path,
    random_seed,
    max_attempts,
):
    accepted = defaultdict(list)
    excluded_semantics, excluded_wording = source_index(excluded_seeds)
    accepted_semantics, accepted_wording = set(), set()
    rejection_counts = Counter()
    wording_overlap_counts = Counter()
    unavailable = []
    batches = 0
    for attempt in range(max_attempts):
        if all(len(accepted[template]) >= quota for template, quota in quotas.items()):
            break
        rows, missing = generated_batches(
            scenario,
            list(quotas),
            max(quotas.values()),
            random_seed,
            attempt,
            conversations_path,
        )
        batches += 1
        unavailable.extend(missing)
        for (template, _), group in sorted(group_seeds(rows).items()):
            if template not in quotas or len(accepted[template]) >= quotas[template]:
                continue
            reason, semantic, wording = candidate_collision(
                group,
                excluded_semantics,
                accepted_semantics,
            )
            if reason:
                rejection_counts[reason] += 1
                continue
            accepted[template].append(group)
            accepted_semantics.add(semantic)
            if wording & excluded_wording:
                wording_overlap_counts["source"] += 1
            if wording & accepted_wording:
                wording_overlap_counts["evaluation"] += 1
            accepted_wording.update(wording)
    else:
        attempt = max_attempts
    shortages = {
        template: quota - len(accepted[template])
        for template, quota in quotas.items()
        if len(accepted[template]) < quota
    }
    if shortages:
        raise GenerationError(
            f"{scenario} 在 {max_attempts} 轮内无法补齐配额：{shortages}；"
            f"碰撞统计：{dict(rejection_counts)}"
        )
    output = []
    for template in sorted(quotas):
        for sequence, group in enumerate(accepted[template], start=1):
            output.extend(rename_group(group, sequence))
    return output, {
        "generation_batches": batches,
        "rejected": dict(sorted(rejection_counts.items())),
        "accepted_wording_overlap_groups": dict(sorted(wording_overlap_counts.items())),
        "unavailable_candidates": len(unavailable),
    }


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--test-ratio", type=float, help="默认读取 config.test_fraction")
    parser.add_argument("--random-seed", type=int, default=20261009)
    parser.add_argument("--score-status", choices=["pass", "all"], default="pass")
    parser.add_argument("--weather-groups", type=int)
    parser.add_argument("--home-switch-groups", type=int)
    parser.add_argument("--max-attempts", type=int, default=200)
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        parser.error("输出目录已存在；请使用新的版本目录，避免覆盖已冻结种子")
    config = read_json(args.config)
    test_ratio = args.test_ratio if args.test_ratio is not None else config.get("test_fraction")
    if test_ratio is None:
        parser.error("请通过 --test-ratio 或 config.test_fraction 指定评估规模")
    sources = {source["scenario"]: source for source in config["sources"]}
    if set(sources) != {"weather", "home_switch"}:
        parser.error("config.sources 必须同时包含 weather 和 home_switch")
    reports = {}
    pending_outputs = {}
    try:
        for scenario in ("weather", "home_switch"):
            source = sources[scenario]
            scores_path = resolve(args.config, source["scores"])
            conversations_path = resolve(args.config, source["conversations"])
            scores = read_json(scores_path)
            conversations = read_json(conversations_path)
            excluded = extract_seed_rows(conversations)
            counts = template_counts(scores, args.score_status)
            forced = args.weather_groups if scenario == "weather" else args.home_switch_groups
            quotas, requested_seeds = apportion_groups(counts, test_ratio, forced)
            generated, diagnostics = generate_scenario(
                scenario,
                quotas,
                excluded,
                conversations_path,
                args.random_seed,
                args.max_attempts,
            )
            output_name = f"{scenario}-seeds.json"
            generated_counts = dict(sorted(Counter(row["template_id"] for row in generated).items()))
            pending_outputs[output_name] = generated
            reports[scenario] = {
                "score_file": str(scores_path),
                "score_file_sha256": sha256_file(scores_path),
                "source_conversations": str(conversations_path),
                "source_conversations_sha256": sha256_file(conversations_path),
                "score_status": args.score_status,
                "source_template_counts": counts,
                "requested_test_ratio": test_ratio,
                "requested_seed_count_before_group_rounding": requested_seeds,
                "group_quotas": quotas,
                "generated_template_counts": generated_counts,
                "generated_groups": len(generated) // 3,
                "generated_seeds": len(generated),
                "output": output_name,
                **diagnostics,
            }
        args.output_dir.mkdir(parents=True)
        for output_name, generated in pending_outputs.items():
            output_path = args.output_dir / output_name
            write_json(output_path, generated)
            reports[output_name.removesuffix("-seeds.json")]["output_sha256"] = sha256_file(output_path)
        report = {
            "schema_version": 1,
            "random_seed": args.random_seed,
            "collision_policy": {
                "unit": "whole_variable_group_P1_P2_P3",
                "exclude": "all source conversation seeds, regardless of score",
                "semantic_fingerprint_ignores": sorted(IDENTITY_FIELDS),
                "wording_overlap": "reported_but_allowed_when_semantic_variables_differ",
                "on_collision": "reject_before_write_and_resample",
            },
            "scenarios": reports,
        }
        write_json(args.output_dir / "generation-report.json", report)
    except (GenerationError, ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({k: v["generated_seeds"] for k, v in reports.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
