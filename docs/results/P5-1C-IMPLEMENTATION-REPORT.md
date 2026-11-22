# P5-1C 限时定向修复实施报告

## 1. 结论

状态：`COMPLETED_PARTIAL_STATISTICAL_GATES`。

在不触碰冻结RC、P5-1A最终配置/种子/结果、比赛数据、远程模型和Docker的前提下，已完成四项定向修复中的三项工程闭环，并部分改善尺度统计可观测性：

- 参考池污染：已修复。`no_drift_detected`、`insufficient_evidence`、`stable`和`confirmed`语义分开，前两者不能进入参考池。
- 统计贡献收据：已完成。每特征保存location、scale、Wasserstein、KS、missingness的原值、标准化分数、经验p值和特征内贡献。
- group/time hints：已完成。只接受显式输入；缺失时记录降级，不用行号伪造组身份。
- maxT/BY降级：已完成。BY经验p值无法达到第一秩阈值时返回`INSUFFICIENT_CALIBRATION`，而不是`STABLE`。
- 方差/噪声功效：仍未达到开发门。A1中等方差检出率为0.50/0.50/0.25，噪声三维均为0；A2 Brown-Forsythe尝试更差，已回退并保留负证据。

因此本任务不能宣称P5-1A统计门已通过，也不能据此进入正式RC。它可以作为后续诊断归因集成前的工程核心候选，但尺度/噪声检测须列为显式限制。

## 2. 实现位置

| 能力 | 实现 |
|---|---|
| 非准入观察与参考池隔离 | `src/brace_formal/drift_state.py:22-23,95,224-230` |
| 五统计贡献收据 | `src/brace_formal/drift.py:24-72,651,685-701` |
| 稀疏极端值质量收据 | `src/brace_formal/drift.py:112-126,235-277` |
| 合法组组成证据 | `src/brace_formal/drift.py:78-96,426-458,608-616` |
| 时间提示审计 | `src/brace_formal/drift.py:98-109,461-481` |
| BY第一秩分辨率失败关闭 | `src/brace_formal/drift.py:560-580` |
| IQR/MAD尺度互补 | `src/brace_formal/drift.py:319-330,369-375` |
| 新开发验证器 | `scripts/run_p5_1c_targeted_validation.py` |

## 3. 测试与验证

- P5-1C新增专项：11项测试，覆盖参考准入、异常、短暂波动、恢复、持续漂移重建、五统计收据、组/时间提示、BY分辨率和尺度收据。
- 漂移相关专项回归：46项通过。
- 全仓回归：`698 passed in 168.92s`。
- `python -m compileall -q src scripts/run_p5_1c_targeted_validation.py`：通过。
- `git diff --check`：通过。

## 4. 保护验证

| 证据 | SHA-256 | 状态 |
|---|---|---|
| P5-1A结果JSON | `5D4090044B2E9D0C3B1785DD8D01FBEF801BBDEB82A150E2C8C1D3431DE77163` | 未变化 |
| P5-1A冻结配置 | `ED419C1DA9A936AF3F0545E023AA35C67D9CDFA81BD60E518270D613E480D97C` | 未变化 |
| P5-1A原始最终收据 | `E6A90496A23CAD8525A710680E6C50E59252C12AD066C883FFABCBD7DB94B38F` | 未变化 |
| 0.11.0rc1冻结归档 | `B7BA01BCC8A60502896082B58578B56C60C539A5460BB373285FF0ABE4503E30` | 未变化 |

没有读取受限validation、XJTU密封或隐藏数据；没有训练工业模型、调用Qwen/PyTRiO/SwanLab、构建Docker、上传平台或消耗试运行次数。

## 5. 停止判断

按6小时限时规则停止。已完成的可靠修复保留；A2负向算法不保留；不继续扩大尺度检测算法复杂度，不进入诊断归因、Qwen、Docker或RC发布。

