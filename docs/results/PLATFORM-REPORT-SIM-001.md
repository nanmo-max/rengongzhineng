# PLATFORM-REPORT-SIM-001 官方报告形态本地复演

## 目的与边界

根据O-PLATFORM-010的正式试运行页面字段，在不使用官方试运行机会、不修改冻结checkpoint的前提下，对`0.7.0rc1`已完成的三任务容器轮次做一次报告形态复演。

本次只读取历史暴露的官方公开validation，逐轮评估已冻结checkpoint并模拟“采用本轮/保留此前最佳”展示。它不是隐藏测试、官方成绩或新的参数选择，不能用于重新调优RC。

## 完整结果

| 任务 | 轮次 | 本地评估样本 | 模拟最终采用 | 模拟采用指标 | 容器CPU秒 | 峰值RSS |
|---|---:|---:|---:|---|---:|---:|
| A | 10/10 | 1,244 | 第9轮 | Accuracy 0.885852；Macro-F1 0.725695 | 0.644193 | 94,965,760 |
| B | 10/10 | 1,679 | 第1轮 | MAE 538.776700；RMSE 660.076488 | 4.157719 | 113,430,528 |
| C | 10/10 | 23,049 | 第9轮 | MAE 38.091484；RMSE 51.949287；NASA 4,026,364,609.895953 | 21.011016 | 238,686,208 |

- 逐轮评估总样本：25,972；与官方旧隐藏测试14,773条不同，这是公开validation规模差异，不是协议错误。
- A第1—8轮均保留父模型，第9轮部署后提升；B第1轮部署后其余候选均被门控拒绝；C第9轮部署后提升。
- 三任务均有10轮记录、每轮checkpoint、动作、是否训练、是否部署、CPU、墙钟、RSS和Token字段。
- 本次确定性容器验收Token为0；这不冒充在线PyTRiO成功。在线状态仍以`NATIVE-COMPETITIVE-RC-001-PYTRIO-SWANLAB.md`为准。

## 产物

- 机器报告：`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM/report.json`
- 静态HTML：`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM/report.html`
- JSON SHA-256：`5137E3C85A2273EC56DE0A6B786DA2CABCB7C9F082A90A09642C68EF37F92CC8`
- HTML SHA-256：`AB9D81BD4285E4D652E4EEFA503D8196CA0AE463AE69264E2D4F44C0AC182F80`
- 生成工具：`scripts/simulate_platform_report.py`

## 验收结论

`PASS_LOCAL_PROTOCOL_SIMULATION`：已按官方页面可见字段完成三任务全十轮报告复演，轮次选择与冻结性能边界一致；未消耗新的平台试运行机会。正式隐藏指标、平台Token和真实运行时仍只能由下一次官方试运行给出。
