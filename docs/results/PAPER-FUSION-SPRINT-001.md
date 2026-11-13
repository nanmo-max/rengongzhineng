# PAPER-FUSION-SPRINT-001 结果报告

## 结论

本轮按预注册协议完成三项方法来源的有界复现与组合。公开 validation 仅在候选冻结后打开一次，机器校验为 `valid=true`。结果是**混合结论**：Engine C 的论文融合候选显著优于 RC3；Gas A 与 Bearing B 未超过 RC3，已由 SafetyGate 拒绝替换。

安全候选因此不是“全部换新”，而是：A/B 继续使用 RC3，C 使用 PaperFusion。30%进取目标未达到，未通过重复读取公开 validation 继续调参。

| 任务 | 静态基线 | RC3 | PaperFusion | 相对静态改善 | 相对RC3改善 | 最终选择 |
|---|---:|---:|---:|---:|---:|---|
| Gas A Macro-F1 ↑ | 0.714030 | 0.725695 | 0.687918 | -3.66% | -5.21% | RC3 |
| Bearing B RMSE ↓ | 681.159833 | 637.180224 | 644.113606 | 5.44% | -1.09% | RC3 |
| Engine C RMSE ↓ | 52.868573 | 51.635999 | **42.330230** | **19.93%** | **18.02%** | PaperFusion |

这些数值来自历史暴露的公开 validation，不是隐藏测试或官方成绩。

## 方法来源与复现边界

| 来源 | 本轮复现内容 | 代码/许可证边界 | 结果 |
|---|---|---|---|
| Lin & Zhan, *Informatics* 2026，Gas知识蒸馏 | 多教师软目标与小MLP学生；所有变换仅在训练折拟合 | 作者仓库 `abob7/gas-drift` 声明MIT；未复制其全批次scaler，因为会违反因果协议 | 学生内部Macro-F1 0.869930，低于教师集成0.978493；公开验证同样不足，拒绝上线 |
| Özcan, *Scientific Reports* 2025，C-MAPSS树模型集成 | 以scikit-learn重建异构CPU模型池与加权集成，不复制作者代码 | 作者仓库README声明代码MIT；本轮只使用方法思想 | Engine公开RMSE 42.330230，显著优于RC3 |
| Li et al., JMLR 2018，Hyperband | 有界Successive Halving，低预算淘汰后只全量训练4个finalist | 使用论文算法思想，无第三方代码迁移 | 将每任务候选限制为8个并保留完整淘汰记录 |

详细来源与限制以 `docs/SOURCE_REGISTRY.md` 的 P-PAPER-001 至 P-PAPER-003 为准。期刊分区未获得权威证据的来源不标记“一区”。

## 协议

- 原始官方训练包只读；所有输出位于 `D:/brace-msi-paper-fusion/PAPER-FUSION-SPRINT-001/`。
- Gas按类别分层做3折内部开发；Bearing按轴承分组；Engine按发动机分组，组身份不跨折。
- Bearing只使用当前snapshot及原始特征；Engine只使用当前cycle、历史差分和截至当前时刻的扩展均值，不使用未来轨迹长度。
- 公开 validation 在模型、权重和配置冻结后仅打开一次；`validation-open.lock` 与 `summary.json` 保留计数。
- A/B/C都先比较独立教师，再拟合非负归一化集成权重。Gas额外验证蒸馏学生。
- 最终部署门只允许相对RC3严格改善的候选进入混合版本。

## 内部开发与消融

| 任务 | 内部指标 | 单模型/模块证据 | 组合结论 |
|---|---:|---|---|
| A | Ensemble Macro-F1 0.978493 | 最佳线性教师0.986865；蒸馏学生0.869930 | 随机分层内部指标不能代表跨批次漂移；KD无独立正贡献 |
| B | Ensemble RMSE 1546.212091 | 最佳ExtraTrees 1518.256968 | 不同轴承寿命差异巨大；公开结果只略优于静态且落后RC3 |
| C | Ensemble RMSE 47.298452 | HGB 49.772111/49.876697，ExtraTrees 50.314069，MLP 47.387189 | 异构组合略优于最佳单模型，且公开验证明显提升 |

因此，本轮没有把“多模块拼接”包装成普遍成功：Gas蒸馏为负，Bearing组合未越过RC3，只有Engine的因果历史特征加异构集成通过部署门。

## 资源

| 任务 | CPU秒 | 墙钟秒 | 峰值RSS | 模型产物 |
|---|---:|---:|---:|---:|
| A | 9.72 | 3.92 | 120,385,536 B | 1,144,843 B |
| B | 64.56 | 36.35 | 386,863,104 B | 47,638,967 B |
| C | 979.44 | 617.63 | 3,019,251,712 B | 456,540,161 B |

全部低于4核8GB目标的内存上限。模型权重不进入镜像；镜像只包含训练代码和配置，运行时在挂载目录生成候选。

## 失败分析与下一步

1. Gas内部随机分层接近满分、公开跨批次却下降，说明主要瓶颈是域漂移而非源域拟合。继续扩大同分布模型池只会增加过拟合风险；后续应在新的合法开发批次上研究因果域适配或漂移校准，而不是重开本次validation。
2. Bearing按轴承分组的内部RMSE很高，说明寿命尺度/工况异质性强。当前因果snapshot特征不足；下一步需要官方批次语义或新的未暴露确认数据，才能验证归一化退化阶段、稳健目标或轨迹表示。
3. Engine在因果历史特征和异构模型组合下获得19.93%相对基线改善，是本轮唯一通过门控的方法。下一轮最有价值的方向是减少模型体积与训练CPU，同时保持一次性确认指标，而不是继续追求已暴露验证集上的30%。

## 机器证据

- 输出：`D:/brace-msi-paper-fusion/PAPER-FUSION-SPRINT-001/`
- 结果摘要SHA-256：`e323b2d89fc01873d86882020d9dd7bc9e6237136bf215385fba7d4432c33296`
- 混合门控：`D:/brace-msi-paper-fusion/PAPER-FUSION-SPRINT-001/hybrid-candidate.json`
- 验证命令：`python scripts/run_paper_fusion_sprint.py --config configs/paper_fusion_sprint.json --output D:/brace-msi-paper-fusion/PAPER-FUSION-SPRINT-001 --validate-only`
- 验证结果：`{"valid": true, "stage": "completed", "errors": []}`
