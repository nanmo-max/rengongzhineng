# OFFICIAL-DATA-REPORT-001 结果

> **2026-11-15证据更正：** 本文件转换自存在validation选择污染的V1机器报告，因此只能保留为页面样式演示。下方“最终采用”不能作为独立模型选择或泛化证据。修正版见`REPORT-EVIDENCE-FIX-001.md`。

## 结论

已将既有Gas、Bearing、Engine冻结十轮机器报告转换为便于查看的官方要素风格HTML和机器JSON。该任务只做格式转换，没有重新训练、重新读取公开validation、调用PyTRiO、同步SwanLab或消耗官方试运行。

## 产物

- HTML：`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM/platform-style/platform-style-report.html`
- JSON：`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM/platform-style/platform-style-report.json`
- HTML SHA-256：`A15445AB633A32B3A4505A2ABCB9623C67E5D5EC944F1214FAC69526390BEDEA`
- JSON SHA-256：`AB64E5A7F8F92DFA675928871A848DFDA5449563CF24CC3CF3F0A22C80B40ED1`

## 结果摘要

| 任务 | 完成轮次 | 最终采用 | 公开验证样本 | 冻结结果 |
| --- | ---: | --- | ---: | --- |
| A · 气体传感器漂移分类 | 10/10 | 第9轮模型 | 1,244 | Accuracy 0.885852；Macro-F1 0.725695 |
| B · 轴承寿命回归 | 10/10 | 第1轮模型 | 1,679 | MAE 538.776700；RMSE 660.076488 |
| C · 发动机寿命预测 | 10/10 | 第9轮模型 | 23,049 | MAE 38.091484；RMSE 51.949287；NASA 4,026,364,609.895953 |

## 验证

- 三任务均为10轮，共30个可展开实验记录。
- 页面包含完成轮次、最终采用模型、公开验证样本、CPU/运行时间、最终指标、逐轮指标、模型选择、动作、Token与资源。
- 历史机器报告未记录的结构化假设、门控原因、epoch、学习率和训练样本量统一显示“未记录”，没有猜测补全。
- `evidence_boundary=historically_exposed_public_validation_not_official_hidden_test`，页面显著说明不是官方隐藏测试或官方评分。
- 敏感标记扫描未发现API Key。
- 生成器专项测试：`4 passed`。
- 当前HEAD完整回归：`387 passed in 156.61s`。

## 证据边界

这些数值来自已反复暴露的官方公开validation及冻结checkpoint，只能用于本地复演和展示检查。它们不是新的独立测试结果，也不能冒充官方隐藏成绩。
