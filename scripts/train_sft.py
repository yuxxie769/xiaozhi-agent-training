"""Qwen3.5-9B 非思考 SFT：预检 → BF16 LoRA 试跑 → 正式训练。

CPU: python scripts/train_sft.py --mode preflight --output-dir runs/preflight-01
GPU: python scripts/train_sft.py --mode smoke --output-dir runs/smoke-01
GPU: python scripts/train_sft.py --mode train --output-dir runs/sft-01

只保存本地 LoRA 适配器和检查记录，不上传模型，不执行工具调用。
"""

import argparse
from dataclasses import asdict
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess

from sft_data import (AssistantOnlyCollator, assert_batch_preserved, check_inputs,
                      encode_dataset, load_config, select_smoke_indices, sha256, write_json)

ROOT = Path(__file__).resolve().parents[1]


def package_versions():
    """只记录包名与版本；不把可能含私有仓库凭据的 pip URL 写入报告。"""
    names = ("torch", "transformers", "tokenizers", "trl", "datasets", "peft",
             "accelerate", "unsloth", "unsloth_zoo", "bitsandbytes", "triton", "jinja2")
    versions = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def load_local_tokenizer(path):
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    if not tokenizer.is_fast or tokenizer.pad_token_id is None:
        raise ValueError("需要带 offset mapping 和 pad token 的 fast tokenizer")
    tokenizer.padding_side = "right"
    return tokenizer


def load_base_model(snapshot, config):
    """固定官方底座；不允许自动换成另一个仓库的量化镜像。

    Unsloth 必须先于 Transformers/TRL 导入。text_only 去掉本任务不使用的视觉
    分支；BF16 LoRA 只优化低秩适配器，底座不进行 4-bit 量化。
    """
    from unsloth import FastLanguageModel
    import torch

    return FastLanguageModel.from_pretrained(
        model_name=snapshot["model_id"], revision=snapshot["revision"],
        use_exact_model_name=True, trust_remote_code=False,
        max_seq_length=config.max_seq_length, dtype=torch.bfloat16,
        load_in_4bit=False, load_in_16bit=True, full_finetuning=False,
        text_only=True, fast_inference=False, device_map={"": 0},
        use_gradient_checkpointing="unsloth", random_state=config.seed,
    )


def check_loaded_tokenizer(loaded, pinned, rows):
    """Unsloth 若改了模板或词表，拒绝沿用此前生成的标签。"""
    loaded = getattr(loaded, "tokenizer", loaded)
    if (loaded.get_vocab() != pinned.get_vocab() or loaded.chat_template != pinned.chat_template
            or loaded.eos_token_id != pinned.eos_token_id or loaded.pad_token_id != pinned.pad_token_id):
        raise ValueError("Unsloth tokenizer 与固定快照不一致，需重新验证，不能继续训练")
    # 同词表不代表同分词算法；对整批实际输入再比一次 token IDs。
    for index, row in enumerate(rows):
        text = pinned.apply_chat_template(row["messages"], tools=row["tools"], tokenize=False,
                                         add_generation_prompt=False, enable_thinking=False)
        if loaded(text, add_special_tokens=False)["input_ids"] != pinned(text, add_special_tokens=False)["input_ids"]:
            raise ValueError(f"loaded_tokenization_changed:{index}")


def training_argument_values(config, output, mode, sample_count):
    """Trainer 只负责优化循环；样本渲染、截断和标签制作均由本项目负责。"""
    steps_per_epoch = math.ceil(sample_count / (config.batch_size * config.gradient_accumulation_steps))
    total_steps = config.smoke_steps if mode == "smoke" else math.ceil(steps_per_epoch * config.epochs)
    return dict(
        output_dir=str(output),
        per_device_train_batch_size=config.batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        num_train_epochs=config.epochs,
        max_steps=config.smoke_steps if mode == "smoke" else -1,
        learning_rate=config.learning_rate, lr_scheduler_type="cosine",
        warmup_steps=math.ceil(total_steps * config.warmup_ratio), weight_decay=config.weight_decay,
        max_grad_norm=config.max_grad_norm,
        bf16=True, fp16=False, optim="adamw_8bit",
        # Unsloth 的 get_peft_model 已启用它自己的 checkpointing；避免 Trainer 重设。
        gradient_checkpointing=False,
        seed=config.seed, data_seed=config.seed,
        logging_steps=1, logging_nan_inf_filter=False,
        save_strategy="steps", save_steps=config.save_steps, save_total_limit=config.save_total_limit,
        eval_strategy="no", report_to="none", push_to_hub=False,
        dataloader_num_workers=0, remove_unused_columns=False,
        # Trainer 接收现成 token/labels，不做模板渲染、截断、packing 或二次掩码。
        label_names=["labels"],
    )


def run_gpu_training(config, snapshot, tokenizer, rows, features, records, output, mode, resume):
    from unsloth import FastLanguageModel
    import torch
    from datasets import Dataset
    from transformers import Trainer, TrainerCallback, TrainingArguments, set_seed

    set_seed(config.seed)
    indices = select_smoke_indices(records, config.smoke_samples, config.seed) if mode == "smoke" else list(range(len(features)))
    selected = [features[i] for i in indices]
    write_json(output / "selected-samples.json", [records[i] for i in indices])
    model, loaded_tokenizer = load_base_model(snapshot, config)
    check_loaded_tokenizer(loaded_tokenizer, tokenizer, rows)
    if getattr(model.config, "_commit_hash", None) not in (None, snapshot["revision"]):
        raise ValueError("loaded_model_revision_mismatch")

    # 按语言模型层的完整路径选择 Linear，避免误训练视觉层、lm_head 或词嵌入。
    # Qwen3.5 还有线性注意力投影；all-language-linear 比只列 q/k/v 更完整。
    targets = [name for name, layer in model.named_modules()
               if isinstance(layer, torch.nn.Linear)
               and not any(part in name.split(".") for part in ("visual", "vision_tower", "lm_head", "mtp"))]
    if not targets:
        raise ValueError("没有找到可训练的语言线性层")
    model = FastLanguageModel.get_peft_model(
        model, r=config.lora_rank, lora_alpha=config.lora_alpha,
        target_modules=targets, lora_dropout=0, bias="none",
        use_gradient_checkpointing="unsloth", random_state=config.seed,
    )
    model.config.use_cache = False
    trainable = [(name, parameter.numel()) for name, parameter in model.named_parameters() if parameter.requires_grad]
    if not trainable or any("lora_" not in name for name, _ in trainable):
        raise ValueError("只能训练 LoRA 参数，检测到底座或其他参数可训练")
    write_json(output / "lora-modules.json", {"target_modules": targets, "trainable_parameters": sum(n for _, n in trainable)})
    model.print_trainable_parameters()

    class FiniteTrainingCallback(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            # NaN 不作为正常 loss 静默记录。异常由入口写入 failed 状态。
            for key in ("loss", "grad_norm"):
                value = (logs or {}).get(key)
                if value is not None and not math.isfinite(float(value)):
                    raise FloatingPointError(f"训练出现非有限 {key}: {value}")

    class CheckedSFTTrainer(Trainer):
        def compute_loss(self, model, inputs, *args, **kwargs):
            # 核对第一次真正进入 forward 的 batch，包含 Trainer/Accelerate 的处理。
            if not getattr(self, "checked_first_batch", False):
                expected = {tuple(row["input_ids"]): row for row in selected}
                batch_rows = []
                for ids, mask in zip(inputs["input_ids"], inputs["attention_mask"]):
                    row = expected[tuple(ids[:int(mask.sum())].tolist())]
                    batch_rows.append(row)
                assert_batch_preserved(inputs, batch_rows)
                write_json(output / "actual-batch-check.json", {
                    "labels_preserved": True, "samples": len(batch_rows),
                    "supervised_tokens": int((inputs["labels"] != -100).sum()),
                })
                self.checked_first_batch = True
            return super().compute_loss(model, inputs, *args, **kwargs)

    trainer = CheckedSFTTrainer(
        model=model, processing_class=tokenizer,
        args=TrainingArguments(**training_argument_values(config, output, mode, len(selected))),
        train_dataset=Dataset.from_list(selected),
        data_collator=AssistantOnlyCollator(tokenizer.pad_token_id),
        callbacks=[FiniteTrainingCallback()],
    )
    # 核对每一行，发现版本不兼容导致的标签变化就在优化前退出。
    if len(trainer.train_dataset) != len(selected):
        raise ValueError("trainer_changed_sample_count")
    for index, row in enumerate(selected):
        if any(trainer.train_dataset[index][name] != row[name] for name in row):
            raise ValueError(f"trainer_changed_dataset:{index}")
    torch.cuda.reset_peak_memory_stats()
    result = trainer.train(resume_from_checkpoint=str(resume) if resume else None)
    if not math.isfinite(result.training_loss):
        raise FloatingPointError("最终 training_loss 非有限")
    # checkpoint 含优化器状态，final-adapter 则是用于加载推理的轻量最终产物。
    adapter_dir = output / "final-adapter"
    trainer.save_model(str(adapter_dir))
    tokenizer.save_pretrained(adapter_dir)
    trainer.save_state()
    trainer.save_metrics("train", result.metrics)
    return {"status": "gpu_training_completed_reload_pending", "mode": mode,
            "optimizer_steps": result.global_step, "train_loss": result.training_loss,
            "peak_allocated_gib": torch.cuda.max_memory_allocated() / 2**30,
            "peak_reserved_gib": torch.cuda.max_memory_reserved() / 2**30,
            "adapter_sha256": {p.name: sha256(p) for p in sorted(adapter_dir.iterdir()) if p.is_file()},
            "adapter_reload_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "train-sft.json")
    parser.add_argument("--mode", choices=("preflight", "smoke", "train"), default="preflight")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume-from-checkpoint", type=Path)
    args = parser.parse_args()
    config, prepared, tokenizer_dir = load_config(args.config)
    output = args.output_dir.resolve()
    rows, metadata, snapshot = check_inputs(prepared, tokenizer_dir)
    resume = args.resume_from_checkpoint.resolve() if args.resume_from_checkpoint else None
    fingerprint = {"config": asdict(config), "mode": args.mode,
                   "prepared_manifest_sha256": sha256(prepared / "manifest.json"),
                   "tokenizer_snapshot_sha256": sha256(tokenizer_dir / "snapshot.json"),
                   "scripts": {name: sha256(Path(__file__).with_name(name))
                               for name in ("train_sft.py", "sft_data.py", "training_format.py")}}
    if resume:
        if args.mode == "preflight" or resume.parent != output:
            raise ValueError("只能恢复同一训练输出目录下的 checkpoint")
        for name in ("trainer_state.json", "optimizer.pt", "scheduler.pt"):
            if not (resume / name).is_file():
                raise ValueError(f"checkpoint 缺少恢复文件:{name}")
        if json.loads((output / "run-fingerprint.json").read_text()) != fingerprint:
            raise ValueError("恢复时数据、配置、模式或代码已改变，请使用原版本")
    else:
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / "run-fingerprint.json", fingerprint)
    write_json(output / "status.json", {"status": "preparing", "mode": args.mode})
    try:
        if args.mode != "preflight":
            # 顶层不导入 Transformers：Unsloth 的补丁必须先安装。
            import unsloth  # noqa: F401
            import torch
            if (not torch.cuda.is_available() or torch.cuda.device_count() != 1
                    or int(os.environ.get("WORLD_SIZE", "1")) != 1):
                raise ValueError("请用 CUDA_VISIBLE_DEVICES 暴露恰好一张 NVIDIA GPU，单进程运行")
            if not torch.cuda.is_bf16_supported():
                raise ValueError("本配置要求原生 BF16，不自动降成 FP16")
            if int(importlib.metadata.version("transformers").split(".")[0]) < 5:
                raise ValueError("Qwen3.5 GPU 训练需要 Transformers 5；旧 CPU 验证环境不能训练")
            write_json(output / "gpu.json", {"name": torch.cuda.get_device_name(0),
                       "total_gib": torch.cuda.get_device_properties(0).total_memory / 2**30,
                       "torch_cuda": torch.version.cuda})
            driver = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv"],
                                    capture_output=True, text=True, check=True)
            (output / "nvidia-smi.txt").write_text(driver.stdout)
        write_json(output / "environment.json", {"python": platform.python_version(),
                   "platform": platform.platform(), "packages": package_versions()})
        tokenizer = load_local_tokenizer(tokenizer_dir)
        features, records = encode_dataset(tokenizer, rows, metadata, config.max_seq_length)
        write_json(output / "preflight.json", {"samples": len(rows), "tools": len(rows[0]["tools"]),
                   "max_tokens": max(r["tokens"] for r in records), "enable_thinking": False,
                   "assistant_messages": sum(r["assistant_messages"] for r in records),
                   "tool_calls": sum(r["tool_calls"] for r in records),
                   "truncation": False, "packing": False})
        write_json(output / "sample-lengths.json", records)
        for name in ("tools.json", "system-prompt.txt"):
            shutil.copy2(prepared / name, output / name)
        write_json(output / "model-source.json", {"model_id": snapshot["model_id"], "revision": snapshot["revision"],
                   "enable_thinking": False, "max_seq_length": config.max_seq_length})
        if args.mode == "preflight":
            result = {"status": "cpu_preflight_passed", "training_started": False}
        else:
            result = run_gpu_training(config, snapshot, tokenizer, rows, features, records,
                                      output, args.mode, resume)
        write_json(output / "status.json", result)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        write_json(output / "status.json", {"status": "failed", "mode": args.mode,
                   "error_type": type(exc).__name__, "message": str(exc)})
        raise


if __name__ == "__main__":
    main()
