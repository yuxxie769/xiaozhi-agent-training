"""Validate the pinned Qwen tokenizer, full tools, sequence lengths and SFT labels.

CPU-only check: no model weights, no training, and no GPU trainer integration.
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
from statistics import median

from training_format import prepare_example, pad_examples

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def stats(values):
    values = sorted(values)
    return {"min": values[0], "median": median(values), "p90": values[math.ceil(.9 * len(values)) - 1],
            "p95": values[math.ceil(.95 * len(values)) - 1], "max": values[-1]}


def validate(prepared_dir, tokenizer_dir, output_dir, enable_thinking=False):
    from transformers import AutoTokenizer
    prepared, tokenizer_dir, output = map(lambda p: Path(p).resolve(), (prepared_dir, tokenizer_dir, output_dir))
    if output.exists():
        raise ValueError("output_exists: choose a new validation directory")
    snapshot = json.loads((tokenizer_dir / "snapshot.json").read_text())
    if snapshot["model_id"] != "Qwen/Qwen3.5-9B":
        raise ValueError("unexpected_model")
    for name, record in snapshot["files"].items():
        if digest(tokenizer_dir / name) != record["sha256"]:
            raise ValueError("tokenizer_snapshot_changed:" + name)
    manifest = json.loads((prepared / "manifest.json").read_text())
    for name, checksum in manifest["artifact_sha256"].items():
        if digest(prepared / name) != checksum:
            raise ValueError("prepared_artifact_changed:" + name)
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir, local_files_only=True, trust_remote_code=False)
    if not tokenizer.is_fast:
        raise ValueError("fast_tokenizer_required_for_offsets")
    data, metadata = read_jsonl(prepared / "train.jsonl"), read_jsonl(prepared / "metadata.jsonl")
    if not data or len(data) != len(metadata):
        raise ValueError("metadata_count_mismatch")
    tools = json.loads((prepared / "tools.json").read_text())
    records, examples = [], []
    preview = None
    for index, (row, source) in enumerate(zip(data, metadata)):
        if source["row_index"] != index or row["tools"] != tools:
            raise ValueError("row_or_tools_mismatch")
        features, audit = prepare_example(tokenizer, row, enable_thinking=enable_thinking)
        records.append({"id": source["id"], "row_index": index, "scenario": source["scenario"],
                        **{key: audit[key] for key in ("tokens", "supervised_tokens", "assistant_messages", "tool_calls")}})
        if len(examples) < 2:
            examples.append(features)
        if preview is None or audit["tokens"] > preview["tokens"]:
            preview = {"tokens": audit["tokens"], "id": source["id"], "rendered": audit["rendered"],
                       "learned": tokenizer.decode([token for token in features["labels"] if token != -100], skip_special_tokens=False)}
    padded = pad_examples(examples, tokenizer.pad_token_id)
    for masks, labels in zip(padded["attention_mask"], padded["labels"]):
        if any(label != -100 for mask, label in zip(masks, labels) if not mask):
            raise ValueError("padding_contributes_to_loss")
    report = {
        "schema_version": 1, "status": "tokenizer_and_explicit_labels_verified_cpu_only",
        "model_id": snapshot["model_id"], "revision": snapshot["revision"],
        "enable_thinking": enable_thinking,
        "prepared_manifest_sha256": digest(prepared / "manifest.json"),
        "training_data_sha256": digest(prepared / "train.jsonl"),
        "tokenizer_snapshot": snapshot,
        "adapter_sha256": digest(Path(__file__).with_name("training_format.py")),
        "validator_sha256": digest(__file__),
        "packages": {package: importlib.metadata.version(package) for package in ("transformers", "tokenizers", "jinja2")},
        "samples": len(records), "tool_count": len(tools),
        "lengths": stats([r["tokens"] for r in records]),
        "by_scenario": {scene: stats([r["tokens"] for r in records if r["scenario"] == scene]) for scene in sorted({r["scenario"] for r in records})},
        "overlength_counts": {str(limit): sum(r["tokens"] > limit for r in records) for limit in (4096, 8192, 16384)},
        "assistant_messages": sum(r["assistant_messages"] for r in records),
        "assistant_tool_calls": sum(r["tool_calls"] for r in records),
        "supervised_tokens": sum(r["supervised_tokens"] for r in records),
        "official_template_generation_blocks": "generation" in tokenizer.chat_template,
        "label_policy": "assistant content/tool calls and EOS; context, headers, empty think prefixes and padding are -100",
        "truncation": False, "packing": False,
        "gpu_trainer_integration_verified": False, "training_started": False,
        "longest_sample": preview["id"],
        "sources": [f"https://huggingface.co/{snapshot['model_id']}/tree/{snapshot['revision']}", "https://huggingface.co/docs/transformers/chat_extras"],
    }
    # The presence of add_generation_prompt is not a Jinja generation block.
    report["official_template_generation_blocks"] = "{% generation" in tokenizer.chat_template or "{%- generation" in tokenizer.chat_template
    output.mkdir(parents=True)
    (output / "token-lengths.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    (output / "rendered-example.txt").write_text(preview["rendered"], encoding="utf-8")
    (output / "learned-example.txt").write_text(preview["learned"], encoding="utf-8")
    lines = ["# Qwen3.5 训练格式验证", "",
             f"已对 {len(records)} 条训练数据完成 CPU tokenizer、工具模板和显式训练标签检查。没有下载模型权重或启动训练。", "",
             f"模型：{snapshot['model_id']}；固定 revision：{snapshot['revision']}。", "",
             f"本次 enable_thinking={enable_thinking}。这是格式验证参数，最终训练与推理须使用确认后的相同模式。", "",
             f"所有样本均渲染完整 {len(tools)} 个工具。{report['assistant_messages']} 条 assistant 消息、{report['assistant_tool_calls']} 次工具调用均有学习标签；用户、system、工具定义、工具返回、空思考前缀和 padding 不参与损失。", "",
             "官方模板没有 Jinja generation 标记，因此本项目显式生成 labels，不能仅开启 assistant_only_loss 后假定其有效。", "",
             "| token 长度 | 最小 | 中位数 | P90 | P95 | 最大 |", "|---|---:|---:|---:|---:|---:|"]
    for name, values in {"全部": report["lengths"], **report["by_scenario"]}.items():
        lines.append(f"| {name} | {values['min']} | {values['median']} | {values['p90']} | {values['p95']} | {values['max']} |")
    lines += ["", "超长样本数：" + "；".join(f"{limit} tokens：{n} 条" for limit, n in report['overlength_counts'].items()) + "。本次没有截断或拼接样本。", "",
              "rendered-example.txt 展示最长样本真正输入模型的文本；learned-example.txt 仅展示参与学习的 assistant 内容。逐条长度见 token-lengths.jsonl。", "",
              "这次验证使用本机 CPU tokenizer 环境，尚未验证 Unsloth/TRL 的实际 GPU 数据整理、loss 和显存；后续训练器必须保留这里生成的 labels，并再次检查实际 batch，不能重新覆盖为全量文本损失。",
              "训练服务器的上下文长度和 batch 仍需小规模实测，未在本阶段确定。"]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    report["artifact_sha256"] = {p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()}
    (output / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-dir", type=Path, default=ROOT / "data/prepared")
    parser.add_argument("--tokenizer-dir", type=Path, default=ROOT / "tokenizer")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--thinking-mode", choices=["non-thinking", "thinking"], default="non-thinking")
    args = parser.parse_args()
    report = validate(args.prepared_dir, args.tokenizer_dir, args.output_dir, args.thinking_mode == "thinking")
    print(json.dumps({key: report[key] for key in ("samples", "tool_count", "lengths", "overlength_counts", "assistant_messages", "assistant_tool_calls")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
