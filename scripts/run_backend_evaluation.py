"""复制固定评测输入，调用本机后端，再把报告带回训练项目。

模型解析、对话循环、模拟器和评分都由后端负责。本入口不启动推理服务，
也不加载模型权重。baseline / sft 只标记批次，两者都使用 model_eval。
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from generate_evaluation_seeds import load_prepared_inputs, Library

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ("weather", "home_switch")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_inputs(config_path, prepared_dir, seeds_dir):
    """复用已有数据版本检查，再核对种子的绑定和文件校验值。"""
    sources, binding = load_prepared_inputs(config_path, prepared_dir)
    report = read_json(seeds_dir / "generation-report.json")
    previous = report["prepared_data"]
    for key in ("manifest_sha256", "artifact_sha256", "target_tool_names"):
        if previous[key] != binding[key]:
            raise ValueError(f"测试种子与当前训练数据不匹配：{key}")
    seeds = {}
    for scene in SCENARIOS:
        info = report["scenarios"][scene]
        path = seeds_dir / f"{scene}-seeds.json"
        if sha256(path) != info["output_sha256"]:
            raise ValueError(f"测试种子校验失败：{scene}")
        if (
            sha256(sources[scene]["conversations_path"])
            != info["source_conversations_sha256"]
        ):
            raise ValueError(f"测试种子来源不一致：{scene}")
        seeds[scene] = read_json(path)
        if not seeds[scene] or len(seeds[scene]) != info["generated_seeds"]:
            raise ValueError(f"测试种子数量不一致：{scene}")
    # 只复制种子使用的 preset；resolve 保留完整静态配置，不重新生成目录。
    library = Library(sources["home_switch"]["conversations_path"])
    presets = {
        name: library.resolve(name)
        for name in sorted({s["preset"] for s in seeds["home_switch"]})
    }
    return seeds, presets, binding


def backend_version(server_dir):
    """记录提交号和实际相关源码校验值，未提交的适配也能追溯。"""
    result = subprocess.run(
        ["git", "-C", str(server_dir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    files = list((server_dir / "text-client").glob("*.py"))
    files += list((server_dir / "core" / "home_switch_simulator").glob("*.py"))
    files += [
        server_dir / "core" / name
        for name in (
            "connection.py",
            "evaluation.py",
            "evaluation_model.py",
            "model_eval.py",
        )
    ]
    return {
        "git_commit": result.stdout.strip() if result.returncode == 0 else None,
        "code_sha256": {
            str(path.relative_to(server_dir)): sha256(path)
            for path in sorted(files)
            if path.is_file()
        },
    }


def invoke(command, cwd, log):
    """参数列表直接传给子进程，路径含空格也无需 shell 转义。"""
    with log.open("w", encoding="utf-8") as stream:
        try:
            return subprocess.run(
                [str(item) for item in command],
                cwd=cwd,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            ).returncode
        except OSError as exc:
            stream.write(f"无法启动子进程：{type(exc).__name__}\n")
            return 127


def run(args):
    # 所有输入检查放在建立批次之前，错误输入不留下貌似成功的批次。
    server = args.server_dir.resolve()
    # 保留虚拟环境中的 Python 符号链接；resolve() 会绕过该环境。
    python = args.server_python.absolute()
    config = args.eval_config.resolve()
    prepared, seeds_dir = args.prepared_dir.resolve(), args.seeds_dir.resolve()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.run_id):
        raise ValueError("批次 ID 仅支持字母、数字、点、下划线和短横线")
    for path in (
        python,
        config,
        server / "text-client/generate_conversations.py",
        server / "text-client/score_results.py",
    ):
        if not path.is_file():
            raise ValueError(f"缺少文件：{path}")
    seeds, presets, binding = checked_inputs(args.config.resolve(), prepared, seeds_dir)
    batch = server / "tmp/model-eval-runs" / args.run_id
    returned = args.results_dir.resolve() / args.run_id
    if batch.exists() or returned.exists():
        raise ValueError("批次目录已存在；请换一个批次 ID，不覆盖历史结果")
    batch.mkdir(parents=True)
    returned.mkdir(parents=True)
    inputs = batch / "inputs"
    inputs.mkdir()
    for name in ("system-prompt.txt", "tools.json"):
        shutil.copy2(prepared / name, inputs / name)
    for scene in SCENARIOS:
        shutil.copy2(seeds_dir / f"{scene}-seeds.json", inputs / f"{scene}-seeds.json")
    shutil.copy2(
        seeds_dir / "generation-report.json", inputs / "seed-generation-report.json"
    )
    write_json(inputs / "preset-snapshots.json", presets)
    record = {
        "schema_version": 1,
        "run_id": args.run_id,
        "stage": args.stage,
        "environment": "model_eval",
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "backend_directory": str(batch),
        "backend_python": str(python),
        "eval_config_path": str(config),
        "eval_config_sha256": sha256(config),
        "prepared_data": binding,
        "backend_version": backend_version(server),
        "launcher_sha256": sha256(Path(__file__)),
        "input_sha256": {path.name: sha256(path) for path in sorted(inputs.iterdir())},
        "generation": {},
    }
    write_json(batch / "run.json", record)
    scoring_dir = batch / "scoring"
    generation_reports = []
    conversations = []
    try:
        for scene in SCENARIOS:
            output = batch / "generation" / scene
            command = [
                python,
                server / "text-client/generate_conversations.py",
                "--scenario",
                scene,
                "--environment",
                "model_eval",
                "--eval-config",
                config,
                "--seeds",
                inputs / f"{scene}-seeds.json",
                "--system-prompt-file",
                inputs / "system-prompt.txt",
                "--tools-file",
                inputs / "tools.json",
                "--output-dir",
                output,
                "--tool-backend",
                "simulated" if scene == "home_switch" else "real",
            ]
            if scene == "home_switch":
                command += ["--preset-snapshots", inputs / "preset-snapshots.json"]
            code = invoke(command, server, batch / f"{scene}-generation.log")
            trajectory = output / "conversations.json"
            # 启动失败时没有生成报告也正常：入口记录计划数和实际落盘数，
            # 原始生成报告保持不变，混合评分仍能以完整计划数计算完成率。
            artifact_error = None
            try:
                saved = read_json(trajectory) if trajectory.exists() else []
                if not isinstance(saved, list):
                    raise ValueError("生成结果不是数组")
                expected_ids = {seed["seed_id"] for seed in seeds[scene]}
                actual_ids = [row["sample_id"] for row in saved]
                if (
                    len(actual_ids) != len(set(actual_ids))
                    or not set(actual_ids) <= expected_ids
                    or any(
                        row.get("context", {}).get("scenario") != scene for row in saved
                    )
                ):
                    raise ValueError("轨迹与本场景种子无法逐条对应")
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                saved = []
                artifact_error = f"{type(exc).__name__}: {exc}"
                code = code or 2
            accounting = {
                "scenario": scene,
                "planned": len(seeds[scene]),
                "saved": len(saved),
                "process_returncode": code,
                "generation_report": str(output / "generation-report.json"),
            }
            if artifact_error:
                accounting["artifact_error"] = artifact_error
            record["generation"][scene] = accounting
            path = batch / f"{scene}-accounting.json"
            write_json(path, accounting)
            generation_reports.append(path)
            if trajectory.exists() and not artifact_error:
                conversations.append(trajectory)
            write_json(batch / "run.json", record)
        # 两场景都未产出时也返回一份未完成报告，不伪造任何轨迹。
        if not conversations:
            empty = batch / "empty-scoring-input.json"
            write_json(empty, [])
            conversations.append(empty)
        command = [
            python,
            server / "text-client/score_results.py",
            "--scenario",
            "auto",
            "--eval-config",
            config,
            "--output-dir",
            scoring_dir,
        ]
        for path in conversations:
            command += ["--input", path]
        for path in generation_reports:
            command += ["--generation-report", path]
        record["scoring_returncode"] = invoke(command, server, batch / "scoring.log")
        score = (
            read_json(scoring_dir / "scores.json")
            if (scoring_dir / "scores.json").exists()
            else {}
        )
        complete = (
            record["scoring_returncode"] == 0
            and score.get("status") == "complete"
            and all(
                item["process_returncode"] == 0
                for item in record["generation"].values()
            )
        )
        record["status"] = "complete" if complete else "incomplete"
        record["summary"] = score.get("summary", {})
    except (OSError, ValueError, KeyError) as exc:
        record["status"] = "incomplete"
        record["launcher_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        # 不复制对话：完整轨迹及日志留在后端；带回评分、证据和公开模型快照。
        if scoring_dir.exists():
            for path in scoring_dir.rglob("*"):
                if path.is_file() and path.suffix in {".json", ".md"}:
                    destination = returned / path.relative_to(scoring_dir)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, destination)
        for scene in SCENARIOS:
            output = batch / "generation" / scene
            for name in (
                "generation-report.json",
                "generation-report.md",
                "models.snapshot.json",
                "generation-config.snapshot.json",
            ):
                source = output / name
                if source.is_file():
                    destination = returned / "generation" / scene / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
        if not (returned / "scoring-report.md").exists():
            (returned / "scoring-report.md").write_text(
                "# 评测未完成\n\n后端未产出评分报告。详见 run.json 和后端日志。\n",
                encoding="utf-8",
            )
        if record["status"] == "running":
            record["status"] = "incomplete"
        record["returned_report_sha256"] = {
            str(path.relative_to(returned)): sha256(path)
            for path in sorted(returned.rglob("*"))
            if path.is_file()
        }
        write_json(batch / "run.json", record)
        write_json(returned / "run.json", record)
    print(
        f"状态：{record['status']}\n报告：{returned / 'scoring-report.md'}\n后端：{batch}"
    )
    return 0 if record["status"] == "complete" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server-dir", type=Path, required=True, help="后端 main/xiaozhi-server 目录"
    )
    parser.add_argument(
        "--server-python", type=Path, required=True, help="已安装后端依赖的 Python 路径"
    )
    parser.add_argument(
        "--eval-config",
        type=Path,
        required=True,
        help="沿用后端评测配置，入口不解析模型",
    )
    parser.add_argument("--run-id", required=True, help="新的批次 ID，不能覆盖旧目录")
    parser.add_argument("--stage", choices=["baseline", "sft"], default="baseline")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--prepared-dir", type=Path, default=ROOT / "data/prepared")
    parser.add_argument(
        "--seeds-dir", type=Path, default=ROOT / "data/evaluation-seeds/v3"
    )
    parser.add_argument(
        "--results-dir", type=Path, default=ROOT / "data/evaluation-results"
    )
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"评测入口检查失败：{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
