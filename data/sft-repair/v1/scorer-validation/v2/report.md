# 事实评分器验收

状态：failed；14 个正反例 × 3 次，符合预期 40/42。

预期标签未发送给评分模型；没有调用设备工具，没有修改训练样本。全部尝试均保留，任何误判或评分错误都会阻止数据修订阶段。

| 用例 | 预期 | 每次结果 |
|---|---|---|
| wrong_room | fail | fail, pass, pass |
| correct_cross_room | pass | pass, pass, pass |
| unchanged_item4 | pass | pass, pass, pass |
| unchanged_item5 | pass | pass, pass, pass |
| unqualified_no_umbrella | fail | fail, fail, fail |
| conditional_umbrella_advice | pass | pass, pass, pass |
| faithful_cloudy_forecast | pass | pass, pass, pass |
| cloudy_means_no_rain | fail | fail, fail, fail |
| current_precipitation_wrong_date | fail | fail, fail, fail |
| temperature_wrong_date | fail | fail, fail, fail |
| dated_forecast | pass | pass, pass, pass |
| explicit_summary_ambiguity | pass | pass, pass, pass |
| humidity_as_rain_probability | fail | fail, fail, fail |
| wrong_room_paraphrase | fail | fail, fail, fail |
