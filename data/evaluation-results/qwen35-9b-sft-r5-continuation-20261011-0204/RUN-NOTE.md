# 第五轮 SFT 断点补跑结果

本次从缺失的 17 条家居任务中成功补齐并评分 16 条（首轮 15 条，保留异常证据重试后补齐 1 条）；复用上一批已经完成的天气 60 条和家居 43 条评分，未重评或修改这些结果。

合并结果：天气 40/60，家居 34/59，总体 74/119（62.2%）；完成率 99.2%。状态：incomplete。

补跑与旧结果按“场景＋样本 ID”关联，ID 无重合，轨迹、评分数量一一对应。沿用相同种子、提示词、完整 9 工具、preset、模型请求配置、评分模型和规则；汇总与分场景报告复用原后端函数。此前断连、502 和中止记录仍保留在原批次，合并后的完成状态不抹除历史故障。

本结果由 2026-10-10 与 2026-10-11 两次运行组成。天气沿用 10 月 10 日的在线查询与原评分；新增家居任务使用模拟器。用户报告已加长服务上下文，原请求 max_tokens=3000 未变。模型接口名仍为 xiaozhi-sft，无法单凭别名确认远端权重 revision。

原批次：/Users/yuxxie/Documents/GitHub/xiaozhi-esp32-server/main/xiaozhi-server/tmp/model-eval-runs/qwen35-9b-sft-r5-20261010-2117
补跑及合并完整结果：/Users/yuxxie/Documents/GitHub/xiaozhi-esp32-server/main/xiaozhi-server/tmp/model-eval-runs/qwen35-9b-sft-r5-continuation-20261011-0204

仍缺 T16-E001-P2：两次均触发工具返回记录缺失。诊断轨迹显示它在开灯并讲笑话任务中调用 play_music，工具执行记录存在，但 action=NONE 的调用未写入对话 messages，导致完整性检查失败。未把错误调用删除或修成正确答案；未修改后端代码或评分规则。T16-E001-P3 一次结构异常后重试成功，重试选择依据仅为轨迹有效性，并非评分高低。

逐文件来源、校验值和剩余任务见 continuation.json；新增评分见 continuation-scoring/ 和 retry-scoring/；完整失败证据保存在后端 retry-traces/。
