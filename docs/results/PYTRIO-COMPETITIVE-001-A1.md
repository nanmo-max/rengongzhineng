# PYTRIO-COMPETITIVE-001-A1 结果

## 结论

一次性合规SFT达到了预注册成功门。A3持久化Sampler在新留出集上五项指标均为100%，并在A/B/C真实首轮状态下3/3主动提出可执行更新，不再依赖最低候选守卫。随后由Sampler决定训练或停止、确定性Harness应用冻结安全参数日程的三任务十轮运行全部机器复算有效。

该结果证明PyTRiO Agent能够提供合规的动作意图，但不证明大模型单独创造了工业模型性能增益。最终性能仍来自此前公开开发阶段冻结的任务参数和SafetyGate。公开验证已历史暴露，以下数值不是隐藏测试或官方成绩。

## A3合规SFT

- 运行目录：`D:/brace-msi-pytrio/PYTRIO-SFT-001-A3/`
- 基座：`Qwen/Qwen3.5-4B`，rank 8，3 epoch，batch 4，学习率`1e-4`
- 语料：48条训练、12条新留出；不含工业原始样本、任务名、凭据或隐藏数据
- 远程步骤：36/36；最终监督Token损失`0.017709274`
- 持久化Sampler：已生成，完整`trio://`路径仅保存在Git外收据中
- 基础模型留出：schema 83.33%，budget 66.67%，action/tool/policy各50%
- A3 Sampler留出：schema、budget、action、tool、policy均100%
- 真实首轮Smoke：A/B/C均主动提出`incremental_update`，3/3训练并通过SafetyGate

## 正式竞争候选十轮结果

运行目录：`D:/brace-msi-pytrio/PYTRIO-COMPETITIVE-001-A1/`。配置为`configs/formal_agent_competitive.json`，三任务各10轮、3个真实候选。

| 任务 | 初始指标 | 最终指标 | 接受候选 | CPU秒 | 峰值RSS | 输入/输出Token |
|---|---:|---:|---:|---:|---:|---:|
| A Gas Macro-F1 ↑ | 0.714030 | 0.725695 | 1/3 | 2.516 | 54,358,016 | 6,809 / 773 |
| B Bearing RMSE ↓ | 681.159833 | 637.180224 | 1/3 | 4.812 | 67,272,704 | 6,765 / 745 |
| C Engine RMSE ↓ | 52.868573 | 51.635999 | 2/3 | 33.750 | 258,281,472 | 6,788 / 754 |

三任务均为`valid=true`、10轮完成、3候选完成、0最低候选守卫覆盖、0模型服务回退。A第8轮和C第10轮各出现一次候选预算耗尽后的额外训练建议，执行沙箱均在训练前拒绝；没有越过预算或污染稳定模型。

## 证据边界与停止决定

- 官方试运行机会使用0次；未访问隐藏测试，未同步SwanLab。
- A/B/C原始训练包保持只读；候选均写入独立运行目录。
- A3通过了D-042允许的唯一一次合规SFT。此后停止LLM调参，不再扩大语料、epoch或搜索。
- 正式候选冻结为“A3 Sampler动作意图 + BRACE冻结参数日程 + ActionSandbox + SafetyGate”；模型服务失败仍回退确定性策略。
- 2次预算耗尽后建议是保留的负边界证据，正式报告不得省略。

## 复核命令

```powershell
$env:PYTHONPATH='src'
python -m brace_msi official-agent-run --config configs/formal_agent_competitive.json --package-root 'C:/Users/Administrator/Desktop/人工智能创新大赛/训练包' --runtime-root 'D:/brace-msi-pytrio/PYTRIO-COMPETITIVE-001-A1/A' --profile A --validate-only
```

B/C只替换`runtime-root`和`profile`。三项输出均为`valid=true`。
