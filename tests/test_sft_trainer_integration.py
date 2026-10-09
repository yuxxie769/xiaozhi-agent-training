"""真实 Trainer + PyTorch CPU 测试：随机微型模型，无网络、无 Qwen 权重。

验证训练器保留标签并完成一步参数更新；不能替代 Unsloth/CUDA 实测。
"""
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sft_data import AssistantOnlyCollator, assert_batch_preserved, load_config
from train_sft import training_argument_values


@unittest.skipUnless(all(importlib.util.find_spec(name) for name in ("torch", "transformers", "datasets")),
                     "需要 PyTorch/Transformers CPU 集成测试环境")
class TrainerIntegrationTests(unittest.TestCase):
    def test_real_trainer_preserves_masks_and_updates_parameters(self):
        import torch
        from datasets import Dataset
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from transformers import (LlamaConfig, LlamaForCausalLM, PreTrainedTokenizerFast,
                                  Trainer, TrainingArguments)

        torch.manual_seed(42)
        tokenizer = PreTrainedTokenizerFast(
            tokenizer_object=Tokenizer(WordLevel({"<pad>": 0, "<eos>": 1, "<unk>": 2,
                                                  **{f"t{i}": i for i in range(3, 32)}}, unk_token="<unk>")),
            pad_token="<pad>", eos_token="<eos>", unk_token="<unk>",
        )
        model = LlamaForCausalLM(LlamaConfig(vocab_size=32, hidden_size=16, intermediate_size=32,
                                             num_hidden_layers=1, num_attention_heads=2,
                                             num_key_value_heads=2, pad_token_id=0, eos_token_id=1))
        # 两条 assistant 段夹着工具上下文；全部 label 掩码须原封不动进入 forward。
        rows = [dict(input_ids=[3, 4, 5, 6, 7, 8, 1], attention_mask=[1]*7,
                     labels=[-100, -100, 5, -100, -100, 8, 1]),
                dict(input_ids=[9, 10, 11, 1], attention_mask=[1]*4,
                     labels=[-100, -100, 11, 1])]
        seen = []

        class InspectTrainer(Trainer):
            def compute_loss(self, model, inputs, *args, **kwargs):
                expected = {tuple(row["input_ids"]): row for row in rows}
                originals = [expected[tuple(ids[:int(mask.sum())].tolist())]
                             for ids, mask in zip(inputs["input_ids"], inputs["attention_mask"])]
                assert_batch_preserved(inputs, originals)
                seen.append(True)
                return super().compute_loss(model, inputs, *args, **kwargs)

        config, _, _ = load_config(ROOT / "train-sft.json")
        with tempfile.TemporaryDirectory() as directory:
            values = training_argument_values(config, directory, "smoke", len(rows))
            # 仅替换硬件和运行时长；沿用生产入口的全部数据与标签处理设置。
            values.update(use_cpu=True, bf16=False, optim="adamw_torch", max_steps=1,
                          per_device_train_batch_size=2, gradient_accumulation_steps=1,
                          save_strategy="no", disable_tqdm=True, dataloader_pin_memory=False, warmup_steps=0)
            trainer = InspectTrainer(model=model, processing_class=tokenizer,
                                     train_dataset=Dataset.from_list(rows), args=TrainingArguments(**values),
                                     data_collator=AssistantOnlyCollator(0))
            self.assertEqual(list(trainer.train_dataset), rows)
            before = model.lm_head.weight.detach().clone()
            result = trainer.train()
            self.assertTrue(seen)
            self.assertTrue(math.isfinite(result.training_loss))
            self.assertEqual(result.global_step, 1)
            self.assertFalse(torch.equal(before, model.lm_head.weight))


if __name__ == "__main__":
    unittest.main()
