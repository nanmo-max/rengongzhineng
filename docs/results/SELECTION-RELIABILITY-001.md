# SELECTION-RELIABILITY-001 结果

## 结论

选择可靠性代码门已通过，未产生新性能结论或新Release Candidate。

## 完成内容

- 唯一MetricContract，指标—方向冲突和未知指标失败关闭。
- 父/候选分别携带validation指纹；不同作用域不得计算收益。
- Harness计算主辅指标方向、有向收益和关系；显式`rmse_nasa`合同才启用NASA。
- Qwen requested decision与Harness applied decision分离；退化候选的deploy请求被确定性保留父模型。
- 非有限候选指标仍完成第二次模型调用、state和finish，但不提交非法候选。
- state v2保存父、候选、选中artifact ID及checkpoint摘要；v1记录显式标记legacy；best_stable在无合法恢复证据时保持null。
- 不同作用域历史不向Qwen暴露旧指标。
- 阶段计时使用互斥、脱敏字段并标记scope、excluded和未归因时间；finish ACK只写stderr聚合行。

## 验证证据

- 红灯：初始专项出现5个预期失败；后续新增scope、NaN、迁移、NASA和计时红灯。
- 正式运行核：`D:\\anaconda3\\python.exe -m pytest -q tests/formal_runtime --tb=short` → `50 passed in 1.43s`。
- 完整回归：`D:\\anaconda3\\python.exe -m pytest -q --tb=short` → `487 passed in 143.52s`。
- 代码提交：`afa9038 fix: enforce metric-consistent model selection`。
- 独立复审：第一次7项P1全部修复，最终复审无剩余P0/P1。

## 未完成与边界

- 未运行A/B/C训练矩阵，不能声称性能提高或泛化改善。
- 未构建Docker、未生成新归档、未上传平台、未消耗试运行。
- 未调用远程PyTRiO，未训练Sampler，未同步SwanLab。
- best_stable历史artifact恢复、有限探索策略和recipe反馈属于下一任务。
