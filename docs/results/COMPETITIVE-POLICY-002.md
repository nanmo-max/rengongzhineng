# COMPETITIVE-POLICY-002 结果

## 结论

`COMPETITIVE-POLICY-002`完成。未读取已暴露确认集或公开 validation，未消耗官方试运行；A/B/C均在十轮顺序代理流中由正式`brace_msi.platform_runtime.start_round`完成父检查点继承、候选训练、门控、下一批收益结算和必要回滚。

| 任务 | 相对静态平均有向收益 | 最差轮收益 | 候选/部署/回滚 | 最终checkpoint |
|---|---:|---:|---:|---:|
| A 分类 | Macro-F1 `+0.319620` | `-0.026616` | `9 / 9 / 0` | 132,184 B |
| B 回归 | RMSE降低 `61.352748` | `-75.227645` | `8 / 8 / 2` | 36,600 B |
| C 回归 | RMSE降低 `0.438766` | `-0.063751` | `9 / 6 / 0` | 28,848 B |

这些数值是训练流上的本地prequential代理证据，不是公开validation、独立确认或官方隐藏成绩。A4摘要：`D:/brace-msi-competitive-policy/COMPETITIVE-POLICY-002-A4/summary.json`，SHA-256 `A60A3645C26A6BB6BF17396DDA90725EB4C3E83289FBD03177D1A4B6BE344317`。

## 候选筛选

- A1证明低风险组合在三任务平均收益均为正，但B收益较小。
- A2只在至少4批、高线性趋势置信度和足够归一化斜率同时成立时启用高步长当前批更新；B平均RMSE收益提高到`40.869286`，三任务仍为正。
- A3尝试更早触发和连续激进更新，B平均收益降至`-92.775049`、最差`-979.518301`；该失败完整保留并淘汰。
- A4恢复A2成熟趋势门并接入正式运行时；B的负延迟收益触发2次直接前任回滚。

最终策略不读取数据集名称：保守父权重插值为默认recipe；分类有充分历史时选择最近窗口；回归只在成熟单调趋势时提高当前批步长，否则使用保守累计回放。PyTRiO只能表达受限训练/retain意图，不能覆盖recipe、预算、Gate或回滚；两次远程失败后显式retain。

## 发布候选

- 代码提交：`851a8ad686bca69f13f237d2b4d17a340c6b1763`。
- 版本：`BRACE-MSI-0.8.0rc1`。
- 回归：`419 passed in 142.99s`；专项`53 passed in 25.63s`；compileall、`pip check`及`git diff --check`通过。
- 容器：linux/amd64，UID 10001，4核8GB、只读根、断网；A/B/C各完成真实父checkpoint入口Smoke。
- PyTRiO：镜像默认`Qwen/Qwen3.5-4B` PyTRiO，SDK版本0.2.9；新镜像断网时2次失败后retain且Token为0，不静默训练。在线非零Token能力沿用未改动的既有适配器证据，平台凭据注入仍需正式环境确认。
- SwanLab：镜像含SwanLab 0.10.4和已有聚合记录接口；本次研究运行未同步公网，避免把代理流写成正式工程训练记录。
- 上传归档：`D:/brace-msi-competitive-policy/BRACE-MSI-0.8.0rc1/brace-msi-0.8.0rc1-harness.tar`，249,024,512 B，SHA-256 `5539632515096B48113098B2E59BBC5CDA943A31DF3B358E26DD32280D438723`，由`docker save`生成并经`docker load`验证。

## 边界

- confirmation/public validation读取0；官方试运行新增0。
- 不能把代理prequential收益解释为官方分数或隐藏泛化保证。
- 0.7.1rc1及全部历史正负证据保留；0.8.0rc1只在新分支形成，不移动旧标签、不合并main。
- 平台镜像导入、真实挂载生命周期、在线Token计量及正式SwanLab要求仍是外部验收项。
