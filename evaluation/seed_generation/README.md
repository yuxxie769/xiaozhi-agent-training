# 测试种子生成器

已接入当前 SFT 数据准备结果。现有 `data/evaluation-seeds/v3/` 保存天气 60 条、家居 60 条测试任务；尚未运行模型。

## 上游输入

默认读取 config.json 同目录下的 `data/prepared/`，可用 `--prepared-dir` 指定其他数据版本：

- inventory.json：来源数量和全部源轨迹的模板计数。
- audit.jsonl、metadata.jsonl、train.jsonl：实际进入训练的数据及来源，用来计算默认模板比例。
- tools.json：训练与模型评测共用的 9 个非 MCP 工具；天气、家居都使用完整列表。
- manifest.json：校验以上文件、提示词副本、源轨迹和评分文件，防止混用版本。

默认 `--score-status pass` 表示实际导出的训练样本（天气 283、家居 273），不再直接使用评分通过数。保留参数名以兼容原命令；`all` 使用盘点中的全部来源（天气 300、家居 299）。不论哪种比例，排重都使用全部源种子。

目标规模读取 `config.evaluation_seed_fraction`，当前为 0.2。每模板至少一组，每组 P1/P2/P3 三条，所以各 20 个模板会生成至少 60 条。可用 `--test-ratio` 或 `--weather-groups`、`--home-switch-groups` 改变规模。

## 生成与去重

沿用迁入的天气、家居生成逻辑及静态模板。家居 preset 从源 conversations 的 preset_config 恢复，不连接 server 或真实设备。

语义指纹忽略 seed_id、variable_group_id、question_pattern_id 和 user_turns。只换 ID 或同一变量的另一种表达仍按重复处理；与源种子或本批已接受种子重合时，整组丢弃并重采样。候选不足时明确报错，不放宽去重或悄悄减少数量。

相同文案但语义变量不同可以保留，例如相同提问对应不同默认城市；报告记录这种文案重合。本次天气和家居各有 5 个组存在源文案重合。字段指纹排重不等于未见模板测试，也不是自然语言语义相似度保证。

## 执行

已有 v1、v2、v3 不覆盖；重新生成用新目录：

```bash
python3 -B scripts/generate_evaluation_seeds.py \
  --config config.json \
  --prepared-dir data/prepared \
  --output-dir data/evaluation-seeds/v4 \
  --random-seed 20261009
```

输出 weather-seeds.json、home_switch-seeds.json、generation-report.json 和 report.md。报告绑定上游训练数据与 manifest 的校验值，并记录模板配额、生成依赖、随机种子、重采样碰撞及产物校验值。同样输入和参数可重复生成相同结果。

v3 绑定允许必要 Markdown 的新提示词版本，v1、v2 为旧版记录。工具列表变更后应重新生成版本绑定报告；相同随机种子下任务内容可以保持相同。

本入口只准备测试任务。后续模型评测入口需要加载种子、执行工具环境并保存对话，再调用评分器；本轮未实现该运行入口。
