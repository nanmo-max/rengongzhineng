# UNSEEN-REPORT-001 官方要素风格本地模拟报告

## 结果

已从冻结的`UNSEEN-SIM-001-A4/report.json`生成一份易读的单页HTML与对应机器JSON。生成过程没有重新训练、打开数据、调用PyTRiO、同步SwanLab或消耗官方试运行。

页面包含截图中的主要信息层次：

- 完成轮次、最终采用模型、确认集样本数、CPU用时和运行时间；
- 最终确认指标；
- 十轮公开适应流指标与模型选择；
- 每轮可展开的读取历史、实验假设、本轮修改、PyTRiO/Token、门控结果和资源记录。

## 三任务摘要

| 任务 | 轮次 | 最终采用 | 确认样本 | CPU秒 | 运行秒 |
|---|---:|---|---:|---:|---:|
| Battery容量回归 | 10/10 | 第3轮模型 | 547 | 65.656250 | 95.868767 |
| Hydraulic蓄能器分类 | 10/10 | 第2轮模型 | 541 | 44.281250 | 74.710762 |
| Mill VB回归 | 10/10 | 初始父模型 | 29 | 65.687500 | 124.723535 |

“最终采用”表示Harness最终checkpoint的来源，不表示该轮在独立确认集上最优。A4的独立确认结论仍是三个任务最佳均为静态父模型，严格改善0/3。

## 产物与校验

- HTML：`D:/brace-msi-unseen/UNSEEN-SIM-001-A4/platform-style-report.html`
  - SHA-256：`F9EFD518AD32BECF350197C2FDBDFF5528AA91E625792CDC0D1A6A1E5A5EC798`
- JSON：`D:/brace-msi-unseen/UNSEEN-SIM-001-A4/platform-style-report.json`
  - SHA-256：`BC5CCAF5596E30FD658D17A0A693DFEBD6D2A2062CAEE4BA0AE0D5F71FDD65FE`
- 页面契约：三任务、各10轮、30个可展开记录；规定字段齐全；敏感标记扫描通过。
- 生成器专项测试：`tests/system/test_platform_style_report.py`。
- 当前HEAD完整回归：`385 passed in 156.71s`。

## 证据边界

页面始终使用“本地独立确认集指标（非官方）”，不得替换为“隐藏测试指标”。其版式只复用官方报告的信息要素，不是官方页面、官方评分或隐藏评测结果。
