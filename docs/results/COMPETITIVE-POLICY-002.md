# COMPETITIVE-POLICY-002 结果

## 结论

`COMPETITIVE-POLICY-002`完成。未读取已暴露确认集或公开 validation，未消耗官方试运行；A/B/C均在十轮顺序代理流中由正式`brace_msi.platform_runtime.start_round`完成父检查点继承、候选训练、门控、下一批收益结算和必要回滚。

| 任务 | 相对静态平均有向收益 | 最差轮收益 | 候选/部署/回滚 | 最终checkpoint |
|---|---:|---:|---:|---:|
| A 分类 | Macro-F1 `+0.319620` | `-0.026616` | `9 / 9 / 0` | 132,184 B |
| B 回归 | RMSE降低 `21.850812` | `0.000000` | `9 / 5 / 0` | 36,600 B |
| C 回归 | RMSE降低 `0.438766` | `-0.063751` | `9 / 6 / 0` | 28,848 B |

这些数值是训练流上的本地prequential代理证据，不是公开validation、独立确认或官方隐藏成绩。最终A6摘要：`D:/brace-msi-competitive-policy/COMPETITIVE-POLICY-002-A6/summary.json`，SHA-256 `680C9AFF813180DB0EE1D79F8287A78E0EF8C3FFF0CF84977AA7365D710C9E77`。

## 候选筛选

- A1证明低风险组合在三任务平均收益均为正，但B收益较小。
- A2只在至少4批、高线性趋势置信度和足够归一化斜率同时成立时启用高步长当前批更新；B平均RMSE收益提高到`40.869286`，三任务仍为正。
- A3尝试更早触发和连续激进更新，B平均收益降至`-92.775049`、最差`-979.518301`；该失败完整保留并淘汰。
- A4恢复A2成熟趋势门并接入正式运行时；最终自审发现Gate标签进入趋势均值，A5修正隔离但因报告ID硬编码而判无效；A6只用Update目标形成趋势，三任务仍保持正收益。

最终策略不读取数据集名称：保守父权重插值为默认recipe；分类有充分历史时选择最近窗口；回归只在成熟单调趋势时提高当前批步长，否则使用保守累计回放。PyTRiO只能表达受限训练/retain意图，不能覆盖recipe、预算、Gate或回滚；两次远程失败后显式retain。

## 发布候选

- 代码提交：`2ba965b5e277c22368f1533e5f66a55432ea3c8b`。
- 版本：`BRACE-MSI-0.8.0rc1`。
- 回归：`421 passed in 141.63s`；Gate隔离与报告ID专项`5 passed`；compileall、`pip check`及`git diff --check`通过。
- 容器：linux/amd64，UID 10001，4核8GB、只读根、断网；A/B/C各完成真实父checkpoint入口Smoke。
- PyTRiO：镜像默认`Qwen/Qwen3.5-4B` PyTRiO，SDK版本0.2.9；新镜像断网时2次失败后retain且Token为0，不静默训练。在线非零Token能力沿用未改动的既有适配器证据，平台凭据注入仍需正式环境确认。
- SwanLab：镜像含SwanLab 0.10.4和已有聚合记录接口；本次研究运行未同步公网，避免把代理流写成正式工程训练记录。
- 上传归档：`D:/brace-msi-competitive-policy/BRACE-MSI-0.8.0rc1-final/brace-msi-0.8.0rc1-harness.tar`，249,024,512 B，SHA-256 `CB9F28D16D88EA985598E9E7A5C1ECC2EC36A1CFC15740854E7F977FC232E6EA`，由`docker save`生成并经`docker load`验证。旧同名候选目录保留为Gate隔离修正前历史，不得上传。

## 边界

- confirmation/public validation读取0；官方试运行新增0。
- 不能把代理prequential收益解释为官方分数或隐藏泛化保证。
- 0.7.1rc1及全部历史正负证据保留；0.8.0rc1只在新分支形成，不移动旧标签、不合并main。
- 平台镜像导入、真实挂载生命周期、在线Token计量及正式SwanLab要求仍是外部验收项。
