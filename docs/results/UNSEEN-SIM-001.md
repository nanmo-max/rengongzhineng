# UNSEEN-SIM-001 三个未见工业任务本地正式流程复演

## 结论

`UNSEEN-SIM-001-A4`完成了三任务各10轮、真实Qwen3.5-4B PyTRiO建议、原生父链续训、门控、保留、独立确认和资源记录。协议门与Agent门通过，但性能门失败：三个任务的最佳确认轮均为静态父模型（round 0），最终严格改善为0/3。

本结果证明当前系统能运行，不证明当前未知任务策略具有竞争泛化能力。不得把本结果写成官方成绩，也不得使用已打开的confirmation继续调参重跑。

## 数据与边界

- 原始只读根：`C:/Users/Administrator/Desktop/人工智能创新大赛/模拟正式数据集`
- Battery：NASA Battery Aging Archive，预测放电容量；按电池ID隔离。
- Hydraulic：UCI液压系统，预测蓄能器状态；按连续目标运行段隔离。
- Mill：NASA/UC Berkeley Mill，预测实测刀具磨损VB；按case隔离。
- 三任务均以bootstrap分区建立`simulated_parent=true`兼容MLP，adaptation分区执行10轮，confirmation只在策略冻结后评估。
- 这不是官方数据、官方父checkpoint、隐藏评测或正式试运行；官方试运行新增消耗0次，SwanLab同步0次。

## 尝试记录

| 尝试 | 状态 | 说明 |
|---|---|---|
| A1 | `FAILED_DATA_QUALITY_BEFORE_TRAINING` | Battery发现25条空`Capacity`记录；训练前失败并保留。 |
| A2 | `INVALID_EVIDENCE_ID_MISMATCH` | 完成流程但报告实验ID错误，只保留诊断，不作有效证据。 |
| A3 | `COMPLETED_NEGATIVE_DETERMINISTIC_CONTROL` | 确定性对照完成30轮；协议通过，严格改善0/3。 |
| A4 | `COMPLETED_AGENT_PASS_PERFORMANCE_FAIL` | PyTRiO/Qwen正式对照完成30轮；Agent门通过，性能门失败。 |

## A4真实性与Agent证据

- 模型：`Qwen/Qwen3.5-4B`基础模型；未使用Sampler LoRA。
- PyTRiO有效响应16次，接受并执行的结构化建议15次。
- 输入Token 8,100，输出Token 3,470；总墙钟322.962秒。
- 每轮最多一次候选；Qwen只能表达训练或retain意图，轮次、epoch、学习率、Gate和父链仍由确定性Harness约束。
- 三任务共30轮，父链、分组隔离、64 MiB产物门和协议检查全部通过。

## 确认集结果

| 任务 | 静态父模型 | A4最终 | 候选/部署 | 最佳轮 | 结论 |
|---|---:|---:|---:|---:|---|
| Battery容量回归 | RMSE 0.335763；MAE 0.162168 | RMSE 0.409475；MAE 0.239151 | 5 / 1 | 0 | 退化 |
| Hydraulic蓄能器分类 | Macro-F1 0.238964；Accuracy 0.332717 | Macro-F1 0.092620；Accuracy 0.227357 | 9 / 1 | 0 | 退化 |
| Mill VB回归 | RMSE 0.392140；MAE 0.265939 | RMSE 0.392140；MAE 0.265939 | 4 / 0 | 0 | 持平 |

A4与A3的最终性能完全相同。PyTRiO改变了部分训练/retain意图，但没有修复同批Gate向跨设备、跨工况确认集迁移失败的问题。

## 机器证据

- A3：`D:/brace-msi-unseen/UNSEEN-SIM-001-A3/report.json`
  - JSON SHA-256：`F6654F8FC7651F1CAB1F4D06C57EEAACEA408DA598B1BEA6E53C245150769BE6`
  - HTML SHA-256：`5BEAC4BFE1432C8DDDD149FF232C2E25597D4F8C6B263B059592EBC7C962B2E6`
- A4：`D:/brace-msi-unseen/UNSEEN-SIM-001-A4/report.json`
  - JSON SHA-256：`AA3CA8F78183F36656647BDCC9FCC35F280FFC9346F297EBB76CD1ACA6AEE8D7`
  - HTML SHA-256：`A01655111B7530626016B9564CE6A5F96C2902ECF9D9C880F27130984E1E92B8`
- A4三个round 10 checkpoint已独立加载并复算，指标与报告一致；大小分别为71,380、187,392、73,280字节。
- 敏感字段扫描未发现`api_key`、`authorization`或`trio_aq`。
- 当前代码完整回归：`383 passed in 171.63s`。

## 失败分析与后续边界

主要失败不是PyTRiO不可用，而是部署证据不能代表未来设备/工况：Battery和Hydraulic候选在当前批Gate上通过，却在独立confirmation上退化。下一代策略若获新任务授权，应优先建立任务契约驱动的组/时间前向验证或未知任务默认不部署规则；不能靠增加Qwen调用次数解决。

RC7与历史结果保持冻结。当前源码已进入`0.7.1rc1`准备态，但在新Docker构建与4核8GB验收前，不得替代已验证的`0.7.0rc1`上传归档。
