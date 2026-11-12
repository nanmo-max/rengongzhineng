# FORMAL-AGENT-SMOKE-001 结果

## 结论

受控Agent Harness已用同一CLI入口分别驱动A/B/C官方原版NumPy训练器完成一个真实1-epoch候选。三个候选均从官方初始检查点继续训练、通过独立收据和严格公开验证改善门控并被接受；机器复算3/3为`valid=true`。

本实验仅验证正式主链路，不用于算法选型。提供者为确定性降级策略，PyTRiO调用、Token和官方试运行次数均为0。指标来自已经反复使用的公开验证集，不是隐藏评测、排行榜成绩或新独立性能证据。

## 冻结输入

- 代码提交：`24c70c8`
- 配置：`configs/formal_agent_dev.json`
- 官方训练包：`C:/Users/Administrator/Desktop/人工智能创新大赛/训练包`（只读）
- 运行根：`D:/brace-msi-formal-agent/FORMAL-AGENT-SMOKE-001/`
- 每任务运行：第1/10轮，最多1个候选，确定性提供者
- 官方平台试运行：0

## 结果

| Profile | 任务/指标 | 初始指标 | 候选后指标 | CPU秒 | 墙钟秒 | 峰值RSS | 门控 |
|---|---|---:|---:|---:|---:|---:|---|
| A | Gas Macro-F1↑ | 0.714030 | 0.725695 | 0.750 | 0.875 | 53,108,736 | 接受 |
| B | Bearing RMSE↓ | 681.159833 | 657.645417 | 1.484 | 1.609 | 67,694,592 | 接受 |
| C | Engine RMSE↓ | 52.868573 | 52.350178 | 10.516 | 10.860 | 254,820,352 | 接受 |

三个任务合计CPU 12.75秒、墙钟13.344秒；每任务1个候选、1次接受；Token为0。结果复现了既有低成本续训方向，不应作为新的独立泛化结论。

## 安全与完整性

- 启动前重新审计三套包的目录树、训练/验证和初始检查点SHA-256；均与冻结配置相符。
- 原始包未写入；候选只写入独立运行根。
- 每个候选收据的父SHA、子检查点SHA、模型/优化器状态变化、指标、CPU/墙钟/RSS均重新打开验证。
- 状态、`audit.jsonl`、候选收据和接受链一致；机器验证重新计算部署门控。
- PyTRiO服务未调用，模型路径和凭据未使用或记录。

验证命令示例：

```powershell
$env:PYTHONPATH='src'
D:\anaconda3\python.exe -m brace_msi official-agent-run --config configs/formal_agent_dev.json --package-root 'C:\Users\Administrator\Desktop\人工智能创新大赛\训练包' --runtime-root 'D:\brace-msi-formal-agent\FORMAL-AGENT-SMOKE-001\A' --profile A --validate-only
```

## 边界与下一步

- `official_package=true`，`official_scoring_ready=false`。
- 此运行没有证明PyTRiO带来增益，也没有形成十轮完成证据。
- 下一步先完成执行侧工具/参数白名单，再为每个任务建立新的内部开发/确认协议；不得继续用本Smoke的公开验证结果调参。
