# UNIFIED-POLICY-OPT-001 统一策略开发结果

## 结论

`UNIFIED-POLICY-OPT-001-DEV-A1`完成81/81个预注册作业并通过严格复算，但复杂BRACE策略触发了预注册停止条件：在3/3个任务级leave-one-task-out留出任务上，相对简单性能触发式策略没有性能优势且消耗更多训练资源。因此最终候选冻结为身份盲的`normalized_performance_triggered`简单策略；复杂配置`shared-f8881ba9c291`只保留为末期对照，不作为最终候选。

这是一项本地公开开发证据，不是平台隐藏测试、正式排名或官方成绩。官方试运行与正式评测机会使用数均为0。

## 执行与完整性

- 执行提交：`e057589521cff0f3d9c3141bd1a6fc0d7a28d914`
- 运行根：`D:/brace-msi-unified/UNIFIED-POLICY-OPT-001-DEV-A1/`
- 任务：Gas分类、Bearing RUL回归、Engine RUL回归
- 策略：静态、固定低成本、归一化性能触发、24组共享BRACE配置
- 作业：9个基线作业与72个BRACE作业，共81个
- 训练协议：MLP最多80次迭代；所有策略在同一任务共享初始检查点和阶段manifest
- 严格验收：`valid=true`，`job_count=81`，`fold_count=3`
- 执行manifest SHA-256：`47CEF397BF47902B7C3A82635D6F7CAA2A00CC98A101C72D42FEEC8BBCB9AE70`
- 汇总SHA-256：`92F12971C89EFCEF858A5BD0630666D5B62E36A31580E2DFA600CFD0EAB8BD58`
- 末期数据：未加载
- 官方测试机会：0

严格复算命令：

```powershell
D:\anaconda3\python.exe scripts/run_unified_policy_optimization.py --runtime-root D:\brace-msi-unified\UNIFIED-POLICY-OPT-001-DEV-A1 --validate-only
```

输出：

```json
{"fold_count": 3, "job_count": 81, "official_test_opportunities_used": 0, "valid": true, "winner": "shared-f8881ba9c291"}
```

## 任务级留出迁移

每一行的BRACE配置只由另外两个任务的中期开发结果选择，留出任务不参与该fold的选型。

| 留出任务 | 由另两任务选出的BRACE配置 | BRACE相对简单策略增益 | BRACE CPU秒 | 简单策略CPU秒 | 判定 |
| --- | --- | ---: | ---: | ---: | --- |
| Bearing | `shared-f8881ba9c291` | 0.000000 | 0.968750 | 0.000000 | 性能持平、资源更差 |
| Engine | `shared-d070dc826679` | -0.001265 | 33.843750 | 0.000000 | 性能与资源均更差 |
| Gas | `shared-a8d149515134` | -0.021493 | 16.640625 | 0.281250 | 性能与资源均更差 |

复杂BRACE至少在两个留出fold被简单策略同时以性能和资源支配；实际为3/3个fold无优势。该结果满足设计文档第8节的停止条件，禁止为了包装继续增加复杂机制。

## 全部中期证据的排序结果

预注册稳健排序在24组复杂配置中给出`shared-f8881ba9c291`作为复杂对照最优项。其全中期任务结果如下：

| 任务 | 静态指标 | 简单触发指标 | 复杂对照指标 | 复杂对照CPU秒 | 简单CPU秒 | 复杂对照训练样本 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Bearing RMSE↓ | 419.026853 | 419.026853 | 419.026853 | 0.968750 | 0.000000 | 2,862 |
| Engine RMSE↓ | 22.067446 | 22.069018 | 22.067446 | 26.781250 | 0.000000 | 65,149 |
| Gas Macro-F1↑ | 0.668681 | 0.680370 | 0.733215 | 28.031250 | 0.281250 | 34,542 |

复杂对照的提升主要来自Gas，在Bearing无收益，在Engine仅回到静态水平；这同时触发“提升只来自单个任务”的停止理由。全中期排序结果不能覆盖任务级留出迁移失败。

## 冻结候选

- 最终候选：`normalized_performance_triggered`
- 共享退化阈值：`0.0`
- 输入：方向归一化的相对性能退化，不含数据集名称、任务ID、Profile、路径或批次名称
- 动作：达到阈值时只尝试一次低成本增量更新；仍经过预算检查、候选评估和SafetyGate
- 冻结记录：`configs/unified_policy_frozen.json`
- 复杂BRACE对照：`shared-f8881ba9c291`，只允许按冻结参数参加一次末期对照，不得再调参

## 末期边界

冻结后才允许运行一次prediction-only末期评估。Gas批次8—10与FD001发动机81—100必须标记`historically_exposed_terminal`；只有此前未生成特征、未训练、未查看指标的XJTU三个密封轴承可在锁校验通过后标记`virgin_terminal`。末期结果不得反馈修改阈值、动作或配置。
