# P5-1C 根因—修复对应表

| P5-1B根因 | 最小修复 | 测试/运行证据 | 结果 | 副作用或限制 |
|---|---|---|---|---|
| R2：未检出被等同于稳定并进入参考池 | 新增`NO_DRIFT_DETECTED`和`INSUFFICIENT_EVIDENCE`；记录`non_admissible_window_ids`；只有显式`STABLE`进入候选/参考池 | `test_no_drift_and_insufficient_evidence_never_enter_reference_pool`；异常、短暂、恢复、重建回归 | PASS | 正向稳定证据仍需上层依据合法数据契约提供，不能从“不显著”自动推出 |
| R1：只见综合分，无法判断尺度/噪声失败来源 | 保存五种统计量逐项原值、标准化分、经验p和贡献；scale取IQR/MAD对数比最大值 | `test_feature_receipt_preserves_each_statistic_contribution`；A1 72/72收据完整 | PASS receipts / PARTIAL power | 128维方差和全部噪声开发门未过 |
| R3：组组成变化未进入输入契约 | 接受显式group identity与time hints；组组成用同步块置换TV证据；缺失时显式降级 | 两项group/time单测；A1三维组组成检出率均1.0 | PASS | 组身份必须由合法数据契约提供；time hints目前只审计可用性和单调性，不单独触发漂移 |
| R4：BY仍依赖maxT置换路径，分辨率不足却可能报稳定 | 按`m * H_m / alpha_window`计算BY第一秩最低置换数；不足即`INSUFFICIENT_CALIBRATION` | `test_by_reports_insufficient_when_empirical_resolution_cannot_cross_rank_one` | PASS | 尚未实现无交换性条件下的合法外部边缘p值提供器，因此BY仍是保守降级而非功效替代 |
| R5：相关结构每格n=6导致区间不足 | 本任务不修改；属于验证规模问题而非代码缺陷 | P5-1B数学分析 | DEFER | 独立最终验收每格至少35条流，未在限时修复内执行 |

## 被拒绝的修复

Brown-Forsythe绝对偏差均值差曾作为A2唯一算法变更。A2使用全新`623001..624072`种子，开发检查由A1的15/19下降为14/19，中等方差与噪声没有可靠改善，故代码已回退。其原始收据与哈希保留在机器结果中。
