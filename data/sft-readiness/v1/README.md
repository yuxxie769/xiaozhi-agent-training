# SFT 下一步诊断

**示范审查与四轮开发诊断已完成执行：159/160 条完成评分，86 条通过。40 题中，7 题四次全过、26 题时对时错、6 题四次全错、1 题缺评分。**

[本次结果与下一步建议](runs/sft-diagnostic-20261012-144933/report.md)。可以进入 DPO 候选复核，尚未开始 DPO 训练。

- [审查报告](training-audit/report.md)：556 条全部检查，1,982 项程序规则无失败。抽查 24 条，发现 1 条明确表述错误、2 条待复核措辞、2 条精简建议。
- [开发任务](development/report.md)：天气 16、家居 24；不进入当前训练集，也不替换原正式测试题。
- 四次重复诊断复用原后端生成、工具执行和评分；固定同一份提示词、9 个工具和设备快照。模型与评分模型配置仍由后端原配置读取，非思考参数也沿用该配置。

当前只做离线检查：

```bash
python3 -B scripts/run_sft_diagnostics.py
```

模型服务恢复且确认加载目标 SFT 版本后，再运行下面这一条。`--run-id` 每次使用新值；将 `--model-version` 改为实际部署标记。密钥从既有环境变量读取，不写入脚本。

```bash
python3 -B scripts/run_sft_diagnostics.py --execute \
  --server-dir ../xiaozhi-esp32-server/main/xiaozhi-server \
  --server-python /Users/yuxxie/Documents/tools/anaconda3/envs/xiaozhi-esp32-server/bin/python \
  --eval-config ../xiaozhi-esp32-server/main/xiaozhi-server/text-client/evaluation.formal.local.json \
  --model-version xiaozhi-sft-实际版本 \
  --run-id sft-diagnostic-001
```

完整轨迹留在后端 `tmp/model-eval-runs/sft-diagnostic-001-r1` 至 `-r4`。报告返回本目录 `runs/sft-diagnostic-001/`。生成或评分出错时保留有效结果并停止后续轮次，不自动重抽到通过。旧批次不覆盖。

看汇总中的四类：**4/4 通过、1～3/4 通过、0/4 通过、未完成**。只有四次都完成评分才能归入前三类；未评分不算模型答错。在线天气可能变化，比较时仍要看工具返回和失败证据。

**何时考虑 DPO：** 对混合通过的任务，确认正确答案确实正确、错误答案确实错误，并能在同一输入及工具上下文下比较，才进入偏好对准备。对持续失败的任务，先查示范质量、训练是否生效及工具调用能力。四次重复只是小样本诊断，不设一个通过率就自动开始 DPO。

离线准备阶段没有修改训练数据、原测试种子或既有评分，没有新增 DPO 配对，也未启动训练。15 项新增离线测试覆盖排重、复现、输入保真、设备引用、默认不请求模型、四次汇总、部分失败及旧目录保护；测试中的执行结果均为替身。

连同复用的种子生成与后端入口测试，本次共 35 项相关测试通过；审查重跑记录按字节一致，训练版本文件校验值保持不变。验证记录见 `validation.json`。
