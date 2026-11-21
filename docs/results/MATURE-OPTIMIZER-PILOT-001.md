# MATURE-OPTIMIZER-PILOT-001 成熟优化器探针结果

## 结论

`MATURE-OPTIMIZER-PILOT-001-A1` 已按预注册范围完成。L2-SP、SAM-Adam 和 AdamW 均未同时满足“跨任务平均正向、最差阶段不劣、成本可接受”的晋级条件，因此不接入正式镜像，不替换冻结的 `0.11.0rc1`。

本结果是 A/B/C 官方训练包内部前三个序贯阶段的低成本趋势证据，不是公开验证、隐藏测试或官方成绩。

## 方法与边界

- 对照：`native_current`、`native_replay`。
- L2-SP：`lambda={1e-4,1e-3}`。
- SAM-Adam：`rho={0.01,0.05}`。
- AdamW：`weight_decay={1e-5,1e-4}`。
- 新机制均从真实父 checkpoint 续接；默认 Adam 路径保持向后兼容。
- 仅使用 `public/train.jsonl` 内部冻结流；`public/validation.jsonl`、密封集和隐藏数据读取 0 次。
- PyTRiO、SwanLab、Docker、平台上传和官方试运行均为 0。

## 跨任务结果

有向收益统一为“越大越好”；分类为 Macro-F1 增益，回归为 RMSE 降低量的归一化方向量。

| 方法 | 三任务平均有向收益 | 最差阶段 | 改善任务数 | 退化任务数 | CPU 秒 |
|---|---:|---:|---:|---:|---:|
| native_current | -0.180406 | -0.682380 | 1 | 1 | 0.344 |
| native_replay | -0.149303 | -0.677916 | 0 | 2 | 0.812 |
| l2sp_1e-4 | -0.180400 | -0.682361 | 1 | 1 | 0.344 |
| l2sp_1e-3 | -0.180351 | -0.682190 | 1 | 1 | 0.359 |
| sam_0.01 | -0.207395 | -0.706925 | 0 | 2 | 0.484 |
| sam_0.05 | -0.167768 | -0.562417 | 0 | 2 | 0.562 |
| adamw_1e-5 | -0.180406 | -0.682381 | 1 | 1 | 0.484 |
| adamw_1e-4 | -0.180408 | -0.682391 | 1 | 1 | 0.375 |

Pareto 集合为 `l2sp_1e-3 / l2sp_1e-4 / native_replay / sam_0.05`，但所有方法的跨任务平均收益均为负；Pareto 成员不等于可晋级方法。

## 分任务观察

- A：全部方法前三阶段平均和最差有向收益均为 0，短阶段 Macro-F1 对参数扰动没有可用分辨率，不能据此宣称等价或有效。
- B：全部候选平均收益为负；`native_replay` 和 `sam_0.05` 只缓和退化，没有转为正向。该任务是本轮明确停止信号。
- C：`native_current`、L2-SP 和 AdamW 均有约 `+0.04132` 平均有向收益并连续选择 3 次；SAM 和 Replay 反而退化。L2-SP/AdamW 没有在现有精度下显示出超越原生 Adam 的额外价值。

## 工程验证

- 新增优化器路径通过参数验证、checkpoint schema、保存加载、非有限值和默认路径兼容测试。
- 实验运行器支持恢复、manifest 冲突失败关闭、逐候选资源记录和 confirmation 读取计数。
- 专项测试：15 项通过。
- 完整回归：644 项通过。

## 可核验证据

- 机器摘要：`D:/brace-msi-competition/MATURE-OPTIMIZER-PILOT-001-A1/summary.json`
- 摘要 SHA-256：`49BFF56946899E48D713E4491405867516F4AAE96EF9371048604748E6087B02`
- 运行规模：3 个任务、24 个方法臂、72 个候选阶段；`confirmation_reads=0`。
- Smoke 摘要：`D:/brace-msi-competition/MATURE-OPTIMIZER-PILOT-001-SMOKE/summary.json`
- Smoke SHA-256：`BF1D8B02E9E0D561E110F2973CF6D336691448F2483CE01DDDAC30B662B847B4`

## 决策

保留研究实现与负结果以供复现，不注册到正式 `RecipeRegistry`，不构建新镜像，不打开 confirmation，不扩大搜索。下一正式动作仍是等待平台授权的 `FORMAL-RELEASE-001`。
