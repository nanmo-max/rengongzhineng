# METHOD-PORTFOLIO-PILOT-001 结果

## 结论

在未读取本地confirmation或公开validation的条件下，多种成熟CPU方法在`t训练→t+1未见评价`上显示显著趋势；正式`contest.cpu-mlp.v1`续训也能获得大幅跨批改善。现有问题不是官方父MLP完全无能力，而是旧Harness候选空间、固定日程和同批Gate不能识别正确的训练范围与更新强度。

## 实验范围

- A/B/C各9个相邻转换；第t项只使用1…t已开放feedback训练，t+1只评价。
- A1比较静态、原生续训、线性、HGB、ExtraTrees和树集成；异构模型只作教师上界。
- A2比较17种正式MLP候选；A4比较9种候选在连续父checkpoint链上的真实累积行为。
- confirmation/public validation读取0次，PyTRiO/SwanLab/官方试运行使用0次。

## 关键结果

| 任务 | A1教师趋势 | A4最佳/稳健正式MLP连续策略 | 对静态平均有向收益 | 胜率 | 最坏收益 |
|---|---:|---|---:|---:|---:|
| A 分类 | 线性`+0.460588` Macro-F1；ExtraTrees`+0.439433` | `recent_e3` | `+0.386974` Macro-F1 | 9/9 | `+0.017072` |
| B 回归 | 树集成平均降低RMSE`393.014219` | `current_e3_lr3` | 降低RMSE`287.436213` | 9/9 | `+45.370270` |
| C 回归 | 异构树整体不稳 | `soup_current_e3_alpha0.25` | 降低RMSE`1.007474` | 6/9 | `-0.196010` |

跨任务低风险候选`25% current-e3 + 75% parent`在A对直接父模型9/9改善、B 8/9改善，C将最坏对静态退化限制为`0.196010 RMSE`。它适合作为首候选，但尚未通过完整SafetyGate/双候选Harness，因此不直接替换RC。

## 失败与边界

- A3在连续使用`3×`学习率时把倍率写入checkpoint并逐轮累乘，超过合法上限后停止。失败目录保留；A4仅修复为训练期临时倍率，并新增十轮不累乘测试。
- A1/A2是独立转换探针，不代表真实连续部署；只有A4提供连续父链证据。
- 这些是本地官方数据流代理结果，不是公开validation、官方隐藏测试或获奖成绩。
- 异构教师不得进入正式checkpoint；正式路线仍必须继承官方父权重、Adam、标准化、epoch和step。

## 产物

- A1：`D:/brace-msi-method-pilot/METHOD-PORTFOLIO-PILOT-001-A1/summary.json`，SHA-256 `9206683D0B1460DF0CA6CF5A543581DFECC5175CC4F478398E1462F0080FD2B3`。
- A2：`D:/brace-msi-method-pilot/METHOD-PORTFOLIO-PILOT-001-A2/summary.json`，SHA-256 `99BE29AC7FC5F413035D8F3E201E33AD8DEA34F8BA4641FB7390072CF53ED17C`。
- A3：失败证据目录`D:/brace-msi-method-pilot/METHOD-PORTFOLIO-PILOT-001-A3/`。
- A4：`D:/brace-msi-method-pilot/METHOD-PORTFOLIO-PILOT-001-A4/summary.json`，SHA-256 `A1DD7F21E71037D1DB72DC1DC0FD023F41D86EA5F8EB0AC9673E293F636B150A`。

## 下一步

执行`COMPETITIVE-POLICY-002`：首候选使用低风险插值，第二候选根据任务契约、当前漂移与既有延迟收益在最近窗口/累计/高步长更新中选择；继续保留下一批收益结算与负收益回滚。只有十轮Harness、完整回归和容器门通过后才产生新RC。
