# REPORT-EVIDENCE-FIX-001 报告验证选择污染修正

## 结论

旧V1报告没有发现训练样本、特征或设备组直接进入公开validation的证据，但它对十轮稳定checkpoint重复读取同一份公开validation，并用该结果选择“最佳轮次”，属于验证集选择污染。旧报告降级为界面/协议演示。

V2已改为：逐轮只展示当前批次Gate上的稳定模型和候选模型指标及Harness真实部署决定；十轮策略冻结后，只对最终`round-10/checkpoint.npz`读取一次公开validation。公开validation不再参与选轮次。

## 机器约束

- A/B/C各10轮，共30轮Gate记录。
- 每任务`public_validation_evaluations=1`，总计3次。
- 逐轮记录没有`public_validation_metrics`。
- 任务记录没有`selected_round`或`selected_metrics`。
- 最终稳定模型来源由Harness部署链决定：A第9轮、B第1轮、C第9轮。
- 未重训、未修改checkpoint、未调用PyTRiO/SwanLab、未消耗官方试运行。

## 冻结后单次描述性指标

| 任务 | 公开validation读取 | 最终稳定来源 | 冻结后指标 |
| --- | ---: | --- | --- |
| A · Gas | 1 | 第9轮部署 | Accuracy 0.885852；Macro-F1 0.725695 |
| B · Bearing | 1 | 第1轮部署 | MAE 538.776700；RMSE 660.076488 |
| C · Engine | 1 | 第9轮部署 | MAE 38.091484；RMSE 51.949287；NASA 4,026,364,609.895953 |

这些validation历史已暴露，因此仍不能作为独立测试或官方隐藏成绩。

## 产物

- V2机器报告：`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM-V2-A2/report.json`
- V2基础HTML：`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM-V2-A2/report.html`
- 官方要素HTML：`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM-V2-A2/platform-style/platform-style-report.html`
- 官方要素JSON：`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM-V2-A2/platform-style/platform-style-report.json`
- 预览：`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM-V2-A2/platform-style/platform-style-report-preview.png`

SHA-256：

- `report.json`: `9008C9582571908387E5D79B7C71DC15713B8B22B48D0AB4568E7264254B00E5`
- `report.html`: `43DDD3E29B6AE8BA65BF2028EF6D4422139E73083D6EEFD76D81FC9F61F74F7B`
- `platform-style-report.json`: `605B651780F1D8C77872CD708DE9CD2686FD8BC212CEFA591CF1939ECF9182B6`
- `platform-style-report.html`: `E2EC4A538F0608BD63129A2F0F48619F45922F9673548B0C98580D25ED5FDA83`
- `platform-style-report-preview-v2.png`: `BA395D05BD3AFB462123B3AA1B137640F98C85DC244CE47179EFD7359E9613E1`

## 验证

- 新增红绿测试验证每任务只评估最终checkpoint一次、无validation轮次选择、无部署时保持初始父模型来源。
- 报告渲染测试验证Gate稳定/候选指标同时展示、V1污染提示和V2证据边界。
- 页面已完成1440×1800视觉检查，摘要、证据边界、Gate双指标和逐轮记录可读。
- 专项测试：`7 passed in 0.81s`。
- 最终HEAD完整回归：`390 passed in 151.76s`。
