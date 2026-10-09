"""重新加载一次训练产物并生成文本；不连接天气服务或真实设备。

这是保存/加载与非思考输入格式的检查，不是业务评测或评分。
"""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from sft_data import sha256, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--prompt", default="你好，请简短介绍一下你能做什么。")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("输出文件已存在，请使用新文件名")
    if args.max_new_tokens <= 0:
        raise ValueError("max-new-tokens 必须为正数")
    run = args.run_dir.resolve()
    status = json.loads((run / "status.json").read_text())
    if status["status"] != "gpu_training_completed_reload_pending":
        raise ValueError("训练尚未成功完成，请先检查 status.json")
    adapter = run / "final-adapter"
    for name, expected in status["adapter_sha256"].items():
        if sha256(adapter / name) != expected:
            raise ValueError(f"adapter_changed:{name}")
    source = json.loads((run / "model-source.json").read_text())
    if source["enable_thinking"] is not False:
        raise ValueError("本项目使用非思考模式")

    # 顺序不能调换：Unsloth 的运行时补丁先于 Transformers/PEFT 加载。
    from unsloth import FastLanguageModel
    import torch
    from peft import PeftModel
    from transformers import AutoTokenizer
    from train_sft import load_base_model, check_loaded_tokenizer

    if not torch.cuda.is_available() or torch.cuda.device_count() != 1 or not torch.cuda.is_bf16_supported():
        raise ValueError("请提供一张支持 BF16 的 NVIDIA GPU")
    config = SimpleNamespace(max_seq_length=source["max_seq_length"], seed=20261009)
    # 显式加载相同 revision 的底座，再挂载适配器，避免 PEFT 默认加载移动的 main。
    model, loaded = load_base_model(source, config)
    tokenizer = AutoTokenizer.from_pretrained(adapter, local_files_only=True, trust_remote_code=False)
    tools = json.loads((run / "tools.json").read_text())
    messages = [{"role": "system", "content": (run / "system-prompt.txt").read_text()},
                {"role": "user", "content": args.prompt}]
    check_loaded_tokenizer(loaded, tokenizer, [{"messages": messages, "tools": tools}])
    model = PeftModel.from_pretrained(model, adapter, is_trainable=False)
    FastLanguageModel.for_inference(model)
    model.eval()
    # 每次推理都明确禁用思考，不依赖库默认值；tools 只由模板插入一次。
    prompt = tokenizer.apply_chat_template(messages, tools=tools, tokenize=False,
                                          add_generation_prompt=True, enable_thinking=False)
    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
    input_length = inputs["input_ids"].shape[1]
    if input_length + args.max_new_tokens > config.max_seq_length:
        raise ValueError("输入与输出预算超出上下文长度，不自动截断")
    with torch.inference_mode():
        generated = model.generate(**inputs, max_new_tokens=args.max_new_tokens,
                                   do_sample=False, use_cache=True,
                                   pad_token_id=tokenizer.pad_token_id,
                                   eos_token_id=tokenizer.eos_token_id)
    completion = tokenizer.decode(generated[0, input_length:], skip_special_tokens=False)
    result = {"adapter_reload_verified": True, "business_evaluation": False,
              "enable_thinking": False, "model_source": source,
              "input_tokens": input_length, "prompt": args.prompt,
              "completion": completion, "tools_executed": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, result)
    print(completion)


if __name__ == "__main__":
    main()
