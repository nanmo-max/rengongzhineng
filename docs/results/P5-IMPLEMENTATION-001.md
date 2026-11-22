# P5-IMPLEMENTATION-001 第一阶段实施报告

## 结论

状态：`PHASE1_PASS / STOP_FOR_HUMAN_REVIEW`

本阶段在独立分支`codex/p5-implementation-001`实现了接口冻结、漂移监测统计核心、运行级alpha账本和参考状态机。没有接入诊断归因逻辑、Qwen、训练器、模型选择器、Docker或正式RC。

## 实现位置

| 能力 | 实现位置 |
| --- | --- |
| `DriftReport`、`FeatureDrift`、状态枚举 | `src/brace_formal/drift.py:15` |
| `DiagnosisReport`接口（无归因逻辑） | `src/brace_formal/diagnosis.py:10` |
| BY保守多重校正 | `src/brace_formal/drift.py:115` |
| 显著性与效应量双门 | `src/brace_formal/drift.py:134` |
| 特征内位置/尺度/Wasserstein/KS联合统计 | `src/brace_formal/drift.py`中的`_feature_statistics` |
| 同步完整块置换与跨边界失败关闭 | `src/brace_formal/drift.py:254` |
| maxT与BY校准、经验p值分辨率检查 | `src/brace_formal/drift.py:339` |
| alpha-spending | `src/brace_formal/drift_state.py:49` |
| `DriftState`序列化与污染校验 | `src/brace_formal/drift_state.py:80` |
| 漂移确认、冻结、恢复和新基准重建 | `src/brace_formal/drift_state.py:185` |

## 测试证据

严格执行测试先行：

- 接口测试先因三个模块不存在而`4 failed`，实现后`4 passed`。
- 统计测试先因BY、效应量门和监测器不存在而`6 failed`，实现后通过。
- 状态机测试先因alpha-spending和状态转移不存在而`7 failed`，实现后通过。
- 不等长完整块最初被错误拒绝，新增回归测试先失败，再移除非必要等长限制。
- 损坏状态把同一窗口放入多个参考池的测试先失败，补充反序列化污染校验后通过。

最终专项：`24 passed`。覆盖：

- BY已知三假设结果和顺序等变性；
- 同步块置换maxT与相关特征；
- 不等长但完整块；
- 跨窗口块失败关闭；
- 经验p值分辨率不足不得报告稳定；
- 效应量双门；
- 正仿射变换与特征置换属性；
- 已知/开放时域alpha-spending；
- WARNING/CONFIRMED污染防护；
- 短暂波动恢复、重复波动、持续新状态原子重建；
- 状态序列化、重复窗口和池重叠失败关闭。

完整回归：

```text
python -m pytest -q
676 passed in 167.54s
```

`compileall`通过。当前锁定环境没有安装Ruff，本阶段没有安装或升级依赖，因此不声明Ruff通过。

## 资源实测

环境：Python 3.12.7，AMD Ryzen 7 7800X3D（8核），可见内存约31.2 GiB。合成矩阵为128维、参考/当前各80行、40个完整块、2047次同步置换，`alpha_window=0.005`，最小经验p值`1/2048`。

| 运行 | CPU | 墙钟 | 峰值RSS | RSS增量 | 结果 |
| --- | ---: | ---: | ---: | ---: | --- |
| A1朴素逐特征实现 | 45.156 s | 43.885 s | 75,898,880 B | 32,370,688 B | 超过30秒目标，负证据保留 |
| A2等价向量化实现 | 6.906 s | 5.546 s | 76,218,368 B | 31,383,552 B | 通过30秒和1 GiB目标 |

A2没有减少置换次数、alpha分辨率、统计量或特征数；同一固定种子仍只选择注入漂移的一个特征。

## 冻结RC保护

- 冻结归档：`D:/brace-msi-release/COMPETITION-CORE-RC-001/harness.tar`
- 大小：`81,232,384`字节
- SHA-256：`B7BA01BCC8A60502896082B58578B56C60C539A5460BB373285FF0ABE4503E30`
- 最后写入时间仍为`2026-11-21T06:17:33.2455870Z`
- 相对实施基线`0a592cf`，`Dockerfile.formal`、`model.py`、`round_core.py`、`selection.py`、`submission.py`、官方`contest_harness`和`brace_msi/official_sdk.py`均为零差异。

## 明确未完成

- 没有实现诊断归因算法；本阶段只冻结`DiagnosisReport`接口。
- 没有把P5接入`round_core.py`、训练器、ArtifactSelector或正式镜像。
- 没有调用Qwen、PyTRiO或SwanLab。
- 没有运行工业模型训练、读取public validation、XJTU密封或隐藏数据。
- 没有完成P5完整八类漂移、误报区间和诊断消融矩阵；这些属于后续审批阶段。
- 没有构建Docker、上传平台或消耗官方试运行次数。

因此，本报告只证明第一阶段统计与状态核心通过本地专项和回归，不证明真实工业漂移效果，也不产生新RC。
