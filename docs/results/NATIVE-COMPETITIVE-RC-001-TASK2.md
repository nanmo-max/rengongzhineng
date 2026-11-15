# NATIVE-COMPETITIVE-RC-001 Task 2 证据

- 日期：2026-11-15
- 边界：仅使用官方公开train内部顺序；未读取公开validation，未使用官方试运行，未调用在线PyTRiO。
- 实现：竞争模式真实retain；第1/5/9轮有界候选；首轮无历史只训练不部署；任务尺度主辅指标Gate；Anchor与Replay相对风险门。
- 参数：A为`1 epoch / 1x LR`三次；B为`1 epoch / 1x`、`5 epoch / 3x`、`1 epoch / 0.3x`；C为`1 epoch / 1x`、`5 epoch / 1x`、`1 epoch / 0.3x`。
- 负证据：DEV-A1与DEV-A2显示早期局部门控会在B部署全历史退化候选，且C的微小RMSE收益可能伴随MAE退化，因此不以单批收益直接发布。
- 测试：`D:/anaconda3/python.exe -m pytest tests/platform_runtime/test_platform_runtime.py -q` → `32 passed in 23.54s`；`D:/anaconda3/python.exe -m pytest -q --tb=short` → `365 passed in 144.39s`。
- 下一步：运行DEV-A3训练内部十轮；只有其全历史安全才冻结配置并执行一次公开validation确认。
