# OFFICIAL-RULES-ALIGNED-DEV-001 结果

## 结论边界

这是依据2026-11-11平台截图完成的本地公开数据开发实验，不是平台试运行、正式评测或排行榜成绩。三任务初始检查点由本地训练得到，虽然参数量与平台公布值精确一致，仍始终标记为`official_checkpoint=false`。实验未使用SwanLab、外部API、平台次数或既有密封段。

执行代码提交为`512d477`，报告生成提交为`9c7bdba`。机器产物位于`D:/brace-msi-official-dev/OFFICIAL-RULES-ALIGNED-DEV-001/`；`validation.json`为`valid=true`，`background.stderr.log`为空。

## 数据与运行验收

| 任务 | 初训样本 | 开发样本 | 特征 | 开发轮次 | 密封批次 | 本地检查点参数量 |
|---|---:|---:|---:|---:|---:|---:|
| Gas | 3,275 | 6,271 | 128 | 10 | 0 | 4,326 |
| Bearing | 7,032 | 1,679 | 25 | 10 | 0 | 865 |
| Engine | 11,942 | 4,196 | 24 | 10 | 0 | 833 |

前三个静态实验完成后生成`first-three-health.json`并通过有限指标、10轮和零候选检查。随后PID 6084从相同运行根断点续跑并完成9/9实验；运行限制为4个逻辑CPU，观测到的候选操作边界峰值RSS不超过152,375,296字节。

## 配对结果

正值“相对静态改善”始终表示更好；分类为Macro-F1增加量，回归为RMSE减少量。资源与性能分开报告，没有推算未公开的官方综合分。

| 任务 | 策略 | 主指标 | 相对静态改善 | 真实候选 | 上线 | 候选CPU秒 | 训练样本 |
|---|---|---:|---:|---:|---:|---:|---:|
| Gas | static | 0.668681 Macro-F1 | 0 | 0 | 0 | 0 | 0 |
| Gas | performance-triggered | 0.704015 Macro-F1 | +0.035334 | 10 | 4 | 0.015625 | 4,701 |
| Gas | BRACE | 0.898620 Macro-F1 | +0.229939 | 10 | 10 | 16.828125 | 44,420 |
| Bearing | static | 419.026853 RMSE | 0 | 0 | 0 | 0 | 0 |
| Bearing | performance-triggered | 419.026853 RMSE | 0 | 0 | 0 | 0 | 0 |
| Bearing | BRACE | 454.113161 RMSE | -35.086308 | 10 | 3 | 10.859375 | 49,398 |
| Engine | static | 22.067446 RMSE | 0 | 0 | 0 | 0 | 0 |
| Engine | performance-triggered | 22.067035 RMSE | +0.000411 | 3 | 1 | 0 | 651 |
| Engine | BRACE | 21.818513 RMSE | +0.248934 | 5 | 3 | 4.937500 | 22,493 |

## 失败分析与冻结建议

- Gas：BRACE改善最大，但比简单策略多使用39,719个候选训练样本；保留为平台检查点到达后的优先候选，不将本地成本收益外推为官方得分。
- Engine：BRACE的RMSE改善为0.248934，幅度较小；保留为待平台检查点复验的暂定候选，不能宣称稳定优势。
- Bearing：BRACE被静态和简单策略支配。10次回放候选中3次通过当前批次验证门控，但累计RMSE反而增加35.086308，说明当前局部验证收益不能可靠预测后续轨迹收益。平台接入的安全默认应保持静态模型，直到官方检查点/切分证明更新有正收益。
- 不基于同一开发流继续调参重跑。下一轮只在平台训练包、官方初始权重和正式切分到达后，以独立实验ID复验；这避免把开发流反复用于门控阈值选型。

## 可核验证据

- 配置：`configs/official_rules_aligned_dev.json`
- 入口：`scripts/run_official_rules_aligned.py`
- 机器状态：`pipeline-status.json`、`status.json`、`validation.json`
- 数据审计：`source-hashes.json`、`stream-audit.json`
- 运行证据：9个`experiments/*/result.json`、`audit.jsonl`和`final-model.pkl`
- 汇总：`summary.json`、`report.md`、`report.html`
- 自动测试：`D:\anaconda3\python.exe -m pytest -q --tb=short`，116项通过
