"""Run the epoch-checkpoint SFT suite directly on shared AutoDL storage.

The queue is intentionally sequential because all experiments share one GPU.
It writes an atomic machine-readable manifest and a short operator README after
every state change.  WANDB_API_KEY must be supplied through the process
environment; it is never written to disk.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SHARED_ROOT = Path("/autodl-fs/data/xiaozhi-agent-sft")
MODEL_DIR = Path("/autodl-fs/data/qwen3.5-9b")
EXPECTED_STEPS = (89, 178, 267)
EXPERIMENTS = (
    {"name": "sft-05", "config": "train-sft-v5.json", "learning_rate": 1e-4,
     "description": "1e-4 learning-rate run with epoch checkpoints"},
    {"name": "sft-03", "config": "train-sft-v3.json", "learning_rate": 7.5e-5,
     "description": "7.5e-5 retrain to recover epoch checkpoints"},
    {"name": "sft-04", "config": "train-sft-v4.json", "learning_rate": 5e-5,
     "description": "5e-5 retrain to recover epoch checkpoints"},
)


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_record(shared: Path, experiment):
    run = shared / "runs" / experiment["name"]
    status_file = run / "status.json"
    reload_file = run / "reload-check.json"
    status = read_json(status_file) if status_file.is_file() else None
    reload = read_json(reload_file) if reload_file.is_file() else None
    checkpoints = []
    for step in EXPECTED_STEPS:
        checkpoint = run / f"checkpoint-{step}"
        state_file = checkpoint / "trainer_state.json"
        state = read_json(state_file) if state_file.is_file() else None
        checkpoints.append({
            "epoch": step // EXPECTED_STEPS[0],
            "step": step,
            "relative_path": str(checkpoint.relative_to(shared)),
            "exists": checkpoint.is_dir(),
            "adapter_present": (checkpoint / "adapter_model.safetensors").is_file(),
            "recorded_global_step": state.get("global_step") if state else None,
            "recorded_epoch": state.get("epoch") if state else None,
        })
    complete = (
        status is not None
        and status.get("status") == "gpu_training_completed_reload_pending"
        and all(item["adapter_present"] and item["recorded_global_step"] == item["step"]
                for item in checkpoints)
        and reload is not None
        and reload.get("adapter_reload_verified") is True
    )
    if complete:
        state = "complete"
    elif status and status.get("status") == "failed":
        state = "failed"
    elif run.exists():
        state = "running_or_incomplete"
    else:
        state = "pending"
    return {
        **experiment,
        "state": state,
        "run_relative_path": str(run.relative_to(shared)),
        "config_relative_path": f"configs/{experiment['config']}",
        "expected_optimizer_steps": 267,
        "expected_epochs": 3,
        "checkpoints": checkpoints,
        "final_adapter_relative_path": str((run / "final-adapter").relative_to(shared)),
        "final_adapter_present": (run / "final-adapter" / "adapter_model.safetensors").is_file(),
        "reload_verified": bool(reload and reload.get("adapter_reload_verified") is True),
        "training_loss": status.get("train_loss") if status else None,
    }


def update_index(shared: Path, queue=None):
    shared.mkdir(parents=True, exist_ok=True)
    records = [run_record(shared, experiment) for experiment in EXPERIMENTS]
    manifest = {
        "schema_version": 1,
        "updated_at": now(),
        "shared_root": str(shared),
        "base_model": {
            "model_id": "Qwen/Qwen3.5-9B",
            "local_path": str(MODEL_DIR),
            "revision": "c202236235762e1c871ad0ccb60c8ee5ba337b9a",
        },
        "training_format": "PEFT LoRA adapter; base model is required",
        "deployment_note": (
            "Raw checkpoints are verified with PEFT/Unsloth. Qwen3.5 vLLM deployment requires "
            "scripts/export_vllm_adapter.py in a vLLM environment before service loading."
        ),
        "expected_epoch_steps": list(EXPECTED_STEPS),
        "queue": queue,
        "versions": records,
        "legacy": [
            {"name": "sft-03-original", "relative_path": "legacy/sft-03-original",
             "note": "Original completed run; only late checkpoints 250 and 267 are retained."},
            {"name": "sft-04-original", "relative_path": "legacy/sft-04-original",
             "note": "Original completed run; only late checkpoints 250 and 267 are retained."},
        ],
    }
    atomic_json(shared / "manifest.json", manifest)
    lines = [
        "# Xiaozhi SFT checkpoint collection",
        "",
        f"Updated: `{manifest['updated_at']}`",
        "",
        "Base model: `Qwen/Qwen3.5-9B` at `/autodl-fs/data/qwen3.5-9b`. ",
        "All official runs use the same 606 base samples plus 53 targeted samples at 3x sampling, "
        "LoRA rank/alpha 16/16, three epochs, and seed 20261009. Only learning rate differs.",
        "",
        "| Version | Learning rate | State | Epoch checkpoints | Reload |",
        "|---|---:|---|---|---|",
    ]
    for record in records:
        available = ", ".join(
            f"e{item['epoch']}→`{item['relative_path']}`"
            for item in record["checkpoints"] if item["adapter_present"]
        ) or "pending"
        lines.append(
            f"| {record['name']} | {record['learning_rate']:.2g} | {record['state']} | "
            f"{available} | {'yes' if record['reload_verified'] else 'no'} |"
        )
    lines.extend([
        "",
        "`manifest.json` is the authoritative machine-readable index. Load a listed checkpoint as "
        "a PEFT LoRA together with the pinned base model. `final-adapter/` is the final three-epoch "
        "copy; the numbered checkpoint directories are the artifacts for epoch-length comparison.",
        "",
        "For vLLM, do not point the service at a raw training checkpoint directly. In the vLLM "
        "environment, run the bundled `tools/export_vllm_adapter.py` with `--source`, `--output`, "
        "and `--base /autodl-fs/data/qwen3.5-9b`; then load the verified exported directory.",
        "",
        "The `legacy/` directory contains the earlier v3/v4 final runs. The `aborted/` directory "
        "contains non-evaluation partial attempts and must not be used for scoring.",
        "",
    ])
    temporary = shared / "README.md.tmp"
    temporary.write_text("\n".join(lines), encoding="utf-8")
    temporary.replace(shared / "README.md")
    return manifest


def write_queue_status(shared: Path, state, current=None, error=None):
    payload = {"state": state, "updated_at": now(), "current": current,
               "order": [item["name"] for item in EXPERIMENTS], "error": error}
    atomic_json(shared / "queue-status.json", payload)
    update_index(shared, payload)
    return payload


def verify_run(run: Path):
    for epoch, step in enumerate(EXPECTED_STEPS, start=1):
        checkpoint = run / f"checkpoint-{step}"
        state = read_json(checkpoint / "trainer_state.json")
        if state.get("global_step") != step or abs(float(state.get("epoch")) - epoch) > 1e-9:
            raise RuntimeError(f"checkpoint mismatch: {checkpoint}")
        for name in ("adapter_config.json", "adapter_model.safetensors"):
            if not (checkpoint / name).is_file():
                raise RuntimeError(f"checkpoint missing {name}: {checkpoint}")


def replace_workspace_link(name: str, target: Path):
    link = ROOT / "runs" / name
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        raise RuntimeError(f"refusing to replace non-symlink workspace path: {link}")
    link.symlink_to(target)


def run_command(command, log):
    with log.open("a", encoding="utf-8") as stream:
        stream.write("\n$ " + " ".join(map(str, command)) + "\n")
        stream.flush()
        subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)


def run_suite(shared: Path):
    if not os.environ.get("WANDB_API_KEY"):
        raise RuntimeError("WANDB_API_KEY is required in the process environment")
    for name in ("runs", "logs", "configs", "tools", "legacy", "aborted"):
        (shared / name).mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts" / "export_vllm_adapter.py",
                 shared / "tools" / "export_vllm_adapter.py")
    for experiment in EXPERIMENTS:
        shutil.copy2(ROOT / experiment["config"], shared / "configs" / experiment["config"])
    write_queue_status(shared, "running", current=EXPERIMENTS[0]["name"])
    try:
        for experiment in EXPERIMENTS:
            name = experiment["name"]
            output = shared / "runs" / name
            if output.exists():
                record = run_record(shared, experiment)
                if record["state"] == "complete":
                    replace_workspace_link(name, output)
                    continue
                raise RuntimeError(f"refusing to overwrite incomplete output: {output}")
            write_queue_status(shared, "running", current=name)
            log = shared / "logs" / f"{name}.log"
            run_command([
                sys.executable, str(ROOT / "scripts" / "train_sft.py"),
                "--config", str(ROOT / experiment["config"]),
                "--mode", "train", "--output-dir", str(output),
                "--model-dir", str(MODEL_DIR),
            ], log)
            verify_run(output)
            run_command([
                sys.executable, str(ROOT / "scripts" / "check_sft_adapter.py"),
                "--run-dir", str(output), "--output", str(output / "reload-check.json"),
            ], log)
            reload = read_json(output / "reload-check.json")
            if reload.get("adapter_reload_verified") is not True:
                raise RuntimeError(f"adapter reload failed: {name}")
            replace_workspace_link(name, output)
            update_index(shared, read_json(shared / "queue-status.json"))
        write_queue_status(shared, "complete")
    except Exception as exc:
        write_queue_status(shared, "failed", current=name if 'name' in locals() else None,
                           error={"type": type(exc).__name__, "message": str(exc)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared-root", type=Path, default=DEFAULT_SHARED_ROOT)
    parser.add_argument("--index-only", action="store_true")
    args = parser.parse_args()
    shared = args.shared_root.resolve()
    if args.index_only:
        print(json.dumps(update_index(shared), ensure_ascii=False, indent=2))
    else:
        run_suite(shared)


if __name__ == "__main__":
    main()
