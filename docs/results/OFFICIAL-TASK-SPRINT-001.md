# OFFICIAL-TASK-SPRINT-001 三任务定向性能筛选

## 冻结候选

| 任务 | 父兼容Recipe | 相邻未见阶段结果 | 选择理由 |
|---|---|---|---|
| A Gas | `class_weighted_current_fast`（3 epoch，3×LR） | 9/9优于静态，平均Macro-F1有向收益+0.400626 | 同时提高平均与最差阶段，CPU低 |
| B Bearing | `regression_asymmetric_current_stable`（4 epoch，2×LR，over=1.25） | 9/9优于静态，平均RMSE降低346.306378，最差仍降低75.955162，NASA改善61.42% | 强收益且没有阶段崩溃 |
| C Engine | `averaged_current_stable`（5 epoch，父/候选90/10插值） | 8/9优于静态，最差约-0.03 RMSE，NASA改善33.22% | 相比高alpha牺牲少量均值换取稳定性 |

所有结果从官方初始checkpoint开始，使用既有合法十轮feedback的`t训练→t+1评价`；公开validation、confirmation、隐藏数据、官方试运行均为0。结果是开发代理证据，不是官方成绩。

## 淘汰项

SAM/L2-SP/AdamW无跨任务优势；B的5 epoch/3×LR虽均值高但存在最差阶段与NASA退化；C的高强度直接更新退化；0.15/0.20插值没有全面超过0.10稳定候选。

## 工程状态

三项Recipe已进入`brace_formal.recipes`注册表并保持`contest.cpu-mlp.v1`、父优化器状态、原特征与checkpoint格式。Qwen仍负责在白名单Recipe中提出实验；ArtifactSelector、硬安全门和回滚不变。下一门为真实Qwen3.8-27B提案收据及三任务十轮正式Harness复演。
