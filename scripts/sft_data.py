"""训练入口共用的数据检查；此文件不导入 GPU 库，也不修改原始数据。"""

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random

from training_format import prepare_example, pad_examples


@dataclass(frozen=True)
class TrainConfig:
    """具体数值集中在 train-sft.json；这里只定义字段和必要的约束。"""

    prepared_dir: str
    tokenizer_dir: str
    enable_thinking: bool
    max_seq_length: int
    batch_size: int
    gradient_accumulation_steps: int
    epochs: float
    learning_rate: float
    lora_rank: int
    lora_alpha: int
    warmup_ratio: float
    weight_decay: float
    max_grad_norm: float
    seed: int
    save_steps: int
    save_total_limit: int
    smoke_samples: int
    smoke_steps: int

    def __post_init__(self):
        if self.enable_thinking is not False:
            raise ValueError("当前训练方案已确认非思考模式，enable_thinking 必须为 false")
        for name in ("max_seq_length", "batch_size", "gradient_accumulation_steps",
                     "lora_rank", "lora_alpha", "save_steps", "save_total_limit",
                     "smoke_samples", "smoke_steps"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} 必须是正整数")
        for name in ("epochs", "learning_rate", "max_grad_norm"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} 必须为有限正数")
        if not 0 <= self.warmup_ratio < 1 or not 0 <= self.weight_decay < 1:
            raise ValueError("warmup_ratio、weight_decay 必须在 [0, 1) 内")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path):
    # 不跳过坏行或空行：训练数量发生变化时必须明确报错。
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def load_config(path):
    path = Path(path).resolve()
    config = TrainConfig(**json.loads(path.read_text(encoding="utf-8")))
    return config, (path.parent / config.prepared_dir).resolve(), (path.parent / config.tokenizer_dir).resolve()


def check_inputs(prepared, tokenizer_dir):
    """只核对已冻结的数据版本；不要求如今的项目进度配置等于历史导出配置。"""
    manifest = json.loads((prepared / "manifest.json").read_text())
    for name, expected in manifest["artifact_sha256"].items():
        if sha256(prepared / name) != expected:
            raise ValueError(f"prepared_artifact_changed:{name}")
    snapshot = json.loads((tokenizer_dir / "snapshot.json").read_text())
    for name, record in snapshot["files"].items():
        if sha256(tokenizer_dir / name) != record["sha256"]:
            raise ValueError(f"tokenizer_snapshot_changed:{name}")
    if snapshot["model_id"] != "Qwen/Qwen3.5-9B" or manifest["checkpoint"] != {
        "model_id": snapshot["model_id"], "revision": snapshot["revision"]
    }:
        raise ValueError("model_revision_mismatch")
    rows = read_jsonl(prepared / "train.jsonl")
    metadata = read_jsonl(prepared / "metadata.jsonl")
    tools = json.loads((prepared / "tools.json").read_text())
    if not rows or len(rows) != len(metadata) or len(rows) != manifest["train_samples"]:
        raise ValueError("training_count_mismatch")
    for index, (row, source) in enumerate(zip(rows, metadata)):
        if source["row_index"] != index or row["tools"] != tools:
            raise ValueError(f"row_or_tools_mismatch:{index}")
    return rows, metadata, snapshot


def encode_dataset(tokenizer, rows, metadata, max_length):
    """整条轨迹只出现一次，所有 assistant 都学习；超长报错，不截断。"""
    features, records = [], []
    for index, (row, source) in enumerate(zip(rows, metadata)):
        try:
            feature, audit = prepare_example(tokenizer, row, enable_thinking=False, max_length=max_length)
        except ValueError as exc:
            raise ValueError(f"第 {index} 行 {source['id']}: {exc}") from exc
        features.append(feature)
        records.append({"id": source["id"], "scenario": source["scenario"], "row_index": index,
                        **{key: audit[key] for key in ("tokens", "supervised_tokens", "assistant_messages", "tool_calls")}})
    return features, records


def select_smoke_indices(records, count, seed):
    """优先包含每个场景的最长轨迹，其余固定随机抽取，避免只测短句。"""
    scenes = sorted({row["scenario"] for row in records})
    if count < len(scenes):
        raise ValueError("smoke_samples 必须足以包含每个场景")
    chosen = [max((i for i, row in enumerate(records) if row["scenario"] == scene),
                  key=lambda i: records[i]["tokens"]) for scene in scenes]
    remaining = [i for i in range(len(records)) if i not in chosen]
    random.Random(seed).shuffle(remaining)
    return chosen + remaining[:max(0, min(count, len(records)) - len(chosen))]


class AssistantOnlyCollator:
    """仅右侧补齐并转成 tensor，绝不把 labels 重建为 input_ids。

    -100 是交叉熵的忽略值。按 attention_mask 屏蔽 padding，不能按 token ID
    屏蔽：有些 tokenizer 的 padding 与 EOS 相同，EOS 仍然需要学习。
    """

    def __init__(self, pad_token_id):
        self.pad_token_id = pad_token_id

    def __call__(self, examples):
        import torch

        for row in examples:
            if not any(label != -100 for label in row["labels"]):
                raise ValueError("样本没有可学习的 assistant token")
            if any(label != -100 and (label != token or mask != 1)
                   for token, mask, label in zip(row["input_ids"], row["attention_mask"], row["labels"])):
                raise ValueError("invalid_training_labels")
        padded = pad_examples(examples, self.pad_token_id)
        return {name: torch.tensor(values, dtype=torch.long) for name, values in padded.items()}


def assert_batch_preserved(batch, examples):
    """检查真正进入模型的 batch，而不仅检查磁盘上的数据格式。"""
    for index, row in enumerate(examples):
        size = len(row["input_ids"])
        for name in ("input_ids", "attention_mask", "labels"):
            if batch[name][index, :size].tolist() != row[name]:
                raise ValueError(f"trainer_changed_{name}")
        if any(x != -100 for x in batch["labels"][index, size:].tolist()):
            raise ValueError("padding_contributes_to_loss")
