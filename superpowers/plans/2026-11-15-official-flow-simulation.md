# OFFICIAL-FLOW-SIM-001 实施计划

1. 红测：验证旧按行切分、预测前标签可见、组跨轮、确认集可被策略读取等行为被新契约拒绝。
2. 实现不可变`StreamPlan`与Gas/Bearing/Engine任务流构造器，加入源哈希、ID/特征/组交叉硬门和输入顺序不变性。
3. 为`start_round`增加向后兼容的独立Update/Gate入口，证明Gate不进入训练、Anchor和Replay。
4. 实现预测封存与`ScoreVault`，保证先预测、后反馈，外部Prequential分数不进入动作策略。
5. 实现十轮编排、一次性最终确认和官方要素机器报告；旧`run_ten_round_simulation`保留为历史兼容入口并显著标记低保真。
6. 运行三任务本地Smoke与完整模拟；记录CPU、RSS、Token、组/文件哈希、部署/拒绝和最终确认读取次数。
7. 运行专项、完整回归和证据一致性检查；更新SSOT、提交Git。正式隐藏测试和平台试运行继续外部阻塞。
