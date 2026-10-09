"""Offline source inventory and SFT dataset export; never calls a model/tool.

Exports model-neutral messages/tools for Qwen + Unsloth. Tokenization and loss
masking must be verified against the selected checkpoint before training.
"""

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from math import ceil
from statistics import median
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "evaluation"))


class DataError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def indexed(rows):
    result = {}
    for row in rows:
        key = row.get("sample_id")
        if not isinstance(key, str) or not key or key in result:
            raise DataError("missing_or_duplicate_sample_id")
        result[key] = row
    return result


def weather_definition(path):
    definition = read_json(path)
    if definition.get("function", {}).get("name") != "get_weather":
        raise DataError("weather_tool_definition_missing")
    return definition


def validate_arguments(value, schema):
    """Validate the JSON-schema subset used by the exported tool definitions."""
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            raise DataError("arguments_not_object")
        props = schema.get("properties", {})
        if set(schema.get("required", [])) - value.keys():
            raise DataError("arguments_missing_required")
        if value.keys() - props.keys():
            raise DataError("arguments_unknown_property")
        for key, item in value.items():
            validate_arguments(item, props[key])
    elif kind == "string" and not isinstance(value, str):
        raise DataError("arguments_not_string")
    elif kind == "boolean" and type(value) is not bool:
        raise DataError("arguments_not_boolean")
    elif kind == "integer" and type(value) is not int:
        raise DataError("arguments_not_integer")
    elif kind == "array":
        if not isinstance(value, list):
            raise DataError("arguments_not_array")
        for item in value:
            validate_arguments(item, schema.get("items", {}))
    if "enum" in schema and value not in schema["enum"]:
        raise DataError("arguments_invalid_enum")


def normalize_messages(sample, tools, action_issues=None):
    messages = sample.get("messages", [])
    context = sample.get("context", {})
    if context.get("trace_complete") is not True:
        raise DataError("incomplete_trace")
    if context.get("internal_message_indices"):
        raise DataError("runtime_injected_messages")
    if not messages or messages[0].get("role") != "system":
        raise DataError("missing_initial_system")
    original_system = messages[0].get("content")
    if not isinstance(original_system, str):
        raise DataError("invalid_system")
    expected_hash = context.get("system_prompt_sha256")
    if expected_hash and hashlib.sha256(original_system.encode()).hexdigest() != expected_hash:
        raise DataError("system_hash_mismatch")
    definitions = {t["function"]["name"]: t["function"]["parameters"] for t in tools}
    result, pending, ids = [], set(), {}
    previous = "system"
    for message in messages[1:]:
        role = message.get("role")
        if role not in {"user", "assistant", "tool"}:
            raise DataError("invalid_message_role")
        if pending and role != "tool":
            raise DataError("missing_tool_response")
        if role == "user" and previous not in {"system", "assistant"}:
            raise DataError("invalid_user_order")
        if role == "assistant" and previous not in {"user", "tool"}:
            raise DataError("invalid_assistant_order")
        cleaned = {"role": role}
        content = message.get("content")
        if content is not None:
            if not isinstance(content, str):
                raise DataError("invalid_content")
            cleaned["content"] = content
        calls = message.get("tool_calls")
        if calls:
            if role != "assistant" or not isinstance(calls, list):
                raise DataError("invalid_tool_calls")
            cleaned["tool_calls"] = []
            for call in calls:
                old_id = call.get("id")
                if not isinstance(old_id, str) or not old_id or old_id in ids:
                    raise DataError("duplicate_or_missing_tool_id")
                if call.get("type") != "function":
                    raise DataError("invalid_tool_type")
                function = call["function"]
                name = function["name"]
                arguments = function["arguments"]
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                try:
                    if name not in definitions:
                        raise DataError("unknown_tool")
                    validate_arguments(arguments, definitions[name])
                except DataError as exc:
                    if action_issues is None:
                        raise
                    # A known-bad action is useful as a rejected candidate. Do
                    # not silently repair it, or invent a definition for it.
                    action_issues.append({"tool": name, "reason": str(exc)})
                new_id = f"call_{len(ids) + 1}"
                ids[old_id] = new_id
                pending.add(old_id)
                cleaned["tool_calls"].append({
                    "id": new_id, "type": "function",
                    "function": {"name": name, "arguments": arguments},
                })
        elif not content:
            raise DataError("empty_message")
        if role == "tool":
            old_id = message.get("tool_call_id")
            if old_id not in pending:
                raise DataError("orphan_or_duplicate_tool_response")
            pending.remove(old_id)
            cleaned["tool_call_id"] = ids[old_id]
        result.append(cleaned)
        previous = role
    if pending or not result or result[-1]["role"] != "assistant" or result[-1].get("tool_calls"):
        raise DataError("unfinished_conversation")
    if [m["content"] for m in result if m["role"] == "user"] != sample["seed"]["user_turns"]:
        raise DataError("user_turns_mismatch")
    return result


def session_system(sample, base_prompt, scenario):
    context = sample["context"]
    if scenario == "home_switch":
        marker = "本次可信设备目录（controllable为允许开关，未列设备不在本次允许范围）："
        system = sample["messages"][0]["content"]
        if system.count(marker) != 1:
            raise DataError("missing_visible_catalog")
        catalog = json.loads(system.split(marker, 1)[1].strip())
        if catalog != context.get("public_catalog"):
            raise DataError("catalog_mismatch")
        allowed = {"entity_id", "name", "aliases", "room", "controllable"}
        if not isinstance(catalog, list) or any(
            not isinstance(item, dict) or item.keys() - allowed
            or not {"entity_id", "name", "controllable"} <= item.keys()
            or type(item["controllable"]) is not bool
            for item in catalog
        ):
            raise DataError("invalid_public_catalog")
        # Keep the original visible block verbatim, including catalog order.
        return base_prompt.rstrip() + "\n\n" + marker + system.split(marker, 1)[1]
    # Never copy seed targets, future turns, initial hidden state or simulator rules.
    return base_prompt.rstrip()


def validate_score(sample, score, scenario):
    if score is None:
        raise DataError("missing_score")
    if score.get("seed_id") != sample["seed"]["seed_id"] or score.get("template_id") != sample["seed"]["template_id"]:
        raise DataError("score_identity_mismatch")
    if scenario == "weather":
        import weather_scoring as adapter
    else:
        import home_switch_scoring as adapter
    state = adapter.analyze(sample)
    expected, _, _ = adapter.plan_checks(sample, state)
    checks = score.get("checks", [])
    keys = [f"{c['turn']}:{c['check_id']}" for c in checks]
    if len(keys) != len(set(keys)) or set(keys) != set(expected):
        raise DataError("incomplete_or_duplicate_score_checks")
    if not checks or any(c.get("status") not in {"pass", "fail"} for c in checks):
        raise DataError("unresolved_score")
    # Evidence test binds legacy judgments to the provided trace when a
    # historical report has no conversations hash.
    for check in checks:
        if not check.get("evidence"):
            raise DataError("score_without_evidence")
        for proof in check["evidence"]:
            index, quote = proof.get("message_index"), proof.get("quote")
            if type(index) is not int or not 0 <= index < len(sample["messages"]) or not isinstance(quote, str) or not quote:
                raise DataError("invalid_score_evidence")
            message = sample["messages"][index]
            texts = [message.get("content", "") or ""]
            if message.get("tool_calls"):
                texts.append(json.dumps(message["tool_calls"], ensure_ascii=False))
            if not any(quote in text for text in texts):
                raise DataError("stale_score_evidence")
    failures = [c for c in checks if c["status"] == "fail"]
    if score.get("status") != ("fail" if failures else "pass"):
        raise DataError("inconsistent_score_status")
    return failures


MISSING = "未提供"
STATUS = "SFT 训练数据集已生成，目标模型训练适配待验证。"


def distribution(values):
    """P90 uses nearest rank; empty populations are explicitly null."""
    if not values:
        return {"count": 0, "min": None, "median": None, "p90": None, "max": None}
    values = sorted(values)
    return {"count": len(values), "min": values[0], "median": median(values),
            "p90": values[ceil(len(values) * .9) - 1], "max": values[-1]}


def field_counts(samples, field, multiple=False):
    counts = Counter()
    for sample in samples:
        value = sample.get("seed", {}).get(field)
        values = value if multiple and isinstance(value, list) else [value]
        # Count samples bearing each tag, not repeated occurrences within a sample.
        labels = {str(v) for v in values if v is not None and v != ""}
        counts.update(labels or [MISSING])
    return dict(sorted(counts.items()))


def structure_inventory(samples):
    turns, message_counts, body_lengths, calls_per_trace, argument_lengths = [], [], [], [], []
    for sample in samples:
        messages = sample.get("messages", [])
        internal = set(sample.get("context", {}).get("internal_message_indices") or [])
        turns.append(sum(m.get("role") == "user" and i not in internal
                         for i, m in enumerate(messages)))
        # Structural lengths measure the raw trace, including system/internal messages.
        message_counts.append(len(messages))
        body_lengths.append(sum(len(m["content"]) for m in messages if isinstance(m.get("content"), str)))
        calls = [call for m in messages for call in (m.get("tool_calls") or [])]
        calls_per_trace.append(len(calls))
        for call in calls:
            arguments = call.get("function", {}).get("arguments")
            if isinstance(arguments, str):
                argument_lengths.append(len(arguments))
            elif arguments is not None:
                argument_lengths.append(len(canonical(arguments)))
    return {
        "samples": len(samples),
        "turn_counts": dict(sorted(Counter(turns).items())),
        "single_turn": turns.count(1), "multi_turn": sum(n > 1 for n in turns),
        "zero_turn": turns.count(0),
        "message_count_per_trace": distribution(message_counts),
        "body_characters_per_trace": distribution(body_lengths),
        "tool_calls_per_trace": distribution(calls_per_trace),
        "argument_characters_per_call": distribution(argument_lengths),
    }


def build_inventory(entries, sources):
    coverage, structures = {}, {}
    for scenario in sorted({e["scenario"] for e in entries}):
        samples = [e["sample"] for e in entries if e["scenario"] == scenario]
        coverage[scenario] = {
            field: field_counts(samples, field, multiple=field == "scenario_ids")
            for field in ("template_id", "variable_group_id", "question_pattern_id", "variant_id", "scenario_ids")
        }
        structures[scenario] = structure_inventory(samples)
    batches = []
    for source in sources:
        samples = [e["sample"] for e in entries if e["source_index"] == source["source_index"]]
        batches.append({"source_index": source["source_index"], "scenario": source["scenario"],
                       "conversations": source["conversations"], "count": len(samples),
                       "run_ids": dict(sorted(Counter(s.get("context", {}).get("run_id") or MISSING
                                                      for s in samples).items()))})
    return {
        "schema_version": 1,
        "definitions": {
            "population": "全部源轨迹，包含后续未通过、待复核和重复样本。",
            "batches": "每个配置来源文件为一批；run_ids 保留文件中已有的运行标识。",
            "coverage": "只读原始 seed 字段；每个标签统计包含该标签的样本数，多标签不相加作为总数；缺失为未提供。",
            "turns": "真实 user 消息数，排除 context.internal_message_indices 标记的运行器消息。",
            "lengths": "消息数和正文字符数按原始全轨迹统计，含 system 和运行器消息；正文不含工具参数。参数字符串按原文字符数，对象按紧凑 JSON 字符数；均非 token 数。",
            "p90": "最近秩法：升序第 ceil(0.9*n) 项；空集合统计值为 null。",
        },
        "sources": {"total": len(entries), "batches": batches,
                    "scenario_counts": dict(sorted(Counter(e["scenario"] for e in entries).items()))},
        "task_coverage": coverage,
        "dialogue_structure": {"all": structure_inventory([e["sample"] for e in entries]),
                               "by_scenario": structures},
    }


def render_report(inventory, summary):
    lines = ["# 数据准备报告", "", STATUS, "",
             f"源轨迹 {inventory['sources']['total']} 条；SFT 训练数据 {summary['train_samples']} 条；"
             f"未通过 {summary['failed_samples']} 条；待复核 {summary['quarantine']} 条；"
             f"重复 {summary['duplicates']} 条。", "",
             "`train.jsonl` 已生成完整 messages 和逐条 tools；未运行训练，也未完成目标模型模板及损失掩码验证。", "",
             "## 1 来源与数量", "", "| 批次文件 | 场景 | 数量 |", "|---|---|---:|"]
    for source in inventory["sources"]["batches"]:
        lines.append(f"| {source['conversations']} | {source['scenario']} | {source['count']} |")
    lines += ["", "## 2 任务覆盖", "", "只统计已有字段。表中为不同取值数及缺失样本数；每个具体取值的样本数见 inventory.json。多标签数不能相加当作样本总数。", "",
              "| 场景 | 字段 | 不同取值数 | 未提供样本数 |", "|---|---|---:|---:|"]
    for scenario, fields in inventory["task_coverage"].items():
        for field, counts in fields.items():
            lines.append(f"| {scenario} | {field} | {len(set(counts) - {MISSING})} | {counts.get(MISSING, 0)} |")
    lines += ["", "## 3 对话结构", "", "轮数仅统计真实用户消息；原始长度含 system 和运行器消息。字符数不是 token 数，P90 使用最近秩法。", "",
              "| 场景 | 单轮 | 多轮 | 无用户轮 |", "|---|---:|---:|---:|"]
    for scenario, stats in inventory["dialogue_structure"]["by_scenario"].items():
        lines.append(f"| {scenario} | {stats['single_turn']} | {stats['multi_turn']} | {stats['zero_turn']} |")
    lines += ["", "| 场景 | 指标 | 最小值 | 中位数 | P90 | 最大值 |", "|---|---|---:|---:|---:|---:|"]
    labels = {"message_count_per_trace": "每条消息数", "body_characters_per_trace": "每条正文字符数",
              "tool_calls_per_trace": "每条工具调用数", "argument_characters_per_call": "每次调用参数字符数"}
    for scenario, stats in {"合计": inventory["dialogue_structure"]["all"], **inventory["dialogue_structure"]["by_scenario"]}.items():
        for key, label in labels.items():
            d = stats[key]
            lines.append(f"| {scenario} | {label} | {d['min']} | {d['median']} | {d['p90']} | {d['max']} |")
    lines += ["", "## 处理结果与异常说明", "", "此处用于核对数据去向，不增加盘点维度。", "",
              "| 场景 | 训练数据 | 未通过 | 待复核 | 重复 |", "|---|---:|---:|---:|---:|"]
    for scenario, counts in summary["counts"].items():
        lines.append(f"| {scenario} | {counts.get('passed_sample', 0)} | {counts.get('failed_sample', 0)} | {counts.get('quarantine', 0)} | {counts.get('duplicate', 0)} |")
    lines.append("")
    for reason, count in sorted(summary["quarantine_reasons"].items()):
        lines.append(f"- 待复核：`{reason}`，{count} 条。原文保留在 raw，通过 review.jsonl 的 source_index 和 source_sample_id 回查。")
    lines += ["", "本次统一工具：" + "、".join(summary["target_tool_names"]) + "。", "", "评分采用最新修订版本。本次读取并校验已有评分、检查项和证据，没有重新调用模型评分。", "",
              "未通过样本可能可用于后续 DPO rejected；当前不做适用性评估或配对。", "",
              "输入不追加元数据日期、时区；家居目录保留原始 system 可见文本。全部训练样本使用 tools.json 中相同的完整非 MCP 工具列表，原工具范围仅用于历史评分追溯。定义与来源记录在 tools-source.json 和 manifest.json。", "",
              "下一阶段直接使用 train.jsonl 验证 Qwen3.5-9B 模板渲染、工具定义和 assistant-only 损失标签，通过后冻结版本并试跑。",
              "测试由独立评估种子生成器负责，本次不划分测试集，不生成覆盖不足报告或补数建议。"]
    return "\n".join(lines) + "\n"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")


def prepare(config_path, output):
    config_path, output = Path(config_path).resolve(), Path(output).resolve()
    if output.exists():
        raise DataError("output_exists: use a new versioned directory")
    config = read_json(config_path)
    resolve = lambda p: (config_path.parent / p).resolve()
    prompt_path = resolve(config["system_prompt"])
    prompt = prompt_path.read_text(encoding="utf-8")
    target_path = resolve(config["target_tools"])
    target_tools = read_json(target_path)
    if not isinstance(target_tools, list) or not target_tools:
        raise DataError("missing_target_tools")
    target_definitions = {}
    for tool in target_tools:
        if not isinstance(tool, dict) or tool.get("type") != "function" or not isinstance(tool.get("function"), dict):
            raise DataError("invalid_target_tools")
        function = tool["function"]
        name = function.get("name")
        if not isinstance(name, str) or not name or name in target_definitions or not isinstance(function.get("parameters"), dict):
            raise DataError("invalid_or_duplicate_target_tool")
        target_definitions[name] = function["parameters"]
    provenance_path = resolve(config["target_tools_provenance"]) if config.get("target_tools_provenance") else None
    weather_source = resolve(config["weather_tool_source"])
    weather_tool = weather_definition(weather_source)
    source_manifest, entries = [], []
    for source_index, source in enumerate(config["sources"]):
        scenario = source["scenario"]
        if scenario not in {"weather", "home_switch"}:
            raise DataError("unknown_scenario")
        conversations, scores_path = resolve(source["conversations"]), resolve(source["scores"])
        samples, report = read_json(conversations), read_json(scores_path)
        indexed(samples)
        scores = indexed(report["samples"])
        revision_hash = report.get("revision", {}).get("conversations_sha256")
        if revision_hash and revision_hash != file_hash(conversations):
            raise DataError("scores_conversations_hash_mismatch")
        source_manifest.append({
            "source_index": source_index, "scenario": scenario, "conversations": source["conversations"],
            "conversations_sha256": file_hash(conversations), "scores": source["scores"],
            "scores_sha256": file_hash(scores_path), "score_policy": source["score_policy"],
            "rubric_version": report.get("rubric_version"), "count": len(samples),
            "scored_statuses": dict(Counter(s["status"] for s in report["samples"])),
            "trace_binding": "sha256" if revision_hash else "identity_check_plan_and_evidence_only",
        })
        for sample in samples:
            tools = sample["context"].get("tool_definitions")
            if not tools and scenario == "weather":
                tools = [weather_tool]
            entries.append({
                "scenario": scenario, "sample": sample, "tools": tools,
                "source_index": source_index, "source_sample_id": sample["sample_id"],
                "score": scores.get(sample["sample_id"]),
                "id": f"{scenario}:{sample['sample_id']}",
                "group": f"{scenario}:{sample.get('seed', {}).get('template_id', MISSING)}",
            })
    if len({e["id"] for e in entries}) != len(entries):
        raise DataError("duplicate_namespaced_sample_id")
    inventory = build_inventory(entries, source_manifest)
    dataset = []
    metadata, failed, quarantine, audit = [], [], [], []
    seen = {}
    for entry in sorted(entries, key=lambda e: e["id"]):
        sample = entry["sample"]
        record = {key: entry[key] for key in ("id", "scenario", "group", "source_index", "source_sample_id")}
        record.update(original_sample_sha256=digest(sample), original_system_sha256=digest(sample.get("messages", [])[0]) if sample.get("messages") else None,
                      tool_provenance=("saved_trace" if sample["context"].get("tool_definitions") else
                                       "reconstructed_contract_aligned_with_latest_rules" if entry["scenario"] == "weather" else "missing_snapshot"))
        try:
            if not entry["tools"]:
                raise DataError("missing_home_tool_snapshot")
            if not isinstance(entry["tools"], list):
                raise DataError("invalid_tool_definitions")
            names = []
            for tool in entry["tools"]:
                if (not isinstance(tool, dict) or tool.get("type") != "function"
                        or not isinstance(tool.get("function"), dict)
                        or not isinstance(tool["function"].get("parameters"), dict)):
                    raise DataError("invalid_tool_definitions")
                name = tool["function"].get("name")
                if not isinstance(name, str) or not name or name in names:
                    raise DataError("duplicate_or_missing_tool_name")
                names.append(name)
            record["source_tools_sha256"] = digest(entry["tools"])
            record["tools_sha256"] = digest(target_tools)
            failures = validate_score(sample, entry["score"], entry["scenario"])
            action_issues = [] if failures else None
            messages = normalize_messages(sample, entry["tools"], action_issues)
            target_issues = []
            for message in messages:
                for call in message.get("tool_calls", []):
                    function = call["function"]
                    try:
                        if function["name"] not in target_definitions:
                            raise DataError("tool_missing_from_target_list")
                        validate_arguments(function["arguments"], target_definitions[function["name"]])
                    except DataError as exc:
                        if not failures:
                            raise DataError("target_tool_incompatible:" + str(exc)) from exc
                        target_issues.append({"tool": function["name"], "reason": str(exc)})
            system = session_system(sample, prompt, entry["scenario"])
            row = {"messages": [{"role": "system", "content": system}] + messages, "tools": copy.deepcopy(target_tools)}
            record["normalized_sha256"] = digest(row)
            if failures:
                record["disposition"] = "failed_sample"
                failed.append({**record, "trajectory": row, "failed_checks": failures,
                                   "invalid_actions": action_issues, "invalid_actions_scope": "original_generation_tools",
                                   "target_invalid_actions": target_issues,
                                   "note": "未通过样本，可能可用于后续 DPO rejected；当前不判断适用性。"})
            elif digest(row) in seen:
                record.update(disposition="duplicate", duplicate_of=seen[digest(row)])
            else:
                seen[digest(row)] = entry["id"]
                record.update(disposition="passed_sample", row_index=len(dataset),
                              assistant_message_indices=[i for i, m in enumerate(row["messages"]) if m["role"] == "assistant"])
                dataset.append(row)
                metadata.append(copy.deepcopy(record))
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            record.update(disposition="quarantine", reason=str(exc))
            quarantine.append(copy.deepcopy(record))
        except Exception as exc:
            # Domain test failures carry error_code; unexpected bugs abort.
            if not hasattr(exc, "error_code"):
                raise
            record.update(disposition="quarantine", reason=exc.error_code)
            quarantine.append(copy.deepcopy(record))
        audit.append(record)
    counts = {scenario: dict(Counter(r["disposition"] for r in audit if r["scenario"] == scenario))
              for scenario in sorted({e["scenario"] for e in entries})}
    summary = {
        "schema_version": 2, "status": STATUS,
        "framework": config.get("project", {}).get("framework", "Unsloth"),
        "model_family": config.get("project", {}).get("model_family"),
        "checkpoint": config.get("project", {}).get("checkpoint_and_revision"),
        "sources": source_manifest, "config_sha256": file_hash(config_path),
        "exporter_sha256": file_hash(__file__), "system_prompt_sha256": file_hash(prompt_path),
        "weather_tool_source": config["weather_tool_source"], "weather_tool_source_sha256": file_hash(weather_source),
        "weather_tool_provenance": "reconstructed_contract_aligned_with_latest_rules_not_historical_snapshot",
        "target_tools_source": config["target_tools"], "target_tools_sha256": file_hash(target_path),
        "target_tool_names": sorted(target_definitions),
        "target_tools_provenance_sha256": file_hash(provenance_path) if provenance_path else None,
        "scoring_sha256": {p.name: file_hash(p) for p in sorted((PROJECT_ROOT / "evaluation").glob("*.py"))},
        "counts": counts, "source_samples": len(entries), "train_samples": len(dataset),
        "failed_samples": len(failed), "quarantine": len(quarantine),
        "duplicates": sum(r["disposition"] == "duplicate" for r in audit),
        "quarantine_reasons": dict(Counter(r["reason"] for r in quarantine)),
        "evaluation_policy": "测试由独立评估种子生成器负责；不从源轨迹划分测试集。",
        "training_contract": {"loss_roles": ["assistant"], "include_assistant_tool_calls": True,
                              "mask_roles": ["system", "user", "tool"], "mask_tool_definitions": True,
                              "token_masks_verified": False, "target_chat_template_verified": False,
                              "verification_scope": "export_stage_only; subsequent CPU checks are recorded separately in data/validation",
                              "tools_argument_required_in_chat_template": True, "arguments_format": "object",
                              "tools_scope": "all_enabled_non_mcp_server_plugins",
                              "packing": False, "truncation": "reject_overlength_until_reviewed"},
        "limitations": [
            "Historical scores and invalid actions use original tool availability; behavior under the unified system and expanded tools has not been re-evaluated.",
            "Weather tool definition is reconstructed, not a historical snapshot.",
            "Failed samples retain evidence; possible future DPO use has not been assessed.",
        ],
    }
    if len(audit) != len(dataset) + len(failed) + len(quarantine) + summary["duplicates"]:
        raise DataError("disposition_count_mismatch")
    output.mkdir(parents=True)
    write_jsonl(output / "train.jsonl", dataset)
    write_jsonl(output / "failed.jsonl", failed)
    write_jsonl(output / "metadata.jsonl", metadata)
    write_jsonl(output / "audit.jsonl", audit)
    write_jsonl(output / "review.jsonl", quarantine)
    write_json(output / "inventory.json", inventory)
    (output / "tools.json").write_bytes(target_path.read_bytes())
    if provenance_path:
        (output / "tools-source.json").write_bytes(provenance_path.read_bytes())
    (output / "system-prompt.txt").write_text(prompt, encoding="utf-8")
    (output / "report.md").write_text(render_report(inventory, summary), encoding="utf-8")
    summary["artifact_sha256"] = {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}
    write_json(output / "manifest.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = prepare(args.config, args.output_dir)
    print(json.dumps({k: summary[k] for k in ("train_samples", "failed_samples", "quarantine", "duplicates")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
