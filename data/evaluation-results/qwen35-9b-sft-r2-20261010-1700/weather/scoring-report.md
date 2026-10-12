# 天气评分报告 V2

规则版本：`2.0`；评分来源：`llm`。

## 核心结果

| 指标 | 结果 |
|---|---:|
| 评分完成率 | 2/60（3.3%） |
| 样本总通过率 | 50.0% |
| 检查项总通过率 | 92.9% |
| 筛掉的候选检查项 | 76 |
| 评分错误样本 | 58 |

## C01—C07

| 检查项 | 通过 | 未通过 | 通过率 |
|---|---:|---:|---:|
| C01 工具调用行为 | 2 | 0 | 100.0% |
| C02 工具参数正确性 | 2 | 0 | 100.0% |
| C03 报告城市名保留 | 2 | 0 | 100.0% |
| C04 对话动作正确性 | 2 | 0 | 100.0% |
| C05 用户需求完成度 | 2 | 0 | 100.0% |
| C06 答复事实有据 | 1 | 1 | 50.0% |
| C07 回复语言符合要求 | 2 | 0 | 100.0% |

## 场景分类

| 分类 | 覆盖 | 宏平均通过率 |
|---|---:|---:|
| R | 0/4 | — |
| T | 1/7 | 100.0% |
| L | 1/6 | 100.0% |
| F | 1/2 | 100.0% |
| M | 0/4 | — |
| O | 3/4 | 83.3% |
| G | 0/1 | — |

## 单场景通过率

| 场景 | 通过 | 未通过 | 通过率 |
|---|---:|---:|---:|
| R01 | 0 | 0 | — |
| R02 | 0 | 0 | — |
| R03 | 0 | 0 | — |
| R04 | 0 | 0 | — |
| T01 | 2 | 0 | 100.0% |
| T02 | 0 | 0 | — |
| T03 | 0 | 0 | — |
| T04 | 0 | 0 | — |
| T05 | 0 | 0 | — |
| T06 | 0 | 0 | — |
| T07 | 0 | 0 | — |
| L01 | 0 | 0 | — |
| L02 | 2 | 0 | 100.0% |
| L04 | 0 | 0 | — |
| L05 | 0 | 0 | — |
| L06 | 0 | 0 | — |
| L08 | 0 | 0 | — |
| F01 | 2 | 0 | 100.0% |
| F02 | 0 | 0 | — |
| M01 | 0 | 0 | — |
| M02 | 0 | 0 | — |
| M03 | 0 | 0 | — |
| M04 | 0 | 0 | — |
| O01 | 1 | 1 | 50.0% |
| O02 | 2 | 0 | 100.0% |
| O03 | 0 | 0 | — |
| O04 | 2 | 0 | 100.0% |
| G02 | 0 | 0 | — |

## 未通过汇总

有效评分 2 条，其中未通过 1 条。

### 按检查项

| 检查项 | 名称 | 未通过判定次数 | 涉及样本 | 有效样本占比 |
|---|---|---:|---:|---:|
| C06 | 答复事实有据 | 1 | 1 | 50.0% |

### 按模板

| 模板 | 输入 | 有效评分 | 评分错误 | 通过 | 未通过 | 通过率 |
|---|---:|---:|---:|---:|---:|---:|
| S01 | 3 | 2 | 1 | 1 | 1 | 50.0% |
| S02 | 3 | 0 | 3 | 0 | 0 | — |
| S03 | 3 | 0 | 3 | 0 | 0 | — |
| S04 | 3 | 0 | 3 | 0 | 0 | — |
| S05 | 3 | 0 | 3 | 0 | 0 | — |
| S06 | 3 | 0 | 3 | 0 | 0 | — |
| S07 | 3 | 0 | 3 | 0 | 0 | — |
| S08 | 3 | 0 | 3 | 0 | 0 | — |
| S09 | 3 | 0 | 3 | 0 | 0 | — |
| S10 | 3 | 0 | 3 | 0 | 0 | — |
| S11 | 3 | 0 | 3 | 0 | 0 | — |
| S12 | 3 | 0 | 3 | 0 | 0 | — |
| S13 | 3 | 0 | 3 | 0 | 0 | — |
| S15 | 3 | 0 | 3 | 0 | 0 | — |
| S17 | 3 | 0 | 3 | 0 | 0 | — |
| S19 | 3 | 0 | 3 | 0 | 0 | — |
| S20 | 3 | 0 | 3 | 0 | 0 | — |
| S21 | 3 | 0 | 3 | 0 | 0 | — |
| S22 | 3 | 0 | 3 | 0 | 0 | — |
| S24 | 3 | 0 | 3 | 0 | 0 | — |

### 常见未通过检查项组合

| 检查项组合 | 样本数 |
|---|---:|
| C06 | 1 |

## 检查项筛选

评分器先按场景为每一轮列出候选检查项，再去掉本轮不适用的项目。这里统计的是检查项次数，不是样本数。

| 阶段 | 数量 | 说明 |
|---|---:|---|
| 初始候选 | 540 | 根据样本场景和轮次列出的全部可能检查项 |
| 不适用并过滤 | 76 | 本轮没有对应天气调用、正常天气报告，或模板规定本轮不检查 |
| 进入评分 | 464 | 过滤后真正需要执行的检查项 |
| 成功产生结果 | 14 | 已得到 pass/fail 的检查项 |
| 因评分错误未产生结果 | 450 | 所属样本评分失败，因此整条样本未落分 |

计算关系：540 个候选 = 76 个过滤 + 464 个进入评分；464 个进入评分 = 14 个已产出结果 + 450 个未产出结果。
本批 450 个未产出检查项不计模型通过或未通过。

| 过滤原因 | 数量 | 含义 |
|---|---:|---|
| `no_new_weather_report` | 8 | 本轮没有新的正常天气报告，不重复检查城市名 |
| `no_weather_call` | 20 | 本轮没有天气工具调用，不检查工具参数 |
| `template_turn_not_applicable` | 48 | 按模板定义，本轮不需要此检查 |

> 被过滤的检查项不计通过或未通过。逐条筛选明细保留在 `scores.json` 的 `selection.filtered_details` 中，Markdown 不展开。

## 评分错误

| 样本 | 模板 | 阶段 | 错误码 | 原因 | 诊断 |
|---|---|---|---|---|---|
| `S01-E001-P3` | S01 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S02-E001-P1` | S02 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S02-E001-P2` | S02 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S02-E001-P3` | S02 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S03-E001-P1` | S03 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S03-E001-P2` | S03 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S03-E001-P3` | S03 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S04-E001-P1` | S04 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S04-E001-P2` | S04 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S04-E001-P3` | S04 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S05-E001-P1` | S05 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S05-E001-P2` | S05 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S05-E001-P3` | S05 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S06-E001-P1` | S06 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S06-E001-P2` | S06 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S06-E001-P3` | S06 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S07-E001-P1` | S07 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S07-E001-P2` | S07 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S07-E001-P3` | S07 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S08-E001-P1` | S08 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S08-E001-P2` | S08 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S08-E001-P3` | S08 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S09-E001-P1` | S09 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S09-E001-P2` | S09 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S09-E001-P3` | S09 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S10-E001-P1` | S10 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S10-E001-P2` | S10 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S10-E001-P3` | S10 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S11-E001-P1` | S11 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S11-E001-P2` | S11 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S11-E001-P3` | S11 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S12-E001-P1` | S12 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S12-E001-P2` | S12 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S12-E001-P3` | S12 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S13-E001-P1` | S13 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S13-E001-P2` | S13 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S13-E001-P3` | S13 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S15-E001-P1` | S15 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S15-E001-P2` | S15 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S15-E001-P3` | S15 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S17-E001-P1` | S17 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S17-E001-P2` | S17 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S17-E001-P3` | S17 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S19-E001-P1` | S19 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S19-E001-P2` | S19 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S19-E001-P3` | S19 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S20-E001-P1` | S20 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S20-E001-P2` | S20 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S20-E001-P3` | S20 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S21-E001-P1` | S21 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S21-E001-P2` | S21 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S21-E001-P3` | S21 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S22-E001-P1` | S22 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S22-E001-P2` | S22 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S22-E001-P3` | S22 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S24-E001-P1` | S24 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S24-E001-P2` | S24 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |
| `S24-E001-P3` | S24 | judge_response | `invalid_judge_json` | 本轮评分响应无效 | turn=1 |

> 评分错误不计为模型通过或未通过，也不进入有效评分通过率。

## 输出文件

- [scoring-report.md](scoring-report.md)：汇总报告。
- [scoring-failures.md](scoring-failures.md)：未通过样本、未通过检查项和简短证据。
- [scores.json](scores.json)：完整评分结果、全部通过/未通过证据和筛选审计数据。
- `scoring-events.jsonl`：评分执行事件；合并报告的事件保留在各原评分目录。
