# PERFORMANCE-METHOD-PILOT-001 原生方法趋势筛选

## 结论

只保留一个开发级变更：分类采用`balanced_current_e3 + native_recent_e3`复合候选组合。前者相对后者同时改变了训练范围和损失，因此不能把收益归因于“类平衡单因素”。回归Huber、非对称Huber和偏差校正均没有在三项性能/最差阶段/资源门上稳定胜出，正式候选继续使用A6既有回归recipe。

该结论来自同一开发代理流，不是隐藏成绩或独立泛化证明；D-088的一次性独立替代流验收仍是正式RC前置。

## A1 单因素趋势

| 任务 | 方法 | 平均对静态有向收益 | 最差收益 | 胜率 | CPU秒 |
|---|---|---:|---:|---:|---:|
| A | native_recent_e3 | +0.386974 Macro-F1 | +0.017072 | 9/9 | 1.109 |
| A | balanced_current_e3 | **+0.399821** | **+0.023635** | 9/9 | **0.250** |
| A | balanced_recent_e3 | +0.370443 | +0.023635 | 9/9 | 0.953 |
| B | native_current_e3_lr3 | **+287.436213 RMSE降低** | +45.370270 | 9/9 | 0.125 |
| B | asymmetric_current_e3_lr3 | +284.064598 | **+53.907658** | 9/9 | 0.125 |
| C | soup_current_e3_alpha0.25 | **+1.007474 RMSE降低** | **-0.196010** | 6/9 | 0.469 |
| C | 最佳新稳健候选huber_recent_e3 | +0.051917 | -3.080878 | 4/9 | 0.531 |

B的非对称Huber改善了最差RMSE阶段和代理NASA代价，但平均RMSE略逊于原生高强度更新；它只保留为研究证据，没有替换正式回归候选。C的新稳健方法均未超过既有权重插值。

## A2 单因素偏差校正

C的0.10/0.25向下偏差校正均失败：平均RMSE收益分别从基线`+1.007474`降至`+0.914193/+0.736587`，NASA改善率从`39.54%`降至`25.25%/10.24%`，最差阶段也扩大。该方法淘汰。

## A3 负结果

把全部新回归方法直接接入十轮矩阵后，B最差相对阶段退化`-5.9527%`，超过灾难门；recipe反馈C分支还暴露新方法冷却后错误回退到旧方法族的执行缺口。A3 `valid=false`，只保留失败证据，不晋级。

## A4 最小组合

A4只改变分类候选，B/C精确恢复A6语义。`bounded_exploration`结果：

| 任务 | A6平均有向收益 | A4平均有向收益 | A6最差相对收益 | A4最差相对收益 |
|---|---:|---:|---:|---:|
| A | +0.312990 | **+0.360481** | -0.5470% | **0.0000%** |
| B | +89.198667 | +89.198667 | -0.0128% | -0.0128% |
| C | +0.173614 | +0.173614 | -1.3983% | -1.3983% |

B/C最终checkpoint SHA-256与A6逐项相同；A4 120/120轮、12/12最终checkpoint绑定、0个5%灾难任务，开发晋级门通过。墙钟42.29秒，三任务累计候选CPU约3.11秒；Token、SwanLab同步和官方试运行均为0。

独立复审未发现技术P0；B/C四策略8条链在排除计时、RSS和输出路径后与A6完全一致。方法/矩阵专项`26 passed`，完整回归`518 passed in 142.91s`。

## 机器证据

- A1：`D:/brace-msi-performance-pilot/PERFORMANCE-METHOD-PILOT-001-A1/summary.json`，SHA-256 `98C75FB2A992BCC6068486E73219E8E29EB85B30DABE83683FC4836AF4A95E2F`
- A2：`D:/brace-msi-performance-pilot/PERFORMANCE-METHOD-PILOT-001-A2/summary.json`，SHA-256 `EAC9D9752E97588F8909C0760526AB91A0D07EAFE7CEC2FC41C21C14EF7E4820`
- A3：`D:/brace-msi-performance-pilot/PERFORMANCE-METHOD-PILOT-001-A3/summary.json`，SHA-256 `2EC495B4DCAB7EA1789EC101F90A0B0DACA225E029D27EEDE32921240D13113F`
- A4：`D:/brace-msi-performance-pilot/PERFORMANCE-METHOD-PILOT-001-A4/summary.json`，SHA-256 `4237A9F445E2E42456D3FD434B579D246046274A0B956278E36D764E110637BD`

## 边界

- 未读取confirmation/public validation。
- 未调用远程PyTRiO、未同步SwanLab、未消耗官方试运行。
- 研究辅助训练函数未进入正式镜像；正式集成仍需Advisor验收、独立替代流和容器门。
