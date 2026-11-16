# DELAYED-GAIN-SIM-001 结果

## 结论

本任务完成了用户指定的序贯适应语义：第 `t` 批先由稳定模型预测并封存，标签开放后计算 `arrival_metric_t` 并进入决策；候选只用本轮 Update 训练、Gate 部署；上一轮部署动作只在第 `t+1` 批通过当前模型与直接前任在同样本上的配对差结算。

协议门全部通过，但性能结论为混合：A、C没有安全候选获准部署；B在A2中暴露“负延迟收益后不能回滚”的真实缺口，A3加入直接前任回滚后避免了灾难性最终模型。该结果是本地代理流程，不是官方隐藏成绩。

## 实验链

| 实验 | 用途 | 结果 |
|---|---|---|
| `DELAYED-GAIN-SIM-001-SMOKE-A1` | 低成本生命周期Smoke | 三任务各10轮，候选各1个，均拒绝，父模型保持 |
| `DELAYED-GAIN-SIM-001-A2` | 完整十轮确定性序贯运行 | A/C保持父模型；B第9轮部署后第10轮延迟收益为负，但旧状态机未回滚，最终RMSE退化至993.202677 |
| `DELAYED-GAIN-SIM-001-A3` | 直接前任回滚修复后的完整运行 | B第10轮执行`rollback`恢复直接前任；A/C负结果保持 |

全部产物位于`D:/brace-msi-delayed-gain/`，历史目录未覆盖。

## A3逐任务摘要

| 任务 | 候选训练 | 候选采用 | 回滚 | CPU秒 | 峰值RSS | 第5次暴露本地确认 |
|---|---:|---:|---:|---:|---:|---|
| A Gas | 7 | 0 | 0 | 6.718750 | 207.03 MiB | Accuracy 0.414722；Macro-F1 0.380649 |
| B Bearing | 3 | 1 | 1 | 1.390625 | 204.42 MiB | MAE 175.586934；RMSE 241.980799 |
| C Engine | 6 | 0 | 0 | 6.406250 | 494.07 MiB | MAE 36.699396；RMSE 48.691951；NASA mean 35312.040688 |

B的关键事务：第9轮`replay_refit`通过Gate并部署；第10轮在新到数据上与直接前任配对，RMSE方向收益为`-310.293697`，随后执行`rollback`，输出checkpoint哈希等于直接前任哈希。A2失败结果没有删除或改写。

## 数据与证据边界

- Gas：父模型未见自然批次构流，Batch 10只作本地确认。
- Bearing：按轴承内严格时间顺序构造十段；这是代理假设，不是官方确认的十轮切法。
- Engine：按完整unit构流，同一unit不跨流与确认边界。
- 逐轮到达指标进入策略；Gate仅决定候选安全；确认集只在十轮冻结后读取一次。
- 当前确认已经是历史第5次暴露，只能作描述和回归诊断，不能再用于调参或声称独立泛化。
- 正式隐藏测试状态为`not_started_not_available`；本任务没有消耗官方试运行。
- A3使用确定性策略，Token为0；PyTRiO在线路径沿用独立的`PYTRIO-ONLINE-001`证据，本任务未为接口证明重复消费余额。

## SwanLab与报告

A3只生成本地离线聚合记录，未同步公网：

- A：`D:/brace-msi-delayed-gain/DELAYED-GAIN-SIM-001-A3/A/swanlab/run-20261116_100707-7a1ir5oz`
- B：`D:/brace-msi-delayed-gain/DELAYED-GAIN-SIM-001-A3/B/swanlab/run-20261116_100710-h4gjwe1t`
- C：`D:/brace-msi-delayed-gain/DELAYED-GAIN-SIM-001-A3/C/swanlab/run-20261116_100719-ihg507uk`

易读报告：

- `D:/brace-msi-delayed-gain/DELAYED-GAIN-SIM-001-A3/report/official-flow-report.html`
- `D:/brace-msi-delayed-gain/DELAYED-GAIN-SIM-001-A3/report/official-flow-report.json`

SHA-256：

- suite summary：`2DF637EA6D862792B7DAE8264EF1F3D5E56E837C360E1ADA9B14A9FE42D046A3`
- report JSON：`92F2B395BE4C89A492523ADC5ED8911070228C3E951D0F066624ADED57BDF52B`
- report HTML：`7B625B00C88C3A769A0936EAEF1360C341F15DDFF5CCDDD13D0D8726B668C937`

## 验证

- 序贯生命周期、Runtime和报告专项：`59 passed in 27.33s`
- 完整回归：`407 passed in 146.63s`
- `python -m compileall -q src scripts`：通过
- `git diff --check`：通过
- 机器不变量：三任务10轮、父链有效、确认各1次、配对样本一致、延迟收益只在部署下一批出现、负收益触发回滚、隐藏测试未开始：通过
- 仓库`trio_aq...`模式密钥扫描：0文件
