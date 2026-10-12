"""Export this text-only Qwen3.5 PEFT LoRA for vLLM's multimodal wrapper.

Run with LLM_test's vLLM Python. Changes tensor names only; verifies every
tensor, base-layer shape and parsed module path before accepting the export.
The original training adapter is never modified.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


SOURCE_PREFIX = "base_model.model.model.layers."
DEPLOY_PREFIX = "base_model.model.model.language_model.layers."


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export(source, output, base):
    import torch
    import vllm
    from safetensors import safe_open
    from safetensors.torch import save_file
    from vllm.lora.lora_model import LoRAModel
    from vllm.lora.peft_helper import PEFTHelper
    from vllm.lora.utils import parse_fine_tuned_lora_name
    from vllm.model_executor.models.qwen3_5 import Qwen3_5ForConditionalGeneration

    source, output, base = source.resolve(), output.resolve(), base.resolve()
    if output.exists():
        raise ValueError(f"Export directory already exists: {output}")
    config_bytes = (source / "adapter_config.json").read_bytes()
    config = json.loads(config_bytes)
    if Path(config["base_model_name_or_path"]).resolve() != base:
        raise ValueError("Adapter base-model path differs from requested base")
    if config["peft_type"] != "LORA" or config.get("modules_to_save"):
        raise ValueError("Only this project's plain LoRA is supported")
    mapper = Qwen3_5ForConditionalGeneration.hf_to_vllm_mapper
    targets = set(config["target_modules"])
    index_path = base / "model.safetensors.index.json"
    index = json.loads(index_path.read_text())["weight_map"]
    base_modules = {}
    for name, shard in index.items():
        if (name.startswith("model.language_model.layers.")
                and name.endswith(".weight")
                and name.split(".")[-2] in targets):
            runtime_name = mapper._map_name(name[:-len(".weight")])
            base_modules[runtime_name] = (name, shard)

    original_path = source / "adapter_model.safetensors"
    renamed, key_map, original_modules, parsed_modules = {}, {}, set(), set()
    with safe_open(str(original_path), framework="pt", device="cpu") as stream:
        metadata = stream.metadata()
        for name in stream.keys():
            if not name.startswith(SOURCE_PREFIX):
                raise ValueError(f"Unexpected source tensor prefix: {name}")
            if not name.endswith((".lora_A.weight", ".lora_B.weight")):
                raise ValueError(f"Unexpected tensor: {name}")
            new_name = DEPLOY_PREFIX + name[len(SOURCE_PREFIX):]
            runtime_name, is_a = parse_fine_tuned_lora_name(new_name, mapper)
            if runtime_name not in base_modules:
                raise ValueError(f"No runtime base layer for {new_name}: {runtime_name}")
            base_name, shard = base_modules[runtime_name]
            if Path(shard).name != shard:
                raise ValueError("Unexpected checkpoint shard path")
            with safe_open(str(base / shard), framework="pt", device="cpu") as bf:
                shape = bf.get_slice(base_name).get_shape()
            tensor = stream.get_tensor(name)
            expected_shape = (config["r"], shape[1]) if is_a else (shape[0], config["r"])
            if tuple(tensor.shape) != expected_shape or not torch.isfinite(tensor).all():
                raise ValueError(f"Invalid tensor or base shape: {name}")
            if new_name in renamed:
                raise ValueError(f"Duplicate exported key: {new_name}")
            renamed[new_name], key_map[name] = tensor, new_name
            original_modules.add(parse_fine_tuned_lora_name(name, mapper)[0])
            parsed_modules.add(runtime_name)
    if parsed_modules != set(base_modules) or len(renamed) != 2 * len(parsed_modules):
        raise ValueError("Incomplete language-layer coverage")

    # Re-read an existing export only through an explicit new output path.
    output.mkdir(parents=True, exist_ok=False)
    (output / "adapter_config.json").write_bytes(config_bytes)
    deploy_path = output / "adapter_model.safetensors"
    save_file(renamed, str(deploy_path), metadata=metadata)
    with safe_open(str(deploy_path), framework="pt", device="cpu") as deployed:
        if set(deployed.keys()) != set(renamed):
            raise ValueError("Export key set changed")
        for original, new_name in key_map.items():
            expected, actual = renamed[new_name], deployed.get_tensor(new_name)
            if expected.dtype != actual.dtype or not torch.equal(expected, actual):
                raise ValueError(f"Export changed tensor values: {original}")
    helper = PEFTHelper.from_local_dir(str(output), 8192)
    loaded = LoRAModel.from_local_checkpoint(
        str(output), targets, helper, lora_model_id=1, device="cpu",
        weights_mapper=mapper,
    )
    if set(loaded.loras) != parsed_modules:
        raise ValueError("vLLM loader module coverage differs from export")
    report = {
        "export_verified": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "vllm_version": vllm.__version__,
        "source": str(source), "output": str(output), "base": str(base),
        "source_sha256": sha256(original_path),
        "deployment_sha256": sha256(deploy_path),
        "base_weight_index_sha256": sha256(index_path),
        "tensor_count": len(renamed), "runtime_modules": len(base_modules),
        "matched_before": len(original_modules & set(base_modules)),
        "matched_after": len(set(loaded.loras) & set(base_modules)),
        "all_tensor_values_shapes_dtypes_identical": True,
        "source_prefix": SOURCE_PREFIX, "deployment_prefix": DEPLOY_PREFIX,
    }
    (output / "export-verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (output / "README.md").write_text(
        "# vLLM deployment adapter\n\n"
        "Generated by scripts/export_vllm_adapter.py for the Qwen3.5 "
        "ConditionalGeneration wrapper. Tensor values are unchanged; only "
        "the language-model path prefix is adapted. Use the original "
        "final-adapter for Unsloth/PEFT training or reload.\n\n"
        "See export-verification.json for source hash and validation.\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.source, args.output, args.base), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
