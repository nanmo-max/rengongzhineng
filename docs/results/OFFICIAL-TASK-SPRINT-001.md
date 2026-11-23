# OFFICIAL-TASK-SPRINT-001 三任务定向性能筛选

## 冻结候选

| 任务 | 父兼容Recipe | 相邻未见阶段结果 | 选择理由 |
|---|---|---|---|
| A Gas | `class_weighted_current_fast`（3 epoch，3×LR） | Macro-F1 9/9优于静态，平均+0.400626、最差+0.050331；Accuracy平均+0.300771、8/9正向 | 同时提高平均与最差阶段，CPU低 |
| B Bearing | `regression_asymmetric_current_stable`（4 epoch，2×LR，over=1.25） | RMSE/MAE/NASA均9/9正向；平均RMSE降低346.306378、MAE降低351.237526、NASA相对降低83.89%；最差RMSE仍降低75.955162 | 强收益且没有阶段崩溃 |
| C Engine | `averaged_current_stable`（5 epoch，父/候选90/10插值） | RMSE 8/9正向、平均降低0.948099、最差-0.032977；MAE 7/9正向、平均降低0.745146；NASA 8/9正向、平均相对降低20.42% | 相比高alpha牺牲少量均值换取稳定性 |

所有结果从官方初始checkpoint开始，使用既有合法十轮feedback的`t训练→t+1评价`；公开validation、confirmation、隐藏数据、官方试运行均为0。结果是开发代理证据，不是官方成绩。

## 淘汰项

SAM/L2-SP/AdamW无跨任务优势；B的5 epoch/3×LR虽均值高但存在最差阶段与NASA退化；C的高强度直接更新退化；0.15/0.20插值没有全面超过0.10稳定候选。

## 工程状态

三项Recipe已进入`brace_formal.recipes`注册表并保持`contest.cpu-mlp.v1`、父优化器状态、原特征与checkpoint格式。正式上下文现在携带任务合同的全部辅助指标和基于合法train内部证据的稳定配方先验；服务异常时同样退回该配方，而不是旧的弱`native_current`。ArtifactSelector、硬安全门和回滚不变。

## 真实27B提案门

`QWEN38-RECIPE-PROBE-001-A2`通过PyTRiO真实调用`Qwen/Qwen3.8-27B`，三个聚合证据场景分别选择上述A/B/C配方，输入/输出Token为722/779，三次采样墙钟合计22.246秒。A1因`max_tokens=None`被直接SDK拒绝，失败证据保留；A2本地探针使用官方示例的4096，正式`rnd.model()`仍不设置参赛者上限。证据为`results/QWEN38-RECIPE-PROBE-001-A2.json`。

## 三任务正式链复演

`FORMAL-STABLE-30R-001-A1`在4核4GB合同下完成A/B/C各10轮、每轮两次模型调用替身、真实候选训练、同作用域选择、父保留和历史回滚；三个任务始终执行对应稳定配方。机器报告SHA-256为`2BF06ED...594A21`，见`results/FORMAL-STABLE-30R-001-A1.json`及D盘HTML。该复演的模型响应是本地宿主替身；真实27B能力由上节独立三次远程收据证明，二者不得合并冒充30轮远程调用。
