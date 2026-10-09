# 天气与家居训练数据 v1

本目录定义离线数据准备规范，目标为 Qwen + Unsloth，训练路线为 SFT 后进行 DPO。尚未选定具体 Qwen checkpoint、思考模式和训练硬件，因此这里输出 `messages` / `tools` JSONL，而非已经分词的训练张量。原始生成器、轨迹和线上提示词不修改。

## 输入与评分选择

`sources.json` 中的路径相对于配置文件目录，不依赖执行命令的工作目录。

- 天气 300 条：选择 `scoring-real/scores.json`，278 条 pass、22 条 fail。暂不采用 `scoring-c03-relaxed-replay` 的 283 条 pass：该版本允许省略城市名中的“市”，而当前天气工具描述和目标提示词仍要求原样保留。未来若采用放宽规则，应同时修订工具契约、提示词、评分配置后重新导出。
- 家居 299 条：选择 `revised-current-rules/scores.json`，288 条 pass、11 条 fail。该版本重新计算程序项并复评受规则变更影响的语义项，适用于当前“相邻上一轮同设备状态可以复用”的规则。
- 家居评分报告带 conversations 文件哈希，导出前强制校验。天气旧报告没有此哈希，按样本身份、完整检查计划及原文证据核对；这不能替代历史文件的密码学绑定，manifest 中明确区分。
- 家居 tools 来自轨迹内的 `context.tool_definitions`。天气历史轨迹未保存 tools，导出器从当前 `get_weather.py` 的字面量读取定义，不导入插件、不执行工具，记录来源文件与哈希；不将其冒充历史快照。

## 统一输入规范

`system-prompt.txt` 固定统一身份、天气与家居的适用规则。每条输入追加当次记录的日期和时区；家居目录从原始 system 解析并与 `context.public_catalog` 比对，只保留身份、别名、房间、权限，不将设备初始状态塞入 system。

每条候选均暴露目标部署范围的三个工具：`get_weather`、`state_hub_snapshot`、`hass_set_state`。三个工具的参数契约保持来源定义；家居工具底层支持的调光等功能仍由 system 限制为即时开关。目录未提供或未授权时不能执行家居控制。

不把 seed 中的目标设备、期望动作、未来用户轮次、评分结果、隐藏状态、模拟故障计划加入模型输入。默认城市仍由天气后端会话配置决定，未指定城市时省略 location。日期与时区来自会话元数据，不伪称原模型当时看到过它们。

这是一版**目标部署规范及候选训练输入**。原评分只验证原轨迹；改写 system、增加上下文和扩展工具集合后仍需行为复评。导出器没有替换线上 `agent-base-prompt.txt`：线上角色、`<Q>`、emoji、上下文注入和工具集必须在部署接入时显式对齐。

## 导出

从仓库根目录执行以下相对路径命令；输出目录必须尚不存在，避免覆盖上一个版本：

```bash
python3 main/xiaozhi-server/text-client/prepare_training_data.py \
  --config main/xiaozhi-server/text-client/training-data/v1/sources.json \
  --output-dir main/xiaozhi-server/tmp/training-data/agent-sft-v1-20261008-final
```

| 文件 | 用途 |
|---|---|
| `sft.train.jsonl` | 全部已评分检查通过且结构合格的训练候选，混合天气与家居 |
| `sft.validation.jsonl` | 开发验证候选，不能加入 SFT 或 DPO 训练 |
| `sft.metadata.jsonl` | 每行对应的原始 ID、来源摘要、划分、目标哈希和 assistant 消息索引；不作为模型文本 |
| `dpo.review.train.jsonl` | 失败轨迹、失败证据与非法动作列表；尚未配对，不能直接传给 DPOTrainer |
| `dpo.review.validation.jsonl` | 验证侧失败案例；禁止拿去补训练 chosen |
| `quarantine.jsonl` | 待复核 ID 和原因；原始轨迹仍在来源文件 |
| `validation.source-trajectories.jsonl` | 验证侧原始环境、种子及轨迹，供复现评测；含隐藏评测信息，不能作为模型输入 |
| `audit.jsonl` | 每条输入的去向，包括重复、失败及隔离原因 |
| `manifest.json` | 文件哈希、来源、规则选择、数据统计、训练契约与限制 |
| `system-prompt.txt` / `tools.json` | 本次目标输入快照 |
| `report.md` | 人可读结果摘要 |

调用参数从 JSON 字符串转换为对象；删除流式调用的 `index`，将随机调用 ID 按出现顺序规范化，同时更新工具返回的关联 ID。用户、工具及助手的内容原文不修改，不伪造缺失结果或修正模型错误。全检查通过的样本才进入 SFT；这不是人工逐条语义审核的替代。

运行器插入的“达到工具次数限制”消息会改变后续模型行为。此版将相关整段轨迹隔离，既不把它当真实用户输入，也不删除后继续训练。非法工具名、参数等明确模型错误可以保留在 DPO 待复核队列，不能进入 SFT 正例。未配对的失败轨迹无需丢弃。

## 划分与留出

先对全部轨迹划分，再按质量筛选。相同 `scenario + template_id` 的样本永远同侧；完整用户消息序列相同的模板合并为同一组。稳定哈希控制组顺序，每场景目标约 20% 验证，实际比例受组大小影响。相同原始轨迹派生的 SFT、DPO 和后续修订必须继承相同划分。

这些历史案例已经用于开发、评分与规则修订，因此本次 validation 只叫**开发验证集**。曾被评分本身并不意味着不能留出；关键是不能参与训练或模型选择后又当作未见最终测试。这里不能追溯保证未参与开发，所以不创建名义上的独立 final test。最终测试应另行设计并在训练前锁定，模板和组合任务也应避免重叠。

## Qwen + Unsloth 接入要求

Qwen 官方提供 [Unsloth 微调指南](https://github.com/QwenLM/Qwen3/blob/main/docs/source/training/unsloth.md)，Unsloth 提供 [DPO 文档](https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide/preference-dpo-orpo-and-kto)。具体 API 以训练环境锁定的版本为准。

1. 选定准确的 checkpoint 和 tokenizer revision，固定是否启用 thinking。当前轨迹没有显式思维链，不凭空补写 `<think>` 内容。
2. 将 `messages` 和 `tools` 同时传入该 checkpoint 自带的工具聊天模板；检查参数对象被序列化为正确的工具调用，而非 Python 字典文本。训练与推理使用同一模板和思考模式。
3. 只给 assistant 的自然语言和工具调用目标计算损失；system、user、tool 返回以及模板包装部分按角色检查屏蔽。`sft.metadata.jsonl` 的 assistant 消息索引只是审计信息，不会自动成为 token labels。
4. 必须查看一次工具调用→返回→最终答复的实际 token labels。不能假设按“assistant 开始到下一个 user”为区间的通用屏蔽函数会正确排除中间 tool 返回。
5. 在选定 tokenizer 后计算真实长度分布。不要按字符数估算后截断工具链；此版不 packing、不自动截断。超长样本单列，再决定增加上下文或按完整决策边界拆分。
6. DPO 从 SFT 权重继续；对同一个 prompt 构造 chosen/rejected，保持 system、tools、当时历史一致。优先选单个 assistant 决策，工具返回留在 prompt。不要把两条用户文本相似但状态不同的完整轨迹直接拼成一对。
7. 数据适配器只读取 JSONL 的 `messages` / `tools`，不能将审计、评分或验证环境配置拼入 prompt。

## 补充数据与复评

`supplemental-cases.json` 是待生成与评测的任务清单，不是合成的训练答案。包含天气→家居、家居→天气、同轮两类请求、取消或更正、普通闲聊和无需工具。现有家居模板已有部分“控制＋文字请求”，仍不能证明两个工具领域的组合能力。

生成新样本时，两类工具需同时可见。家居使用可复位的模拟器，天气使用有明确来源、日期与故障状态的工具响应；每个候选从相同环境快照开始。完成真实调用轨迹生成与评分后，再补入下一版来源配置。不得把预期行为清单伪装成观察到的工具返回。

原始数据不覆盖。重跑使用新的输出目录；报告记录候选状态，直到统一输入行为评测和 Qwen token-mask 检查完成。
