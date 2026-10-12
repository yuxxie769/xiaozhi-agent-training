"""Check Qwen3.5 LoRA binding, tokens and home first-tool behavior via vLLM.

Calls inference only. Never executes generated tools. Training-set probes
verify deployment; they are not a held-out business evaluation.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def request(base, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=180) as response:
        return json.load(response)


def prefix_and_first(row):
    messages = []
    for message in row["messages"]:
        if message["role"] == "assistant":
            calls = message.get("tool_calls") or []
            return messages, [c["function"]["name"] for c in calls]
        messages.append(message)
    raise ValueError("No assistant target")


def check(args):
    from safetensors import safe_open
    from transformers import AutoTokenizer
    from vllm.lora.utils import parse_fine_tuned_lora_name
    from vllm.model_executor.models.qwen3_5 import Qwen3_5ForConditionalGeneration

    export = json.loads((args.adapter / "export-verification.json").read_text())
    if not export["export_verified"] or export["matched_after"] != export["runtime_modules"]:
        raise ValueError("Adapter export verification incomplete")
    models = request(args.upstream, "/v1/models")["data"]
    by_name = {m["id"]: m for m in models}
    if Path(by_name[args.sft_model]["root"]).resolve() != args.adapter.resolve():
        raise ValueError("Server is using a different adapter path")
    rows = [json.loads(line) for line in (ROOT / "data/prepared/train.jsonl").read_text().splitlines()]
    metadata = [json.loads(line) for line in (ROOT / "data/prepared/metadata.jsonl").read_text().splitlines()]
    tokenizer = AutoTokenizer.from_pretrained(ROOT / "tokenizer", local_files_only=True)
    messages, _ = prefix_and_first(rows[0])
    local_ids = tokenizer.apply_chat_template(
        messages, tools=rows[0]["tools"], add_generation_prompt=True,
        enable_thinking=False, tokenize=True, return_dict=True,
    )["input_ids"]
    remote = request(args.upstream, "/tokenize", {
        "model": args.sft_model, "messages": messages,
        "tools": rows[0]["tools"], "add_generation_prompt": True,
    })["tokens"]
    if local_ids != remote:
        raise ValueError("Training/service token IDs differ")
    plain = request(args.gateway, "/v1/chat/completions", {
        "model": args.sft_model,
        "messages": [{"role": "user", "content": "只回答：SFT服务运行正常"}],
        "temperature": 0, "max_tokens": 64,
    }, args.gateway_token)
    if plain["model"] != args.sft_model or plain["choices"][0]["message"].get("reasoning"):
        raise ValueError("Wrong route or unexpected thinking")
    if not plain["choices"][0]["message"].get("content"):
        raise ValueError("Plain generation returned empty content")
    long_probe = None
    if args.long_context_tokens:
        if args.long_context_tokens < 8193:
            raise ValueError("Long-context probe must exceed the old 8192-token limit")
        max_len = by_name[args.base_model]["max_model_len"]
        if args.long_context_tokens + 128 > max_len:
            raise ValueError("Long-context probe does not leave enough output budget")
        # Fixed repeated text exercises the service limit, not long-context
        # comprehension. Do not infer task quality from this synthetic probe.
        repetitions = args.long_context_tokens // 5
        for _ in range(12):
            long_messages = [{"role": "user", "content":
                "以下是长上下文容量测试文本：\n" + "测试文本。\n" * repetitions
                + "\n忽略以上重复文本，只回答：长上下文测试通过"}]
            long_ids = tokenizer.apply_chat_template(
                long_messages, add_generation_prompt=True, enable_thinking=False,
                tokenize=True, return_dict=True,
            )["input_ids"]
            if args.long_context_tokens <= len(long_ids) < args.long_context_tokens + 64:
                break
            delta = args.long_context_tokens - len(long_ids)
            adjustment = max(1, delta // 4) if delta > 0 else delta // 4
            repetitions = max(1, repetitions + adjustment)
        else:
            raise ValueError("Could not construct long-context probe within target range")
        long_probe = {"input_tokens": len(long_ids), "max_tokens": 32,
                      "service_max_model_len": max_len, "results": {}}
        for label, model in [("base", args.base_model), ("sft", args.sft_model)]:
            remote_ids = request(args.upstream, "/tokenize", {
                "model": model, "messages": long_messages,
                "add_generation_prompt": True,
            })["tokens"]
            if remote_ids != long_ids:
                raise ValueError(f"Long-context tokens differ for {model}")
            data = request(args.gateway, "/v1/chat/completions", {
                "model": model, "messages": long_messages,
                "temperature": 0, "max_tokens": 32,
            }, args.gateway_token)
            message = data["choices"][0]["message"]
            if data["model"] != model or not message.get("content") or message.get("reasoning"):
                raise ValueError(f"Long-context generation failed for {model}")
            long_probe["results"][label] = data
        print(json.dumps({"long_context_input_tokens": len(long_ids),
                          "both_routes_passed": True}, ensure_ascii=False), flush=True)
    home = [i for i, row in enumerate(rows)
            if metadata[i]["scenario"] == "home_switch"
            and prefix_and_first(row)[1] == ["state_hub_snapshot"]]
    if len(home) < 10:
        raise ValueError("Not enough home samples with snapshot-first targets")
    indices = [home[round(i * (len(home) - 1) / 9)] for i in range(10)]
    results = []
    for index in indices:
        row = rows[index]
        messages, target = prefix_and_first(row)
        result = {"row_index": index, "id": metadata[index]["id"], "expected_first_tools": target}
        for label, model in [("base", args.base_model), ("sft", args.sft_model)]:
            data = request(args.gateway, "/v1/chat/completions", {
                "model": model, "messages": messages, "tools": row["tools"],
                "temperature": 0, "max_tokens": 256, "seed": 20261009,
            }, args.gateway_token)
            message = data["choices"][0]["message"]
            result[label] = {
                "model": data["model"], "first_tools": [c["function"]["name"] for c in message.get("tool_calls") or []],
                "tool_calls": message.get("tool_calls"), "content": message.get("content"),
                "reasoning": message.get("reasoning"),
                "finish_reason": data["choices"][0]["finish_reason"],
            }
        results.append(result)
        print(json.dumps({"row": index, "base": result["base"]["first_tools"],
                          "sft": result["sft"]["first_tools"]}, ensure_ascii=False), flush=True)

    # Audit real activation logs against every fused runtime target.
    mapping = Qwen3_5ForConditionalGeneration.packed_modules_mapping
    children_to_parent = {child: parent for parent, children in mapping.items() for child in children}
    expected = set()
    with safe_open(str(args.adapter / "adapter_model.safetensors"), framework="pt") as stream:
        for key in stream.keys():
            name, _ = parse_fine_tuned_lora_name(key, Qwen3_5ForConditionalGeneration.hf_to_vllm_mapper)
            prefix, suffix = name.rsplit(".", 1)
            expected.add(prefix + "." + children_to_parent.get(suffix, suffix))
    logs = args.log.read_text(errors="replace").rsplit("non-default args:", 1)[-1]
    # Warmup uses dummy adapters with the same integer ID. Only the final
    # real activation (after graph capture and inference) is evidence.
    if "Graph capturing finished" not in logs:
        raise ValueError("No completed graph-capture boundary in this startup log")
    logs = logs.rsplit("Graph capturing finished", 1)[-1]
    activations = re.split(r"Activating LoRA\. int id: \d+, slot index: \d+", logs)
    if len(activations) < 2:
        raise ValueError("No real LoRA activation after warmup")
    logs = activations[-1]
    successful = {m.rstrip(".") for m in re.findall(r"Successfully loaded LoRA weights for module ([\w.]+)", logs)}
    all_skipped = {m.rstrip(".") for m in re.findall(r"No LoRA weights found for module ([\w.]+)", logs)}
    skipped = expected & all_skipped
    missing = sorted(expected - successful)
    base_hits = sum(r["base"]["first_tools"][:1] == ["state_hub_snapshot"] for r in results)
    sft_hits = sum(r["sft"]["first_tools"][:1] == ["state_hub_snapshot"] for r in results)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "deployment_verified": not missing and not skipped,
        "export": export, "model_list": models,
        "token_alignment": {"tokens": len(local_ids), "mismatches": 0},
        "plain_generation": plain,
        "long_context_capacity_probe": long_probe,
        "runtime_binding": {"expected_fused_modules": len(expected),
                            "bound_fused_modules": len(expected & successful),
                            "missing": missing, "skipped_target_layers": sorted(skipped),
                            "skipped_untrained_modules": sorted(all_skipped - expected)},
        "training_home_first_tool_probe": {"samples": len(results), "base_snapshot_first": base_hits,
                                           "sft_snapshot_first": sft_hits, "results": results},
        "held_out_business_evaluation": False, "tools_executed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"deployment_verified": report["deployment_verified"],
                      "runtime_binding": report["runtime_binding"], "base_snapshot_first": base_hits,
                      "sft_snapshot_first": sft_hits, "report": str(args.output)}, ensure_ascii=False, indent=2))
    if missing or skipped or sft_hits <= base_hits:
        raise SystemExit("Deployment binding or home behavior probe failed; inspect the saved report")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--upstream", default="http://127.0.0.1:8001")
    parser.add_argument("--gateway", default="http://127.0.0.1:6006")
    parser.add_argument("--gateway-token", default="local-dev-token")
    parser.add_argument("--base-model", default="/autodl-fs/data/qwen3.5-9b")
    parser.add_argument("--sft-model", default="xiaozhi-sft")
    parser.add_argument("--long-context-tokens", type=int, default=0,
                        help="Optionally test both routes above 8K; e.g. 10000 for a 12K service")
    parser.add_argument("--log", type=Path, default=Path("/GitHub/LLM_test/logs/vllm-qwen35.stdout.log"))
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Report exists; use a new output path")
    check(args)


if __name__ == "__main__":
    main()
