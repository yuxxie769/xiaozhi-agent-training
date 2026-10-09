# 评估种子生成器

本目录保存从原 agent server 迁入的天气、家居种子生成逻辑和所需静态资源。`scripts/generate_evaluation_seeds.py` 负责读取当前评分结果、计算模板比例、调用这些生成器并去除与源种子重合的变量组。

生成器只生成测试定义，不调用模型、天气服务或真实家居设备。家居 preset 从已保存的 `conversations.json` 中恢复，因此生成结果与源评估器使用同一批模拟器条件。`snapshot_library.py` 只实现种子生成需要的只读接口。

重合检查以完整变量组为单位。语义指纹忽略 `seed_id`、`variable_group_id`、`question_pattern_id` 和 `user_turns`，因此同一变量仅改成 P1/P2/P3 的另一种说法仍会被判为重合。用户消息相同但语义变量不同可以保留，例如“今天天气怎么样”在不同默认城市下是不同测试条件；报告会记录这类文案重合。

从项目根目录执行：

```bash
python3 scripts/generate_evaluation_seeds.py \
  --config config.json \
  --output-dir data/evaluation-seeds/v1 \
  --random-seed 20261009
```

默认从 `config.test_fraction` 读取评估规模，并以评分结果中 `status=pass` 的样本计算模板比例。可用 `--weather-groups` 或 `--home-switch-groups` 明确覆盖某个场景的变量组总数。输出目录必须不存在，生成器不会覆盖已经冻结的测试种子。
