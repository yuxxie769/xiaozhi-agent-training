"""Offline, provenance-preserving SFT candidate export; never calls a model/tool.

Exports model-neutral messages/tools for Qwen + Unsloth. Tokenization and loss
masking must be verified against the selected checkpoint before training.
"""

import argparse
import ast
import copy
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo


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
    # Read a literal, without importing the plugin or touching credentials/network.
    for node in ast.parse(Path(path).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "GET_WEATHER_FUNCTION_DESC"
            for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise DataError("weather_tool_literal_missing")


def validate_arguments(value, schema):
    """Validate the JSON-schema subset used by this version's three tools."""
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
    date.fromisoformat(context["base_date"])
    ZoneInfo(context["timezone"])
    public = {"date": context["base_date"], "timezone": context["timezone"]}
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
        public["device_catalog"] = catalog
    # Never copy seed targets, future turns, initial hidden state or simulator rules.
    return base_prompt.rstrip() + "\n" + canonical(public)


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
    # Evidence validation binds legacy judgments to the provided trace when a
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


def assign_splits(entries, seed, fraction):
    """Keep entire templates and duplicate full user sequences together."""
    parents = {e["group"]: e["group"] for e in entries}

    def root(key):
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    queries = {}
    for entry in entries:
        query = digest(entry["sample"]["seed"]["user_turns"])
        group = entry["group"]
        if query in queries:
            a, b = root(group), root(queries[query])
            parents[max(a, b)] = min(a, b)
        queries[query] = group
    components = defaultdict(list)
    for entry in entries:
        components[root(entry["group"])].append(entry)
    validation = set()
    for scenario in sorted({e["scenario"] for e in entries}):
        groups = [g for g, es in components.items() if any(e["scenario"] == scenario for e in es)]
        target = sum(e["scenario"] == scenario for e in entries) * fraction
        count = sum(e["scenario"] == scenario for g in validation for e in components[g])
        for group in sorted(groups, key=lambda g: digest([seed, g])):
            if count >= target or len(set(groups) - validation) <= 1:
                break
            if group not in validation:
                validation.add(group)
                count += sum(e["scenario"] == scenario for e in components[group])
    for entry in entries:
        entry["split"] = "validation" if root(entry["group"]) in validation else "train"
        entry["split_group"] = root(entry["group"])


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
    weather_source = resolve(config["weather_tool_source"])
    weather_tool = weather_definition(weather_source)
    source_manifest, entries, all_tools = [], [], {"get_weather": weather_tool}
    for source in config["sources"]:
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
            "scenario": scenario, "conversations": str(conversations),
            "conversations_sha256": file_hash(conversations), "scores": str(scores_path),
            "scores_sha256": file_hash(scores_path), "score_policy": source["score_policy"],
            "rubric_version": report.get("rubric_version"), "count": len(samples),
            "scored_statuses": dict(Counter(s["status"] for s in report["samples"])),
            "trace_binding": "sha256" if revision_hash else "identity_check_plan_and_evidence_only",
        })
        for sample in samples:
            tools = sample["context"].get("tool_definitions")
            if not tools:
                if scenario != "weather":
                    raise DataError("missing_home_tool_snapshot")
                tools = [weather_tool]
            for tool in tools:
                name = tool["function"]["name"]
                if name in all_tools and all_tools[name] != tool:
                    raise DataError("inconsistent_tool_definitions")
                all_tools[name] = tool
            entries.append({
                "scenario": scenario, "sample": sample, "tools": tools,
                "score": scores.get(sample["sample_id"]),
                "id": f"{scenario}:{sample['sample_id']}",
                "group": f"{scenario}:{sample['seed']['template_id']}",
            })
    if len({e["id"] for e in entries}) != len(entries):
        raise DataError("duplicate_namespaced_sample_id")
    fraction = config["validation_fraction"]
    if not 0 < fraction < 1:
        raise DataError("invalid_validation_fraction")
    assign_splits(entries, config["split_seed"], fraction)
    tools = [all_tools[name] for name in sorted(all_tools)]
    if set(all_tools) != {"get_weather", "state_hub_snapshot", "hass_set_state"}:
        raise DataError("unexpected_target_tools")
    datasets = {"train": [], "validation": []}
    metadata, candidates, quarantine, audit = [], [], [], []
    seen = {}
    for entry in sorted(entries, key=lambda e: digest([config["split_seed"], e["id"]])):
        sample = entry["sample"]
        record = {key: entry[key] for key in ("id", "scenario", "group", "split_group", "split")}
        record.update(original_sample_sha256=digest(sample), original_system_sha256=digest(sample["messages"][0]),
                      tool_provenance="saved_trace" if sample["context"].get("tool_definitions") else "reconstructed_current_source_not_historical_snapshot")
        try:
            failures = validate_score(sample, entry["score"], entry["scenario"])
            action_issues = [] if failures else None
            messages = normalize_messages(sample, entry["tools"], action_issues)
            system = session_system(sample, prompt, entry["scenario"])
            row = {"messages": [{"role": "system", "content": system}] + messages, "tools": copy.deepcopy(tools)}
            record["normalized_sha256"] = digest(row)
            if failures:
                record["disposition"] = "dpo_review_candidate"
                candidates.append({**record, "trajectory": row, "failed_checks": failures,
                                   "invalid_actions": action_issues,
                                   "pair_status": "unpaired_requires_same_prefix_chosen_and_review"})
            elif digest(row) in seen:
                record.update(disposition="duplicate", duplicate_of=seen[digest(row)])
            else:
                seen[digest(row)] = entry["id"]
                record.update(disposition="sft_candidate", row_index=len(datasets[entry["split"]]),
                              assistant_message_indices=[i for i, m in enumerate(row["messages"]) if m["role"] == "assistant"])
                datasets[entry["split"]].append(row)
                metadata.append(copy.deepcopy(record))
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            record.update(disposition="quarantine", reason=str(exc))
            quarantine.append(copy.deepcopy(record))
        except Exception as exc:
            # Domain validation failures carry error_code; unexpected bugs abort.
            if not hasattr(exc, "error_code"):
                raise
            record.update(disposition="quarantine", reason=exc.error_code)
            quarantine.append(copy.deepcopy(record))
        audit.append(record)
    output.mkdir(parents=True)
    for split, rows in datasets.items():
        write_jsonl(output / f"sft.{split}.jsonl", rows)
        write_jsonl(output / f"dpo.review.{split}.jsonl", [r for r in candidates if r["split"] == split])
    write_jsonl(output / "sft.metadata.jsonl", metadata)
    write_jsonl(output / "audit.jsonl", audit)
    write_jsonl(output / "quarantine.jsonl", quarantine)
    write_jsonl(output / "validation.source-trajectories.jsonl", [
        {"id": e["id"], "scenario": e["scenario"], "sample": e["sample"]}
        for e in entries if e["split"] == "validation"
    ])
    (output / "system-prompt.txt").write_text(prompt, encoding="utf-8")
    write_json(output / "tools.json", tools)
    counts = {scenario: dict(Counter(
        f"{r['disposition']}:{r['split']}" for r in audit if r["scenario"] == scenario
    )) for scenario in sorted({e["scenario"] for e in entries})}
    summary = {
        "schema_version": 1, "status": "candidates_require_target_prompt_and_tokenizer_validation",
        "framework": "Qwen + Unsloth", "checkpoint": None,
        "sources": source_manifest, "config_sha256": file_hash(config_path),
        "exporter_sha256": file_hash(__file__), "system_prompt_sha256": file_hash(prompt_path),
        "weather_tool_source": str(weather_source), "weather_tool_source_sha256": file_hash(weather_source),
        "target_tools_sha256": digest(tools), "counts": counts,
        "sft_train": len(datasets["train"]), "sft_validation": len(datasets["validation"]),
        "dpo_review_candidates": len(candidates), "dpo_ready_pairs": 0,
        "quarantine": len(quarantine), "quarantine_reasons": dict(Counter(r["reason"] for r in quarantine)),
        "split_policy": {"seed": config["split_seed"], "validation_fraction_requested": fraction,
                         "unit": "scenario_template_and_identical_full_user_sequences",
                         "assigned_before_filtering": True, "final_test_set": False},
        "training_contract": {"loss_roles": ["assistant"], "include_assistant_tool_calls": True,
                              "mask_roles": ["system", "user", "tool"], "token_masks_verified": False,
                              "tools_argument_required_in_chat_template": True, "arguments_format": "object",
                              "packing": False, "truncation": "reject_overlength_until_reviewed"},
        "limitations": [
            "Historical scores validate original trajectories, not the rewritten system or expanded tool set.",
            "Weather tool definition reconstructed from current source; historical snapshot unavailable.",
            "Date/timezone added from session metadata; no hidden simulator state or seed answers exported to model input.",
            "Development validation uses previously evaluated templates; collect fresh final-test cases before training.",
            "Cross-domain tool interactions and general-chat coverage require new generated and scored trajectories.",
            "No chosen responses invented; DPO files are a review queue, not trainable preference pairs.",
        ],
    }
    summary["artifact_sha256"] = {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}
    write_json(output / "manifest.json", summary)
    lines = ["# 数据准备报告", "", "状态：离线筛选及统一输入候选已完成；尚未验证目标 Qwen 聊天模板和统一提示词下的行为。", "",
             f"原始轨迹：{len(entries)}；SFT train：{summary['sft_train']}；SFT validation：{summary['sft_validation']}；DPO 待配对：{len(candidates)}；待复核：{len(quarantine)}。", "",
             "| 场景 | 分类 | 数量 |", "|---|---|---:|"]
    for scenario, values in counts.items():
        lines.extend(f"| {scenario} | {key} | {n} |" for key, n in sorted(values.items()))
    lines += ["", "## 评分选择", ""] + [f"- {s['scenario']}：{s['score_policy']}" for s in source_manifest]
    lines += ["", "## 训练前剩余检查", "", "- 选定 Qwen checkpoint，渲染工具调用聊天模板，验证 assistant-only token labels；messages JSONL 本身不实现损失屏蔽。", "- 在统一提示词及三个工具同时可见的环境下重评，并增加跨场景组合样本。", "- validation 按模板及相同完整用户序列隔离，属于开发验证集；最终测试必须另行收集并锁定。", "- DPO review 仅存失败候选及证据，必须在相同历史下补充正确候选并复核。", "- 运行器插入的限次提示未被删除后冒充普通对话；相关轨迹保留在原文件，并记录到 quarantine。"]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).parent / "training-data/v1/sources.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = prepare(args.config, args.output_dir)
    print(json.dumps({k: summary[k] for k in ("sft_train", "sft_validation", "dpo_review_candidates", "quarantine")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
