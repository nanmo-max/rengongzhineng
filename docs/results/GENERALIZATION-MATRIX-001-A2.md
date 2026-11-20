# GENERALIZATION-MATRIX-001-A2 十轮本地矩阵

## 结论

执行链完整，但四种策略均未通过性能晋级门。A2不得进入正式镜像。

| 策略 | A平均有向收益 | B平均有向收益 | C平均有向收益 | 灾难任务数 |
|---|---:|---:|---:|---:|
| strict_parent_gate | +0.313085 | -10.860323 | +0.128450 | 1 |
| bounded_exploration | +0.312990 | -32.487069 | +0.173614 | 1 |
| conditional_champion | +0.313085 | -10.860323 | +0.147862 | 1 |
| recipe_feedback | +0.313085 | +29.449707 | +0.524004 | 1 |

B的最差相对退化在四策略下均超过预注册的5%门。recipe反馈虽然提高平均值，但最差阶段退化`-109.33%`，不能以平均收益掩盖。

## 证据边界

- A/B/C各10轮，每轮至少一个真实原生MLP候选。
- confirmation/public validation读取0；PyTRiO远程、SwanLab、Docker、官方试运行均为0。
- 代理流不是官方隐藏生命周期；结果只用于本地淘汰策略。
- `summary.json`的`valid=true`是技术执行完整，不是晋级通过；后续runner已增加独立`promotion_pass`。

## 产物

- `D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A2/summary.json`
- SHA-256：`517AA24C2064A1231A13D06A27CDD7458E50262CE671BB52C070DDEB8C138223`
